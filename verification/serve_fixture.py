"""Isolated browser-test server; never touches the user's practice database."""
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app import make_server
with TemporaryDirectory(prefix='adlab-browser-') as tmp:
    server=make_server(db=Path(tmp)/'practice.sqlite3')
    print('http://127.0.0.1:'+str(server.server_port),flush=True)
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: server.server_close()
