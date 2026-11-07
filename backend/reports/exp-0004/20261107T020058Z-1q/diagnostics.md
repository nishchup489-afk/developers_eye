# Developer's Eye | EXP-0004 Batch Search Diagnostics

Run: `20261107T020058Z-1q` | Queries: **1** | Corpus snapshot: {'text': {'N': 42114, 'avgDL': 679.9384458177218}, 'code': {'N': 42114, 'avgDL': 231.94013940139402}}

**Scope:** same retrieved candidate IDs, ranked by BM25 versus PostgreSQL 
`ts_rank_cd`. TITLE_HINT and language are heuristics, not human relevance 
grades. Rank agreement is not ranking quality. The corpus can change 
between queries while the crawler runs. This is not Recall@100, 
Precision@10, MRR@10 or nDCG@10.

Flags: TARGET_BELOW_K: 1

## All queries

| ID | Category | Query | Mode | Candidates | Overlap | Time (ms) | Flags |
|---|---|---|---|---:|---:|---:|---|
| Q051 | JavaScript | javascript fetch examples | all | 141 | 50% | 709 | TARGET_BELOW_K |

## Flagged queries

### Q051: javascript fetch examples

Mode: `all` | Flags: `TARGET_BELOW_K` | Candidates: 141 | Time: 709 ms

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
6. [WebAssembly.instantiate() - WebAssembly | MDN](https://developer.mozilla.org/en-US/docs/WebAssembly/Reference/JavaScript_interface/instantiate_static) (id=5620, locale=en)
7. [WebAssembly.instantiateStreaming() - WebAssembly | MDN](https://developer.mozilla.org/en-US/docs/WebAssembly/Reference/JavaScript_interface/instantiateStreaming_static) (id=5623, locale=en)
8. [WebAssembly.compileStreaming() - WebAssembly | MDN](https://developer.mozilla.org/en-US/docs/WebAssembly/Reference/JavaScript_interface/compileStreaming_static) (id=5617, locale=en)
9. [Response: bytes() method - Web APIs | MDN](https://developer.mozilla.org/en-US/docs/Web/API/Response/bytes) (id=66096, locale=en)
10. [Making network requests with JavaScript - Learn web development | MDN](https://developer.mozilla.org/en-US/docs/Learn_web_development/Core/Scripting/Network_requests) (id=6413, locale=en)

## Next steps

1. Review flagged queries manually; flags are **leads**, not relevance verdicts.
2. Add independently judged document relevance labels (qrels).
3. Evaluate ranking quality with P@10, MRR@10 and nDCG@10; separately test candidate recall.
