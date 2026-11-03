"""Persistencia SQLite, snapshots y validación de campos editables."""
import sqlite3, json, os, pathlib, datetime, threading
from contextlib import contextmanager
from uuid import uuid4

DATA_DIR=pathlib.Path(os.getenv('DATA_DIR', pathlib.Path(__file__).resolve().parent/'data'))
DB_PATH=DATA_DIR/'argentex.sqlite3'
# Render Free tiene disco efímero. En modo remoto, Neon/Postgres guarda un
# snapshot consistente de SQLite después de cada operación de escritura.
# Este adaptador es para la etapa de testeo con un solo proceso/worker.
REMOTE_URL=os.getenv('DATABASE_URL', '').strip()
_DB_LOCK=threading.RLock()

def _remote_connect():
    if not REMOTE_URL: return None
    import psycopg
    return psycopg.connect(REMOTE_URL, connect_timeout=12)

def _restore_remote():
    if not REMOTE_URL:return
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with _remote_connect() as pg:
        pg.execute('CREATE TABLE IF NOT EXISTS app_snapshot (id integer PRIMARY KEY CHECK (id=1), sqlite_bytes bytea NOT NULL, updated_at timestamptz NOT NULL DEFAULT now())')
        result=pg.execute('SELECT sqlite_bytes FROM app_snapshot WHERE id=1').fetchone()
    if result:
        import tempfile
        fd, temp_name=tempfile.mkstemp(prefix='argentex-restore-',suffix='.sqlite',dir=DATA_DIR)
        try:
            with os.fdopen(fd, 'wb') as f:
                f.write(bytes(result[0]))
                f.flush();os.fsync(f.fileno())
            os.replace(temp_name, DB_PATH)
            # No se conservan archivos WAL efímeros después de un redeploy.
        finally:
            if os.path.exists(temp_name): os.unlink(temp_name)

def _save_remote(db):
    if not REMOTE_URL:return
    # Backup a memoria desde la conexión ya confirmada; captura también fotos.
    with sqlite3.connect(':memory:') as snapshot:
        db.backup(snapshot)
        raw=snapshot.serialize()
    with _remote_connect() as pg:
        pg.execute('INSERT INTO app_snapshot(id,sqlite_bytes,updated_at) VALUES(1,%s,now()) ON CONFLICT(id) DO UPDATE SET sqlite_bytes=excluded.sqlite_bytes,updated_at=excluded.updated_at', (raw,))


DEFAULT_SETTINGS={
 'rates_usd_kg': {'ropa':45,'perfumes':45,'calzado':45,'maquillaje':50,'vitaminas':50,'juguetes':50,'accesorios':50,'paletas_padel':50},
 'internal_shipping_usd':15,
 'internal_shipping_limit_kg':5,
 'weight_protection_pct':15,
 'min_protection_g':150,
 'rounding_g':100,
 'capture_market_gap_pct':45,
 'fx_max_age_hours':48,
}

SCHEMA='''
CREATE TABLE IF NOT EXISTS settings (id INTEGER PRIMARY KEY CHECK (id = 1), content TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS customers (id TEXT PRIMARY KEY, full_name TEXT NOT NULL, phone TEXT NOT NULL DEFAULT '', notes TEXT DEFAULT '', created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS orders (id TEXT PRIMARY KEY, customer_id TEXT REFERENCES customers(id) ON DELETE SET NULL, label TEXT NOT NULL DEFAULT '', status TEXT NOT NULL DEFAULT 'draft', outer_packaging_g INTEGER NOT NULL DEFAULT 0, tax_mode TEXT NOT NULL DEFAULT 'not_applicable', tax_rate REAL NOT NULL DEFAULT 0, us_shipping_override REAL, import_extra_usd REAL NOT NULL DEFAULT 0, notes TEXT DEFAULT '', price_override_usd REAL, approved_at TEXT, approved_fx_ars REAL, approved_sell_usd REAL, approved_cost_usd REAL, tax_reviewed INTEGER NOT NULL DEFAULT 0, import_cost_reviewed INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS items (id TEXT PRIMARY KEY, order_id TEXT NOT NULL REFERENCES orders(id) ON DELETE CASCADE, name TEXT NOT NULL, brand TEXT DEFAULT '', sku TEXT DEFAULT '', variant TEXT DEFAULT '', category TEXT NOT NULL, unit_price_usd REAL NOT NULL DEFAULT 0, qty INTEGER NOT NULL DEFAULT 1, unit_weight_g INTEGER NOT NULL DEFAULT 0, weight_source TEXT DEFAULT '', weight_verified INTEGER NOT NULL DEFAULT 0, photo BLOB, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS item_photos (id TEXT PRIMARY KEY, item_id TEXT NOT NULL REFERENCES items(id) ON DELETE CASCADE, role TEXT NOT NULL DEFAULT 'detalle', mime_type TEXT NOT NULL, data BLOB NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS market (id TEXT PRIMARY KEY, item_id TEXT NOT NULL REFERENCES items(id) ON DELETE CASCADE, source_name TEXT NOT NULL, source_url TEXT NOT NULL, price_ars REAL NOT NULL, shipping_ars REAL NOT NULL DEFAULT 0, same_sku INTEGER NOT NULL DEFAULT 0, brand_new INTEGER NOT NULL DEFAULT 0, original INTEGER NOT NULL DEFAULT 0, in_stock INTEGER NOT NULL DEFAULT 0, reputation_ok INTEGER NOT NULL DEFAULT 0, payment_verified INTEGER NOT NULL DEFAULT 0, shipping_verified INTEGER NOT NULL DEFAULT 0, conditions_note TEXT NOT NULL DEFAULT '', observed_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS fx_quotes (label TEXT PRIMARY KEY, sell_ars REAL NOT NULL, source_url TEXT NOT NULL, updated_at TEXT NOT NULL, fetched_at TEXT NOT NULL, kind TEXT NOT NULL DEFAULT 'api');
'''

def now(): return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds')
def new_id(): return uuid4().hex[:12]

@contextmanager
def connect():
    with _DB_LOCK:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        db=sqlite3.connect(DB_PATH, timeout=8)
        db.row_factory=sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON')
        db.execute('PRAGMA journal_mode=DELETE' if REMOTE_URL else 'PRAGMA journal_mode=WAL')
        try:
            yield db
            changed = db.total_changes > 0
            db.commit()
            if changed and REMOTE_URL:
                _save_remote(db)
        except:
            db.rollback()
            raise
        finally: db.close()

def init():
    with _DB_LOCK:
        _restore_remote()
    with connect() as db:
        db.executescript(SCHEMA)
        db.execute('INSERT OR IGNORE INTO settings(id, content) VALUES(1, ?)', (json.dumps(DEFAULT_SETTINGS),))
        columns={r['name'] for r in db.execute('PRAGMA table_info(orders)')}
        for name,sql in {'approved_sell_usd':'REAL','approved_cost_usd':'REAL','tax_reviewed':'INTEGER NOT NULL DEFAULT 0','import_cost_reviewed':'INTEGER NOT NULL DEFAULT 0'}.items():
            if name not in columns: db.execute(f'ALTER TABLE orders ADD COLUMN {name} {sql}')
        # Migración no destructiva: la imagen original de v1.3 pasa a la galería.
        # Se mantienen fotos originales durante la migración; el cambio es atómico.
        db.execute('''INSERT INTO item_photos(id,item_id,role,mime_type,data,created_at)
            SELECT lower(hex(randomblob(8))),i.id,'producto',
               CASE WHEN substr(i.photo,1,8)=X'89504E470D0A1A0A' THEN 'image/png'
                    WHEN substr(i.photo,1,4)=X'52494646' THEN 'image/webp'
                    ELSE 'image/jpeg' END,
               i.photo, i.created_at FROM items AS i
            WHERE i.photo IS NOT NULL AND NOT EXISTS(SELECT 1 FROM item_photos AS p WHERE p.item_id=i.id)''')
        db.execute('UPDATE items SET photo=NULL WHERE photo IS NOT NULL')
        market_cols={r['name'] for r in db.execute('PRAGMA table_info(market)')}
        for name,sql in {'reputation_ok':'INTEGER NOT NULL DEFAULT 0','payment_verified':'INTEGER NOT NULL DEFAULT 0','shipping_verified':'INTEGER NOT NULL DEFAULT 0','conditions_note':"TEXT NOT NULL DEFAULT ''"}.items():
            if name not in market_cols: db.execute(f'ALTER TABLE market ADD COLUMN {name} {sql}')

def row(x): return dict(x) if x is not None else None

def get_settings(db): return json.loads(db.execute('SELECT content FROM settings WHERE id=1').fetchone()['content'])

def all_orders(db):
    orders=[row(r) for r in db.execute('SELECT * FROM orders ORDER BY updated_at DESC')]
    for order in orders:
        order['items']=[row(x) for x in db.execute('SELECT id,order_id,name,brand,sku,variant,category,unit_price_usd,qty,unit_weight_g,weight_source,weight_verified,photo IS NOT NULL as has_photo, created_at FROM items WHERE order_id=? ORDER BY created_at ASC', (order['id'],))]
        for item in order['items']:
            item['photos']=[row(x) for x in db.execute('SELECT id,role,mime_type,created_at FROM item_photos WHERE item_id=? ORDER BY rowid ASC',(item['id'],))]
            item['has_photo']=bool(item['photos']) or bool(item['has_photo'])
            item['market']=[row(x) for x in db.execute('SELECT * FROM market WHERE item_id=? ORDER BY observed_at DESC',(item['id'],))]
    return orders

def invalidate_order(db, order_id):
    db.execute("UPDATE orders SET status='draft', approved_at=NULL, approved_fx_ars=NULL, approved_sell_usd=NULL, approved_cost_usd=NULL, updated_at=? WHERE id=?", (now(),order_id))

def ensure_fields(obj, allowed):
    invalid=set(obj)-set(allowed)
    if invalid: raise ValueError('Campos no permitidos: '+', '.join(sorted(invalid)))
    return obj

def patch(db, table, id, values, allowed, foreign_key=None):
    ensure_fields(values,allowed)
    if not values: return
    cols=', '.join(f'{k}=?' for k in values)
    db.execute(f'UPDATE {table} SET {cols} WHERE id=?', (*values.values(),id))
