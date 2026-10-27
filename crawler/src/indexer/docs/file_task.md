File	Responsibility
config.py	Indexer settings and limits
schemas.py	Data structures shared between components
errors.py	Custom indexer exceptions
selector.py	Find documents requiring indexing
builder.py	Convert database documents into indexing inputs
analyzer.py	Prepare and normalize searchable text
vector.py	Build weighted full-text search vectors
repository.py	Read/write indexed data in PostgreSQL
service.py	Coordinate indexing a document
reindex.py	Manage rebuilding outdated indexes
reporting.py	Indexing metrics and diagnostics
worker/runner.py	Execute continuous or one-shot indexing jobs
__init__.py	Mark the directories as Python packages
docs/	Technical documentation