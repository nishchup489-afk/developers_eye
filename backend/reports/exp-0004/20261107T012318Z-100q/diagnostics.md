# Developer's Eye | EXP-0004 Batch Search Diagnostics

Run: `20261107T012318Z-100q` | Queries: **100** | Corpus snapshot: {'text': {'N': 42114, 'avgDL': 697.5938412665881}, 'code': {'N': 42114, 'avgDL': 231.70477841049765}}

**Scope:** same retrieved candidate IDs, ranked by BM25 versus PostgreSQL 
`ts_rank_cd`. TITLE_HINT and language are heuristics, not human relevance 
grades. Rank agreement is not ranking quality. The corpus can change 
between queries while the crawler runs. This is not Recall@100, 
Precision@10, MRR@10 or nDCG@10.

Flags: MULTILINGUAL_TOP: 56, LOW_AGREEMENT: 24, TARGET_BELOW_K: 9, TARGET_NOT_IN_CANDIDATES: 6, ZERO_RESULTS: 4, THIN_POOL: 2

## All queries

| ID | Category | Query | Mode | Candidates | Overlap | Time (ms) | Flags |
|---|---|---|---|---:|---:|---:|---|
| Q001 | Python Core | python list comprehension | text | 71 | 30% | 74 | MULTILINGUAL_TOP, TARGET_NOT_IN_CANDIDATES |
| Q002 | Python Core | python dict get default | code | 100 | 0% | 184 | LOW_AGREEMENT, MULTILINGUAL_TOP |
| Q003 | Python Core | python generator yield from | all | 100 | 50% | 129 | OK |
| Q004 | Python Core | python dataclasses | text | 43 | 30% | 19 | OK |
| Q005 | Python Core | python type hints | text | 100 | 40% | 386 | OK |
| Q006 | Python Core | python pathlib Path | code | 22 | 20% | 54 | LOW_AGREEMENT, MULTILINGUAL_TOP |
| Q007 | Python Core | python logging configuration | text | 100 | 60% | 80 | MULTILINGUAL_TOP |
| Q008 | Python Core | python virtual environment venv | text | 34 | 60% | 60 | OK |
| Q009 | Python Core | python context manager | all | 174 | 0% | 287 | LOW_AGREEMENT, MULTILINGUAL_TOP |
| Q010 | Python Core | python exception traceback | all | 149 | 30% | 418 | OK |
| Q011 | Python Async | python async api | text | 100 | 30% | 164 | OK |
| Q012 | Python Async | python asyncio event loop | text | 46 | 50% | 170 | OK |
| Q013 | Python Async | asyncio.create_task | code | 6 | 100% | 6 | OK |
| Q014 | Python Async | asyncio gather | all | 9 | 100% | 21 | OK |
| Q015 | Python Async | asyncio TaskGroup | code | 1 | 100% | 3 | THIN_POOL |
| Q016 | Python Async | async await python | all | 145 | 30% | 245 | MULTILINGUAL_TOP |
| Q017 | Python Async | asyncio Semaphore | code | 0 | N/A | 0 | ZERO_RESULTS, TARGET_NOT_IN_CANDIDATES |
| Q018 | Python Async | python concurrent.futures | text | 32 | 30% | 32 | OK |
| Q019 | Python Async | python async generator | all | 100 | 30% | 171 | OK |
| Q020 | Python Async | python thread pool executor | all | 7 | 100% | 64 | OK |
| Q021 | FastAPI Basics | FastAPI path parameters | text | 100 | 10% | 229 | LOW_AGREEMENT, MULTILINGUAL_TOP |
| Q022 | FastAPI Basics | FastAPI request body | text | 100 | 10% | 220 | LOW_AGREEMENT, MULTILINGUAL_TOP |
| Q023 | FastAPI Basics | FastAPI query parameters | text | 100 | 50% | 170 | MULTILINGUAL_TOP |
| Q024 | FastAPI Basics | FastAPI Depends | all | 156 | 70% | 192 | MULTILINGUAL_TOP |
| Q025 | FastAPI Basics | FastAPI async tests | text | 25 | 40% | 16 | OK |
| Q026 | FastAPI Basics | FastAPI response model | text | 100 | 90% | 116 | MULTILINGUAL_TOP, TARGET_BELOW_K |
| Q027 | FastAPI Basics | FastAPI HTTPException | all | 170 | 90% | 280 | MULTILINGUAL_TOP |
| Q028 | FastAPI Basics | FastAPI middleware | text | 55 | 50% | 46 | MULTILINGUAL_TOP |
| Q029 | FastAPI Basics | FastAPI background tasks | all | 64 | 80% | 194 | MULTILINGUAL_TOP |
| Q030 | FastAPI Basics | FastAPI WebSockets | all | 100 | 10% | 130 | LOW_AGREEMENT, MULTILINGUAL_TOP |
| Q031 | FastAPI Advanced | FastAPI CORS | text | 100 | 50% | 256 | MULTILINGUAL_TOP |
| Q032 | FastAPI Advanced | FastAPI OAuth2 | text | 100 | 80% | 97 | MULTILINGUAL_TOP, TARGET_BELOW_K |
| Q033 | FastAPI Advanced | FastAPI dependency overrides | all | 71 | 30% | 239 | MULTILINGUAL_TOP |
| Q034 | FastAPI Advanced | FastAPI lifespan events | text | 48 | 70% | 41 | MULTILINGUAL_TOP, TARGET_BELOW_K |
| Q035 | FastAPI Advanced | FastAPI upload file | text | 42 | 0% | 168 | LOW_AGREEMENT, MULTILINGUAL_TOP, TARGET_BELOW_K |
| Q036 | FastAPI Advanced | FastAPI streaming response | code | 40 | 0% | 20 | LOW_AGREEMENT, MULTILINGUAL_TOP |
| Q037 | FastAPI Advanced | FastAPI custom OpenAPI | text | 60 | 0% | 55 | LOW_AGREEMENT, MULTILINGUAL_TOP |
| Q038 | FastAPI Advanced | FastAPI settings environment variables | text | 5 | 100% | 685 | OK |
| Q039 | FastAPI Advanced | FastAPI APIRouter | code | 78 | 0% | 51 | LOW_AGREEMENT, MULTILINGUAL_TOP, TARGET_BELOW_K |
| Q040 | FastAPI Advanced | FastAPI status codes | text | 100 | 0% | 58 | LOW_AGREEMENT, MULTILINGUAL_TOP, TARGET_BELOW_K |
| Q041 | Django | django asynchronous support | text | 76 | 50% | 97 | OK |
| Q042 | Django | django ORM filter | all | 98 | 30% | 135 | MULTILINGUAL_TOP |
| Q043 | Django | django migrations | text | 100 | 40% | 138 | MULTILINGUAL_TOP |
| Q044 | Django | django class based views | text | 100 | 50% | 875 | OK |
| Q045 | Django | django middleware | text | 100 | 40% | 69 | MULTILINGUAL_TOP |
| Q046 | Django | django cache framework | text | 100 | 20% | 66 | LOW_AGREEMENT, TARGET_BELOW_K |
| Q047 | Django | django authentication | text | 100 | 90% | 55 | MULTILINGUAL_TOP |
| Q048 | Django | django template language | text | 100 | 30% | 75 | OK |
| Q049 | Django | django model field | all | 162 | 20% | 182 | LOW_AGREEMENT, MULTILINGUAL_TOP |
| Q050 | Django | django QuerySet select_related | code | 30 | 50% | 44 | MULTILINGUAL_TOP |
| Q051 | JavaScript | javascript fetch examples | all | 162 | 20% | 146 | LOW_AGREEMENT, TARGET_NOT_IN_CANDIDATES |
| Q052 | JavaScript | javascript Promise.all | code | 44 | 60% | 27 | MULTILINGUAL_TOP |
| Q053 | JavaScript | javascript async await | text | 100 | 60% | 105 | MULTILINGUAL_TOP |
| Q054 | JavaScript | javascript array map filter | all | 94 | 40% | 122 | OK |
| Q055 | JavaScript | javascript event loop | text | 100 | 30% | 57 | OK |
| Q056 | JavaScript | javascript closures | text | 100 | 70% | 60 | MULTILINGUAL_TOP |
| Q057 | JavaScript | javascript destructuring assignment | text | 77 | 40% | 36 | MULTILINGUAL_TOP |
| Q058 | JavaScript | javascript optional chaining | text | 100 | 80% | 73 | MULTILINGUAL_TOP |
| Q059 | JavaScript | javascript Object.entries | code | 26 | 100% | 11 | MULTILINGUAL_TOP |
| Q060 | JavaScript | javascript modules import export | text | 100 | 50% | 192 | MULTILINGUAL_TOP |
| Q061 | Web Platform | HTTP 404 | code | 100 | 0% | 31 | LOW_AGREEMENT, MULTILINGUAL_TOP |
| Q062 | Web Platform | HTTP 500 internal server error | text | 100 | 90% | 192 | MULTILINGUAL_TOP |
| Q063 | Web Platform | HTTP caching Cache-Control | all | 105 | 40% | 249 | MULTILINGUAL_TOP |
| Q064 | Web Platform | HTTP CORS preflight | text | 81 | 40% | 49 | MULTILINGUAL_TOP |
| Q065 | Web Platform | Content Security Policy | text | 100 | 50% | 71 | MULTILINGUAL_TOP |
| Q066 | Web Platform | HTML forms validation | text | 100 | 30% | 143 | OK |
| Q067 | Web Platform | CSS flexbox | text | 100 | 20% | 68 | LOW_AGREEMENT, MULTILINGUAL_TOP, TARGET_BELOW_K |
| Q068 | Web Platform | CSS grid layout | text | 100 | 60% | 98 | MULTILINGUAL_TOP |
| Q069 | Web Platform | WebSocket API | text | 100 | 70% | 58 | MULTILINGUAL_TOP |
| Q070 | Web Platform | service worker fetch event | all | 105 | 10% | 227 | LOW_AGREEMENT, MULTILINGUAL_TOP |
| Q071 | Rust | Rust ownership borrowing | text | 53 | 20% | 66 | LOW_AGREEMENT, TARGET_NOT_IN_CANDIDATES |
| Q072 | Rust | Rust lifetimes | text | 100 | 50% | 42 | TARGET_NOT_IN_CANDIDATES |
| Q073 | Rust | Rust Result Option | code | 100 | 10% | 52 | LOW_AGREEMENT |
| Q074 | Rust | Rust async await | all | 29 | 80% | 21 | OK |
| Q075 | Rust | Rust Vec push | code | 27 | 40% | 42 | OK |
| Q076 | Rust | Rust HashMap entry | code | 12 | 90% | 24 | OK |
| Q077 | Rust | Rust traits generics | text | 100 | 30% | 55 | OK |
| Q078 | Rust | Rust iterator map | all | 117 | 20% | 196 | LOW_AGREEMENT |
| Q079 | Rust | Rust pattern matching | text | 97 | 50% | 122 | TARGET_BELOW_K |
| Q080 | Rust | Rust cargo workspace | text | 17 | 80% | 14 | TARGET_NOT_IN_CANDIDATES |
| Q081 | Identifiers | __init__ | code | 100 | 70% | 139 | MULTILINGUAL_TOP |
| Q082 | Identifiers | get_user_by_id | code | 0 | N/A | 5 | ZERO_RESULTS |
| Q083 | Identifiers | useEffect | code | 2 | 100% | 3 | THIN_POOL |
| Q084 | Identifiers | __enter__ | code | 100 | 0% | 78 | LOW_AGREEMENT, MULTILINGUAL_TOP |
| Q085 | Identifiers | __aenter__ | code | 6 | 100% | 5 | OK |
| Q086 | Identifiers | HTTPException | code | 100 | 0% | 38 | LOW_AGREEMENT, MULTILINGUAL_TOP |
| Q087 | Identifiers | select_related | code | 44 | 50% | 66 | MULTILINGUAL_TOP |
| Q088 | Identifiers | requestAnimationFrame | code | 100 | 70% | 33 | MULTILINGUAL_TOP |
| Q089 | Identifiers | fetch() | code | 100 | 50% | 49 | MULTILINGUAL_TOP |
| Q090 | Identifiers | QuerySet | code | 100 | 0% | 109 | LOW_AGREEMENT, MULTILINGUAL_TOP |
| Q091 | Edge Cases | asynci create task | text | 0 | N/A | 2 | ZERO_RESULTS |
| Q092 | Edge Cases | fastapi dependecy injection | text | 0 | N/A | 1 | ZERO_RESULTS |
| Q093 | Edge Cases | python OR javascript | text | 100 | 10% | 773 | LOW_AGREEMENT, MULTILINGUAL_TOP |
| Q094 | Edge Cases | python -django | text | 100 | 30% | 114 | OK |
| Q095 | Edge Cases | "event loop" | text | 100 | 70% | 69 | OK |
| Q096 | Edge Cases | HTTP/2 | all | 132 | 60% | 74 | MULTILINGUAL_TOP |
| Q097 | Edge Cases | python C++ | all | 148 | 30% | 330 | OK |
| Q098 | Edge Cases | async def fetch | code | 12 | 90% | 11 | MULTILINGUAL_TOP |
| Q099 | Edge Cases | zznonexistentdevelopertermzz | all | 0 | N/A | 2 | OK |
| Q100 | Edge Cases | qwertyuiopasdfghzxcvbnm | text | 0 | N/A | 1 | OK |

## Flagged queries

### Q001: python list comprehension

Mode: `text` | Flags: `MULTILINGUAL_TOP, TARGET_NOT_IN_CANDIDATES` | Candidates: 71 | Time: 74 ms

**BM25 top 10**

1. [6. Expressions](https://docs.python.org/3/reference/expressions.html) (id=7973, locale=en)
2. [The Python Tutorial](https://docs.python.org/3/tutorial/index.html) (id=152, locale=en)
3. [5. Data Structures](https://docs.python.org/3/tutorial/datastructures.html) (id=8020, locale=en)
4. [Functional Programming HOWTO](https://docs.python.org/3/howto/functional.html) (id=8104, locale=en)
5. [6. Editors and IDEs](https://docs.python.org/3/using/editors.html) (id=8117, locale=en)
6. [ast — Abstract Syntax Trees](https://docs.python.org/3/library/ast.html) (id=7659, locale=en)
7. [Getting started | Django documentation](https://docs.djangoproject.com/en/6.1/intro/) (id=27758, locale=en)
8. [さぁ始めましょう | Django ドキュメント](https://docs.djangoproject.com/ja/6.1/intro/) (id=37903, locale=ja)
9. [开始 | Django 文档](https://docs.djangoproject.com/zh-hans/6.1/intro/) (id=63050, locale=zh)
10. [시작하기 | Django 문서](https://docs.djangoproject.com/ko/6.1/intro/) (id=37906, locale=ko)

**PostgreSQL top 10**

1. [What’s New in Python 2.0](https://docs.python.org/3/whatsnew/2.0.html) (id=8033, locale=en)
2. [Functional Programming HOWTO](https://docs.python.org/3/howto/functional.html) (id=8104, locale=en)
3. [What’s New in Python 2.4](https://docs.python.org/3/whatsnew/2.4.html) (id=8012, locale=en)
4. [Index — Python 3.12.16 documentation](https://docs.python.org/3/genindex-all.html) (id=36451, locale=en)
5. [Built-in Types](https://docs.python.org/3/library/stdtypes.html) (id=38356, locale=en)
6. [Programming FAQ](https://docs.python.org/3/faq/programming.html) (id=8169, locale=en)
7. [Python Documentation contents](https://docs.python.org/3/contents.html) (id=165, locale=en)
8. [What’s New in Python](https://docs.python.org/3/whatsnew/index.html) (id=151, locale=en)
9. [Getting started | Django documentation](https://docs.djangoproject.com/en/6.1/intro/) (id=27758, locale=en)
10. [시작하기 | Django 문서](https://docs.djangoproject.com/ko/6.1/intro/) (id=37906, locale=ko)

### Q002: python dict get default

Mode: `code` | Flags: `LOW_AGREEMENT, MULTILINGUAL_TOP` | Candidates: 100 | Time: 184 ms

**BM25 top 10**

1. [django.contrib.postgres.forms.hstore | Εγχειρίδιο Django](https://docs.djangoproject.com/el/6.1/_modules/django/contrib/postgres/forms/hstore/) (id=28616, locale=el)
2. [django.urls.resolvers | Django ドキュメント](https://docs.djangoproject.com/ja/6.1/_modules/django/urls/resolvers/) (id=41700, locale=ja)
3. [django.urls.resolvers | Django documentation](https://docs.djangoproject.com/en/6.1/_modules/django/urls/resolvers/) (id=41692, locale=en)
4. [django.urls.resolvers | Dokumentasi Django](https://docs.djangoproject.com/id/6.1/_modules/django/urls/resolvers/) (id=41698, locale=id)
5. [django.urls.resolvers | Django 문서](https://docs.djangoproject.com/ko/6.1/_modules/django/urls/resolvers/) (id=41702, locale=ko)
6. [django.urls.resolvers | Dokumentacja Django](https://docs.djangoproject.com/pl/6.1/_modules/django/urls/resolvers/) (id=41704, locale=pl)
7. [django.urls.resolvers | Django 文档](https://docs.djangoproject.com/zh-hans/6.1/_modules/django/urls/resolvers/) (id=41708, locale=zh)
8. [django.urls.resolvers | Documentación de Django](https://docs.djangoproject.com/es/6.1/_modules/django/urls/resolvers/) (id=41694, locale=es)
9. [django.urls.resolvers | Documentation de Django](https://docs.djangoproject.com/fr/6.1/_modules/django/urls/resolvers/) (id=41696, locale=fr)
10. [django.urls.resolvers | Documentação do Django](https://docs.djangoproject.com/pt-br/6.1/_modules/django/urls/resolvers/) (id=41706, locale=pt)

**PostgreSQL top 10**

1. [APIRouter class - FastAPI](https://fastapi.tiangolo.com/reference/apirouter/) (id=27904, locale=en)
2. [APIRouter class - FastAPI](https://fastapi.tiangolo.com/de/reference/apirouter/) (id=28676, locale=de)
3. [APIRouter class - FastAPI](https://fastapi.tiangolo.com/es/reference/apirouter/) (id=29435, locale=es)
4. [APIRouter class - FastAPI](https://fastapi.tiangolo.com/fr/reference/apirouter/) (id=30193, locale=fr)
5. [APIRouter class - FastAPI](https://fastapi.tiangolo.com/hi/reference/apirouter/) (id=30951, locale=hi)
6. [APIRouter class - FastAPI](https://fastapi.tiangolo.com/ja/reference/apirouter/) (id=31644, locale=ja)
7. [APIRouter class - FastAPI](https://fastapi.tiangolo.com/ko/reference/apirouter/) (id=32250, locale=ko)
8. [APIRouter class - FastAPI](https://fastapi.tiangolo.com/pt/reference/apirouter/) (id=32855, locale=pt)
9. [APIRouter class - FastAPI](https://fastapi.tiangolo.com/ru/reference/apirouter/) (id=33464, locale=ru)
10. [APIRouter class - FastAPI](https://fastapi.tiangolo.com/tr/reference/apirouter/) (id=34048, locale=tr)

### Q006: python pathlib Path

Mode: `code` | Flags: `LOW_AGREEMENT, MULTILINGUAL_TOP` | Candidates: 22 | Time: 54 ms

**BM25 top 10**

1. [How to override templates | Django documentation](https://docs.djangoproject.com/en/6.1/howto/overriding-templates/) (id=37626, locale=en)
2. [What’s new in Python 3.15](https://docs.python.org/3/whatsnew/3.15.html) (id=150, locale=en)
3. [zipapp — Manage executable Python zip archives](https://docs.python.org/3/library/zipapp.html) (id=7928, locale=en)
4. [管理文件 | Django 文档](https://docs.djangoproject.com/zh-hans/6.1/topics/files/) (id=65231, locale=zh)
5. [ファイルの管理 | Django ドキュメント](https://docs.djangoproject.com/ja/6.1/topics/files/) (id=65223, locale=ja)
6. [Hantera filer | Django-dokumentation](https://docs.djangoproject.com/sv/6.1/topics/files/) (id=65228, locale=sv)
7. [Managing files | Django documentation](https://docs.djangoproject.com/en/6.1/topics/files/) (id=28223, locale=en)
8. [Gestion des fichiers | Documentation de Django](https://docs.djangoproject.com/fr/6.1/topics/files/) (id=65221, locale=fr)
9. [pathlib — Object-oriented filesystem paths](https://docs.python.org/3/library/pathlib.html) (id=7820, locale=en)
10. [What’s new in Python 3.14](https://docs.python.org/3/whatsnew/3.14.html) (id=7589, locale=en)

**PostgreSQL top 10**

1. [What’s new in Python 3.15](https://docs.python.org/3/whatsnew/3.15.html) (id=150, locale=en)
2. [GeoDjango Tutorial | Django documentation](https://docs.djangoproject.com/en/6.1/ref/contrib/gis/tutorial/) (id=63658, locale=en)
3. [How to override templates | Django documentation](https://docs.djangoproject.com/en/6.1/howto/overriding-templates/) (id=37626, locale=en)
4. [django.views.debug | Django documentation](https://docs.djangoproject.com/en/6.1/_modules/django/views/debug/) (id=42047, locale=en)
5. [django.views.debug | Dokumentasi Django](https://docs.djangoproject.com/id/6.1/_modules/django/views/debug/) (id=42053, locale=id)
6. [django.views.debug | Django ドキュメント](https://docs.djangoproject.com/ja/6.1/_modules/django/views/debug/) (id=42055, locale=ja)
7. [django.views.debug | Django 문서](https://docs.djangoproject.com/ko/6.1/_modules/django/views/debug/) (id=42057, locale=ko)
8. [django.views.debug | Dokumentacja Django](https://docs.djangoproject.com/pl/6.1/_modules/django/views/debug/) (id=42059, locale=pl)
9. [django.views.debug | Django 文档](https://docs.djangoproject.com/zh-hans/6.1/_modules/django/views/debug/) (id=42063, locale=zh)
10. [django.views.debug | Documentación de Django](https://docs.djangoproject.com/es/6.1/_modules/django/views/debug/) (id=42049, locale=es)

### Q007: python logging configuration

Mode: `text` | Flags: `MULTILINGUAL_TOP` | Candidates: 100 | Time: 80 ms

**BM25 top 10**

1. [How to configure and use logging | Django documentation](https://docs.djangoproject.com/en/6.1/howto/logging/) (id=62308, locale=en)
2. [Logging | Django documentation](https://docs.djangoproject.com/en/6.1/topics/logging/) (id=28302, locale=en)
3. [OpenTelemetry - FastAPI](https://fastapi.tiangolo.com/advanced/opentelemetry/) (id=27597, locale=en)
4. [Logging | Django documentation](https://docs.djangoproject.com/en/6.1/ref/logging/) (id=62345, locale=en)
5. [Logging HOWTO](https://docs.python.org/3/howto/logging.html) (id=8111, locale=en)
6. [Journalisation | Documentation de Django](https://docs.djangoproject.com/fr/6.1/topics/logging/) (id=65442, locale=fr)
7. [Logging Cookbook](https://docs.python.org/3/howto/logging-cookbook.html) (id=8101, locale=en)
8. [logging.config — Logging configuration](https://docs.python.org/3/library/logging.config.html) (id=7791, locale=en)
9. [日志 | Django 文档](https://docs.djangoproject.com/zh-hans/6.1/topics/logging/) (id=65452, locale=zh)
10. [ロギング | Django ドキュメント](https://docs.djangoproject.com/ja/6.1/topics/logging/) (id=65445, locale=ja)

**PostgreSQL top 10**

1. [How to configure and use logging | Django documentation](https://docs.djangoproject.com/en/6.1/howto/logging/) (id=62308, locale=en)
2. [Logging | Django documentation](https://docs.djangoproject.com/en/6.1/topics/logging/) (id=28302, locale=en)
3. [Logging | Django documentation](https://docs.djangoproject.com/en/6.1/ref/logging/) (id=62345, locale=en)
4. [Réglages | Documentation de Django](https://docs.djangoproject.com/fr/6.1/ref/settings/) (id=64141, locale=fr)
5. [Logging HOWTO](https://docs.python.org/3/howto/logging.html) (id=8111, locale=en)
6. [Logging Cookbook](https://docs.python.org/3/howto/logging-cookbook.html) (id=8101, locale=en)
7. [What’s New In Python 3.2](https://docs.python.org/3/whatsnew/3.2.html) (id=8018, locale=en)
8. [The Python standard library](https://docs.python.org/3/library/index.html) (id=153, locale=en)
9. [logging.config — Logging configuration](https://docs.python.org/3/library/logging.config.html) (id=7791, locale=en)
10. [Index — Python 3.12.16 documentation](https://docs.python.org/3/genindex-all.html) (id=36451, locale=en)

### Q009: python context manager

Mode: `all` | Flags: `LOW_AGREEMENT, MULTILINGUAL_TOP` | Candidates: 174 | Time: 287 ms

**BM25 top 10**

1. [django.shortcuts | Εγχειρίδιο Django](https://docs.djangoproject.com/el/6.1/_modules/django/shortcuts/) (id=29565, locale=el)
2. [django.shortcuts | Django ドキュメント](https://docs.djangoproject.com/ja/6.1/_modules/django/shortcuts/) (id=41285, locale=ja)
3. [django.shortcuts | Django 文档](https://docs.djangoproject.com/zh-hans/6.1/_modules/django/shortcuts/) (id=41293, locale=zh)
4. [django.shortcuts | Django 문서](https://docs.djangoproject.com/ko/6.1/_modules/django/shortcuts/) (id=41287, locale=ko)
5. [django.shortcuts | Dokumentasi Django](https://docs.djangoproject.com/id/6.1/_modules/django/shortcuts/) (id=41283, locale=id)
6. [django.shortcuts | Dokumentacja Django](https://docs.djangoproject.com/pl/6.1/_modules/django/shortcuts/) (id=41289, locale=pl)
7. [django.shortcuts | Documentação do Django](https://docs.djangoproject.com/pt-br/6.1/_modules/django/shortcuts/) (id=41291, locale=pt)
8. [django.shortcuts | Django documentation](https://docs.djangoproject.com/en/6.1/_modules/django/shortcuts/) (id=41278, locale=en)
9. [django.shortcuts | Documentación de Django](https://docs.djangoproject.com/es/6.1/_modules/django/shortcuts/) (id=41280, locale=es)
10. [django.shortcuts | Documentation de Django](https://docs.djangoproject.com/fr/6.1/_modules/django/shortcuts/) (id=41282, locale=fr)

**PostgreSQL top 10**

1. [Django Utils | Django documentation](https://docs.djangoproject.com/en/6.1/ref/utils/) (id=62362, locale=en)
2. [sqlite3 — DB-API 2.0 interface for SQLite databases](https://docs.python.org/3/library/sqlite3.html) (id=7833, locale=en)
3. [Django 1.7 release notes | Django documentation](https://docs.djangoproject.com/en/6.1/releases/1.7/) (id=62523, locale=en)
4. [3. Data model](https://docs.python.org/3/reference/datamodel.html) (id=7988, locale=en)
5. [unittest.mock — getting started](https://docs.python.org/3/library/unittest.mock-examples.html) (id=8017, locale=en)
6. [Django 1.3 release notes | Django documentation](https://docs.djangoproject.com/en/6.1/releases/1.3/) (id=62955, locale=en)
7. [QuerySet API reference | Django documentation](https://docs.djangoproject.com/en/6.1/ref/models/querysets/) (id=28041, locale=en)
8. [Référence de l’API QuerySet | Documentation de Django](https://docs.djangoproject.com/fr/6.1/ref/models/querysets/) (id=64090, locale=fr)
9. [Réglages | Documentation de Django](https://docs.djangoproject.com/fr/6.1/ref/settings/) (id=64141, locale=fr)
10. [Index — Python 3.12.16 documentation](https://docs.python.org/3/genindex-all.html) (id=36451, locale=en)

### Q015: asyncio TaskGroup

Mode: `code` | Flags: `THIN_POOL` | Candidates: 1 | Time: 3 ms

**BM25 top 10**

1. [Coroutines and Tasks](https://docs.python.org/3/library/asyncio-task.html) (id=7965, locale=en)

**PostgreSQL top 10**

1. [Coroutines and Tasks](https://docs.python.org/3/library/asyncio-task.html) (id=7965, locale=en)

### Q016: async await python

Mode: `all` | Flags: `MULTILINGUAL_TOP` | Candidates: 145 | Time: 245 ms

**BM25 top 10**

1. [异步支持 | Django 文档](https://docs.djangoproject.com/zh-hans/6.1/topics/async/) (id=64925, locale=zh)
2. [非同期サポート | Django ドキュメント](https://docs.djangoproject.com/ja/6.1/topics/async/) (id=64919, locale=ja)
3. [Asynchronous support | Django documentation](https://docs.djangoproject.com/en/6.1/topics/async/) (id=28115, locale=en)
4. [Streams](https://docs.python.org/3/library/asyncio-stream.html) (id=8138, locale=en)
5. [Asynkront stöd | Django-dokumentation](https://docs.djangoproject.com/sv/6.1/topics/async/) (id=64923, locale=sv)
6. [Gestion du code asynchrone | Documentation de Django](https://docs.djangoproject.com/fr/6.1/topics/async/) (id=64917, locale=fr)
7. [asyncio and free-threaded Python](https://docs.python.org/3/library/asyncio-threading.html) (id=8172, locale=en)
8. [A Conceptual Overview of asyncio](https://docs.python.org/3/howto/a-conceptual-overview-of-asyncio.html) (id=8082, locale=en)
9. [Async Tests - FastAPI](https://fastapi.tiangolo.com/advanced/async-tests/) (id=27557, locale=en)
10. [Coroutines and Tasks](https://docs.python.org/3/library/asyncio-task.html) (id=7965, locale=en)

**PostgreSQL top 10**

1. [What’s New In Python 3.5](https://docs.python.org/3/whatsnew/3.5.html) (id=8011, locale=en)
2. [What’s New In Python 3.6](https://docs.python.org/3/whatsnew/3.6.html) (id=7987, locale=en)
3. [What’s New In Python 3.7](https://docs.python.org/3/whatsnew/3.7.html) (id=7981, locale=en)
4. [profiling.sampling — Statistical profiler](https://docs.python.org/3/library/profiling.sampling.html) (id=7863, locale=en)
5. [3. Data model](https://docs.python.org/3/reference/datamodel.html) (id=7988, locale=en)
6. [Index — Python 3.12.16 documentation](https://docs.python.org/3/genindex-all.html) (id=36451, locale=en)
7. [Async Tests - FastAPI](https://fastapi.tiangolo.com/advanced/async-tests/) (id=27557, locale=en)
8. [6. Expressions](https://docs.python.org/3/reference/expressions.html) (id=7973, locale=en)
9. [A Conceptual Overview of asyncio](https://docs.python.org/3/howto/a-conceptual-overview-of-asyncio.html) (id=8082, locale=en)
10. [异步支持 | Django 文档](https://docs.djangoproject.com/zh-hans/6.1/topics/async/) (id=64925, locale=zh)

### Q017: asyncio Semaphore

Mode: `code` | Flags: `ZERO_RESULTS, TARGET_NOT_IN_CANDIDATES` | Candidates: 0 | Time: 0 ms

### Q021: FastAPI path parameters

Mode: `text` | Flags: `LOW_AGREEMENT, MULTILINGUAL_TOP` | Candidates: 100 | Time: 229 ms

**BM25 top 10**

1. [Path Parameters - FastAPI](https://fastapi.tiangolo.com/tutorial/path-params/) (id=28188, locale=en)
2. [Query Parameters - FastAPI](https://fastapi.tiangolo.com/tutorial/query-params/) (id=28202, locale=en)
3. [Request Body - FastAPI](https://fastapi.tiangolo.com/tutorial/body/) (id=28074, locale=en)
4. [Using the Request Directly - FastAPI](https://fastapi.tiangolo.com/advanced/using-request-directly/) (id=27677, locale=en)
5. [Path Operation Configuration - FastAPI](https://fastapi.tiangolo.com/tutorial/path-operation-configuration/) (id=28178, locale=en)
6. [Path Operation Advanced Configuration - FastAPI](https://fastapi.tiangolo.com/advanced/path-operation-advanced-configuration/) (id=27601, locale=en)
7. [APIRouter class - FastAPI](https://fastapi.tiangolo.com/reference/apirouter/) (id=27904, locale=en)
8. [APIRouter class - FastAPI](https://fastapi.tiangolo.com/de/reference/apirouter/) (id=28676, locale=de)
9. [APIRouter class - FastAPI](https://fastapi.tiangolo.com/es/reference/apirouter/) (id=29435, locale=es)
10. [APIRouter class - FastAPI](https://fastapi.tiangolo.com/fr/reference/apirouter/) (id=30193, locale=fr)

**PostgreSQL top 10**

1. [Path Parameters - FastAPI](https://fastapi.tiangolo.com/tutorial/path-params/) (id=28188, locale=en)
2. [Path Parameters - FastAPI](https://fastapi.tiangolo.com/hi/tutorial/path-params/) (id=31224, locale=hi)
3. [Request Parameters - FastAPI](https://fastapi.tiangolo.com/reference/parameters/) (id=27958, locale=en)
4. [Request Parameters - FastAPI](https://fastapi.tiangolo.com/de/reference/parameters/) (id=28731, locale=de)
5. [Request Parameters - FastAPI](https://fastapi.tiangolo.com/es/reference/parameters/) (id=29490, locale=es)
6. [Request Parameters - FastAPI](https://fastapi.tiangolo.com/fr/reference/parameters/) (id=30248, locale=fr)
7. [Request Parameters - FastAPI](https://fastapi.tiangolo.com/hi/reference/parameters/) (id=31005, locale=hi)
8. [Request Parameters - FastAPI](https://fastapi.tiangolo.com/ja/reference/parameters/) (id=31687, locale=ja)
9. [Request Parameters - FastAPI](https://fastapi.tiangolo.com/ko/reference/parameters/) (id=32294, locale=ko)
10. [Request Parameters - FastAPI](https://fastapi.tiangolo.com/pt/reference/parameters/) (id=32899, locale=pt)

### Q022: FastAPI request body

Mode: `text` | Flags: `LOW_AGREEMENT, MULTILINGUAL_TOP` | Candidates: 100 | Time: 220 ms

**BM25 top 10**

1. [Request Body - FastAPI](https://fastapi.tiangolo.com/tutorial/body/) (id=28074, locale=en)
2. [Path Operation Advanced Configuration - FastAPI](https://fastapi.tiangolo.com/advanced/path-operation-advanced-configuration/) (id=27601, locale=en)
3. [OpenAPI Callbacks - FastAPI](https://fastapi.tiangolo.com/advanced/openapi-callbacks/) (id=27589, locale=en)
4. [Handling Errors - FastAPI](https://fastapi.tiangolo.com/tutorial/handling-errors/) (id=28153, locale=en)
5. [OpenAPI Webhooks - FastAPI](https://fastapi.tiangolo.com/advanced/openapi-webhooks/) (id=27593, locale=en)
6. [Using the Request Directly - FastAPI](https://fastapi.tiangolo.com/advanced/using-request-directly/) (id=27677, locale=en)
7. [Request class - FastAPI](https://fastapi.tiangolo.com/reference/request/) (id=27963, locale=en)
8. [Request class - FastAPI](https://fastapi.tiangolo.com/de/reference/request/) (id=28736, locale=de)
9. [Request class - FastAPI](https://fastapi.tiangolo.com/es/reference/request/) (id=29495, locale=es)
10. [Request class - FastAPI](https://fastapi.tiangolo.com/fr/reference/request/) (id=30253, locale=fr)

**PostgreSQL top 10**

1. [Request Body - FastAPI](https://fastapi.tiangolo.com/tutorial/body/) (id=28074, locale=en)
2. [Request Body - FastAPI](https://fastapi.tiangolo.com/tr/tutorial/body/) (id=34174, locale=tr)
3. [Request Body - FastAPI](https://fastapi.tiangolo.com/es/tutorial/body/) (id=29599, locale=es)
4. [Request Body - FastAPI](https://fastapi.tiangolo.com/hi/tutorial/body/) (id=31113, locale=hi)
5. [Custom Request and APIRoute class - FastAPI](https://fastapi.tiangolo.com/how-to/custom-request-and-route/) (id=27825, locale=en)
6. [Custom Request और APIRoute class - FastAPI](https://fastapi.tiangolo.com/hi/how-to/custom-request-and-route/) (id=30886, locale=hi)
7. [Özel Request ve APIRoute sınıfı - FastAPI](https://fastapi.tiangolo.com/tr/how-to/custom-request-and-route/) (id=33998, locale=tr)
8. [Release Notes - FastAPI](https://fastapi.tiangolo.com/release-notes/) (id=28015, locale=en)
9. [Release Notes - FastAPI](https://fastapi.tiangolo.com/de/release-notes/) (id=28791, locale=de)
10. [Release Notes - FastAPI](https://fastapi.tiangolo.com/es/release-notes/) (id=29549, locale=es)

### Q023: FastAPI query parameters

Mode: `text` | Flags: `MULTILINGUAL_TOP` | Candidates: 100 | Time: 170 ms

**BM25 top 10**

1. [Query Parameters - FastAPI](https://fastapi.tiangolo.com/tutorial/query-params/) (id=28202, locale=en)
2. [Request Body - FastAPI](https://fastapi.tiangolo.com/tutorial/body/) (id=28074, locale=en)
3. [Request Parameters - FastAPI](https://fastapi.tiangolo.com/reference/parameters/) (id=27958, locale=en)
4. [Request Parameters - FastAPI](https://fastapi.tiangolo.com/de/reference/parameters/) (id=28731, locale=de)
5. [Request Parameters - FastAPI](https://fastapi.tiangolo.com/es/reference/parameters/) (id=29490, locale=es)
6. [Request Parameters - FastAPI](https://fastapi.tiangolo.com/fr/reference/parameters/) (id=30248, locale=fr)
7. [Request Parameters - FastAPI](https://fastapi.tiangolo.com/hi/reference/parameters/) (id=31005, locale=hi)
8. [Request Parameters - FastAPI](https://fastapi.tiangolo.com/ja/reference/parameters/) (id=31687, locale=ja)
9. [Request Parameters - FastAPI](https://fastapi.tiangolo.com/ko/reference/parameters/) (id=32294, locale=ko)
10. [Request Parameters - FastAPI](https://fastapi.tiangolo.com/pt/reference/parameters/) (id=32899, locale=pt)

**PostgreSQL top 10**

1. [Query Parameters - FastAPI](https://fastapi.tiangolo.com/tutorial/query-params/) (id=28202, locale=en)
2. [Query Parameters - FastAPI](https://fastapi.tiangolo.com/hi/tutorial/query-params/) (id=31239, locale=hi)
3. [Query-Parameter - FastAPI](https://fastapi.tiangolo.com/de/tutorial/query-params/) (id=28970, locale=de)
4. [Query Parameter Models - FastAPI](https://fastapi.tiangolo.com/tutorial/query-param-models/) (id=28194, locale=en)
5. [Query Parameter Models - FastAPI](https://fastapi.tiangolo.com/hi/tutorial/query-param-models/) (id=31229, locale=hi)
6. [Query Parameter Modelleri - FastAPI](https://fastapi.tiangolo.com/tr/tutorial/query-param-models/) (id=34266, locale=tr)
7. [Request Parameters - FastAPI](https://fastapi.tiangolo.com/reference/parameters/) (id=27958, locale=en)
8. [Request Parameters - FastAPI](https://fastapi.tiangolo.com/de/reference/parameters/) (id=28731, locale=de)
9. [Request Parameters - FastAPI](https://fastapi.tiangolo.com/es/reference/parameters/) (id=29490, locale=es)
10. [Request Parameters - FastAPI](https://fastapi.tiangolo.com/fr/reference/parameters/) (id=30248, locale=fr)

### Q024: FastAPI Depends

Mode: `all` | Flags: `MULTILINGUAL_TOP` | Candidates: 156 | Time: 192 ms

**BM25 top 10**

1. [Sub-dependencies - FastAPI](https://fastapi.tiangolo.com/tutorial/dependencies/sub-dependencies/) (id=28124, locale=en)
2. [Dependencies - FastAPI](https://fastapi.tiangolo.com/tutorial/dependencies/) (id=28098, locale=en)
3. [Global Dependencies - FastAPI](https://fastapi.tiangolo.com/tutorial/dependencies/global-dependencies/) (id=28119, locale=en)
4. [Dependencies - Depends() and Security() - FastAPI](https://fastapi.tiangolo.com/reference/dependencies/) (id=27914, locale=en)
5. [Dependencies - Depends() and Security() - FastAPI](https://fastapi.tiangolo.com/de/reference/dependencies/) (id=28686, locale=de)
6. [Dependencies - Depends() and Security() - FastAPI](https://fastapi.tiangolo.com/es/reference/dependencies/) (id=29446, locale=es)
7. [Dependencies - Depends() and Security() - FastAPI](https://fastapi.tiangolo.com/fr/reference/dependencies/) (id=30203, locale=fr)
8. [Dependencies - Depends() and Security() - FastAPI](https://fastapi.tiangolo.com/hi/reference/dependencies/) (id=30961, locale=hi)
9. [Dependencies - Depends() and Security() - FastAPI](https://fastapi.tiangolo.com/ja/reference/dependencies/) (id=31651, locale=ja)
10. [Dependencies - Depends() and Security() - FastAPI](https://fastapi.tiangolo.com/ko/reference/dependencies/) (id=32258, locale=ko)

**PostgreSQL top 10**

1. [Dependencies - Depends() and Security() - FastAPI](https://fastapi.tiangolo.com/reference/dependencies/) (id=27914, locale=en)
2. [Dependencies - Depends() and Security() - FastAPI](https://fastapi.tiangolo.com/de/reference/dependencies/) (id=28686, locale=de)
3. [Dependencies - Depends() and Security() - FastAPI](https://fastapi.tiangolo.com/es/reference/dependencies/) (id=29446, locale=es)
4. [Dependencies - Depends() and Security() - FastAPI](https://fastapi.tiangolo.com/fr/reference/dependencies/) (id=30203, locale=fr)
5. [Dependencies - Depends() and Security() - FastAPI](https://fastapi.tiangolo.com/hi/reference/dependencies/) (id=30961, locale=hi)
6. [Dependencies - Depends() and Security() - FastAPI](https://fastapi.tiangolo.com/ja/reference/dependencies/) (id=31651, locale=ja)
7. [Dependencies - Depends() and Security() - FastAPI](https://fastapi.tiangolo.com/ko/reference/dependencies/) (id=32258, locale=ko)
8. [Dependencies - Depends() and Security() - FastAPI](https://fastapi.tiangolo.com/pt/reference/dependencies/) (id=32863, locale=pt)
9. [Dependencies - Depends() and Security() - FastAPI](https://fastapi.tiangolo.com/ru/reference/dependencies/) (id=33471, locale=ru)
10. [Dependencies - Depends() and Security() - FastAPI](https://fastapi.tiangolo.com/tr/reference/dependencies/) (id=34056, locale=tr)

### Q026: FastAPI response model

Mode: `text` | Flags: `MULTILINGUAL_TOP, TARGET_BELOW_K` | Candidates: 100 | Time: 116 ms

**BM25 top 10**

1. [Return a Response Directly - FastAPI](https://fastapi.tiangolo.com/advanced/response-directly/) (id=27614, locale=en)
2. [APIRouter class - FastAPI](https://fastapi.tiangolo.com/reference/apirouter/) (id=27904, locale=en)
3. [APIRouter class - FastAPI](https://fastapi.tiangolo.com/de/reference/apirouter/) (id=28676, locale=de)
4. [APIRouter class - FastAPI](https://fastapi.tiangolo.com/es/reference/apirouter/) (id=29435, locale=es)
5. [APIRouter class - FastAPI](https://fastapi.tiangolo.com/fr/reference/apirouter/) (id=30193, locale=fr)
6. [APIRouter class - FastAPI](https://fastapi.tiangolo.com/hi/reference/apirouter/) (id=30951, locale=hi)
7. [APIRouter class - FastAPI](https://fastapi.tiangolo.com/ja/reference/apirouter/) (id=31644, locale=ja)
8. [APIRouter class - FastAPI](https://fastapi.tiangolo.com/ko/reference/apirouter/) (id=32250, locale=ko)
9. [APIRouter class - FastAPI](https://fastapi.tiangolo.com/pt/reference/apirouter/) (id=32855, locale=pt)
10. [APIRouter class - FastAPI](https://fastapi.tiangolo.com/ru/reference/apirouter/) (id=33464, locale=ru)

**PostgreSQL top 10**

1. [APIRouter class - FastAPI](https://fastapi.tiangolo.com/reference/apirouter/) (id=27904, locale=en)
2. [APIRouter class - FastAPI](https://fastapi.tiangolo.com/de/reference/apirouter/) (id=28676, locale=de)
3. [APIRouter class - FastAPI](https://fastapi.tiangolo.com/es/reference/apirouter/) (id=29435, locale=es)
4. [APIRouter class - FastAPI](https://fastapi.tiangolo.com/fr/reference/apirouter/) (id=30193, locale=fr)
5. [APIRouter class - FastAPI](https://fastapi.tiangolo.com/hi/reference/apirouter/) (id=30951, locale=hi)
6. [APIRouter class - FastAPI](https://fastapi.tiangolo.com/ja/reference/apirouter/) (id=31644, locale=ja)
7. [APIRouter class - FastAPI](https://fastapi.tiangolo.com/ko/reference/apirouter/) (id=32250, locale=ko)
8. [APIRouter class - FastAPI](https://fastapi.tiangolo.com/pt/reference/apirouter/) (id=32855, locale=pt)
9. [APIRouter class - FastAPI](https://fastapi.tiangolo.com/ru/reference/apirouter/) (id=33464, locale=ru)
10. [APIRouter class - FastAPI](https://fastapi.tiangolo.com/tr/reference/apirouter/) (id=34048, locale=tr)

### Q027: FastAPI HTTPException

Mode: `all` | Flags: `MULTILINGUAL_TOP` | Candidates: 170 | Time: 280 ms

**BM25 top 10**

1. [Handling Errors - FastAPI](https://fastapi.tiangolo.com/tutorial/handling-errors/) (id=28153, locale=en)
2. [Use Old 403 Authentication Error Status Codes - FastAPI](https://fastapi.tiangolo.com/how-to/authentication-error-status-code/) (id=27807, locale=en)
3. [Exceptions - HTTPException and WebSocketException - FastAPI](https://fastapi.tiangolo.com/reference/exceptions/) (id=27924, locale=en)
4. [Exceptions - HTTPException and WebSocketException - FastAPI](https://fastapi.tiangolo.com/de/reference/exceptions/) (id=28696, locale=de)
5. [Exceptions - HTTPException and WebSocketException - FastAPI](https://fastapi.tiangolo.com/es/reference/exceptions/) (id=29455, locale=es)
6. [Exceptions - HTTPException and WebSocketException - FastAPI](https://fastapi.tiangolo.com/fr/reference/exceptions/) (id=30213, locale=fr)
7. [Exceptions - HTTPException and WebSocketException - FastAPI](https://fastapi.tiangolo.com/hi/reference/exceptions/) (id=30970, locale=hi)
8. [Exceptions - HTTPException and WebSocketException - FastAPI](https://fastapi.tiangolo.com/ja/reference/exceptions/) (id=31658, locale=ja)
9. [Exceptions - HTTPException and WebSocketException - FastAPI](https://fastapi.tiangolo.com/ko/reference/exceptions/) (id=32266, locale=ko)
10. [Exceptions - HTTPException and WebSocketException - FastAPI](https://fastapi.tiangolo.com/pt/reference/exceptions/) (id=32871, locale=pt)

**PostgreSQL top 10**

1. [Handling Errors - FastAPI](https://fastapi.tiangolo.com/tutorial/handling-errors/) (id=28153, locale=en)
2. [Exceptions - HTTPException and WebSocketException - FastAPI](https://fastapi.tiangolo.com/reference/exceptions/) (id=27924, locale=en)
3. [Exceptions - HTTPException and WebSocketException - FastAPI](https://fastapi.tiangolo.com/de/reference/exceptions/) (id=28696, locale=de)
4. [Exceptions - HTTPException and WebSocketException - FastAPI](https://fastapi.tiangolo.com/es/reference/exceptions/) (id=29455, locale=es)
5. [Exceptions - HTTPException and WebSocketException - FastAPI](https://fastapi.tiangolo.com/fr/reference/exceptions/) (id=30213, locale=fr)
6. [Exceptions - HTTPException and WebSocketException - FastAPI](https://fastapi.tiangolo.com/hi/reference/exceptions/) (id=30970, locale=hi)
7. [Exceptions - HTTPException and WebSocketException - FastAPI](https://fastapi.tiangolo.com/ja/reference/exceptions/) (id=31658, locale=ja)
8. [Exceptions - HTTPException and WebSocketException - FastAPI](https://fastapi.tiangolo.com/ko/reference/exceptions/) (id=32266, locale=ko)
9. [Exceptions - HTTPException and WebSocketException - FastAPI](https://fastapi.tiangolo.com/pt/reference/exceptions/) (id=32871, locale=pt)
10. [Exceptions - HTTPException and WebSocketException - FastAPI](https://fastapi.tiangolo.com/ru/reference/exceptions/) (id=33480, locale=ru)

### Q028: FastAPI middleware

Mode: `text` | Flags: `MULTILINGUAL_TOP` | Candidates: 55 | Time: 46 ms

**BM25 top 10**

1. [Advanced Middleware - FastAPI](https://fastapi.tiangolo.com/advanced/middleware/) (id=27585, locale=en)
2. [Middleware - FastAPI](https://fastapi.tiangolo.com/tutorial/middleware/) (id=28173, locale=en)
3. [CORS (Cross-Origin Resource Sharing) - FastAPI](https://fastapi.tiangolo.com/tutorial/cors/) (id=28089, locale=en)
4. [Frontend - FastAPI](https://fastapi.tiangolo.com/tutorial/frontend/) (id=28148, locale=en)
5. [고급 Middleware - FastAPI](https://fastapi.tiangolo.com/ko/advanced/middleware/) (id=32006, locale=ko)
6. [Middleware - FastAPI](https://fastapi.tiangolo.com/tr/tutorial/middleware/) (id=34250, locale=tr)
7. [Middleware - FastAPI](https://fastapi.tiangolo.com/uk/tutorial/middleware/) (id=34836, locale=uk)
8. [Расширенное использование middleware - FastAPI](https://fastapi.tiangolo.com/ru/advanced/middleware/) (id=33224, locale=ru)
9. [İleri Seviye Middleware - FastAPI](https://fastapi.tiangolo.com/tr/advanced/middleware/) (id=33816, locale=tr)
10. [Middleware - FastAPI](https://fastapi.tiangolo.com/ru/tutorial/middleware/) (id=33668, locale=ru)

**PostgreSQL top 10**

1. [Advanced Middleware - FastAPI](https://fastapi.tiangolo.com/advanced/middleware/) (id=27585, locale=en)
2. [Middleware - FastAPI](https://fastapi.tiangolo.com/tutorial/middleware/) (id=28173, locale=en)
3. [Middleware - FastAPI](https://fastapi.tiangolo.com/de/tutorial/middleware/) (id=28940, locale=de)
4. [Middleware - FastAPI](https://fastapi.tiangolo.com/es/tutorial/middleware/) (id=29699, locale=es)
5. [Middleware - FastAPI](https://fastapi.tiangolo.com/fr/tutorial/middleware/) (id=30458, locale=fr)
6. [Middleware - FastAPI](https://fastapi.tiangolo.com/hi/tutorial/middleware/) (id=31209, locale=hi)
7. [Middleware - FastAPI](https://fastapi.tiangolo.com/pt/tutorial/middleware/) (id=33055, locale=pt)
8. [Middleware - FastAPI](https://fastapi.tiangolo.com/ru/tutorial/middleware/) (id=33668, locale=ru)
9. [Middleware - FastAPI](https://fastapi.tiangolo.com/uk/tutorial/middleware/) (id=34836, locale=uk)
10. [Middleware - FastAPI](https://fastapi.tiangolo.com/tr/tutorial/middleware/) (id=34250, locale=tr)

### Q029: FastAPI background tasks

Mode: `all` | Flags: `MULTILINGUAL_TOP` | Candidates: 64 | Time: 194 ms

**BM25 top 10**

1. [Background Tasks - BackgroundTasks - FastAPI](https://fastapi.tiangolo.com/reference/background/) (id=27909, locale=en)
2. [Background Tasks - BackgroundTasks - FastAPI](https://fastapi.tiangolo.com/de/reference/background/) (id=28681, locale=de)
3. [Background Tasks - BackgroundTasks - FastAPI](https://fastapi.tiangolo.com/es/reference/background/) (id=29440, locale=es)
4. [Background Tasks - BackgroundTasks - FastAPI](https://fastapi.tiangolo.com/fr/reference/background/) (id=30198, locale=fr)
5. [Background Tasks - BackgroundTasks - FastAPI](https://fastapi.tiangolo.com/hi/reference/background/) (id=30955, locale=hi)
6. [Background Tasks - BackgroundTasks - FastAPI](https://fastapi.tiangolo.com/ja/reference/background/) (id=31647, locale=ja)
7. [Background Tasks - BackgroundTasks - FastAPI](https://fastapi.tiangolo.com/ko/reference/background/) (id=32254, locale=ko)
8. [Background Tasks - BackgroundTasks - FastAPI](https://fastapi.tiangolo.com/pt/reference/background/) (id=32859, locale=pt)
9. [Background Tasks - BackgroundTasks - FastAPI](https://fastapi.tiangolo.com/ru/reference/background/) (id=33468, locale=ru)
10. [Background Tasks - BackgroundTasks - FastAPI](https://fastapi.tiangolo.com/tr/reference/background/) (id=34052, locale=tr)

**PostgreSQL top 10**

1. [Background Tasks - FastAPI](https://fastapi.tiangolo.com/tutorial/background-tasks/) (id=28044, locale=en)
2. [Background Tasks - FastAPI](https://fastapi.tiangolo.com/hi/tutorial/background-tasks/) (id=31083, locale=hi)
3. [Background Tasks - BackgroundTasks - FastAPI](https://fastapi.tiangolo.com/reference/background/) (id=27909, locale=en)
4. [Background Tasks - BackgroundTasks - FastAPI](https://fastapi.tiangolo.com/de/reference/background/) (id=28681, locale=de)
5. [Background Tasks - BackgroundTasks - FastAPI](https://fastapi.tiangolo.com/es/reference/background/) (id=29440, locale=es)
6. [Background Tasks - BackgroundTasks - FastAPI](https://fastapi.tiangolo.com/fr/reference/background/) (id=30198, locale=fr)
7. [Background Tasks - BackgroundTasks - FastAPI](https://fastapi.tiangolo.com/hi/reference/background/) (id=30955, locale=hi)
8. [Background Tasks - BackgroundTasks - FastAPI](https://fastapi.tiangolo.com/ja/reference/background/) (id=31647, locale=ja)
9. [Background Tasks - BackgroundTasks - FastAPI](https://fastapi.tiangolo.com/ko/reference/background/) (id=32254, locale=ko)
10. [Background Tasks - BackgroundTasks - FastAPI](https://fastapi.tiangolo.com/pt/reference/background/) (id=32859, locale=pt)

### Q030: FastAPI WebSockets

Mode: `all` | Flags: `LOW_AGREEMENT, MULTILINGUAL_TOP` | Candidates: 100 | Time: 130 ms

**BM25 top 10**

1. [Testing WebSockets - FastAPI](https://fastapi.tiangolo.com/advanced/testing-websockets/) (id=27672, locale=en)
2. [WebSockets - FastAPI](https://fastapi.tiangolo.com/advanced/websockets/) (id=27682, locale=en)
3. [测试 WebSockets - FastAPI](https://fastapi.tiangolo.com/zh/advanced/testing-websockets/) (id=35633, locale=zh)
4. [Probando WebSockets - FastAPI](https://fastapi.tiangolo.com/es/advanced/testing-websockets/) (id=29225, locale=es)
5. [WebSockets testen - FastAPI](https://fastapi.tiangolo.com/de/advanced/testing-websockets/) (id=28467, locale=de)
6. [Testando WebSockets - FastAPI](https://fastapi.tiangolo.com/pt/advanced/testing-websockets/) (id=32687, locale=pt)
7. [WebSockets'i Test Etmek - FastAPI](https://fastapi.tiangolo.com/tr/advanced/testing-websockets/) (id=33886, locale=tr)
8. [Tester les WebSockets - FastAPI](https://fastapi.tiangolo.com/fr/advanced/testing-websockets/) (id=29985, locale=fr)
9. [WebSockets की Testing - FastAPI](https://fastapi.tiangolo.com/hi/advanced/testing-websockets/) (id=30743, locale=hi)
10. [WebSockets - FastAPI](https://fastapi.tiangolo.com/zh/advanced/websockets/) (id=35640, locale=zh)

**PostgreSQL top 10**

1. [WebSockets - FastAPI](https://fastapi.tiangolo.com/advanced/websockets/) (id=27682, locale=en)
2. [WebSockets - FastAPI](https://fastapi.tiangolo.com/reference/websockets/) (id=28011, locale=en)
3. [WebSockets - FastAPI](https://fastapi.tiangolo.com/de/reference/websockets/) (id=28786, locale=de)
4. [WebSockets - FastAPI](https://fastapi.tiangolo.com/es/reference/websockets/) (id=29544, locale=es)
5. [WebSockets - FastAPI](https://fastapi.tiangolo.com/fr/reference/websockets/) (id=30303, locale=fr)
6. [WebSockets - FastAPI](https://fastapi.tiangolo.com/hi/reference/websockets/) (id=31059, locale=hi)
7. [WebSockets - FastAPI](https://fastapi.tiangolo.com/ja/reference/websockets/) (id=31730, locale=ja)
8. [WebSockets - FastAPI](https://fastapi.tiangolo.com/ko/reference/websockets/) (id=32338, locale=ko)
9. [WebSockets - FastAPI](https://fastapi.tiangolo.com/pt/reference/websockets/) (id=32943, locale=pt)
10. [WebSockets - FastAPI](https://fastapi.tiangolo.com/ru/reference/websockets/) (id=33549, locale=ru)

### Q031: FastAPI CORS

Mode: `text` | Flags: `MULTILINGUAL_TOP` | Candidates: 100 | Time: 256 ms

**BM25 top 10**

1. [CORS (Cross-Origin Resource Sharing) - FastAPI](https://fastapi.tiangolo.com/tutorial/cors/) (id=28089, locale=en)
2. [Response Headers - FastAPI](https://fastapi.tiangolo.com/advanced/response-headers/) (id=27618, locale=en)
3. [Middleware - FastAPI](https://fastapi.tiangolo.com/tutorial/middleware/) (id=28173, locale=en)
4. [Advanced Middleware - FastAPI](https://fastapi.tiangolo.com/advanced/middleware/) (id=27585, locale=en)
5. [CORS（跨域资源共享） - FastAPI](https://fastapi.tiangolo.com/zh/tutorial/cors/) (id=35930, locale=zh)
6. [CORS（跨來源資源共用） - FastAPI](https://fastapi.tiangolo.com/zh-hant/tutorial/cors/) (id=35348, locale=zh)
7. [CORS (Cross-Origin Resource Sharing) - FastAPI](https://fastapi.tiangolo.com/ja/tutorial/cors/) (id=31786, locale=ja)
8. [Strict Content-Type Checking - FastAPI](https://fastapi.tiangolo.com/advanced/strict-content-type/) (id=27647, locale=en)
9. [CORS (교차-출처 리소스 공유) - FastAPI](https://fastapi.tiangolo.com/ko/tutorial/cors/) (id=32393, locale=ko)
10. [CORS (Обмін ресурсами між різними джерелами) - FastAPI](https://fastapi.tiangolo.com/uk/tutorial/cors/) (id=34771, locale=uk)

**PostgreSQL top 10**

1. [CORS（跨來源資源共用） - FastAPI](https://fastapi.tiangolo.com/zh-hant/tutorial/cors/) (id=35348, locale=zh)
2. [CORS（跨域资源共享） - FastAPI](https://fastapi.tiangolo.com/zh/tutorial/cors/) (id=35930, locale=zh)
3. [CORS (Cross-Origin Resource Sharing) - FastAPI](https://fastapi.tiangolo.com/es/tutorial/cors/) (id=29614, locale=es)
4. [CORS (Cross-Origin Resource Sharing) - FastAPI](https://fastapi.tiangolo.com/tutorial/cors/) (id=28089, locale=en)
5. [CORS (Обмін ресурсами між різними джерелами) - FastAPI](https://fastapi.tiangolo.com/uk/tutorial/cors/) (id=34771, locale=uk)
6. [CORS (Cross-Origin Resource Sharing) - FastAPI](https://fastapi.tiangolo.com/de/tutorial/cors/) (id=28856, locale=de)
7. [CORS (Cross-Origin Resource Sharing) - FastAPI](https://fastapi.tiangolo.com/hi/tutorial/cors/) (id=31128, locale=hi)
8. [CORS (교차-출처 리소스 공유) - FastAPI](https://fastapi.tiangolo.com/ko/tutorial/cors/) (id=32393, locale=ko)
9. [CORS (Partage des ressources entre origines) - FastAPI](https://fastapi.tiangolo.com/fr/tutorial/cors/) (id=30373, locale=fr)
10. [CORS (Cross-Origin Resource Sharing) - FastAPI](https://fastapi.tiangolo.com/pt/tutorial/cors/) (id=32998, locale=pt)

### Q032: FastAPI OAuth2

Mode: `text` | Flags: `MULTILINGUAL_TOP, TARGET_BELOW_K` | Candidates: 100 | Time: 97 ms

**BM25 top 10**

1. [Custom Docs UI Static Assets (Self-Hosting) - FastAPI](https://fastapi.tiangolo.com/how-to/custom-docs-ui-assets/) (id=27820, locale=en)
2. [Security - FastAPI](https://fastapi.tiangolo.com/tutorial/security/) (id=28241, locale=en)
3. [Security Tools - FastAPI](https://fastapi.tiangolo.com/reference/security/) (id=27978, locale=en)
4. [Security Tools - FastAPI](https://fastapi.tiangolo.com/de/reference/security/) (id=28751, locale=de)
5. [Security Tools - FastAPI](https://fastapi.tiangolo.com/es/reference/security/) (id=29509, locale=es)
6. [Security Tools - FastAPI](https://fastapi.tiangolo.com/fr/reference/security/) (id=30268, locale=fr)
7. [Security Tools - FastAPI](https://fastapi.tiangolo.com/hi/reference/security/) (id=31024, locale=hi)
8. [Security Tools - FastAPI](https://fastapi.tiangolo.com/ja/reference/security/) (id=31703, locale=ja)
9. [Security Tools - FastAPI](https://fastapi.tiangolo.com/ko/reference/security/) (id=32310, locale=ko)
10. [Security Tools - FastAPI](https://fastapi.tiangolo.com/pt/reference/security/) (id=32915, locale=pt)

**PostgreSQL top 10**

1. [Security Tools - FastAPI](https://fastapi.tiangolo.com/reference/security/) (id=27978, locale=en)
2. [Security Tools - FastAPI](https://fastapi.tiangolo.com/de/reference/security/) (id=28751, locale=de)
3. [Security Tools - FastAPI](https://fastapi.tiangolo.com/es/reference/security/) (id=29509, locale=es)
4. [Security Tools - FastAPI](https://fastapi.tiangolo.com/fr/reference/security/) (id=30268, locale=fr)
5. [Security Tools - FastAPI](https://fastapi.tiangolo.com/hi/reference/security/) (id=31024, locale=hi)
6. [Security Tools - FastAPI](https://fastapi.tiangolo.com/ja/reference/security/) (id=31703, locale=ja)
7. [Security Tools - FastAPI](https://fastapi.tiangolo.com/ko/reference/security/) (id=32310, locale=ko)
8. [Security Tools - FastAPI](https://fastapi.tiangolo.com/pt/reference/security/) (id=32915, locale=pt)
9. [Security Tools - FastAPI](https://fastapi.tiangolo.com/ru/reference/security/) (id=33523, locale=ru)
10. [Security Tools - FastAPI](https://fastapi.tiangolo.com/tr/reference/security/) (id=34106, locale=tr)

### Q033: FastAPI dependency overrides

Mode: `all` | Flags: `MULTILINGUAL_TOP` | Candidates: 71 | Time: 239 ms

**BM25 top 10**

1. [Testing Dependencies with Overrides - FastAPI](https://fastapi.tiangolo.com/advanced/testing-dependencies/) (id=27662, locale=en)
2. [Override Kullanarak Dependency'leri Test Etme - FastAPI](https://fastapi.tiangolo.com/tr/advanced/testing-dependencies/) (id=33877, locale=tr)
3. [Overrides के साथ Dependencies की Testing - FastAPI](https://fastapi.tiangolo.com/hi/advanced/testing-dependencies/) (id=30733, locale=hi)
4. [Probando Dependencias con Overrides - FastAPI](https://fastapi.tiangolo.com/es/advanced/testing-dependencies/) (id=29215, locale=es)
5. [使用覆盖测试依赖项 - FastAPI](https://fastapi.tiangolo.com/zh/advanced/testing-dependencies/) (id=35625, locale=zh)
6. [用覆寫測試相依 - FastAPI](https://fastapi.tiangolo.com/zh-hant/advanced/testing-dependencies/) (id=35041, locale=zh)
7. [依存関係のオーバーライドによるテスト - FastAPI](https://fastapi.tiangolo.com/ja/advanced/testing-dependencies/) (id=31468, locale=ja)
8. [오버라이드로 의존성 테스트하기 - FastAPI](https://fastapi.tiangolo.com/ko/advanced/testing-dependencies/) (id=32074, locale=ko)
9. [Тестування залежностей з переписуваннями - FastAPI](https://fastapi.tiangolo.com/uk/advanced/testing-dependencies/) (id=34463, locale=uk)
10. [Тестирование зависимостей с переопределениями - FastAPI](https://fastapi.tiangolo.com/ru/advanced/testing-dependencies/) (id=33292, locale=ru)

**PostgreSQL top 10**

1. [Testing Dependencies with Overrides - FastAPI](https://fastapi.tiangolo.com/advanced/testing-dependencies/) (id=27662, locale=en)
2. [Override Kullanarak Dependency'leri Test Etme - FastAPI](https://fastapi.tiangolo.com/tr/advanced/testing-dependencies/) (id=33877, locale=tr)
3. [Overrides के साथ Dependencies की Testing - FastAPI](https://fastapi.tiangolo.com/hi/advanced/testing-dependencies/) (id=30733, locale=hi)
4. [APIRouter class - FastAPI](https://fastapi.tiangolo.com/reference/apirouter/) (id=27904, locale=en)
5. [APIRouter class - FastAPI](https://fastapi.tiangolo.com/de/reference/apirouter/) (id=28676, locale=de)
6. [APIRouter class - FastAPI](https://fastapi.tiangolo.com/es/reference/apirouter/) (id=29435, locale=es)
7. [APIRouter class - FastAPI](https://fastapi.tiangolo.com/fr/reference/apirouter/) (id=30193, locale=fr)
8. [APIRouter class - FastAPI](https://fastapi.tiangolo.com/hi/reference/apirouter/) (id=30951, locale=hi)
9. [APIRouter class - FastAPI](https://fastapi.tiangolo.com/ja/reference/apirouter/) (id=31644, locale=ja)
10. [APIRouter class - FastAPI](https://fastapi.tiangolo.com/ko/reference/apirouter/) (id=32250, locale=ko)

### Q034: FastAPI lifespan events

Mode: `text` | Flags: `MULTILINGUAL_TOP, TARGET_BELOW_K` | Candidates: 48 | Time: 41 ms

**BM25 top 10**

1. [Testing Events: lifespan and startup - shutdown - FastAPI](https://fastapi.tiangolo.com/advanced/testing-events/) (id=27667, locale=en)
2. [Event'leri Test Etme: lifespan ve startup - shutdown - FastAPI](https://fastapi.tiangolo.com/tr/advanced/testing-events/) (id=33882, locale=tr)
3. [Events testen: Lifespan und Startup – Shutdown - FastAPI](https://fastapi.tiangolo.com/de/advanced/testing-events/) (id=28463, locale=de)
4. [Testing Events: lifespan और startup - shutdown - FastAPI](https://fastapi.tiangolo.com/hi/advanced/testing-events/) (id=30738, locale=hi)
5. [APIRouter class - FastAPI](https://fastapi.tiangolo.com/reference/apirouter/) (id=27904, locale=en)
6. [APIRouter class - FastAPI](https://fastapi.tiangolo.com/de/reference/apirouter/) (id=28676, locale=de)
7. [APIRouter class - FastAPI](https://fastapi.tiangolo.com/es/reference/apirouter/) (id=29435, locale=es)
8. [APIRouter class - FastAPI](https://fastapi.tiangolo.com/fr/reference/apirouter/) (id=30193, locale=fr)
9. [APIRouter class - FastAPI](https://fastapi.tiangolo.com/hi/reference/apirouter/) (id=30951, locale=hi)
10. [APIRouter class - FastAPI](https://fastapi.tiangolo.com/ja/reference/apirouter/) (id=31644, locale=ja)

**PostgreSQL top 10**

1. [Lifespan Events - FastAPI](https://fastapi.tiangolo.com/advanced/events/) (id=27574, locale=en)
2. [Lifespan event - FastAPI](https://fastapi.tiangolo.com/hi/advanced/events/) (id=30633, locale=hi)
3. [Lifespan-Events - FastAPI](https://fastapi.tiangolo.com/de/advanced/events/) (id=28360, locale=de)
4. [Testing Events: lifespan and startup - shutdown - FastAPI](https://fastapi.tiangolo.com/advanced/testing-events/) (id=27667, locale=en)
5. [Testing Events: lifespan और startup - shutdown - FastAPI](https://fastapi.tiangolo.com/hi/advanced/testing-events/) (id=30738, locale=hi)
6. [Events testen: Lifespan und Startup – Shutdown - FastAPI](https://fastapi.tiangolo.com/de/advanced/testing-events/) (id=28463, locale=de)
7. [Event'leri Test Etme: lifespan ve startup - shutdown - FastAPI](https://fastapi.tiangolo.com/tr/advanced/testing-events/) (id=33882, locale=tr)
8. [APIRouter class - FastAPI](https://fastapi.tiangolo.com/reference/apirouter/) (id=27904, locale=en)
9. [APIRouter class - FastAPI](https://fastapi.tiangolo.com/de/reference/apirouter/) (id=28676, locale=de)
10. [APIRouter class - FastAPI](https://fastapi.tiangolo.com/es/reference/apirouter/) (id=29435, locale=es)

### Q035: FastAPI upload file

Mode: `text` | Flags: `LOW_AGREEMENT, MULTILINGUAL_TOP, TARGET_BELOW_K` | Candidates: 42 | Time: 168 ms

**BM25 top 10**

1. [UploadFile class - FastAPI](https://fastapi.tiangolo.com/reference/uploadfile/) (id=28006, locale=en)
2. [UploadFile class - FastAPI](https://fastapi.tiangolo.com/de/reference/uploadfile/) (id=28781, locale=de)
3. [UploadFile class - FastAPI](https://fastapi.tiangolo.com/es/reference/uploadfile/) (id=29540, locale=es)
4. [UploadFile class - FastAPI](https://fastapi.tiangolo.com/fr/reference/uploadfile/) (id=30298, locale=fr)
5. [UploadFile class - FastAPI](https://fastapi.tiangolo.com/hi/reference/uploadfile/) (id=31054, locale=hi)
6. [UploadFile class - FastAPI](https://fastapi.tiangolo.com/ja/reference/uploadfile/) (id=31726, locale=ja)
7. [UploadFile class - FastAPI](https://fastapi.tiangolo.com/ko/reference/uploadfile/) (id=32334, locale=ko)
8. [UploadFile class - FastAPI](https://fastapi.tiangolo.com/pt/reference/uploadfile/) (id=32939, locale=pt)
9. [UploadFile class - FastAPI](https://fastapi.tiangolo.com/ru/reference/uploadfile/) (id=33545, locale=ru)
10. [UploadFile class - FastAPI](https://fastapi.tiangolo.com/tr/reference/uploadfile/) (id=34128, locale=tr)

**PostgreSQL top 10**

1. [Request Files - FastAPI](https://fastapi.tiangolo.com/hi/tutorial/request-files/) (id=31244, locale=hi)
2. [Request Files - FastAPI](https://fastapi.tiangolo.com/tutorial/request-files/) (id=28207, locale=en)
3. [Release Notes - FastAPI](https://fastapi.tiangolo.com/release-notes/) (id=28015, locale=en)
4. [Release Notes - FastAPI](https://fastapi.tiangolo.com/de/release-notes/) (id=28791, locale=de)
5. [Release Notes - FastAPI](https://fastapi.tiangolo.com/es/release-notes/) (id=29549, locale=es)
6. [Release Notes - FastAPI](https://fastapi.tiangolo.com/fr/release-notes/) (id=30308, locale=fr)
7. [Release Notes - FastAPI](https://fastapi.tiangolo.com/hi/release-notes/) (id=31064, locale=hi)
8. [Release Notes - FastAPI](https://fastapi.tiangolo.com/ja/release-notes/) (id=31734, locale=ja)
9. [Release Notes - FastAPI](https://fastapi.tiangolo.com/ko/release-notes/) (id=32342, locale=ko)
10. [Release Notes - FastAPI](https://fastapi.tiangolo.com/pt/release-notes/) (id=32947, locale=pt)

### Q036: FastAPI streaming response

Mode: `code` | Flags: `LOW_AGREEMENT, MULTILINGUAL_TOP` | Candidates: 40 | Time: 20 ms

**BM25 top 10**

1. [Test Client - TestClient - FastAPI](https://fastapi.tiangolo.com/reference/testclient/) (id=28002, locale=en)
2. [Test Client - TestClient - FastAPI](https://fastapi.tiangolo.com/de/reference/testclient/) (id=28776, locale=de)
3. [Test Client - TestClient - FastAPI](https://fastapi.tiangolo.com/es/reference/testclient/) (id=29535, locale=es)
4. [Test Client - TestClient - FastAPI](https://fastapi.tiangolo.com/fr/reference/testclient/) (id=30293, locale=fr)
5. [Test Client - TestClient - FastAPI](https://fastapi.tiangolo.com/hi/reference/testclient/) (id=31049, locale=hi)
6. [Test Client - TestClient - FastAPI](https://fastapi.tiangolo.com/ja/reference/testclient/) (id=31723, locale=ja)
7. [Test Client - TestClient - FastAPI](https://fastapi.tiangolo.com/ko/reference/testclient/) (id=32330, locale=ko)
8. [Test Client - TestClient - FastAPI](https://fastapi.tiangolo.com/pt/reference/testclient/) (id=32935, locale=pt)
9. [Test Client - TestClient - FastAPI](https://fastapi.tiangolo.com/ru/reference/testclient/) (id=33541, locale=ru)
10. [Test Client - TestClient - FastAPI](https://fastapi.tiangolo.com/tr/reference/testclient/) (id=34123, locale=tr)

**PostgreSQL top 10**

1. [Custom Response Classes - File, HTML, Redirect, Streaming, etc. - FastAPI](https://fastapi.tiangolo.com/reference/responses/) (id=27973, locale=en)
2. [Custom Response Classes - File, HTML, Redirect, Streaming, etc. - FastAPI](https://fastapi.tiangolo.com/de/reference/responses/) (id=28746, locale=de)
3. [Custom Response Classes - File, HTML, Redirect, Streaming, etc. - FastAPI](https://fastapi.tiangolo.com/es/reference/responses/) (id=29506, locale=es)
4. [Custom Response Classes - File, HTML, Redirect, Streaming, etc. - FastAPI](https://fastapi.tiangolo.com/fr/reference/responses/) (id=30264, locale=fr)
5. [Custom Response Classes - File, HTML, Redirect, Streaming, etc. - FastAPI](https://fastapi.tiangolo.com/hi/reference/responses/) (id=31019, locale=hi)
6. [Custom Response Classes - File, HTML, Redirect, Streaming, etc. - FastAPI](https://fastapi.tiangolo.com/ja/reference/responses/) (id=31699, locale=ja)
7. [Custom Response Classes - File, HTML, Redirect, Streaming, etc. - FastAPI](https://fastapi.tiangolo.com/ko/reference/responses/) (id=32306, locale=ko)
8. [Custom Response Classes - File, HTML, Redirect, Streaming, etc. - FastAPI](https://fastapi.tiangolo.com/pt/reference/responses/) (id=32911, locale=pt)
9. [Custom Response Classes - File, HTML, Redirect, Streaming, etc. - FastAPI](https://fastapi.tiangolo.com/ru/reference/responses/) (id=33519, locale=ru)
10. [Custom Response Classes - File, HTML, Redirect, Streaming, etc. - FastAPI](https://fastapi.tiangolo.com/tr/reference/responses/) (id=34102, locale=tr)

### Q037: FastAPI custom OpenAPI

Mode: `text` | Flags: `LOW_AGREEMENT, MULTILINGUAL_TOP` | Candidates: 60 | Time: 55 ms

**BM25 top 10**

1. [Extending OpenAPI - FastAPI](https://fastapi.tiangolo.com/how-to/extending-openapi/) (id=27830, locale=en)
2. [Path Operation Advanced Configuration - FastAPI](https://fastapi.tiangolo.com/advanced/path-operation-advanced-configuration/) (id=27601, locale=en)
3. [OpenAPI docs - FastAPI](https://fastapi.tiangolo.com/reference/openapi/docs/) (id=27948, locale=en)
4. [OpenAPI docs - FastAPI](https://fastapi.tiangolo.com/de/reference/openapi/docs/) (id=28721, locale=de)
5. [OpenAPI docs - FastAPI](https://fastapi.tiangolo.com/es/reference/openapi/docs/) (id=29480, locale=es)
6. [OpenAPI docs - FastAPI](https://fastapi.tiangolo.com/fr/reference/openapi/docs/) (id=30238, locale=fr)
7. [OpenAPI docs - FastAPI](https://fastapi.tiangolo.com/hi/reference/openapi/docs/) (id=30995, locale=hi)
8. [OpenAPI docs - FastAPI](https://fastapi.tiangolo.com/ja/reference/openapi/docs/) (id=31678, locale=ja)
9. [OpenAPI docs - FastAPI](https://fastapi.tiangolo.com/ko/reference/openapi/docs/) (id=32286, locale=ko)
10. [OpenAPI docs - FastAPI](https://fastapi.tiangolo.com/pt/reference/openapi/docs/) (id=32890, locale=pt)

**PostgreSQL top 10**

1. [APIRouter class - FastAPI](https://fastapi.tiangolo.com/reference/apirouter/) (id=27904, locale=en)
2. [APIRouter class - FastAPI](https://fastapi.tiangolo.com/de/reference/apirouter/) (id=28676, locale=de)
3. [APIRouter class - FastAPI](https://fastapi.tiangolo.com/es/reference/apirouter/) (id=29435, locale=es)
4. [APIRouter class - FastAPI](https://fastapi.tiangolo.com/fr/reference/apirouter/) (id=30193, locale=fr)
5. [APIRouter class - FastAPI](https://fastapi.tiangolo.com/hi/reference/apirouter/) (id=30951, locale=hi)
6. [APIRouter class - FastAPI](https://fastapi.tiangolo.com/ja/reference/apirouter/) (id=31644, locale=ja)
7. [APIRouter class - FastAPI](https://fastapi.tiangolo.com/ko/reference/apirouter/) (id=32250, locale=ko)
8. [APIRouter class - FastAPI](https://fastapi.tiangolo.com/pt/reference/apirouter/) (id=32855, locale=pt)
9. [APIRouter class - FastAPI](https://fastapi.tiangolo.com/ru/reference/apirouter/) (id=33464, locale=ru)
10. [APIRouter class - FastAPI](https://fastapi.tiangolo.com/tr/reference/apirouter/) (id=34048, locale=tr)

### Q039: FastAPI APIRouter

Mode: `code` | Flags: `LOW_AGREEMENT, MULTILINGUAL_TOP, TARGET_BELOW_K` | Candidates: 78 | Time: 51 ms

**BM25 top 10**

1. [フロントエンド - FastAPI](https://fastapi.tiangolo.com/ja/tutorial/frontend/) (id=31834, locale=ja)
2. [前端 - FastAPI](https://fastapi.tiangolo.com/zh-hant/tutorial/frontend/) (id=35393, locale=zh)
3. [前端 - FastAPI](https://fastapi.tiangolo.com/zh/tutorial/frontend/) (id=35976, locale=zh)
4. [Frontend - FastAPI](https://fastapi.tiangolo.com/de/tutorial/frontend/) (id=28915, locale=de)
5. [Фронтенд - FastAPI](https://fastapi.tiangolo.com/ru/tutorial/frontend/) (id=33649, locale=ru)
6. [프론트엔드 - FastAPI](https://fastapi.tiangolo.com/ko/tutorial/frontend/) (id=32441, locale=ko)
7. [Frontend - FastAPI](https://fastapi.tiangolo.com/tutorial/frontend/) (id=28148, locale=en)
8. [Фронтенд - FastAPI](https://fastapi.tiangolo.com/uk/tutorial/frontend/) (id=34818, locale=uk)
9. [Frontend - FastAPI](https://fastapi.tiangolo.com/fr/tutorial/frontend/) (id=30433, locale=fr)
10. [Frontend - FastAPI](https://fastapi.tiangolo.com/tr/tutorial/frontend/) (id=34232, locale=tr)

**PostgreSQL top 10**

1. [APIRouter class - FastAPI](https://fastapi.tiangolo.com/reference/apirouter/) (id=27904, locale=en)
2. [APIRouter class - FastAPI](https://fastapi.tiangolo.com/de/reference/apirouter/) (id=28676, locale=de)
3. [APIRouter class - FastAPI](https://fastapi.tiangolo.com/es/reference/apirouter/) (id=29435, locale=es)
4. [APIRouter class - FastAPI](https://fastapi.tiangolo.com/fr/reference/apirouter/) (id=30193, locale=fr)
5. [APIRouter class - FastAPI](https://fastapi.tiangolo.com/hi/reference/apirouter/) (id=30951, locale=hi)
6. [APIRouter class - FastAPI](https://fastapi.tiangolo.com/ja/reference/apirouter/) (id=31644, locale=ja)
7. [APIRouter class - FastAPI](https://fastapi.tiangolo.com/ko/reference/apirouter/) (id=32250, locale=ko)
8. [APIRouter class - FastAPI](https://fastapi.tiangolo.com/pt/reference/apirouter/) (id=32855, locale=pt)
9. [APIRouter class - FastAPI](https://fastapi.tiangolo.com/ru/reference/apirouter/) (id=33464, locale=ru)
10. [APIRouter class - FastAPI](https://fastapi.tiangolo.com/tr/reference/apirouter/) (id=34048, locale=tr)

### Q040: FastAPI status codes

Mode: `text` | Flags: `LOW_AGREEMENT, MULTILINGUAL_TOP, TARGET_BELOW_K` | Candidates: 100 | Time: 58 ms

**BM25 top 10**

1. [Response Status Code - FastAPI](https://fastapi.tiangolo.com/tutorial/response-status-code/) (id=28231, locale=en)
2. [Exceptions - HTTPException and WebSocketException - FastAPI](https://fastapi.tiangolo.com/reference/exceptions/) (id=27924, locale=en)
3. [Exceptions - HTTPException and WebSocketException - FastAPI](https://fastapi.tiangolo.com/de/reference/exceptions/) (id=28696, locale=de)
4. [Exceptions - HTTPException and WebSocketException - FastAPI](https://fastapi.tiangolo.com/es/reference/exceptions/) (id=29455, locale=es)
5. [Exceptions - HTTPException and WebSocketException - FastAPI](https://fastapi.tiangolo.com/fr/reference/exceptions/) (id=30213, locale=fr)
6. [Exceptions - HTTPException and WebSocketException - FastAPI](https://fastapi.tiangolo.com/hi/reference/exceptions/) (id=30970, locale=hi)
7. [Exceptions - HTTPException and WebSocketException - FastAPI](https://fastapi.tiangolo.com/ja/reference/exceptions/) (id=31658, locale=ja)
8. [Exceptions - HTTPException and WebSocketException - FastAPI](https://fastapi.tiangolo.com/ko/reference/exceptions/) (id=32266, locale=ko)
9. [Exceptions - HTTPException and WebSocketException - FastAPI](https://fastapi.tiangolo.com/pt/reference/exceptions/) (id=32871, locale=pt)
10. [Exceptions - HTTPException and WebSocketException - FastAPI](https://fastapi.tiangolo.com/ru/reference/exceptions/) (id=33480, locale=ru)

**PostgreSQL top 10**

1. [Status Codes - FastAPI](https://fastapi.tiangolo.com/reference/status/) (id=27992, locale=en)
2. [Status Codes - FastAPI](https://fastapi.tiangolo.com/de/reference/status/) (id=28766, locale=de)
3. [Status Codes - FastAPI](https://fastapi.tiangolo.com/es/reference/status/) (id=29526, locale=es)
4. [Status Codes - FastAPI](https://fastapi.tiangolo.com/fr/reference/status/) (id=30283, locale=fr)
5. [Status Codes - FastAPI](https://fastapi.tiangolo.com/hi/reference/status/) (id=31039, locale=hi)
6. [Status Codes - FastAPI](https://fastapi.tiangolo.com/ja/reference/status/) (id=31715, locale=ja)
7. [Status Codes - FastAPI](https://fastapi.tiangolo.com/ko/reference/status/) (id=32322, locale=ko)
8. [Status Codes - FastAPI](https://fastapi.tiangolo.com/pt/reference/status/) (id=32927, locale=pt)
9. [Status Codes - FastAPI](https://fastapi.tiangolo.com/ru/reference/status/) (id=33533, locale=ru)
10. [Status Codes - FastAPI](https://fastapi.tiangolo.com/tr/reference/status/) (id=34116, locale=tr)

### Q042: django ORM filter

Mode: `all` | Flags: `MULTILINGUAL_TOP` | Candidates: 98 | Time: 135 ms

**BM25 top 10**

1. [Django 1.1 release notes | Django documentation](https://docs.djangoproject.com/en/6.1/releases/1.1/) (id=62953, locale=en)
2. [Django 4.1 release notes | Django documentation](https://docs.djangoproject.com/en/6.1/releases/4.1/) (id=62963, locale=en)
3. [Django 1.4 release notes | Django documentation](https://docs.djangoproject.com/en/6.1/releases/1.4/) (id=62520, locale=en)
4. [Django 6.0 release notes | Django documentation](https://docs.djangoproject.com/en/6.1/releases/6.0/) (id=62967, locale=en)
5. [聚合 | Django 文档](https://docs.djangoproject.com/zh-hans/6.1/topics/db/aggregation/) (id=65091, locale=zh)
6. [Django 3.0 release notes | Django documentation](https://docs.djangoproject.com/en/6.1/releases/3.0/) (id=62537, locale=en)
7. [Aggregation | Django documentation](https://docs.djangoproject.com/en/6.1/topics/db/aggregation/) (id=28174, locale=en)
8. [Django 1.6 release notes | Django documentation](https://docs.djangoproject.com/en/6.1/releases/1.6/) (id=62524, locale=en)
9. [マイグレーション・オペレーション | Django ドキュメント](https://docs.djangoproject.com/ja/6.1/ref/migration-operations/) (id=63949, locale=ja)
10. [Aggregering | Django-dokumentation](https://docs.djangoproject.com/sv/6.1/topics/db/aggregation/) (id=65089, locale=sv)

**PostgreSQL top 10**

1. [Django 1.1 release notes | Django documentation](https://docs.djangoproject.com/en/6.1/releases/1.1/) (id=62953, locale=en)
2. [Django 1.4 release notes | Django documentation](https://docs.djangoproject.com/en/6.1/releases/1.4/) (id=62520, locale=en)
3. [マイグレーション・オペレーション | Django ドキュメント](https://docs.djangoproject.com/ja/6.1/ref/migration-operations/) (id=63949, locale=ja)
4. [迁移操作 | Django 文档](https://docs.djangoproject.com/zh-hans/6.1/ref/migration-operations/) (id=63954, locale=zh)
5. [クエリ式 (Query Expression) | Django ドキュメント](https://docs.djangoproject.com/ja/6.1/ref/models/expressions/) (id=64004, locale=ja)
6. [查询表达式 | Django 文档](https://docs.djangoproject.com/zh-hans/6.1/ref/models/expressions/) (id=64010, locale=zh)
7. [データベースアクセスの最適化 | Django ドキュメント](https://docs.djangoproject.com/ja/6.1/topics/db/optimization/) (id=65140, locale=ja)
8. [数据库访问优化 | Django 文档](https://docs.djangoproject.com/zh-hans/6.1/topics/db/optimization/) (id=65146, locale=zh)
9. [执行查询 | Django 文档](https://docs.djangoproject.com/zh-hans/6.1/topics/db/queries/) (id=65161, locale=zh)
10. [素の SQL 文の実行 | Django ドキュメント](https://docs.djangoproject.com/ja/6.1/topics/db/sql/) (id=65181, locale=ja)

### Q043: django migrations

Mode: `text` | Flags: `MULTILINGUAL_TOP` | Candidates: 100 | Time: 138 ms

**BM25 top 10**

1. [Migrations | Django documentation](https://docs.djangoproject.com/en/6.1/topics/migrations/) (id=28307, locale=en)
2. [マイグレーション | Django ドキュメント](https://docs.djangoproject.com/ja/6.1/topics/migrations/) (id=65461, locale=ja)
3. [迁移 | Django 文档](https://docs.djangoproject.com/zh-hans/6.1/topics/migrations/) (id=65468, locale=zh)
4. [Database migration operations | Django documentation](https://docs.djangoproject.com/en/6.1/ref/contrib/postgres/operations/) (id=62509, locale=en)
5. [django-admin and manage.py | Django documentation](https://docs.djangoproject.com/en/6.1/ref/django-admin/) (id=27949, locale=en)
6. [Migrations | Documentation de Django](https://docs.djangoproject.com/fr/6.1/topics/migrations/) (id=65457, locale=fr)
7. [Django 4.1.1 release notes | Django documentation](https://docs.djangoproject.com/en/6.1/releases/4.1.1/) (id=64730, locale=en)
8. [Writing your first Django app, part 2 | Django documentation](https://docs.djangoproject.com/en/6.1/intro/tutorial02/) (id=27784, locale=en)
9. [编写你的第一个 Django 应用，第 2 部分 | Django 文档](https://docs.djangoproject.com/zh-hans/6.1/intro/tutorial02/) (id=63151, locale=zh)
10. [はじめての Django アプリ作成、その 2 | Django ドキュメント](https://docs.djangoproject.com/ja/6.1/intro/tutorial02/) (id=38197, locale=ja)

**PostgreSQL top 10**

1. [Migrations | Django documentation](https://docs.djangoproject.com/en/6.1/topics/migrations/) (id=28307, locale=en)
2. [Migrations | Documentation de Django](https://docs.djangoproject.com/fr/6.1/topics/migrations/) (id=65457, locale=fr)
3. [django-admin and manage.py | Django documentation](https://docs.djangoproject.com/en/6.1/ref/django-admin/) (id=27949, locale=en)
4. [django-admin et manage.py | Documentation de Django](https://docs.djangoproject.com/fr/6.1/ref/django-admin/) (id=63823, locale=fr)
5. [django-admin 和 manage.py | Django 文档](https://docs.djangoproject.com/zh-hans/6.1/ref/django-admin/) (id=63831, locale=zh)
6. [django-admin と manage.py | Django ドキュメント](https://docs.djangoproject.com/ja/6.1/ref/django-admin/) (id=63826, locale=ja)
7. [How to create database migrations | Django documentation](https://docs.djangoproject.com/en/6.1/howto/writing-migrations/) (id=27717, locale=en)
8. [Migration Operations | Django documentation](https://docs.djangoproject.com/en/6.1/ref/migration-operations/) (id=27993, locale=en)
9. [Database migration operations | Django documentation](https://docs.djangoproject.com/en/6.1/ref/contrib/postgres/operations/) (id=62509, locale=en)
10. [django-admin och manage.py | Django-dokumentation](https://docs.djangoproject.com/sv/6.1/ref/django-admin/) (id=63829, locale=sv)

### Q045: django middleware

Mode: `text` | Flags: `MULTILINGUAL_TOP` | Candidates: 100 | Time: 69 ms

**BM25 top 10**

1. [Middleware | Django documentation](https://docs.djangoproject.com/en/6.1/topics/http/middleware/) (id=28257, locale=en)
2. [ミドルウェア (Middleware) | Django ドキュメント](https://docs.djangoproject.com/ja/6.1/topics/http/middleware/) (id=65323, locale=ja)
3. [中间件 | Django 文档](https://docs.djangoproject.com/zh-hans/6.1/topics/http/middleware/) (id=65329, locale=zh)
4. [Middleware | Django-dokumentation](https://docs.djangoproject.com/sv/6.1/topics/http/middleware/) (id=65328, locale=sv)
5. [| Django-dokumentation](https://docs.djangoproject.com/sv/6.1/py-modindex/) (id=63503, locale=sv)
6. [| Django documentation](https://docs.djangoproject.com/en/6.1/py-modindex/) (id=27831, locale=en)
7. [| Django 文档](https://docs.djangoproject.com/zh-hans/6.1/py-modindex/) (id=63504, locale=zh)
8. [| Documentazione di Django](https://docs.djangoproject.com/it/6.1/py-modindex/) (id=63493, locale=it)
9. [| Django ドキュメント](https://docs.djangoproject.com/ja/6.1/py-modindex/) (id=63496, locale=ja)
10. [| Django 문서](https://docs.djangoproject.com/ko/6.1/py-modindex/) (id=63498, locale=ko)

**PostgreSQL top 10**

1. [Middleware | Django documentation](https://docs.djangoproject.com/en/6.1/topics/http/middleware/) (id=28257, locale=en)
2. [Middleware | Django-dokumentation](https://docs.djangoproject.com/sv/6.1/topics/http/middleware/) (id=65328, locale=sv)
3. [ミドルウェア (Middleware) | Django ドキュメント](https://docs.djangoproject.com/ja/6.1/topics/http/middleware/) (id=65323, locale=ja)
4. [Middleware | Django documentation](https://docs.djangoproject.com/en/6.1/ref/middleware/) (id=27988, locale=en)
5. [Middleware | Django-dokumentation](https://docs.djangoproject.com/sv/6.1/ref/middleware/) (id=63938, locale=sv)
6. [Intergiciels (« Middleware ») | Documentation de Django](https://docs.djangoproject.com/fr/6.1/topics/http/middleware/) (id=65321, locale=fr)
7. [中间件 | Django 文档](https://docs.djangoproject.com/zh-hans/6.1/topics/http/middleware/) (id=65329, locale=zh)
8. [Intergiciels (« middleware ») | Documentation de Django](https://docs.djangoproject.com/fr/6.1/ref/middleware/) (id=63931, locale=fr)
9. [Réglages | Documentation de Django](https://docs.djangoproject.com/fr/6.1/ref/settings/) (id=64141, locale=fr)
10. [Asynkront stöd | Django-dokumentation](https://docs.djangoproject.com/sv/6.1/topics/async/) (id=64923, locale=sv)

### Q046: django cache framework

Mode: `text` | Flags: `LOW_AGREEMENT, TARGET_BELOW_K` | Candidates: 100 | Time: 66 ms

**BM25 top 10**

1. [Django 1.4.11 release notes | Django documentation](https://docs.djangoproject.com/en/6.1/releases/1.4.11/) (id=64358, locale=en)
2. [Django 1.5.6 release notes | Django documentation](https://docs.djangoproject.com/en/6.1/releases/1.5.6/) (id=64411, locale=en)
3. [Using Django | Django documentation](https://docs.djangoproject.com/en/6.1/topics/) (id=28110, locale=en)
4. [Design philosophies | Django documentation](https://docs.djangoproject.com/en/6.1/misc/design-philosophies/) (id=27821, locale=en)
5. [Django 1.6.3 release notes | Django documentation](https://docs.djangoproject.com/en/6.1/releases/1.6.3/) (id=64424, locale=en)
6. [Performance and optimization | Django documentation](https://docs.djangoproject.com/en/6.1/topics/performance/) (id=28317, locale=en)
7. [The “sites” framework | Django documentation](https://docs.djangoproject.com/en/6.1/ref/contrib/sites/) (id=27920, locale=en)
8. [Django documentation contents | Django documentation](https://docs.djangoproject.com/en/6.1/contents/) (id=27615, locale=en)
9. [Django 1.4.13 release notes | Django documentation](https://docs.djangoproject.com/en/6.1/releases/1.4.13/) (id=64361, locale=en)
10. [Django 1.5.8 release notes | Django documentation](https://docs.djangoproject.com/en/6.1/releases/1.5.8/) (id=64413, locale=en)

**PostgreSQL top 10**

1. [Django’s cache framework | Django documentation](https://docs.djangoproject.com/en/6.1/topics/cache/) (id=28140, locale=en)
2. [Performance and optimization | Django documentation](https://docs.djangoproject.com/en/6.1/topics/performance/) (id=28317, locale=en)
3. [Design di filosofie | Documentazione di Django](https://docs.djangoproject.com/it/6.1/misc/design-philosophies/) (id=63280, locale=it)
4. [Filosofi rancangan | Dokumentasi Django](https://docs.djangoproject.com/id/6.1/misc/design-philosophies/) (id=38556, locale=id)
5. [Filozofie projektowe | Dokumentacja Django](https://docs.djangoproject.com/pl/6.1/misc/design-philosophies/) (id=63285, locale=pl)
6. [Settings | Django documentation](https://docs.djangoproject.com/en/6.1/ref/settings/) (id=28060, locale=en)
7. [Design philosophies | Django documentation](https://docs.djangoproject.com/en/6.1/misc/design-philosophies/) (id=27821, locale=en)
8. [Filosofias de Projeto | Documentação do Django](https://docs.djangoproject.com/pt-br/6.1/misc/design-philosophies/) (id=38563, locale=pt)
9. [Περιεχόμενα του εγχειριδίου του Django | Εγχειρίδιο Django](https://docs.djangoproject.com/el/6.1/contents/) (id=28807, locale=el)
10. [Φιλοσοφίες σχεδιασμού | Εγχειρίδιο Django](https://docs.djangoproject.com/el/6.1/misc/design-philosophies/) (id=29071, locale=el)

### Q047: django authentication

Mode: `text` | Flags: `MULTILINGUAL_TOP` | Candidates: 100 | Time: 55 ms

**BM25 top 10**

1. [User authentication | Django documentation](https://docs.djangoproject.com/en/6.1/topics/auth/) (id=28120, locale=en)
2. [How to authenticate against Django’s user database from Apache | Django documentation](https://docs.djangoproject.com/en/6.1/howto/deployment/wsgi/apache-auth/) (id=37235, locale=en)
3. [How to authenticate using REMOTE_USER | Django documentation](https://docs.djangoproject.com/en/6.1/howto/auth-remote-user/) (id=36876, locale=en)
4. [Customizing authentication | Django documentation](https://docs.djangoproject.com/en/6.1/topics/auth/customizing/) (id=28125, locale=en)
5. [Django Tutorial Part 8: User authentication and permissions - Learn web development | MDN](https://developer.mozilla.org/en-US/docs/Learn_web_development/Extensions/Server-side/Django/Authentication) (id=6487, locale=en)
6. [Django 中的自定义验证 | Django 文档](https://docs.djangoproject.com/zh-hans/6.1/topics/auth/customizing/) (id=64953, locale=zh)
7. [Django の認証方法のカスタマイズ | Django ドキュメント](https://docs.djangoproject.com/ja/6.1/topics/auth/customizing/) (id=64948, locale=ja)
8. [django.contrib.auth | Django 文档](https://docs.djangoproject.com/zh-hans/6.1/ref/contrib/auth/) (id=63621, locale=zh)
9. [Using the Django authentication system | Django documentation](https://docs.djangoproject.com/en/6.1/topics/auth/default/) (id=28130, locale=en)
10. [django.contrib.auth | Django documentation](https://docs.djangoproject.com/en/6.1/ref/contrib/auth/) (id=27876, locale=en)

**PostgreSQL top 10**

1. [Using the Django authentication system | Django documentation](https://docs.djangoproject.com/en/6.1/topics/auth/default/) (id=28130, locale=en)
2. [Customizing authentication | Django documentation](https://docs.djangoproject.com/en/6.1/topics/auth/customizing/) (id=28125, locale=en)
3. [User authentication | Django documentation](https://docs.djangoproject.com/en/6.1/topics/auth/) (id=28120, locale=en)
4. [Django Tutorial Part 8: User authentication and permissions - Learn web development | MDN](https://developer.mozilla.org/en-US/docs/Learn_web_development/Extensions/Server-side/Django/Authentication) (id=6487, locale=en)
5. [How to authenticate against Django’s user database from Apache | Django documentation](https://docs.djangoproject.com/en/6.1/howto/deployment/wsgi/apache-auth/) (id=37235, locale=en)
6. [Authentication using REMOTE_USER | Εγχειρίδιο Django](https://docs.djangoproject.com/el/6.1/howto/auth-remote-user/) (id=28867, locale=el)
7. [Django 中的自定义验证 | Django 文档](https://docs.djangoproject.com/zh-hans/6.1/topics/auth/customizing/) (id=64953, locale=zh)
8. [How to authenticate using REMOTE_USER | Django documentation](https://docs.djangoproject.com/en/6.1/howto/auth-remote-user/) (id=36876, locale=en)
9. [Django の認証方法のカスタマイズ | Django ドキュメント](https://docs.djangoproject.com/ja/6.1/topics/auth/customizing/) (id=64948, locale=ja)
10. [django.contrib.auth | Django documentation](https://docs.djangoproject.com/en/6.1/ref/contrib/auth/) (id=27876, locale=en)

### Q049: django model field

Mode: `all` | Flags: `LOW_AGREEMENT, MULTILINGUAL_TOP` | Candidates: 162 | Time: 182 ms

**BM25 top 10**

1. [Model _meta API | Django documentation](https://docs.djangoproject.com/en/6.1/ref/models/meta/) (id=62349, locale=en)
2. [Model forms | Django documentation](https://docs.djangoproject.com/en/6.1/ref/forms/models/) (id=62342, locale=en)
3. [Django Tutorial Part 3: Using models - Learn web development | MDN](https://developer.mozilla.org/en-US/docs/Learn_web_development/Extensions/Server-side/Django/Models) (id=6481, locale=en)
4. [GeoDjango Model API | Django documentation](https://docs.djangoproject.com/en/6.1/ref/contrib/gis/model-api/) (id=62491, locale=en)
5. [django.db.models.options | Django ドキュメント](https://docs.djangoproject.com/ja/6.1/_modules/django/db/models/options/) (id=40699, locale=ja)
6. [django.db.models.options | Django 文档](https://docs.djangoproject.com/zh-hans/6.1/_modules/django/db/models/options/) (id=40711, locale=zh)
7. [django.db.models.options | Django 문서](https://docs.djangoproject.com/ko/6.1/_modules/django/db/models/options/) (id=40702, locale=ko)
8. [django.db.models.options | Documentação do Django](https://docs.djangoproject.com/pt-br/6.1/_modules/django/db/models/options/) (id=40708, locale=pt)
9. [django.db.models.options | Dokumentasi Django](https://docs.djangoproject.com/id/6.1/_modules/django/db/models/options/) (id=40696, locale=id)
10. [django.db.models.options | Dokumentacja Django](https://docs.djangoproject.com/pl/6.1/_modules/django/db/models/options/) (id=40705, locale=pl)

**PostgreSQL top 10**

1. [Model field reference | Django documentation](https://docs.djangoproject.com/en/6.1/ref/models/fields/) (id=28016, locale=en)
2. [How to create custom model fields | Django documentation](https://docs.djangoproject.com/en/6.1/howto/custom-model-fields/) (id=27653, locale=en)
3. [PostgreSQL specific model fields | Django documentation](https://docs.djangoproject.com/en/6.1/ref/contrib/postgres/fields/) (id=62503, locale=en)
4. [Come creare model field personalizzati | Documentazione di Django](https://docs.djangoproject.com/it/6.1/howto/custom-model-fields/) (id=62681, locale=it)
5. [Models | Django documentation](https://docs.djangoproject.com/en/6.1/topics/db/models/) (id=28184, locale=en)
6. [Django 1.6 release notes | Django documentation](https://docs.djangoproject.com/en/6.1/releases/1.6/) (id=62524, locale=en)
7. [Django 6.1 release notes | Django documentation](https://docs.djangoproject.com/en/6.1/releases/6.1/) (id=62969, locale=en)
8. [GeoDjango Model API | Django documentation](https://docs.djangoproject.com/en/6.1/ref/contrib/gis/model-api/) (id=62491, locale=en)
9. [Model forms | Django documentation](https://docs.djangoproject.com/en/6.1/ref/forms/models/) (id=62342, locale=en)
10. [django.db.models.options | Django documentation](https://docs.djangoproject.com/en/6.1/_modules/django/db/models/options/) (id=40687, locale=en)

### Q050: django QuerySet select_related

Mode: `code` | Flags: `MULTILINGUAL_TOP` | Candidates: 30 | Time: 44 ms

**BM25 top 10**

1. [QuerySet API reference | Django documentation](https://docs.djangoproject.com/en/6.1/ref/models/querysets/) (id=28041, locale=en)
2. [QuerySet API 参考 | Django 文档](https://docs.djangoproject.com/zh-hans/6.1/ref/models/querysets/) (id=64097, locale=zh)
3. [QuerySet API リファレンス | Django ドキュメント](https://docs.djangoproject.com/ja/6.1/ref/models/querysets/) (id=64092, locale=ja)
4. [Référence de l’API QuerySet | Documentation de Django](https://docs.djangoproject.com/fr/6.1/ref/models/querysets/) (id=64090, locale=fr)
5. [aPI-referens för QuerySet | Django-dokumentation](https://docs.djangoproject.com/sv/6.1/ref/models/querysets/) (id=64096, locale=sv)
6. [django.db.models.query | Εγχειρίδιο Django](https://docs.djangoproject.com/el/6.1/_modules/django/db/models/query/) (id=29456, locale=el)
7. [django.db.models.query | Django ドキュメント](https://docs.djangoproject.com/ja/6.1/_modules/django/db/models/query/) (id=40731, locale=ja)
8. [django.db.models.query | Dokumentasi Django](https://docs.djangoproject.com/id/6.1/_modules/django/db/models/query/) (id=40728, locale=id)
9. [django.db.models.query | Django 문서](https://docs.djangoproject.com/ko/6.1/_modules/django/db/models/query/) (id=40734, locale=ko)
10. [django.db.models.query | Dokumentacja Django](https://docs.djangoproject.com/pl/6.1/_modules/django/db/models/query/) (id=40737, locale=pl)

**PostgreSQL top 10**

1. [django.db.models.query | Εγχειρίδιο Django](https://docs.djangoproject.com/el/6.1/_modules/django/db/models/query/) (id=29456, locale=el)
2. [django.db.models.query | Documentación de Django](https://docs.djangoproject.com/es/6.1/_modules/django/db/models/query/) (id=40722, locale=es)
3. [django.db.models.query | Documentation de Django](https://docs.djangoproject.com/fr/6.1/_modules/django/db/models/query/) (id=40725, locale=fr)
4. [django.db.models.query | Dokumentasi Django](https://docs.djangoproject.com/id/6.1/_modules/django/db/models/query/) (id=40728, locale=id)
5. [django.db.models.query | Django ドキュメント](https://docs.djangoproject.com/ja/6.1/_modules/django/db/models/query/) (id=40731, locale=ja)
6. [django.db.models.query | Django 문서](https://docs.djangoproject.com/ko/6.1/_modules/django/db/models/query/) (id=40734, locale=ko)
7. [django.db.models.query | Dokumentacja Django](https://docs.djangoproject.com/pl/6.1/_modules/django/db/models/query/) (id=40737, locale=pl)
8. [django.db.models.query | Documentação do Django](https://docs.djangoproject.com/pt-br/6.1/_modules/django/db/models/query/) (id=40740, locale=pt)
9. [django.db.models.query | Django 文档](https://docs.djangoproject.com/zh-hans/6.1/_modules/django/db/models/query/) (id=40743, locale=zh)
10. [django.db.models.query | Django documentation](https://docs.djangoproject.com/en/6.1/_modules/django/db/models/query/) (id=40719, locale=en)

### Q051: javascript fetch examples

Mode: `all` | Flags: `LOW_AGREEMENT, TARGET_NOT_IN_CANDIDATES` | Candidates: 162 | Time: 146 ms

**BM25 top 10**

1. [AggregateError: No Promise in Promise.any was resolved - JavaScript | MDN](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Errors/Promise_any_all_rejected) (id=3194, locale=en)
2. [WebAssembly.instantiate() - WebAssembly | MDN](https://developer.mozilla.org/en-US/docs/WebAssembly/Reference/JavaScript_interface/instantiate_static) (id=5620, locale=en)
3. [WebAssembly.validate() - WebAssembly | MDN](https://developer.mozilla.org/en-US/docs/WebAssembly/Reference/JavaScript_interface/validate_static) (id=5628, locale=en)
4. [WebAssembly.compileStreaming() - WebAssembly | MDN](https://developer.mozilla.org/en-US/docs/WebAssembly/Reference/JavaScript_interface/compileStreaming_static) (id=5617, locale=en)
5. [WebAssembly.instantiateStreaming() - WebAssembly | MDN](https://developer.mozilla.org/en-US/docs/WebAssembly/Reference/JavaScript_interface/instantiateStreaming_static) (id=5623, locale=en)
6. [WebAssembly.Instance.prototype.exports - WebAssembly | MDN](https://developer.mozilla.org/en-US/docs/WebAssembly/Reference/JavaScript_interface/Instance/exports) (id=5635, locale=en)
7. [WebAssembly.Instance - WebAssembly | MDN](https://developer.mozilla.org/en-US/docs/WebAssembly/Reference/JavaScript_interface/Instance) (id=5634, locale=en)
8. [WebAssembly.compile() - WebAssembly | MDN](https://developer.mozilla.org/en-US/docs/WebAssembly/Reference/JavaScript_interface/compile_static) (id=5608, locale=en)
9. [WebAssembly.Suspending - WebAssembly | MDN](https://developer.mozilla.org/en-US/docs/WebAssembly/Reference/JavaScript_interface/Suspending) (id=5661, locale=en)
10. [Making network requests with JavaScript - Learn web development | MDN](https://developer.mozilla.org/en-US/docs/Learn_web_development/Core/Scripting/Network_requests) (id=6413, locale=en)

**PostgreSQL top 10**

1. [Resource timing - Web APIs | MDN](https://developer.mozilla.org/en-US/docs/Web/API/Performance_API/Resource_timing) (id=6053, locale=en)
2. [XMLHttpRequest API - Web APIs | MDN](https://developer.mozilla.org/en-US/docs/Web/API/XMLHttpRequest_API) (id=3630, locale=en)
3. [WebAssembly.Instance.prototype.exports - WebAssembly | MDN](https://developer.mozilla.org/en-US/docs/WebAssembly/Reference/JavaScript_interface/Instance/exports) (id=5635, locale=en)
4. [Using readable streams - Web APIs | MDN](https://developer.mozilla.org/en-US/docs/Web/API/Streams_API/Using_readable_streams) (id=23922, locale=en)
5. [Response: bodyUsed property - Web APIs | MDN](https://developer.mozilla.org/en-US/docs/Web/API/Response/bodyUsed) (id=66091, locale=en)
6. [Understanding WebAssembly text format - WebAssembly | MDN](https://developer.mozilla.org/en-US/docs/WebAssembly/Guides/Understanding_the_text_format) (id=5596, locale=en)
7. [Fetch metadata - HTTP | MDN](https://developer.mozilla.org/en-US/docs/Web/HTTP/Guides/Fetch_metadata) (id=4935, locale=en)
8. [Challenge: Building a house data UI - Learn web development | MDN](https://developer.mozilla.org/en-US/docs/Learn_web_development/Core/Scripting/House_data_UI) (id=6416, locale=en)
9. [WebAssembly.instantiate() - WebAssembly | MDN](https://developer.mozilla.org/en-US/docs/WebAssembly/Reference/JavaScript_interface/instantiate_static) (id=5620, locale=en)
10. [Web performance | MDN](https://developer.mozilla.org/en-US/docs/Web/Performance) (id=60, locale=en)

### Q052: javascript Promise.all

Mode: `code` | Flags: `MULTILINGUAL_TOP` | Candidates: 44 | Time: 27 ms

**BM25 top 10**

1. [Promise.all() - JavaScript | MDN](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Promise/all) (id=22809, locale=en)
2. [Array.fromAsync() - JavaScript | MDN](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Array/fromAsync) (id=22607, locale=en)
3. [SyntaxError: await ist nur in asynchronen Funktionen, asynchronen Generatoren und Modulen gültig - JavaScript | MDN](https://developer.mozilla.org/de/docs/Web/JavaScript/Reference/Errors/Bad_await) (id=21395, locale=de)
4. [SyntaxError: await is only valid in async functions, async generators and modules - JavaScript | MDN](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Errors/Bad_await) (id=3223, locale=en)
5. [Element: getAnimations() method - Web APIs | MDN](https://developer.mozilla.org/en-US/docs/Web/API/Element/getAnimations) (id=4569, locale=en)
6. [async function - JavaScript | MDN](https://developer.mozilla.org/fr/docs/Web/JavaScript/Reference/Statements/async_function) (id=20571, locale=fr)
7. [Element: getAnimations() Methode - Web-APIs | MDN](https://developer.mozilla.org/de/docs/Web/API/Element/getAnimations) (id=67347, locale=de)
8. [Promise.allKeyed() - JavaScript | MDN](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Promise/allKeyed) (id=23039, locale=en)
9. [Element : méthode getAnimations() - Les API Web | MDN](https://developer.mozilla.org/fr/docs/Web/API/Element/getAnimations) (id=67364, locale=fr)
10. [async function - JavaScript | MDN](https://developer.mozilla.org/zh-CN/docs/Web/JavaScript/Reference/Statements/async_function) (id=20893, locale=zh)

**PostgreSQL top 10**

1. [Promise.all() - JavaScript | MDN](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Promise/all) (id=22809, locale=en)
2. [Promise.allKeyed() - JavaScript | MDN](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Promise/allKeyed) (id=23039, locale=en)
3. [JavaScript のリソース管理 - JavaScript | MDN](https://developer.mozilla.org/ja/docs/Web/JavaScript/Guide/Resource_management) (id=22007, locale=ja)
4. [JavaScript resource management - JavaScript | MDN](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Guide/Resource_management) (id=2994, locale=en)
5. [Ressourcenverwaltung in JavaScript - JavaScript | MDN](https://developer.mozilla.org/de/docs/Web/JavaScript/Guide/Resource_management) (id=21172, locale=de)
6. [理解 WebAssembly 文本格式 - WebAssembly | MDN](https://developer.mozilla.org/zh-CN/docs/WebAssembly/Guides/Understanding_the_text_format) (id=72441, locale=zh)
7. [SyntaxError: await is only valid in async functions, async generators and modules - JavaScript | MDN](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Errors/Bad_await) (id=3223, locale=en)
8. [SyntaxError: await ist nur in asynchronen Funktionen, asynchronen Generatoren und Modulen gültig - JavaScript | MDN](https://developer.mozilla.org/de/docs/Web/JavaScript/Reference/Errors/Bad_await) (id=21395, locale=de)
9. [Element: getAnimations() Methode - Web-APIs | MDN](https://developer.mozilla.org/de/docs/Web/API/Element/getAnimations) (id=67347, locale=de)
10. [Element: getAnimations() method - Web APIs | MDN](https://developer.mozilla.org/en-US/docs/Web/API/Element/getAnimations) (id=4569, locale=en)

### Q053: javascript async await

Mode: `text` | Flags: `MULTILINGUAL_TOP` | Candidates: 100 | Time: 105 ms

**BM25 top 10**

1. [SyntaxError: await is only valid in async functions, async generators and modules - JavaScript | MDN](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Errors/Bad_await) (id=3223, locale=en)
2. [async function - JavaScript | MDN](https://developer.mozilla.org/zh-CN/docs/Web/JavaScript/Reference/Statements/async_function) (id=20893, locale=zh)
3. [SyntaxError: await ist nur in asynchronen Funktionen, asynchronen Generatoren und Modulen gültig - JavaScript | MDN](https://developer.mozilla.org/de/docs/Web/JavaScript/Reference/Errors/Bad_await) (id=21395, locale=de)
4. [async function - JavaScript | MDN](https://developer.mozilla.org/ja/docs/Web/JavaScript/Reference/Statements/async_function) (id=22136, locale=ja)
5. [async function - JavaScript | MDN](https://developer.mozilla.org/zh-TW/docs/Web/JavaScript/Reference/Statements/async_function) (id=21079, locale=zh)
6. [AsyncIterator.prototype\[Symbol.asyncDispose\]() - JavaScript | MDN](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/AsyncIterator/Symbol.asyncDispose) (id=22912, locale=en)
7. [async function - JavaScript | MDN](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Statements/async_function) (id=3130, locale=en)
8. [await - JavaScript | MDN](https://developer.mozilla.org/zh-TW/docs/Web/JavaScript/Reference/Operators/await) (id=21062, locale=zh)
9. [AsyncIterator.prototype\[Symbol.asyncIterator\]() - JavaScript | MDN](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/AsyncIterator/Symbol.asyncIterator) (id=22911, locale=en)
10. [await using - JavaScript | MDN](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Statements/await_using) (id=3139, locale=en)

**PostgreSQL top 10**

1. [SyntaxError: await is only valid in async functions, async generators and modules - JavaScript | MDN](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Errors/Bad_await) (id=3223, locale=en)
2. [async function - JavaScript | MDN](https://developer.mozilla.org/zh-CN/docs/Web/JavaScript/Reference/Statements/async_function) (id=20893, locale=zh)
3. [async function - JavaScript | MDN](https://developer.mozilla.org/ja/docs/Web/JavaScript/Reference/Statements/async_function) (id=22136, locale=ja)
4. [async function - JavaScript | MDN](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Statements/async_function) (id=3130, locale=en)
5. [SyntaxError: await ist nur in asynchronen Funktionen, asynchronen Generatoren und Modulen gültig - JavaScript | MDN](https://developer.mozilla.org/de/docs/Web/JavaScript/Reference/Errors/Bad_await) (id=21395, locale=de)
6. [How to use promises - Learn web development | MDN](https://developer.mozilla.org/en-US/docs/Learn_web_development/Extensions/Async_JS/Promises) (id=6448, locale=en)
7. [async function - JavaScript | MDN](https://developer.mozilla.org/es/docs/Web/JavaScript/Reference/Statements/async_function) (id=20346, locale=es)
8. [Делаем асинхронное программирование более простым с async и await - Изучение веб-разработки | MDN](https://developer.mozilla.org/ru/docs/Learn_web_development/Extensions/Async_JS/Promises) (id=12032, locale=ru)
9. [async function - JavaScript | MDN](https://developer.mozilla.org/zh-TW/docs/Web/JavaScript/Reference/Statements/async_function) (id=21079, locale=zh)
10. [async function - JavaScript | MDN](https://developer.mozilla.org/ko/docs/Web/JavaScript/Reference/Statements/async_function) (id=21674, locale=ko)

### Q056: javascript closures

Mode: `text` | Flags: `MULTILINGUAL_TOP` | Candidates: 100 | Time: 60 ms

**BM25 top 10**

1. [Closures - JavaScript | MDN](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Guide/Closures) (id=2920, locale=en)
2. [Closure - Glossary | MDN](https://developer.mozilla.org/en-US/docs/Glossary/Closure) (id=6945, locale=en)
3. [Closures - JavaScript | MDN](https://developer.mozilla.org/de/docs/Web/JavaScript/Guide/Closures) (id=21135, locale=de)
4. [Closures - JavaScript | MDN](https://developer.mozilla.org/pt-BR/docs/Web/JavaScript/Guide/Closures) (id=21803, locale=pt)
5. [Closures - JavaScript | MDN](https://developer.mozilla.org/es/docs/Web/JavaScript/Guide/Closures) (id=20251, locale=es)
6. [Functions - JavaScript | MDN](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Guide/Functions) (id=2971, locale=en)
7. [Функции - JavaScript | MDN](https://developer.mozilla.org/ru/docs/Web/JavaScript/Guide/Functions) (id=22320, locale=ru)
8. [Funções - JavaScript | MDN](https://developer.mozilla.org/pt-BR/docs/Web/JavaScript/Guide/Functions) (id=21794, locale=pt)
9. [Funktionen - JavaScript | MDN](https://developer.mozilla.org/de/docs/Web/JavaScript/Guide/Functions) (id=21167, locale=de)
10. [JavaScript | MDN](https://developer.mozilla.org/zh-TW/docs/Web/JavaScript) (id=2892, locale=zh)

**PostgreSQL top 10**

1. [Closures - JavaScript | MDN](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Guide/Closures) (id=2920, locale=en)
2. [Closures - JavaScript | MDN](https://developer.mozilla.org/de/docs/Web/JavaScript/Guide/Closures) (id=21135, locale=de)
3. [Closures - JavaScript | MDN](https://developer.mozilla.org/es/docs/Web/JavaScript/Guide/Closures) (id=20251, locale=es)
4. [Closures - JavaScript | MDN](https://developer.mozilla.org/pt-BR/docs/Web/JavaScript/Guide/Closures) (id=21803, locale=pt)
5. [Closures (Fermetures) - JavaScript | MDN](https://developer.mozilla.org/fr/docs/Web/JavaScript/Guide/Closures) (id=20453, locale=fr)
6. [Closure - Glossary | MDN](https://developer.mozilla.org/en-US/docs/Glossary/Closure) (id=6945, locale=en)
7. [Überblick über die JavaScript-Sprache - JavaScript | MDN](https://developer.mozilla.org/de/docs/Web/JavaScript/Guide/Language_overview) (id=21133, locale=de)
8. [JavaScript language overview - JavaScript | MDN](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Guide/Language_overview) (id=2922, locale=en)
9. [Functions - JavaScript | MDN](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Guide/Functions) (id=2971, locale=en)
10. [Funktionen - JavaScript | MDN](https://developer.mozilla.org/de/docs/Web/JavaScript/Guide/Functions) (id=21167, locale=de)

### Q057: javascript destructuring assignment

Mode: `text` | Flags: `MULTILINGUAL_TOP` | Candidates: 77 | Time: 36 ms

**BM25 top 10**

1. [Destructuring - JavaScript | MDN](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Operators/Destructuring) (id=3076, locale=en)
2. [Assignment (=) - JavaScript | MDN](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Operators/Assignment) (id=3059, locale=en)
3. [TypeError: null/undefined has no properties - JavaScript | MDN](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Errors/No_properties) (id=3315, locale=en)
4. [const - JavaScript | MDN](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Statements/const) (id=2944, locale=en)
5. [TypeError: null/undefined has no properties - JavaScript | MDN](https://developer.mozilla.org/ja/docs/Web/JavaScript/Reference/Errors/No_properties) (id=22263, locale=ja)
6. [TypeError: null/undefined has no properties - JavaScript | MDN](https://developer.mozilla.org/zh-TW/docs/Web/JavaScript/Reference/Errors/No_properties) (id=21106, locale=zh)
7. [Destructuring - JavaScript | MDN](https://developer.mozilla.org/de/docs/Web/JavaScript/Reference/Operators/Destructuring) (id=21252, locale=de)
8. [Atribuição via desestruturação (destructuring assignment) - JavaScript | MDN](https://developer.mozilla.org/pt-BR/docs/Web/JavaScript/Reference/Operators/Destructuring) (id=21843, locale=pt)
9. [TypeError: null/undefined hat keine Eigenschaften - JavaScript | MDN](https://developer.mozilla.org/de/docs/Web/JavaScript/Reference/Errors/No_properties) (id=21490, locale=de)
10. [Default parameters - JavaScript | MDN](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Functions/Default_parameters) (id=3163, locale=en)

**PostgreSQL top 10**

1. [Atribuição via desestruturação (destructuring assignment) - JavaScript | MDN](https://developer.mozilla.org/pt-BR/docs/Web/JavaScript/Reference/Operators/Destructuring) (id=21843, locale=pt)
2. [Destructuring - JavaScript | MDN](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Operators/Destructuring) (id=3076, locale=en)
3. [Expressions and operators - JavaScript | MDN](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Guide/Expressions_and_operators) (id=2963, locale=en)
4. [Parámetros Rest - JavaScript | MDN](https://developer.mozilla.org/es/docs/Web/JavaScript/Reference/Functions/rest_parameters) (id=20365, locale=es)
5. [其餘參數 - JavaScript | MDN](https://developer.mozilla.org/zh-TW/docs/Web/JavaScript/Reference/Functions/rest_parameters) (id=21095, locale=zh)
6. [Assignment (=) - JavaScript | MDN](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Operators/Assignment) (id=3059, locale=en)
7. [Firefox 2 release notes for developers - Mozilla | MDN](https://developer.mozilla.org/en-US/docs/Mozilla/Firefox/Releases/2) (id=17697, locale=en)
8. [Default parameters - JavaScript | MDN](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Functions/Default_parameters) (id=3163, locale=en)
9. [let - JavaScript | MDN](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Statements/let) (id=2948, locale=en)
10. [var - JavaScript | MDN](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Statements/var) (id=2940, locale=en)

### Q058: javascript optional chaining

Mode: `text` | Flags: `MULTILINGUAL_TOP` | Candidates: 100 | Time: 73 ms

**BM25 top 10**

1. [SyntaxError: tagged template cannot be used with optional chain - JavaScript | MDN](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Errors/Bad_optional_template) (id=3281, locale=en)
2. [SyntaxError: new keyword cannot be used with an optional chain - JavaScript | MDN](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Errors/Bad_new_optional) (id=3270, locale=en)
3. [Optional chaining (?.) - JavaScript | MDN](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Operators/Optional_chaining) (id=3112, locale=en)
4. [Optional Chaining (?.) - JavaScript | MDN](https://developer.mozilla.org/de/docs/Web/JavaScript/Reference/Operators/Optional_chaining) (id=21293, locale=de)
5. [Optional chaining - JavaScript | MDN](https://developer.mozilla.org/ko/docs/Web/JavaScript/Reference/Operators/Optional_chaining) (id=21654, locale=ko)
6. [SyntaxError: new keyword cannot be used with an optional chain - JavaScript | MDN](https://developer.mozilla.org/de/docs/Web/JavaScript/Reference/Errors/Bad_new_optional) (id=21436, locale=de)
7. [オプショナルチェーン演算子 (?.) - JavaScript | MDN](https://developer.mozilla.org/ja/docs/Web/JavaScript/Reference/Operators/Optional_chaining) (id=22119, locale=ja)
8. [Conditional (ternary) operator - JavaScript | MDN](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Operators/Conditional_operator) (id=3078, locale=en)
9. [SyntaxError: invalid assignment left-hand side - JavaScript | MDN](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Errors/Invalid_assignment_left-hand_side) (id=3241, locale=en)
10. [Nullish coalescing operator - JavaScript | MDN](https://developer.mozilla.org/ko/docs/Web/JavaScript/Reference/Operators/Nullish_coalescing) (id=21649, locale=ko)

**PostgreSQL top 10**

1. [Optional Chaining (?.) - JavaScript | MDN](https://developer.mozilla.org/de/docs/Web/JavaScript/Reference/Operators/Optional_chaining) (id=21293, locale=de)
2. [Optional chaining (?.) - JavaScript | MDN](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Operators/Optional_chaining) (id=3112, locale=en)
3. [Optional chaining - JavaScript | MDN](https://developer.mozilla.org/ko/docs/Web/JavaScript/Reference/Operators/Optional_chaining) (id=21654, locale=ko)
4. [SyntaxError: tagged template cannot be used with optional chain - JavaScript | MDN](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Errors/Bad_optional_template) (id=3281, locale=en)
5. [SyntaxError: new keyword cannot be used with an optional chain - JavaScript | MDN](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Errors/Bad_new_optional) (id=3270, locale=en)
6. [SyntaxError: new keyword cannot be used with an optional chain - JavaScript | MDN](https://developer.mozilla.org/de/docs/Web/JavaScript/Reference/Errors/Bad_new_optional) (id=21436, locale=de)
7. [Firefox 74 release notes for developers - Mozilla | MDN](https://developer.mozilla.org/en-US/docs/Mozilla/Firefox/Releases/74) (id=70732, locale=en)
8. [SyntaxError: invalid assignment left-hand side - JavaScript | MDN](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Errors/Invalid_assignment_left-hand_side) (id=3241, locale=en)
9. [Expressions and operators - JavaScript | MDN](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Guide/Expressions_and_operators) (id=2963, locale=en)
10. [オプショナルチェーン演算子 (?.) - JavaScript | MDN](https://developer.mozilla.org/ja/docs/Web/JavaScript/Reference/Operators/Optional_chaining) (id=22119, locale=ja)

### Q059: javascript Object.entries

Mode: `code` | Flags: `MULTILINGUAL_TOP` | Candidates: 26 | Time: 11 ms

**BM25 top 10**

1. [Object.entries() - JavaScript | MDN](https://developer.mozilla.org/zh-TW/docs/Web/JavaScript/Reference/Global_Objects/Object/entries) (id=23543, locale=zh)
2. [Object.entries() - JavaScript | MDN](https://developer.mozilla.org/ja/docs/Web/JavaScript/Reference/Global_Objects/Object/entries) (id=23541, locale=ja)
3. [Object.entries() - JavaScript | MDN](https://developer.mozilla.org/zh-CN/docs/Web/JavaScript/Reference/Global_Objects/Object/entries) (id=23546, locale=zh)
4. [Object.entries() - JavaScript | MDN](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Object/entries) (id=3431, locale=en)
5. [Object.entries() - JavaScript | MDN](https://developer.mozilla.org/de/docs/Web/JavaScript/Reference/Global_Objects/Object/entries) (id=23540, locale=de)
6. [Object.entries() - JavaScript | MDN](https://developer.mozilla.org/es/docs/Web/JavaScript/Reference/Global_Objects/Object/entries) (id=23548, locale=es)
7. [Object.entries() - JavaScript | MDN](https://developer.mozilla.org/pt-BR/docs/Web/JavaScript/Reference/Global_Objects/Object/entries) (id=23545, locale=pt)
8. [Object.entries() - JavaScript | MDN](https://developer.mozilla.org/ko/docs/Web/JavaScript/Reference/Global_Objects/Object/entries) (id=23544, locale=ko)
9. [Object.entries() - JavaScript | MDN](https://developer.mozilla.org/ru/docs/Web/JavaScript/Reference/Global_Objects/Object/entries) (id=23549, locale=ru)
10. [Object : méthode statique entries() - JavaScript | MDN](https://developer.mozilla.org/fr/docs/Web/JavaScript/Reference/Global_Objects/Object/entries) (id=23547, locale=fr)

**PostgreSQL top 10**

1. [Object.entries() - JavaScript | MDN](https://developer.mozilla.org/pt-BR/docs/Web/JavaScript/Reference/Global_Objects/Object/entries) (id=23545, locale=pt)
2. [Object.entries() - JavaScript | MDN](https://developer.mozilla.org/es/docs/Web/JavaScript/Reference/Global_Objects/Object/entries) (id=23548, locale=es)
3. [Object.entries() - JavaScript | MDN](https://developer.mozilla.org/zh-TW/docs/Web/JavaScript/Reference/Global_Objects/Object/entries) (id=23543, locale=zh)
4. [Object.entries() - JavaScript | MDN](https://developer.mozilla.org/ko/docs/Web/JavaScript/Reference/Global_Objects/Object/entries) (id=23544, locale=ko)
5. [Object.entries() - JavaScript | MDN](https://developer.mozilla.org/zh-CN/docs/Web/JavaScript/Reference/Global_Objects/Object/entries) (id=23546, locale=zh)
6. [Object.entries() - JavaScript | MDN](https://developer.mozilla.org/ru/docs/Web/JavaScript/Reference/Global_Objects/Object/entries) (id=23549, locale=ru)
7. [Object.entries() - JavaScript | MDN](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Object/entries) (id=3431, locale=en)
8. [Object.entries() - JavaScript | MDN](https://developer.mozilla.org/de/docs/Web/JavaScript/Reference/Global_Objects/Object/entries) (id=23540, locale=de)
9. [Object.entries() - JavaScript | MDN](https://developer.mozilla.org/ja/docs/Web/JavaScript/Reference/Global_Objects/Object/entries) (id=23541, locale=ja)
10. [Object : méthode statique entries() - JavaScript | MDN](https://developer.mozilla.org/fr/docs/Web/JavaScript/Reference/Global_Objects/Object/entries) (id=23547, locale=fr)

### Q060: javascript modules import export

Mode: `text` | Flags: `MULTILINGUAL_TOP` | Candidates: 100 | Time: 192 ms

**BM25 top 10**

1. [export - JavaScript | MDN](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Statements/export) (id=3149, locale=en)
2. [JavaScript modules - JavaScript | MDN](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Guide/Modules) (id=2990, locale=en)
3. [export - JavaScript | MDN](https://developer.mozilla.org/fr/docs/Web/JavaScript/Reference/Statements/export) (id=20580, locale=fr)
4. [import - JavaScript | MDN](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Statements/import) (id=3143, locale=en)
5. [JavaScript モジュール - JavaScript | MDN](https://developer.mozilla.org/ja/docs/Web/JavaScript/Guide/Modules) (id=22009, locale=ja)
6. [WebAssembly.Suspending - WebAssembly | MDN](https://developer.mozilla.org/en-US/docs/WebAssembly/Reference/JavaScript_interface/Suspending) (id=5661, locale=en)
7. [import source - JavaScript | MDN](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Statements/import/source) (id=3156, locale=en)
8. [JavaScript 模块 - JavaScript | MDN](https://developer.mozilla.org/zh-CN/docs/Web/JavaScript/Guide/Modules) (id=20766, locale=zh)
9. [export - JavaScript | MDN](https://developer.mozilla.org/ko/docs/Web/JavaScript/Reference/Statements/export) (id=21678, locale=ko)
10. [funcref: Wasm value type - WebAssembly | MDN](https://developer.mozilla.org/en-US/docs/WebAssembly/Reference/Value_types/funcref) (id=5719, locale=en)

**PostgreSQL top 10**

1. [Guide JavaScript - JavaScript | MDN](https://developer.mozilla.org/fr/docs/Web/JavaScript/Guide) (id=3436, locale=fr)
2. [JavaScript Guide - JavaScript | MDN](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Guide) (id=40, locale=en)
3. [JavaScript 안내서 - JavaScript | MDN](https://developer.mozilla.org/ko/docs/Web/JavaScript/Guide) (id=3440, locale=ko)
4. [import - JavaScript | MDN](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Statements/import) (id=3143, locale=en)
5. [Understanding WebAssembly text format - WebAssembly | MDN](https://developer.mozilla.org/en-US/docs/WebAssembly/Guides/Understanding_the_text_format) (id=5596, locale=en)
6. [JavaScript modules - JavaScript | MDN](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Guide/Modules) (id=2990, locale=en)
7. [export - JavaScript | MDN](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Statements/export) (id=3149, locale=en)
8. [import source - JavaScript | MDN](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Statements/import/source) (id=3156, locale=en)
9. [WebAssembly テキスト形式の理解 - WebAssembly | MDN](https://developer.mozilla.org/ja/docs/WebAssembly/Guides/Understanding_the_text_format) (id=72383, locale=ja)
10. [JavaScript モジュール - JavaScript | MDN](https://developer.mozilla.org/ja/docs/Web/JavaScript/Guide/Modules) (id=22009, locale=ja)

### Q061: HTTP 404

Mode: `code` | Flags: `LOW_AGREEMENT, MULTILINGUAL_TOP` | Candidates: 100 | Time: 31 ms

**BM25 top 10**

1. [404 Not Found - HTTP | MDN](https://developer.mozilla.org/zh-CN/docs/Web/HTTP/Reference/Status/404) (id=67680, locale=zh)
2. [404 Not Found - HTTP | MDN](https://developer.mozilla.org/es/docs/Web/HTTP/Reference/Status/404) (id=67676, locale=es)
3. [404 Not Found - HTTP | MDN](https://developer.mozilla.org/ko/docs/Web/HTTP/Reference/Status/404) (id=67681, locale=ko)
4. [404 Not Found - HTTP | MDN](https://developer.mozilla.org/ru/docs/Web/HTTP/Reference/Status/404) (id=67682, locale=ru)
5. [404 Not Found - HTTP | MDN](https://developer.mozilla.org/pt-BR/docs/Web/HTTP/Reference/Status/404) (id=67678, locale=pt)
6. [404 Not Found - HTTP | MDN](https://developer.mozilla.org/ja/docs/Web/HTTP/Reference/Status/404) (id=67613, locale=ja)
7. [404 Not Found - HTTP | MDN](https://developer.mozilla.org/zh-TW/docs/Web/HTTP/Reference/Status/404) (id=67659, locale=zh)
8. [404 Not Found - HTTP | MDN](https://developer.mozilla.org/de/docs/Web/HTTP/Reference/Status/404) (id=67487, locale=de)
9. [404 Not Found - HTTP | MDN](https://developer.mozilla.org/fr/docs/Web/HTTP/Reference/Status/404) (id=67524, locale=fr)
10. [404 Not Found - HTTP | MDN](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Status/404) (id=4614, locale=en)

**PostgreSQL top 10**

1. [Status Codes - FastAPI](https://fastapi.tiangolo.com/reference/status/) (id=27992, locale=en)
2. [Status Codes - FastAPI](https://fastapi.tiangolo.com/de/reference/status/) (id=28766, locale=de)
3. [Status Codes - FastAPI](https://fastapi.tiangolo.com/es/reference/status/) (id=29526, locale=es)
4. [Status Codes - FastAPI](https://fastapi.tiangolo.com/fr/reference/status/) (id=30283, locale=fr)
5. [Status Codes - FastAPI](https://fastapi.tiangolo.com/hi/reference/status/) (id=31039, locale=hi)
6. [Status Codes - FastAPI](https://fastapi.tiangolo.com/ja/reference/status/) (id=31715, locale=ja)
7. [Status Codes - FastAPI](https://fastapi.tiangolo.com/ko/reference/status/) (id=32322, locale=ko)
8. [Status Codes - FastAPI](https://fastapi.tiangolo.com/pt/reference/status/) (id=32927, locale=pt)
9. [Status Codes - FastAPI](https://fastapi.tiangolo.com/ru/reference/status/) (id=33533, locale=ru)
10. [Status Codes - FastAPI](https://fastapi.tiangolo.com/tr/reference/status/) (id=34116, locale=tr)

### Q062: HTTP 500 internal server error

Mode: `text` | Flags: `MULTILINGUAL_TOP` | Candidates: 100 | Time: 192 ms

**BM25 top 10**

1. [500 Internal Server Error - HTTP | MDN](https://developer.mozilla.org/ja/docs/Web/HTTP/Reference/Status/500) (id=68759, locale=ja)
2. [500 Internal Server Error - HTTP | MDN](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Status/500) (id=5681, locale=en)
3. [500 Internal Server Error - HTTP | MDN](https://developer.mozilla.org/zh-TW/docs/Web/HTTP/Reference/Status/500) (id=69857, locale=zh)
4. [500 Internal Server Error - HTTP | MDN](https://developer.mozilla.org/zh-CN/docs/Web/HTTP/Reference/Status/500) (id=70054, locale=zh)
5. [500 Internal Server Error - HTTP | MDN](https://developer.mozilla.org/de/docs/Web/HTTP/Reference/Status/500) (id=69097, locale=de)
6. [500 Internal Server Error - HTTP | MDN](https://developer.mozilla.org/es/docs/Web/HTTP/Reference/Status/500) (id=69768, locale=es)
7. [500 Internal Server Error - HTTP | MDN](https://developer.mozilla.org/ko/docs/Web/HTTP/Reference/Status/500) (id=70230, locale=ko)
8. [500 Internal Server Error - HTTP | MDN](https://developer.mozilla.org/fr/docs/Web/HTTP/Reference/Status/500) (id=69609, locale=fr)
9. [WebDriver のエラー - WebDriver | MDN](https://developer.mozilla.org/ja/docs/Web/WebDriver/Reference/Errors) (id=72011, locale=ja)
10. [500 Internal Server Error - HTTP | MDN](https://developer.mozilla.org/pt-BR/docs/Web/HTTP/Reference/Status/500) (id=69328, locale=pt)

**PostgreSQL top 10**

1. [500 Internal Server Error - HTTP | MDN](https://developer.mozilla.org/zh-TW/docs/Web/HTTP/Reference/Status/500) (id=69857, locale=zh)
2. [500 Internal Server Error - HTTP | MDN](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Status/500) (id=5681, locale=en)
3. [500 Internal Server Error - HTTP | MDN](https://developer.mozilla.org/ja/docs/Web/HTTP/Reference/Status/500) (id=68759, locale=ja)
4. [500 Internal Server Error - HTTP | MDN](https://developer.mozilla.org/ko/docs/Web/HTTP/Reference/Status/500) (id=70230, locale=ko)
5. [500 Internal Server Error - HTTP | MDN](https://developer.mozilla.org/zh-CN/docs/Web/HTTP/Reference/Status/500) (id=70054, locale=zh)
6. [500 Internal Server Error - HTTP | MDN](https://developer.mozilla.org/es/docs/Web/HTTP/Reference/Status/500) (id=69768, locale=es)
7. [500 Internal Server Error - HTTP | MDN](https://developer.mozilla.org/fr/docs/Web/HTTP/Reference/Status/500) (id=69609, locale=fr)
8. [500 Internal Server Error - HTTP | MDN](https://developer.mozilla.org/de/docs/Web/HTTP/Reference/Status/500) (id=69097, locale=de)
9. [500 Internal Server Error - HTTP | MDN](https://developer.mozilla.org/pt-BR/docs/Web/HTTP/Reference/Status/500) (id=69328, locale=pt)
10. [500 Internal Server Error - HTTP | MDN](https://developer.mozilla.org/ru/docs/Web/HTTP/Reference/Status/500) (id=70349, locale=ru)

### Q063: HTTP caching Cache-Control

Mode: `all` | Flags: `MULTILINGUAL_TOP` | Candidates: 105 | Time: 249 ms

**BM25 top 10**

1. [HTTP caching - HTTP | MDN](https://developer.mozilla.org/zh-TW/docs/Web/HTTP/Guides/Caching) (id=69770, locale=zh)
2. [HTTP caching - HTTP | MDN](https://developer.mozilla.org/en-US/docs/Web/HTTP/Guides/Caching) (id=4904, locale=en)
3. [HTTP-Caching - HTTP | MDN](https://developer.mozilla.org/de/docs/Web/HTTP/Guides/Caching) (id=68841, locale=de)
4. [Cache-Control header - HTTP | MDN](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Cache-Control) (id=4973, locale=en)
5. [HTTP caching - HTTP | MDN](https://developer.mozilla.org/pt-BR/docs/Web/HTTP/Guides/Caching) (id=69184, locale=pt)
6. [HTTP caching - HTTP | MDN](https://developer.mozilla.org/es/docs/Web/HTTP/Guides/Caching) (id=69694, locale=es)
7. [Cache-Control - HTTP | MDN](https://developer.mozilla.org/zh-CN/docs/Web/HTTP/Reference/Headers/Cache-Control) (id=69930, locale=zh)
8. [Cache-Control - HTTP | MDN](https://developer.mozilla.org/zh-TW/docs/Web/HTTP/Reference/Headers/Cache-Control) (id=69790, locale=zh)
9. [Cache-Control - HTTP | MDN](https://developer.mozilla.org/ko/docs/Web/HTTP/Reference/Headers/Cache-Control) (id=70148, locale=ko)
10. [Cache-Control - HTTP | MDN](https://developer.mozilla.org/ru/docs/Web/HTTP/Reference/Headers/Cache-Control) (id=70273, locale=ru)

**PostgreSQL top 10**

1. [En-tête Cache-Control - HTTP | MDN](https://developer.mozilla.org/fr/docs/Web/HTTP/Reference/Headers/Cache-Control) (id=69413, locale=fr)
2. [Cache-Control - HTTP | MDN](https://developer.mozilla.org/es/docs/Web/HTTP/Reference/Headers/Cache-Control) (id=69717, locale=es)
3. [Cache-Control header - HTTP | MDN](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Cache-Control) (id=4973, locale=en)
4. [Cache-Control ヘッダー - HTTP | MDN](https://developer.mozilla.org/ja/docs/Web/HTTP/Reference/Headers/Cache-Control) (id=68607, locale=ja)
5. [Cache-Control header - HTTP | MDN](https://developer.mozilla.org/de/docs/Web/HTTP/Reference/Headers/Cache-Control) (id=68907, locale=de)
6. [Cache-Control - HTTP | MDN](https://developer.mozilla.org/zh-TW/docs/Web/HTTP/Reference/Headers/Cache-Control) (id=69790, locale=zh)
7. [HTTP caching - HTTP | MDN](https://developer.mozilla.org/en-US/docs/Web/HTTP/Guides/Caching) (id=4904, locale=en)
8. [HTTP キャッシュ - HTTP | MDN](https://developer.mozilla.org/ja/docs/Web/HTTP/Guides/Caching) (id=68550, locale=ja)
9. [HTTP 缓存 - HTTP | MDN](https://developer.mozilla.org/zh-CN/docs/Web/HTTP/Guides/Caching) (id=69868, locale=zh)
10. [HTTP-Caching - HTTP | MDN](https://developer.mozilla.org/de/docs/Web/HTTP/Guides/Caching) (id=68841, locale=de)

### Q064: HTTP CORS preflight

Mode: `text` | Flags: `MULTILINGUAL_TOP` | Candidates: 81 | Time: 49 ms

**BM25 top 10**

1. [Preflight request - Glossary | MDN](https://developer.mozilla.org/en-US/docs/Glossary/Preflight_request) (id=7195, locale=en)
2. [Cross-Origin Resource Sharing (CORS) - HTTP | MDN](https://developer.mozilla.org/en-US/docs/Web/HTTP/Guides/CORS) (id=224, locale=en)
3. [Access-Control-Allow-Headers header - HTTP | MDN](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Access-Control-Allow-Headers) (id=4962, locale=en)
4. [Reason: CORS preflight channel did not succeed - HTTP | MDN](https://developer.mozilla.org/en-US/docs/Web/HTTP/Guides/CORS/Errors/CORSPreflightDidNotSucceed) (id=4945, locale=en)
5. [Cross-Origin Resource Sharing (CORS) - HTTP | MDN](https://developer.mozilla.org/de/docs/Web/HTTP/Guides/CORS) (id=8227, locale=de)
6. [CORS - Glossary | MDN](https://developer.mozilla.org/en-US/docs/Glossary/CORS) (id=6967, locale=en)
7. [Reason: missing token ‘xyz’ in CORS header ‘Access-Control-Allow-Headers’ from CORS preflight channel - HTTP | MDN](https://developer.mozilla.org/ja/docs/Web/HTTP/Guides/CORS/Errors/CORSMissingAllowHeaderFromPreflight) (id=68590, locale=ja)
8. [原因：missing token 'xyz' in CORS header 'Access-Control-Allow-Headers' from CORS preflight channel - HTTP | MDN](https://developer.mozilla.org/zh-CN/docs/Web/HTTP/Guides/CORS/Errors/CORSMissingAllowHeaderFromPreflight) (id=69908, locale=zh)
9. [Reason: missing token 'xyz' in CORS header 'Access-Control-Allow-Headers' from CORS preflight channel - HTTP | MDN](https://developer.mozilla.org/en-US/docs/Web/HTTP/Guides/CORS/Errors/CORSMissingAllowHeaderFromPreflight) (id=4954, locale=en)
10. [Access-Control-Allow-Headers header - HTTP | MDN](https://developer.mozilla.org/de/docs/Web/HTTP/Reference/Headers/Access-Control-Allow-Headers) (id=68893, locale=de)

**PostgreSQL top 10**

1. [原因：missing token 'xyz' in CORS header 'Access-Control-Allow-Headers' from CORS preflight channel - HTTP | MDN](https://developer.mozilla.org/zh-CN/docs/Web/HTTP/Guides/CORS/Errors/CORSMissingAllowHeaderFromPreflight) (id=69908, locale=zh)
2. [Reason: missing token ‘xyz’ in CORS header ‘Access-Control-Allow-Headers’ from CORS preflight channel - HTTP | MDN](https://developer.mozilla.org/ja/docs/Web/HTTP/Guides/CORS/Errors/CORSMissingAllowHeaderFromPreflight) (id=68590, locale=ja)
3. [Reason: missing token 'xyz' in CORS header 'Access-Control-Allow-Headers' from CORS preflight channel - HTTP | MDN](https://developer.mozilla.org/en-US/docs/Web/HTTP/Guides/CORS/Errors/CORSMissingAllowHeaderFromPreflight) (id=4954, locale=en)
4. [Reason: missing token 'xyz' in CORS header 'Access-Control-Allow-Headers' from CORS preflight channel - HTTP | MDN](https://developer.mozilla.org/ko/docs/Web/HTTP/Guides/CORS/Errors/CORSMissingAllowHeaderFromPreflight) (id=70130, locale=ko)
5. [Reason: missing token 'xyz' in CORS header 'Access-Control-Allow-Headers' from CORS preflight channel - HTTP | MDN](https://developer.mozilla.org/de/docs/Web/HTTP/Guides/CORS/Errors/CORSMissingAllowHeaderFromPreflight) (id=68880, locale=de)
6. [Reason: CORS preflight channel did not succeed - HTTP | MDN](https://developer.mozilla.org/en-US/docs/Web/HTTP/Guides/CORS/Errors/CORSPreflightDidNotSucceed) (id=4945, locale=en)
7. [Reason: CORS preflight channel did not succeed - HTTP | MDN](https://developer.mozilla.org/ja/docs/Web/HTTP/Guides/CORS/Errors/CORSPreflightDidNotSucceed) (id=68581, locale=ja)
8. [Reason: CORS preflight channel did not succeed - HTTP | MDN](https://developer.mozilla.org/de/docs/Web/HTTP/Guides/CORS/Errors/CORSPreflightDidNotSucceed) (id=68871, locale=de)
9. [Reason: CORS preflight channel did not succeed - HTTP | MDN](https://developer.mozilla.org/es/docs/Web/HTTP/Guides/CORS/Errors/CORSPreflightDidNotSucceed) (id=69712, locale=es)
10. [原因：CORS preflight channel did not succeed - HTTP | MDN](https://developer.mozilla.org/zh-CN/docs/Web/HTTP/Guides/CORS/Errors/CORSPreflightDidNotSucceed) (id=69901, locale=zh)

### Q065: Content Security Policy

Mode: `text` | Flags: `MULTILINGUAL_TOP` | Candidates: 100 | Time: 71 ms

**BM25 top 10**

1. [content_security_policy - Mozilla | MDN](https://developer.mozilla.org/en-US/docs/Mozilla/Add-ons/WebExtensions/manifest.json/content_security_policy) (id=5393, locale=en)
2. [Content-Security-Policy-Report-Only header - HTTP | MDN](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Content-Security-Policy-Report-Only) (id=4986, locale=en)
3. [Content-Security-Policy-Report-Only - HTTP | MDN](https://developer.mozilla.org/zh-CN/docs/Web/HTTP/Reference/Headers/Content-Security-Policy-Report-Only) (id=69937, locale=zh)
4. [Content Security Policy - Mozilla | MDN](https://developer.mozilla.org/en-US/docs/Mozilla/Add-ons/WebExtensions/Content_Security_Policy) (id=4707, locale=en)
5. [Content Security Policy - Mozilla | MDN](https://developer.mozilla.org/ja/docs/Mozilla/Add-ons/WebExtensions/Content_Security_Policy) (id=67856, locale=ja)
6. [Content Security Policy: The page's settings blocked the loading of a resource: xyz - HTTP | MDN](https://developer.mozilla.org/en-US/docs/Web/HTTP/Guides/CSP/Errors/CSPViolation) (id=70405, locale=en)
7. [content_security_policy - Mozilla | MDN](https://developer.mozilla.org/ja/docs/Mozilla/Add-ons/WebExtensions/manifest.json/content_security_policy) (id=71224, locale=ja)
8. [Content-Security-Policy-Report-Only ヘッダー - HTTP | MDN](https://developer.mozilla.org/ja/docs/Web/HTTP/Reference/Headers/Content-Security-Policy-Report-Only) (id=68615, locale=ja)
9. [Content-Security-Policy: report-uri ディレクティブ - HTTP | MDN](https://developer.mozilla.org/ja/docs/Web/HTTP/Reference/Headers/Content-Security-Policy/report-uri) (id=68780, locale=ja)
10. [Content-Security-Policy: report-uri directive - HTTP | MDN](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Content-Security-Policy/report-uri) (id=5726, locale=en)

**PostgreSQL top 10**

1. [Content-Security-Policy: report-uri directive - HTTP | MDN](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Content-Security-Policy/report-uri) (id=5726, locale=en)
2. [Content-Security-Policy - HTTP | MDN](https://developer.mozilla.org/es/docs/Web/HTTP/Reference/Headers/Content-Security-Policy) (id=67569, locale=es)
3. [Content-Security-Policy: report-uri-Direktive - HTTP | MDN](https://developer.mozilla.org/de/docs/Web/HTTP/Reference/Headers/Content-Security-Policy/report-uri) (id=69122, locale=de)
4. [Content-Security-Policy: report-uri ディレクティブ - HTTP | MDN](https://developer.mozilla.org/ja/docs/Web/HTTP/Reference/Headers/Content-Security-Policy/report-uri) (id=68780, locale=ja)
5. [Content-Security-Policy : directive report-uri - HTTP | MDN](https://developer.mozilla.org/fr/docs/Web/HTTP/Reference/Headers/Content-Security-Policy/report-uri) (id=69633, locale=fr)
6. [Content Security Policy - Mozilla | MDN](https://developer.mozilla.org/en-US/docs/Mozilla/Add-ons/WebExtensions/Content_Security_Policy) (id=4707, locale=en)
7. [Content Security Policy - Mozilla | MDN](https://developer.mozilla.org/de/docs/Mozilla/Add-ons/WebExtensions/Content_Security_Policy) (id=67870, locale=de)
8. [Content-Security-Policy-Report-Only header - HTTP | MDN](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Content-Security-Policy-Report-Only) (id=4986, locale=en)
9. [Content-Security-Policy-Report-Only header - HTTP | MDN](https://developer.mozilla.org/de/docs/Web/HTTP/Reference/Headers/Content-Security-Policy-Report-Only) (id=68918, locale=de)
10. [content_security_policy - Mozilla | MDN](https://developer.mozilla.org/en-US/docs/Mozilla/Add-ons/WebExtensions/manifest.json/content_security_policy) (id=5393, locale=en)

### Q067: CSS flexbox

Mode: `text` | Flags: `LOW_AGREEMENT, MULTILINGUAL_TOP, TARGET_BELOW_K` | Candidates: 100 | Time: 68 ms

**BM25 top 10**

1. [Flexbox - Glosario de MDN Web Docs | MDN](https://developer.mozilla.org/es/docs/Glossary/Flexbox) (id=10093, locale=es)
2. [Flexbox - Glossário do MDN Web Docs | MDN](https://developer.mozilla.org/pt-BR/docs/Glossary/Flexbox) (id=10199, locale=pt)
3. [CSS-Flexbox-Layout - CSS | MDN](https://developer.mozilla.org/de/docs/Web/CSS/Guides/Flexible_box_layout) (id=17310, locale=de)
4. [Flexbox - Glossary | MDN](https://developer.mozilla.org/en-US/docs/Glossary/Flexbox) (id=458, locale=en)
5. [Relationship of flexbox to other layout methods - CSS | MDN](https://developer.mozilla.org/en-US/docs/Web/CSS/Guides/Flexible_box_layout/Relationship_with_other_layout_methods) (id=2184, locale=en)
6. [CSS flexible box layout - CSS | MDN](https://developer.mozilla.org/en-US/docs/Web/CSS/Guides/Flexible_box_layout) (id=2077, locale=en)
7. [CSS 弹性盒子布局 - CSS：层叠样式表 | MDN](https://developer.mozilla.org/zh-CN/docs/Web/CSS/Guides/Flexible_box_layout) (id=15647, locale=zh)
8. [Flexbox - Glossaire | MDN](https://developer.mozilla.org/fr/docs/Glossary/Flexbox) (id=10135, locale=fr)
9. [Flexbox - Glossary | MDN](https://developer.mozilla.org/de/docs/Glossary/Flexbox) (id=10056, locale=de)
10. [Diseño de caja flexible CSS - CSS | MDN](https://developer.mozilla.org/es/docs/Web/CSS/Guides/Flexible_box_layout) (id=14332, locale=es)

**PostgreSQL top 10**

1. [CSS-Flexbox-Layout - CSS | MDN](https://developer.mozilla.org/de/docs/Web/CSS/Guides/Flexible_box_layout) (id=17310, locale=de)
2. [WebKit (-webkit-) vendor-prefixed CSS extensions - CSS | MDN](https://developer.mozilla.org/en-US/docs/Web/CSS/Reference/Webkit_extensions) (id=2051, locale=en)
3. [WebKit (-webkit-) vendor-spezifische CSS-Erweiterungen - CSS | MDN](https://developer.mozilla.org/de/docs/Web/CSS/Reference/Webkit_extensions) (id=17242, locale=de)
4. [Flexbox - Glossário do MDN Web Docs | MDN](https://developer.mozilla.org/pt-BR/docs/Glossary/Flexbox) (id=10199, locale=pt)
5. [Flexbox - Learn web development | MDN](https://developer.mozilla.org/en-US/docs/Learn_web_development/Core/CSS_layout/Flexbox) (id=6373, locale=en)
6. [Основные понятия Flexbox - CSS: каскадные таблицы стилей | MDN](https://developer.mozilla.org/ru/docs/Web/CSS/Guides/Flexible_box_layout/Basic_concepts) (id=2847, locale=ru)
7. [Casos de uso típicos de Flexbox - CSS | MDN](https://developer.mozilla.org/es/docs/Web/CSS/Guides/Flexible_box_layout/Use_cases) (id=14358, locale=es)
8. [Firefox (-moz-) vendor-prefixed CSS extensions - CSS | MDN](https://developer.mozilla.org/en-US/docs/Web/CSS/Reference/Mozilla_extensions) (id=2048, locale=en)
9. [Extensions CSS préfixées par le vendeur Firefox (-moz-) - CSS | MDN](https://developer.mozilla.org/fr/docs/Web/CSS/Reference/Mozilla_extensions) (id=15008, locale=fr)
10. [Firefox (-moz-) anbieterpräfixierte CSS-Erweiterungen - CSS | MDN](https://developer.mozilla.org/de/docs/Web/CSS/Reference/Mozilla_extensions) (id=17236, locale=de)

### Q068: CSS grid layout

Mode: `text` | Flags: `MULTILINGUAL_TOP` | Candidates: 100 | Time: 98 ms

**BM25 top 10**

1. [CSS grid layout - CSS | MDN](https://developer.mozilla.org/en-US/docs/Web/CSS/Guides/Grid_layout) (id=2082, locale=en)
2. [CSS Grid Layout - CSS | MDN](https://developer.mozilla.org/pt-BR/docs/Web/CSS/Guides/Grid_layout) (id=18066, locale=pt)
3. [CSS-Grid-Layout - CSS | MDN](https://developer.mozilla.org/de/docs/Web/CSS/Guides/Grid_layout) (id=17322, locale=de)
4. [Grid lanes layout - CSS | MDN](https://developer.mozilla.org/en-US/docs/Web/CSS/Guides/Grid_layout/Grid_lanes) (id=2208, locale=en)
5. [CSS Grid Layout - CSS | MDN](https://developer.mozilla.org/es/docs/Web/CSS/Guides/Grid_layout) (id=14316, locale=es)
6. [CSS Grid Layout - CSS: каскадные таблицы стилей | MDN](https://developer.mozilla.org/ru/docs/Web/CSS/Guides/Grid_layout) (id=18073, locale=ru)
7. [Grid layout and accessibility - CSS | MDN](https://developer.mozilla.org/en-US/docs/Web/CSS/Guides/Grid_layout/Accessibility) (id=2198, locale=en)
8. [Realizing common layouts using grids - CSS | MDN](https://developer.mozilla.org/en-US/docs/Web/CSS/Guides/Grid_layout/Common_grid_layouts) (id=2204, locale=en)
9. [网格布局 - CSS：层叠样式表 | MDN](https://developer.mozilla.org/zh-CN/docs/Web/CSS/Guides/Grid_layout) (id=15688, locale=zh)
10. [CSS 그리드 레이아웃 - CSS: Cascading Style Sheets | MDN](https://developer.mozilla.org/ko/docs/Web/CSS/Guides/Grid_layout) (id=18051, locale=ko)

**PostgreSQL top 10**

1. [CSS grid layout - CSS | MDN](https://developer.mozilla.org/en-US/docs/Web/CSS/Guides/Grid_layout) (id=2082, locale=en)
2. [CSS Grid Layout - CSS | MDN](https://developer.mozilla.org/es/docs/Web/CSS/Guides/Grid_layout) (id=14316, locale=es)
3. [CSS-Grid-Layout - CSS | MDN](https://developer.mozilla.org/de/docs/Web/CSS/Guides/Grid_layout) (id=17322, locale=de)
4. [CSS Grid Layout - CSS | MDN](https://developer.mozilla.org/pt-BR/docs/Web/CSS/Guides/Grid_layout) (id=18066, locale=pt)
5. [CSS Grid Layout - CSS: каскадные таблицы стилей | MDN](https://developer.mozilla.org/ru/docs/Web/CSS/Guides/Grid_layout) (id=18073, locale=ru)
6. [Aligning items in CSS grid layout - CSS | MDN](https://developer.mozilla.org/en-US/docs/Web/CSS/Guides/Grid_layout/Box_alignment) (id=2200, locale=en)
7. [Realizing common layouts using grids - CSS | MDN](https://developer.mozilla.org/en-US/docs/Web/CSS/Guides/Grid_layout/Common_grid_layouts) (id=2204, locale=en)
8. [CSS grid layout - Learn web development | MDN](https://developer.mozilla.org/en-US/docs/Learn_web_development/Core/CSS_layout/Grids) (id=6375, locale=en)
9. [Realisierung gängiger Layouts mit Grids - CSS | MDN](https://developer.mozilla.org/de/docs/Web/CSS/Guides/Grid_layout/Common_grid_layouts) (id=17396, locale=de)
10. [Basic concepts of grid layout - CSS | MDN](https://developer.mozilla.org/en-US/docs/Web/CSS/Guides/Grid_layout/Basic_concepts) (id=2722, locale=en)

### Q069: WebSocket API

Mode: `text` | Flags: `MULTILINGUAL_TOP` | Candidates: 100 | Time: 58 ms

**BM25 top 10**

1. [WebSocket API (WebSockets) - Web API | MDN](https://developer.mozilla.org/ja/docs/Web/API/WebSockets_API) (id=24315, locale=ja)
2. [WebSocket API (WebSocket) - Web API | MDN](https://developer.mozilla.org/zh-TW/docs/Web/API/WebSockets_API) (id=25878, locale=zh)
3. [WebSocket API - Web API | MDN](https://developer.mozilla.org/zh-CN/docs/Web/API/WebSockets_API) (id=26369, locale=zh)
4. [WebSocket API (WebSockets) - Web APIs | MDN](https://developer.mozilla.org/en-US/docs/Web/API/WebSockets_API) (id=3620, locale=en)
5. [WebSocket API (WebSockets) - Web-APIs | MDN](https://developer.mozilla.org/de/docs/Web/API/WebSockets_API) (id=24960, locale=de)
6. [API WebSocket (WebSockets) - Les API Web | MDN](https://developer.mozilla.org/fr/docs/Web/API/WebSockets_API) (id=23964, locale=fr)
7. [WebSocket - Web API | MDN](https://developer.mozilla.org/ja/docs/Web/API/WebSocket) (id=66819, locale=ja)
8. [WebSocket - Web API | MDN](https://developer.mozilla.org/zh-CN/docs/Web/API/WebSocket) (id=66930, locale=zh)
9. [协议升级机制 - HTTP | MDN](https://developer.mozilla.org/zh-CN/docs/Web/HTTP/Guides/Protocol_upgrade_mechanism) (id=69887, locale=zh)
10. [WebSockets - API web | MDN](https://developer.mozilla.org/es/docs/Web/API/WebSockets_API) (id=26023, locale=es)

**PostgreSQL top 10**

1. [WebSocket API (WebSockets) - Web API | MDN](https://developer.mozilla.org/ja/docs/Web/API/WebSockets_API) (id=24315, locale=ja)
2. [WebSocket API (WebSocket) - Web API | MDN](https://developer.mozilla.org/zh-TW/docs/Web/API/WebSockets_API) (id=25878, locale=zh)
3. [WebSocket API (WebSockets) - Web APIs | MDN](https://developer.mozilla.org/en-US/docs/Web/API/WebSockets_API) (id=3620, locale=en)
4. [WebSocket API (WebSockets) - Web-APIs | MDN](https://developer.mozilla.org/de/docs/Web/API/WebSockets_API) (id=24960, locale=de)
5. [API WebSocket (WebSockets) - Les API Web | MDN](https://developer.mozilla.org/fr/docs/Web/API/WebSockets_API) (id=23964, locale=fr)
6. [WebSocket API - Web API | MDN](https://developer.mozilla.org/zh-CN/docs/Web/API/WebSockets_API) (id=26369, locale=zh)
7. [WebSockets - API web | MDN](https://developer.mozilla.org/es/docs/Web/API/WebSockets_API) (id=26023, locale=es)
8. [WebSockets - APIs da Web | MDN](https://developer.mozilla.org/pt-BR/docs/Web/API/WebSockets_API) (id=25931, locale=pt)
9. [WebSocket - API web | MDN](https://developer.mozilla.org/es/docs/Web/API/WebSocket) (id=67048, locale=es)
10. [WebSockets - Интерфейсы веб API | MDN](https://developer.mozilla.org/ru/docs/Web/API/WebSockets_API) (id=26149, locale=ru)

### Q070: service worker fetch event

Mode: `all` | Flags: `LOW_AGREEMENT, MULTILINGUAL_TOP` | Candidates: 105 | Time: 227 ms

**BM25 top 10**

1. [使用 Service Worker - Web API | MDN](https://developer.mozilla.org/zh-CN/docs/Web/API/Service_Worker_API/Using_Service_Workers) (id=67288, locale=zh)
2. [Using Service Workers - Web APIs | MDN](https://developer.mozilla.org/en-US/docs/Web/API/Service_Worker_API/Using_Service_Workers) (id=4533, locale=en)
3. [Service Worker verwenden - Web-APIs | MDN](https://developer.mozilla.org/de/docs/Web/API/Service_Worker_API/Using_Service_Workers) (id=67227, locale=de)
4. [Использование Service Worker - Интерфейсы веб API | MDN](https://developer.mozilla.org/ru/docs/Web/API/Service_Worker_API/Using_Service_Workers) (id=67281, locale=ru)
5. [ServiceWorkerContainer: messageerror event - Web APIs | MDN](https://developer.mozilla.org/en-US/docs/Web/API/ServiceWorkerContainer/messageerror_event) (id=66520, locale=en)
6. [Uso de Service Workers - API web | MDN](https://developer.mozilla.org/es/docs/Web/API/Service_Worker_API/Using_Service_Workers) (id=67245, locale=es)
7. [Setting up service workers on Vultr | MDN Blog](https://developer.mozilla.org/en-US/blog/setting-up-service-workers-on-vultr/) (id=6706, locale=en)
8. [Utiliser les service workers - Les API Web | MDN](https://developer.mozilla.org/fr/docs/Web/API/Service_Worker_API/Using_Service_Workers) (id=67235, locale=fr)
9. [js13kGames: Making the PWA work offline with service workers - Progressive web apps | MDN](https://developer.mozilla.org/en-US/docs/Web/Progressive_web_apps/Tutorials/js13kGames/Offline_Service_workers) (id=6250, locale=en)
10. [Response: error() static method - Web APIs | MDN](https://developer.mozilla.org/en-US/docs/Web/API/Response/error_static) (id=63979, locale=en)

**PostgreSQL top 10**

1. [Caching - Progressive web apps | MDN](https://developer.mozilla.org/en-US/docs/Web/Progressive_web_apps/Guides/Caching) (id=4649, locale=en)
2. [InstallEvent: addRoutes() method - Web APIs | MDN](https://developer.mozilla.org/en-US/docs/Web/API/InstallEvent/addRoutes) (id=4536, locale=en)
3. [CycleTracker: Service workers - Progressive web apps | MDN](https://developer.mozilla.org/en-US/docs/Web/Progressive_web_apps/Tutorials/CycleTracker/Service_workers) (id=6249, locale=en)
4. [Using Service Workers - Web APIs | MDN](https://developer.mozilla.org/en-US/docs/Web/API/Service_Worker_API/Using_Service_Workers) (id=4533, locale=en)
5. [NavigationPreloadManager - Web APIs | MDN](https://developer.mozilla.org/en-US/docs/Web/API/NavigationPreloadManager) (id=4173, locale=en)
6. [ServiceWorkerGlobalScope: fetch event - Web APIs | MDN](https://developer.mozilla.org/en-US/docs/Web/API/ServiceWorkerGlobalScope/fetch_event) (id=4528, locale=en)
7. [InstallEvent: Methode addRoutes() - Web-APIs | MDN](https://developer.mozilla.org/de/docs/Web/API/InstallEvent/addRoutes) (id=67228, locale=de)
8. [FetchEvent - Web APIs | MDN](https://developer.mozilla.org/en-US/docs/Web/API/FetchEvent) (id=3893, locale=en)
9. [Offline and background operation - Progressive web apps | MDN](https://developer.mozilla.org/en-US/docs/Web/Progressive_web_apps/Guides/Offline_and_background_operation) (id=6060, locale=en)
10. [Request: isReloadNavigation property - Web APIs | MDN](https://developer.mozilla.org/en-US/docs/Web/API/Request/isReloadNavigation) (id=66052, locale=en)

### Q071: Rust ownership borrowing

Mode: `text` | Flags: `LOW_AGREEMENT, TARGET_NOT_IN_CANDIDATES` | Candidates: 53 | Time: 66 ms

**BM25 top 10**

1. [References and Borrowing - The Rust Programming Language](https://doc.rust-lang.org/book/ch04-02-references-and-borrowing.html) (id=31016, locale=en)
2. [ToOwned in std::borrow - Rust](https://doc.rust-lang.org/std/borrow/trait.ToOwned.html) (id=30016, locale=en)
3. [AsRawHandle in std::os::windows::io - Rust](https://doc.rust-lang.org/std/os/windows/io/trait.AsRawHandle.html) (id=29941, locale=en)
4. [std::boxed - Rust](https://doc.rust-lang.org/std/boxed/index.html) (id=28743, locale=en)
5. [raw.rs - source](https://doc.rust-lang.org/src/std/os/windows/io/raw.rs.html) (id=29736, locale=en)
6. [Closures - The Rust Programming Language](https://doc.rust-lang.org/book/ch13-01-closures.html) (id=28588, locale=en)
7. [dbg in std - Rust](https://doc.rust-lang.org/std/macro.dbg.html) (id=27674, locale=en)
8. [dbg in std - Rust](https://doc.rust-lang.org/stable/std/macro.dbg.html) (id=31389, locale=en)
9. [AsRawFd in std::os::fd - Rust](https://doc.rust-lang.org/std/os/fd/trait.AsRawFd.html) (id=29911, locale=en)
10. [std::io - Rust](https://doc.rust-lang.org/std/io/index.html) (id=28908, locale=en)

**PostgreSQL top 10**

1. [rc.rs - source](https://doc.rust-lang.org/src/alloc/rc.rs.html) (id=30355, locale=en)
2. [sync.rs - source](https://doc.rust-lang.org/src/alloc/sync.rs.html) (id=30365, locale=en)
3. [mod.rs - source](https://doc.rust-lang.org/src/alloc/vec/mod.rs.html) (id=30370, locale=en)
4. [References and Borrowing - The Rust Programming Language](https://doc.rust-lang.org/book/ch04-02-references-and-borrowing.html) (id=31016, locale=en)
5. [mod.rs - source](https://doc.rust-lang.org/src/std/os/unix/io/mod.rs.html) (id=29721, locale=en)
6. [mod.rs - source](https://doc.rust-lang.org/src/std/os/windows/io/mod.rs.html) (id=29731, locale=en)
7. [AsRawHandle in std::os::windows::io - Rust](https://doc.rust-lang.org/std/os/windows/io/trait.AsRawHandle.html) (id=29941, locale=en)
8. [Unions - The Rust Reference](https://doc.rust-lang.org/reference/items/unions.html) (id=27639, locale=en)
9. [Unions - The Rust Reference](https://doc.rust-lang.org/stable/reference/items/unions.html) (id=31359, locale=en)
10. [std::pin - Rust](https://doc.rust-lang.org/std/pin/index.html) (id=29392, locale=en)

### Q072: Rust lifetimes

Mode: `text` | Flags: `TARGET_NOT_IN_CANDIDATES` | Candidates: 100 | Time: 42 ms

**BM25 top 10**

1. [const - Rust](https://doc.rust-lang.org/std/keyword.const.html) (id=28947, locale=en)
2. [std::marker - Rust](https://doc.rust-lang.org/std/marker/index.html) (id=29327, locale=en)
3. [where - Rust](https://doc.rust-lang.org/std/keyword.where.html) (id=29107, locale=en)
4. [Trait object types - The Rust Reference](https://doc.rust-lang.org/reference/types/trait-object.html) (id=28322, locale=en)
5. [format_args in std - Rust](https://doc.rust-lang.org/std/macro.format_args.html) (id=29212, locale=en)
6. [Constant items - The Rust Reference](https://doc.rust-lang.org/reference/items/constant-items.html) (id=28253, locale=en)
7. [Subtyping and variance - The Rust Reference](https://doc.rust-lang.org/reference/subtyping.html) (id=28387, locale=en)
8. [Trait and lifetime bounds - The Rust Reference](https://doc.rust-lang.org/reference/trait-bounds.html) (id=27649, locale=en)
9. [Trait and lifetime bounds - The Rust Reference](https://doc.rust-lang.org/stable/reference/trait-bounds.html) (id=31369, locale=en)
10. [Functions - The Rust Reference](https://doc.rust-lang.org/reference/items/functions.html) (id=28096, locale=en)

**PostgreSQL top 10**

1. [Trait and lifetime bounds - The Rust Reference](https://doc.rust-lang.org/reference/trait-bounds.html) (id=27649, locale=en)
2. [Trait and lifetime bounds - The Rust Reference](https://doc.rust-lang.org/stable/reference/trait-bounds.html) (id=31369, locale=en)
3. [mod.rs - source](https://doc.rust-lang.org/src/alloc/vec/mod.rs.html) (id=30370, locale=en)
4. [SemVer Compatibility - The Cargo Book](https://doc.rust-lang.org/cargo/reference/semver.html) (id=27965, locale=en)
5. [Trait object types - The Rust Reference](https://doc.rust-lang.org/reference/types/trait-object.html) (id=28322, locale=en)
6. [std::cell - Rust](https://doc.rust-lang.org/std/cell/index.html) (id=28753, locale=en)
7. [cell.rs - source](https://doc.rust-lang.org/src/core/cell.rs.html) (id=30106, locale=en)
8. [format_args in std - Rust](https://doc.rust-lang.org/std/macro.format_args.html) (id=29212, locale=en)
9. [const - Rust](https://doc.rust-lang.org/std/keyword.const.html) (id=28947, locale=en)
10. [Static items - The Rust Reference](https://doc.rust-lang.org/reference/items/static-items.html) (id=28258, locale=en)

### Q073: Rust Result Option

Mode: `code` | Flags: `LOW_AGREEMENT` | Candidates: 100 | Time: 52 ms

**BM25 top 10**

1. [FromResidual in std::ops - Rust](https://doc.rust-lang.org/std/ops/trait.FromResidual.html) (id=30175, locale=en)
2. [StdioExt in std::os::windows::io - Rust](https://doc.rust-lang.org/std/os/windows/io/trait.StdioExt.html) (id=29946, locale=en)
3. [Residual in std::ops - Rust](https://doc.rust-lang.org/std/ops/trait.Residual.html) (id=30180, locale=en)
4. [Yeet in std::ops - Rust](https://doc.rust-lang.org/std/ops/struct.Yeet.html) (id=30155, locale=en)
5. [report_time - The Rust Unstable Book](https://doc.rust-lang.org/unstable-book/compiler-flags/report-time.html) (id=28460, locale=en)
6. [mod.rs - source](https://doc.rust-lang.org/src/std/prelude/mod.rs.html) (id=30215, locale=en)
7. [FromUtf16Error in std::string - Rust](https://doc.rust-lang.org/std/string/struct.FromUtf16Error.html) (id=30858, locale=en)
8. [Poll in std::task - Rust](https://doc.rust-lang.org/std/task/enum.Poll.html) (id=30799, locale=en)
9. [StrSearcher in std::str::pattern - Rust](https://doc.rust-lang.org/std/str/pattern/struct.StrSearcher.html) (id=30615, locale=en)
10. [std::async_iter - Rust](https://doc.rust-lang.org/std/async_iter/index.html) (id=28648, locale=en)

**PostgreSQL top 10**

1. [rc.rs - source](https://doc.rust-lang.org/src/alloc/rc.rs.html) (id=30355, locale=en)
2. [mod.rs - source](https://doc.rust-lang.org/src/core/slice/mod.rs.html) (id=31072, locale=en)
3. [path.rs - source](https://doc.rust-lang.org/src/std/path.rs.html) (id=30430, locale=en)
4. [mod.rs - source](https://doc.rust-lang.org/src/alloc/vec/mod.rs.html) (id=30370, locale=en)
5. [sync.rs - source](https://doc.rust-lang.org/src/alloc/sync.rs.html) (id=30365, locale=en)
6. [lib.rs - source](https://doc.rust-lang.org/src/std/lib.rs.html) (id=28613, locale=en)
7. [option.rs - source](https://doc.rust-lang.org/src/core/option.rs.html) (id=30116, locale=en)
8. [StdioExt in std::os::windows::io - Rust](https://doc.rust-lang.org/std/os/windows/io/trait.StdioExt.html) (id=29946, locale=en)
9. [IterMut in std::option - Rust](https://doc.rust-lang.org/std/option/struct.IterMut.html) (id=30200, locale=en)
10. [DoubleEndedIterator in std::iter - Rust](https://doc.rust-lang.org/std/iter/trait.DoubleEndedIterator.html) (id=30245, locale=en)

### Q078: Rust iterator map

Mode: `all` | Flags: `LOW_AGREEMENT` | Candidates: 117 | Time: 196 ms

**BM25 top 10**

1. [std::collections::hash_map - Rust](https://doc.rust-lang.org/std/collections/hash_map/index.html) (id=28494, locale=en)
2. [std::collections::btree_map - Rust](https://doc.rust-lang.org/std/collections/btree_map/index.html) (id=28479, locale=en)
3. [std::iter - Rust](https://doc.rust-lang.org/std/iter/index.html) (id=28553, locale=en)
4. [accum.rs - source](https://doc.rust-lang.org/src/core/iter/traits/accum.rs.html) (id=30111, locale=en)
5. [ExactSizeIterator in std::iter - Rust](https://doc.rust-lang.org/std/iter/trait.ExactSizeIterator.html) (id=30250, locale=en)
6. [mod.rs - source](https://doc.rust-lang.org/src/std/collections/mod.rs.html) (id=28469, locale=en)
7. [FromIterator in std::iter - Rust](https://doc.rust-lang.org/std/iter/trait.FromIterator.html) (id=30135, locale=en)
8. [std::collections - Rust](https://doc.rust-lang.org/std/collections/index.html) (id=27659, locale=en)
9. [std::collections - Rust](https://doc.rust-lang.org/stable/std/collections/index.html) (id=31374, locale=en)
10. [Default in std::default - Rust](https://doc.rust-lang.org/std/default/trait.Default.html) (id=30130, locale=en)

**PostgreSQL top 10**

1. [mod.rs - source](https://doc.rust-lang.org/src/alloc/vec/mod.rs.html) (id=30370, locale=en)
2. [rc.rs - source](https://doc.rust-lang.org/src/alloc/rc.rs.html) (id=30355, locale=en)
3. [mod.rs - source](https://doc.rust-lang.org/src/core/slice/mod.rs.html) (id=31072, locale=en)
4. [path.rs - source](https://doc.rust-lang.org/src/std/path.rs.html) (id=30430, locale=en)
5. [sync.rs - source](https://doc.rust-lang.org/src/alloc/sync.rs.html) (id=30365, locale=en)
6. [collect.rs - source](https://doc.rust-lang.org/src/core/iter/traits/collect.rs.html) (id=30390, locale=en)
7. [mod.rs - source](https://doc.rust-lang.org/src/core/convert/mod.rs.html) (id=29701, locale=en)
8. [std::collections - Rust](https://doc.rust-lang.org/std/collections/index.html) (id=27659, locale=en)
9. [std::collections - Rust](https://doc.rust-lang.org/stable/std/collections/index.html) (id=31374, locale=en)
10. [DoubleEndedIterator in std::iter - Rust](https://doc.rust-lang.org/std/iter/trait.DoubleEndedIterator.html) (id=30245, locale=en)

### Q079: Rust pattern matching

Mode: `text` | Flags: `TARGET_BELOW_K` | Candidates: 97 | Time: 122 ms

**BM25 top 10**

1. [let - Rust](https://doc.rust-lang.org/std/keyword.let.html) (id=29012, locale=en)
2. [matches in std - Rust](https://doc.rust-lang.org/std/macro.matches.html) (id=29252, locale=en)
3. [ref - Rust](https://doc.rust-lang.org/std/keyword.ref.html) (id=29047, locale=en)
4. [Macros - The Rust Programming Language](https://doc.rust-lang.org/book/ch20-05-macros.html) (id=27776, locale=en)
5. [assert_matches in std - Rust](https://doc.rust-lang.org/std/macro.assert_matches.html) (id=29127, locale=en)
6. [match - Rust](https://doc.rust-lang.org/std/keyword.match.html) (id=29022, locale=en)
7. [debug_assert_matches in std - Rust](https://doc.rust-lang.org/std/macro.debug_assert_matches.html) (id=29177, locale=en)
8. [union - Rust](https://doc.rust-lang.org/std/keyword.union.html) (id=29092, locale=en)
9. [if - Rust](https://doc.rust-lang.org/std/keyword.if.html) (id=28997, locale=en)
10. [while - Rust](https://doc.rust-lang.org/std/keyword.while.html) (id=29112, locale=en)

**PostgreSQL top 10**

1. [Macros - The Rust Programming Language](https://doc.rust-lang.org/book/ch20-05-macros.html) (id=27776, locale=en)
2. [mod.rs - source](https://doc.rust-lang.org/src/core/slice/mod.rs.html) (id=31072, locale=en)
3. [4. More Control Flow Tools](https://docs.python.org/3/tutorial/controlflow.html) (id=7995, locale=en)
4. [match - Rust](https://doc.rust-lang.org/std/keyword.match.html) (id=29022, locale=en)
5. [let - Rust](https://doc.rust-lang.org/std/keyword.let.html) (id=29012, locale=en)
6. [ref - Rust](https://doc.rust-lang.org/std/keyword.ref.html) (id=29047, locale=en)
7. [ReverseSearcher in std::str::pattern - Rust](https://doc.rust-lang.org/std/str/pattern/trait.ReverseSearcher.html) (id=30630, locale=en)
8. [Unions - The Rust Reference](https://doc.rust-lang.org/reference/items/unions.html) (id=27639, locale=en)
9. [Unions - The Rust Reference](https://doc.rust-lang.org/stable/reference/items/unions.html) (id=31359, locale=en)
10. [assert_matches in std - Rust](https://doc.rust-lang.org/std/macro.assert_matches.html) (id=29127, locale=en)

### Q080: Rust cargo workspace

Mode: `text` | Flags: `TARGET_NOT_IN_CANDIDATES` | Candidates: 17 | Time: 14 ms

**BM25 top 10**

1. [Appendix: Glossary - The Cargo Book](https://doc.rust-lang.org/cargo/appendix/glossary.html) (id=27795, locale=en)
2. [Environment Variables - The Cargo Book](https://doc.rust-lang.org/cargo/reference/environment-variables.html) (id=27877, locale=en)
3. [The Manifest Format - The Cargo Book](https://doc.rust-lang.org/cargo/reference/manifest.html) (id=27891, locale=en)
4. [cargo bench - The Cargo Book](https://doc.rust-lang.org/cargo/commands/cargo-bench.html) (id=27826, locale=en)
5. [cargo test - The Cargo Book](https://doc.rust-lang.org/cargo/commands/cargo-test.html) (id=27857, locale=en)
6. [cargo check - The Cargo Book](https://doc.rust-lang.org/cargo/commands/cargo-check.html) (id=27837, locale=en)
7. [cargo build - The Cargo Book](https://doc.rust-lang.org/cargo/commands/cargo-build.html) (id=27832, locale=en)
8. [Unstable Features - The Cargo Book](https://doc.rust-lang.org/cargo/reference/unstable.html) (id=27901, locale=en)
9. [Cargo Reference - The Cargo Book](https://doc.rust-lang.org/cargo/reference/index.html) (id=27822, locale=en)
10. [Configuration - The Cargo Book](https://doc.rust-lang.org/cargo/reference/config.html) (id=27872, locale=en)

**PostgreSQL top 10**

1. [Changelog - The Cargo Book](https://doc.rust-lang.org/cargo/CHANGELOG.html) (id=27785, locale=en)
2. [Cargo Reference - The Cargo Book](https://doc.rust-lang.org/cargo/reference/index.html) (id=27822, locale=en)
3. [Continuous Integration - The Cargo Book](https://doc.rust-lang.org/cargo/guide/continuous-integration.html) (id=27960, locale=en)
4. [Unstable Features - The Cargo Book](https://doc.rust-lang.org/cargo/reference/unstable.html) (id=27901, locale=en)
5. [The Manifest Format - The Cargo Book](https://doc.rust-lang.org/cargo/reference/manifest.html) (id=27891, locale=en)
6. [Appendix: Glossary - The Cargo Book](https://doc.rust-lang.org/cargo/appendix/glossary.html) (id=27795, locale=en)
7. [cargo test - The Cargo Book](https://doc.rust-lang.org/cargo/commands/cargo-test.html) (id=27857, locale=en)
8. [cargo bench - The Cargo Book](https://doc.rust-lang.org/cargo/commands/cargo-bench.html) (id=27826, locale=en)
9. [Configuration - The Cargo Book](https://doc.rust-lang.org/cargo/reference/config.html) (id=27872, locale=en)
10. [Environment Variables - The Cargo Book](https://doc.rust-lang.org/cargo/reference/environment-variables.html) (id=27877, locale=en)

### Q081: __init__

Mode: `code` | Flags: `MULTILINGUAL_TOP` | Candidates: 100 | Time: 139 ms

**BM25 top 10**

1. [dataclasses — Data Classes](https://docs.python.org/3/library/dataclasses.html) (id=7709, locale=en)
2. [MaybeUninit in std::mem - Rust](https://doc.rust-lang.org/std/mem/union.MaybeUninit.html) (id=31125, locale=en)
3. [django.db.models.functions.base | Εγχειρίδιο Django](https://docs.djangoproject.com/el/6.1/_modules/django/db/models/functions/base/) (id=29421, locale=el)
4. [2. Defining Extension Types: Tutorial](https://docs.python.org/3/extending/newtypes_tutorial.html) (id=8103, locale=en)
5. [Custom Response Classes - File, HTML, Redirect, Streaming, etc. - FastAPI](https://fastapi.tiangolo.com/reference/responses/) (id=27973, locale=en)
6. [Custom Response Classes - File, HTML, Redirect, Streaming, etc. - FastAPI](https://fastapi.tiangolo.com/de/reference/responses/) (id=28746, locale=de)
7. [Custom Response Classes - File, HTML, Redirect, Streaming, etc. - FastAPI](https://fastapi.tiangolo.com/es/reference/responses/) (id=29506, locale=es)
8. [Custom Response Classes - File, HTML, Redirect, Streaming, etc. - FastAPI](https://fastapi.tiangolo.com/fr/reference/responses/) (id=30264, locale=fr)
9. [Custom Response Classes - File, HTML, Redirect, Streaming, etc. - FastAPI](https://fastapi.tiangolo.com/hi/reference/responses/) (id=31019, locale=hi)
10. [Custom Response Classes - File, HTML, Redirect, Streaming, etc. - FastAPI](https://fastapi.tiangolo.com/ja/reference/responses/) (id=31699, locale=ja)

**PostgreSQL top 10**

1. [MaybeUninit in std::mem - Rust](https://doc.rust-lang.org/std/mem/union.MaybeUninit.html) (id=31125, locale=en)
2. [Custom Response Classes - File, HTML, Redirect, Streaming, etc. - FastAPI](https://fastapi.tiangolo.com/reference/responses/) (id=27973, locale=en)
3. [Custom Response Classes - File, HTML, Redirect, Streaming, etc. - FastAPI](https://fastapi.tiangolo.com/de/reference/responses/) (id=28746, locale=de)
4. [Custom Response Classes - File, HTML, Redirect, Streaming, etc. - FastAPI](https://fastapi.tiangolo.com/es/reference/responses/) (id=29506, locale=es)
5. [Custom Response Classes - File, HTML, Redirect, Streaming, etc. - FastAPI](https://fastapi.tiangolo.com/fr/reference/responses/) (id=30264, locale=fr)
6. [Custom Response Classes - File, HTML, Redirect, Streaming, etc. - FastAPI](https://fastapi.tiangolo.com/hi/reference/responses/) (id=31019, locale=hi)
7. [Custom Response Classes - File, HTML, Redirect, Streaming, etc. - FastAPI](https://fastapi.tiangolo.com/ja/reference/responses/) (id=31699, locale=ja)
8. [Custom Response Classes - File, HTML, Redirect, Streaming, etc. - FastAPI](https://fastapi.tiangolo.com/ko/reference/responses/) (id=32306, locale=ko)
9. [Custom Response Classes - File, HTML, Redirect, Streaming, etc. - FastAPI](https://fastapi.tiangolo.com/pt/reference/responses/) (id=32911, locale=pt)
10. [Custom Response Classes - File, HTML, Redirect, Streaming, etc. - FastAPI](https://fastapi.tiangolo.com/ru/reference/responses/) (id=33519, locale=ru)

### Q082: get_user_by_id

Mode: `code` | Flags: `ZERO_RESULTS` | Candidates: 0 | Time: 5 ms

### Q083: useEffect

Mode: `code` | Flags: `THIN_POOL` | Candidates: 2 | Time: 3 ms

**BM25 top 10**

1. [Accessibility in React - Learn web development | MDN](https://developer.mozilla.org/en-US/docs/Learn_web_development/Core/Frameworks_libraries/React_accessibility) (id=6425, locale=en)
2. [Accessibility in React - Web 개발 학습하기 | MDN](https://developer.mozilla.org/ko/docs/Learn_web_development/Core/Frameworks_libraries/React_accessibility) (id=11865, locale=ko)

**PostgreSQL top 10**

1. [Accessibility in React - Learn web development | MDN](https://developer.mozilla.org/en-US/docs/Learn_web_development/Core/Frameworks_libraries/React_accessibility) (id=6425, locale=en)
2. [Accessibility in React - Web 개발 학습하기 | MDN](https://developer.mozilla.org/ko/docs/Learn_web_development/Core/Frameworks_libraries/React_accessibility) (id=11865, locale=ko)

### Q084: __enter__

Mode: `code` | Flags: `LOW_AGREEMENT, MULTILINGUAL_TOP` | Candidates: 100 | Time: 78 ms

**BM25 top 10**

1. [The HTML5 input types - Learn web development | MDN](https://developer.mozilla.org/en-US/docs/Learn_web_development/Extensions/Forms/HTML5_input_types) (id=6453, locale=en)
2. [TextTrackCue: enter event - Web APIs | MDN](https://developer.mozilla.org/en-US/docs/Web/API/TextTrackCue/enter_event) (id=62954, locale=en)
3. [DocumentPictureInPicture: enter event - Web APIs | MDN](https://developer.mozilla.org/en-US/docs/Web/API/DocumentPictureInPicture/enter_event) (id=26881, locale=en)
4. [ARIA: textbox role - ARIA | MDN](https://developer.mozilla.org/de/docs/Web/Accessibility/ARIA/Reference/Roles/textbox_role) (id=68252, locale=de)
5. [ARIA: textbox role - ARIA | MDN](https://developer.mozilla.org/en-US/docs/Web/Accessibility/ARIA/Reference/Roles/textbox_role) (id=4882, locale=en)
6. [ARIA: button ロール - ARIA | MDN](https://developer.mozilla.org/ja/docs/Web/Accessibility/ARIA/Reference/Roles/button_role) (id=68010, locale=ja)
7. [ARIA：button 角色 - ARIA | MDN](https://developer.mozilla.org/zh-CN/docs/Web/Accessibility/ARIA/Reference/Roles/button_role) (id=68515, locale=zh)
8. [Fullscreen API - Web APIs | MDN](https://developer.mozilla.org/en-US/docs/Web/API/Fullscreen_API) (id=3540, locale=en)
9. [<input> HTML input element - HTML | MDN](https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Elements/input) (id=229, locale=en)
10. [Das HTML-Element <input> - HTML | MDN](https://developer.mozilla.org/de/docs/Web/HTML/Reference/Elements/input) (id=8254, locale=de)

**PostgreSQL top 10**

1. [django.forms.fields | Εγχειρίδιο Django](https://docs.djangoproject.com/el/6.1/_modules/django/forms/fields/) (id=29486, locale=el)
2. [django.forms.fields | Django documentation](https://docs.djangoproject.com/en/6.1/_modules/django/forms/fields/) (id=40919, locale=en)
3. [django.forms.fields | Documentación de Django](https://docs.djangoproject.com/es/6.1/_modules/django/forms/fields/) (id=40922, locale=es)
4. [django.forms.fields | Documentation de Django](https://docs.djangoproject.com/fr/6.1/_modules/django/forms/fields/) (id=40925, locale=fr)
5. [django.forms.fields | Dokumentasi Django](https://docs.djangoproject.com/id/6.1/_modules/django/forms/fields/) (id=40928, locale=id)
6. [django.forms.fields | Django ドキュメント](https://docs.djangoproject.com/ja/6.1/_modules/django/forms/fields/) (id=40931, locale=ja)
7. [django.forms.fields | Django 문서](https://docs.djangoproject.com/ko/6.1/_modules/django/forms/fields/) (id=40934, locale=ko)
8. [django.forms.fields | Dokumentacja Django](https://docs.djangoproject.com/pl/6.1/_modules/django/forms/fields/) (id=40937, locale=pl)
9. [django.forms.fields | Documentação do Django](https://docs.djangoproject.com/pt-br/6.1/_modules/django/forms/fields/) (id=40940, locale=pt)
10. [django.forms.fields | Django 文档](https://docs.djangoproject.com/zh-hans/6.1/_modules/django/forms/fields/) (id=40942, locale=zh)

### Q086: HTTPException

Mode: `code` | Flags: `LOW_AGREEMENT, MULTILINGUAL_TOP` | Candidates: 100 | Time: 38 ms

**BM25 top 10**

1. [路徑操作裝飾器中的依賴 - FastAPI](https://fastapi.tiangolo.com/zh-hant/tutorial/dependencies/dependencies-in-path-operation-decorators/) (id=35363, locale=zh)
2. [路径操作装饰器依赖项 - FastAPI](https://fastapi.tiangolo.com/zh/tutorial/dependencies/dependencies-in-path-operation-decorators/) (id=35947, locale=zh)
3. [path operation デコレータの依存関係 - FastAPI](https://fastapi.tiangolo.com/ja/tutorial/dependencies/dependencies-in-path-operation-decorators/) (id=31801, locale=ja)
4. [Abhängigkeiten in Pfadoperation-Dekoratoren - FastAPI](https://fastapi.tiangolo.com/de/tutorial/dependencies/dependencies-in-path-operation-decorators/) (id=28876, locale=de)
5. [경로 처리 데코레이터에서의 의존성 - FastAPI](https://fastapi.tiangolo.com/ko/tutorial/dependencies/dependencies-in-path-operation-decorators/) (id=32409, locale=ko)
6. [Залежності в декораторах операцій шляху - FastAPI](https://fastapi.tiangolo.com/uk/tutorial/dependencies/dependencies-in-path-operation-decorators/) (id=34788, locale=uk)
7. [Dependencies in path operation decorators - FastAPI](https://fastapi.tiangolo.com/tutorial/dependencies/dependencies-in-path-operation-decorators/) (id=28109, locale=en)
8. [path operation decorators में Dependencies - FastAPI](https://fastapi.tiangolo.com/hi/tutorial/dependencies/dependencies-in-path-operation-decorators/) (id=31146, locale=hi)
9. [Зависимости в декораторах операции пути - FastAPI](https://fastapi.tiangolo.com/ru/tutorial/dependencies/dependencies-in-path-operation-decorators/) (id=33617, locale=ru)
10. [Path Operation Decorator'lerinde Dependency'ler - FastAPI](https://fastapi.tiangolo.com/tr/tutorial/dependencies/dependencies-in-path-operation-decorators/) (id=34200, locale=tr)

**PostgreSQL top 10**

1. [OAuth2 scopes - FastAPI](https://fastapi.tiangolo.com/advanced/security/oauth2-scopes/) (id=27633, locale=en)
2. [OAuth2-Scopes - FastAPI](https://fastapi.tiangolo.com/de/advanced/security/oauth2-scopes/) (id=28429, locale=de)
3. [Scopes de OAuth2 - FastAPI](https://fastapi.tiangolo.com/es/advanced/security/oauth2-scopes/) (id=29185, locale=es)
4. [Scopes OAuth2 - FastAPI](https://fastapi.tiangolo.com/fr/advanced/security/oauth2-scopes/) (id=29945, locale=fr)
5. [OAuth2 scopes - FastAPI](https://fastapi.tiangolo.com/hi/advanced/security/oauth2-scopes/) (id=30703, locale=hi)
6. [OAuth2 のスコープ - FastAPI](https://fastapi.tiangolo.com/ja/advanced/security/oauth2-scopes/) (id=31442, locale=ja)
7. [OAuth2 스코프 - FastAPI](https://fastapi.tiangolo.com/ko/advanced/security/oauth2-scopes/) (id=32050, locale=ko)
8. [Escopos OAuth2 - FastAPI](https://fastapi.tiangolo.com/pt/advanced/security/oauth2-scopes/) (id=32655, locale=pt)
9. [OAuth2 scopes - FastAPI](https://fastapi.tiangolo.com/ru/advanced/security/oauth2-scopes/) (id=33268, locale=ru)
10. [OAuth2 scope'ları - FastAPI](https://fastapi.tiangolo.com/tr/advanced/security/oauth2-scopes/) (id=33856, locale=tr)

### Q087: select_related

Mode: `code` | Flags: `MULTILINGUAL_TOP` | Candidates: 44 | Time: 66 ms

**BM25 top 10**

1. [QuerySet API reference | Django documentation](https://docs.djangoproject.com/en/6.1/ref/models/querysets/) (id=28041, locale=en)
2. [QuerySet API 参考 | Django 文档](https://docs.djangoproject.com/zh-hans/6.1/ref/models/querysets/) (id=64097, locale=zh)
3. [QuerySet API リファレンス | Django ドキュメント](https://docs.djangoproject.com/ja/6.1/ref/models/querysets/) (id=64092, locale=ja)
4. [aPI-referens för QuerySet | Django-dokumentation](https://docs.djangoproject.com/sv/6.1/ref/models/querysets/) (id=64096, locale=sv)
5. [Référence de l’API QuerySet | Documentation de Django](https://docs.djangoproject.com/fr/6.1/ref/models/querysets/) (id=64090, locale=fr)
6. [django.db.models.query | Εγχειρίδιο Django](https://docs.djangoproject.com/el/6.1/_modules/django/db/models/query/) (id=29456, locale=el)
7. [django.db.models.query | Django ドキュメント](https://docs.djangoproject.com/ja/6.1/_modules/django/db/models/query/) (id=40731, locale=ja)
8. [django.db.models.query | Dokumentasi Django](https://docs.djangoproject.com/id/6.1/_modules/django/db/models/query/) (id=40728, locale=id)
9. [django.db.models.query | Django 문서](https://docs.djangoproject.com/ko/6.1/_modules/django/db/models/query/) (id=40734, locale=ko)
10. [django.db.models.query | Dokumentacja Django](https://docs.djangoproject.com/pl/6.1/_modules/django/db/models/query/) (id=40737, locale=pl)

**PostgreSQL top 10**

1. [django.db.models.query | Εγχειρίδιο Django](https://docs.djangoproject.com/el/6.1/_modules/django/db/models/query/) (id=29456, locale=el)
2. [django.db.models.query | Django documentation](https://docs.djangoproject.com/en/6.1/_modules/django/db/models/query/) (id=40719, locale=en)
3. [django.db.models.query | Documentación de Django](https://docs.djangoproject.com/es/6.1/_modules/django/db/models/query/) (id=40722, locale=es)
4. [django.db.models.query | Documentation de Django](https://docs.djangoproject.com/fr/6.1/_modules/django/db/models/query/) (id=40725, locale=fr)
5. [django.db.models.query | Dokumentasi Django](https://docs.djangoproject.com/id/6.1/_modules/django/db/models/query/) (id=40728, locale=id)
6. [django.db.models.query | Django ドキュメント](https://docs.djangoproject.com/ja/6.1/_modules/django/db/models/query/) (id=40731, locale=ja)
7. [django.db.models.query | Django 문서](https://docs.djangoproject.com/ko/6.1/_modules/django/db/models/query/) (id=40734, locale=ko)
8. [django.db.models.query | Dokumentacja Django](https://docs.djangoproject.com/pl/6.1/_modules/django/db/models/query/) (id=40737, locale=pl)
9. [django.db.models.query | Documentação do Django](https://docs.djangoproject.com/pt-br/6.1/_modules/django/db/models/query/) (id=40740, locale=pt)
10. [django.db.models.query | Django 文档](https://docs.djangoproject.com/zh-hans/6.1/_modules/django/db/models/query/) (id=40743, locale=zh)

### Q088: requestAnimationFrame

Mode: `code` | Flags: `MULTILINGUAL_TOP` | Candidates: 100 | Time: 33 ms

**BM25 top 10**

1. [Window：requestAnimationFrame() 方法 - Web API | MDN](https://developer.mozilla.org/zh-CN/docs/Web/API/Window/requestAnimationFrame) (id=67353, locale=zh)
2. [Window: requestAnimationFrame() メソッド - Web API | MDN](https://developer.mozilla.org/ja/docs/Web/API/Window/requestAnimationFrame) (id=67349, locale=ja)
3. [Window: requestAnimationFrame() 메서드 - Web API | MDN](https://developer.mozilla.org/ko/docs/Web/API/Window/requestAnimationFrame) (id=67346, locale=ko)
4. [Window: requestAnimationFrame() method - Web APIs | MDN](https://developer.mozilla.org/en-US/docs/Web/API/Window/requestAnimationFrame) (id=4542, locale=en)
5. [Window: requestAnimationFrame() Methode - Web-APIs | MDN](https://developer.mozilla.org/de/docs/Web/API/Window/requestAnimationFrame) (id=67320, locale=de)
6. [Window : méthode requestAnimationFrame() - Les API Web | MDN](https://developer.mozilla.org/fr/docs/Web/API/Window/requestAnimationFrame) (id=67345, locale=fr)
7. [Window: cancelAnimationFrame() method - Web APIs | MDN](https://developer.mozilla.org/en-US/docs/Web/API/Window/cancelAnimationFrame) (id=20128, locale=en)
8. [Производительность CSS и JavaScript анимации - Web Performance | MDN](https://developer.mozilla.org/ru/docs/Web/Performance/Guides/CSS_JavaScript_animation_performance) (id=72589, locale=ru)
9. [Window.requestAnimationFrame() - API web | MDN](https://developer.mozilla.org/es/docs/Web/API/Window/requestAnimationFrame) (id=67298, locale=es)
10. [DedicatedWorkerGlobalScope: requestAnimationFrame() method - Web APIs | MDN](https://developer.mozilla.org/en-US/docs/Web/API/DedicatedWorkerGlobalScope/requestAnimationFrame) (id=63001, locale=en)

**PostgreSQL top 10**

1. [Window: requestAnimationFrame() method - Web APIs | MDN](https://developer.mozilla.org/en-US/docs/Web/API/Window/requestAnimationFrame) (id=4542, locale=en)
2. [Window: requestAnimationFrame() Methode - Web-APIs | MDN](https://developer.mozilla.org/de/docs/Web/API/Window/requestAnimationFrame) (id=67320, locale=de)
3. [Window : méthode requestAnimationFrame() - Les API Web | MDN](https://developer.mozilla.org/fr/docs/Web/API/Window/requestAnimationFrame) (id=67345, locale=fr)
4. [Window: requestAnimationFrame() 메서드 - Web API | MDN](https://developer.mozilla.org/ko/docs/Web/API/Window/requestAnimationFrame) (id=67346, locale=ko)
5. [Window: requestAnimationFrame() メソッド - Web API | MDN](https://developer.mozilla.org/ja/docs/Web/API/Window/requestAnimationFrame) (id=67349, locale=ja)
6. [Window：requestAnimationFrame() 方法 - Web API | MDN](https://developer.mozilla.org/zh-CN/docs/Web/API/Window/requestAnimationFrame) (id=67353, locale=zh)
7. [VRDisplay: requestAnimationFrame() method - Web APIs | MDN](https://developer.mozilla.org/en-US/docs/Web/API/VRDisplay/requestAnimationFrame) (id=27345, locale=en)
8. [DedicatedWorkerGlobalScope: requestAnimationFrame() method - Web APIs | MDN](https://developer.mozilla.org/en-US/docs/Web/API/DedicatedWorkerGlobalScope/requestAnimationFrame) (id=63001, locale=en)
9. [Drawing graphics - Learn web development | MDN](https://developer.mozilla.org/en-US/docs/Learn_web_development/Extensions/Client-side_APIs/Drawing_graphics) (id=2844, locale=en)
10. [WebGL model view projection - Web APIs | MDN](https://developer.mozilla.org/en-US/docs/Web/API/WebGL_API/WebGL_model_view_projection) (id=10353, locale=en)

### Q089: fetch()

Mode: `code` | Flags: `MULTILINGUAL_TOP` | Candidates: 100 | Time: 49 ms

**BM25 top 10**

1. [Sec-Fetch-Dest header - HTTP | MDN](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Sec-Fetch-Dest) (id=5065, locale=en)
2. [Sec-Fetch-Dest header - HTTP | MDN](https://developer.mozilla.org/de/docs/Web/HTTP/Reference/Headers/Sec-Fetch-Dest) (id=68995, locale=de)
3. [Sec-Fetch-Dest ヘッダー - HTTP | MDN](https://developer.mozilla.org/ja/docs/Web/HTTP/Reference/Headers/Sec-Fetch-Dest) (id=68673, locale=ja)
4. [En-tête Sec-Fetch-Dest - HTTP | MDN](https://developer.mozilla.org/fr/docs/Web/HTTP/Reference/Headers/Sec-Fetch-Dest) (id=69500, locale=fr)
5. [Sec-Fetch-Dest - HTTP | MDN](https://developer.mozilla.org/zh-CN/docs/Web/HTTP/Reference/Headers/Sec-Fetch-Dest) (id=69979, locale=zh)
6. [Sec-Fetch-Mode ヘッダー - HTTP | MDN](https://developer.mozilla.org/ja/docs/Web/HTTP/Reference/Headers/Sec-Fetch-Mode) (id=68676, locale=ja)
7. [Sec-Fetch-Mode header - HTTP | MDN](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Sec-Fetch-Mode) (id=5057, locale=en)
8. [Sec-Fetch-Mode header - HTTP | MDN](https://developer.mozilla.org/de/docs/Web/HTTP/Reference/Headers/Sec-Fetch-Mode) (id=68991, locale=de)
9. [En-tête Sec-Fetch-Mode - HTTP | MDN](https://developer.mozilla.org/fr/docs/Web/HTTP/Reference/Headers/Sec-Fetch-Mode) (id=69503, locale=fr)
10. [Sec-Fetch-Site ヘッダー - HTTP | MDN](https://developer.mozilla.org/ja/docs/Web/HTTP/Reference/Headers/Sec-Fetch-Site) (id=68671, locale=ja)

**PostgreSQL top 10**

1. [Atomic in std::sync::atomic - Rust](https://doc.rust-lang.org/std/sync/atomic/struct.Atomic.html) (id=30913, locale=en)
2. [Using the Fetch API - Web APIs | MDN](https://developer.mozilla.org/en-US/docs/Web/API/Fetch_API/Using_Fetch) (id=51, locale=en)
3. [Verwenden der Fetch API - Web-APIs | MDN](https://developer.mozilla.org/de/docs/Web/API/Fetch_API/Using_Fetch) (id=4594, locale=de)
4. [Sec-Fetch-Dest header - HTTP | MDN](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Sec-Fetch-Dest) (id=5065, locale=en)
5. [Sec-Fetch-Dest header - HTTP | MDN](https://developer.mozilla.org/de/docs/Web/HTTP/Reference/Headers/Sec-Fetch-Dest) (id=68995, locale=de)
6. [En-tête Sec-Fetch-Dest - HTTP | MDN](https://developer.mozilla.org/fr/docs/Web/HTTP/Reference/Headers/Sec-Fetch-Dest) (id=69500, locale=fr)
7. [Utiliser l'API Fetch - Les API Web | MDN](https://developer.mozilla.org/fr/docs/Web/API/Fetch_API/Using_Fetch) (id=4598, locale=fr)
8. [Sec-Fetch-Dest ヘッダー - HTTP | MDN](https://developer.mozilla.org/ja/docs/Web/HTTP/Reference/Headers/Sec-Fetch-Dest) (id=68673, locale=ja)
9. [使用 Fetch API - Web API | MDN](https://developer.mozilla.org/zh-TW/docs/Web/API/Fetch_API/Using_Fetch) (id=4607, locale=zh)
10. [Sec-Fetch-Dest - HTTP | MDN](https://developer.mozilla.org/zh-CN/docs/Web/HTTP/Reference/Headers/Sec-Fetch-Dest) (id=69979, locale=zh)

### Q090: QuerySet

Mode: `code` | Flags: `LOW_AGREEMENT, MULTILINGUAL_TOP` | Candidates: 100 | Time: 109 ms

**BM25 top 10**

1. [Many-to-many relationships | Django documentation](https://docs.djangoproject.com/en/6.1/topics/db/examples/many_to_many/) (id=65102, locale=en)
2. [PostgreSQL specific model fields | Django documentation](https://docs.djangoproject.com/en/6.1/ref/contrib/postgres/fields/) (id=62503, locale=en)
3. [django.db.models.manager | Django ドキュメント](https://docs.djangoproject.com/ja/6.1/_modules/django/db/models/manager/) (id=40665, locale=ja)
4. [django.db.models.manager | Django documentation](https://docs.djangoproject.com/en/6.1/_modules/django/db/models/manager/) (id=40653, locale=en)
5. [django.db.models.manager | Dokumentasi Django](https://docs.djangoproject.com/id/6.1/_modules/django/db/models/manager/) (id=40662, locale=id)
6. [django.db.models.manager | Django 문서](https://docs.djangoproject.com/ko/6.1/_modules/django/db/models/manager/) (id=40668, locale=ko)
7. [django.db.models.manager | Dokumentacja Django](https://docs.djangoproject.com/pl/6.1/_modules/django/db/models/manager/) (id=40671, locale=pl)
8. [django.db.models.manager | Django 文档](https://docs.djangoproject.com/zh-hans/6.1/_modules/django/db/models/manager/) (id=40677, locale=zh)
9. [django.db.models.manager | Documentación de Django](https://docs.djangoproject.com/es/6.1/_modules/django/db/models/manager/) (id=40656, locale=es)
10. [django.db.models.manager | Documentation de Django](https://docs.djangoproject.com/fr/6.1/_modules/django/db/models/manager/) (id=40659, locale=fr)

**PostgreSQL top 10**

1. [django.db.models.query | Εγχειρίδιο Django](https://docs.djangoproject.com/el/6.1/_modules/django/db/models/query/) (id=29456, locale=el)
2. [QuerySet API reference | Django documentation](https://docs.djangoproject.com/en/6.1/ref/models/querysets/) (id=28041, locale=en)
3. [django.db.models.query | Django documentation](https://docs.djangoproject.com/en/6.1/_modules/django/db/models/query/) (id=40719, locale=en)
4. [django.db.models.query | Documentación de Django](https://docs.djangoproject.com/es/6.1/_modules/django/db/models/query/) (id=40722, locale=es)
5. [django.db.models.query | Documentation de Django](https://docs.djangoproject.com/fr/6.1/_modules/django/db/models/query/) (id=40725, locale=fr)
6. [django.db.models.query | Dokumentasi Django](https://docs.djangoproject.com/id/6.1/_modules/django/db/models/query/) (id=40728, locale=id)
7. [django.db.models.query | Django ドキュメント](https://docs.djangoproject.com/ja/6.1/_modules/django/db/models/query/) (id=40731, locale=ja)
8. [django.db.models.query | Django 문서](https://docs.djangoproject.com/ko/6.1/_modules/django/db/models/query/) (id=40734, locale=ko)
9. [django.db.models.query | Dokumentacja Django](https://docs.djangoproject.com/pl/6.1/_modules/django/db/models/query/) (id=40737, locale=pl)
10. [django.db.models.query | Documentação do Django](https://docs.djangoproject.com/pt-br/6.1/_modules/django/db/models/query/) (id=40740, locale=pt)

### Q091: asynci create task

Mode: `text` | Flags: `ZERO_RESULTS` | Candidates: 0 | Time: 2 ms

### Q092: fastapi dependecy injection

Mode: `text` | Flags: `ZERO_RESULTS` | Candidates: 0 | Time: 1 ms

### Q093: python OR javascript

Mode: `text` | Flags: `LOW_AGREEMENT, MULTILINGUAL_TOP` | Candidates: 100 | Time: 773 ms

**BM25 top 10**

1. [翻译 | Django 文档](https://docs.djangoproject.com/zh-hans/6.1/topics/i18n/translation/) (id=65439, locale=zh)
2. [翻訳 | Django ドキュメント](https://docs.djangoproject.com/ja/6.1/topics/i18n/translation/) (id=65432, locale=ja)
3. [JavaScript 语言概览 - JavaScript | MDN](https://developer.mozilla.org/zh-CN/docs/Web/JavaScript/Guide/Language_overview) (id=20721, locale=zh)
4. [JavaScript 言語概要 - JavaScript | MDN](https://developer.mozilla.org/ja/docs/Web/JavaScript/Guide/Language_overview) (id=21960, locale=ja)
5. [Translation | Django documentation](https://docs.djangoproject.com/en/6.1/topics/i18n/translation/) (id=28297, locale=en)
6. [JavaScript language overview - JavaScript | MDN](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Guide/Language_overview) (id=2922, locale=en)
7. [Översättning | Django-dokumentation](https://docs.djangoproject.com/sv/6.1/topics/i18n/translation/) (id=65438, locale=sv)
8. [Traduction | Documentation de Django](https://docs.djangoproject.com/fr/6.1/topics/i18n/translation/) (id=65429, locale=fr)
9. [What’s New in Python 2.6](https://docs.python.org/3/whatsnew/2.6.html) (id=8019, locale=en)
10. [Überblick über die JavaScript-Sprache - JavaScript | MDN](https://developer.mozilla.org/de/docs/Web/JavaScript/Guide/Language_overview) (id=21133, locale=de)

**PostgreSQL top 10**

1. [Python Documentation contents](https://docs.python.org/3/contents.html) (id=165, locale=en)
2. [What’s New In Python 3.13](https://docs.python.org/3/whatsnew/3.13.html) (id=7552, locale=en)
3. [4. Using Python on Windows](https://docs.python.org/3/using/windows.html) (id=8067, locale=en)
4. [What’s New in Python](https://docs.python.org/3/whatsnew/index.html) (id=151, locale=en)
5. [What’s New in Python 2.7](https://docs.python.org/3/whatsnew/2.7.html) (id=8005, locale=en)
6. [What’s new in Python 3.15](https://docs.python.org/3/whatsnew/3.15.html) (id=150, locale=en)
7. [What’s New In Python 3.12](https://docs.python.org/3/whatsnew/3.12.html) (id=7628, locale=en)
8. [What’s New in Python 2.6](https://docs.python.org/3/whatsnew/2.6.html) (id=8019, locale=en)
9. [Python Initialization Configuration](https://docs.python.org/3/c-api/init_config.html) (id=7952, locale=en)
10. [General Python FAQ](https://docs.python.org/3/faq/general.html) (id=8130, locale=en)

### Q096: HTTP/2

Mode: `all` | Flags: `MULTILINGUAL_TOP` | Candidates: 132 | Time: 74 ms

**BM25 top 10**

1. [HTTP/2 - 用語集 | MDN](https://developer.mozilla.org/ja/docs/Glossary/HTTP_2) (id=72731, locale=ja)
2. [HTTP/2 - Glossary | MDN](https://developer.mozilla.org/en-US/docs/Glossary/HTTP_2) (id=6085, locale=en)
3. [HTTP/2 - MDN Web 文档术语表：Web 相关术语的定义 | MDN](https://developer.mozilla.org/zh-CN/docs/Glossary/HTTP_2) (id=72871, locale=zh)
4. [HTTP/2 - Glossary | MDN](https://developer.mozilla.org/de/docs/Glossary/HTTP_2) (id=72651, locale=de)
5. [HTTP/2 - Glossário do MDN Web Docs | MDN](https://developer.mozilla.org/pt-BR/docs/Glossary/HTTP_2) (id=72934, locale=pt)
6. [HTTP/2 - Глоссарий MDN Web Docs | MDN](https://developer.mozilla.org/ru/docs/Glossary/HTTP_2) (id=72567, locale=ru)
7. [HTTP/2 - MDN Web Docs 용어 사전: 웹 용어 정의 | MDN](https://developer.mozilla.org/ko/docs/Glossary/HTTP_2) (id=72781, locale=ko)
8. [HTTP/2 - Glossaire | MDN](https://developer.mozilla.org/fr/docs/Glossary/HTTP_2) (id=72525, locale=fr)
9. [HTTP 範囲付きリクエスト - HTTP | MDN](https://developer.mozilla.org/ja/docs/Web/HTTP/Guides/Range_requests) (id=68551, locale=ja)
10. [307 Temporary Redirect - HTTP | MDN](https://developer.mozilla.org/ja/docs/Web/HTTP/Reference/Status/307) (id=68725, locale=ja)

**PostgreSQL top 10**

1. [HTTP messages - HTTP | MDN](https://developer.mozilla.org/en-US/docs/Web/HTTP/Guides/Messages) (id=4910, locale=en)
2. [HTTP メッセージ - HTTP | MDN](https://developer.mozilla.org/ja/docs/Web/HTTP/Guides/Messages) (id=68542, locale=ja)
3. [Messages HTTP - HTTP | MDN](https://developer.mozilla.org/fr/docs/Web/HTTP/Guides/Messages) (id=69345, locale=fr)
4. [HTTP/2 - Glossário do MDN Web Docs | MDN](https://developer.mozilla.org/pt-BR/docs/Glossary/HTTP_2) (id=72934, locale=pt)
5. [HTTP/2 - Glossary | MDN](https://developer.mozilla.org/en-US/docs/Glossary/HTTP_2) (id=6085, locale=en)
6. [HTTP/2 - Glossaire | MDN](https://developer.mozilla.org/fr/docs/Glossary/HTTP_2) (id=72525, locale=fr)
7. [HTTP/2 - Глоссарий MDN Web Docs | MDN](https://developer.mozilla.org/ru/docs/Glossary/HTTP_2) (id=72567, locale=ru)
8. [HTTP/2 - Glossary | MDN](https://developer.mozilla.org/de/docs/Glossary/HTTP_2) (id=72651, locale=de)
9. [HTTP/2 - 用語集 | MDN](https://developer.mozilla.org/ja/docs/Glossary/HTTP_2) (id=72731, locale=ja)
10. [L'évolution du protocole HTTP - HTTP | MDN](https://developer.mozilla.org/fr/docs/Web/HTTP/Guides/Evolution_of_HTTP) (id=69344, locale=fr)

### Q098: async def fetch

Mode: `code` | Flags: `MULTILINGUAL_TOP` | Candidates: 12 | Time: 11 ms

**BM25 top 10**

1. [profiling.sampling — Statistical profiler](https://docs.python.org/3/library/profiling.sampling.html) (id=7863, locale=en)
2. [typing — Support for type hints](https://docs.python.org/3/library/typing.html) (id=7883, locale=en)
3. [执行查询 | Django 文档](https://docs.djangoproject.com/zh-hans/6.1/topics/db/queries/) (id=65161, locale=zh)
4. [クエリを作成する | Django ドキュメント](https://docs.djangoproject.com/ja/6.1/topics/db/queries/) (id=65155, locale=ja)
5. [Making queries | Django documentation](https://docs.djangoproject.com/en/6.1/topics/db/queries/) (id=28200, locale=en)
6. [Göra förfrågningar | Django-dokumentation](https://docs.djangoproject.com/sv/6.1/topics/db/queries/) (id=65160, locale=sv)
7. [Création de requêtes | Documentation de Django](https://docs.djangoproject.com/fr/6.1/topics/db/queries/) (id=65151, locale=fr)
8. [QuerySet API 参考 | Django 文档](https://docs.djangoproject.com/zh-hans/6.1/ref/models/querysets/) (id=64097, locale=zh)
9. [QuerySet API リファレンス | Django ドキュメント](https://docs.djangoproject.com/ja/6.1/ref/models/querysets/) (id=64092, locale=ja)
10. [QuerySet API reference | Django documentation](https://docs.djangoproject.com/en/6.1/ref/models/querysets/) (id=28041, locale=en)

**PostgreSQL top 10**

1. [profiling.sampling — Statistical profiler](https://docs.python.org/3/library/profiling.sampling.html) (id=7863, locale=en)
2. [Making queries | Django documentation](https://docs.djangoproject.com/en/6.1/topics/db/queries/) (id=28200, locale=en)
3. [Création de requêtes | Documentation de Django](https://docs.djangoproject.com/fr/6.1/topics/db/queries/) (id=65151, locale=fr)
4. [クエリを作成する | Django ドキュメント](https://docs.djangoproject.com/ja/6.1/topics/db/queries/) (id=65155, locale=ja)
5. [Göra förfrågningar | Django-dokumentation](https://docs.djangoproject.com/sv/6.1/topics/db/queries/) (id=65160, locale=sv)
6. [执行查询 | Django 文档](https://docs.djangoproject.com/zh-hans/6.1/topics/db/queries/) (id=65161, locale=zh)
7. [typing — Support for type hints](https://docs.python.org/3/library/typing.html) (id=7883, locale=en)
8. [QuerySet API reference | Django documentation](https://docs.djangoproject.com/en/6.1/ref/models/querysets/) (id=28041, locale=en)
9. [Référence de l’API QuerySet | Documentation de Django](https://docs.djangoproject.com/fr/6.1/ref/models/querysets/) (id=64090, locale=fr)
10. [QuerySet API リファレンス | Django ドキュメント](https://docs.djangoproject.com/ja/6.1/ref/models/querysets/) (id=64092, locale=ja)

## Next steps

1. Review flagged queries manually; flags are **leads**, not relevance verdicts.
2. Add independently judged document relevance labels (qrels).
3. Evaluate ranking quality with P@10, MRR@10 and nDCG@10; separately test candidate recall.
