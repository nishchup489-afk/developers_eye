# Vocabulary issues at the documentation baseline

Reviewed at `facd333` on 2026-11-02.

| Issue | Impact | Record / next evidence |
| --- | --- | --- |
| Added-term batch runs once per added term | Inflated document frequencies | [INC-0007](INC-0007-vocabulary-overcount-and-uncoordinated-removal.md); repair multi-term lifecycle before recount |
| Indexer removal does not acquire shared mutex | Rebuild/writer coordination is incomplete | INC-0007; real concurrent deletion/upsert/rebuild test |
| Global mutex serializes participating writers | Potential throughput cost, not yet measured | [EXP-0006](EXP-0006-vocabulary-lock-contention.md) |
| Legacy VocabularyDocumentState | Misleading model/state remnants; named migration is empty | [EXP-0002](EXP-0002-abandoned-vocabulary-worker.md) |
| Combined text/code filtered vocabulary | Unsuitable as per-channel exact BM25 DF | [ADR-0027](../../backend/bm25-statistics/ADR-0027-batch-ranking-statistics-and-external-corpus.md) |

A rebuild repairs stored counts at that instant. It cannot compensate for a buggy incremental writer continuing to run afterward.
