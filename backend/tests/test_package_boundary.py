"""The API must be usable without installing the worker package."""
import os
import subprocess
import sys


def test_backend_import_and_routes_do_not_require_crawler():
    code = '''
import importlib.abc, sys
class NoCrawler(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in ('crawler', 'indexer'):
            raise AssertionError('Backend imported crawler: ' + fullname)
sys.meta_path.insert(0, NoCrawler())
from backend.main import app
from backend.services.crawler_monitoring import build_monitor
assert '/admin/crawler/monitor' in app.openapi()['paths']
assert '/admin/indexer/report' in app.openapi()['paths']
'''
    subprocess.run([sys.executable, '-c', code], check=True, timeout=20,
        env={**os.environ, 'DATABASE_URL': 'postgresql+asyncpg://test@127.0.0.1:1/test'})
