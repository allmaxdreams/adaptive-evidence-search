"""
CLI Entrypoint for Adaptive Ontology-Driven Evidence Search Orchestrator.
"""

import sys
import asyncio
import json
from orchestrator import OntologicalSearchOrchestrator


async def main():
    question = sys.argv[1] if len(sys.argv) > 1 else "Identify hidden supply chain vulnerabilities and undisclosed FPGA R&D initiatives in next-gen autonomous drone platforms"
    
    orchestrator = OntologicalSearchOrchestrator()
    result = await orchestrator.run(question)
    
    print("\n--- FINAL SYNTHESIS REPORT ---")
    print(json.dumps(result["synthesis"], indent=2, ensure_ascii=False))

    print("\n--- AUDIT METRICS ---")
    print(json.dumps(result["metrics"], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
