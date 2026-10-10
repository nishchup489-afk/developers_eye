

"""
so we already got enabled source in registry.py now we will 
read the configs and see which one we can crawl intially 

# 1. Open a database session
# 2. Retrieve enabled sources
# 3. Convert each source into initial crawl targets
# 4. Normalize and validate their URLs
# 5. Insert them into crawl_target
# 6. Commit the transaction

"""



from backend.models import Source
from backend.db.session import SessionFactory
from .registry import get_enabled_sources
from sqlalchemy import insert
from backend.models import CrawlTarget
from backend.schema import CrawlAttemptCreate



# it will return what we about to crawl with source id , kind , fetch_url 
# def build_initial_target(source : Source ) -> dict:
#     async with SessionFactory() as session:
#         async with session.begin():
#             sources = get_enabled_sources()

#             urls = []
#             for source in sources : 
#                 urls.append({"source_id" : source.id ,
#                              "fetch_url" : source.base_url, 
#                               "normalized_url": normalize_url(source.base_url) , 
#                               "kind" : source.kind,
#                               "priority" : source.config.get("priority" , 0) ,
#                               "discovered_from_id" : source.id})

#             for url in urls:
#                 to_insert = CrawlAttemptCreate.model_validate(*url)

#                 CrawlTarget.insert(to_insert)

#             session.commit()

#             return 



            





