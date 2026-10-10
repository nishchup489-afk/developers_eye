# what it does?it insert the registry in source table of postgres 


from backend.core.config import settings
from backend.db.base import Base
from backend.models.source import Source

from sqlalchemy import select 
from sqlalchemy.ext.asyncio import AsyncSession 
from sqlalchemy.orm import selectinload 

