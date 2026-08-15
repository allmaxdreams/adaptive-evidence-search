"""
Generic & Parameterized Benchmarking Script: Ontological Search V1.0 vs V2.1 Core.
Compares legacy static ontological search against dynamic v2.1 pipeline on any input query or startup profile.
"""

import asyncio
import json
import sys
import os
import argparse
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from orchestrator import OntologicalSearchOrchestrator
from vc_due_diligence_orchestrator import VCDueDiligenceOrchestrator, StartupProfile


async def run_benchmark(
    name: str = "Target Tech",
    category: str = "Enterprise Architecture",
    query: Optional[str] = None
):
    print("=" * 80)
    print(f"BENCHMARKING ONTOLOGICAL SEARCH V1.0 VS V2.1 CORE FOR: {name} ({category})")
    print("=" * 80 + "\n")

    search_query = query or f"Analyze technical architecture, trade-offs, and disproving risks for {name}"

    # --- PIPELINE V1.0 (LEGACY STATIC SEARCH) ---
    print(">>> [ENGINE V1.0] Running Legacy Static Ontological Search...")
    v1 = OntologicalSearchOrchestrator()
    res_v1 = await v1.run(search_query)

    print("\n" + "-" * 80 + "\n")

    # --- PIPELINE V2.1 (ONTOLOGICAL SEARCH 2.1 - DYNAMIC AUTOSCHEMA + ACH + GATED SYNTHESIS) ---
    print(">>> [ENGINE V2.1] Running Dynamic Ontological Search 2.1 Core...")
    v2 = VCDueDiligenceOrchestrator()
    profile = StartupProfile(
        name=name,
        category=category,
        website=f"https://{name.lower().replace(' ', '')}.local",
        founders=["Engineering Leadership"],
        stated_mission=f"Evaluation of {name}",
        target_market=category
    )
    res_v2_report = await v2.analyze_startup(profile)
    res_v2 = res_v2_report.dict()

    print("\n" + "=" * 80)
    print(f"DETAILED COMPARATIVE BENCHMARK: {name.upper()} RISK DISCOVERY")
    print("=" * 80)

    v1_claims = res_v1.get("claims", [])
    v2_claims = res_v2.get("claims_provenance", [])
    v2_red_flags = res_v2.get("red_flags", [])

    print("\n>>> V1.0 FINDINGS SUMMARY:")
    for c in v1_claims[:3]:
        print(f"  - [{c.get('supports_hypothesis', 'H1')}] {c.get('statement')}")

    print("\n>>> V2.1 RED FLAGS & SKEPTIC DISPROVING FINDINGS:")
    for rf in v2_red_flags:
        print(f"  - [{rf['severity']}] {rf['title']}")
        print(f"    Evidence: {rf['evidence']}")
        print(f"    Source: {rf['source']}\n")

    print("\n>>> V2.1 ACH MATRIX VERDICT & CONVICTION SCORE:")
    print(f"  - Recommendation: {res_v2.get('investment_recommendation')}")
    print(f"  - Conviction Score: {res_v2.get('conviction_score')}/1.0")
    print(f"  - Key Questions: {len(res_v2.get('key_questions_for_founders', []))} items generated")

    return res_v1, res_v2


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generic Ontological Search Benchmark Runner")
    parser.add_argument("--name", default="PostgreSQL vs CockroachDB", help="Target name or comparison pair")
    parser.add_argument("--category", default="Distributed Systems", help="Domain category")
    parser.add_argument("--query", default=None, help="Explicit search query")
    args = parser.parse_args()

    asyncio.run(run_benchmark(name=args.name, category=args.category, query=args.query))
