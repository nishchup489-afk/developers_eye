# `selector.py` · What should be processed?

**Purpose:** Decide which documents need work. Does not contain SQL or write to the database.

The selector calls `repository.py` to identify documents whose `search_index` revision has not yet been processed by the vocabulary worker.

- `select_sync_candidates()` returns newly indexed or changed documents.
- `select_removal_candidates()` returns previously processed documents whose index/source disappeared or became unavailable.
- Already processed, unchanged documents are skipped.

**`after_document_id`** is a pagination cursor: after returning document IDs 101 and 102, the next batch starts after 102.

**Returns:** `VocabularyCandidate(document_id, action, indexed_hash)`.

**Rule:** Selection is only a hint. The future writer must lock and re-check the revision before modifying frequencies.
