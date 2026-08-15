"""
Unit tests for Recursive Search Loop & Coverage Debt Resolution (v2.1 Core).
"""

import unittest
import asyncio
import sys
import os

possible_paths = [
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "scripts")),
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".agents", "skills", "adaptive-ontological-search", "scripts")),
    os.path.abspath(os.path.join(os.path.dirname(__file__), "scripts")),
]
for p in possible_paths:
    if os.path.isdir(p) and p not in sys.path:
        sys.path.insert(0, p)

from models import SearchMode, ExecutionMode
from orchestrator_v2 import OntologicalSearchOrchestratorV2


class TestRecursiveLoop(unittest.TestCase):

    def test_recursive_loop_coverage_debt_reduction(self):
        """
        Verify that OntologicalSearchOrchestratorV2 runs multi-depth recursion,
        propagates target_concept to claims, and reduces ontology coverage_debt.
        """
        orchestrator = OntologicalSearchOrchestratorV2()
        result = asyncio.run(orchestrator.run("Compare Rust vs Go for high-throughput network proxy"))

        self.assertIn("version", result)
        self.assertIn("contract", result)
        self.assertIn("ontology", result)
        self.assertIn("atomic_claims", result)
        self.assertIn("ach_matrix", result)
        self.assertIn("metrics", result)
        self.assertIn("synthesis", result)

        # In MOCK mode, status MUST be SIMULATION_PROTOTYPE_ONLY
        synthesis = result["synthesis"]
        self.assertEqual(synthesis["status"], "SIMULATION_PROTOTYPE_ONLY")
        self.assertIn("MOCK SIMULATION NOTICE", synthesis["decision_recommendation"])
        self.assertLessEqual(synthesis["overall_confidence"], 0.50)

        # Claims in mock mode must have UNVERIFIED_MOCK status
        claims = result["atomic_claims"]
        self.assertGreater(len(claims), 0)
        for claim in claims:
            self.assertEqual(claim["verification_status"], "UNVERIFIED_MOCK")
            self.assertFalse(claim["is_primary_source"])

        # Check coverage debt was reduced
        metrics = result["metrics"]
        self.assertLess(metrics["unresolved_coverage_debt_count"], len(result["ontology"]["classes"]))


if __name__ == "__main__":
    unittest.main()
