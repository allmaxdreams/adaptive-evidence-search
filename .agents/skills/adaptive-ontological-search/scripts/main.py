"""
CLI Entrypoint for Adaptive Ontology-Driven Evidence Search Orchestrator 2.0.
"""

import sys
import os
import asyncio
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from orchestrator_v2 import OntologicalSearchOrchestratorV2
from orchestrator import OntologicalSearchOrchestrator


async def main():
    use_v1 = "--v1" in sys.argv
    args = [a for a in sys.argv[1:] if a != "--v1"]
    
    question = args[0] if args else "Identify breakthrough AI Agent frameworks, protocols, and execution runtimes for production deployment"
    
    if use_v1:
        print(">>> Running Ontological Search 1.0 (Legacy Engine)...")
        orchestrator = OntologicalSearchOrchestrator()
        result = await orchestrator.run(question)
    else:
        print(">>> Running Ontological Search 2.0 (AutoSchemaKG + Skeptic + ACH Matrix)...")
        orchestrator = OntologicalSearchOrchestratorV2()
        result = await orchestrator.run(question)
    
    print("\n--- FINAL SYNTHESIS REPORT ---")
    print(json.dumps(result["synthesis"], indent=2, ensure_ascii=False))

    if "ach_matrix" in result:
        print("\n--- ACH CONSISTENCY MATRIX ---")
        print(json.dumps(result["ach_matrix"], indent=2, ensure_ascii=False))

    print("\n--- AUDIT METRICS ---")
    print(json.dumps(result["metrics"], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())

