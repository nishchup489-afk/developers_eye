"""Regenerate the API map in 0_tech_docs/infra/system-architecture/api-map.md from the code.

Usage, from the repository root:

    python scripts/update_api_map.py          # rewrite the map
    python scripts/update_api_map.py --check  # exit 1 if the map is stale or a call reaches no route
    python scripts/update_api_map.py --diff   # print what would change, write nothing
    python scripts/update_api_map.py --json   # print the parsed model as JSON (for other tools)

What it reads (standard library only, nothing is imported or executed):

    backend/src/backend/main.py      FastAPI app: include_router() calls and @app routes
    backend/src/backend/**.py        each included APIRouter: prefix, dependencies, routes, params
    frontend/app/**/route.(ts|js)    Next.js route handlers: URL from the folder, exported methods,
                                     auth guard, and the FastAPI or external URL each one calls
    frontend/{app,components,lib}    browser calls: api.get(...), usePolling("/api/..."),
                                     href="/api/...", <form action="/api/...">
    deploy/Caddyfile, deploy/docker-compose.yml
                                     which service is reachable from the internet

The generated block sits between the two marker comments. Text above the start
marker is kept as written, so the intro can be edited by hand.

--check fails when the file is out of date, when a browser call matches no
Next.js route, when a Next.js route calls a FastAPI path that does not exist, or
when a proxy helper listed in HELPERS has changed shape and needs re-checking.
"""

from __future__ import annotations

import argparse
import ast
import difflib
import json
import os
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parent.parent
DOC = "0_tech_docs/infra/system-architecture/api-map.md"
START = "<!-- api-map:start -->"
END = "<!-- api-map:end -->"

BACKEND_SRC = "backend/src"
BACKEND_MAIN = "backend/src/backend/main.py"
FRONTEND = "frontend"
CADDYFILE = "deploy/Caddyfile"
COMPOSE = "deploy/docker-compose.yml"

METHODS = ("get", "post", "put", "patch", "delete", "head", "options")

# FastAPI dependencies that guard a route, and how a caller satisfies them.
BACKEND_AUTH = {
    "require_report_key": "service key: `Authorization: Bearer $CRAWLER_REPORT_API_KEY`",
}

# Frontend helpers that call FastAPI on a route's behalf. Each entry is checked
# against its file on every run (see check_helpers), so a refactor that breaks
# these assumptions fails --check instead of producing a wrong map.
HELPERS = {
    "adminProxy": {
        "file": "frontend/lib/crawler-proxy.ts",
        "must_contain": ["export async function adminProxy", "getViewer()", "adminGet(", "/admin/"],
        "prefix": "/admin/",
        "auth": "viewer session",
        "via": "`adminProxy` → `adminGet` (Bearer key)",
    },
    "crawlerProxy": {
        "file": "frontend/lib/crawler-proxy.ts",
        "must_contain": ["export const crawlerProxy", "adminProxy(`crawler/${path}`"],
        "prefix": "/admin/crawler/",
        "auth": "viewer session",
        "via": "`crawlerProxy` → `adminProxy` → `adminGet` (Bearer key)",
    },
}

# Env vars that hold a full FastAPI URL (not just a base). A route that reads one
# and calls adminGet() directly hits this path.
ENV_ENDPOINTS = {"CRAWLER_REPORT_API_URL": "/admin/crawler/report"}
# Env vars that hold the FastAPI base URL; the route appends a path to it.
ENV_BASES = ("BACKEND_URL",)

ROUTE_GUARDS = {
    "getViewer(": "viewer session",
    "requireViewer(": "viewer session",
    "requireAdmin(": "admin session (admin role only)",
    "getAdmin(": "admin session (admin role only)",
}
SESSION_FILE = "frontend/lib/admin-session.ts"


# --------------------------------------------------------------------------- model


@dataclass
class Param:
    name: str
    where: str  # query | path
    type: str
    default: str
    rules: str


@dataclass
class BackendEndpoint:
    method: str
    path: str
    file: str
    line: int
    handler: str
    auth: list[str]
    params: list[Param]
    response_model: str
    summary: str
    tags: list[str]


@dataclass
class Upstream:
    method: str
    target: str  # FastAPI path, or a full https URL for external services
    kind: str  # backend | external | redirect
    via: str
    line: int
    matches: list[str] = field(default_factory=list)  # "METHOD /path" of matched FastAPI endpoints


@dataclass
class NextRoute:
    path: str
    methods: list[str]
    file: str
    auth: str
    reads: list[str]
    upstream: list[Upstream]


@dataclass
class BrowserCall:
    method: str
    path: str
    file: str
    line: int
    how: str
    route: str = ""  # matched Next.js route path, empty if none


# --------------------------------------------------------------------------- helpers


def rel(path: str | Path) -> str:
    return PurePosixPath(Path(path).resolve().relative_to(ROOT)).as_posix()


def read(path: str | Path) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def line_of(text: str, index: int) -> int:
    return text.count("\n", 0, index) + 1


def segments(path: str) -> list[str]:
    return [s for s in path.strip("/").split("/") if s]


def is_param(segment: str) -> bool:
    return (segment.startswith("{") and segment.endswith("}")) or segment == "*"


def path_matches(call: str, route: str) -> bool:
    """A call path matches a route when every segment is equal or either side is a parameter."""
    a, b = segments(call), segments(route)
    if len(a) != len(b):
        return False
    return all(x == y or is_param(x) or is_param(y) for x, y in zip(a, b))


def template_to_path(raw: str) -> str:
    """`/admin/${type}/${id}` -> `/admin/*/*`; cut at a query string or a mid-segment template."""
    raw = raw.split("?", 1)[0]
    out = []
    for seg in raw.split("/"):
        if seg.startswith("${"):
            out.append("*")
        elif "${" in seg:
            out.append(seg.split("${", 1)[0])
            break
        else:
            out.append(seg)
    path = "/".join(out)
    return path.rstrip("/") or "/"


# --------------------------------------------------------------------------- backend


def module_file(module: str) -> Path:
    base = ROOT / BACKEND_SRC / Path(*module.split("."))
    return base.with_suffix(".py") if base.with_suffix(".py").exists() else base / "__init__.py"


def dep_names(node: ast.AST | None) -> list[str]:
    """Names inside Depends(...) calls found anywhere in node."""
    names = []
    if node is None:
        return names
    for call in ast.walk(node):
        if isinstance(call, ast.Call) and getattr(call.func, "id", None) == "Depends" and call.args:
            names.append(ast.unparse(call.args[0]))
    return names


def kwarg(call: ast.Call, name: str) -> ast.AST | None:
    return next((k.value for k in call.keywords if k.arg == name), None)


def const(node: ast.AST | None, fallback=""):
    return node.value if isinstance(node, ast.Constant) else fallback


SKIP_PARAM_TYPES = {"Response", "Request", "AsyncSession", "BackgroundTasks", "WebSocket"}
RULE_KEYS = ("ge", "gt", "le", "lt", "min_length", "max_length", "pattern", "regex")


def parse_params(fn: ast.FunctionDef | ast.AsyncFunctionDef, path: str) -> tuple[list[Param], list[str]]:
    args = fn.args.posonlyargs + fn.args.args
    defaults = [None] * (len(args) - len(fn.args.defaults)) + list(fn.args.defaults)
    pairs = list(zip(args, defaults)) + list(zip(fn.args.kwonlyargs, fn.args.kw_defaults))
    params, deps = [], []
    for arg, default in pairs:
        ann = arg.annotation
        found = dep_names(ann) + dep_names(default)
        if found:
            deps += found
            continue
        type_node, marker = ann, None
        if isinstance(ann, ast.Subscript) and ast.unparse(ann.value) in ("Annotated", "typing.Annotated"):
            parts = ann.slice.elts if isinstance(ann.slice, ast.Tuple) else [ann.slice]
            type_node = parts[0]
            marker = next((p for p in parts[1:] if isinstance(p, ast.Call)), None)
        type_name = ast.unparse(type_node) if type_node is not None else "any"
        if type_name in SKIP_PARAM_TYPES:
            continue
        if isinstance(default, ast.Call) and getattr(default.func, "id", None) in ("Query", "Path"):
            marker, default = default, (default.args[0] if default.args else kwarg(default, "default"))
        where = "path" if f"{{{arg.arg}}}" in path else "query"
        if marker is not None and getattr(marker.func, "id", None) == "Path":
            where = "path"
        rules = []
        if marker is not None:
            for key in RULE_KEYS:
                value = kwarg(marker, key)
                if value is not None:
                    rules.append(f"{key}={ast.unparse(value)}")
        shown_default = "required" if default is None or where == "path" else ast.unparse(default)
        params.append(Param(arg.arg, where, type_name, shown_default, ", ".join(rules)))
    return params, deps


def routers_in(tree: ast.Module) -> dict[str, dict]:
    found = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call) and getattr(node.value.func, "id", None) in ("APIRouter", "FastAPI"):
            call = node.value
            tags = kwarg(call, "tags")
            info = {
                "prefix": const(kwarg(call, "prefix")),
                "deps": dep_names(kwarg(call, "dependencies")),
                "tags": [const(t) for t in tags.elts] if isinstance(tags, ast.List) else [],
            }
            for target in node.targets:
                if isinstance(target, ast.Name):
                    found[target.id] = info
    return found


def endpoints_in(path: Path, var: str, include_prefix: str = "", include_deps: list[str] | None = None) -> list[BackendEndpoint]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    router = routers_in(tree).get(var, {"prefix": "", "deps": [], "tags": []})
    result = []
    for fn in tree.body:
        if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for dec in fn.decorator_list:
            if not (isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute)):
                continue
            if getattr(dec.func.value, "id", None) != var or dec.func.attr not in METHODS:
                continue
            sub = const(dec.args[0]) if dec.args else const(kwarg(dec, "path"))
            full = (include_prefix + router["prefix"] + sub) or "/"
            params, param_deps = parse_params(fn, full)
            deps = (include_deps or []) + router["deps"] + dep_names(kwarg(dec, "dependencies")) + param_deps
            model = kwarg(dec, "response_model")
            if model is None and fn.returns is not None:
                model = fn.returns
            doc = ast.get_docstring(fn) or ""
            result.append(BackendEndpoint(
                method=dec.func.attr.upper(), path=full, file=rel(path), line=dec.lineno,
                handler=fn.name, auth=sorted(set(deps)), params=params,
                response_model=ast.unparse(model) if model is not None else "",
                summary=doc.strip().splitlines()[0] if doc.strip() else "",
                tags=router["tags"],
            ))
    return result


def parse_backend() -> tuple[list[BackendEndpoint], list[str]]:
    main = ROOT / BACKEND_MAIN
    tree = ast.parse(main.read_text(encoding="utf-8"))
    imports: dict[str, tuple[str, str]] = {}
    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and node.module:
            for alias in node.names:
                imports[alias.asname or alias.name] = (node.module, alias.name)
    app_var = next((name for name, info in routers_in(tree).items()), "app")
    endpoints = endpoints_in(main, app_var)
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "include_router":
            name = ast.unparse(node.args[0])
            if name not in imports:
                continue
            module, attr = imports[name]
            endpoints += endpoints_in(module_file(module), attr, const(kwarg(node, "prefix")), dep_names(kwarg(node, "dependencies")))
    cors = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and ast.unparse(node.func).endswith("add_middleware"):
            origins = kwarg(node, "allow_origins")
            if isinstance(origins, ast.List):
                cors = [const(o) for o in origins.elts]
    endpoints.sort(key=lambda e: (e.path, e.method))
    return endpoints, cors


# --------------------------------------------------------------------------- frontend

CODE_EXT = (".ts", ".tsx", ".js", ".jsx", ".mjs")


def next_route_path(file: Path) -> str:
    parts = file.relative_to(ROOT / FRONTEND / "app").parts[:-1]
    out = []
    for part in parts:
        if part.startswith("(") and part.endswith(")"):
            continue  # route group
        if part.startswith("@"):
            continue  # parallel route slot
        m = re.fullmatch(r"\[\[?(?:\.\.\.)?(\w+)\]?\]", part)
        out.append(f"{{{m.group(1)}}}" if m else part)
    return "/" + "/".join(out)


def check_helpers() -> list[str]:
    problems = []
    for name, info in HELPERS.items():
        path = ROOT / info["file"]
        text = path.read_text(encoding="utf-8") if path.exists() else ""
        missing = [s for s in info["must_contain"] if s not in text]
        if missing:
            problems.append(f"helper {name} in {info['file']} changed (missing {missing}); update HELPERS in scripts/update_api_map.py")
    return problems


def parse_route_file(file: Path) -> NextRoute:
    text = file.read_text(encoding="utf-8")
    methods = re.findall(r"export\s+(?:async\s+)?function\s+(GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS)\b", text)
    methods += re.findall(r"export\s+const\s+(GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS)\b", text)
    auth = ""
    for needle, label in ROUTE_GUARDS.items():
        if needle in text:
            auth = label
    upstream: list[Upstream] = []

    for m in re.finditer(r"\b(%s)\(\s*([\"'`])(.*?)\2" % "|".join(HELPERS), text):
        info = HELPERS[m.group(1)]
        upstream.append(Upstream("GET", template_to_path(info["prefix"] + m.group(3)), "backend", info["via"], line_of(text, m.start())))
        auth = auth or info["auth"]

    for env, endpoint in ENV_ENDPOINTS.items():
        if f"process.env.{env}" in text and "adminGet(" in text and not any(h + "(" in text for h in HELPERS):
            m = re.search(r"adminGet\(", text)
            upstream.append(Upstream("GET", endpoint, "backend", f"`adminGet` on `${env}` (Bearer key)", line_of(text, m.start())))

    for env in ENV_BASES:
        if f"process.env.{env}" not in text:
            continue
        call = re.search(r"\bbackend\.(get|post|put|patch|delete)\(\s*(?![\"'`]https?:)", text)
        method = call.group(1).upper() if call else "GET"
        for m in re.finditer(r"`\$\{[^`]*?\}(/[^`]*)`", text):
            upstream.append(Upstream(method, template_to_path(m.group(1)), "backend", f"`backend.{method.lower()}` on `${env}`", line_of(text, m.start())))

    for m in re.finditer(r"\bbackend\.(get|post|put|patch|delete)\(\s*[\"'`](https?://[^\"'`]+)", text):
        upstream.append(Upstream(m.group(1).upper(), m.group(2), "external", "`backend` axios client", line_of(text, m.start())))
    for m in re.finditer(r"new URL\(\s*[\"'`](https?://[^\"'`]+)", text):
        upstream.append(Upstream("GET", m.group(1), "redirect", "browser redirect", line_of(text, m.start())))

    reads = sorted(set(re.findall(r"\b(?:params|query|incoming|searchParams|search)\.get\(\s*\"([A-Za-z_]+)\"\s*\)", text)))
    reads += sorted(set(re.findall(r"searchParams\.get\(\s*\"([A-Za-z_]+)\"\s*\)", text)) - set(reads))
    if re.search(r"\.get\(\s*name\s*\)", text):
        reads.append("…names from a table in the file")
    return NextRoute(next_route_path(file), methods, rel(file), auth, reads, upstream)


def parse_routes() -> list[NextRoute]:
    files = sorted(p for ext in (".ts", ".js") for p in (ROOT / FRONTEND / "app").rglob(f"route{ext}") if "node_modules" not in p.parts)
    return sorted((parse_route_file(f) for f in files), key=lambda r: r.path)


BROWSER_PATTERNS = [
    # api client: baseURL "/api" unless the call overrides baseURL
    (re.compile(r"\bapi\.(get|post|put|patch|delete)(?:<[^>]*>)?\(\s*[\"'`]([^\"'`]+)[\"'`]([^\n]*)"), "axios `api` client"),
    (re.compile(r"\busePolling\(\s*[\"'`](/api/[^\"'`]*)"), "`usePolling` → axios `api` client"),
    (re.compile(r"\bhref=\"(/api/[^\"]+)\""), "link"),
    (re.compile(r"\baction=\"(/api/[^\"]+)\"[^>]*?method=\"(\w+)\""), "form"),
]


def parse_browser_calls() -> list[BrowserCall]:
    calls = []
    roots = [ROOT / FRONTEND / d for d in ("app", "components", "lib")]
    for root in roots:
        for file in sorted(root.rglob("*")):
            if file.suffix not in CODE_EXT or "node_modules" in file.parts or file.stem == "route":
                continue
            text = file.read_text(encoding="utf-8")
            for regex, how in BROWSER_PATTERNS:
                for m in regex.finditer(text):
                    if how == "axios `api` client":
                        method, raw, rest = m.group(1).upper(), m.group(2), m.group(3)
                        path = raw if 'baseURL: ""' in rest else "/api" + (raw if raw.startswith("/") else "/" + raw)
                    elif how == "form":
                        method, path = m.group(2).upper(), m.group(1)
                    else:
                        method, path = "GET", m.group(1)
                    calls.append(BrowserCall(method, template_to_path(path), rel(file), line_of(text, m.start()), how))
    return sorted(calls, key=lambda c: (c.path, c.file, c.line))


# --------------------------------------------------------------------------- deploy


def parse_exposure() -> dict:
    out = {"published": {}, "caddy_upstreams": [], "env": {}}
    if (ROOT / CADDYFILE).exists():
        out["caddy_upstreams"] = re.findall(r"reverse_proxy\s+(\S+)", read(CADDYFILE))
    if (ROOT / COMPOSE).exists():
        service, in_env = None, False
        for raw in read(COMPOSE).splitlines():
            m = re.match(r"^  ([A-Za-z0-9_-]+):\s*$", raw)
            if m:
                service, in_env = m.group(1), False
                continue
            if re.match(r"^\S", raw):
                service = None
                continue
            if service is None:
                continue
            ports = re.match(r"^\s+ports:\s*\[(.*)\]", raw)
            if ports:
                out["published"][service] = [p.strip().strip("\"'") for p in ports.group(1).split(",")]
            if re.match(r"^    environment:", raw):
                in_env = True
                continue
            if in_env:
                kv = re.match(r"^      ([A-Z_]+):\s*(\S+)", raw)
                if kv and kv.group(1) in (*ENV_BASES, *ENV_ENDPOINTS):
                    out["env"].setdefault(service, {})[kv.group(1)] = kv.group(2)
                elif not raw.startswith("      "):
                    in_env = False
    return out


# --------------------------------------------------------------------------- link & render


def link_up(backend: list[BackendEndpoint], routes: list[NextRoute], calls: list[BrowserCall]) -> list[str]:
    problems = []
    for route in routes:
        for up in route.upstream:
            if up.kind != "backend":
                continue
            up.matches = [f"{e.method} {e.path}" for e in backend if e.method == up.method and path_matches(up.target, e.path)]
            if not up.matches:
                problems.append(f"{route.file}:{up.line} calls {up.method} {up.target}, which no FastAPI route serves")
    for call in calls:
        hit = next((r for r in routes if path_matches(call.path, r.path) and call.method in r.methods), None)
        if hit:
            call.route = hit.path
        else:
            problems.append(f"{call.file}:{call.line} calls {call.method} {call.path}, which no Next.js route serves")
    return problems


class Renderer:
    def __init__(self, backend, cors, routes, calls, exposure):
        self.backend, self.cors, self.routes, self.calls, self.exposure = backend, cors, routes, calls, exposure
        self.doc_dir = (ROOT / DOC).parent
        self.by_key = {f"{e.method} {e.path}": e for e in backend}

    def link(self, file: str, line: int | None = None, label: str | None = None) -> str:
        target = PurePosixPath(os.path.relpath(ROOT / file, self.doc_dir)).as_posix()
        target = target.replace("(", "%28").replace(")", "%29").replace(" ", "%20")  # route groups like (protected)
        shown = label or (f"{file}:{line}" if line else file)
        return f"[`{shown}`]({target}{f'#L{line}' if line else ''})"

    def config_warnings(self) -> list[str]:
        """Env values in docker-compose that a route's own URL check will reject."""
        out = []
        for svc, env in sorted(self.exposure["env"].items()):
            for name, endpoint in ENV_ENDPOINTS.items():
                value = env.get(name)
                if value and not value.rstrip("/").endswith(endpoint):
                    out.append(f"`{svc}` sets `{name}={value}` in `{COMPOSE}`, but the admin routes need it to end with "
                               f"`{endpoint}` (e.g. `{value.rstrip('/')}{endpoint}`); otherwise every admin page gets 503/502.")
        return out

    def backend_auth(self, e: BackendEndpoint) -> str:
        return "; ".join(BACKEND_AUTH.get(a, f"`{a}`") for a in e.auth) or "none"

    @staticmethod
    def esc(text: str) -> str:
        return text.replace("|", "\\|")

    def params(self, params: list[Param]) -> str:
        if not params:
            return "—"
        shown = []
        for p in params:
            bits = [p.type]
            if p.rules:
                bits.append(p.rules)
            if p.where == "query":
                bits.append(f"default {p.default}" if p.default != "required" else "required")
            shown.append(f"`{p.name}` ({p.where}: {', '.join(bits)})")
        return self.esc("<br>".join(shown))

    def render(self, problems: list[str]) -> str:
        out: list[str] = [START, ""]
        w = out.append
        backend_callers: dict[str, list[tuple[NextRoute, Upstream]]] = {}
        for r in self.routes:
            for up in r.upstream:
                for key in up.matches:
                    backend_callers.setdefault(key, []).append((r, up))

        # 1. exposure
        w("## 1. Who can reach what")
        w("")
        pub = self.exposure["published"]
        if pub:
            listed = ", ".join(f"`{s}` ({', '.join(p)})" for s, p in sorted(pub.items()))
            w(f"In [`{COMPOSE}`]({PurePosixPath(os.path.relpath(ROOT / COMPOSE, self.doc_dir)).as_posix()}), only these services publish ports: {listed}.")
        if self.exposure["caddy_upstreams"]:
            w(f"Caddy forwards every request to {', '.join(f'`{u}`' for u in self.exposure['caddy_upstreams'])} (the Next.js app), so **third parties on the internet can call only the Next.js routes**.")
        if pub and "api" not in pub:
            w("The FastAPI service `api` publishes no port: it is reachable only from other containers (the Next.js server, workers).")
        for svc, env in sorted(self.exposure["env"].items()):
            pairs = ", ".join(f"`{k}={v}`" for k, v in sorted(env.items()))
            w(f"`{svc}` reaches FastAPI through {pairs}.")
        if self.cors:
            w(f"FastAPI CORS allows browser calls only from {', '.join(f'`{o}`' for o in self.cors)} (local development).")
        w("")

        w("### Public: no credentials")
        w("")
        w("| Layer | Method | Path | Accepts | Source |")
        w("| --- | --- | --- | --- | --- |")
        for r in self.routes:
            if not r.auth:
                for m in r.methods:
                    w(f"| Next.js (internet) | {m} | `{r.path}` | {self.esc(', '.join(f'`{x}`' for x in r.reads) or '—')} | {self.link(r.file)} |")
        for e in self.backend:
            if not e.auth:
                w(f"| FastAPI (internal in prod) | {e.method} | `{e.path}` | {self.params(e.params)} | {self.link(e.file, e.line)} |")
        w("")
        w("### Admin: needs credentials")
        w("")
        w("| Layer | Method | Path | Credential | Source |")
        w("| --- | --- | --- | --- | --- |")
        for r in self.routes:
            if r.auth:
                for m in r.methods:
                    w(f"| Next.js (internet) | {m} | `{r.path}` | {r.auth} (signed cookie) | {self.link(r.file)} |")
        for e in self.backend:
            if e.auth:
                w(f"| FastAPI (internal in prod) | {e.method} | `{e.path}` | {self.backend_auth(e)} | {self.link(e.file, e.line)} |")
        w("")
        if any(r.auth == "viewer session" for r in self.routes) and "ADMIN_VIEWER_ACCESS" in (read(SESSION_FILE) if (ROOT / SESSION_FILE).exists() else ""):
            w(f"A *viewer session* ({self.link(SESSION_FILE)}) is granted to GitHub ids in `ADMIN_GITHUB_IDS` or `ADMIN_VIEWER_GITHUB_IDS`; "
              "with `ADMIN_VIEWER_ACCESS=github` to any GitHub account, and with `ADMIN_VIEWER_ACCESS=public` to anyone without signing in. "
              "So with `public`, every Next.js admin route above is effectively a third-party API.")
            w("")
        for warning in self.config_warnings():
            w(f"> **Config warning:** {warning}")
            w("")

        # 2. chains
        w("## 2. Frontend → backend: which call reaches which endpoint")
        w("")
        w("One row per browser call site. The browser only talks to Next.js; the Next.js route then calls FastAPI or an external service.")
        w("")
        w("| Browser call (file) | Next.js route (file) | Calls upstream | Upstream handler (file) |")
        w("| --- | --- | --- | --- |")
        routes = {r.path: r for r in self.routes}
        for c in self.calls:
            r = routes.get(c.route)
            left = f"{c.method} `{c.path}` via {c.how}<br>{self.link(c.file, c.line)}"
            if not r:
                w(f"| {left} | **no matching route** | — | — |")
                continue
            mid = f"`{r.path}`<br>{self.link(r.file)}"
            ups = r.upstream or [None]
            for up in ups:
                if up is None:
                    w(f"| {left} | {mid} | none (handled in Next.js) | — |")
                    continue
                if up.kind == "backend":
                    targets = [self.by_key[k] for k in up.matches]
                    shown = "<br>".join(f"FastAPI {e.method} `{e.path}`" for e in targets) or f"**{up.method} `{up.target}` (missing)**"
                    files = "<br>".join(f"`{e.handler}` {self.link(e.file, e.line)}" for e in targets) or "—"
                else:
                    shown, files = f"{up.kind} {up.method} `{up.target}`", "external"
                w(f"| {left} | {mid} | {shown}<br>{up.via}, {self.link(r.file, up.line, f'line {up.line}')} | {files} |")
        w("")

        # 3. reference
        w("## 3. Next.js routes (`frontend/app/**/route.ts`)")
        w("")
        w("| Method | Path | Auth | Reads | Upstream | File |")
        w("| --- | --- | --- | --- | --- | --- |")
        for r in self.routes:
            ups = "<br>".join(
                (f"FastAPI {', '.join(f'`{k}`' for k in u.matches) or f'**`{u.target}` (missing)**'}" if u.kind == "backend" else f"{u.kind} `{u.target}`")
                for u in r.upstream
            ) or "—"
            reads = self.esc(", ".join(f"`{x}`" for x in r.reads)) or "—"
            w(f"| {', '.join(r.methods)} | `{r.path}` | {r.auth or 'public'} | {reads} | {ups} | {self.link(r.file)} |")
        w("")
        w("## 4. FastAPI endpoints (`backend/src/backend`)")
        w("")
        w("| Method | Path | Auth | Parameters | Response | Handler | Called by |")
        w("| --- | --- | --- | --- | --- | --- | --- |")
        for e in self.backend:
            callers = "<br>".join(sorted({self.link(r.file, None, r.path) for r, _ in backend_callers.get(f"{e.method} {e.path}", [])})) or "—"
            summary = f"<br>{self.esc(e.summary)}" if e.summary else ""
            w(f"| {e.method} | `{e.path}` | {self.backend_auth(e)} | {self.params(e.params)} | {f'`{self.esc(e.response_model)}`' if e.response_model else '—'} | `{e.handler}` {self.link(e.file, e.line)}{summary} | {callers} |")
        w("")

        # 5. gaps
        w("## 5. Gaps found by the generator")
        w("")
        unused = [e for e in self.backend if f"{e.method} {e.path}" not in backend_callers]
        w("FastAPI endpoints no Next.js route calls (reachable only inside the server, or by health checks):")
        w("")
        for e in unused:
            w(f"- {e.method} `{e.path}` ({self.link(e.file, e.line)})")
        if not unused:
            w("- none")
        w("")
        called = {c.route for c in self.calls}
        idle = [r for r in self.routes if r.path not in called]
        w("Next.js routes no browser code calls (used by other clients, redirects or OAuth):")
        w("")
        for r in idle:
            w(f"- {', '.join(r.methods)} `{r.path}` ({self.link(r.file)})")
        if not idle:
            w("- none")
        w("")
        w("Broken links (calls that reach no route; `--check` fails on these):")
        w("")
        for p in problems:
            w(f"- {self.esc(p)}")
        if not problems:
            w("- none")
        w("")
        w(END)
        return "\n".join(out) + "\n"


INTRO = """# API map

Generated from the code by [`scripts/update_api_map.py`](../../../scripts/update_api_map.py). Do not edit between the markers; change the code and run:

```bash
python scripts/update_api_map.py          # rewrite this file
python scripts/update_api_map.py --check  # exit 1 if stale or a call reaches no route
```

The pre-commit hook runs it, so the map follows every commit. It answers three questions: what is exposed to third parties (section 1), which frontend call reaches which backend endpoint and in which files (section 2), and the full route lists (sections 3 and 4). The public, hand-written contract for API users is [`frontend/public/api-reference.md`](../../../frontend/public/api-reference.md).

"""


def build() -> tuple[str, list[str], dict]:
    backend, cors = parse_backend()
    routes = parse_routes()
    calls = parse_browser_calls()
    exposure = parse_exposure()
    problems = check_helpers() + link_up(backend, routes, calls)
    body = Renderer(backend, cors, routes, calls, exposure).render(problems)
    model = {"backend": [asdict(e) for e in backend], "cors": cors, "routes": [asdict(r) for r in routes],
             "browser_calls": [asdict(c) for c in calls], "exposure": exposure, "problems": problems}
    return body, problems, model


def merged(current: str | None, body: str) -> str:
    if current and START in current and END in current:
        head = current.split(START, 1)[0]
        tail = current.split(END, 1)[1].lstrip("\n")
        return head + body + (("\n" + tail) if tail else "")
    return INTRO + body


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--check", action="store_true", help="exit 1 if the map is stale or has broken links")
    group.add_argument("--diff", action="store_true", help="print the changes, write nothing")
    group.add_argument("--json", action="store_true", help="print the parsed model as JSON")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    body, problems, model = build()
    if args.json:
        print(json.dumps(model, indent=2))
        return 0
    path = ROOT / DOC
    current = path.read_text(encoding="utf-8") if path.exists() else None
    wanted = merged(current, body)

    if args.diff:
        sys.stdout.writelines(difflib.unified_diff((current or "").splitlines(True), wanted.splitlines(True), DOC, DOC))
        return 0
    if args.check:
        stale = current != wanted
        if stale:
            print(f"{DOC} is stale; run: python scripts/update_api_map.py", file=sys.stderr)
        for p in problems:
            print(f"api-map: {p}", file=sys.stderr)
        return 1 if stale or problems else 0
    if current != wanted:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(wanted.encode("utf-8"))  # LF endings on every OS
        if not args.quiet:
            print(f"wrote {DOC}")
    elif not args.quiet:
        print(f"{DOC} is up to date")
    for p in problems:
        print(f"api-map: {p}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
