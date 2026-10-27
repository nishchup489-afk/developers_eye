# Running the processing tests

What each test checks is in [test_case.md](test_case.md).

These tests are fully offline: no HTTP, DNS, database, or worker.

From the repository root:

```powershell
.\crawler\.venv\Scripts\python.exe -m pytest crawler/src/crawler/processing/tests -q
```

For colored PASS/FAIL output grouped by stage (normalize, classify, fingerprint, processor), run the suite directly:

```powershell
.\crawler\.venv\Scripts\python.exe crawler/src/crawler/processing/tests/test_processing.py
```

`test_fingerprint.py` has no assertions. It only prints three values when imported (`True`, `False`, `64`), so check those by eye:

```powershell
.\crawler\.venv\Scripts\python.exe -m crawler.processing.tests.test_fingerprint
```
