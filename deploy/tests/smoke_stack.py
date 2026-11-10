"""Build and exercise an isolated PG18/API/Caddy stack; never starts public crawls.

Run on Linux with Docker: python3 deploy/tests/smoke_stack.py --output report.json
Only generated credentials and a temporary database are used. No real .env is read.
"""
import argparse
import json
import os
from pathlib import Path
import secrets
import shutil
import socket
import subprocess
import tempfile
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", help="Use an already built Python image")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--frontend", action="store_true", help="Also start a previously built local Next.js frontend")
    args = parser.parse_args()
    project = "de-oracle-smoke-" + secrets.token_hex(5)
    image = args.image or project + ":local"
    checks = []
    with tempfile.TemporaryDirectory(prefix=project + "-") as folder:
        folder = Path(folder)
        (folder / "pgdata").mkdir()
        values = {"POSTGRES_PASSWORD": secrets.token_hex(32), "EDGE_SHARED_SECRET": secrets.token_hex(32),
                  "CRAWLER_REPORT_API_KEY": secrets.token_hex(32), "SITE_ADDRESS": ":80",
                  "PGDATA_HOST_PATH": str(folder / "pgdata"), "SEARCH_RATE_LIMIT_PER_MINUTE": "1",
                  "SEARCH_RATE_LIMIT_BURST": "1", "AI_OVERVIEW": "false", "BACKUP_DIR": str(folder / "backups")}
        env_file = folder / "test.env"
        env_file.write_text("".join(f"{k}={v}\n" for k, v in values.items()))
        env = {**os.environ, **values, "DEPLOY_ENV_FILE": str(env_file)}

        def run(command, **kwargs):
            return subprocess.run(command, cwd=ROOT, env=env, check=True, text=True, **kwargs)

        rendered = json.loads(run(["docker", "compose", "-p", project, "--env-file", str(env_file), "-f",
                                  "deploy/docker-compose.yml", "config", "--format", "json"], capture_output=True).stdout)
        services = rendered["services"]
        assert all(v.get("name", "").startswith(project + "_") for v in rendered.get("volumes", {}).values())
        assert all(v.get("name", "").startswith(project + "_") for v in rendered.get("networks", {}).values())
        assert "web" not in services and "indexer-1" not in services
        assert services["crawler"]["deploy"]["replicas"] == 1
        assert services["indexer-0"]["environment"]["INDEXER_SHARD_COUNT"] == "1"
        assert all(s["logging"]["options"] == {"max-file": "3", "max-size": "20m"} for s in services.values())
        assert not any(s.get("ports") for n, s in services.items() if n != "caddy")
        checks.append("Production Compose: API-only ingress, one crawler/indexer, private DB/API, bounded logs")

        if not args.image:
            run(["docker", "build", "-t", image, "-f", "deploy/Dockerfile.python", "."])
        rendered["services"] = {k: v for k, v in services.items() if k in {"db", "migrate", "api", "caddy"}}
        for name in ("migrate", "api"):
            services[name].pop("build", None)
            services[name]["image"] = image
        # Test isolation: small buffers and random loopback port; production config
        # remains unchanged and is not suitable for an arbitrary CI machine's RAM.
        services["db"]["command"] = ["postgres", "-c", "shared_buffers=128MB", "-c", "max_connections=30"]
        services["db"]["shm_size"] = "256m"
        services["caddy"]["ports"] = [{"target": 80, "published": "0", "host_ip": "127.0.0.1", "protocol": "tcp"}]
        rendered.pop("name", None)
        config = folder / "compose.json"
        config.write_text(json.dumps(rendered))
        compose = ["docker", "compose", "-p", project, "--env-file", str(env_file), "-f", str(config)]

        def request(path, status, *, identity=None, secret=None, admin_key=None):
            headers = {"X-Forwarded-For": "203.0.113.99"}
            if identity is not None:
                headers["X-Eye-Client-IP"] = identity
            if secret is not None:
                headers["X-Edge-Secret"] = secret
            if admin_key is not None:
                headers["Authorization"] = "Bearer " + admin_key
            try:
                response = urlopen(Request(base + path, headers=headers), timeout=10)
            except HTTPError as exc:
                response = exc
            with response:
                body = response.read()
                assert response.status == status, (path, response.status, status, body[:200])

        try:
            run(compose + ["up", "-d"])
            port = run(compose + ["port", "caddy", "80"], capture_output=True).stdout.strip().split(":")[-1]
            base = "http://127.0.0.1:" + port
            for attempt in range(60):
                try:
                    request("/health", 200)
                    break
                except (URLError, ConnectionError, TimeoutError):
                    time.sleep(1)
            else:
                raise RuntimeError("Caddy did not become ready")
            checks.append("PG18 empty migration, FastAPI startup, Caddy config/runtime and unauthenticated health")
            seed = """WITH s AS (
              INSERT INTO source(slug,name,kind,base_url,allowed_hosts)
              VALUES ('smoke','Smoke','website','https://smoke.example.test',ARRAY['smoke.example.test']) RETURNING id
            ), d AS (
              INSERT INTO document(source_id,canonical_url,document_type,title,body,content_hash)
              SELECT id,'https://smoke.example.test/python','documentation','Python smoke','python guide','smoke-hash' FROM s RETURNING id
            ) INSERT INTO search_index(document_id,search_vector,code_vector,indexed_hash,category)
              SELECT id,to_tsvector('english','python guide'),to_tsvector('simple',''),'smoke-hash','docs' FROM d;
              INSERT INTO search_terms(term,document_frequency) VALUES ('python',1);"""
            run(compose + ["exec", "-T", "db", "psql", "-U", "developers_eye", "-d", "developers_eye", "-v", "ON_ERROR_STOP=1", "-c", seed])
            request("/search?q=python", 403, identity="198.51.100.1")
            request("/search?q=python", 403, identity="198.51.100.1", secret="wrong")
            request("/health/db", 403)
            request("/docs", 403)
            request("/docs", 404, secret=values["EDGE_SHARED_SECRET"])
            request("/openapi.json", 404, secret=values["EDGE_SHARED_SECRET"])
            checks.append("Missing/wrong edge credentials denied; spoofed IP cannot bypass; production docs disabled")
            request("/search?q=python", 200, identity="198.51.100.1", secret=values["EDGE_SHARED_SECRET"])
            request("/search?q=python", 429, identity="198.51.100.1", secret=values["EDGE_SHARED_SECRET"])
            request("/search?q=python", 200, identity="198.51.100.2", secret=values["EDGE_SHARED_SECRET"])
            request("/search?q=python", 400, identity="bad-ip", secret=values["EDGE_SHARED_SECRET"])
            request("/admin/crawler/report", 401, secret=values["EDGE_SHARED_SECRET"])
            request("/admin/crawler/report", 200, secret=values["EDGE_SHARED_SECRET"], admin_key=values["CRAWLER_REPORT_API_KEY"])
            checks.append("Authenticated visitor rate buckets separate; repeat limited; malformed identity and missing admin key denied")
            # Also bypass Caddy inside the private API container: app gate must hold.
            probe = "import urllib.request,urllib.error;\ntry: urllib.request.urlopen('http://127.0.0.1:8000/search?q=python')\nexcept urllib.error.HTTPError as e: assert e.code==403\nelse: raise AssertionError('unguarded API')"
            run(compose + ["exec", "-T", "api", "python", "-c", probe])
            checks.append("Direct private API request still requires edge credential")
            if args.frontend:
                frontend = ROOT / "frontend"
                build_dir = os.environ.get("NEXT_BUILD_DIR", ".next")
                assert (frontend / build_dir / "BUILD_ID").exists(), "Build the frontend first with the same NEXT_BUILD_DIR"
                with socket.socket() as listener:
                    listener.bind(("127.0.0.1", 0))
                    next_port = listener.getsockname()[1]
                with (folder / "next.log").open("w+") as next_log:
                    server = subprocess.Popen([shutil.which("node"), "node_modules/next/dist/bin/next", "start",
                        "--hostname", "127.0.0.1", "--port", str(next_port)], cwd=frontend, stdout=next_log, stderr=next_log,
                        env={**os.environ, "BACKEND_URL": base, "EDGE_SHARED_SECRET": values["EDGE_SHARED_SECRET"],
                             "KNOWLEDGE_PANEL": "off", "VERCEL": "1"})
                    next_base = "http://127.0.0.1:" + str(next_port)
                    try:
                        for attempt in range(100):
                            if server.poll() is not None:
                                raise RuntimeError("Next.js exited during startup")
                            try:
                                urlopen(next_base + "/api/search", timeout=2)
                            except HTTPError as exc:
                                assert exc.code == 400  # Ready, missing query.
                                break
                            except (URLError, ConnectionError, TimeoutError):
                                time.sleep(.1)
                        else:
                            raise RuntimeError("Next.js did not become ready")

                        def visit(ip, status, spoofed_ip):
                            req = Request(next_base + "/api/search?q=python", headers={
                                "X-Vercel-Forwarded-For": ip, "X-Eye-Client-IP": spoofed_ip,
                                "X-Edge-Secret": "caller-supplied-wrong-secret"})
                            try:
                                result = urlopen(req, timeout=10)
                            except HTTPError as exc:
                                result = exc
                            with result:
                                data = json.load(result)
                                assert result.status == status, (result.status, data)
                                if status == 200:
                                    assert data["mode"] == "live" and len(data["results"]) == 1
                                else:
                                    assert result.headers.get("Retry-After")

                        visit("198.51.100.30", 200, "203.0.113.1")
                        visit("198.51.100.30", 429, "203.0.113.2")
                        visit("198.51.100.31", 200, "203.0.113.1")
                        checks.append("Real Next.js -> Caddy -> FastAPI -> PG18: runtime edge secret, live result, spoof-resistant independent visitor limits")
                    except BaseException:
                        next_log.seek(0)
                        print(next_log.read()[-4000:])
                        raise
                    finally:
                        server.terminate()
                        try:
                            server.wait(timeout=10)
                        except subprocess.TimeoutExpired:
                            server.kill()
                            server.wait()
            env.update(COMPOSE_FILE=str(config), COMPOSE_PROJECT_NAME=project)
            run(["sh", "deploy/backup.sh"])
            run(["sh", "deploy/restore-test.sh"])
            checks.append("Actual backup.sh and restore-test.sh round-trip nonempty PG18 core tables in isolated containers")
            signal_name = project + "-signal"
            code = """import asyncio
from backend.core.shutdown import with_sigterm
async def work():
    print('READY',flush=True)
    try: await asyncio.Event().wait()
    finally:
        await asyncio.sleep(.1)
        print('CLEANUP',flush=True)
raise SystemExit(asyncio.run(with_sigterm(work())))
"""
            try:
                run(["docker", "run", "-d", "--name", signal_name, image, "python", "-u", "-c", code])
                for attempt in range(50):
                    if "READY" in run(["docker", "logs", signal_name], capture_output=True).stdout:
                        break
                    time.sleep(.1)
                else:
                    raise RuntimeError("SIGTERM probe did not become ready")
                run(["docker", "stop", "--time", "10", signal_name])
                assert run(["docker", "inspect", "--format", "{{.State.ExitCode}}", signal_name], capture_output=True).stdout.strip() == "0"
                assert "CLEANUP" in run(["docker", "logs", signal_name], capture_output=True).stdout
                checks.append("Linux container SIGTERM waits for async finally cleanup and exits zero")
            finally:
                subprocess.run(["docker", "rm", "-f", signal_name], cwd=ROOT, env=env, check=True)
            print("\n".join("PASS " + check for check in checks))
            if args.output:
                args.output.parent.mkdir(parents=True, exist_ok=True)
                args.output.write_text(json.dumps({"status": "passed", "checks": checks,
                    "frontend_included": args.frontend,
                    "scope": "Isolated local Linux/amd64 Docker PG18/API/Caddy and optional real Next.js; no public cloud, DNS, TLS, ARM execution or crawler network traffic"}, indent=2) + "\n")
        except BaseException:
            subprocess.run(compose + ["logs", "--tail", "50"], cwd=ROOT, env=env)
            raise
        finally:
            subprocess.run(compose + ["down", "--volumes", "--remove-orphans"], cwd=ROOT, env=env, check=True)


if __name__ == "__main__":
    main()
