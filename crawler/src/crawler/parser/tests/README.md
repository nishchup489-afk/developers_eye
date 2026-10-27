# Running the parser tests

What each test checks is in [test_case.md](test_case.md).

These tests are fully offline: no network, database, policy coordinator, or worker.

From the repository root:

```powershell
.\crawler\.venv\Scripts\python.exe -m pytest crawler/src/crawler/parser/tests -q
```

`test_html_parser.py` is a `unittest` suite, so it can also be run on its own:

```powershell
.\crawler\.venv\Scripts\python.exe -m crawler.parser.tests.test_html_parser
```

The RSS/Atom, JSON API, and sitemap parsers are tested in [crawler/tests](../../../../tests/README.md).
