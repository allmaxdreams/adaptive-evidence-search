"""
Unit tests for ACH Safety Gates, Zero-Evidence Prevention, Synthesis Blocking,
Risk Lens Deduplication, MOCK Zero-Bias, Idiom & Contextual Latency/Cost Handling,
Subject Entity Resolution, Structured Proposition Extraction, Entity-Driven Stance Classification,
Comparison Intent Parsing, C++/C# Boundary Matching, Dynamic Relations, Collision Resolution,
and Strict Evidenced vs Searched Coverage Gates (v2.1 Core).
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

from models import (
    AtomicClaim, VerificationStatus, HypothesisSet, SingleHypothesis, RiskLens,
    ResearchContract, DynamicOntology, SearchMode, ExecutionMode, AuditMetrics,
    EntityDefinition, ComparisonIntent, QueryItem, PrecisionLevel, EvidenceRequirements,
    ACHMatrix, GateDecision, ValidatedClaim, ValidatedEvidenceSet, SearchQueryRecord
)
from ach_engine import ACHHeuerEngine
from deep_research_adapter import GeminiDeepResearchAdapter
from evidence_policy import EvidencePolicy, check_primary_authority, PRIMARY_AUTHORITY_REGISTRY, is_source_url_allowed, normalize_source
from orchestrator_v2 import OntologicalSearchOrchestratorV2
from vc_due_diligence_orchestrator import VCDueDiligenceOrchestrator, StartupProfile


class TestACHSafetyGates(unittest.TestCase):

    def setUp(self):
        self.engine = ACHHeuerEngine(inconclusive_threshold=0.40, min_corroboration_support=0.30)
        self.hypotheses = HypothesisSet(
            primary_h1=SingleHypothesis(id="H1", statement="Solar Storage Tech A is viable."),
            alternative_h2=SingleHypothesis(id="H2", statement="Solar Storage Tech B is viable."),
            null_h0=SingleHypothesis(id="H0", statement="Neither tech provides viable storage efficiency."),
            risk_lenses=[
                RiskLens(id="REGULATORY_COMPLIANCE", name="Regulatory Risk", description="Compliance requirements."),
                RiskLens(id="SUPPLY_CHAIN", name="Supply Chain Risk", description="Raw material sourcing.")
            ],
            entity_registry={
                "H1": EntityDefinition(id="tech_a", name="Solar Storage Tech A", aliases=["Solar Storage Tech A", "Tech A"]),
                "H2": EntityDefinition(id="tech_b", name="Solar Storage Tech B", aliases=["Solar Storage Tech B", "Tech B"])
            }
        )

    def _val(self, claims, hypotheses=None, precision="Standard", allowed_sources=None, execution_mode=ExecutionMode.LIVE):
        contract = ResearchContract(
            question="Test Evaluation", decision_context="Context", target_object="Object",
            required_precision=precision, output_format="Brief",
            allowed_sources=allowed_sources or [],
            search_mode=SearchMode.RECURSIVE_EVIDENCE_SEARCH, execution_mode=execution_mode
        )
        ontology = DynamicOntology(
            domain_name="Test Domain",
            classes=[
                "CockroachDB", "PostgreSQL", "MySQL", "Rust", "Go", "Tech A", "Tech B",
                "Solar Storage Tech A", "Solar Storage Tech B", "RelationalDatabaseEngine",
                "DistributedConsensusProtocol", "TransactionIsolationLevel"
            ],
            coverage_debt=[]
        )
        return EvidencePolicy.validate_claims(contract, ontology, claims, hypotheses or self.hypotheses)

    def test_known_pair_does_not_override_user_request(self):
        """
        [P0] Verify that 'Compare PostgreSQL vs MySQL' does NOT get rewritten to PostgreSQL vs CockroachDB,
        and 'CockroachDB vs YugabyteDB' does NOT get rewritten to PostgreSQL vs CockroachDB.
        """
        orchestrator = OntologicalSearchOrchestratorV2()
        
        # PostgreSQL vs MySQL
        intent = orchestrator.parse_comparison_intent("Compare PostgreSQL vs MySQL for web backend")
        e1, e2, ctx = intent
        self.assertEqual(e1.name, "PostgreSQL")
        self.assertEqual(e2.name, "MySQL")
        self.assertIn("Postgres", e1.aliases)
        self.assertIn("InnoDB", e2.aliases)

        # CockroachDB vs YugabyteDB
        intent2 = orchestrator.parse_comparison_intent("CockroachDB vs YugabyteDB for multi-region")
        e3, e4, ctx2 = intent2
        self.assertEqual(e3.name, "CockroachDB")
        self.assertEqual(e4.name, "YugabyteDB")
        self.assertIn("CRDB", e3.aliases)
        self.assertIn("YSQL", e4.aliases)

    def test_abstract_ontology_class_as_subject_has_zero_bias(self):
        """
        [P0] Verify that when a statement discusses an abstract class (e.g. 'RelationalDatabaseEngine is certified'),
        it is NOT attributed to PostgreSQL or MySQL, but resolved as UNKNOWN with 0/0/0 ratings.
        """
        orchestrator = OntologicalSearchOrchestratorV2()
        q = "Compare PostgreSQL vs MySQL"
        e1, e2, ctx = orchestrator.parse_comparison_intent(q)
        hyp_set = HypothesisSet(
            primary_h1=SingleHypothesis(id="H1", statement="PostgreSQL is superior."),
            alternative_h2=SingleHypothesis(id="H2", statement="MySQL is superior."),
            null_h0=SingleHypothesis(id="H0", statement="Neither is superior."),
            entity_registry={"H1": e1, "H2": e2}
        )
        ontology = DynamicOntology(domain_name="DB", classes=["RelationalDatabaseEngine"], coverage_debt=[])

        doc = {
            "document_text": "RelationalDatabaseEngine is certified and guarantees transactional durability.",
            "target_concept": "RelationalDatabaseEngine",
            "target_hypothesis": "H1",
            "source_title": "DB Overview",
            "source_url": "https://db.org",
            "source_domain": "db.org",
            "upstream_origin_id": "origin_db"
        }

        claims = asyncio.run(orchestrator.extract_atomic_claims(
            q, ontology, hyp_set, [doc], ExecutionMode.LIVE
        ))

        self.assertGreaterEqual(len(claims), 1)
        for c in claims:
            self.assertEqual(c.subject, "RelationalDatabaseEngine")
            self.assertEqual(c.subject_entity_id, "relationaldatabaseengine")
            self.assertEqual(c.inconsistency_ratings, {"H1": 0.0, "H2": 0.0, "H0": 0.0})

    def test_database_ontology_dynamic_relations_no_cockroach_in_postgres_mysql(self):
        """
        [P0] Verify that auto_induce_ontology generates relations dynamically for the requested pair (PostgreSQL vs MySQL)
        and does NOT inject irrelevant CockroachDB relations.
        """
        orchestrator = OntologicalSearchOrchestratorV2()
        contract = ResearchContract(
            question="Compare PostgreSQL vs MySQL", decision_context="DB",
            target_object="PostgreSQL vs MySQL", required_precision="High", output_format="Brief",
            search_mode=SearchMode.RECURSIVE_EVIDENCE_SEARCH, execution_mode=ExecutionMode.LIVE
        )
        ontology = asyncio.run(orchestrator.auto_induce_ontology("Compare PostgreSQL vs MySQL", contract))

        sources = [r.source_entity for r in ontology.dynamic_relations]
        targets = [r.target_entity for r in ontology.dynamic_relations]
        all_rel_entities = set(sources + targets)

        self.assertIn("PostgreSQL", all_rel_entities)
        self.assertIn("MySQL", all_rel_entities)
        self.assertNotIn("CockroachDB", all_rel_entities)

    def test_research_and_development_vs_operations_splitting(self):
        """
        [P1] Verify that 'Compare Research and Development vs Operations' correctly parses
        Entity A = 'Research and Development', Entity B = 'Operations' (strong 'vs' takes precedence over 'and').
        """
        orchestrator = OntologicalSearchOrchestratorV2()
        intent = orchestrator.parse_comparison_intent("Compare Research and Development vs Operations")
        
        self.assertTrue(intent.is_comparison)
        self.assertEqual(intent.e1.name, "Research and Development")
        self.assertEqual(intent.e2.name, "Operations")

    def test_non_comparative_query_single_target(self):
        """
        [P1] Verify that a single-target non-comparative query like 'Rust ownership'
        does NOT fabricate a comparison alternative.
        """
        orchestrator = OntologicalSearchOrchestratorV2()
        intent = orchestrator.parse_comparison_intent("Rust ownership")
        
        self.assertFalse(intent.is_comparison)
        self.assertEqual(intent.e1.name, "Rust ownership")
        self.assertIsNone(intent.e2)

        contract = asyncio.run(orchestrator.create_research_contract("Rust ownership", SearchMode.DIRECT_LOOKUP))
        self.assertEqual(contract.target_object, "Rust ownership")

    def test_searched_vs_evidenced_coverage_debt_strict_gate(self):
        """
        [P1] Verify that non-diagnostic claims (ratings 0/0/0) do NOT clear coverage debt in LIVE mode,
        while diagnostic claims (ratings > 0) properly resolve it.
        """
        orchestrator = OntologicalSearchOrchestratorV2()
        ontology = DynamicOntology(
            domain_name="Distributed DB",
            classes=["RelationalDatabaseEngine", "DistributedConsensusProtocol"],
            coverage_debt=["RelationalDatabaseEngine", "DistributedConsensusProtocol"]
        )

        contract = ResearchContract(
            question="PostgreSQL vs CockroachDB", decision_context="DB Selection",
            target_object="PostgreSQL vs CockroachDB", required_precision="High", output_format="Brief",
            search_mode=SearchMode.RECURSIVE_EVIDENCE_SEARCH, execution_mode=ExecutionMode.LIVE
        )

        # 1. Claim targeting RelationalDatabaseEngine but with 0/0/0 neutral ratings
        neutral_claim = AtomicClaim(
            id="c_neutral", subject="RelationalDatabaseEngine", subject_entity_id="relationaldatabaseengine",
            target_concept="RelationalDatabaseEngine", covered_ontology_classes=["RelationalDatabaseEngine"],
            predicate="exhibits_property", object="overview",
            source_url="https://postgres.org", source_title="PG", source_domain="postgres.org", locator="p1",
            retrieval_timestamp="2026-08-15T00:00:00Z", upstream_origin_id="postgres.org",
            verification_status=VerificationStatus.VERIFIED_SECONDARY, is_primary_source=False,
            confidence=0.85, target_hypothesis="H1",
            inconsistency_ratings={"H1": 0.0, "H2": 0.0, "H0": 0.0}
        )

        matrix = self.engine.evaluate_matrix(self.hypotheses, self._val([neutral_claim]))
        metrics_1 = asyncio.run(orchestrator.evaluate_stopping_rules(
            contract, ontology, [neutral_claim], matrix, current_depth=1, effective_max_depth=3
        ))

        # Debt MUST remain 2 because the claim has 0 diagnostic impact!
        self.assertEqual(len(ontology.coverage_debt), 2)
        self.assertEqual(metrics_1.searched_classes_count, 1)
        self.assertEqual(metrics_1.evidenced_classes_count, 0)

        # 2. Now add a substantive diagnostic claim
        diagnostic_claim = AtomicClaim(
            id="c_diag", subject="PostgreSQL", subject_entity_id="postgresql",
            target_concept="RelationalDatabaseEngine", covered_ontology_classes=["RelationalDatabaseEngine"],
            predicate="has_certification_status", object="certified / production ready",
            source_url="https://postgres.org", source_title="PG", source_domain="postgres.org", locator="p1",
            retrieval_timestamp="2026-08-15T00:00:00Z", upstream_origin_id="postgres.org",
            verification_status=VerificationStatus.VERIFIED_SECONDARY, is_primary_source=False,
            confidence=0.85, target_hypothesis="H1",
            inconsistency_ratings={"H1": 0.5, "H2": -0.5, "H0": -1.0}
        )

        matrix_2 = self.engine.evaluate_matrix(self.hypotheses, self._val([neutral_claim, diagnostic_claim]))
        metrics_2 = asyncio.run(orchestrator.evaluate_stopping_rules(
            contract, ontology, [neutral_claim, diagnostic_claim], matrix_2, current_depth=1, effective_max_depth=3
        ))

        # Debt now reduces from 2 to 1!
        self.assertEqual(len(ontology.coverage_debt), 1)
        self.assertEqual(ontology.coverage_debt, ["DistributedConsensusProtocol"])
        self.assertEqual(metrics_2.evidenced_classes_count, 1)

    def test_live_coverage_debt_reduction_via_target_concept(self):
        """
        [P0] Verify that in LIVE mode (where upstream_origin_id is a web domain),
        claims carrying target_concept reduce coverage debt in ontology.
        """
        orchestrator = OntologicalSearchOrchestratorV2()
        ontology = DynamicOntology(
            domain_name="Distributed DB",
            classes=["RelationalDatabaseEngine", "DistributedConsensusProtocol", "TransactionIsolationLevel"],
            coverage_debt=["RelationalDatabaseEngine", "DistributedConsensusProtocol", "TransactionIsolationLevel"]
        )

        contract = ResearchContract(
            question="PostgreSQL vs CockroachDB", decision_context="DB Selection",
            target_object="PostgreSQL vs CockroachDB", required_precision="High", output_format="Brief",
            search_mode=SearchMode.RECURSIVE_EVIDENCE_SEARCH, execution_mode=ExecutionMode.LIVE
        )

        # Claims from live web domains with target_concept attached and diagnostic ratings
        live_claims = [
            AtomicClaim(
                id="c1", subject="PostgreSQL", subject_entity_id="postgresql",
                target_concept="RelationalDatabaseEngine", covered_ontology_classes=["RelationalDatabaseEngine"],
                predicate="has_certification_status", object="certified / production ready",
                source_url="https://postgres.org", source_title="PG", source_domain="postgres.org", locator="p1",
                retrieval_timestamp="2026-08-14T23:00:00Z", upstream_origin_id="postgres.org",
                verification_status=VerificationStatus.VERIFIED_SECONDARY, is_primary_source=False,
                confidence=0.85, target_hypothesis="H1",
                inconsistency_ratings={"H1": 0.5, "H2": -0.5, "H0": -1.0}
            ),
            AtomicClaim(
                id="c2", subject="CockroachDB", subject_entity_id="cockroachdb",
                target_concept="DistributedConsensusProtocol", covered_ontology_classes=["DistributedConsensusProtocol"],
                predicate="implements_consensus", object="Raft consensus",
                source_url="https://cockroachlabs.com", source_title="CRDB", source_domain="cockroachlabs.com", locator="p1",
                retrieval_timestamp="2026-08-14T23:00:00Z", upstream_origin_id="cockroachlabs.com",
                verification_status=VerificationStatus.VERIFIED_SECONDARY, is_primary_source=False,
                confidence=0.85, target_hypothesis="H2",
                inconsistency_ratings={"H1": -0.5, "H2": 0.5, "H0": -1.0}
            )
        ]

        matrix = self.engine.evaluate_matrix(self.hypotheses, self._val(live_claims))
        metrics = asyncio.run(orchestrator.evaluate_stopping_rules(
            contract, ontology, live_claims, matrix, current_depth=1, effective_max_depth=3
        ))

        # 2 out of 3 debt items must be resolved!
        self.assertEqual(len(ontology.coverage_debt), 1)
        self.assertEqual(ontology.coverage_debt, ["TransactionIsolationLevel"])
        self.assertEqual(metrics.unresolved_coverage_debt_count, 1)

    def test_which_is_better_question_intent_parsing(self):
        """
        [P1] Verify that 'Which is better, Rust or Go for proxy' parses cleanly into
        Entity A = 'Rust', Entity B = 'Go', and sets target_object = 'Rust vs Go'.
        """
        orchestrator = OntologicalSearchOrchestratorV2()
        q = "Which is better, Rust or Go for proxy"
        e1, e2, ctx = orchestrator.parse_comparison_intent(q)
        
        self.assertEqual(e1.name, "Rust")
        self.assertEqual(e2.name, "Go")
        self.assertEqual(ctx, "proxy")

        contract = asyncio.run(orchestrator.create_research_contract(q, SearchMode.RECURSIVE_EVIDENCE_SEARCH))
        self.assertEqual(contract.target_object, "Rust vs Go")

    def test_c_plus_plus_and_c_sharp_boundary_matching(self):
        """
        [P1] Verify that C++ and C# match accurately without being broken by word boundaries.
        """
        orchestrator = OntologicalSearchOrchestratorV2()
        q = "Compare C++ vs Rust for network engine"
        e1, e2, ctx = orchestrator.parse_comparison_intent(q)
        
        self.assertEqual(e1.name, "C++")
        self.assertEqual(e2.name, "Rust")

        hyp_set = HypothesisSet(
            primary_h1=SingleHypothesis(id="H1", statement="C++ is superior."),
            alternative_h2=SingleHypothesis(id="H2", statement="Rust is superior."),
            null_h0=SingleHypothesis(id="H0", statement="Neither is superior."),
            entity_registry={"H1": e1, "H2": e2}
        )
        ontology = DynamicOntology(domain_name="Low Level", classes=["C++Architecture", "RustArchitecture"], coverage_debt=[])

        doc = {
            "document_text": "C++ is certified and has low latency under concurrent stress.",
            "target_concept": "C++Architecture",
            "target_hypothesis": "H1",
            "source_title": "C++ Study",
            "source_url": "https://cpp.org",
            "source_domain": "cpp.org",
            "upstream_origin_id": "origin_cpp"
        }

        claims = asyncio.run(orchestrator.extract_atomic_claims(
            q, ontology, hyp_set, [doc], ExecutionMode.LIVE
        ))

        self.assertEqual(len(claims), 2)
        self.assertEqual(claims[0].subject, "C++")
        self.assertEqual(claims[0].subject_entity_id, "c_plus")
        self.assertEqual(claims[0].target_hypothesis, "H1")
        self.assertEqual(claims[0].inconsistency_ratings["H1"], 0.5)

    def test_canonical_entity_id_stored_on_claims(self):
        """
        [P1] Verify that claim.subject_entity_id stores the canonical entity id ('postgresql'),
        while target_hypothesis stores the current role ('H1').
        """
        orchestrator = OntologicalSearchOrchestratorV2()
        contract = ResearchContract(
            question="PostgreSQL vs CockroachDB", decision_context="DB Selection",
            target_object="PostgreSQL vs CockroachDB", required_precision="High", output_format="Brief",
            search_mode=SearchMode.DIRECT_LOOKUP, execution_mode=ExecutionMode.LIVE
        )
        ontology = DynamicOntology(
            domain_name="DB",
            classes=["RelationalDatabaseEngine", "DistributedConsensusProtocol"],
            coverage_debt=[]
        )
        hyp_set = asyncio.run(orchestrator.formulate_hypotheses(contract, ontology))

        doc = {
            "document_text": "PostgreSQL is certified in production.",
            "target_concept": "RelationalDatabaseEngine",
            "target_hypothesis": "H1",
            "source_title": "PG",
            "source_url": "https://pg.org",
            "source_domain": "pg.org",
            "upstream_origin_id": "origin_pg"
        }

        claims = asyncio.run(orchestrator.extract_atomic_claims(
            contract.question, ontology, hyp_set, [doc], ExecutionMode.LIVE
        ))

        self.assertEqual(claims[0].subject_entity_id, "postgresql")
        self.assertEqual(claims[0].target_hypothesis, "H1")

    def test_triple_and_stance_polarity_consistency(self):
        """
        [P1] Verify that extracted triple objects strictly match stance polarity:
        - 'not only certified' -> object='certified / production ready', stance=+0.5 (not 'not certified'!)
        - 'cost-effective' -> object='cost-effective / low TCO', stance=+0.5 (not 'high TCO'!)
        """
        orchestrator = OntologicalSearchOrchestratorV2()
        
        # 1. Not only certified
        triples_1 = orchestrator._extract_proposition_triples(
            "Solar Storage Tech A is not only certified but production ready.",
            "Solar Storage Tech A", ["TechACore"], self.hypotheses.entity_registry
        )
        self.assertEqual(triples_1[0]["object"], "certified / production ready")
        self.assertTrue(triples_1[0]["is_positive"])

        # 2. Cost-effective
        triples_2 = orchestrator._extract_proposition_triples(
            "Solar Storage Tech A is cost-effective in high-volume deployment.",
            "Solar Storage Tech A", ["TechACore"], self.hypotheses.entity_registry
        )
        self.assertEqual(triples_2[0]["predicate"], "has_cost_efficiency")
        self.assertEqual(triples_2[0]["object"], "cost-effective / low TCO")
        self.assertTrue(triples_2[0]["is_positive"])

    def test_two_named_alternatives_split_with_and(self):
        """
        [P1] Verify that 'Tech A is certified and Tech B is expensive' is split into 2 separate claims
        with respective entity mappings.
        """
        orchestrator = OntologicalSearchOrchestratorV2()
        doc = {
            "document_text": "Tech A is certified and Tech B is expensive.",
            "target_concept": "TechACore",
            "target_hypothesis": "H1",
            "source_title": "Market Comparison",
            "source_url": "https://market.org/eval",
            "source_domain": "market.org",
            "upstream_origin_id": "origin_market"
        }
        ontology = DynamicOntology(domain_name="Tech", classes=["TechACore", "TechBCore"], coverage_debt=[])

        claims = asyncio.run(orchestrator.extract_atomic_claims(
            "Compare Tech A vs Tech B", ontology, self.hypotheses, [doc], ExecutionMode.LIVE
        ))

        self.assertEqual(len(claims), 2)
        c_a = next(c for c in claims if "Tech A" in c.subject)
        c_b = next(c for c in claims if "Tech B" in c.subject)

        # Tech A claim is positive for H1
        self.assertEqual(c_a.subject_entity_id, "tech_a")
        self.assertEqual(c_a.target_hypothesis, "H1")
        self.assertEqual(c_a.object, "certified / production ready")
        self.assertEqual(c_a.inconsistency_ratings["H1"], 0.5)

        # Tech B claim is negative for H2
        self.assertEqual(c_b.subject_entity_id, "tech_b")
        self.assertEqual(c_b.target_hypothesis, "H1")
        self.assertEqual(c_b.object, "high TCO / expensive")
        self.assertEqual(c_b.inconsistency_ratings["H2"], -1.5)

    def test_mock_claims_have_zero_ach_bias(self):
        """Verify that MOCK fixtures / UNVERIFIED text do NOT pollute ACH ratings."""
        orchestrator = OntologicalSearchOrchestratorV2()
        mock_ratings = orchestrator._derive_evidence_ratings(
            doc_text="SIMULATION FIXTURE: This payload is an UNVERIFIED test fixture for Tech A.",
            subject="Tech A",
            risk_lens_id=None,
            strategy="Ontological",
            hypotheses=self.hypotheses,
            is_mock=True
        )
        self.assertEqual(mock_ratings, {"H1": 0.0, "H2": 0.0, "H0": 0.0})

    def test_zero_evidence_hypothesis_cannot_win(self):
        """Verify that when zero evidence exists for any hypothesis, the ACH engine returns ALL_HYPOTHESES_UNTESTED."""
        matrix = self.engine.evaluate_matrix(self.hypotheses, [])
        self.assertTrue(matrix.is_inconclusive)
        self.assertEqual(matrix.winning_hypothesis, "ALL_HYPOTHESES_UNTESTED")

    def test_risk_lens_provenance_deduplication(self):
        """Verify that duplicate claims sharing the SAME upstream_origin_id do NOT elevate risk to HIGH."""
        duplicate_claims = [
            AtomicClaim(
                id=f"risk_c_{i}",
                subject="REGULATORY_COMPLIANCE",
                predicate="faces_pending_audit",
                object="Solar Regulatory Commission",
                grounded_summary="Grounded notice: Pending regulatory audit.",
                source_url=f"https://news{i}.com",
                source_title="News",
                source_domain=f"news{i}.com",
                locator="p1",
                retrieval_timestamp="2026-08-14T22:00:00Z",
                upstream_origin_id="single_press_release_origin",
                verification_status=VerificationStatus.VERIFIED_SECONDARY,
                is_primary_source=False,
                confidence=0.85,
                target_hypothesis="RISK_LENS",
                target_risk_lens_id="REGULATORY_COMPLIANCE",
                inconsistency_ratings={"H1": 0.0, "H2": 0.0, "H0": 0.0}
            )
            for i in range(3)
        ]

        matrix = self.engine.evaluate_matrix(self.hypotheses, self._val(duplicate_claims))
        reg_risk = next(r for r in matrix.evaluated_risk_lenses if r["lens_id"] == "REGULATORY_COMPLIANCE")
        
        self.assertEqual(reg_risk["risk_level"], "MEDIUM")
        self.assertEqual(reg_risk["independent_roots_count"], 1)

    def test_contextual_latency_classification(self):
        """
        [P0] Verify that 'low latency' and 'latency improved' are positive capabilities,
        while 'latency penalty' is a negative limitation.
        """
        orchestrator = OntologicalSearchOrchestratorV2()
        
        # Low latency -> positive
        r1 = orchestrator._derive_evidence_ratings(
            "Solar Storage Tech A has low latency under concurrent load.",
            "Solar Storage Tech A", None, "Direct", self.hypotheses, is_mock=False
        )
        self.assertEqual(r1["H1"], 0.5)

        # Latency improved -> positive
        r2 = orchestrator._derive_evidence_ratings(
            "Solar Storage Tech A latency improved by 50 percent in latest benchmark.",
            "Solar Storage Tech A", None, "Direct", self.hypotheses, is_mock=False
        )
        self.assertEqual(r2["H1"], 0.5)

        # Latency penalty -> negative
        r3 = orchestrator._derive_evidence_ratings(
            "Solar Storage Tech A incurs severe latency penalty across WAN replication.",
            "Solar Storage Tech A", None, "Direct", self.hypotheses, is_mock=False
        )
        self.assertEqual(r3["H1"], -1.5)

    def test_competitor_subject_isolation(self):
        """
        [P0] Verify that in 'The competitor is not certified, while Tech A is certified',
        the competitor's lack of certification is NOT assigned to Tech A.
        """
        orchestrator = OntologicalSearchOrchestratorV2()
        doc = {
            "document_text": "The competitor is not certified, while Solar Storage Tech A is certified.",
            "target_concept": "Solar Storage Tech A",
            "target_hypothesis": "H1",
            "source_title": "Comparison Report",
            "source_url": "https://report.com",
            "source_domain": "report.com",
            "upstream_origin_id": "origin_comp"
        }
        ontology = DynamicOntology(domain_name="Solar", classes=["Solar Storage Tech A", "Solar Storage Tech B"], coverage_debt=[])

        claims = asyncio.run(orchestrator.extract_atomic_claims(
            "Compare Solar", ontology, self.hypotheses, [doc], ExecutionMode.LIVE
        ))

        self.assertEqual(len(claims), 2)
        comp_claim = next(c for c in claims if c.subject == "Competitor")
        tech_a_claim = next(c for c in claims if c.subject == "Solar Storage Tech A")

        # Competitor claim must be neutral regarding Tech A (ratings 0/0/0)
        self.assertEqual(comp_claim.inconsistency_ratings, {"H1": 0.0, "H2": 0.0, "H0": 0.0})
        # Tech A claim must be positive
        self.assertEqual(tech_a_claim.inconsistency_ratings["H1"], 0.5)

    def test_neutral_h0_cannot_satisfy_coverage_gate(self):
        """
        [P1] Verify that having diagnostic H1 and H2 evidence BUT only neutral (0/0/0) H0 evidence
        strictly keeps stopping_rule_met as False.
        """
        orchestrator = OntologicalSearchOrchestratorV2()
        
        # Diagnostic H1 claim
        h1_claim = AtomicClaim(
            id="c1", subject="Solar Storage Tech A", predicate="has_certification_status", object="certified",
            grounded_summary="Certified by ISO", source_url="https://a.org",
            source_title="A", source_domain="a.org", locator="p1",
            retrieval_timestamp="2026-08-14T22:00:00Z", upstream_origin_id="org_a",
            verification_status=VerificationStatus.VERIFIED_SECONDARY, is_primary_source=False,
            confidence=0.85, target_hypothesis="H1",
            inconsistency_ratings={"H1": 0.5, "H2": -0.5, "H0": -1.0}
        )
        # Diagnostic H2 claim
        h2_claim = AtomicClaim(
            id="c2", subject="Solar Storage Tech B", predicate="has_certification_status", object="certified",
            grounded_summary="Certified by TUV", source_url="https://b.org",
            source_title="B", source_domain="b.org", locator="p1",
            retrieval_timestamp="2026-08-14T22:00:00Z", upstream_origin_id="org_b",
            verification_status=VerificationStatus.VERIFIED_SECONDARY, is_primary_source=False,
            confidence=0.85, target_hypothesis="H2",
            inconsistency_ratings={"H1": -0.5, "H2": 0.5, "H0": -1.0}
        )
        # Neutral H0 claim (ratings 0/0/0)
        h0_neutral_claim = AtomicClaim(
            id="c3", subject="Solar Market", predicate="exhibits_property", object="overview",
            grounded_summary="General summary of energy storage market.", source_url="https://c.org",
            source_title="C", source_domain="c.org", locator="p1",
            retrieval_timestamp="2026-08-14T22:00:00Z", upstream_origin_id="org_c",
            verification_status=VerificationStatus.VERIFIED_SECONDARY, is_primary_source=False,
            confidence=0.85, target_hypothesis="H0",
            inconsistency_ratings={"H1": 0.0, "H2": 0.0, "H0": 0.0}
        )

        all_claims = [h1_claim, h2_claim, h0_neutral_claim]
        contract = ResearchContract(
            question="Solar Tech A vs B", decision_context="Tech Selection",
            target_object="Solar", required_precision="High", output_format="Brief",
            search_mode=SearchMode.RECURSIVE_EVIDENCE_SEARCH, execution_mode=ExecutionMode.LIVE
        )
        ontology = DynamicOntology(domain_name="Solar", classes=["Solar Storage Tech A", "Solar Storage Tech B"], coverage_debt=[])
        matrix = self.engine.evaluate_matrix(self.hypotheses, self._val(all_claims))

        metrics = asyncio.run(orchestrator.evaluate_stopping_rules(
            contract, ontology, all_claims, matrix, current_depth=1, effective_max_depth=3
        ))

        self.assertFalse(metrics.stopping_rule_met)
        self.assertTrue(metrics.counterevidence_searched)

    def test_h1_only_evidence_without_h0_search_blocks_stopping(self):
        """
        [P0] Verify that having 3 independent positive H1 claims with a conclusive ACH matrix
        strictly BLOCKS stopping_rule_met (False) when counterevidence/H0 search was never attempted.
        """
        orchestrator = OntologicalSearchOrchestratorV2()
        
        # 3 independent H1 claims
        h1_claims = [
            AtomicClaim(
                id=f"c_h1_{i}", subject="Solar Storage Tech A", predicate="has_certification_status", object="certified",
                grounded_summary=f"Certified in benchmark {i}", source_url=f"https://source{i}.org",
                source_title=f"Source {i}", source_domain=f"source{i}.org", locator="p1",
                retrieval_timestamp="2026-08-15T00:00:00Z", upstream_origin_id=f"independent_origin_{i}",
                verification_status=VerificationStatus.VERIFIED_SECONDARY, is_primary_source=False,
                confidence=0.90, target_hypothesis="H1",
                inconsistency_ratings={"H1": 0.5, "H2": -0.5, "H0": -1.0}
            )
            for i in range(3)
        ]

        contract = ResearchContract(
            question="Solar Tech A vs B", decision_context="Tech Selection",
            target_object="Solar", required_precision="High", output_format="Brief",
            search_mode=SearchMode.RECURSIVE_EVIDENCE_SEARCH, execution_mode=ExecutionMode.LIVE
        )
        ontology = DynamicOntology(domain_name="Solar", classes=["Solar Storage Tech A"], coverage_debt=[])
        matrix = self.engine.evaluate_matrix(self.hypotheses, self._val(h1_claims))

        # Matrix is conclusive for H1
        self.assertFalse(matrix.is_inconclusive)
        self.assertEqual(matrix.winning_hypothesis, "H1")

        metrics = asyncio.run(orchestrator.evaluate_stopping_rules(
            contract, ontology, h1_claims, matrix, current_depth=1, effective_max_depth=3
        ))

        # MUST BE BLOCKED because counterevidence/H0 was never searched!
        self.assertFalse(metrics.counterevidence_searched)
        self.assertFalse(metrics.stopping_rule_met)
        self.assertIn("Continue recursive pass", metrics.recommended_next_step)

    def test_search_mode_boundary_matching(self):
        """
        [P1] Verify that word-boundary checking prevents false recursive search triggers
        for queries containing substring 'or' (e.g. work, Oracle, performance).
        """
        orchestrator = OntologicalSearchOrchestratorV2()
        
        mode_1 = asyncio.run(orchestrator.select_search_mode("How does ownership work in Rust?"))
        self.assertEqual(mode_1, SearchMode.STRUCTURED_SEARCH)

        mode_2 = asyncio.run(orchestrator.select_search_mode("Oracle backup strategy"))
        self.assertEqual(mode_2, SearchMode.DIRECT_LOOKUP)

        mode_3 = asyncio.run(orchestrator.select_search_mode("Performance tuning guide"))
        self.assertEqual(mode_3, SearchMode.DIRECT_LOOKUP)

        mode_4 = asyncio.run(orchestrator.select_search_mode("Compare Rust vs Go"))
        self.assertEqual(mode_4, SearchMode.RECURSIVE_EVIDENCE_SEARCH)

    def test_compare_a_and_b_single_letter_entities(self):
        """
        [P1] Verify that 'Compare A and B' correctly parses Entity A = 'A', Entity B = 'B',
        without eating single-letter tokens as articles.
        """
        orchestrator = OntologicalSearchOrchestratorV2()
        intent = orchestrator.parse_comparison_intent("Compare A and B")
        
        self.assertTrue(intent.is_comparison)
        self.assertEqual(intent.e1.name, "A")
        self.assertEqual(intent.e2.name, "B")

    def test_database_architecture_symmetric_classification(self):
        """
        [P1] Verify that database architecture mapping is fully symmetric regardless of entity order.
        """
        orchestrator = OntologicalSearchOrchestratorV2()
        contract = ResearchContract(
            question="DB Test", decision_context="DB", target_object="DB",
            required_precision="High", output_format="Brief",
            search_mode=SearchMode.RECURSIVE_EVIDENCE_SEARCH, execution_mode=ExecutionMode.LIVE
        )

        # 1. CockroachDB vs PostgreSQL
        onto_1 = asyncio.run(orchestrator.auto_induce_ontology("Compare CockroachDB vs PostgreSQL", contract))
        rel_crdb_1 = next(r for r in onto_1.dynamic_relations if r.source_entity == "CockroachDB" and r.relation_type == "implements_architecture")
        rel_pg_1 = next(r for r in onto_1.dynamic_relations if r.source_entity == "PostgreSQL" and r.relation_type == "implements_architecture")
        self.assertEqual(rel_crdb_1.target_entity, "DistributedConsensusProtocol")
        self.assertEqual(rel_pg_1.target_entity, "RelationalDatabaseEngine")

        # 2. PostgreSQL vs CockroachDB
        onto_2 = asyncio.run(orchestrator.auto_induce_ontology("Compare PostgreSQL vs CockroachDB", contract))
        rel_pg_2 = next(r for r in onto_2.dynamic_relations if r.source_entity == "PostgreSQL" and r.relation_type == "implements_architecture")
        rel_crdb_2 = next(r for r in onto_2.dynamic_relations if r.source_entity == "CockroachDB" and r.relation_type == "implements_architecture")
        self.assertEqual(rel_pg_2.target_entity, "RelationalDatabaseEngine")
        self.assertEqual(rel_crdb_2.target_entity, "DistributedConsensusProtocol")

    def test_primary_claim_without_diagnostic_value_does_not_clear_debt(self):
        """
        [P1] Verify that a high-confidence VERIFIED_PRIMARY claim with 0/0/0 ratings and unknown subject
        does NOT clear coverage debt in LIVE mode.
        """
        orchestrator = OntologicalSearchOrchestratorV2()
        ontology = DynamicOntology(
            domain_name="DB",
            classes=["RelationalDatabaseEngine"],
            coverage_debt=["RelationalDatabaseEngine"]
        )
        contract = ResearchContract(
            question="DB Test", decision_context="DB", target_object="DB",
            required_precision="High", output_format="Brief",
            search_mode=SearchMode.RECURSIVE_EVIDENCE_SEARCH, execution_mode=ExecutionMode.LIVE
        )

        primary_neutral_claim = AtomicClaim(
            id="c_pri_neutral", subject="UNKNOWN", subject_entity_id="unknown",
            target_concept="RelationalDatabaseEngine", covered_ontology_classes=["RelationalDatabaseEngine"],
            predicate="exhibits_property", object="general doc",
            source_url="https://gov.ua", source_title="Gov Doc", source_domain="gov.ua", locator="p1",
            retrieval_timestamp="2026-08-15T00:00:00Z", upstream_origin_id="gov_origin",
            verification_status=VerificationStatus.VERIFIED_PRIMARY, is_primary_source=True,
            confidence=0.95, target_hypothesis="H1",
            inconsistency_ratings={"H1": 0.0, "H2": 0.0, "H0": 0.0}
        )

        matrix = self.engine.evaluate_matrix(self.hypotheses, self._val([primary_neutral_claim]))
        metrics = asyncio.run(orchestrator.evaluate_stopping_rules(
            contract, ontology, [primary_neutral_claim], matrix, current_depth=1, effective_max_depth=3
        ))

        # Debt MUST remain 1 because primary status does not bypass diagnostic relevance
        self.assertEqual(len(ontology.coverage_debt), 1)
        self.assertEqual(metrics.unresolved_coverage_debt_count, 1)


    def test_risk_lens_verbatim_quote_priority(self):
        """[P2] Verify that verbatim_quote has precedence over grounded_summary in risk lens key_evidence."""
        claim = AtomicClaim(
            id="risk_1", subject="REGULATORY_COMPLIANCE", predicate="has_violation", object="Notice",
            grounded_summary="LLM summary of regulatory issue",
            verbatim_quote="EXACT VERBATIM QUOTE FROM DOCUMENT: Section 4 non-compliance",
            source_url="https://gov.ua/notice", source_title="Gov Notice", source_domain="gov.ua", locator="p1",
            retrieval_timestamp="2026-08-14T22:00:00Z", upstream_origin_id="gov_origin",
            verification_status=VerificationStatus.VERIFIED_PRIMARY, is_primary_source=True,
            confidence=0.95, target_hypothesis="RISK_LENS", target_risk_lens_id="REGULATORY_COMPLIANCE",
            inconsistency_ratings={"H1": 0.0, "H2": 0.0, "H0": 0.0}
        )

        matrix = self.engine.evaluate_matrix(self.hypotheses, self._val([claim]))
        reg_risk = next(r for r in matrix.evaluated_risk_lenses if r["lens_id"] == "REGULATORY_COMPLIANCE")
        
        self.assertEqual(reg_risk["key_evidence"][0], "EXACT VERBATIM QUOTE FROM DOCUMENT: Section 4 non-compliance")

    def test_direct_mode_effective_max_depth_next_step(self):
        """Verify that in DIRECT_LOOKUP mode at depth 1, the next-step recommendation does NOT advise recursion."""
        orchestrator = OntologicalSearchOrchestratorV2()
        contract = ResearchContract(
            question="Rust proxy", decision_context="Tech Selection",
            target_object="Rust", required_precision="High", output_format="Brief",
            search_mode=SearchMode.DIRECT_LOOKUP, execution_mode=ExecutionMode.MOCK
        )
        ontology = DynamicOntology(domain_name="Rust", classes=["Proxy"], coverage_debt=["Proxy"])
        matrix = self.engine.evaluate_matrix(self.hypotheses, [])

        metrics = asyncio.run(orchestrator.evaluate_stopping_rules(
            contract, ontology, [], matrix, current_depth=1, effective_max_depth=1
        ))

        self.assertIn("Halt search at mode depth limit", metrics.recommended_next_step)

    def test_inconclusive_safety_blocks_categorical_synthesis(self):
        """Verify that if the ACH matrix is inconclusive, Synthesis strictly blocks categorical choice."""
        orchestrator = OntologicalSearchOrchestratorV2()

        claim_h1 = AtomicClaim(
            id="c1", subject="Solar Storage Tech A", predicate="has_efficiency", object="90%",
            grounded_summary="90% roundtrip efficiency verified in benchmark", source_url="https://src1.org",
            source_title="T1", source_domain="src1.org", locator="p1",
            retrieval_timestamp="2026-08-14T22:00:00Z", upstream_origin_id="org1",
            verification_status=VerificationStatus.VERIFIED_SECONDARY, is_primary_source=False,
            confidence=0.85, target_hypothesis="H1",
            inconsistency_ratings={"H1": 0.5, "H2": -1.0, "H0": -1.0}
        )
        claim_h2 = AtomicClaim(
            id="c2", subject="Solar Storage Tech B", predicate="has_efficiency", object="91%",
            grounded_summary="91% roundtrip efficiency verified in benchmark", source_url="https://src2.org",
            source_title="T2", source_domain="src2.org", locator="p1",
            retrieval_timestamp="2026-08-14T22:00:00Z", upstream_origin_id="org2",
            verification_status=VerificationStatus.VERIFIED_SECONDARY, is_primary_source=False,
            confidence=0.85, target_hypothesis="H2",
            inconsistency_ratings={"H1": -1.0, "H2": 0.5, "H0": -1.0}
        )

        matrix = self.engine.evaluate_matrix(self.hypotheses, self._val([claim_h1, claim_h2]))
        self.assertTrue(matrix.is_inconclusive)
        self.assertEqual(matrix.winning_hypothesis, "INCONCLUSIVE_EVIDENCE")

        contract = ResearchContract(
            question="Solar Storage Tech A vs Tech B", decision_context="Tech Selection",
            target_object="Solar Tech", required_precision="High", output_format="Brief",
            search_mode=SearchMode.RECURSIVE_EVIDENCE_SEARCH, execution_mode=ExecutionMode.LIVE
        )
        ontology = DynamicOntology(domain_name="Solar Storage", classes=["TechA", "TechB"], coverage_debt=[])
        metrics = AuditMetrics(
            coverage_score=0.90, novelty_score=0.85, reliability_score=0.85,
            counterevidence_searched=True, calibration_score=0.45, stopping_rule_met=False,
            recommended_next_step="Targeted search required"
        )

        synthesis = asyncio.run(orchestrator.synthesize_knowledge_v2(
            contract, ontology, self.hypotheses, [claim_h1, claim_h2], matrix, metrics
        ))

        self.assertEqual(synthesis.status, "INSUFFICIENT_EVIDENCE_SAFETY_BLOCK")
        self.assertIn("SAFETY GATE TRIGGERED", synthesis.decision_recommendation)
        self.assertLessEqual(synthesis.overall_confidence, 0.50)


    def test_risk_lens_zero_evidence_is_unassessed_not_low(self):
        """
        [P0] Verify that a risk lens with 0 evidence claims is tagged UNASSESSED,
        with severity UNKNOWN_UNASSESSED and confidence 0.0 (NEVER 'LOW' risk!).
        """
        matrix = self.engine.evaluate_matrix(self.hypotheses, [])
        reg_risk = next(r for r in matrix.evaluated_risk_lenses if r["lens_id"] == "REGULATORY_COMPLIANCE")
        
        self.assertEqual(reg_risk["assessment_status"], "UNASSESSED")
        self.assertEqual(reg_risk["severity"], "UNKNOWN_UNASSESSED")
        self.assertEqual(reg_risk["risk_level"], "UNKNOWN")
        self.assertEqual(reg_risk["confidence"], 0.0)

    def test_risk_lens_compliance_audits_are_refuted_not_high(self):
        """
        [P0] Verify that two independent audits confirming full compliance are classified as
        REFUTES_RISK with severity LOW (NEVER 'HIGH' risk simply because of 2 sources!).
        """
        compliant_claims = [
            AtomicClaim(
                id=f"audit_c_{i}",
                subject="REGULATORY_COMPLIANCE",
                predicate="passed_regulatory_audit",
                object="Solar Regulatory Commission",
                grounded_summary="Passed audit and certified: fully compliant; no violations found.",
                verbatim_quote="Certified: fully compliant with standard; no violations.",
                source_url=f"https://audit{i}.org",
                source_title=f"Audit {i}",
                source_domain=f"audit{i}.org",
                locator="p1",
                retrieval_timestamp="2026-08-15T00:00:00Z",
                upstream_origin_id=f"audit_agency_root_{i}",
                verification_status=VerificationStatus.VERIFIED_PRIMARY,
                is_primary_source=True,
                confidence=0.95,
                target_hypothesis="RISK_LENS",
                target_risk_lens_id="REGULATORY_COMPLIANCE",
                inconsistency_ratings={"H1": 0.0, "H2": 0.0, "H0": 0.0}
            )
            for i in range(2)
        ]

        matrix = self.engine.evaluate_matrix(self.hypotheses, self._val(compliant_claims))
        reg_risk = next(r for r in matrix.evaluated_risk_lenses if r["lens_id"] == "REGULATORY_COMPLIANCE")
        
        self.assertEqual(reg_risk["assessment_status"], "ASSESSED")
        self.assertEqual(reg_risk["risk_direction"], "REFUTES_RISK")
        self.assertEqual(reg_risk["severity"], "LOW")
        self.assertEqual(reg_risk["risk_level"], "LOW")
        self.assertEqual(reg_risk["independent_roots_count"], 2)

    def test_stopping_rule_blocks_when_risk_lenses_unassessed_or_h1_roots_under_three(self):
        """
        [P0] Verify that stopping_rule_met is strictly False when:
        1. H1 only has 1 root (< 3 required by contract), even if H2 and H0 have 1 root.
        2. Configured risk lenses have not been assessed (assessment_status == UNASSESSED).
        """
        orchestrator = OntologicalSearchOrchestratorV2()
        
        # 1 claim for H1, 1 for H2, 1 for H0 (total 3 origins, but H1 only has 1 root!)
        claims = [
            AtomicClaim(
                id="c1", subject="Solar Storage Tech A", predicate="has_certification_status", object="certified",
                grounded_summary="Certified A", source_url="https://a.org", source_title="A", source_domain="a.org", locator="p1",
                retrieval_timestamp="2026-08-15T00:00:00Z", upstream_origin_id="origin_a",
                verification_status=VerificationStatus.VERIFIED_SECONDARY, is_primary_source=False,
                confidence=0.90, target_hypothesis="H1", inconsistency_ratings={"H1": 0.5, "H2": -0.5, "H0": -1.0}
            ),
            AtomicClaim(
                id="c2", subject="Solar Storage Tech B", predicate="has_certification_status", object="certified",
                grounded_summary="Certified B", source_url="https://b.org", source_title="B", source_domain="b.org", locator="p1",
                retrieval_timestamp="2026-08-15T00:00:00Z", upstream_origin_id="origin_b",
                verification_status=VerificationStatus.VERIFIED_SECONDARY, is_primary_source=False,
                confidence=0.90, target_hypothesis="H2", inconsistency_ratings={"H1": -0.5, "H2": 0.5, "H0": -1.0}
            ),
            AtomicClaim(
                id="c3", subject="Solar Market", predicate="has_concurrency_bottleneck", object="bottleneck",
                grounded_summary="Bottleneck in market", source_url="https://c.org", source_title="C", source_domain="c.org", locator="p1",
                retrieval_timestamp="2026-08-15T00:00:00Z", upstream_origin_id="origin_c",
                verification_status=VerificationStatus.VERIFIED_SECONDARY, is_primary_source=False,
                confidence=0.90, target_hypothesis="H0", inconsistency_ratings={"H1": -0.5, "H2": -0.5, "H0": 0.5}
            )
        ]

        contract = ResearchContract(
            question="Solar Tech A vs B", decision_context="Tech Selection",
            target_object="Solar", required_precision="High", output_format="Brief",
            search_mode=SearchMode.RECURSIVE_EVIDENCE_SEARCH, execution_mode=ExecutionMode.LIVE
        )
        ontology = DynamicOntology(domain_name="Solar", classes=["Solar Storage Tech A"], coverage_debt=[])
        matrix = self.engine.evaluate_matrix(self.hypotheses, self._val(claims))

        metrics = asyncio.run(orchestrator.evaluate_stopping_rules(
            contract, ontology, claims, matrix, current_depth=1, effective_max_depth=3
        ))

        # Must fail because H1 only has 1 root (needs >=3) and risk lenses are unassessed!
        self.assertFalse(metrics.stopping_rule_met)
        self.assertEqual(metrics.h1_diagnostic_origins_count, 1)
        self.assertFalse(metrics.all_risk_lenses_assessed)

    def test_neutral_h0_claim_with_bottleneck_predicate_does_not_pass_gate(self):
        """
        [P1] Verify that a neutral H0 claim with 0/0/0 ratings and unknown subject does NOT satisfy
        the H0 diagnostic origin count just because its predicate contains 'bottleneck'.
        """
        orchestrator = OntologicalSearchOrchestratorV2()
        
        # Neutral claim with bottleneck predicate but unknown subject and 0/0/0 rating
        neutral_h0_claim = AtomicClaim(
            id="c_h0_neutral", subject="UNKNOWN", subject_entity_id="unknown",
            target_concept="RelationalDatabaseEngine", covered_ontology_classes=["RelationalDatabaseEngine"],
            predicate="has_concurrency_bottleneck", object="bottleneck overview",
            source_url="https://report.org", source_title="Report", source_domain="report.org", locator="p1",
            retrieval_timestamp="2026-08-15T00:00:00Z", upstream_origin_id="origin_report",
            verification_status=VerificationStatus.VERIFIED_SECONDARY, is_primary_source=False,
            confidence=0.85, target_hypothesis="H0",
            inconsistency_ratings={"H1": 0.0, "H2": 0.0, "H0": 0.0}
        )

        contract = ResearchContract(
            question="DB Test", decision_context="DB", target_object="DB",
            required_precision="High", output_format="Brief",
            search_mode=SearchMode.RECURSIVE_EVIDENCE_SEARCH, execution_mode=ExecutionMode.LIVE
        )
        ontology = DynamicOntology(domain_name="DB", classes=["RelationalDatabaseEngine"], coverage_debt=[])
        matrix = self.engine.evaluate_matrix(self.hypotheses, self._val([neutral_h0_claim]))

        metrics = asyncio.run(orchestrator.evaluate_stopping_rules(
            contract, ontology, [neutral_h0_claim], matrix, current_depth=1, effective_max_depth=3
        ))

        self.assertEqual(metrics.h0_diagnostic_origins_count, 0)
        self.assertFalse(metrics.stopping_rule_met)

    def test_ukrainian_and_complex_question_parsing(self):
        """
        [P1] Verify that Ukrainian questions, questions with colons, and 'Should we use'
        parse cleanly into Entity A, Entity B, and comparison intent.
        """
        orchestrator = OntologicalSearchOrchestratorV2()
        
        # 1. Which database is better: PostgreSQL or MySQL?
        intent_1 = orchestrator.parse_comparison_intent("Which database is better: PostgreSQL or MySQL?")
        self.assertTrue(intent_1.is_comparison)
        self.assertEqual(intent_1.e1.name, "PostgreSQL")
        self.assertEqual(intent_1.e2.name, "MySQL")

        # 2. Should we use Rust or Go?
        intent_2 = orchestrator.parse_comparison_intent("Should we use Rust or Go?")
        self.assertTrue(intent_2.is_comparison)
        self.assertEqual(intent_2.e1.name, "Rust")
        self.assertEqual(intent_2.e2.name, "Go")

        # 3. Порівняй PostgreSQL та MySQL
        intent_3 = orchestrator.parse_comparison_intent("Порівняй PostgreSQL та MySQL")
        self.assertTrue(intent_3.is_comparison)
        self.assertEqual(intent_3.e1.name, "PostgreSQL")
        self.assertEqual(intent_3.e2.name, "MySQL")

        # 4. Що обрати між PostgreSQL та MySQL для фінтеху?
        intent_4 = orchestrator.parse_comparison_intent("Що обрати між PostgreSQL та MySQL для фінтеху?")
        self.assertTrue(intent_4.is_comparison)
        self.assertEqual(intent_4.e1.name, "PostgreSQL")
        self.assertEqual(intent_4.e2.name, "MySQL")
        self.assertEqual(intent_4.domain_context, "фінтеху")

    def test_adversarial_risk_phrases_negation_and_neutral(self):
        """
        [P0] Verify that adversarial risk phrases are classified with negation-awareness:
        1. 'No violations were found.' -> REFUTES_RISK / LOW (NOT SUPPORTS_RISK / CRITICAL)
        2. 'No bottleneck was detected.' -> REFUTES_RISK / LOW (NOT SUPPORTS_RISK / HIGH)
        3. 'General regulatory overview; no conclusion was reached.' -> NEUTRAL / INSUFFICIENT / UNKNOWN (NOT SUPPORTS_RISK / MEDIUM)
        """
        # Case 1: Two claims with "No violations were found."
        claims_no_violations = [
            AtomicClaim(
                id=f"c_novio_{i}", subject="REGULATORY_COMPLIANCE", predicate="audit_result",
                object="No violations were found.", grounded_summary="Independent audit report: No violations were found.",
                verbatim_quote="No violations were found during the comprehensive inspection.",
                source_url=f"https://audit{i}.gov", source_title="Audit", source_domain=f"audit{i}.gov",
                locator="p1", retrieval_timestamp="2026-08-15T00:00:00Z", upstream_origin_id=f"origin_audit_{i}",
                verification_status=VerificationStatus.VERIFIED_PRIMARY, is_primary_source=True, confidence=0.95,
                target_hypothesis="RISK_LENS", target_risk_lens_id="REGULATORY_COMPLIANCE",
                inconsistency_ratings={"H1": 0.0, "H2": 0.0, "H0": 0.0}
            )
            for i in range(2)
        ]
        matrix_1 = self.engine.evaluate_matrix(self.hypotheses, self._val(claims_no_violations))
        reg_risk_1 = next(r for r in matrix_1.evaluated_risk_lenses if r["lens_id"] == "REGULATORY_COMPLIANCE")
        self.assertEqual(reg_risk_1["risk_direction"], "REFUTES_RISK")
        self.assertEqual(reg_risk_1["severity"], "LOW")
        self.assertEqual(reg_risk_1["risk_level"], "LOW")
        self.assertEqual(reg_risk_1["assessment_status"], "ASSESSED")

        # Case 2: Two claims with "No bottleneck was detected."
        claims_no_bottleneck = [
            AtomicClaim(
                id=f"c_nobottle_{i}", subject="PERFORMANCE_BOTTLENECK", predicate="benchmark_finding",
                object="No bottleneck was detected.", grounded_summary="Under full stress load, no bottleneck was detected.",
                verbatim_quote="No bottleneck was detected across all storage clusters.",
                source_url=f"https://bench{i}.org", source_title="Bench", source_domain=f"bench{i}.org",
                locator="p1", retrieval_timestamp="2026-08-15T00:00:00Z", upstream_origin_id=f"origin_bench_{i}",
                verification_status=VerificationStatus.VERIFIED_PRIMARY, is_primary_source=True, confidence=0.95,
                target_hypothesis="RISK_LENS", target_risk_lens_id="PERFORMANCE_BOTTLENECK",
                inconsistency_ratings={"H1": 0.0, "H2": 0.0, "H0": 0.0}
            )
            for i in range(2)
        ]
        hypotheses_with_perf = HypothesisSet(
            primary_h1=self.hypotheses.primary_h1,
            alternative_h2=self.hypotheses.alternative_h2,
            null_h0=self.hypotheses.null_h0,
            risk_lenses=[RiskLens(id="PERFORMANCE_BOTTLENECK", name="Performance Bottleneck", description="Concurrency bottleneck risk")]
        )
        matrix_2 = self.engine.evaluate_matrix(hypotheses_with_perf, self._val(claims_no_bottleneck, hypotheses_with_perf))
        perf_risk_2 = next(r for r in matrix_2.evaluated_risk_lenses if r["lens_id"] == "PERFORMANCE_BOTTLENECK")
        self.assertEqual(perf_risk_2["risk_direction"], "REFUTES_RISK")
        self.assertEqual(perf_risk_2["severity"], "LOW")
        self.assertEqual(perf_risk_2["risk_level"], "LOW")
        self.assertEqual(perf_risk_2["assessment_status"], "ASSESSED")

        # Case 3: One claim with "General regulatory overview; no conclusion was reached."
        claim_overview = [
            AtomicClaim(
                id="c_overview_1", subject="REGULATORY_COMPLIANCE", predicate="has_status",
                object="General regulatory overview; no conclusion was reached.",
                grounded_summary="General regulatory overview; no conclusion was reached.",
                verbatim_quote="General regulatory overview; no conclusion was reached in this preliminary paper.",
                source_url="https://study.org", source_title="Study", source_domain="study.org",
                locator="p1", retrieval_timestamp="2026-08-15T00:00:00Z", upstream_origin_id="origin_study",
                verification_status=VerificationStatus.VERIFIED_SECONDARY, is_primary_source=False, confidence=0.80,
                target_hypothesis="RISK_LENS", target_risk_lens_id="REGULATORY_COMPLIANCE",
                inconsistency_ratings={"H1": 0.0, "H2": 0.0, "H0": 0.0}
            )
        ]
        matrix_3 = self.engine.evaluate_matrix(self.hypotheses, self._val(claim_overview))
        reg_risk_3 = next(r for r in matrix_3.evaluated_risk_lenses if r["lens_id"] == "REGULATORY_COMPLIANCE")
        self.assertEqual(reg_risk_3["risk_direction"], "NEUTRAL")
        self.assertEqual(reg_risk_3["assessment_status"], "INSUFFICIENT")
        self.assertEqual(reg_risk_3["severity"], "UNKNOWN_UNASSESSED")
        self.assertEqual(reg_risk_3["risk_level"], "UNKNOWN")

    def test_insufficient_risk_lens_blocks_conclusive_synthesis(self):
        """
        [P1] Verify that when H1 has 3 roots, H2 has 1, H0 has 1, but a risk lens is INSUFFICIENT:
        1. stopping_rule_met is False
        2. all_material_risks_sufficiently_assessed is False
        3. unresolved_material_risks contains the lens name
        4. synthesize_knowledge_v2 emits CONDITIONAL_RECOMMENDATION (not CONCLUSIVE_RECOMMENDATION)
        """
        orchestrator = OntologicalSearchOrchestratorV2()
        
        # 3 independent roots for H1 (with 1 registered primary authority)
        claims_h1 = [
            AtomicClaim(
                id="c_h1_0", subject="Solar Storage Tech A", predicate="has_efficiency", object="92%",
                grounded_summary="Efficiency 92% confirmed in official standard benchmark",
                source_url="https://docs.solarcouncil.org/spec_0",
                source_title="Solar Council Official Spec", source_domain="docs.solarcouncil.org", locator="p1",
                retrieval_timestamp="2026-08-15T00:00:00Z", upstream_origin_id="solar_council_root",
                verification_status=VerificationStatus.VERIFIED_PRIMARY, is_primary_source=True, confidence=0.95,
                target_hypothesis="H1", inconsistency_ratings={"H1": 0.5, "H2": -0.5, "H0": -1.0}
            ),
            AtomicClaim(
                id="c_h1_1", subject="Solar Storage Tech A", predicate="has_efficiency", object="92%",
                grounded_summary="Efficiency 92% confirmed in lab 1", source_url="https://lab1.org",
                source_title="Lab 1", source_domain="lab1.org", locator="p1",
                retrieval_timestamp="2026-08-15T00:00:00Z", upstream_origin_id="lab_root_1",
                verification_status=VerificationStatus.VERIFIED_SECONDARY, is_primary_source=False, confidence=0.90,
                target_hypothesis="H1", inconsistency_ratings={"H1": 0.5, "H2": -0.5, "H0": -1.0}
            ),
            AtomicClaim(
                id="c_h1_2", subject="Solar Storage Tech A", predicate="has_efficiency", object="92%",
                grounded_summary="Efficiency 92% confirmed in lab 2", source_url="https://lab2.org",
                source_title="Lab 2", source_domain="lab2.org", locator="p1",
                retrieval_timestamp="2026-08-15T00:00:00Z", upstream_origin_id="lab_root_2",
                verification_status=VerificationStatus.VERIFIED_SECONDARY, is_primary_source=False, confidence=0.90,
                target_hypothesis="H1", inconsistency_ratings={"H1": 0.5, "H2": -0.5, "H0": -1.0}
            )
        ]
        # 1 root for H2
        claim_h2 = AtomicClaim(
            id="c_h2_1", subject="Solar Storage Tech B", predicate="has_efficiency", object="88%",
            grounded_summary="Efficiency 88%", source_url="https://lab_b.org",
            source_title="Lab B", source_domain="lab_b.org", locator="p1",
            retrieval_timestamp="2026-08-15T00:00:00Z", upstream_origin_id="lab_root_b",
            verification_status=VerificationStatus.VERIFIED_PRIMARY, is_primary_source=True, confidence=0.90,
            target_hypothesis="H2", inconsistency_ratings={"H1": -0.5, "H2": 0.5, "H0": -1.0}
        )
        # 1 root for H0
        claim_h0 = AtomicClaim(
            id="c_h0_1", subject="Solar Storage Tech A", predicate="exhibits_thermal_runaway", object="thermal runaway observed",
            grounded_summary="Thermal runaway observed under stress", source_url="https://safety_lab.org",
            source_title="Safety Lab", source_domain="safety_lab.org", locator="p1",
            retrieval_timestamp="2026-08-15T00:00:00Z", upstream_origin_id="safety_lab_root",
            verification_status=VerificationStatus.VERIFIED_PRIMARY, is_primary_source=True, confidence=0.90,
            target_hypothesis="H0", inconsistency_ratings={"H1": -1.0, "H2": -1.0, "H0": 0.5}
        )
        # 1 INSUFFICIENT risk claim
        claim_risk_neutral = AtomicClaim(
            id="c_risk_1", subject="REGULATORY_COMPLIANCE", predicate="overview", object="General overview; no conclusion was reached.",
            grounded_summary="General regulatory overview; no conclusion was reached.", source_url="https://reg.org",
            source_title="Reg", source_domain="reg.org", locator="p1",
            retrieval_timestamp="2026-08-15T00:00:00Z", upstream_origin_id="reg_root",
            verification_status=VerificationStatus.VERIFIED_SECONDARY, is_primary_source=False, confidence=0.75,
            target_hypothesis="RISK_LENS", target_risk_lens_id="REGULATORY_COMPLIANCE",
            inconsistency_ratings={"H1": 0.0, "H2": 0.0, "H0": 0.0}
        )
        # 1 ASSESSED risk claim for Supply Chain
        claim_risk_supply = AtomicClaim(
            id="c_risk_supply", subject="SUPPLY_CHAIN", predicate="audit_status", object="Fully certified supply chain.",
            grounded_summary="Global audit: Fully compliant and certified supply chain.", source_url="https://supply.org",
            source_title="Supply", source_domain="supply.org", locator="p1",
            retrieval_timestamp="2026-08-15T00:00:00Z", upstream_origin_id="supply_root",
            verification_status=VerificationStatus.VERIFIED_PRIMARY, is_primary_source=True, confidence=0.90,
            target_hypothesis="RISK_LENS", target_risk_lens_id="SUPPLY_CHAIN",
            inconsistency_ratings={"H1": 0.0, "H2": 0.0, "H0": 0.0}
        )

        all_claims = claims_h1 + [claim_h2, claim_h0, claim_risk_neutral, claim_risk_supply]
        contract = ResearchContract(
            question="Solar Tech A vs B", decision_context="Tech Selection", target_object="Solar",
            required_precision="High", output_format="Brief",
            search_mode=SearchMode.RECURSIVE_EVIDENCE_SEARCH, execution_mode=ExecutionMode.LIVE
        )
        ontology = DynamicOntology(domain_name="Solar Storage", classes=["Solar Storage Tech A"], coverage_debt=[])
        matrix = self.engine.evaluate_matrix(self.hypotheses, self._val(all_claims))

        metrics = asyncio.run(orchestrator.evaluate_stopping_rules(
            contract, ontology, all_claims, matrix, current_depth=1, effective_max_depth=3
        ))

        self.assertFalse(metrics.stopping_rule_met)
        self.assertFalse(metrics.all_material_risks_sufficiently_assessed)
        self.assertIn("Regulatory Risk", metrics.unresolved_material_risks)

        synthesis = asyncio.run(orchestrator.synthesize_knowledge_v2(
            contract, ontology, self.hypotheses, all_claims, matrix, metrics
        ))
        self.assertEqual(synthesis.status, "CONDITIONAL_RECOMMENDATION")
        self.assertIn("CONDITIONAL RECOMMENDATION", synthesis.decision_recommendation)

    def test_query_ledger_end_to_end_query_id_isolation(self):
        """
        [P1] Verify that SearchQueryRecord attributes documents and claims strictly by query_id,
        ensuring multiple queries with the same hypothesis or risk lens receive isolated counts.
        """
        orchestrator = OntologicalSearchOrchestratorV2()
        result = asyncio.run(orchestrator.run("Compare PostgreSQL vs MySQL for high concurrency"))

        ledger = result.get("query_ledger", [])
        self.assertGreaterEqual(len(ledger), 4)

        # Check each record in ledger has valid query_id and accurate per-query counts
        for rec in ledger:
            self.assertTrue(rec["query_id"].startswith("q_"))
            self.assertEqual(rec["status"], "EXECUTED")
            self.assertGreaterEqual(rec["retrieved_docs_count"], 1)

    def test_expanded_negation_scope_phrases(self):
        """
        [P0] Verify comprehensive negation scope detection across four challenging patterns:
        1. 'No evidence that any violations exist.'
        2. 'The audit did not detect any violations.'
        3. 'Bottleneck was not served.' (or 'Bottleneck was not observed.')
        4. 'The system is unlikely to experience an outage.'
        All must evaluate to REFUTES_RISK / LOW severity.
        """
        hypotheses_with_risks = HypothesisSet(
            primary_h1=self.hypotheses.primary_h1,
            alternative_h2=self.hypotheses.alternative_h2,
            null_h0=self.hypotheses.null_h0,
            risk_lenses=[
                RiskLens(id="REGULATORY_COMPLIANCE", name="Regulatory Risk", description="Compliance"),
                RiskLens(id="PERFORMANCE_BOTTLENECK", name="Performance Risk", description="Bottleneck"),
                RiskLens(id="AVAILABILITY_OUTAGE", name="Outage Risk", description="Outages")
            ]
        )

        test_cases = [
            ("REGULATORY_COMPLIANCE", "audit_scope", "No evidence that any violations exist.", "Independent study: No evidence that any violations exist."),
            ("REGULATORY_COMPLIANCE", "audit_check", "The audit did not detect any violations.", "Government audit: The audit did not detect any violations."),
            ("PERFORMANCE_BOTTLENECK", "concurrency_test", "Bottleneck was not served.", "Under maximum capacity, bottleneck was not served."),
            ("AVAILABILITY_OUTAGE", "reliability_eval", "The system is unlikely to experience an outage.", "Failover model: The system is unlikely to experience an outage.")
        ]

        for lens_id, predicate, obj_text, summary in test_cases:
            claim = AtomicClaim(
                id=f"c_{lens_id}_neg", subject=lens_id, predicate=predicate,
                object=obj_text, grounded_summary=summary, verbatim_quote=summary,
                source_url="https://audit.gov", source_title="Report", source_domain="audit.gov",
                locator="p1", retrieval_timestamp="2026-08-15T00:00:00Z", upstream_origin_id=f"origin_{lens_id}",
                verification_status=VerificationStatus.VERIFIED_PRIMARY, is_primary_source=True, confidence=0.95,
                target_hypothesis="RISK_LENS", target_risk_lens_id=lens_id,
                inconsistency_ratings={"H1": 0.0, "H2": 0.0, "H0": 0.0}
            )
            matrix = self.engine.evaluate_matrix(hypotheses_with_risks, self._val([claim], hypotheses_with_risks))
            risk_eval = next(r for r in matrix.evaluated_risk_lenses if r["lens_id"] == lens_id)
            self.assertEqual(risk_eval["risk_direction"], "REFUTES_RISK", f"Failed for {summary}")
            self.assertEqual(risk_eval["severity"], "LOW", f"Failed severity for {summary}")
            self.assertEqual(risk_eval["assessment_status"], "ASSESSED")

    def test_conditional_recommendation_strictly_blocked_when_other_gates_unmet(self):
        """
        [P0] Verify that CONDITIONAL_RECOMMENDATION is strictly forbidden if ANY other contract gate
        is failing (e.g. coverage debt > 0, or H1 origins < 3). Status must be INSUFFICIENT_EVIDENCE_SAFETY_BLOCK.
        """
        orchestrator = OntologicalSearchOrchestratorV2()

        # Only 1 root for H1 (needs >= 3)
        claim_h1 = AtomicClaim(
            id="c_h1_only", subject="Tech A", predicate="has_efficiency", object="95%",
            grounded_summary="Efficiency 95%", source_url="https://lab1.org",
            source_title="Lab 1", source_domain="lab1.org", locator="p1",
            retrieval_timestamp="2026-08-15T00:00:00Z", upstream_origin_id="lab_root_1",
            verification_status=VerificationStatus.VERIFIED_PRIMARY, is_primary_source=True, confidence=0.95,
            target_hypothesis="H1", inconsistency_ratings={"H1": 0.5, "H2": -0.5, "H0": -1.0}
        )
        claim_risk_unresolved = AtomicClaim(
            id="c_risk_neutral", subject="REGULATORY_COMPLIANCE", predicate="overview",
            object="General regulatory overview; no conclusion was reached.",
            grounded_summary="General regulatory overview; no conclusion was reached.",
            source_url="https://reg.org", source_title="Reg", source_domain="reg.org", locator="p1",
            retrieval_timestamp="2026-08-15T00:00:00Z", upstream_origin_id="reg_root",
            verification_status=VerificationStatus.VERIFIED_SECONDARY, is_primary_source=False, confidence=0.75,
            target_hypothesis="RISK_LENS", target_risk_lens_id="REGULATORY_COMPLIANCE",
            inconsistency_ratings={"H1": 0.0, "H2": 0.0, "H0": 0.0}
        )

        all_claims = [claim_h1, claim_risk_unresolved]
        contract = ResearchContract(
            question="Tech A vs Tech B", decision_context="Context", target_object="Tech",
            required_precision="High", output_format="Brief",
            search_mode=SearchMode.RECURSIVE_EVIDENCE_SEARCH, execution_mode=ExecutionMode.LIVE
        )
        # Ontology has coverage debt
        ontology = DynamicOntology(domain_name="Tech", classes=["Tech A", "Tech B", "UnresolvedDebtComponent"], coverage_debt=["UnresolvedDebtComponent"])
        matrix = self.engine.evaluate_matrix(self.hypotheses, self._val(all_claims))

        metrics = asyncio.run(orchestrator.evaluate_stopping_rules(
            contract, ontology, all_claims, matrix, current_depth=1, effective_max_depth=3
        ))

        self.assertFalse(metrics.stopping_rule_met)
        self.assertIn("Regulatory Risk", metrics.unresolved_material_risks)

        synthesis = asyncio.run(orchestrator.synthesize_knowledge_v2(
            contract, ontology, self.hypotheses, all_claims, matrix, metrics
        ))

        # Must be strictly blocked!
        self.assertEqual(synthesis.status, "INSUFFICIENT_EVIDENCE_SAFETY_BLOCK")
        self.assertIn("SAFETY GATE TRIGGERED", synthesis.decision_recommendation)
        self.assertNotIn("CONDITIONAL RECOMMENDATION: Preliminary adoption", synthesis.decision_recommendation)

    def test_severity_determined_by_evidence_impact_not_root_count(self):
        """
        [P1] Verify that duplicating independent confirmations scales confidence, but does NOT
        inflate or determine severity level.
        """
        hypotheses_with_risk = HypothesisSet(
            primary_h1=self.hypotheses.primary_h1,
            alternative_h2=self.hypotheses.alternative_h2,
            null_h0=self.hypotheses.null_h0,
            risk_lenses=[RiskLens(id="PERFORMANCE_BOTTLENECK", name="Performance Risk", description="Concurrency bottleneck")]
        )

        # 1 root confirmation of standard bottleneck
        claim_1_root = [
            AtomicClaim(
                id="c_perf_1", subject="PERFORMANCE_BOTTLENECK", predicate="exhibits_bottleneck",
                object="Bottleneck observed under load.", grounded_summary="Direct benchmark: Bottleneck observed under load.",
                source_url="https://bench1.org", source_title="Bench 1", source_domain="bench1.org", locator="p1",
                retrieval_timestamp="2026-08-15T00:00:00Z", upstream_origin_id="bench_cluster_1",
                verification_status=VerificationStatus.VERIFIED_PRIMARY, is_primary_source=True, confidence=0.85,
                target_hypothesis="RISK_LENS", target_risk_lens_id="PERFORMANCE_BOTTLENECK",
                inconsistency_ratings={"H1": 0.0, "H2": 0.0, "H0": 0.0}
            )
        ]
        matrix_1 = self.engine.evaluate_matrix(hypotheses_with_risk, self._val(claim_1_root, hypotheses_with_risk))
        risk_1 = next(r for r in matrix_1.evaluated_risk_lenses if r["lens_id"] == "PERFORMANCE_BOTTLENECK")
        self.assertEqual(risk_1["severity"], "HIGH")
        conf_1 = risk_1["confidence"]

        # 2 independent roots with identical bottleneck evidence
        claim_2_roots = claim_1_root + [
            AtomicClaim(
                id="c_perf_2", subject="PERFORMANCE_BOTTLENECK", predicate="exhibits_bottleneck",
                object="Bottleneck observed under load.", grounded_summary="Direct benchmark: Bottleneck observed under load.",
                source_url="https://bench2.org", source_title="Bench 2", source_domain="bench2.org", locator="p1",
                retrieval_timestamp="2026-08-15T00:00:00Z", upstream_origin_id="bench_cluster_2",
                verification_status=VerificationStatus.VERIFIED_PRIMARY, is_primary_source=True, confidence=0.85,
                target_hypothesis="RISK_LENS", target_risk_lens_id="PERFORMANCE_BOTTLENECK",
                inconsistency_ratings={"H1": 0.0, "H2": 0.0, "H0": 0.0}
            )
        ]
        matrix_2 = self.engine.evaluate_matrix(hypotheses_with_risk, self._val(claim_2_roots, hypotheses_with_risk))
        risk_2 = next(r for r in matrix_2.evaluated_risk_lenses if r["lens_id"] == "PERFORMANCE_BOTTLENECK")
        self.assertEqual(risk_2["severity"], "HIGH")  # Severity remains HIGH, not escalated to CRITICAL!
        conf_2 = risk_2["confidence"]

        # Confidence increases with more independent roots
        self.assertGreater(conf_2, conf_1)

    def test_failed_risk_query_blocks_risk_searches_completed_and_partial_failure(self):
        """
        [P1] Verify that a FAILED query in the ledger blocks all_risk_searches_completed,
        and per-query lifecycle maintains distinct statuses across queries.
        """
        orchestrator = OntologicalSearchOrchestratorV2()
        
        # Setup ledger with 1 EXECUTED query and 1 FAILED risk query
        from models import SearchQueryRecord
        orchestrator.query_ledger = [
            SearchQueryRecord(
                query_id="q_1", query_text="H1 query", target_hypothesis="H1",
                target_concept="Concept", search_strategy="BROAD_OVERVIEW", depth=1,
                timestamp="2026-08-15T00:00:00Z", status="EXECUTED"
            ),
            SearchQueryRecord(
                query_id="q_2", query_text="Risk query", target_hypothesis="RISK_LENS",
                target_risk_lens_id="REGULATORY_COMPLIANCE", target_concept="Concept",
                search_strategy="BROAD_OVERVIEW", depth=1, timestamp="2026-08-15T00:00:00Z",
                status="FAILED", error_message="HTTP 500 API Gateway Timeout"
            )
        ]

        contract = ResearchContract(
            question="Tech A vs Tech B", decision_context="Context", target_object="Tech",
            required_precision="High", output_format="Brief",
            search_mode=SearchMode.RECURSIVE_EVIDENCE_SEARCH, execution_mode=ExecutionMode.LIVE
        )
        ontology = DynamicOntology(domain_name="Tech", classes=["Tech A"], coverage_debt=[])
        matrix = self.engine.evaluate_matrix(self.hypotheses, [])

        metrics = asyncio.run(orchestrator.evaluate_stopping_rules(
            contract, ontology, [], matrix, current_depth=1, effective_max_depth=3
        ))

        # all_risk_searches_completed must be False due to FAILED status!
        self.assertFalse(metrics.all_risk_searches_completed)
        self.assertFalse(metrics.stopping_rule_met)

    def test_negated_positive_terms_support_risk(self):
        """
        [P0] Verify that negated positive terms and non-compliance prefixes correctly SUPPORTS_RISK:
        1. 'The product is not certified.' -> SUPPORTS_RISK
        2. 'The product is not compliant with regulation.' -> SUPPORTS_RISK
        3. 'The system is not resilient under load.' -> SUPPORTS_RISK
        4. 'The product was not approved by the regulator.' -> SUPPORTS_RISK
        5. 'The product is non-compliant with ISO 27001.' -> SUPPORTS_RISK
        """
        hypotheses = HypothesisSet(
            primary_h1=self.hypotheses.primary_h1,
            alternative_h2=self.hypotheses.alternative_h2,
            null_h0=self.hypotheses.null_h0,
            risk_lenses=[
                RiskLens(id="REGULATORY_COMPLIANCE", name="Regulatory Risk", description="Compliance"),
                RiskLens(id="SYSTEM_RESILIENCE", name="Resilience Risk", description="Resilience")
            ]
        )

        test_cases = [
            ("REGULATORY_COMPLIANCE", "has_status", "not certified", "The product is not certified."),
            ("REGULATORY_COMPLIANCE", "compliance_status", "not compliant with regulation", "The product is not compliant with regulation."),
            ("SYSTEM_RESILIENCE", "resilience_status", "not resilient under load", "The system is not resilient under load."),
            ("REGULATORY_COMPLIANCE", "approval_status", "was not approved by the regulator", "The product was not approved by the regulator."),
            ("REGULATORY_COMPLIANCE", "iso_status", "non-compliant with ISO 27001", "The product is non-compliant with ISO 27001.")
        ]

        for lens_id, predicate, obj, text in test_cases:
            claim = AtomicClaim(
                id=f"c_negpos_{lens_id}", subject=lens_id, predicate=predicate,
                object=obj, grounded_summary=text, verbatim_quote=text,
                source_url="https://audit.org", source_title="Audit", source_domain="audit.org",
                locator="p1", retrieval_timestamp="2026-08-15T00:00:00Z", upstream_origin_id="audit_origin",
                verification_status=VerificationStatus.VERIFIED_PRIMARY, is_primary_source=True, confidence=0.90,
                target_hypothesis="RISK_LENS", target_risk_lens_id=lens_id,
                inconsistency_ratings={"H1": 0.0, "H2": 0.0, "H0": 0.0}
            )
            matrix = self.engine.evaluate_matrix(hypotheses, self._val([claim], hypotheses))
            eval_risk = next(r for r in matrix.evaluated_risk_lenses if r["lens_id"] == lens_id)
            self.assertEqual(eval_risk["risk_direction"], "SUPPORTS_RISK", f"Failed for: {text}")
            self.assertEqual(eval_risk["assessment_status"], "ASSESSED")

    def test_typical_no_evidence_constructions_refute_risk(self):
        """
        [P0] Verify that typical no-evidence constructions evaluate to REFUTES_RISK:
        1. 'No evidence of violations was found.' -> REFUTES_RISK / LOW
        2. 'There is no evidence to suggest any violations.' -> REFUTES_RISK / LOW
        """
        hypotheses = HypothesisSet(
            primary_h1=self.hypotheses.primary_h1,
            alternative_h2=self.hypotheses.alternative_h2,
            null_h0=self.hypotheses.null_h0,
            risk_lenses=[RiskLens(id="REGULATORY_COMPLIANCE", name="Regulatory Risk", description="Compliance")]
        )

        phrases = [
            "No evidence of violations was found.",
            "There is no evidence to suggest any violations."
        ]

        for text in phrases:
            claim = AtomicClaim(
                id="c_noev", subject="REGULATORY_COMPLIANCE", predicate="audit_scope",
                object=text, grounded_summary=text, verbatim_quote=text,
                source_url="https://audit.gov", source_title="Audit", source_domain="audit.gov",
                locator="p1", retrieval_timestamp="2026-08-15T00:00:00Z", upstream_origin_id="audit_gov",
                verification_status=VerificationStatus.VERIFIED_PRIMARY, is_primary_source=True, confidence=0.95,
                target_hypothesis="RISK_LENS", target_risk_lens_id="REGULATORY_COMPLIANCE",
                inconsistency_ratings={"H1": 0.0, "H2": 0.0, "H0": 0.0}
            )
            matrix = self.engine.evaluate_matrix(hypotheses, self._val([claim], hypotheses))
            eval_risk = next(r for r in matrix.evaluated_risk_lenses if r["lens_id"] == "REGULATORY_COMPLIANCE")
            self.assertEqual(eval_risk["risk_direction"], "REFUTES_RISK", f"Failed for: {text}")
            self.assertEqual(eval_risk["severity"], "LOW", f"Failed severity for: {text}")

    def test_materiality_severity_distinction(self):
        """
        [P1] Verify materiality impact on severity:
        1. 'A minor isolated violation was corrected immediately.' -> LOW severity
        2. 'A severe recurring violation caused customer harm.' -> HIGH severity
        """
        hypotheses = HypothesisSet(
            primary_h1=self.hypotheses.primary_h1,
            alternative_h2=self.hypotheses.alternative_h2,
            null_h0=self.hypotheses.null_h0,
            risk_lenses=[RiskLens(id="REGULATORY_COMPLIANCE", name="Regulatory Risk", description="Compliance")]
        )

        # Case 1: Remediated minor violation -> LOW
        claim_minor = AtomicClaim(
            id="c_minor", subject="REGULATORY_COMPLIANCE", predicate="audit_finding",
            object="A minor isolated violation was corrected immediately.",
            grounded_summary="Audit note: A minor isolated violation was corrected immediately.",
            verbatim_quote="A minor isolated violation was corrected immediately.",
            source_url="https://audit.gov", source_title="Audit", source_domain="audit.gov",
            locator="p1", retrieval_timestamp="2026-08-15T00:00:00Z", upstream_origin_id="audit_gov_1",
            verification_status=VerificationStatus.VERIFIED_PRIMARY, is_primary_source=True, confidence=0.90,
            target_hypothesis="RISK_LENS", target_risk_lens_id="REGULATORY_COMPLIANCE",
            inconsistency_ratings={"H1": 0.0, "H2": 0.0, "H0": 0.0}
        )
        matrix_1 = self.engine.evaluate_matrix(hypotheses, self._val([claim_minor], hypotheses))
        risk_1 = next(r for r in matrix_1.evaluated_risk_lenses if r["lens_id"] == "REGULATORY_COMPLIANCE")
        self.assertEqual(risk_1["risk_direction"], "SUPPORTS_RISK")
        self.assertEqual(risk_1["severity"], "LOW")

        # Case 2: Severe recurring harm -> HIGH
        claim_severe = AtomicClaim(
            id="c_severe", subject="REGULATORY_COMPLIANCE", predicate="audit_finding",
            object="A severe recurring violation caused customer harm.",
            grounded_summary="Investigation report: A severe recurring violation caused customer harm.",
            verbatim_quote="A severe recurring violation caused customer harm.",
            source_url="https://audit.gov", source_title="Audit", source_domain="audit.gov",
            locator="p1", retrieval_timestamp="2026-08-15T00:00:00Z", upstream_origin_id="audit_gov_2",
            verification_status=VerificationStatus.VERIFIED_PRIMARY, is_primary_source=True, confidence=0.90,
            target_hypothesis="RISK_LENS", target_risk_lens_id="REGULATORY_COMPLIANCE",
            inconsistency_ratings={"H1": 0.0, "H2": 0.0, "H0": 0.0}
        )
        matrix_2 = self.engine.evaluate_matrix(hypotheses, self._val([claim_severe], hypotheses))
        risk_2 = next(r for r in matrix_2.evaluated_risk_lenses if r["lens_id"] == "REGULATORY_COMPLIANCE")
        self.assertEqual(risk_2["risk_direction"], "SUPPORTS_RISK")
        self.assertEqual(risk_2["severity"], "HIGH")

    def test_unknown_remains_unknown_not_low(self):
        """
        [P1] Verify that ambiguous context without risk keywords remains UNKNOWN / UNASSESSED,
        never falsely defaulting to LOW.
        """
        hypotheses = HypothesisSet(
            primary_h1=self.hypotheses.primary_h1,
            alternative_h2=self.hypotheses.alternative_h2,
            null_h0=self.hypotheses.null_h0,
            risk_lenses=[RiskLens(id="REGULATORY_COMPLIANCE", name="Regulatory Risk", description="Compliance")]
        )

        claim_ambiguous = AtomicClaim(
            id="c_ambig", subject="REGULATORY_COMPLIANCE", predicate="context",
            object="General database architecture concepts and storage structures",
            grounded_summary="General database architecture concepts and storage structures",
            source_url="https://wiki.org", source_title="Wiki", source_domain="wiki.org",
            locator="p1", retrieval_timestamp="2026-08-15T00:00:00Z", upstream_origin_id="wiki_root",
            verification_status=VerificationStatus.VERIFIED_SECONDARY, is_primary_source=False, confidence=0.60,
            target_hypothesis="RISK_LENS", target_risk_lens_id="REGULATORY_COMPLIANCE",
            inconsistency_ratings={"H1": 0.0, "H2": 0.0, "H0": 0.0}
        )
        matrix = self.engine.evaluate_matrix(hypotheses, self._val([claim_ambiguous], hypotheses))
        eval_risk = next(r for r in matrix.evaluated_risk_lenses if r["lens_id"] == "REGULATORY_COMPLIANCE")
        self.assertEqual(eval_risk["risk_direction"], "NEUTRAL")
        self.assertEqual(eval_risk["assessment_status"], "INSUFFICIENT")
        self.assertEqual(eval_risk["severity"], "UNKNOWN_UNASSESSED")
        self.assertEqual(eval_risk["risk_level"], "UNKNOWN")

    def test_mixed_minor_and_severe_materiality_takes_maximum_severity(self):
        """
        [P0] Verify that when a risk lens receives both a minor remediated violation claim
        AND a severe recurring violation claim from independent roots:
        1. The risk direction is SUPPORTS_RISK
        2. The aggregate severity is HIGH (the minor claim does NOT downgrade the severe risk to LOW)
        3. Confidence scales with 2 independent roots
        """
        hypotheses = HypothesisSet(
            primary_h1=self.hypotheses.primary_h1,
            alternative_h2=self.hypotheses.alternative_h2,
            null_h0=self.hypotheses.null_h0,
            risk_lenses=[RiskLens(id="REGULATORY_COMPLIANCE", name="Regulatory Risk", description="Compliance")]
        )

        claim_minor = AtomicClaim(
            id="c_minor_1", subject="REGULATORY_COMPLIANCE", predicate="audit_finding",
            object="minor isolated violation corrected immediately",
            grounded_summary="Audit note: minor isolated violation corrected immediately",
            verbatim_quote="A minor isolated violation was corrected immediately.",
            source_url="https://audit1.gov", source_title="Audit 1", source_domain="audit1.gov",
            locator="p1", retrieval_timestamp="2026-08-15T00:00:00Z", upstream_origin_id="audit_root_1",
            verification_status=VerificationStatus.VERIFIED_PRIMARY, is_primary_source=True, confidence=0.90,
            target_hypothesis="RISK_LENS", target_risk_lens_id="REGULATORY_COMPLIANCE",
            inconsistency_ratings={"H1": 0.0, "H2": 0.0, "H0": 0.0}
        )

        claim_severe = AtomicClaim(
            id="c_severe_2", subject="REGULATORY_COMPLIANCE", predicate="audit_finding",
            object="severe recurring violation caused customer harm",
            grounded_summary="Investigation report: severe recurring violation caused customer harm",
            verbatim_quote="A severe recurring violation caused customer harm.",
            source_url="https://audit2.gov", source_title="Audit 2", source_domain="audit2.gov",
            locator="p1", retrieval_timestamp="2026-08-15T00:00:00Z", upstream_origin_id="audit_root_2",
            verification_status=VerificationStatus.VERIFIED_PRIMARY, is_primary_source=True, confidence=0.90,
            target_hypothesis="RISK_LENS", target_risk_lens_id="REGULATORY_COMPLIANCE",
            inconsistency_ratings={"H1": 0.0, "H2": 0.0, "H0": 0.0}
        )

        matrix = self.engine.evaluate_matrix(hypotheses, self._val([claim_minor, claim_severe], hypotheses))
        eval_risk = next(r for r in matrix.evaluated_risk_lenses if r["lens_id"] == "REGULATORY_COMPLIANCE")
        
        self.assertEqual(eval_risk["risk_direction"], "SUPPORTS_RISK")
        self.assertEqual(eval_risk["assessment_status"], "ASSESSED")
        # Must be HIGH, strictly not downgraded to LOW
        self.assertEqual(eval_risk["severity"], "HIGH")
        self.assertEqual(eval_risk["risk_level"], "HIGH")
        self.assertEqual(eval_risk["independent_roots_count"], 2)

    def test_structured_risk_impact_is_source_of_truth(self):
        """
        [P1] Verify that structured AtomicClaim.risk_impact and risk_likelihood are the primary source
        of truth, returning CRITICAL/HIGH even if plain text is neutral.
        """
        hypotheses = HypothesisSet(
            primary_h1=self.hypotheses.primary_h1,
            alternative_h2=self.hypotheses.alternative_h2,
            null_h0=self.hypotheses.null_h0,
            risk_lenses=[RiskLens(id="REGULATORY_COMPLIANCE", name="Regulatory Risk", description="Compliance")]
        )

        claim_critical = AtomicClaim(
            id="c_crit_struct", subject="REGULATORY_COMPLIANCE", predicate="status",
            object="Vendor assessment noted compliance findings",
            grounded_summary="Vendor assessment noted compliance findings",
            source_url="https://audit.org", source_title="Audit", source_domain="audit.org",
            locator="p1", retrieval_timestamp="2026-08-15T00:00:00Z", upstream_origin_id="audit_org",
            verification_status=VerificationStatus.VERIFIED_PRIMARY, is_primary_source=True, confidence=0.95,
            target_hypothesis="RISK_LENS", target_risk_lens_id="REGULATORY_COMPLIANCE",
            risk_stance="SUPPORTS",
            risk_impact="CRITICAL",
            risk_likelihood="HIGH",
            inconsistency_ratings={"H1": 0.0, "H2": 0.0, "H0": 0.0}
        )

        matrix = self.engine.evaluate_matrix(hypotheses, self._val([claim_critical], hypotheses))
        eval_risk = next(r for r in matrix.evaluated_risk_lenses if r["lens_id"] == "REGULATORY_COMPLIANCE")
        
        self.assertEqual(eval_risk["risk_direction"], "SUPPORTS_RISK")
        self.assertEqual(eval_risk["assessment_status"], "ASSESSED")
        # Must strictly return CRITICAL based on structured risk_impact, not MEDIUM
        self.assertEqual(eval_risk["severity"], "CRITICAL")
        self.assertEqual(eval_risk["risk_level"], "CRITICAL")

    def test_unverified_mock_claims_with_nonzero_ratings_cannot_win_or_assess_risk(self):
        """
        [P0] Fail-closed verification gate:
        Verify that AtomicClaims with UNVERIFIED_MOCK status, even with non-zero ACH ratings
        and distinct origins:
        1. Produce winning_hypothesis = ALL_HYPOTHESES_UNTESTED and is_inconclusive = True
        2. Leave risk lenses UNASSESSED with severity UNKNOWN_UNASSESSED and 0 independent roots
        3. Do not count towards diagnostic origins in LIVE stopping rules
        """
        orchestrator = OntologicalSearchOrchestratorV2()
        
        # 3 mock claims with non-zero H1 ratings and distinct origins
        mock_claims_h1 = [
            AtomicClaim(
                id=f"c_mock_h1_{i}", subject="Solar Storage Tech A", predicate="has_efficiency", object="99%",
                grounded_summary=f"Mock claim {i}", source_url=f"simulation://mock{i}",
                source_title=f"Mock {i}", source_domain="simulation.local", locator="p1",
                retrieval_timestamp="2026-08-15T00:00:00Z", upstream_origin_id=f"mock_origin_{i}",
                verification_status=VerificationStatus.UNVERIFIED_MOCK, is_primary_source=False, confidence=0.90,
                target_hypothesis="H1", inconsistency_ratings={"H1": 0.5, "H2": -0.5, "H0": -1.0}
            )
            for i in range(3)
        ]

        # 1 mock risk claim with non-zero severity text
        mock_risk_claim = AtomicClaim(
            id="c_mock_risk", subject="REGULATORY_COMPLIANCE", predicate="audit_failure",
            object="A severe recurring violation caused customer harm",
            grounded_summary="A severe recurring violation caused customer harm",
            source_url="simulation://mock_risk", source_title="Mock Risk", source_domain="simulation.local",
            locator="p1", retrieval_timestamp="2026-08-15T00:00:00Z", upstream_origin_id="mock_risk_origin",
            verification_status=VerificationStatus.UNVERIFIED_MOCK, is_primary_source=False, confidence=0.95,
            target_hypothesis="RISK_LENS", target_risk_lens_id="REGULATORY_COMPLIANCE",
            risk_stance="SUPPORTS", inconsistency_ratings={"H1": 0.0, "H2": 0.0, "H0": 0.0}
        )

        all_mock_claims = mock_claims_h1 + [mock_risk_claim]
        matrix = self.engine.evaluate_matrix(self.hypotheses, self._val(all_mock_claims, execution_mode=ExecutionMode.LIVE))

        # 1. Hypothesis scoring must fail-closed
        self.assertTrue(matrix.is_inconclusive)
        self.assertEqual(matrix.winning_hypothesis, "ALL_HYPOTHESES_UNTESTED")
        self.assertEqual(matrix.h1_positive_support, 0.0)

        # 2. Risk lens must remain UNASSESSED
        reg_risk = next(r for r in matrix.evaluated_risk_lenses if r["lens_id"] == "REGULATORY_COMPLIANCE")
        self.assertEqual(reg_risk["assessment_status"], "UNASSESSED")
        self.assertEqual(reg_risk["severity"], "UNKNOWN_UNASSESSED")
        self.assertEqual(reg_risk["independent_roots_count"], 0)

        # 3. Stopping gate in LIVE mode must not count UNVERIFIED_MOCK claims as diagnostic origins
        contract = ResearchContract(
            question="Solar Tech A vs B", decision_context="Tech Selection", target_object="Solar",
            required_precision="High", output_format="Brief",
            search_mode=SearchMode.RECURSIVE_EVIDENCE_SEARCH, execution_mode=ExecutionMode.LIVE
        )
        ontology = DynamicOntology(domain_name="Solar", classes=["Solar Storage Tech A"], coverage_debt=[])
        metrics = asyncio.run(orchestrator.evaluate_stopping_rules(
            contract, ontology, all_mock_claims, matrix, current_depth=1, effective_max_depth=3
        ))
        self.assertEqual(metrics.h1_diagnostic_origins_count, 0)
        self.assertFalse(metrics.stopping_rule_met)

    def test_intraclaim_materiality_dominance(self):
        """
        [P1] Verify that within a single claim text containing both remediated and severe harm terms:
        'A minor issue was remediated, but a severe recurring violation caused customer harm.'
        the severe/critical finding strictly dominates the remediated/minor finding, producing HIGH severity.
        """
        hypotheses = HypothesisSet(
            primary_h1=self.hypotheses.primary_h1,
            alternative_h2=self.hypotheses.alternative_h2,
            null_h0=self.hypotheses.null_h0,
            risk_lenses=[RiskLens(id="REGULATORY_COMPLIANCE", name="Regulatory Risk", description="Compliance")]
        )

        claim_mixed_text = AtomicClaim(
            id="c_mixed_intraclaim", subject="REGULATORY_COMPLIANCE", predicate="audit_scope",
            object="A minor issue was remediated, but a severe recurring violation caused customer harm.",
            grounded_summary="Audit record: A minor issue was remediated, but a severe recurring violation caused customer harm.",
            verbatim_quote="A minor issue was remediated, but a severe recurring violation caused customer harm.",
            source_url="https://reg.gov", source_title="Reg", source_domain="reg.gov",
            locator="p1", retrieval_timestamp="2026-08-15T00:00:00Z", upstream_origin_id="reg_gov",
            verification_status=VerificationStatus.VERIFIED_PRIMARY, is_primary_source=True, confidence=0.90,
            target_hypothesis="RISK_LENS", target_risk_lens_id="REGULATORY_COMPLIANCE",
            inconsistency_ratings={"H1": 0.0, "H2": 0.0, "H0": 0.0}
        )

        mat = self.engine.classify_claim_risk_materiality(claim_mixed_text)
        self.assertEqual(mat, "HIGH")

        matrix = self.engine.evaluate_matrix(hypotheses, self._val([claim_mixed_text], hypotheses))
        reg_risk = next(r for r in matrix.evaluated_risk_lenses if r["lens_id"] == "REGULATORY_COMPLIANCE")
        self.assertEqual(reg_risk["risk_direction"], "SUPPORTS_RISK")
        self.assertEqual(reg_risk["severity"], "HIGH")

    def test_unknown_and_neutral_stance_no_medium_impact_default(self):
        """
        [P1] Verify that claims extracted with UNKNOWN or NEUTRAL risk stance
        do not receive a default MEDIUM impact/likelihood.
        """
        orchestrator = OntologicalSearchOrchestratorV2()
        contract = ResearchContract(
            question="Solar Storage Tech", decision_context="Context", target_object="Solar",
            required_precision="High", output_format="Brief",
            search_mode=SearchMode.STRUCTURED_SEARCH, execution_mode=ExecutionMode.LIVE
        )
        ontology = DynamicOntology(domain_name="Solar", classes=["Solar Storage Tech A"], coverage_debt=[])
        
        doc = {
            "document_text": "Solar storage technology architecture overview and structural background notes.",
            "source_segment": "Solar storage technology architecture overview and structural background notes.",
            "source_url": "https://wiki.org",
            "source_title": "Overview",
            "source_domain": "wiki.org",
            "locator": "p1",
            "upstream_origin_id": "wiki_origin",
            "query_id": "q1",
            "target_risk_lens_id": "REGULATORY_COMPLIANCE",
            "strategy": "BROAD_OVERVIEW"
        }

        claims = asyncio.run(orchestrator.extract_atomic_claims(
            "Solar Storage Tech", ontology, self.hypotheses, [doc], ExecutionMode.LIVE
        ))
        self.assertGreater(len(claims), 0)
        for c in claims:
            # Must remain UNKNOWN or None, never default to MEDIUM
            self.assertIn(c.risk_impact, ["UNKNOWN", None])
            self.assertIn(c.risk_likelihood, ["UNKNOWN", None])

    def test_one_segment_multi_chunks_deduplicated_to_single_root(self):
        """
        [P0] Provenance Independence:
        Verify that a single response segment cited by 3 distinct grounding chunks
        (ONE_SEGMENT_DOCS=3, UNIQUE_SUMMARIES=1) clusters into 1 independent root,
        NOT 3 roots, correctly keeping stopping_rule_met=False (since H1 requires >= 3 roots).
        """
        adapter = GeminiDeepResearchAdapter(api_key="valid_test_key")
        adapter.is_live = True
        orchestrator = OntologicalSearchOrchestratorV2()

        # Simulated Gemini Grounding API response: 1 segment supported by 3 distinct chunks
        api_response = {
            "candidates": [{
                "content": {
                    "parts": [{
                        "text": "Solar Storage Tech A achieves 99 percent round-trip efficiency in benchmark tests."
                    }]
                },
                "groundingMetadata": {
                    "groundingChunks": [
                        {"web": {"uri": "https://news.com/post", "title": "News Site"}},
                        {"web": {"uri": "https://techblog.org/post", "title": "Tech Blog"}},
                        {"web": {"uri": "https://aggregator.io/post", "title": "Aggregator"}}
                    ],
                    "groundingSupports": [
                        {
                            "segment": {"startIndex": 0, "endIndex": 83},
                            "groundingChunkIndices": [0, 1, 2]
                        }
                    ]
                }
            }]
        }

        query = QueryItem(query_id="q1", text="Solar Storage Tech A efficiency", strategy="Direct", target_hypothesis="H1")
        docs = adapter.parse_grounded_response(api_response, query, "2026-08-15T00:00:00Z")

        # 3 documents created for 1 segment across 3 citations
        self.assertEqual(len(docs), 3)
        # All 3 share the exact same segment content and segment provenance ID
        self.assertEqual(len(set(d["grounded_summary"] for d in docs)), 1)
        self.assertEqual(len(set(d["upstream_origin_id"] for d in docs)), 1)

        ontology = DynamicOntology(domain_name="Solar", classes=["Solar Storage Tech A"], coverage_debt=[])
        claims = asyncio.run(orchestrator.extract_atomic_claims(
            "Solar Storage Tech A", ontology, self.hypotheses, docs, ExecutionMode.LIVE
        ))
        
        # Verify inconsistency ratings and target hypothesis
        for c in claims:
            c.inconsistency_ratings = {"H1": 0.5, "H2": -0.5, "H0": -1.0}

        contract = ResearchContract(
            question="Solar Tech A vs B", decision_context="Tech Selection", target_object="Solar",
            required_precision="High", output_format="Brief",
            search_mode=SearchMode.RECURSIVE_EVIDENCE_SEARCH, execution_mode=ExecutionMode.LIVE
        )
        matrix = self.engine.evaluate_matrix(self.hypotheses, self._val(claims))
        metrics = asyncio.run(orchestrator.evaluate_stopping_rules(
            contract, ontology, claims, matrix, current_depth=1, effective_max_depth=3
        ))

        # Must strictly evaluate to 1 independent diagnostic origin, NOT 3!
        self.assertEqual(metrics.h1_diagnostic_origins_count, 1)
        self.assertEqual(metrics.unique_upstream_origins_count, 1)
        self.assertFalse(metrics.stopping_rule_met)

    def test_high_precision_stopping_blocks_when_primary_source_ratio_zero(self):
        """
        [P0/P1] Source-Quality Contract:
        Verify that in a High-Precision contract (required_precision='High'),
        having 3 independent secondary blog claims for H1 (primary_source_ratio=0.0)
        strictly BLOCKS stopping_rule_met (False).
        Adding 1 verified primary source unblocks the primary floor.
        """
        orchestrator = OntologicalSearchOrchestratorV2()
        hypotheses_no_risk = HypothesisSet(
            primary_h1=self.hypotheses.primary_h1,
            alternative_h2=self.hypotheses.alternative_h2,
            null_h0=self.hypotheses.null_h0,
            risk_lenses=[]
        )

        # 3 secondary blog sources for H1 (distinct domains)
        secondary_h1_claims = [
            AtomicClaim(
                id=f"c_sec_h1_{i}", subject="Solar Storage Tech A", predicate="has_efficiency", object="high",
                grounded_summary=f"Secondary report {i}", source_url=f"https://blog{i}.com/post",
                source_title=f"Blog {i}", source_domain=f"blog{i}.com", locator="p1",
                retrieval_timestamp="2026-08-15T00:00:00Z", upstream_origin_id=f"blog_origin_{i}",
                verification_status=VerificationStatus.VERIFIED_SECONDARY, is_primary_source=False, confidence=0.85,
                target_hypothesis="H1", target_concept="Solar Storage Tech A", covered_ontology_classes=["Solar Storage Tech A"],
                inconsistency_ratings={"H1": 0.5, "H2": -0.5, "H0": -1.0}
            )
            for i in range(3)
        ]

        h2_claim = AtomicClaim(
            id="c_h2", subject="Solar Storage Tech B", predicate="has_cost", object="expensive",
            grounded_summary="Cost benchmark", source_url="https://blog_h2.com", source_title="H2",
            source_domain="blog_h2.com", locator="p1", retrieval_timestamp="2026-08-15T00:00:00Z",
            upstream_origin_id="blog_h2_origin", verification_status=VerificationStatus.VERIFIED_SECONDARY,
            is_primary_source=False, confidence=0.85, target_hypothesis="H2",
            target_concept="Solar Storage Tech B", covered_ontology_classes=["Solar Storage Tech B"],
            inconsistency_ratings={"H1": -0.5, "H2": 0.5, "H0": -1.0}
        )

        h0_claim = AtomicClaim(
            id="c_h0", subject="Solar Storage Tech A", predicate="counterevidence", object="limitation",
            grounded_summary="Counterevidence report", source_url="https://skeptic.com", source_title="H0",
            source_domain="skeptic.com", locator="p1", retrieval_timestamp="2026-08-15T00:00:00Z",
            upstream_origin_id="skeptic_origin", verification_status=VerificationStatus.VERIFIED_SECONDARY,
            is_primary_source=False, confidence=0.85, target_hypothesis="H0",
            target_concept="Solar Storage Tech A", covered_ontology_classes=["Solar Storage Tech A"],
            inconsistency_ratings={"H1": -1.0, "H2": -1.0, "H0": 0.5}
        )

        all_secondary_claims = secondary_h1_claims + [h2_claim, h0_claim]

        contract = ResearchContract(
            question="Solar Tech A vs B", decision_context="Tech Selection", target_object="Solar",
            required_precision="High", output_format="Brief",
            search_mode=SearchMode.RECURSIVE_EVIDENCE_SEARCH, execution_mode=ExecutionMode.LIVE
        )
        ontology = DynamicOntology(domain_name="Solar", classes=["Solar Storage Tech A", "Solar Storage Tech B"], coverage_debt=[])
        matrix = self.engine.evaluate_matrix(hypotheses_no_risk, self._val(all_secondary_claims, hypotheses_no_risk))

        metrics_sec = asyncio.run(orchestrator.evaluate_stopping_rules(
            contract, ontology, all_secondary_claims, matrix, current_depth=1, effective_max_depth=3
        ))

        # Primary ratio is 0.0 -> BLOCKED by high-precision quality gate!
        self.assertEqual(metrics_sec.primary_source_ratio, 0.0)
        self.assertFalse(metrics_sec.stopping_rule_met)
        self.assertIn("verified primary source", metrics_sec.recommended_next_step)

        # Now add 1 verified primary source (e.g. Official Docs)
        primary_claim = AtomicClaim(
            id="c_prim_h1", subject="Solar Storage Tech A", predicate="official_spec", object="certified",
            grounded_summary="Official standard documentation specification.",
            source_url="https://docs.solarcouncil.org/spec", source_title="Official Solar Council Docs",
            source_domain="docs.solarcouncil.org", locator="p1", retrieval_timestamp="2026-08-15T00:00:00Z",
            upstream_origin_id="origin_official_docs", verification_status=VerificationStatus.VERIFIED_PRIMARY,
            is_primary_source=True, confidence=0.95, target_hypothesis="H1",
            target_concept="Solar Storage Tech A", covered_ontology_classes=["Solar Storage Tech A"],
            inconsistency_ratings={"H1": 0.5, "H2": -0.5, "H0": -1.0}
        )

        all_claims_with_primary = all_secondary_claims + [primary_claim]
        matrix_prim = self.engine.evaluate_matrix(hypotheses_no_risk, self._val(all_claims_with_primary, hypotheses_no_risk))
        metrics_prim = asyncio.run(orchestrator.evaluate_stopping_rules(
            contract, ontology, all_claims_with_primary, matrix_prim, current_depth=1, effective_max_depth=3
        ))

        # With 1 verified primary source, primary_source_ratio > 0.0 -> STOPPING UNBLOCKED!
        self.assertGreater(metrics_prim.primary_source_ratio, 0.0)
        self.assertTrue(metrics_prim.stopping_rule_met)

    def test_primary_vs_secondary_source_classification(self):
        """
        [P1] Verify automatic primary authority classification based on exact authority registry.
        Strictly rejects domain, path, and title spoofing.
        """
        # Primary Sources (Registered Canonical Authorities & Subdomains)
        self.assertTrue(GeminiDeepResearchAdapter.is_primary_source("https://github.com/postgres/postgres", "github.com"))
        self.assertTrue(GeminiDeepResearchAdapter.is_primary_source("https://docs.cockroachlabs.com/v23.2/architecture", "docs.cockroachlabs.com"))
        self.assertTrue(GeminiDeepResearchAdapter.is_primary_source("https://w3.org/TR/webauthn-2/", "w3.org"))
        self.assertTrue(GeminiDeepResearchAdapter.is_primary_source("https://postgresql.org/manual/v16/", "postgresql.org"))
        self.assertTrue(GeminiDeepResearchAdapter.is_primary_source("https://ietf.org/rfc/rfc1234.txt", "ietf.org"))
        self.assertTrue(GeminiDeepResearchAdapter.is_primary_source("https://iso.org/standard/1234.html", "iso.org"))

        # Spoofed Domains & Secondary Sources (MUST NOT be Primary)
        self.assertFalse(GeminiDeepResearchAdapter.is_primary_source("https://notgithub.com/postgres/postgres", "notgithub.com"))
        self.assertFalse(GeminiDeepResearchAdapter.is_primary_source("https://fake-postgresql.org/manual", "fake-postgresql.org"))
        self.assertFalse(GeminiDeepResearchAdapter.is_primary_source("https://malicious.example/docs/fake", "malicious.example"))
        self.assertFalse(GeminiDeepResearchAdapter.is_primary_source("https://example.com/spec/v1.0.pdf", "example.com"))
        self.assertFalse(GeminiDeepResearchAdapter.is_primary_source("https://techcrunch.com/2026/08/new-database", "techcrunch.com"))
        self.assertFalse(GeminiDeepResearchAdapter.is_primary_source("https://medium.com/@author/why-postgres-is-best", "medium.com"))
        self.assertFalse(GeminiDeepResearchAdapter.is_primary_source("https://reddit.com/r/programming/comments/123", "reddit.com"))

    def test_real_contract_precision_activates_strict_gates(self):
        """
        [P0] Verify that PrecisionLevel typed contract ('High-Precision Strategic Evidence')
        activates strict EvidenceRequirements (min_primary_roots_h1=1).
        """
        contract = ResearchContract(
            question="Compare CockroachDB vs PostgreSQL", decision_context="DB Migration", target_object="Database",
            required_precision="High-Precision Strategic Evidence", output_format="Brief",
            search_mode=SearchMode.RECURSIVE_EVIDENCE_SEARCH, execution_mode=ExecutionMode.LIVE
        )

        self.assertEqual(contract.precision_level, PrecisionLevel.HIGH)
        self.assertIsNotNone(contract.evidence_requirements)
        self.assertEqual(contract.evidence_requirements.min_primary_roots_h1, 1)
        self.assertEqual(contract.evidence_requirements.min_independent_roots_h1, 3)

    def test_spoofed_domains_and_paths_rejected_as_secondary(self):
        """
        [P0] Verify exact normalized authority registry rejects spoofed domains, paths, and titles.
        """
        is_p1, auth1, reason1 = check_primary_authority("https://notgithub.com/postgres", "notgithub.com")
        self.assertFalse(is_p1)
        self.assertEqual(reason1, "UNREGISTERED_SECONDARY_SOURCE")

        is_p2, auth2, reason2 = check_primary_authority("https://malicious.example/docs/fake", "malicious.example")
        self.assertFalse(is_p2)
        self.assertEqual(reason2, "UNREGISTERED_SECONDARY_SOURCE")

        is_p3, auth3, reason3 = check_primary_authority("https://techblog.io/article", "techblog.io")
        self.assertFalse(is_p3)
        self.assertEqual(reason3, "UNREGISTERED_SECONDARY_SOURCE")

        # Legitimate verified subdomain
        is_p4, auth4, reason4 = check_primary_authority("https://docs.postgresql.org/16/index.html", "docs.postgresql.org")
        self.assertTrue(is_p4)
        self.assertIn("VERIFIED_SUBDOMAIN_AUTHORITY", reason4)

    def test_unrelated_primary_claim_does_not_satisfy_h1_primary_floor(self):
        """
        [P0] Dimensional Relevancy:
        Verify that a primary source claim for an unrelated hypothesis / competitor (H2)
        does NOT satisfy H1's required primary floor (min_primary_roots_h1=1), blocking stopping.
        """
        orchestrator = OntologicalSearchOrchestratorV2()
        hypotheses_no_risk = HypothesisSet(
            primary_h1=self.hypotheses.primary_h1,
            alternative_h2=self.hypotheses.alternative_h2,
            null_h0=self.hypotheses.null_h0,
            risk_lenses=[]
        )

        # 3 secondary blog sources for H1 (distinct domains)
        secondary_h1_claims = [
            AtomicClaim(
                id=f"c_sec_h1_{i}", subject="Solar Storage Tech A", predicate="has_efficiency", object="high",
                grounded_summary=f"Secondary report {i}", source_url=f"https://blog{i}.com/post",
                source_title=f"Blog {i}", source_domain=f"blog{i}.com", locator="p1",
                retrieval_timestamp="2026-08-15T00:00:00Z", upstream_origin_id=f"blog_origin_{i}",
                verification_status=VerificationStatus.VERIFIED_SECONDARY, is_primary_source=False, confidence=0.85,
                target_hypothesis="H1", target_concept="Solar Storage Tech A", covered_ontology_classes=["Solar Storage Tech A"],
                inconsistency_ratings={"H1": 0.5, "H2": -0.5, "H0": -1.0}
            )
            for i in range(3)
        ]

        h0_claim = AtomicClaim(
            id="c_h0", subject="Solar Storage Tech A", predicate="counterevidence", object="limitation",
            grounded_summary="Counterevidence report", source_url="https://skeptic.com", source_title="H0",
            source_domain="skeptic.com", locator="p1", retrieval_timestamp="2026-08-15T00:00:00Z",
            upstream_origin_id="skeptic_origin", verification_status=VerificationStatus.VERIFIED_SECONDARY,
            is_primary_source=False, confidence=0.85, target_hypothesis="H0",
            target_concept="Solar Storage Tech A", covered_ontology_classes=["Solar Storage Tech A"],
            inconsistency_ratings={"H1": -1.0, "H2": -1.0, "H0": 0.5}
        )

        # Primary claim specifically for H2 (Unrelated to H1!)
        unrelated_primary_h2_claim = AtomicClaim(
            id="c_prim_h2", subject="Solar Storage Tech B", predicate="official_spec", object="certified",
            grounded_summary="Official standard documentation for Tech B.",
            source_url="https://docs.solarcouncil.org/spec_b", source_title="Official Solar Council Docs",
            source_domain="docs.solarcouncil.org", locator="p1", retrieval_timestamp="2026-08-15T00:00:00Z",
            upstream_origin_id="origin_official_docs_b", verification_status=VerificationStatus.VERIFIED_PRIMARY,
            is_primary_source=True, confidence=0.95, target_hypothesis="H2",
            target_concept="Solar Storage Tech B", covered_ontology_classes=["Solar Storage Tech B"],
            inconsistency_ratings={"H1": -0.5, "H2": 0.5, "H0": -1.0}
        )

        all_claims = secondary_h1_claims + [h0_claim, unrelated_primary_h2_claim]

        contract = ResearchContract(
            question="Solar Tech A vs B", decision_context="Tech Selection", target_object="Solar",
            required_precision="High-Precision Strategic Evidence", output_format="Brief",
            search_mode=SearchMode.RECURSIVE_EVIDENCE_SEARCH, execution_mode=ExecutionMode.LIVE
        )
        ontology = DynamicOntology(domain_name="Solar", classes=["Solar Storage Tech A", "Solar Storage Tech B"], coverage_debt=[])
        matrix = self.engine.evaluate_matrix(hypotheses_no_risk, self._val(all_claims, hypotheses_no_risk))

        # Evaluate via EvidencePolicy
        evidence_set = EvidencePolicy.evaluate_evidence(
            contract, ontology, all_claims, hypotheses_no_risk, current_depth=1, effective_max_depth=3
        )

        # Primary exists for H2, but H1 primary roots count is 0!
        self.assertEqual(evidence_set.h2_primary_roots_count, 1)
        self.assertEqual(evidence_set.h1_primary_roots_count, 0)
        self.assertGreater(evidence_set.primary_source_ratio, 0.0)

        # Stopping rule must FAIL CLOSED because H1 lacks a primary source!
        metrics = asyncio.run(orchestrator.evaluate_stopping_rules(
            contract, ontology, all_claims, matrix, current_depth=1, effective_max_depth=3
        ))
        self.assertFalse(metrics.stopping_rule_met)
        self.assertIn("verified primary source specifically for H1", metrics.recommended_next_step)

    def test_unknown_precision_level_fails_closed(self):
        """
        [P0] Fail-Closed Security:
        Verify that an unknown or unrecognized precision string strictly triggers
        UNKNOWN_FAIL_CLOSED, blocking stopping rules even if evidence is otherwise present.
        """
        orchestrator = OntologicalSearchOrchestratorV2()
        hypotheses_no_risk = HypothesisSet(
            primary_h1=self.hypotheses.primary_h1,
            alternative_h2=self.hypotheses.alternative_h2,
            null_h0=self.hypotheses.null_h0,
            risk_lenses=[]
        )

        contract = ResearchContract(
            question="Solar Tech A vs B", decision_context="Tech Selection", target_object="Solar",
            required_precision="UNRECOGNIZED_ARBITRARY_PRECISION_STRING", output_format="Brief",
            search_mode=SearchMode.RECURSIVE_EVIDENCE_SEARCH, execution_mode=ExecutionMode.LIVE
        )

        self.assertEqual(contract.precision_level, PrecisionLevel.UNKNOWN_FAIL_CLOSED)
        self.assertTrue(contract.evidence_requirements.is_fail_closed)

        # Even with 3 primary sources for H1, 1 for H2, 1 for H0
        claims = [
            AtomicClaim(
                id=f"c_prim_h1_{i}", subject="Solar Storage Tech A", predicate="efficiency", object="high",
                grounded_summary="Grounded spec", source_url=f"https://github.com/repo{i}",
                source_title="Repo", source_domain=f"github{i}.com", locator="p1",
                retrieval_timestamp="2026-08-15T00:00:00Z", upstream_origin_id=f"github_orig_{i}",
                verification_status=VerificationStatus.VERIFIED_PRIMARY, is_primary_source=True, confidence=0.95,
                target_hypothesis="H1", target_concept="Solar Storage Tech A", covered_ontology_classes=["Solar Storage Tech A"],
                inconsistency_ratings={"H1": 0.5, "H2": -0.5, "H0": -1.0}
            )
            for i in range(3)
        ] + [
            AtomicClaim(
                id="c_prim_h2", subject="Solar Storage Tech B", predicate="cost", object="medium",
                grounded_summary="Grounded spec", source_url="https://w3.org/spec",
                source_title="W3", source_domain="w3.org", locator="p1",
                retrieval_timestamp="2026-08-15T00:00:00Z", upstream_origin_id="w3_orig",
                verification_status=VerificationStatus.VERIFIED_PRIMARY, is_primary_source=True, confidence=0.95,
                target_hypothesis="H2", target_concept="Solar Storage Tech B", covered_ontology_classes=["Solar Storage Tech B"],
                inconsistency_ratings={"H1": -0.5, "H2": 0.5, "H0": -1.0}
            ),
            AtomicClaim(
                id="c_prim_h0", subject="Solar Storage Tech A", predicate="counter", object="limitation",
                grounded_summary="Grounded spec", source_url="https://ietf.org/rfc",
                source_title="IETF", source_domain="ietf.org", locator="p1",
                retrieval_timestamp="2026-08-15T00:00:00Z", upstream_origin_id="ietf_orig",
                verification_status=VerificationStatus.VERIFIED_PRIMARY, is_primary_source=True, confidence=0.95,
                target_hypothesis="H0", target_concept="Solar Storage Tech A", covered_ontology_classes=["Solar Storage Tech A"],
                inconsistency_ratings={"H1": -1.0, "H2": -1.0, "H0": 0.5}
            )
        ]

        ontology = DynamicOntology(domain_name="Solar", classes=["Solar Storage Tech A", "Solar Storage Tech B"], coverage_debt=[])
        matrix = self.engine.evaluate_matrix(hypotheses_no_risk, self._val(claims, hypotheses_no_risk))

        evidence_set = EvidencePolicy.evaluate_evidence(
            contract, ontology, claims, hypotheses_no_risk, current_depth=1, effective_max_depth=3
        )
        self.assertTrue(evidence_set.is_fail_closed)
        self.assertFalse(evidence_set.contract_stopping_criteria_met)

        metrics = asyncio.run(orchestrator.evaluate_stopping_rules(
            contract, ontology, claims, matrix, current_depth=1, effective_max_depth=3
        ))
        self.assertFalse(metrics.stopping_rule_met)
        self.assertIn("Halt: UNKNOWN_PRECISION_LEVEL", metrics.recommended_next_step)

    def test_high_precision_no_primary_cannot_produce_conditional_recommendation(self):
        """
        [P0] Synthesis Gate Bypass Prevention:
        Verify that in High-Precision mode without primary evidence, synthesis strictly emits
        INSUFFICIENT_EVIDENCE_SAFETY_BLOCK and CANNOT bypass contract policy to emit CONDITIONAL_RECOMMENDATION,
        even if risk lenses are present or unassessed.
        """
        orchestrator = OntologicalSearchOrchestratorV2()
        hypotheses_with_risk = HypothesisSet(
            primary_h1=self.hypotheses.primary_h1,
            alternative_h2=self.hypotheses.alternative_h2,
            null_h0=self.hypotheses.null_h0,
            risk_lenses=[
                RiskLens(id="risk_1", name="Latency Degradation", description="Risk of latency degradation under high concurrency")
            ]
        )

        # 3 secondary blog sources for H1 (NO primary source)
        claims = [
            AtomicClaim(
                id=f"c_sec_{i}", subject="CockroachDB", predicate="supports", object="transactions",
                grounded_summary=f"Secondary report {i}", source_url=f"https://blog{i}.com/post",
                source_title=f"Blog {i}", source_domain=f"blog{i}.com", locator="p1",
                retrieval_timestamp="2026-08-15T00:00:00Z", upstream_origin_id=f"blog_orig_{i}",
                verification_status=VerificationStatus.VERIFIED_SECONDARY, is_primary_source=False,
                confidence=0.85, target_hypothesis="H1", target_concept="CockroachDB",
                covered_ontology_classes=["CockroachDB"],
                inconsistency_ratings={"H1": 0.5, "H2": -0.5, "H0": -1.0}
            )
            for i in range(3)
        ] + [
            AtomicClaim(
                id="c_h2", subject="PostgreSQL", predicate="supports", object="acid",
                grounded_summary="Postgres report", source_url="https://blog_pg.com/post",
                source_title="Blog Postgres", source_domain="blog_pg.com", locator="p1",
                retrieval_timestamp="2026-08-15T00:00:00Z", upstream_origin_id="pg_orig",
                verification_status=VerificationStatus.VERIFIED_SECONDARY, is_primary_source=False,
                confidence=0.85, target_hypothesis="H2", target_concept="PostgreSQL",
                covered_ontology_classes=["PostgreSQL"],
                inconsistency_ratings={"H1": -0.5, "H2": 0.5, "H0": -1.0}
            ),
            AtomicClaim(
                id="c_h0", subject="CockroachDB", predicate="has_limitation", object="cross_region_latency",
                grounded_summary="Skeptic report", source_url="https://skeptic.com/post",
                source_title="Skeptic", source_domain="skeptic.com", locator="p1",
                retrieval_timestamp="2026-08-15T00:00:00Z", upstream_origin_id="skeptic_orig",
                verification_status=VerificationStatus.VERIFIED_SECONDARY, is_primary_source=False,
                confidence=0.85, target_hypothesis="H0", target_concept="CockroachDB",
                covered_ontology_classes=["CockroachDB"],
                inconsistency_ratings={"H1": -1.0, "H2": -1.0, "H0": 0.5}
            )
        ]

        contract = ResearchContract(
            question="Compare CockroachDB vs PostgreSQL", decision_context="DB Migration", target_object="Database",
            required_precision="High-Precision Strategic Evidence", output_format="Brief",
            search_mode=SearchMode.RECURSIVE_EVIDENCE_SEARCH, execution_mode=ExecutionMode.LIVE
        )
        ontology = DynamicOntology(domain_name="Database", classes=["CockroachDB", "PostgreSQL"], coverage_debt=[])
        matrix = self.engine.evaluate_matrix(hypotheses_with_risk, self._val(claims, hypotheses_with_risk))

        metrics = asyncio.run(orchestrator.evaluate_stopping_rules(
            contract, ontology, claims, matrix, current_depth=1, effective_max_depth=3
        ))
        self.assertFalse(metrics.stopping_rule_met)

        brief = asyncio.run(orchestrator.synthesize_knowledge_v2(
            contract, ontology, hypotheses_with_risk, claims, matrix, metrics
        ))

        # Must strictly be safety blocked! NEVER conditional recommendation when primary evidence is missing!
        self.assertEqual(brief.status, "INSUFFICIENT_EVIDENCE_SAFETY_BLOCK")
        self.assertNotIn("CONDITIONAL RECOMMENDATION", brief.decision_recommendation)
        self.assertIn("SAFETY GATE TRIGGERED", brief.decision_recommendation)

    def test_arbitrary_platform_repo_rejected_as_secondary(self):
        """
        [P0] Entity/Repository Authority Protection:
        Verify that an arbitrary repository on github.com (e.g. github.com/attacker/fake-evidence)
        is rejected as VERIFIED_SECONDARY, while canonical repositories (e.g. github.com/postgres/postgres)
        are accepted as VERIFIED_PRIMARY.
        """
        # Attacker / user repo on multi-tenant platform
        is_p1, auth1, reason1 = check_primary_authority("https://github.com/attacker/fake-evidence", "github.com")
        self.assertFalse(is_p1)
        self.assertIn("UNVERIFIED_PLATFORM_REPOSITORY", reason1)

        is_p2, auth2, reason2 = check_primary_authority("https://github.com/randomuser/my-db-notes", "github.com")
        self.assertFalse(is_p2)
        self.assertIn("UNVERIFIED_PLATFORM_REPOSITORY", reason2)

        # Canonical verified project on GitHub
        is_p3, auth3, reason3 = check_primary_authority("https://github.com/postgres/postgres", "github.com")
        self.assertTrue(is_p3)
        self.assertEqual(auth3, "OFFICIAL_CODE_REPOSITORY")
        self.assertIn("VERIFIED_CANONICAL_ORGANIZATION", reason3)

        is_p4, auth4, reason4 = check_primary_authority("https://github.com/cockroachdb/cockroach", "github.com")
        self.assertTrue(is_p4)
        self.assertEqual(auth4, "OFFICIAL_CODE_REPOSITORY")

    def test_exploratory_mode_without_h0_counterevidence_satisfies_contract(self):
        """
        [P1] Contract Precision Flexibility:
        Verify that Exploratory precision (require_counterevidence_search=False, min_independent_roots_h0=0)
        satisfies contract stopping criteria with only H1 and H2 evidence.
        """
        contract = ResearchContract(
            question="Compare Tech A vs Tech B", decision_context="Exploration", target_object="Tech",
            required_precision="Exploratory", output_format="Brief",
            search_mode=SearchMode.RECURSIVE_EVIDENCE_SEARCH, execution_mode=ExecutionMode.LIVE
        )
        self.assertEqual(contract.precision_level, PrecisionLevel.EXPLORATORY)
        self.assertFalse(contract.evidence_requirements.require_counterevidence_search)
        self.assertEqual(contract.evidence_requirements.min_independent_roots_h0, 0)

        hypotheses_no_risk = HypothesisSet(
            primary_h1=self.hypotheses.primary_h1,
            alternative_h2=self.hypotheses.alternative_h2,
            null_h0=self.hypotheses.null_h0,
            risk_lenses=[]
        )

        claims = [
            AtomicClaim(
                id="c1", subject="Tech A", predicate="feature", object="good",
                grounded_summary="H1 grounded claim", source_url="https://site1.com", source_title="S1",
                source_domain="site1.com", locator="p1", retrieval_timestamp="2026-08-15T00:00:00Z",
                upstream_origin_id="orig1", verification_status=VerificationStatus.VERIFIED_SECONDARY,
                is_primary_source=False, confidence=0.85, target_hypothesis="H1", target_concept="Tech A",
                covered_ontology_classes=["Tech A"], inconsistency_ratings={"H1": 0.5, "H2": -0.5, "H0": -1.0}
            ),
            AtomicClaim(
                id="c2", subject="Tech B", predicate="feature", object="alt",
                grounded_summary="H2 grounded claim", source_url="https://site2.com", source_title="S2",
                source_domain="site2.com", locator="p1", retrieval_timestamp="2026-08-15T00:00:00Z",
                upstream_origin_id="orig2", verification_status=VerificationStatus.VERIFIED_SECONDARY,
                is_primary_source=False, confidence=0.85, target_hypothesis="H2", target_concept="Tech B",
                covered_ontology_classes=["Tech B"], inconsistency_ratings={"H1": -0.5, "H2": 0.5, "H0": -1.0}
            )
        ]

        ontology = DynamicOntology(domain_name="Tech", classes=["Tech A", "Tech B"], coverage_debt=[])

        # Evaluate evidence without any H0 claim or H0 search
        evidence_set = EvidencePolicy.evaluate_evidence(
            contract, ontology, claims, hypotheses_no_risk, current_depth=1, effective_max_depth=3
        )

        self.assertTrue(evidence_set.contract_stopping_criteria_met)
        self.assertEqual(evidence_set.gate_decision.synthesis_status, "CONCLUSIVE_RECOMMENDATION")

    def test_single_canonical_enum_and_requirements(self):
        """
        [P1] Architecture Refactor & Deduplication:
        Verify that models.py and evidence_policy.py share the exact same canonical enum/schema.
        """
        import models
        import evidence_policy

        self.assertIs(models.PrecisionLevel, evidence_policy.PrecisionLevel)
        self.assertIs(models.EvidenceRequirements, evidence_policy.EvidenceRequirements)
        self.assertIs(models.GateDecision, evidence_policy.GateDecision)

    def test_ach_ignores_rejected_claims_via_validated_evidence_set(self):
        """
        [P1] ACH Engine Validated Evidence Integration:
        Verify that ACH matrix evaluation ignores unverified or rejected claims when consuming
        ValidatedEvidenceSet.
        """
        contract = ResearchContract(
            question="Compare Tech A vs Tech B", decision_context="Context", target_object="Tech",
            required_precision="Standard", output_format="Brief",
            search_mode=SearchMode.RECURSIVE_EVIDENCE_SEARCH, execution_mode=ExecutionMode.LIVE
        )
        ontology = DynamicOntology(domain_name="Tech", classes=["Tech A"], coverage_debt=[])
        hypotheses_no_risk = HypothesisSet(
            primary_h1=self.hypotheses.primary_h1,
            alternative_h2=self.hypotheses.alternative_h2,
            null_h0=self.hypotheses.null_h0,
            risk_lenses=[]
        )

        valid_claim = AtomicClaim(
            id="c_valid", subject="Tech A", predicate="feature", object="good",
            grounded_summary="Valid secondary claim", source_url="https://site1.com", source_title="S1",
            source_domain="site1.com", locator="p1", retrieval_timestamp="2026-08-15T00:00:00Z",
            upstream_origin_id="orig1", verification_status=VerificationStatus.VERIFIED_SECONDARY,
            is_primary_source=False, confidence=0.90, target_hypothesis="H1", target_concept="Tech A",
            covered_ontology_classes=["Tech A"], inconsistency_ratings={"H1": 0.5, "H2": -0.5, "H0": -1.0}
        )

        mock_claim = AtomicClaim(
            id="c_mock_rejected", subject="Tech A", predicate="feature", object="fake",
            grounded_summary="Unverified mock claim", source_url="https://fake.local", source_title="Fake",
            source_domain="fake.local", locator="p1", retrieval_timestamp="2026-08-15T00:00:00Z",
            upstream_origin_id="orig_fake", verification_status=VerificationStatus.UNVERIFIED_MOCK,
            is_primary_source=False, confidence=0.99, target_hypothesis="H1", target_concept="Tech A",
            covered_ontology_classes=["Tech A"], inconsistency_ratings={"H1": 0.5, "H2": -0.5, "H0": -1.0}
        )

        all_claims = [valid_claim, mock_claim]

        evidence_set = EvidencePolicy.evaluate_evidence(
            contract, ontology, all_claims, hypotheses_no_risk, current_depth=1, effective_max_depth=3
        )
        self.assertEqual(len(evidence_set.eligible_claims), 1)
        self.assertEqual(len(evidence_set.rejected_claims), 1)

        # Evaluate matrix with validated_evidence_set
        matrix = self.engine.evaluate_matrix(hypotheses_no_risk, all_claims, validated_evidence_set=evidence_set)

        # The matrix rows must only contain the 1 eligible claim!
        self.assertEqual(len(matrix.rows), 1)
        self.assertEqual(matrix.rows[0].claim_id, "c_valid")

    def test_allowed_sources_constraint_strictly_enforced(self):
        """
        [P0] Contract Integrity:
        Verify that when ResearchContract specifies allowed_sources=["allowed.example"],
        claims from locked.example or other non-whitelisted domains are strictly rejected,
        preventing contract stopping even in Exploratory LIVE mode.
        """
        contract = ResearchContract(
            question="Compare Tech A vs Tech B", decision_context="Context", target_object="Tech",
            required_precision="Exploratory", output_format="Brief",
            search_mode=SearchMode.RECURSIVE_EVIDENCE_SEARCH, execution_mode=ExecutionMode.LIVE,
            allowed_sources=["allowed.example"]
        )
        ontology = DynamicOntology(domain_name="Tech", classes=["Tech A", "Tech B"], coverage_debt=[])
        hypotheses_no_risk = HypothesisSet(
            primary_h1=self.hypotheses.primary_h1,
            alternative_h2=self.hypotheses.alternative_h2,
            null_h0=self.hypotheses.null_h0,
            risk_lenses=[]
        )

        # Claims from locked.example (NOT in allowed_sources)
        locked_claims = [
            AtomicClaim(
                id=f"c_locked_{i}", subject="Tech A", predicate="feature", object="good",
                grounded_summary="Locked domain claim", source_url=f"https://locked.example/doc_{i}",
                source_title="Locked", source_domain="locked.example", locator="p1",
                retrieval_timestamp="2026-08-15T00:00:00Z", upstream_origin_id=f"locked_orig_{i}",
                verification_status=VerificationStatus.VERIFIED_SECONDARY, is_primary_source=False,
                confidence=0.90, target_hypothesis="H1", target_concept="Tech A",
                covered_ontology_classes=["Tech A"], inconsistency_ratings={"H1": 0.5, "H2": -0.5, "H0": -1.0}
            )
            for i in range(3)
        ]

        evidence_set = EvidencePolicy.evaluate_evidence(
            contract, ontology, locked_claims, hypotheses_no_risk, current_depth=1, effective_max_depth=3
        )

        # All claims must be rejected with REJECTED_DISALLOWED_SOURCE
        self.assertEqual(len(evidence_set.eligible_claims), 0)
        self.assertEqual(len(evidence_set.rejected_claims), 3)
        for _, reason in evidence_set.rejected_claims:
            self.assertEqual(reason, "REJECTED_DISALLOWED_SOURCE")

        # Contract stopping criteria MUST BE FALSE
        self.assertFalse(evidence_set.contract_stopping_criteria_met)
        self.assertEqual(evidence_set.gate_decision.synthesis_status, "INSUFFICIENT_EVIDENCE_SAFETY_BLOCK")

    def test_policy_re_verifies_incoming_primary_status_against_uri(self):
        """
        [P0] Primary Authority Verification:
        Verify that EvidencePolicy does NOT trust incoming is_primary_source=True or
        verification_status=VERIFIED_PRIMARY if the source URL is on an unverified domain
        (e.g. https://attacker.example/fake). The claim must be demoted to secondary,
        resulting in h1_primary_roots_count=0 and blocking High-Precision stopping.
        """
        contract = ResearchContract(
            question="Compare Tech A vs Tech B", decision_context="Context", target_object="Tech",
            required_precision="High-Precision Strategic Evidence", output_format="Brief",
            search_mode=SearchMode.RECURSIVE_EVIDENCE_SEARCH, execution_mode=ExecutionMode.LIVE
        )
        ontology = DynamicOntology(domain_name="Tech", classes=["Tech A", "Tech B"], coverage_debt=[])
        hypotheses_no_risk = HypothesisSet(
            primary_h1=self.hypotheses.primary_h1,
            alternative_h2=self.hypotheses.alternative_h2,
            null_h0=self.hypotheses.null_h0,
            risk_lenses=[]
        )

        # 3 claims where one maliciously claims to be VERIFIED_PRIMARY on attacker.example
        claims = [
            AtomicClaim(
                id="c_spoofed_primary", subject="Tech A", predicate="feature", object="good",
                grounded_summary="Attacker fake primary claim", source_url="https://attacker.example/fake",
                source_title="Fake Official", source_domain="attacker.example", locator="p1",
                retrieval_timestamp="2026-08-15T00:00:00Z", upstream_origin_id="attacker_orig",
                verification_status=VerificationStatus.VERIFIED_PRIMARY, is_primary_source=True,
                confidence=0.95, target_hypothesis="H1", target_concept="Tech A",
                covered_ontology_classes=["Tech A"], inconsistency_ratings={"H1": 0.5, "H2": -0.5, "H0": -1.0}
            ),
            AtomicClaim(
                id="c_sec_2", subject="Tech A", predicate="feature", object="good",
                grounded_summary="Secondary claim 2", source_url="https://blog2.com/post",
                source_title="Blog 2", source_domain="blog2.com", locator="p1",
                retrieval_timestamp="2026-08-15T00:00:00Z", upstream_origin_id="blog2_orig",
                verification_status=VerificationStatus.VERIFIED_SECONDARY, is_primary_source=False,
                confidence=0.85, target_hypothesis="H1", target_concept="Tech A",
                covered_ontology_classes=["Tech A"], inconsistency_ratings={"H1": 0.5, "H2": -0.5, "H0": -1.0}
            ),
            AtomicClaim(
                id="c_sec_3", subject="Tech A", predicate="feature", object="good",
                grounded_summary="Secondary claim 3", source_url="https://blog3.com/post",
                source_title="Blog 3", source_domain="blog3.com", locator="p1",
                retrieval_timestamp="2026-08-15T00:00:00Z", upstream_origin_id="blog3_orig",
                verification_status=VerificationStatus.VERIFIED_SECONDARY, is_primary_source=False,
                confidence=0.85, target_hypothesis="H1", target_concept="Tech A",
                covered_ontology_classes=["Tech A"], inconsistency_ratings={"H1": 0.5, "H2": -0.5, "H0": -1.0}
            ),
            AtomicClaim(
                id="c_h2", subject="Tech B", predicate="feature", object="alt",
                grounded_summary="H2 claim", source_url="https://blog_b.com/post",
                source_title="Blog B", source_domain="blog_b.com", locator="p1",
                retrieval_timestamp="2026-08-15T00:00:00Z", upstream_origin_id="blog_b_orig",
                verification_status=VerificationStatus.VERIFIED_SECONDARY, is_primary_source=False,
                confidence=0.85, target_hypothesis="H2", target_concept="Tech B",
                covered_ontology_classes=["Tech B"], inconsistency_ratings={"H1": -0.5, "H2": 0.5, "H0": -1.0}
            ),
            AtomicClaim(
                id="c_h0", subject="Tech A", predicate="limitation", object="bad",
                grounded_summary="H0 claim", source_url="https://skeptic.com/post",
                source_title="Skeptic", source_domain="skeptic.com", locator="p1",
                retrieval_timestamp="2026-08-15T00:00:00Z", upstream_origin_id="skeptic_orig",
                verification_status=VerificationStatus.VERIFIED_SECONDARY, is_primary_source=False,
                confidence=0.85, target_hypothesis="H0", target_concept="Tech A",
                covered_ontology_classes=["Tech A"], inconsistency_ratings={"H1": -1.0, "H2": -1.0, "H0": 0.5}
            )
        ]

        evidence_set = EvidencePolicy.evaluate_evidence(
            contract, ontology, claims, hypotheses_no_risk, current_depth=1, effective_max_depth=3
        )

        # The spoofed claim must be demoted to secondary
        spoofed = next(c for c in evidence_set.eligible_claims if c.id == "c_spoofed_primary")
        self.assertFalse(spoofed.is_primary_source)
        self.assertEqual(spoofed.verification_status, VerificationStatus.VERIFIED_SECONDARY)

        # Primary roots count must be 0!
        self.assertEqual(evidence_set.h1_primary_roots_count, 0)
        self.assertEqual(evidence_set.primary_claims_count, 0)
        self.assertEqual(evidence_set.primary_source_ratio, 0.0)

        # Stopping must be BLOCKED!
        self.assertFalse(evidence_set.contract_stopping_criteria_met)
        self.assertEqual(evidence_set.gate_decision.synthesis_status, "INSUFFICIENT_EVIDENCE_SAFETY_BLOCK")

    def test_missing_evaluated_risk_lenses_blocks_conclusive_recommendation(self):
        """
        [P0] Risk Policy Gate:
        Verify that when hypotheses contain material risk lenses, and ledger has completed risk queries,
        but evaluated_risk_lenses=None (or empty), EvidencePolicy strictly treats risk lenses as unassessed,
        blocking CONCLUSIVE_RECOMMENDATION and setting contract_stopping_criteria_met=False.
        """
        from models import SearchQueryRecord

        contract = ResearchContract(
            question="Compare CockroachDB vs PostgreSQL", decision_context="Context", target_object="Database",
            required_precision="High-Precision Strategic Evidence", output_format="Brief",
            search_mode=SearchMode.RECURSIVE_EVIDENCE_SEARCH, execution_mode=ExecutionMode.LIVE
        )
        ontology = DynamicOntology(domain_name="Database", classes=["CockroachDB", "PostgreSQL"], coverage_debt=[])
        hypotheses_with_risk = HypothesisSet(
            primary_h1=self.hypotheses.primary_h1,
            alternative_h2=self.hypotheses.alternative_h2,
            null_h0=self.hypotheses.null_h0,
            risk_lenses=[
                RiskLens(id="risk_latency", name="Tail Latency Degradation", description="Cross-region p99 risk")
            ]
        )

        claims = [
            AtomicClaim(
                id="c_prim_h1", subject="CockroachDB", predicate="supports", object="transactions",
                grounded_summary="Official spec", source_url="https://docs.cockroachlabs.com/v23.2/architecture",
                source_title="Official Docs", source_domain="docs.cockroachlabs.com", locator="p1",
                retrieval_timestamp="2026-08-15T00:00:00Z", upstream_origin_id="crdb_orig",
                verification_status=VerificationStatus.VERIFIED_PRIMARY, is_primary_source=True,
                confidence=0.95, target_hypothesis="H1", target_concept="CockroachDB", query_id="q_h1",
                covered_ontology_classes=["CockroachDB"], inconsistency_ratings={"H1": 0.5, "H2": -0.5, "H0": -1.0}
            ),
            AtomicClaim(
                id="c_sec_h1_2", subject="CockroachDB", predicate="supports", object="transactions",
                grounded_summary="Secondary 2", source_url="https://blog2.com/post",
                source_title="Blog 2", source_domain="blog2.com", locator="p1",
                retrieval_timestamp="2026-08-15T00:00:00Z", upstream_origin_id="blog2_orig",
                verification_status=VerificationStatus.VERIFIED_SECONDARY, is_primary_source=False,
                confidence=0.85, target_hypothesis="H1", target_concept="CockroachDB", query_id="q_h1",
                covered_ontology_classes=["CockroachDB"], inconsistency_ratings={"H1": 0.5, "H2": -0.5, "H0": -1.0}
            ),
            AtomicClaim(
                id="c_sec_h1_3", subject="CockroachDB", predicate="supports", object="transactions",
                grounded_summary="Secondary 3", source_url="https://blog3.com/post",
                source_title="Blog 3", source_domain="blog3.com", locator="p1",
                retrieval_timestamp="2026-08-15T00:00:00Z", upstream_origin_id="blog3_orig",
                verification_status=VerificationStatus.VERIFIED_SECONDARY, is_primary_source=False,
                confidence=0.85, target_hypothesis="H1", target_concept="CockroachDB", query_id="q_h1",
                covered_ontology_classes=["CockroachDB"], inconsistency_ratings={"H1": 0.5, "H2": -0.5, "H0": -1.0}
            ),
            AtomicClaim(
                id="c_h2", subject="PostgreSQL", predicate="supports", object="acid",
                grounded_summary="Postgres claim", source_url="https://docs.postgresql.org/manual",
                source_title="PG Docs", source_domain="docs.postgresql.org", locator="p1",
                retrieval_timestamp="2026-08-15T00:00:00Z", upstream_origin_id="pg_orig",
                verification_status=VerificationStatus.VERIFIED_PRIMARY, is_primary_source=True,
                confidence=0.95, target_hypothesis="H2", target_concept="PostgreSQL", query_id="q_h2",
                covered_ontology_classes=["PostgreSQL"], inconsistency_ratings={"H1": -0.5, "H2": 0.5, "H0": -1.0}
            ),
            AtomicClaim(
                id="c_h0", subject="CockroachDB", predicate="limitation", object="bad",
                grounded_summary="H0 claim", source_url="https://skeptic.com/post",
                source_title="Skeptic", source_domain="skeptic.com", locator="p1",
                retrieval_timestamp="2026-08-15T00:00:00Z", upstream_origin_id="skeptic_orig",
                verification_status=VerificationStatus.VERIFIED_SECONDARY, is_primary_source=False,
                confidence=0.85, target_hypothesis="H0", target_concept="CockroachDB", query_id="q_h0",
                covered_ontology_classes=["CockroachDB"], inconsistency_ratings={"H1": -1.0, "H2": -1.0, "H0": 0.5}
            )
        ]

        ledger = [
            SearchQueryRecord(query_id="q_h1", query_text="CockroachDB architecture", target_hypothesis="H1", target_concept="CockroachDB", target_risk_lens_id=None, search_strategy="BROAD_OVERVIEW", depth=1, timestamp="2026-08-15T00:00:00Z", status="EXECUTED", retrieved_docs_count=3, extracted_claims_count=3),
            SearchQueryRecord(query_id="q_h2", query_text="PostgreSQL architecture", target_hypothesis="H2", target_concept="PostgreSQL", target_risk_lens_id=None, search_strategy="BROAD_OVERVIEW", depth=1, timestamp="2026-08-15T00:00:00Z", status="EXECUTED", retrieved_docs_count=1, extracted_claims_count=1),
            SearchQueryRecord(query_id="q_h0", query_text="CockroachDB limitations skeptic", target_hypothesis="H0", target_concept="CockroachDB", target_risk_lens_id=None, search_strategy="DISPROVING", depth=1, timestamp="2026-08-15T00:00:00Z", status="EXECUTED", retrieved_docs_count=1, extracted_claims_count=1),
            SearchQueryRecord(query_id="q_risk", query_text="CockroachDB latency risk", target_hypothesis="RISK_LENS", target_concept="CockroachDB", target_risk_lens_id="risk_latency", search_strategy="TARGETED_RISK", depth=1, timestamp="2026-08-15T00:00:00Z", status="EXECUTED", retrieved_docs_count=1, extracted_claims_count=1)
        ]

        # Evaluate evidence with evaluated_risk_lenses = None
        evidence_set = EvidencePolicy.evaluate_evidence(
            contract, ontology, claims, hypotheses_with_risk, current_depth=1, effective_max_depth=3,
            query_ledger=ledger, evaluated_risk_lenses=None
        )

        # Must NOT be contract stopping criteria met!
        self.assertFalse(evidence_set.contract_stopping_criteria_met)
        self.assertEqual(evidence_set.gate_decision.synthesis_status, "CONDITIONAL_RECOMMENDATION")
        self.assertIn("Tail Latency Degradation", evidence_set.gate_decision.unresolved_material_risks)

    def test_allowed_sources_query_and_path_spoofing_rejected(self):
        """
        [P0 Invariant Test] Strict Allowlist Auditing:
        Verify that query parameter spoofing, path spoofing, userinfo, and subdomain spoofing
        are strictly rejected and never match allowed sources.
        """
        allowed = ["allowed.example", "trusted.org"]

        # 1. Query parameter spoofing: https://evil.example/x?next=allowed.example
        is_ok1, reason1 = EvidencePolicy.is_source_url_allowed(
            "https://evil.example/x?next=allowed.example", "evil.example", allowed
        )
        self.assertFalse(is_ok1)
        self.assertIn("DISALLOWED_HOST", reason1)

        # 2. Path spoofing: https://evil.example/allowed.example/docs
        is_ok2, reason2 = EvidencePolicy.is_source_url_allowed(
            "https://evil.example/allowed.example/docs", "evil.example", allowed
        )
        self.assertFalse(is_ok2)
        self.assertIn("DISALLOWED_HOST", reason2)

        # 3. Trailing domain spoofing: https://allowed.example.evil.com/fake
        is_ok3, reason3 = EvidencePolicy.is_source_url_allowed(
            "https://allowed.example.evil.com/fake", "allowed.example.evil.com", allowed
        )
        self.assertFalse(is_ok3)
        self.assertIn("DISALLOWED_HOST", reason3)

        # 4. Legitimate exact match
        is_ok4, reason4 = EvidencePolicy.is_source_url_allowed(
            "https://allowed.example/docs/spec", "allowed.example", allowed
        )
        self.assertTrue(is_ok4)
        self.assertIn("EXACT_MATCH", reason4)

        # 5. Legitimate true subdomain match
        is_ok5, reason5 = EvidencePolicy.is_source_url_allowed(
            "https://sub.allowed.example/api", "sub.allowed.example", allowed
        )
        self.assertTrue(is_ok5)
        self.assertIn("SUBDOMAIN_MATCH", reason5)

        # 6. Malformed allowlist fails closed
        is_ok6, reason6 = EvidencePolicy.is_source_url_allowed(
            "https://allowed.example/doc", "allowed.example", ["invalid:host:8080@evil", "allowed.example"]
        )
        self.assertFalse(is_ok6)
        self.assertIn("MALFORMED_ALLOWLIST_ENTRY", reason6)

    def test_input_claims_immutability_and_policy_idempotence(self):
        """
        [P0 Invariant Test] Pure Trust Boundary & Immutability:
        Verify that EvidencePolicy does NOT mutate input AtomicClaim objects in place,
        and executing validation multiple times is completely idempotent.
        """
        contract = ResearchContract(
            question="Compare Rust vs Go", decision_context="Tech Selection", target_object="Language",
            required_precision="High-Precision Strategic Evidence", output_format="Brief",
            search_mode=SearchMode.RECURSIVE_EVIDENCE_SEARCH, execution_mode=ExecutionMode.LIVE
        )
        ontology = DynamicOntology(domain_name="Language", classes=["Rust", "Go"], coverage_debt=[])

        original_claim = AtomicClaim(
            id="c_mut_test", subject="Rust", predicate="has_feature", object="zero-cost abstractions",
            grounded_summary="Verified compiler spec", source_url="https://rust-lang.org/docs",
            source_title="Rust Docs", source_domain="rust-lang.org", locator="p1",
            retrieval_timestamp="2026-08-15T00:00:00Z", upstream_origin_id="rust_official",
            verification_status=VerificationStatus.VERIFIED_PRIMARY, is_primary_source=False, # Deliberately set to False
            confidence=0.90, target_hypothesis="H1", inconsistency_ratings={"H1": 0.5, "H2": -0.5, "H0": -1.0}
        )

        import copy
        claim_snapshot_before = copy.deepcopy(original_claim)

        # First validation pass
        evidence_set_1 = EvidencePolicy.validate_claims(
            contract, ontology, [original_claim], self.hypotheses
        )

        # Invariant 1: Input claim is completely untouched
        self.assertEqual(original_claim.is_primary_source, claim_snapshot_before.is_primary_source)
        self.assertEqual(original_claim.verification_status, claim_snapshot_before.verification_status)
        self.assertEqual(original_claim.confidence, claim_snapshot_before.confidence)
        self.assertEqual(original_claim.dict(), claim_snapshot_before.dict())

        # Second validation pass (Idempotence)
        evidence_set_2 = EvidencePolicy.validate_claims(
            contract, ontology, [original_claim], self.hypotheses
        )

        self.assertEqual(len(evidence_set_1.eligible_claims), len(evidence_set_2.eligible_claims))
        self.assertEqual(evidence_set_1.h1_primary_roots_count, evidence_set_2.h1_primary_roots_count)
        self.assertEqual(evidence_set_1.primary_source_ratio, evidence_set_2.primary_source_ratio)

    def test_raw_rejected_claims_cannot_enter_ach_or_affect_winner_or_risk(self):
        """
        [P0 Invariant Test] Raw / Rejected Claim Segregation:
        Verify that disallowed or rejected claims NEVER appear in ACHMatrix.rows and
        cannot alter the winning hypothesis or orthogonal risk evaluations.
        """
        contract = ResearchContract(
            question="Compare DBs", decision_context="DB", target_object="Database",
            required_precision="Standard", output_format="Brief",
            allowed_sources=["allowed.org"],
            search_mode=SearchMode.RECURSIVE_EVIDENCE_SEARCH, execution_mode=ExecutionMode.LIVE
        )
        ontology = DynamicOntology(domain_name="DB", classes=["Tech A", "Tech B"], coverage_debt=[])

        eligible_claim = AtomicClaim(
            id="c_eligible", subject="Tech A", predicate="has_feature", object="optimal",
            grounded_summary="Verified performance on allowed domain", source_url="https://allowed.org/spec",
            source_title="Allowed Spec", source_domain="allowed.org", locator="p1",
            retrieval_timestamp="2026-08-15T00:00:00Z", upstream_origin_id="allowed_root",
            verification_status=VerificationStatus.VERIFIED_PRIMARY, is_primary_source=True,
            confidence=0.90, target_hypothesis="H1", inconsistency_ratings={"H1": 0.5, "H2": -0.5, "H0": -1.0}
        )

        # Injected malicious / disallowed claim with high H2 ratings
        malicious_claim = AtomicClaim(
            id="c_evil", subject="Tech B", predicate="has_feature", object="super",
            grounded_summary="Attacker site claim", source_url="https://evil.org/fake",
            source_title="Evil", source_domain="evil.org", locator="p1",
            retrieval_timestamp="2026-08-15T00:00:00Z", upstream_origin_id="evil_root",
            verification_status=VerificationStatus.VERIFIED_PRIMARY, is_primary_source=True,
            confidence=0.99, target_hypothesis="H2", inconsistency_ratings={"H1": -1.0, "H2": 1.0, "H0": -1.0}
        )

        # Phase 1: Validate
        evidence_set = EvidencePolicy.validate_claims(
            contract, ontology, [eligible_claim, malicious_claim], self.hypotheses
        )

        self.assertEqual(len(evidence_set.eligible_claims), 1)
        self.assertEqual(len(evidence_set.rejected_claims), 1)
        self.assertEqual(evidence_set.rejected_claims[0][1], "REJECTED_DISALLOWED_SOURCE")

        # Phase 2: ACH Matrix strictly consumes ValidatedEvidenceSet
        matrix = self.engine.evaluate_matrix(self.hypotheses, evidence_set)

        # Invariant: Malicious claim is NOT in matrix rows
        row_ids = [r.claim_id for r in matrix.rows]
        self.assertIn("c_eligible", row_ids)
        self.assertNotIn("c_evil", row_ids)

        # Winner remains H1, uncorrupted by evil claim
        self.assertEqual(matrix.winning_hypothesis, "H1")
        self.assertLess(matrix.h2_net_score, 0.0)

    def test_duplicate_evidence_preserves_provenance_root_counts(self):
        """
        [Metamorphic Test] Provenance Root Invariance:
        Duplicating the same piece of evidence 1, 5, or 20 times across syndicated URLs
        sharing the same upstream root ID strictly preserves provenance root count == 1.
        """
        contract = ResearchContract(
            question="Compare Tech", decision_context="Eval", target_object="Tech",
            required_precision="Standard", output_format="Brief",
            search_mode=SearchMode.RECURSIVE_EVIDENCE_SEARCH, execution_mode=ExecutionMode.LIVE
        )
        ontology = DynamicOntology(domain_name="Tech", classes=["Tech A"], coverage_debt=[])

        def make_claim(idx: int) -> AtomicClaim:
            return AtomicClaim(
                id=f"c_wire_{idx}", subject="Tech A", predicate="benchmarks", object="high",
                grounded_summary="Syndicated wire report on benchmark", source_url=f"https://news-outlet-{idx}.com/story",
                source_title=f"News {idx}", source_domain=f"news-outlet-{idx}.com", locator="p1",
                retrieval_timestamp="2026-08-15T00:00:00Z", upstream_origin_id="single_shared_wire_origin",
                verification_status=VerificationStatus.VERIFIED_SECONDARY, is_primary_source=False,
                confidence=0.85, target_hypothesis="H1", inconsistency_ratings={"H1": 0.5, "H2": -0.5, "H0": -1.0}
            )

        claims_1 = [make_claim(1)]
        claims_10 = [make_claim(i) for i in range(10)]

        set_1 = EvidencePolicy.validate_claims(contract, ontology, claims_1, self.hypotheses)
        set_10 = EvidencePolicy.validate_claims(contract, ontology, claims_10, self.hypotheses)

        # Root count must remain 1
        self.assertEqual(set_1.h1_diagnostic_origins_count, 1)
        self.assertEqual(set_10.h1_diagnostic_origins_count, 1)
        self.assertEqual(len(set_1.provenance_clusters), 1)
        self.assertEqual(len(set_10.provenance_clusters), 1)

    def test_no_conclusive_or_conditional_synthesis_when_fail_closed(self):
        """
        [P0 Invariant Test] Synthesis Gate Safety:
        Verify that when a contract is fail-closed, synthesis strictly blocks with
        INSUFFICIENT_EVIDENCE_SAFETY_BLOCK and never emits conclusive or conditional recommendation.
        """
        orchestrator = OntologicalSearchOrchestratorV2()
        contract = ResearchContract(
            question="Compare Tech", decision_context="Eval", target_object="Tech",
            required_precision="INVALID_UNKNOWN_PRECISION", output_format="Brief",
            search_mode=SearchMode.RECURSIVE_EVIDENCE_SEARCH, execution_mode=ExecutionMode.LIVE
        )
        ontology = DynamicOntology(domain_name="Tech", classes=["Tech A"], coverage_debt=[])
        matrix = ACHMatrix(
            winning_hypothesis="H1", decision_rationale="Conclusive H1", is_inconclusive=False,
            rows=[], h1_net_score=1.0, h2_net_score=-1.0, h0_net_score=-1.0
        )
        metrics = AuditMetrics(
            coverage_score=1.0, novelty_score=1.0, reliability_score=1.0, counterevidence_searched=True,
            calibration_score=0.85, stopping_rule_met=False, recommended_next_step="Halt",
            unique_upstream_origins_count=3, primary_source_ratio=0.5, current_search_depth=1,
            unresolved_coverage_debt_count=0, searched_classes_count=1, evidenced_classes_count=1,
            h1_diagnostic_origins_count=3, h2_diagnostic_origins_count=1, h0_diagnostic_origins_count=1,
            all_risk_lenses_assessed=True, all_risk_searches_completed=True,
            all_material_risks_sufficiently_assessed=True, unresolved_material_risks=[], executed_queries_count=3
        )

        synthesis = asyncio.run(orchestrator.synthesize_knowledge_v2(
            contract, ontology, self.hypotheses, [], matrix, metrics
        ))

        self.assertEqual(synthesis.status, "INSUFFICIENT_EVIDENCE_SAFETY_BLOCK")
        self.assertNotIn("CONDITIONAL RECOMMENDATION", synthesis.decision_recommendation)
        self.assertIn("SAFETY GATE TRIGGERED", synthesis.decision_recommendation)

    def test_immutable_validated_claim_and_evidence_set_mutations_raise_error(self):
        """
        [P0 Invariant Test] Deep Immutability & Frozen Dataclasses:
        Verify that mutating ValidatedEvidenceSet, ValidatedClaim, nested inconsistency_ratings,
        or collection tuples raises FrozenInstanceError, TypeError, or AttributeError.
        """
        raw_claim = AtomicClaim(
            id="c_freeze", subject="Tech A", predicate="has_feature", object="certified",
            grounded_summary="Verified spec", source_url="https://postgresql.org/docs",
            source_title="Postgres", source_domain="postgresql.org", locator="p1",
            retrieval_timestamp="2026-08-15T00:00:00Z", upstream_origin_id="pg_origin",
            verification_status=VerificationStatus.VERIFIED_PRIMARY, is_primary_source=True,
            confidence=0.95, target_hypothesis="H1", inconsistency_ratings={"H1": 0.5, "H2": -0.5, "H0": -1.0}
        )

        evidence_set = self._val([raw_claim])
        v_claim = evidence_set.eligible_claims[0]

        # 1. Mutating ValidatedEvidenceSet attributes must raise FrozenInstanceError
        import dataclasses
        with self.assertRaises((dataclasses.FrozenInstanceError, AttributeError)):
            evidence_set.contract_stopping_criteria_met = True

        with self.assertRaises((dataclasses.FrozenInstanceError, AttributeError)):
            evidence_set.h1_primary_roots_count = 99

        # 2. Mutating ValidatedClaim attributes must raise FrozenInstanceError
        with self.assertRaises((dataclasses.FrozenInstanceError, AttributeError)):
            v_claim.is_primary_source = False

        # 3. Mutating nested inconsistency_ratings mapping must raise TypeError
        with self.assertRaises(TypeError):
            v_claim.inconsistency_ratings["H1"] = 0.99

        # 4. Mutating collection tuples must raise AttributeError
        with self.assertRaises(AttributeError):
            evidence_set.eligible_claims.append(v_claim)

        with self.assertRaises(AttributeError):
            v_claim.covered_ontology_classes.append("NewClass")

    def test_replace_decision_does_not_mutate_prior_set(self):
        """
        [P0 Invariant Test] Pure Decision Replacement:
        Verify that replacing gate_decision returns a new frozen object and does not
        mutate the prior ValidatedEvidenceSet.
        """
        raw_claim = AtomicClaim(
            id="c_repl", subject="Tech A", predicate="has_feature", object="optimal",
            grounded_summary="Spec", source_url="https://postgresql.org/docs",
            source_title="Postgres", source_domain="postgresql.org", locator="p1",
            retrieval_timestamp="2026-08-15T00:00:00Z", upstream_origin_id="pg_origin",
            verification_status=VerificationStatus.VERIFIED_PRIMARY, is_primary_source=True,
            confidence=0.95, target_hypothesis="H1", inconsistency_ratings={"H1": 0.5, "H2": -0.5, "H0": -1.0}
        )

        evidence_set = self._val([raw_claim])
        self.assertFalse(evidence_set.contract_stopping_criteria_met)

        new_decision = GateDecision(
            is_stopping_allowed=True,
            synthesis_status="CONCLUSIVE_RECOMMENDATION",
            reason="All gates verified.",
            is_fail_closed=False,
            unresolved_material_risks=(),
            action_required="Publish",
            can_synthesize_conditional=False
        )

        updated_set = evidence_set.replace_decision(new_decision)

        # Prior set must remain unmodified
        self.assertIsNot(evidence_set, updated_set)
        self.assertFalse(evidence_set.contract_stopping_criteria_met)
        self.assertEqual(evidence_set.gate_decision.synthesis_status, "INSUFFICIENT_EVIDENCE_SAFETY_BLOCK")

        # New set reflects updated decision
        self.assertTrue(updated_set.contract_stopping_criteria_met)
        self.assertEqual(updated_set.gate_decision.synthesis_status, "CONCLUSIVE_RECOMMENDATION")

    def test_raw_atomic_claims_cannot_create_ach_rows_or_bypass_policy(self):
        """
        [P0 Invariant Test] Raw Claim Rejection in ACH Engine:
        Verify that passing raw AtomicClaim instances directly to ACHHeuerEngine.evaluate_matrix
        fails closed and produces 0 ACH rows.
        """
        raw_claim = AtomicClaim(
            id="c_raw_bypass", subject="Tech A", predicate="has_feature", object="bypassing",
            grounded_summary="Attacker unvalidated claim", source_url="https://unvalidated.example/x",
            source_title="Unvalidated", source_domain="unvalidated.example", locator="p1",
            retrieval_timestamp="2026-08-15T00:00:00Z", upstream_origin_id="attacker_root",
            verification_status=VerificationStatus.VERIFIED_PRIMARY, is_primary_source=True,
            confidence=0.99, target_hypothesis="H1", inconsistency_ratings={"H1": 1.0, "H2": -1.0, "H0": -1.0}
        )

        # Direct API call with raw AtomicClaim sequence
        matrix = self.engine.evaluate_matrix(self.hypotheses, [raw_claim])

        # Must fail closed: no ACH rows, inconclusive, all hypotheses untested
        self.assertEqual(len(matrix.rows), 0)
        self.assertTrue(matrix.is_inconclusive)
        self.assertEqual(matrix.winning_hypothesis, "ALL_HYPOTHESES_UNTESTED")
        self.assertEqual(matrix.h1_positive_support, 0.0)

    def test_audit_metrics_stopping_and_risk_flags_mirror_canonical_policy_facts(self):
        """
        [P0 Invariant Test] Pure AuditMetrics Projection:
        Verify that AuditMetrics stopping and risk flags are a 100% pure projection
        of canonical GateDecision and ValidatedEvidenceSet audit facts.
        """
        orchestrator = OntologicalSearchOrchestratorV2()
        contract = ResearchContract(
            question="Compare DBs", decision_context="DB", target_object="Database",
            required_precision="Standard", output_format="Brief",
            search_mode=SearchMode.RECURSIVE_EVIDENCE_SEARCH, execution_mode=ExecutionMode.LIVE
        )
        ontology = DynamicOntology(domain_name="DB", classes=["Tech A", "Tech B"], coverage_debt=[])

        raw_claim = AtomicClaim(
            id="c_audit", subject="Tech A", predicate="has_feature", object="robust",
            grounded_summary="Verified performance", source_url="https://postgresql.org/docs",
            source_title="Postgres", source_domain="postgresql.org", locator="p1",
            retrieval_timestamp="2026-08-15T00:00:00Z", upstream_origin_id="pg_origin",
            verification_status=VerificationStatus.VERIFIED_PRIMARY, is_primary_source=True,
            confidence=0.92, target_hypothesis="H1", inconsistency_ratings={"H1": 0.5, "H2": -0.5, "H0": -1.0}
        )

        evidence_set = self._val([raw_claim])
        matrix = self.engine.evaluate_matrix(self.hypotheses, evidence_set)

        decision = EvidencePolicy.evaluate_gate_decision(
            contract, ontology, self.hypotheses, evidence_set, matrix, query_ledger=None, current_depth=1, effective_max_depth=3
        )

        metrics = asyncio.run(orchestrator.evaluate_stopping_rules(
            contract, ontology, [raw_claim], matrix, current_depth=1, effective_max_depth=3,
            validated_evidence_set=evidence_set, gate_decision=decision
        ))

        # Metrics must exactly mirror canonical policy facts
        self.assertEqual(metrics.stopping_rule_met, decision.is_stopping_allowed)
        self.assertEqual(metrics.counterevidence_searched, decision.counterevidence_searched)
        self.assertEqual(metrics.all_risk_searches_completed, decision.all_risk_searches_completed)
        self.assertEqual(metrics.all_material_risks_sufficiently_assessed, decision.all_material_risks_assessed)
        self.assertEqual(metrics.unresolved_material_risks, list(decision.unresolved_material_risks))
        self.assertEqual(metrics.executed_queries_count, decision.executed_queries_count)
        self.assertEqual(metrics.searched_classes_count, decision.searched_classes_count)
        self.assertEqual(metrics.reliability_score, decision.reliability_score)
        self.assertEqual(metrics.novelty_score, decision.novelty_score)
        self.assertEqual(metrics.calibration_score, decision.calibration_score)

    def test_json_serialization_round_trip_and_immutability(self):
        """
        [P0 Invariant Test] JSON Serialization & MappingProxy Safety:
        Verify that ValidatedEvidenceSet.dict() converts MappingProxyType to plain copied dict,
        json.dumps(evidence_set.dict()) succeeds and round-trips both eligible and rejected claims,
        while the in-memory representation remains strictly frozen and immutable.
        """
        import json
        from types import MappingProxyType

        contract = ResearchContract(
            question="Compare Tech", decision_context="Context", target_object="Tech",
            required_precision="Standard", output_format="Brief",
            allowed_sources=["postgresql.org"],
            search_mode=SearchMode.RECURSIVE_EVIDENCE_SEARCH, execution_mode=ExecutionMode.LIVE
        )
        ontology = DynamicOntology(domain_name="Tech", classes=["Tech A", "Tech B"], coverage_debt=[])

        eligible_raw = AtomicClaim(
            id="c_ser_eligible", subject="Tech A", predicate="has_feature", object="optimal",
            grounded_summary="Verified performance on allowed host", source_url="https://postgresql.org/docs",
            source_title="Postgres", source_domain="postgresql.org", locator="p1",
            retrieval_timestamp="2026-08-15T00:00:00Z", upstream_origin_id="pg_root",
            verification_status=VerificationStatus.VERIFIED_PRIMARY, is_primary_source=True,
            confidence=0.95, target_hypothesis="H1", inconsistency_ratings={"H1": 0.5, "H2": -0.5, "H0": -1.0}
        )

        rejected_raw = AtomicClaim(
            id="c_ser_rejected", subject="Tech B", predicate="has_feature", object="blocked",
            grounded_summary="Disallowed host claim", source_url="https://disallowed.example/fake",
            source_title="Disallowed", source_domain="disallowed.example", locator="p1",
            retrieval_timestamp="2026-08-15T00:00:00Z", upstream_origin_id="disallowed_root",
            verification_status=VerificationStatus.VERIFIED_PRIMARY, is_primary_source=True,
            confidence=0.80, target_hypothesis="H2", inconsistency_ratings={"H1": -1.0, "H2": 1.0, "H0": -1.0}
        )

        evidence_set = EvidencePolicy.validate_claims(
            contract, ontology, [eligible_raw, rejected_raw], self.hypotheses
        )

        # 1. In-memory object must have MappingProxyType
        in_memory_claim = evidence_set.eligible_claims[0]
        self.assertIsInstance(in_memory_claim.inconsistency_ratings, MappingProxyType)
        with self.assertRaises(TypeError):
            in_memory_claim.inconsistency_ratings["H1"] = 0.99

        # 2. Serialize to dictionary
        d = evidence_set.dict()
        self.assertIsInstance(d, dict)
        self.assertIsInstance(d["eligible_claims"], list)
        self.assertIsInstance(d["rejected_claims"], list)
        self.assertIsInstance(d["provenance_clusters"], list)
        self.assertEqual(len(d["eligible_claims"]), 1)
        self.assertEqual(len(d["rejected_claims"]), 1)

        # 3. JSON dump and load round-trip
        json_str = json.dumps(d)
        self.assertIsInstance(json_str, str)

        loaded = json.loads(json_str)
        self.assertEqual(loaded["eligible_claims"][0]["id"], "c_ser_eligible")
        self.assertEqual(loaded["eligible_claims"][0]["inconsistency_ratings"]["H1"], 0.5)
        self.assertEqual(loaded["rejected_claims"][0][0]["id"], "c_ser_rejected")
        self.assertEqual(loaded["rejected_claims"][0][1], "REJECTED_DISALLOWED_SOURCE")

        # 4. In-memory object still remains immutable after dict serialization
        self.assertIsInstance(in_memory_claim.inconsistency_ratings, MappingProxyType)
        with self.assertRaises(TypeError):
            in_memory_claim.inconsistency_ratings["H1"] = 0.99

    def test_provenance_fields_preserved_in_validated_claim_matrix_row_and_json(self):
        """
        [P0 Invariant Test] Provenance Field Preservation:
        Verify that ValidatedClaim and ACHMatrixRow preserve exact source_title, locator,
        and retrieval_timestamp, and that all provenance fields survive JSON serialization.
        """
        import json
        raw_claim = AtomicClaim(
            id="c_prov_test",
            subject="PostgreSQL",
            predicate="supports",
            object="ACID transactions",
            grounded_summary="Postgres 16 docs state full ACID compliance.",
            verbatim_quote="PostgreSQL provides full ACID support for all transactions.",
            source_url="https://postgresql.org/docs/16/acid.html",
            source_title="PostgreSQL 16 Official Manual",
            source_domain="postgresql.org",
            locator="Chapter 13.1, para 4",
            retrieval_timestamp="2026-08-15T05:10:00Z",
            upstream_origin_id="pg_acid_manual",
            verification_status=VerificationStatus.VERIFIED_PRIMARY,
            is_primary_source=True,
            confidence=0.98,
            target_hypothesis="H1",
            inconsistency_ratings={"H1": 0.5, "H2": -0.5, "H0": -1.0}
        )

        evidence_set = self._val([raw_claim])
        v_claim = evidence_set.eligible_claims[0]

        # 1. ValidatedClaim attributes
        self.assertEqual(v_claim.source_title, "PostgreSQL 16 Official Manual")
        self.assertEqual(v_claim.locator, "Chapter 13.1, para 4")
        self.assertEqual(v_claim.retrieval_timestamp, "2026-08-15T05:10:00Z")

        # 2. ACHMatrixRow attributes
        matrix = self.engine.evaluate_matrix(self.hypotheses, evidence_set)
        self.assertEqual(len(matrix.rows), 1)
        row = matrix.rows[0]
        self.assertEqual(row.source_url, "https://postgresql.org/docs/16/acid.html")
        self.assertEqual(row.source_title, "PostgreSQL 16 Official Manual")
        self.assertEqual(row.locator, "Chapter 13.1, para 4")
        self.assertEqual(row.retrieval_timestamp, "2026-08-15T05:10:00Z")

        # 3. JSON round-trip
        row_dict = row.dict()
        self.assertEqual(row_dict["source_title"], "PostgreSQL 16 Official Manual")
        self.assertEqual(row_dict["locator"], "Chapter 13.1, para 4")
        self.assertEqual(row_dict["retrieval_timestamp"], "2026-08-15T05:10:00Z")

        dumped = json.dumps(evidence_set.dict())
        loaded = json.loads(dumped)
        c_json = loaded["eligible_claims"][0]
        self.assertEqual(c_json["source_title"], "PostgreSQL 16 Official Manual")
        self.assertEqual(c_json["locator"], "Chapter 13.1, para 4")
        self.assertEqual(c_json["retrieval_timestamp"], "2026-08-15T05:10:00Z")

    def test_rejected_claims_cannot_appear_in_synthesis_confirmed_facts_counts_or_contradictions(self):
        """
        [P0 Invariant Test] Synthesis Isolation of Rejected Evidence:
        Verify that synthesize_knowledge_v2 consumes only eligible claims.
        A claim from evil.example rejected by allowlist must NEVER appear in confirmed_facts,
        strong inference counts, contradictions, confidence, or recommendations.
        """
        orchestrator = OntologicalSearchOrchestratorV2()
        contract = ResearchContract(
            question="Compare DBs", decision_context="DB", target_object="Database",
            required_precision="Standard", output_format="Brief",
            allowed_sources=["postgresql.org"],
            search_mode=SearchMode.RECURSIVE_EVIDENCE_SEARCH, execution_mode=ExecutionMode.LIVE
        )
        ontology = DynamicOntology(domain_name="DB", classes=["Tech A", "Tech B"], coverage_debt=[])

        valid_claim = AtomicClaim(
            id="c_valid_auth", subject="Tech A", predicate="has_feature", object="optimal",
            grounded_summary="Valid Postgres benchmark", source_url="https://postgresql.org/docs",
            source_title="Postgres Manual", source_domain="postgresql.org", locator="p1",
            retrieval_timestamp="2026-08-15T00:00:00Z", upstream_origin_id="pg_root",
            verification_status=VerificationStatus.VERIFIED_PRIMARY, is_primary_source=True,
            confidence=0.95, target_hypothesis="H1", inconsistency_ratings={"H1": 0.5, "H2": -0.5, "H0": -1.0}
        )

        evil_claim = AtomicClaim(
            id="c_evil_fake", subject="Attacker Tech", predicate="is_superior_to", object="all",
            grounded_summary="Attacker fake benchmark from disallowed domain", source_url="https://evil.example/fake",
            source_title="Evil Site", source_domain="evil.example", locator="p99",
            retrieval_timestamp="2026-08-15T00:00:00Z", upstream_origin_id="evil_root",
            verification_status=VerificationStatus.VERIFIED_PRIMARY, is_primary_source=True,
            confidence=0.99, target_hypothesis="H0", inconsistency_ratings={"H1": -1.0, "H2": -1.0, "H0": 1.0}
        )

        evidence_set = EvidencePolicy.validate_claims(
            contract, ontology, [valid_claim, evil_claim], self.hypotheses
        )
        self.assertEqual(len(evidence_set.eligible_claims), 1)
        self.assertEqual(len(evidence_set.rejected_claims), 1)

        matrix = self.engine.evaluate_matrix(self.hypotheses, evidence_set)
        decision = EvidencePolicy.evaluate_gate_decision(
            contract, ontology, self.hypotheses, evidence_set, matrix, query_ledger=None, current_depth=1, effective_max_depth=3
        )
        metrics = asyncio.run(orchestrator.evaluate_stopping_rules(
            contract, ontology, [valid_claim, evil_claim], matrix, current_depth=1, effective_max_depth=3,
            validated_evidence_set=evidence_set, gate_decision=decision
        ))

        synthesis = asyncio.run(orchestrator.synthesize_knowledge_v2(
            contract, ontology, self.hypotheses, [valid_claim, evil_claim], matrix, metrics,
            validated_evidence_set=evidence_set
        ))

        # 1. Evil claim must NOT appear in confirmed_facts
        for fact in synthesis.confirmed_facts:
            self.assertNotIn("evil.example", fact)
            self.assertNotIn("Attacker Tech", fact)

        # 2. Strong inferences must count ONLY verified eligible claims (1, not 2)
        inferences_text = " ".join(synthesis.strong_inferences)
        self.assertIn("Evaluated 1 verified eligible atomic claims", inferences_text)
        self.assertNotIn("Evaluated 2", inferences_text)

        # 3. Contradictions must count 0 counter-evidence records (evil H0 was rejected)
        contradictions_text = " ".join(synthesis.contradictions)
        self.assertIn("evaluated 0 counter-evidence records", contradictions_text)

        # 4. Evil claim appears solely in rejected_evidence_audit
        self.assertEqual(len(synthesis.rejected_evidence_audit), 1)
        self.assertIn("evil.example", synthesis.rejected_evidence_audit[0])
        self.assertIn("REJECTED_DISALLOWED_SOURCE", synthesis.rejected_evidence_audit[0])

    def test_non_http_schemes_fail_closed_in_authority_and_allowlist(self):
        """
        [P1 Invariant Test] URI Scheme Enforcement:
        Verify that non-http/https schemes (javascript:, data:, file:, ftp:) are rejected
        and cannot be classified as primary authority or allowed sources.
        """
        disallowed_uris = [
            "javascript://postgresql.org/docs",
            "javascript:alert(1)",
            "data:text/html,<h1>attack</h1>",
            "file:///etc/passwd",
            "ftp://postgresql.org/pub/docs"
        ]

        for uri in disallowed_uris:
            # 1. check_primary_authority fails closed
            is_primary, auth_type, reason = check_primary_authority(uri, "postgresql.org")
            self.assertFalse(is_primary)
            self.assertIn("DISALLOWED_URI_SCHEME", reason)

            # 2. normalize_source fails closed
            norm_source = normalize_source(uri, "postgresql.org")
            self.assertFalse(norm_source.is_primary_authority)
            self.assertIn("DISALLOWED_URI_SCHEME", norm_source.authority_reason)

            # 3. is_source_url_allowed fails closed
            is_allowed, allow_reason = is_source_url_allowed(uri, "postgresql.org", ["postgresql.org"])
            self.assertFalse(is_allowed)
            self.assertIn("DISALLOWED_CLAIM_URI_SCHEME", allow_reason)

    def test_platform_organization_root_without_repo_rejected_as_secondary(self):
        """
        [P1 Invariant Test] Multi-Tenant Platform Namespace Boundary:
        Verify that github.com/postgres (bare org root without repository) is rejected as primary authority,
        while github.com/postgres/postgres is recognized as OFFICIAL_CODE_REPOSITORY.
        """
        # Bare org root without repository
        is_primary, auth_type, reason = check_primary_authority("https://github.com/postgres", "github.com")
        self.assertFalse(is_primary)
        self.assertIn("missing repository name", reason)

        is_primary_slash, auth_type_slash, reason_slash = check_primary_authority("https://github.com/postgres/", "github.com")
        self.assertFalse(is_primary_slash)
        self.assertIn("missing repository name", reason_slash)

        # Valid repository under canonical organization
        is_primary_repo, auth_type_repo, reason_repo = check_primary_authority("https://github.com/postgres/postgres", "github.com")
        self.assertTrue(is_primary_repo)
        self.assertEqual(auth_type_repo, "OFFICIAL_CODE_REPOSITORY")
        self.assertIn("VERIFIED_CANONICAL_ORGANIZATION", reason_repo)

    def test_query_ledger_forged_query_id_rejected_in_live_mode(self):
        """
        [P0 Lineage Invariant Test] Forged Query ID Rejection:
        Verify that a LIVE claim with query_id='q_forged' is rejected when the ledger
        contains only 'q_real_h1'.
        """
        contract = ResearchContract(
            question="Compare DBs", decision_context="DB", target_object="Database",
            required_precision="Standard", output_format="Brief",
            search_mode=SearchMode.RECURSIVE_EVIDENCE_SEARCH, execution_mode=ExecutionMode.LIVE
        )
        ontology = DynamicOntology(domain_name="DB", classes=["Tech A"], coverage_debt=[])
        ledger = [
            SearchQueryRecord(
                query_id="q_real_h1", query_text="tech a performance",
                target_hypothesis="H1", status="EXECUTED"
            )
        ]

        claim = AtomicClaim(
            id="c_forged", subject="Tech A", predicate="has_feature", object="optimal",
            grounded_summary="Spec", source_url="https://postgresql.org/docs",
            source_title="Postgres", source_domain="postgresql.org", locator="p1",
            retrieval_timestamp="2026-08-15T00:00:00Z", upstream_origin_id="pg_origin",
            verification_status=VerificationStatus.VERIFIED_PRIMARY, is_primary_source=True,
            confidence=0.95, target_hypothesis="H1", query_id="q_forged"
        )

        evidence_set = EvidencePolicy.validate_claims(
            contract, ontology, [claim], self.hypotheses, query_ledger=ledger
        )

        self.assertEqual(len(evidence_set.eligible_claims), 0)
        self.assertEqual(len(evidence_set.rejected_claims), 1)
        self.assertEqual(evidence_set.rejected_claims[0][1], "REJECTED_UNKNOWN_QUERY_ID")
        self.assertEqual(evidence_set.rejected_claims[0][0].rejection_reason_code, "REJECTED_UNKNOWN_QUERY_ID")

    def test_query_ledger_failed_query_status_rejected_in_live_mode(self):
        """
        [P0 Lineage Invariant Test] Failed Query Status Rejection:
        Verify that a claim bound to a FAILED or NO_RESULTS query is rejected.
        """
        contract = ResearchContract(
            question="Compare DBs", decision_context="DB", target_object="Database",
            required_precision="Standard", output_format="Brief",
            search_mode=SearchMode.RECURSIVE_EVIDENCE_SEARCH, execution_mode=ExecutionMode.LIVE
        )
        ontology = DynamicOntology(domain_name="DB", classes=["Tech A"], coverage_debt=[])
        ledger = [
            SearchQueryRecord(
                query_id="q_fail", query_text="tech a performance",
                target_hypothesis="H1", status="FAILED"
            )
        ]

        claim = AtomicClaim(
            id="c_from_fail", subject="Tech A", predicate="has_feature", object="optimal",
            grounded_summary="Spec", source_url="https://postgresql.org/docs",
            source_title="Postgres", source_domain="postgresql.org", locator="p1",
            retrieval_timestamp="2026-08-15T00:00:00Z", upstream_origin_id="pg_origin",
            verification_status=VerificationStatus.VERIFIED_PRIMARY, is_primary_source=True,
            confidence=0.95, target_hypothesis="H1", query_id="q_fail"
        )

        evidence_set = EvidencePolicy.validate_claims(
            contract, ontology, [claim], self.hypotheses, query_ledger=ledger
        )

        self.assertEqual(len(evidence_set.eligible_claims), 0)
        self.assertEqual(len(evidence_set.rejected_claims), 1)
        self.assertEqual(evidence_set.rejected_claims[0][1], "REJECTED_FAILED_QUERY_LINEAGE")

    def test_query_ledger_target_hypothesis_mismatch_rejected_in_live_mode(self):
        """
        [P0 Lineage Invariant Test] Hypothesis Lineage Mismatch Rejection:
        Verify that a claim bound to a query targeting 'H1' but self-labeling 'H2' is rejected.
        """
        contract = ResearchContract(
            question="Compare DBs", decision_context="DB", target_object="Database",
            required_precision="Standard", output_format="Brief",
            search_mode=SearchMode.RECURSIVE_EVIDENCE_SEARCH, execution_mode=ExecutionMode.LIVE
        )
        ontology = DynamicOntology(domain_name="DB", classes=["Tech A"], coverage_debt=[])
        ledger = [
            SearchQueryRecord(
                query_id="q_real_h1", query_text="tech a performance",
                target_hypothesis="H1", status="EXECUTED"
            )
        ]

        claim = AtomicClaim(
            id="c_mismatch_hyp", subject="Tech A", predicate="has_feature", object="optimal",
            grounded_summary="Spec", source_url="https://postgresql.org/docs",
            source_title="Postgres", source_domain="postgresql.org", locator="p1",
            retrieval_timestamp="2026-08-15T00:00:00Z", upstream_origin_id="pg_origin",
            verification_status=VerificationStatus.VERIFIED_PRIMARY, is_primary_source=True,
            confidence=0.95, target_hypothesis="H2", query_id="q_real_h1"
        )

        evidence_set = EvidencePolicy.validate_claims(
            contract, ontology, [claim], self.hypotheses, query_ledger=ledger
        )

        self.assertEqual(len(evidence_set.eligible_claims), 0)
        self.assertEqual(len(evidence_set.rejected_claims), 1)
        self.assertEqual(evidence_set.rejected_claims[0][1], "REJECTED_QUERY_HYPOTHESIS_MISMATCH")

    def test_query_ledger_risk_lens_and_concept_mismatch_rejected_in_live_mode(self):
        """
        [P0 Lineage Invariant Test] Risk Lens & Concept Mismatch Rejection:
        Verify that risk lens / concept mismatches against the ledger record are rejected.
        """
        contract = ResearchContract(
            question="Compare DBs", decision_context="DB", target_object="Database",
            required_precision="Standard", output_format="Brief",
            search_mode=SearchMode.RECURSIVE_EVIDENCE_SEARCH, execution_mode=ExecutionMode.LIVE
        )
        ontology = DynamicOntology(domain_name="DB", classes=["Tech A"], coverage_debt=[])
        ledger = [
            SearchQueryRecord(
                query_id="q_risk", query_text="tech a vulnerability",
                target_hypothesis="RISK_LENS", target_risk_lens_id="RL_SECURITY", status="EXECUTED"
            )
        ]

        claim = AtomicClaim(
            id="c_mismatch_lens", subject="Tech A", predicate="has_risk", object="financial",
            grounded_summary="Risk", source_url="https://postgresql.org/docs",
            source_title="Postgres", source_domain="postgresql.org", locator="p1",
            retrieval_timestamp="2026-08-15T00:00:00Z", upstream_origin_id="pg_origin",
            verification_status=VerificationStatus.VERIFIED_PRIMARY, is_primary_source=True,
            confidence=0.95, target_hypothesis="RISK_LENS", target_risk_lens_id="RL_FINANCIAL", query_id="q_risk"
        )

        evidence_set = EvidencePolicy.validate_claims(
            contract, ontology, [claim], self.hypotheses, query_ledger=ledger
        )

        self.assertEqual(len(evidence_set.eligible_claims), 0)
        self.assertEqual(len(evidence_set.rejected_claims), 1)
        self.assertEqual(evidence_set.rejected_claims[0][1], "REJECTED_QUERY_RISK_LENS_MISMATCH")

    def test_vc_diligence_orchestrator_dynamic_pipeline_all_profiles(self):
        """
        [P0/P1 Generality Invariant Test] Dynamic VC Diligence Execution:
        Verify that MilTech, Pharma, PropTech, Consumer (Lensa), and Unknown profiles
        all route through the unified dynamic OntologicalSearchOrchestratorV2 pipeline
        without hardcoded branch conditionals.
        """
        orchestrator = VCDueDiligenceOrchestrator()

        profiles = [
            StartupProfile(name="Moodro MilTech", category="AI + MilTech & Defense", website="https://moodro.local", stated_mission="UAV EW Autonomy", target_market="Defense"),
            StartupProfile(name="Insilico Pharma", category="AI + Pharma & Biotech", website="https://insilico.local", stated_mission="Generative small molecules", target_market="Oncology"),
            StartupProfile(name="PropTech AI", category="AI + PropTech", website="https://proptech.local", stated_mission="Generative zoning feasibility", target_market="Real Estate"),
            StartupProfile(name="Lensa AI", category="AI + Consumer & Creative", website="https://lensa.local", stated_mission="Magic Avatars portrait generation", target_market="Consumer Media"),
            StartupProfile(name="Frontier AI", category="AI + Quantum Computing", website="https://frontier.local", stated_mission="Quantum error mitigation", target_market="Quantum Computing")
        ]

        for profile in profiles:
            report = asyncio.run(orchestrator.audit_startup(profile))
            self.assertEqual(report.startup_name, profile.name)
            self.assertEqual(report.category, profile.category)
            self.assertTrue(report.is_synthetic_demo)
            self.assertIn("MOCK simulation mode", report.warning_notice)
            self.assertIn("tech_moat_evaluation", report.dict())
            self.assertIn("red_flags", report.dict())
            self.assertIn("investment_recommendation", report.dict())

    def test_live_mode_cannot_consume_synthetic_demo_profiles(self):
        """
        [P1 Generality Invariant Test] LIVE Mode Isolation:
        Verify that LIVE execution mode requires verified live retrieval and cannot treat
        mock simulation data as verified primary evidence.
        """
        contract = ResearchContract(
            question="Audit Lensa", decision_context="VC", target_object="Lensa AI",
            required_precision="Strategic Decision", output_format="Brief",
            search_mode=SearchMode.RECURSIVE_EVIDENCE_SEARCH, execution_mode=ExecutionMode.LIVE
        )
        ontology = DynamicOntology(domain_name="VC", classes=["Lensa AI"], coverage_debt=[])

        # 1. Claim from mock URL with UNVERIFIED_MOCK status in LIVE mode
        mock_claim_http = AtomicClaim(
            id="c_mock_http", subject="Lensa AI", predicate="has_feature", object="Magic Avatars",
            grounded_summary="Synthetic mock summary", source_url="https://lensa.ai/press",
            source_title="Mock Document", source_domain="lensa.ai", locator="p1",
            retrieval_timestamp="2026-08-15T00:00:00Z", upstream_origin_id="mock_origin",
            verification_status=VerificationStatus.UNVERIFIED_MOCK, is_primary_source=False,
            confidence=0.50, target_hypothesis="H1"
        )

        evidence_set_http = EvidencePolicy.validate_claims(contract, ontology, [mock_claim_http], self.hypotheses)
        self.assertEqual(len(evidence_set_http.eligible_claims), 0)
        self.assertEqual(len(evidence_set_http.rejected_claims), 1)
        self.assertEqual(evidence_set_http.rejected_claims[0][1], "REJECTED_UNVERIFIED_MOCK")

        # 2. Claim from synthetic simulation URL scheme in LIVE mode
        mock_claim_sim = AtomicClaim(
            id="c_mock_sim", subject="Lensa AI", predicate="has_feature", object="Magic Avatars",
            grounded_summary="Synthetic mock summary", source_url="simulation://mock_profile",
            source_title="Mock Document", source_domain="simulation.local", locator="p1",
            retrieval_timestamp="2026-08-15T00:00:00Z", upstream_origin_id="mock_origin",
            verification_status=VerificationStatus.UNVERIFIED_MOCK, is_primary_source=False,
            confidence=0.50, target_hypothesis="H1"
        )

        evidence_set_sim = EvidencePolicy.validate_claims(contract, ontology, [mock_claim_sim], self.hypotheses)
        self.assertEqual(len(evidence_set_sim.eligible_claims), 0)
        self.assertEqual(len(evidence_set_sim.rejected_claims), 1)
        self.assertEqual(evidence_set_sim.rejected_claims[0][1], "REJECTED_DISALLOWED_SOURCE")

    def test_empty_query_ledger_rejects_all_live_claims(self):
        """
        [P0 Lineage Invariant Test] Empty Query Ledger Rejection:
        Verify that in LIVE mode, if an empty query_ledger=[] is supplied,
        all claims are rejected because no executed queries exist in the ledger.
        """
        contract = ResearchContract(
            question="Compare DBs", decision_context="DB", target_object="Database",
            required_precision="Standard", output_format="Brief",
            search_mode=SearchMode.RECURSIVE_EVIDENCE_SEARCH, execution_mode=ExecutionMode.LIVE
        )
        ontology = DynamicOntology(domain_name="DB", classes=["Tech A"], coverage_debt=[])

        claim = AtomicClaim(
            id="c_orphaned", subject="Tech A", predicate="has_feature", object="optimal",
            grounded_summary="Spec", source_url="https://postgresql.org/docs",
            source_title="Postgres", source_domain="postgresql.org", locator="p1",
            retrieval_timestamp="2026-08-15T00:00:00Z", upstream_origin_id="pg_origin",
            verification_status=VerificationStatus.VERIFIED_PRIMARY, is_primary_source=True,
            confidence=0.95, target_hypothesis="H1", query_id="q1"
        )

        # Pass explicitly empty query_ledger=[]
        evidence_set = EvidencePolicy.validate_claims(
            contract, ontology, [claim], self.hypotheses, query_ledger=[]
        )

        self.assertEqual(len(evidence_set.eligible_claims), 0)
        self.assertEqual(len(evidence_set.rejected_claims), 1)
        self.assertEqual(evidence_set.rejected_claims[0][1], "REJECTED_UNKNOWN_QUERY_ID")
        self.assertEqual(evidence_set.rejected_claims[0][0].rejection_reason_code, "REJECTED_UNKNOWN_QUERY_ID")

    def test_vc_diligence_orchestrator_force_live_fails_closed_without_credentials(self):
        """
        [P0/P1 Generality Invariant Test] force_live=True Fail-Closed:
        Verify that VCDueDiligenceOrchestrator.audit_startup(profile, force_live=True)
        enforces LIVE retrieval and fails closed (RuntimeError) when live credentials are dummy/missing.
        """
        orchestrator = VCDueDiligenceOrchestrator()
        # Force dummy API key
        orchestrator.v2_engine.deep_research.api_key = "dummy"

        profile = StartupProfile(
            name="Test Startup",
            category="AI & Cloud",
            website="https://test-startup.local",
            stated_mission="Autonomous Cloud Operations",
            target_market="Enterprise Cloud"
        )

        with self.assertRaises(RuntimeError) as ctx:
            asyncio.run(orchestrator.audit_startup(profile, force_live=True))

        self.assertIn("LIVE_RETRIEVAL execution failed-closed", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()






