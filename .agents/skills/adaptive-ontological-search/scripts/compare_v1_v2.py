"""
Comparison and Benchmarking Script: Ontological Search V1.0 vs V2.0.
Executes the research query on both pipelines and compares
ontology induction, skeptic disproving search, atomic claim extraction,
Richards Heuer ACH matrix resolution, and dynamic audit metrics.
"""

import asyncio
import json
import sys
import os

# Ensure current directory is in PYTHONPATH for script imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from orchestrator import OntologicalSearchOrchestrator
from orchestrator_v2 import OntologicalSearchOrchestratorV2


async def run_comparison(user_query: str):
    print("=" * 80)
    print("STARTING SIDE-BY-SIDE BENCHMARK: ONTOLOGICAL SEARCH V1.0 VS V2.0")
    print(f"QUERY: '{user_query}'")
    print("=" * 80 + "\n")

    # 1. Run V1 Pipeline
    print(">>> RUNNING PIPELINE V1.0 (LEGACY STATIC ENGINE)...")
    v1_orchestrator = OntologicalSearchOrchestrator()
    v1_result = await v1_orchestrator.run(user_query)

    print("\n" + "-" * 80 + "\n")

    # 2. Run V2 Pipeline
    print(">>> RUNNING PIPELINE V2.0 (SOTA DYNAMIC AUTOSCHEMA + HEUER ACH ENGINE)...")
    v2_orchestrator = OntologicalSearchOrchestratorV2()
    v2_result = await v2_orchestrator.run(user_query)

    # 3. Generate Comparative Metric Report
    print("\n" + "=" * 80)
    print("COMPARATIVE BENCHMARK REPORT: V1.0 vs V2.0")
    print("=" * 80)

    v1_metrics = v1_result.get("metrics", {})
    v2_metrics = v2_result.get("metrics", {})

    v1_claims = v1_result.get("claims", [])
    v2_claims = v2_result.get("atomic_claims", [])

    v1_domains = len(set(c.get("source_url", "").split("/")[2] for c in v1_claims if "://" in c.get("source_url", "")))
    v2_domains = v2_metrics.get("domain_diversity_count", len(set(c.get("source_domain", "") for c in v2_claims)))

    report = f"""
+------------------------------------+-----------------------------+------------------------------------+
| METRIC / FEATURE                   | V1.0 (LEGACY ENGINE)        | V2.0 (ONTOLOGICAL SEARCH 2.0)      |
+------------------------------------+-----------------------------+------------------------------------+
| Architecture Version               | 1.0 (Static Schema)         | 2.0 (AutoSchemaKG & Heuer ACH)     |
| Domain Ontology Induction          | Static Pre-configured       | Dynamic AutoSchemaKG               |
| Retrieval Strategy                 | Generic Multi-Hop           | LightRAG Dual-Level                |
| Skeptic Disproving Subagent (H0/HV)| No (Confirmation Bias Risk)| YES (Targeted Counter-Evidence)    |
| Claim Extraction Format            | Generic Findings Text       | Claimify Atomic Tuples (S-P-O)     |
| Evaluation Matrix                  | Simple Critic Confidence    | ACH (Richards Heuer Inconsistency) |
| Total Claims Extracted             | {len(v1_claims):<27} | {len(v2_claims):<34} |
| Source Independence Clusters       | {v1_domains:<27} | {v2_domains:<34} |
| Novelty Score                      | {v1_metrics.get('novelty_score', 0.0):<27} | {v2_metrics.get('novelty_score', 0.0):<34} |
| Reliability Score                  | {v1_metrics.get('reliability_score', 0.0):<27} | {v2_metrics.get('reliability_score', 0.0):<34} |
| Overall Confidence                 | {v1_result.get('synthesis', {}).get('overall_confidence', 0.0):<27} | {v2_result.get('synthesis', {}).get('overall_confidence', 0.0):<34} |
| Winning Hypothesis                 | H1 (Unrated Against H0/HV)  | {v2_result.get('ach_matrix', {}).get('winning_hypothesis', 'H1'):<34} |
+------------------------------------+-----------------------------+------------------------------------+
"""

    print(report)

    print("\n>>> V2.0 RICHARDS HEUER ACH INCONSISTENCY MATRIX SUMMARY:")
    ach = v2_result.get("ach_matrix", {})
    print(f"H1 Inconsistency Penalty: {ach.get('h1_inconsistency_penalty')} (Net Score: {ach.get('h1_net_score')})")
    print(f"H2 Inconsistency Penalty: {ach.get('h2_inconsistency_penalty')} (Net Score: {ach.get('h2_net_score')})")
    print(f"H0 Inconsistency Penalty: {ach.get('h0_inconsistency_penalty')} (Net Score: {ach.get('h0_net_score')})")
    print(f"HV Inconsistency Penalty: {ach.get('hv_inconsistency_penalty')} (Net Score: {ach.get('hv_net_score')})")
    print(f"VERDICT: Winning Hypothesis = {ach.get('winning_hypothesis')}")
    print(f"RATIONALE: {ach.get('decision_rationale')}")

    print("\n>>> V2.0 ATOMIC CLAIMS EXTRACTED (CLAIMIFY TUPLES):")
    for claim in v2_claims[:5]:
        origin = claim.get("upstream_origin_id") or claim.get("independence_group") or "root_cluster"
        print(f"  - [{claim.get('id')}] ({origin}) {claim.get('subject')} -> {claim.get('predicate')} -> {claim.get('object')}")

    print("\n" + "=" * 80)
    print("BENCHMARK COMPLETED SUCCESSFULLY.")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    query = sys.argv[1] if len(sys.argv) > 1 else "PostgreSQL vs CockroachDB for fintech registry in Ukraine"
    asyncio.run(run_comparison(query))
