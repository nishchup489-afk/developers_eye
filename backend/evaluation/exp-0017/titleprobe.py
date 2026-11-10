# EXP-0017: where the 100k recall-miss targets land in the title and code channels.
# Usage: PYTHONPATH=backend/src DATABASE_URL=... python titleprobe.py out.json
import asyncio, json
from backend.db.session import SessionFactory
from backend.search.retrieval.titles import search_titles
from backend.search.retrieval.code import search_code
from sqlalchemy import text
MISSES=[("Q015","asyncio TaskGroup","code","Coroutines and Tasks"),("Q017","asyncio Semaphore","code","Synchronization Primitives"),
("Q055","javascript event loop","text","event loop"),("Q058","javascript optional chaining","text","Optional chaining"),
("Q059","javascript Object.entries","code","Object.entries"),("Q061","HTTP 404","code","404 Not Found"),
("Q062","HTTP 500 internal server error","text","500 Internal Server Error"),("Q063","HTTP caching Cache-Control","all","Cache-Control"),
("Q072","Rust lifetimes","text","Lifetimes"),("Q079","Rust pattern matching","text","Patterns")]
async def main():
    rows=[]
    async with SessionFactory() as s:
        for qid,q,mode,hint in MISSES:
            hits=await search_titles(s,q)
            ids=[h.document_id for h in hits]
            titles={i:t for i,t in (await s.execute(text("select id,title from document where id = any(:ids)"),{"ids":ids or [0]})).all()}
            pos=next((n for n,i in enumerate(ids,1) if hint.casefold() in titles[i].casefold()),None)
            code=[h.document_id for h in await search_code(s,q,limit=100)] if mode=="code" else []
            ctitles={i:t for i,t in (await s.execute(text("select id,title from document where id = any(:ids)"),{"ids":code or [0]})).all()}
            cpos=next((n for n,i in enumerate(code,1) if hint.casefold() in ctitles[i].casefold()),None)
            indexed=(await s.execute(text("select count(*) from document d join search_index si on si.document_id=d.id where d.title ilike :h"),{"h":f"%{hint}%"})).scalar()
            r=dict(id=qid,query=q,mode=mode,hint=hint,indexed_with_hint=indexed,title_channel_size=len(ids),title_channel_target_position=pos,code_channel_target_position=cpos)
            rows.append(r); print(r)
    import sys; json.dump(rows,open(sys.argv[1],'w'),indent=1)
asyncio.run(main())
