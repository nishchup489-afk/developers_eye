# what is it?


documet_id : Links the index to its original document. It is both a PK and FK, enforcing one search-index row per document

search_vector : Stores tokenized, normalized text that PostgreSQL uses for full-text search

indexed_hash : Records which document content version was indexed



# what is tsvector?
- it is a special postgres component that turns raw text into resembled representation 

raw : 
Title: Learning Python Programming

Body: Python is a popular programming language.

tsvector : 
'learn':1
'python':2,4
'program':3,8
'popular':7
'languag':9

# why gin index?
- GIN (Generalized Inverted Index) is a PostgreSQL index type particularly useful for full-text search.

# wanna explore more about search system. go ahead and check this fancy project - https://advanced-search-system.vercel.app/
[ caution : hosted on render for backend. so first load may take a while.]

# we already have content_hash , why store another hash?
- because source document and search index may have different versions