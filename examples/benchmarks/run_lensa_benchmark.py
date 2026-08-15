"""
Example Benchmark: Ontological Search V1.0 vs V2.0 on Lensa.ai Business & Legal Risks.
Note: Moved to examples/benchmarks/ to keep core production scripts entity-agnostic.
"""

import asyncio
import json
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".agents", "skills", "adaptive-ontological-search", "scripts"))

from orchestrator import OntologicalSearchOrchestrator
from vc_due_diligence_orchestrator import VCDueDiligenceOrchestrator, StartupProfile


async def run_lensa_comparison():
    print("=" * 80)
    print("EXAMPLE BENCHMARK: ONTOLOGICAL SEARCH V1.0 VS V2.0 FOR LENSA.AI RISKS")
    print("=" * 80 + "\n")

    query = "Analyze business, legal, technological moat, and churn risks for Lensa.ai (Prisma Labs)"

    # --- PIPELINE V1.0 (LEGACY STATIC SEARCH) ---
    print(">>> [ENGINE V1.0] Running Legacy Static Ontological Search...")
    v1 = OntologicalSearchOrchestrator()
    res_v1 = await v1.run(query)

    print("\n" + "-" * 80 + "\n")

    # --- PIPELINE V2.0 (ONTOLOGICAL SEARCH 2.0 - AUTOSCHEMA + LIGHTRAG + SKEPTIC + ACH) ---
    print(">>> [ENGINE V2.0] Running Ontological Search 2.0 (Mode 3 Dynamic VC Audit)...")
    v2 = VCDueDiligenceOrchestrator()
    profile = StartupProfile(
        name="Lensa AI",
        category="AI + Consumer & Creative",
        website="https://lensa-ai.com",
        founders=["Alexey Moiseenkov", "Prisma Labs Team"],
        stated_mission="AI-powered photo and video editing & Magic Avatars",
        target_market="Consumer Generative AI & Mobile Media"
    )
    res_v2_report = await v2.analyze_startup(profile)
    res_v2 = res_v2_report.dict()

    print("\n" + "=" * 80)
    print("DETAILED COMPARATIVE BENCHMARK: LENSA.AI RISK DISCOVERY")
    print("=" * 80)

    # Display comparison summary table
    v1_claims = res_v1.get("claims", [])
    v2_claims = res_v2.get("claims_provenance", [])
    v2_red_flags = res_v2.get("red_flags", [])

    print("\n>>> V1.0 FINDINGS SUMMARY:")
    for c in v1_claims[:3]:
        print(f"  - [{c.get('supports_hypothesis', 'H1')}] {c.get('statement')}")

    print("\n>>> V2.0 RED FLAGS & SKEPTIC DISPROVING FINDINGS:")
    for rf in v2_red_flags:
        print(f"  - [{rf['severity']}] {rf['title']}")
        print(f"    Evidence: {rf['evidence']}")
        print(f"    Source: {rf['source']}\n")

    print("\n>>> V2.0 ACH MATRIX VERDICT & CONVICTION SCORE:")
    print(f"  - Recommendation: {res_v2.get('investment_recommendation')}")
    print(f"  - Conviction Score: {res_v2.get('conviction_score')}/1.0")
    print(f"  - Key Questions for Founders: {len(res_v2.get('key_questions_for_founders', []))} items generated")

    return res_v1, res_v2


if __name__ == "__main__":
    asyncio.run(run_lensa_comparison())
