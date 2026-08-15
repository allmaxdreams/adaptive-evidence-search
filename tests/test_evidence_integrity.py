"""
Unit tests for Evidence Integrity, Fail-Closed LIVE mode, & Root Provenance Deduplication.
"""

import unittest
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

from models import (
    AtomicClaim, VerificationStatus, HypothesisSet, SingleHypothesis, QueryPortfolio, QueryItem
)
from ach_engine import ACHHeuerEngine
from deep_research_adapter import GeminiDeepResearchAdapter
from config import SearchConfig


class TestEvidenceIntegrity(unittest.TestCase):

    def setUp(self):
        self.engine = ACHHeuerEngine(inconclusive_threshold=0.40, min_corroboration_support=0.30)
        self.hypotheses = HypothesisSet(
            primary_h1=SingleHypothesis(id="H1", statement="PostgreSQL is superior for single-region OLTP."),
            alternative_h2=SingleHypothesis(id="H2", statement="CockroachDB is superior for multi-region Raft."),
            null_h0=SingleHypothesis(id="H0", statement="Neither database provides structural advantage.")
        )

    def test_mock_claims_have_unverified_status(self):
        """Verify that simulation claims are explicitly tagged UNVERIFIED_MOCK."""
        claim = AtomicClaim(
            id="mock_1",
            subject="PostgreSQL",
            predicate="operates_in",
            object="Financial Ledger",
            grounded_summary="SIMULATION FIXTURE: Mock payload",
            source_url="simulation://local/mock",
            source_title="Mock Document",
            source_domain="simulation.local",
            locator="para_1",
            retrieval_timestamp="2026-08-14T22:00:00Z",
            upstream_origin_id="mock_cluster",
            verification_status=VerificationStatus.UNVERIFIED_MOCK,
            is_primary_source=False,
            confidence=0.50,
            target_hypothesis="H1"
        )
        self.assertEqual(claim.verification_status, VerificationStatus.UNVERIFIED_MOCK)
        self.assertFalse(claim.is_primary_source)

    def test_live_adapter_fails_closed_without_credentials_or_dummy_key(self):
        """
        Verify that LIVE_RETRIEVAL mode fails closed with RuntimeError if credentials/key are missing or dummy,
        rather than fabricating fake live URLs.
        """
        for invalid_key in [None, "", "dummy", "DUMMY"]:
            adapter = GeminiDeepResearchAdapter(api_key=invalid_key)
            adapter.is_live = True

            portfolio = QueryPortfolio(queries=[QueryItem(text="test query", strategy="Direct", target_hypothesis="H1")])
            
            import asyncio
            with self.assertRaises(RuntimeError) as ctx:
                asyncio.run(adapter.execute_deep_research("test query", portfolio))
            
            self.assertIn("failed-closed", str(ctx.exception))

    def test_missing_grounding_supports_fails_closed(self):
        """
        Verify that if Gemini returns search chunks but no segment-level groundingSupports,
        the adapter fails closed rather than duplicating text across all chunks.
        """
        adapter = GeminiDeepResearchAdapter(api_key="valid_key")
        adapter.is_live = True

        unsourced_api_response = {
            "candidates": [{
                "content": {
                    "parts": [{"text": "PostgreSQL has ACID. CockroachDB has Raft."}]
                },
                "groundingMetadata": {
                    "groundingChunks": [
                        {"web": {"uri": "https://a.example", "title": "Source A"}},
                        {"web": {"uri": "https://b.example", "title": "Source B"}}
                    ],
                    # groundingSupports is intentionally absent!
                }
            }]
        }
        query = QueryItem(text="test query", strategy="Direct", target_hypothesis="H1")
        with self.assertRaises(RuntimeError) as ctx:
            adapter.parse_grounded_response(unsourced_api_response, query, "2026-08-14T23:00:00Z")
        self.assertIn("groundingSupports", str(ctx.exception))

    def test_multi_source_grounding_supports_parsing(self):
        """
        Fixture test verifying that Gemini Search Grounding responses with groundingSupports
        properly segment and attribute claims to multiple independent citations.
        """
        adapter = GeminiDeepResearchAdapter(api_key="valid_test_key")
        adapter.is_live = True

        mock_api_response = {
            "candidates": [{
                "content": {
                    "parts": [{
                        "text": "PostgreSQL provides standard ACID isolation. In contrast, CockroachDB implements distributed multi-region Raft consensus."
                    }]
                },
                "groundingMetadata": {
                    "groundingChunks": [
                        {"web": {"uri": "https://postgresql.org/docs/acid", "title": "PostgreSQL ACID Docs"}},
                        {"web": {"uri": "https://cockroachlabs.com/docs/raft", "title": "CockroachDB Raft Consensus"}}
                    ],
                    "groundingSupports": [
                        {
                            "segment": {"startIndex": 0, "endIndex": 47},
                            "groundingChunkIndices": [0]
                        },
                        {
                            "segment": {"startIndex": 48, "endIndex": 125},
                            "groundingChunkIndices": [1]
                        }
                    ]
                }
            }]
        }

        query = QueryItem(text="Compare PostgreSQL ACID vs CockroachDB Raft", strategy="Direct", target_hypothesis="H1")
        docs = adapter.parse_grounded_response(mock_api_response, query, "2026-08-14T23:00:00Z")

        self.assertEqual(len(docs), 2)
        # First segment
        self.assertEqual(docs[0]["source_url"], "https://postgresql.org/docs/acid")
        self.assertEqual(docs[0]["source_domain"], "postgresql.org")
        self.assertIn("PostgreSQL provides standard ACID", docs[0]["document_text"])

        # Second segment
        self.assertEqual(docs[1]["source_url"], "https://cockroachlabs.com/docs/raft")
        self.assertEqual(docs[1]["source_domain"], "cockroachlabs.com")
        self.assertIn("CockroachDB implements distributed", docs[1]["document_text"])

    def test_root_provenance_deduplication(self):
        """
        Verify that 10 duplicate articles copying the exact same press release (same upstream_origin_id)
        are collapsed into a single effective evidence cluster (total cluster weight = 1.0).
        """
        echo_claims = [
            AtomicClaim(
                id=f"echo_{i}",
                subject="CockroachDB",
                predicate="claims_instant_failover",
                object="Global Multi-DC",
                grounded_summary=f"Echo quote {i}",
                source_url=f"https://blog{i}.com/post",
                source_title=f"Blog Post {i}",
                source_domain=f"blog{i}.com",
                locator="p_1",
                retrieval_timestamp="2026-08-14T22:00:00Z",
                upstream_origin_id="press_release_pr_101",
                verification_status=VerificationStatus.VERIFIED_SECONDARY,
                is_primary_source=False,
                confidence=0.90,
                target_hypothesis="H2",
                inconsistency_ratings={"H1": -1.0, "H2": 0.5, "H0": -1.0}
            )
            for i in range(10)
        ]

        independent_claim = AtomicClaim(
            id="indep_1",
            subject="CockroachDB",
            predicate="incurs_wan_latency_penalty",
            object="45ms under Raft",
            grounded_summary="Empirical benchmark showed 45ms latency under WAN consensus.",
            source_url="https://dba-audits.org/benchmark",
            source_title="Independent DBA Benchmark 2026",
            source_domain="dba-audits.org",
            locator="section_4",
            retrieval_timestamp="2026-08-14T22:00:00Z",
            upstream_origin_id="dba_audit_lab_origin",
            verification_status=VerificationStatus.VERIFIED_PRIMARY,
            is_primary_source=True,
            confidence=0.95,
            target_hypothesis="H0",
            inconsistency_ratings={"H1": 0.5, "H2": -2.0, "H0": 0.5}
        )

        from evidence_policy import EvidencePolicy
        from models import ResearchContract, DynamicOntology, SearchMode, ExecutionMode

        contract = ResearchContract(
            question="Compare CockroachDB vs PostgreSQL", decision_context="DB", target_object="Database",
            required_precision="Standard", output_format="Brief",
            search_mode=SearchMode.RECURSIVE_EVIDENCE_SEARCH, execution_mode=ExecutionMode.LIVE
        )
        ontology = DynamicOntology(domain_name="DB", classes=["CockroachDB", "PostgreSQL"], coverage_debt=[])

        all_claims = echo_claims + [independent_claim]
        evidence_set = EvidencePolicy.validate_claims(contract, ontology, all_claims, self.hypotheses)
        matrix = self.engine.evaluate_matrix(self.hypotheses, evidence_set)

        self.assertLessEqual(matrix.h2_positive_support, 0.60)
        self.assertGreater(matrix.h2_inconsistency_penalty, 1.0)


if __name__ == "__main__":
    unittest.main()
