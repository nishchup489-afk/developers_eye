# Developer's Eye fetcher tests

Copy both files from `tests/` into the repository's `crawler/tests/` directory. Run from `crawler/`:

```bash
poetry add --group dev pytest colorama
poetry run pytest tests/test_fetcher.py -q -s
```

The suite uses HTTPX MockTransport and fake HTTPCore network objects. It **does not make live HTTP or DNS requests**.

Expected test interpretation:

- **PASS** (green): a normal behavior works.
- **FAIL** (red): behavior is broken. At present the `httpcore.HTTPError` catch is a known incompatibility with HTTPCore 1.0.9.
- **XFAIL** (yellow): a known security gap the test is intentionally tracking (custom Host header, custom `sni_hostname`, and different path on the approved origin).
- **XPASS** (red, when marked `strict=True`): code now passes an expected-failure test, so remove the xfail marker and keep it as a permanent regression test.

### HTTPcore exception compatibility fix

The `httpcore.HTTPError` exception name is not defined in HTTPcore 1.0.9. In `crawler/src/crawler/fetcher/transport.py` define:

```python
CORE_ERRORS = (
    httpcore.TimeoutException,
    httpcore.NetworkError,
    httpcore.ProtocolError,
    httpcore.ProxyError,
    httpcore.UnsupportedProtocol,
)
```

Replace the three occurrences of `except httpcore.HTTPError as exc:` with `except CORE_ERRORS as exc:`. Run the tests again. Keep the explicit subtype-to-HTTPX exception mapping as-is.

Also verify `PolicyCoordinator` imports shared `FetcherSecurityError` / `ResponseTooLargeError` from `crawler.fetcher.errors` rather than redefining them.
