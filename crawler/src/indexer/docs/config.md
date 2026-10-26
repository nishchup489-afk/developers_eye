`TypeVar("_T")`

Look ahead to this function:
def read(    name: str,    cast: Callable[[str], _T],    default: _T,) -> _T:



We're making one reusable function that can read integers, floats, and strings.

For example:
read("BATCH_SIZE", int, 100)# Returns an intread("POLL_SECONDS", float, 10.0)# Returns a floatread("LOG_LEVEL", str, "INFO")# Returns a str



_T means the type depends on what conversion function and default we provide.

Setting	Default	Meaning
batch_size	100	Number of documents fetched for one indexing batch
concurrency	2	Maximum simultaneous indexing tasks, once implemented
poll_seconds	10.0	Delay between continuous-worker polls
index_version	1	Version of our indexing rules
max_document_chars	1,000,000	Maximum allowed indexable character count
text_search_config	english	PostgreSQL linguistic text processing
code_search_config	simple	PostgreSQL non-stemming text-search configuration
log_level	INFO	Amount of diagnostic output