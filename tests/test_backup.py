"""La copia descargada es SQLite coherente y queda protegida por sesión."""
import io
import sqlite3
from fastapi.testclient import TestClient
from app import app


def test_backup_coherente_y_con_clientes():
    with TestClient(app) as c:
        c.post('/api/customers', json={'data':{'full_name':'Cliente para respaldo','phone':''}})
        res=c.get('/api/backup')
        assert res.status_code == 200
        assert res.content[:16] == b'SQLite format 3\x00'
        assert 'attachment' in res.headers['content-disposition']
        # SQLite no abre BytesIO directamente; verificar contenido en DB temporal.
        import tempfile
        with tempfile.NamedTemporaryFile(suffix='.sqlite3') as f:
            f.write(res.content);f.flush()
            with sqlite3.connect(f.name) as db:
                assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
                assert db.execute('SELECT COUNT(*) FROM customers WHERE full_name=?',('Cliente para respaldo',)).fetchone()[0]>=1


def test_backup_sin_sesion_rechazado(monkeypatch):
    import app as appmod
    monkeypatch.setattr(appmod,'AUTH_PASSWORD','test-password-12-strong')
    with TestClient(app) as c:
        assert c.get('/api/backup').status_code==401
        assert c.post('/api/login',json={'password':'equivocada'}).status_code==401
        assert c.post('/api/login',json={'password':'test-password-12-strong'}).status_code==200
        assert c.get('/api/backup').status_code==200
