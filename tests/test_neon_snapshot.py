"""Pruebas del adaptador de persistencia, sin depender de una red externa."""
import os, sqlite3, tempfile
from pathlib import Path
from unittest.mock import patch
import database


def test_local_connect_sin_conexion_remota():
    with tempfile.TemporaryDirectory() as d:
        with patch.object(database, 'REMOTE_URL', ''), patch.object(database, 'DATA_DIR', Path(d)), patch.object(database, 'DB_PATH', Path(d) / 'test.sqlite3'):
            database.init()
            with database.connect() as db:
                assert database.get_settings(db)['rates_usd_kg']['perfumes'] == 45
            with sqlite3.connect(Path(d) / 'test.sqlite3') as db:
                assert db.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'


def test_configuracion_render_apunta_a_un_worker():
    from pathlib import Path
    yaml = (Path(__file__).resolve().parents[1] / 'render.yaml').read_text()
    assert 'workers 1' in yaml
    assert 'plan: free' in yaml
    assert 'sync: false' in yaml
