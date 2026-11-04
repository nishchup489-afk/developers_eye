
import getpass
import urllib.error
import urllib.request

URL = "http://127.0.0.1:8000/admin/crawler/report?days=1&top_sources=1&recent_errors=0"


def check_key(key: str) -> int:
    request = urllib.request.Request(
        URL,
        headers={
            "Authorization": f"Bearer {key}",
        },
    )

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.status
    except urllib.error.HTTPError as exc:
        return exc.code


def main() -> None:
    old_key = getpass.getpass("Previously exposed key: ")
    new_key = getpass.getpass("New API key: ")

    if not old_key or not new_key or old_key == new_key:
        raise SystemExit("Keys must be nonempty and different.")

    old_status = check_key(old_key)
    new_status = check_key(new_key)

    print(f"Old key HTTP status: {old_status}")
    print(f"New key HTTP status: {new_status}")

    if old_status == 401 and new_status == 200:
        print("PASS: rotation verified locally.")
    else:
        raise SystemExit("FAIL: investigate key configuration or backend status.")


if __name__ == "__main__":
    main()
