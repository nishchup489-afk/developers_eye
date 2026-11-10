# EXP-0016: time BM25 document-frequency counts with the old (seq-scan) plan and the GIN-only plan.
# Usage: PYTHONPATH=backend/src DATABASE_URL=... python dfbench.py out.json
import asyncio, time, json, sys
from sqlalchemy import text, select, func
from backend.db.session import SessionFactory
from backend.search.tokenizer import tokenize_query
from backend.search.ranking.statistics import _get_document_frequencies
SLOW = [("python generator yield from","all"),("python dataclasses","text"),("python context manager","all"),
 ("python asyncio event loop","text"),("python concurrent.futures","text"),("FastAPI Depends","all"),
 ("FastAPI settings environment variables","text"),("django class based views","text"),("HTTP 500 internal server error","text")]
async def main():
    out=[]
    for q,m in SLOW:
        row={"query":q,"mode":m}
        for variant in ("seq_scan_plan","gin_plan"):
            async with SessionFactory() as s:
                tt, ct = await tokenize_query(s, q)
                chans=[("TEXT",tt)] if m=="text" else [("TEXT",tt),("CODE",ct)]
                if variant=="seq_scan_plan":
                    await s.execute(text("SET LOCAL enable_bitmapscan=off")); await s.execute(text("SET LOCAL enable_indexscan=off"))
                t=time.perf_counter(); dfs={}
                for ch,terms in chans:
                    if terms:
                        if variant=="seq_scan_plan":
                            # same SQL without the GIN-only guard
                            from backend.search.ranking import statistics as st
                            from sqlalchemy import union_all, literal
                            v=st._get_vector(ch)
                            qs=[select(literal(x).label("term"),func.count()).select_from(st.SearchIndex).where(v.bool_op("@@")(st._exact_lexeme_query(x))) for x in terms]
                            rows=(await s.execute(qs[0] if len(qs)==1 else union_all(*qs))).all()
                            dfs[ch]=dict(rows)
                        else:
                            dfs[ch]=await _get_document_frequencies(s, terms, ch)
                row[variant+"_ms"]=round((time.perf_counter()-t)*1000,1); row[variant+"_df"]=dfs
        assert row["seq_scan_plan_df"]==row["gin_plan_df"], row
        del row["seq_scan_plan_df"]; row["df"]=row.pop("gin_plan_df")
        out.append(row); print(json.dumps(row), flush=True)
    json.dump(out, open(sys.argv[1],"w"), indent=1)
asyncio.run(main())
