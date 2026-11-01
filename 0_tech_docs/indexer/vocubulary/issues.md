lock issue 

- If 10 indexer workers acquire this same lock, only one can pass the lock point at a time. Other workers wait, even if they're updating completely different vocabulary terms. [TODO]

