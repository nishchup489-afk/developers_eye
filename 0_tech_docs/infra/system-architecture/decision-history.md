# Decision history and abandoned directions

This history separates linked repository changes from remembered intent. Dates below use the commit timestamps in UTC; they can differ by one day from the builder's New York workday. This is not a claim that every private/local experiment was retained.

| Date | Change or learning | Evidence and consequence |
| --- | --- | --- |
| 2026-10-05–06 | Backend-heavy developer search; frontend first supported a typed demo contract | [999c231](https://github.com/nishchup489-afk/developers_eye/commit/999c2318cf9a3ddc63d688a0d8c380abccf74cc2); keep demo and live mode explicit |
| 2026-10-09–12 | Models, Alembic, registry, discovery and PostgreSQL frontier/leases | [39ae757](https://github.com/nishchup489-afk/developers_eye/commit/39ae7572d65f1c0410918c1a00a735de4f21bb00), [762c94b](https://github.com/nishchup489-afk/developers_eye/commit/762c94ba9b6d33882979ee93c5d3486d5f5f660a); durable queue chosen without external broker |
| 2026-10-13–16 | Host/DNS/robots/politeness/redirect policy and bounded fetcher | [3a84cd7](https://github.com/nishchup489-afk/developers_eye/commit/3a84cd7b48ea3931d0a5bd761576e6e7c14c0d60), [87d5205](https://github.com/nishchup489-afk/developers_eye/commit/87d5205c0775a00b175c4d0680404766aec39df8); policy approval precedes transport |
| 2026-10-17–20 | HTML extraction, normalization/classification/fingerprints, persistence and worker execution | [7d188a3](https://github.com/nishchup489-afk/developers_eye/commit/7d188a31cebc10b628c0c1a2eeaea5749fe3ca9f), [0c93212](https://github.com/nishchup489-afk/developers_eye/commit/0c932125b7cca9dfae62dd29fc379088d8fa42f0); keep pure processing separate from writer decisions |
| 2026-10-20–21 | Real integration defects: deadlocks, scope, pinned identity, robots matching, recovery and unavailable content | Existing INC-0002–0005 plus INC-0010–0012; fix logs preserve causes and regression intent |
| 2026-10-21 | Sitemap, RSS/Atom and configurable JSON ingestion | [d9fde47](https://github.com/nishchup489-afk/developers_eye/commit/d9fde47df8dcf18985b4b5c6c0192c2d155f316f); shared frontier/parser/writer path rather than unrestricted adapters |
| 2026-10-26 | Static eye replaced by three.js/GSAP presentation | [022b134](https://github.com/nishchup489-afk/developers_eye/commit/022b134bed134958481cee73e9b0ac27fa28f5cf); preserve static/reduced-motion paths |
| 2026-10-27 | Indexer completed as freshness-derived work with versioned hashes and dual vectors | ADR-0008–0010; stored vectors are not proof of ranking quality |
| 2026-10-27 | Global-priority starvation led to source rotation and priority-before-depth claims | [e019701](https://github.com/nishchup489-afk/developers_eye/commit/e0197011eedcc46c3ea23331bfc1b8db2b4b330b); ADR-0005 |
| 2026-10-27 | Source-row locks starved additional workers for one eligible source | [8f63063](https://github.com/nishchup489-afk/developers_eye/commit/8f63063f70479f8c5388cd4fe196cf41c943c191); ADR-0001 and measured EXP-0001 |
| 2026-10-30 | Public GET /search served PostgreSQL results; frontend moved to shared Axios clients | [e9e8726](https://github.com/nishchup489-afk/developers_eye/commit/e9e87269c101aec4a64f12fc6457faf2afa9922a), [08c73e3](https://github.com/nishchup489-afk/developers_eye/commit/08c73e3484b1409d832c8a54c234e54cb436fea7); old handoff claim of no endpoint is obsolete |
| 2026-10-30–31 | Separate vocabulary worker prototype abandoned | [a8b1b03](https://github.com/nishchup489-afk/developers_eye/commit/a8b1b0329a5cd43a9f55d27f2decc13fa2355620); EXP-0002 and ADR-0002 explain stored-lexeme ownership |
| 2026-10-31–11-01 | PR #3 vocabulary deltas needed PR #4 schema/delete/rebuild repair; PR #5 aligned rebuild CLI logging | PRs [#3](https://github.com/nishchup489-afk/developers_eye/pull/3), [#4](https://github.com/nishchup489-afk/developers_eye/pull/4), [#5](https://github.com/nishchup489-afk/developers_eye/pull/5); current defects still listed in INC-0007 |
| 2026-10-31–11-02 | Analyzer, explicit planner, snippets, typed merge and ranking scaffolding added | [884d07c](https://github.com/nishchup489-afk/developers_eye/commit/884d07cd85a65ea3c9c81f3dfe052739c7d92020), [f195afd](https://github.com/nishchup489-afk/developers_eye/commit/f195afd47eb37c543e52304056739a0594a70b65); components are not yet the public pipeline |
| 2026-11-02 | Snippet hard-budget fix merged | PR [#6](https://github.com/nishchup489-afk/developers_eye/pull/6); incident INC-0009 |
| 2026-11-02 | BM25 single-value statistics replaced with batching and explicit corpus input | [581d7b2](https://github.com/nishchup489-afk/developers_eye/commit/581d7b29befeabb3ee95f43889c84d320bdd1390) → [facd333](https://github.com/nishchup489-afk/developers_eye/commit/facd3336285f2da58b4f9c73efcd0d5ed6a05492); EXP-0003 counts calls, not speed |

## Directions discussed but not established as shipped

| Direction | Current interpretation |
| --- | --- |
| Custom inverted index / BM25 from the early design | PostgreSQL GIN/TSVECTOR is the implemented index; custom BM25 scoring is still a proposal |
| Redis/ARQ queues and separate worker types for each platform | PostgreSQL frontier and existing crawler/indexer processes serve the current design; extra workers/brokers are deferred |
| APIs for GitHub/Reddit/Stack Overflow, crawling for docs/blogs | Product/acquisition intent; generic mapped JSON and feeds do not certify those platform-specific integrations |
| Nginx query optimization | Intended HTTP infrastructure; retrieval selection is application logic and SQL optimization is database/application work |
| Benchmarking hosted search alternatives | An exploratory idea; no comparative measured result is retained |
| Persist BM25 statistics during indexing | Next optimization candidate after exact term/channel/deletion/rebuild semantics are defined |
| Vector retrieval, embeddings, RAG and AI answers | Deferred beyond a working lexical search path; no measured model/search benefit is claimed |
| Hosting/provider recommendations | Prior discussions explored options; this repository does not establish one active production deployment |

These descriptions use prior project discussions only for intent and are cross-checked against the current repository. Proposed alternatives are not retroactively described as failed experiments. Personal milestones, résumé counts and unrelated projects are deliberately not used as engineering validation.
