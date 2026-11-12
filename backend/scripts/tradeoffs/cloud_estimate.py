"""Trade-off 14: local machine vs an Oracle Cloud Always Free ARM VM (estimate).

  python backend/scripts/tradeoffs/cloud_estimate.py
  python backend/scripts/tradeoffs/cloud_estimate.py --arm-per-core 0.45 --local-watts 110 --price-kwh 0.16

No cloud VM was available, so this is an ESTIMATE built only from the measured
local reports in backend/reports/tradeoffs/ plus the assumptions printed in the
output. It reads, never measures:

  CPU time per unit of work (search, crawled page, indexed document), measured
  locally as Python + PostgreSQL CPU seconds divided by the work done.

  ARM time = local CPU time / arm_per_core, where arm_per_core is how fast one
  Ampere A1 core is relative to one core of this machine (default 0.45, range
  0.35-0.55; set it from your own single-thread benchmark when you have the VM).

  ARM capacity per second = usable cores / ARM CPU seconds per unit, with
  usable cores = 4 OCPU x target utilisation (default 0.7, headroom for
  autovacuum, checkpoints and spikes).

  Latency on ARM = local p50/p95 / arm_per_core (CPU-bound path; I/O waits
  are not scaled, which is why the result is a range, not a number).

Monthly cost: Always Free A1 is $0 inside the free allowance (4 OCPU, 24 GB,
200 GB block storage, 10 TB egress). The pay-as-you-go figure uses the A1 list
price given by --ocpu-hour / --gb-hour; check the current price list.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402

HOURS_PER_MONTH = 730


def load(name: str) -> dict:
    path = common.REPORT_DIR / f"{name}.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--arm-per-core", type=float, default=0.45)
    parser.add_argument("--arm-cores", type=int, default=4)
    parser.add_argument("--arm-ram-gb", type=int, default=24)
    parser.add_argument("--utilisation", type=float, default=0.7)
    parser.add_argument("--local-watts", type=float, default=110, help="average wall power of this PC while serving")
    parser.add_argument("--price-kwh", type=float, default=0.16, help="electricity price per kWh")
    parser.add_argument("--ocpu-hour", type=float, default=0.01)
    parser.add_argument("--gb-hour", type=float, default=0.0015)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    search = load("04-search-concurrency")
    crawl = load("06-crawler-concurrency")
    index = load("07-indexer-batch-size")
    scaling = load("11-corpus-scaling")
    usable = args.arm_cores * args.utilisation
    pg_idle = load("01-ranking-bm25-vs-pg").get("idle_baseline", {}).get("postgres_cpu_cores", 0.0)
    local_cpus = common.machine()["logical_cpus"]
    out: dict = {"assumptions": vars(args) | {"output": None}, "label": "ESTIMATE, not measured on a VM"}

    # Search: take the best measured level (highest successful searches/second).
    if search:
        best = max(search["levels"], key=lambda r: r["successful_per_second"])
        ok = best["status_counts"].get("200", 0)
        # API process CPU only (the load generator runs in the benchmark process), plus
        # PostgreSQL CPU minus the background rate seen while idle (another crawler, autovacuum).
        api_cpu = best["api_process_cpu_cores"] * best["window_seconds"]
        pg_cpu = max(0.0, best["resources"]["postgres_cpu_seconds"] - pg_idle * best["window_seconds"])
        cpu_per_search = (api_cpu + pg_cpu) / max(1, ok)
        one_user = next(r for r in search["levels"] if r["users"] == 1)
        out["search"] = {
            "local_best_successful_per_second": best["successful_per_second"], "at_users": best["users"],
            "local_cpu_ms_per_search": round(cpu_per_search * 1000, 1),
            "arm_cpu_ms_per_search": round(cpu_per_search * 1000 / args.arm_per_core, 1),
            "arm_cpu_bound_searches_per_second": round(usable / (cpu_per_search / args.arm_per_core), 1),
            "local_single_user_p50_ms": one_user["latency_all_responses"]["p50_ms"],
            "local_single_user_p95_ms": one_user["latency_all_responses"]["p95_ms"],
            "arm_single_user_p50_ms_range": [one_user["latency_all_responses"]["p50_ms"],
                                             round(one_user["latency_all_responses"]["p50_ms"] / args.arm_per_core)],
            "arm_single_user_p95_ms_range": [one_user["latency_all_responses"]["p95_ms"],
                                             round(one_user["latency_all_responses"]["p95_ms"] / args.arm_per_core)],
            "note": "one uvicorn worker is single-threaded: the API process itself is capped at one core either way",
        }
    if crawl:
        best = max(crawl["runs"], key=lambda r: r["docs_per_second"])
        docs = max(1, best["documents"])
        window = best["resources"]["wall_seconds"]
        cpu = (best["resources"]["python_cpu_seconds"] + max(0.0, best["resources"]["postgres_cpu_seconds"] - pg_idle * window)) / docs
        out["crawl"] = {
            "local_best_docs_per_second": best["docs_per_second"], "at_workers": best["workers"],
            "local_cpu_ms_per_page": round(cpu * 1000, 1),
            "arm_cpu_ms_per_page": round(cpu * 1000 / args.arm_per_core, 1),
            "arm_cpu_bound_pages_per_second": round(usable / (cpu / args.arm_per_core), 1),
            "note": "real crawling is capped by politeness (hosts / 2 s) long before CPU",
        }
    if index:
        best = max(index["runs"], key=lambda r: r["docs_per_second"])
        window = best["resources"]["wall_seconds"]
        cpu = (best["resources"]["python_cpu_seconds"] + max(0.0, best["resources"]["postgres_cpu_seconds"] - pg_idle * window)) / max(1, best["indexed"])
        out["index"] = {
            "local_best_docs_per_second": best["docs_per_second"], "label": best["label"],
            "local_cpu_ms_per_document": round(cpu * 1000, 1),
            "arm_cpu_bound_docs_per_second": round(usable / (cpu / args.arm_per_core), 1),
            "arm_hours_to_index_2m": round(2_000_000 / (usable / (cpu / args.arm_per_core)) / 3600, 1),
        }
    if scaling:
        full = scaling["sizes"][max(scaling["sizes"], key=int)]
        per_doc_mb = full["table_total_mb"] / full["rows"]
        out["storage"] = {
            "search_index_mb_per_1000_docs": round(per_doc_mb * 1000, 2),
            "search_index_gb_at_2m_linear": round(per_doc_mb * 2_000_000 / 1024, 1),
            "fits_in_arm_ram": per_doc_mb * 2_000_000 / 1024 < args.arm_ram_gb * 0.5,
        }
    paid = args.arm_cores * args.ocpu_hour + args.arm_ram_gb * args.gb_hour
    local_power = args.local_watts / 1000 * HOURS_PER_MONTH * args.price_kwh
    out["monthly_cost_usd"] = {
        "oracle_always_free_a1": 0.0,
        "oracle_a1_same_shape_pay_as_you_go": round(paid * HOURS_PER_MONTH, 2),
        "local_pc_electricity_only": round(local_power, 2),
        "note": "local excludes hardware wear and home internet; Oracle free tier excludes nothing within its limits",
    }
    out["local_machine"] = {"logical_cpus": local_cpus, "postgres_idle_cpu_cores_subtracted": pg_idle}
    common.write_report("14-local-vs-cloud", out, args.output)
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
