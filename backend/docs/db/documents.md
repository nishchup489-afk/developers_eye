# what it is?
- stores the scraped data , what we got from those crawled website. mostly html , metadata , little description


# why metadata_ not metadata?
- metadata is a preserved word in sqlalchemy


# what is hash?

- Suppose you crawl a documentation page today and revisit it tomorrow.
If the cleaned content hasn't changed, the hash remains the same. Your ingestion pipeline can skip unnecessary reindexing.
- why hash? why not just check the raw content changing?
- efficiency. 

Document ( 1:00 PM) : " I code in python, today i just finished coding in my computer"
Document as hash : abc233.......... (mock)
Document (2:00PM) : " I code in python, today i just finished coding in my computer. now i am in my mac"
Document as hash : abc323........


searching hash is more efficient than searching whole doc. hash is always fixed size.