

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
from backend.schema import CrawlTargetCreate
from frontier.urls import normalize_url



# it will return what we about to crawl with source id , kind , fetch_url 



def build_initial_target(source : Source) -> dict[str , int | str]:

    if source.kind != "website":
        raise ValueError("Unsupported source kind")

    target = {
        "source_id" : source.id,
        "fetch_url" : source.base_url , 
        "normalized_url" : normalize_url(source.base_url) , 
        "kind" : "page",
        "priority" : source.config.get("priority" , 0),
        "discovered_from_id" : None
    }

    return CrawlTargetCreate.model_validate(target)







            





