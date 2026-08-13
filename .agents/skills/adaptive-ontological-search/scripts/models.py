"""
Data models and schemas for Adaptive Ontology-Driven Evidence Search.
Defines all structured types for Search Modes, Ontologies, Hypotheses, Claims,
Evidence Evaluation, and Knowledge Synthesis using Python standard library dataclasses.
"""

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import List, Optional, Dict, Any


class SearchMode(str, Enum):
    DIRECT_LOOKUP = "Mode 1: Direct Lookup"
    STRUCTURED_SEARCH = "Mode 2: Structured Search"
    RECURSIVE_EVIDENCE_SEARCH = "Mode 3: Recursive Evidence Search"


class ModelTier(str, Enum):
    PRO = "gemini-3.6-pro"      # High-reasoning orchestrator, critic, synthesizer
    FLASH = "gemini-3.6-flash"  # Fast schema generators, query expansion, claim extractors
    FLASH_LITE = "gemini-3.6-flash-lite" # High-throughput scrapers / basic extractors


@dataclass
class ResearchContract:
    question: str
    decision_context: str
    target_object: str
    required_precision: str
    output_format: str
    search_mode: SearchMode
    time_frame: Optional[str] = None
    geography: Optional[str] = None
    allowed_sources: List[str] = field(default_factory=list)
    stopping_criteria: List[str] = field(default_factory=list)

    def dict(self) -> Dict[str, Any]:
        res = asdict(self)
        res["search_mode"] = self.search_mode.value
        return res


@dataclass
class Entity:
    id: str
    name: str
    type: str  # Actor, Technology, Product, Document, Resource, Policy
    description: Optional[str] = None

    def dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Relation:
    source_entity: str
    relation_type: str  # controls, develops, funds, collaborates_with, supports, changes
    target_entity: str

    def dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Ontology:
    version: int = 1
    actors: List[str] = field(default_factory=list)
    objects: List[str] = field(default_factory=list)
    actions: List[str] = field(default_factory=list)
    processes: List[str] = field(default_factory=list)
    relations: List[Relation] = field(default_factory=list)
    domain_vocabulary: List[str] = field(default_factory=list)

    def dict(self) -> Dict[str, Any]:
        res = asdict(self)
        res["relations"] = [r.dict() if isinstance(r, Relation) else r for r in self.relations]
        return res


@dataclass
class VisibilityModel:
    direct_traces: List[str] = field(default_factory=list)
    indirect_traces: List[str] = field(default_factory=list)
    counter_traces: List[str] = field(default_factory=list)
    anti_traces: List[str] = field(default_factory=list)
    hidden_dependencies: List[str] = field(default_factory=list)
    visibility_biases: List[str] = field(default_factory=list)

    def dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class SingleHypothesis:
    id: str
    statement: str
    expected_evidence: List[str] = field(default_factory=list)
    contradicting_evidence: List[str] = field(default_factory=list)
    hidden_variables: List[str] = field(default_factory=list)
    confidence: float = 0.5

    def dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class HypothesisSet:
    primary_h1: SingleHypothesis
    alternative_h2: SingleHypothesis
    null_h0: SingleHypothesis
    visibility_hv: Optional[SingleHypothesis] = None

    def dict(self) -> Dict[str, Any]:
        return {
            "primary_h1": self.primary_h1.dict(),
            "alternative_h2": self.alternative_h2.dict(),
            "null_h0": self.null_h0.dict(),
            "visibility_hv": self.visibility_hv.dict() if self.visibility_hv else None
        }


@dataclass
class QueryItem:
    text: str
    strategy: str  # Direct, Ontological, Artifact, Lifecycle, Bottleneck, Disproving, Multilingual
    target_hypothesis: str  # H1, H2, H0, HV
    language: str = "en"

    def dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class QueryPortfolio:
    queries: List[QueryItem] = field(default_factory=list)

    def dict(self) -> Dict[str, Any]:
        return {"queries": [q.dict() if isinstance(q, QueryItem) else q for q in self.queries]}


@dataclass
class Claim:
    id: str
    statement: str
    entity: str
    source_url: str
    source_type: str
    event_date: Optional[str] = None
    publication_date: Optional[str] = None
    primary_or_secondary: str = "secondary"
    independence_group: str = "default_group"
    evidence_status: str = "unverified"
    supports_hypothesis: Optional[str] = None
    contradicts_hypothesis: Optional[str] = None
    alternative_interpretation: Optional[str] = None
    confidence: float = 0.5

    def dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class EvidenceEvaluation:
    claim_id: str
    relevance: str
    reliability: str
    independence: str
    specificity: str
    recency: str
    novelty: str
    actionability: str
    visibility_bias_risk: str
    verdict: str

    def dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class SynthesisBrief:
    confirmed_facts: List[str]
    strong_inferences: List[str]
    working_hypotheses: List[str]
    contradictions: List[str]
    knowledge_gaps: List[str]
    alternative_explanations: List[str]
    update_triggers: List[str]
    overall_confidence: float
    decision_recommendation: str

    def dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class AuditMetrics:
    coverage_score: float
    novelty_score: float
    reliability_score: float
    counterevidence_searched: bool
    calibration_score: float
    stopping_rule_met: bool
    recommended_next_step: str

    def dict(self) -> Dict[str, Any]:
        return asdict(self)


# =====================================================================
# ONTOLOGICAL SEARCH 2.0 EXTENSIONS (AutoSchema, AtomicClaims, ACH Matrix)
# =====================================================================

@dataclass
class AtomicClaim:
    id: str
    subject: str
    predicate: str
    object: str
    source_url: str
    source_domain: str
    independence_group: str
    is_primary_source: bool
    confidence: float
    target_hypothesis: str

    def dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ACHMatrixRow:
    claim_id: str
    statement: str
    h1_score: int  # +1 supporting, -1 contradicting, 0 neutral
    h2_score: int
    h0_score: int
    hv_score: int

    def dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ACHMatrix:
    rows: List[ACHMatrixRow] = field(default_factory=list)
    h1_net_score: int = 0
    h2_net_score: int = 0
    h0_net_score: int = 0
    hv_net_score: int = 0
    winning_hypothesis: str = "H1"

    def dict(self) -> Dict[str, Any]:
        return {
            "rows": [r.dict() for r in self.rows],
            "h1_net_score": self.h1_net_score,
            "h2_net_score": self.h2_net_score,
            "h0_net_score": self.h0_net_score,
            "hv_net_score": self.hv_net_score,
            "winning_hypothesis": self.winning_hypothesis
        }


@dataclass
class DynamicOntology:
    version: int = 2
    domain_name: str = "Auto-Induced Domain"
    classes: List[str] = field(default_factory=list)
    dynamic_relations: List[Relation] = field(default_factory=list)
    extracted_vocabulary: List[str] = field(default_factory=list)
    shacl_validated: bool = True

    def dict(self) -> Dict[str, Any]:
        res = asdict(self)
        res["dynamic_relations"] = [r.dict() if isinstance(r, Relation) else r for r in self.dynamic_relations]
        return res

