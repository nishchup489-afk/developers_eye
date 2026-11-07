# Developer's Eye | EXP-0004 Batch Search Diagnostics

Run: `20261107T012230Z-5q` | Queries: **5** | Corpus snapshot: {'text': {'N': 42114, 'avgDL': 700.0938453713123}, 'code': {'N': 42114, 'avgDL': 244.17799813460311}}

**Scope:** same retrieved candidate IDs, ranked by BM25 versus PostgreSQL 
`ts_rank_cd`. TITLE_HINT and language are heuristics, not human relevance 
grades. Rank agreement is not ranking quality. The corpus can change 
between queries while the crawler runs. This is not Recall@100, 
Precision@10, MRR@10 or nDCG@10.

Flags: MULTILINGUAL_TOP: 2, TARGET_NOT_IN_CANDIDATES: 1, LOW_AGREEMENT: 1

## All queries

| ID | Category | Query | Mode | Candidates | Overlap | Time (ms) | Flags |
|---|---|---|---|---:|---:|---:|---|
| Q001 | Python Core | python list comprehension | text | 71 | 30% | 96 | MULTILINGUAL_TOP, TARGET_NOT_IN_CANDIDATES |
| Q002 | Python Core | python dict get default | code | 100 | 0% | 88 | LOW_AGREEMENT, MULTILINGUAL_TOP |
| Q003 | Python Core | python generator yield from | all | 100 | 50% | 155 | OK |
| Q004 | Python Core | python dataclasses | text | 43 | 30% | 24 | OK |
| Q005 | Python Core | python type hints | text | 100 | 40% | 401 | OK |

## Flagged queries

### Q001: python list comprehension

Mode: `text` | Flags: `MULTILINGUAL_TOP, TARGET_NOT_IN_CANDIDATES` | Candidates: 71 | Time: 96 ms

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

Mode: `code` | Flags: `LOW_AGREEMENT, MULTILINGUAL_TOP` | Candidates: 100 | Time: 88 ms

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

## Next steps

1. Review flagged queries manually; flags are **leads**, not relevance verdicts.
2. Add independently judged document relevance labels (qrels).
3. Evaluate ranking quality with P@10, MRR@10 and nDCG@10; separately test candidate recall.
