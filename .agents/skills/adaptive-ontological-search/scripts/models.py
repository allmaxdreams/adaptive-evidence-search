"""
Data models and schemas for Adaptive Ontology-Driven Evidence Search (v2.1 Core).
Defines structured types for Search Modes, Execution Modes, Ontologies,
Hypotheses, Risk Lenses, Grounded Atomic Claims, Richards Heuer ACH Matrix,
and Knowledge Synthesis.
"""

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import List, Optional, Dict, Any, Tuple, Mapping, Sequence, Set, Union
import uuid

from config import DEFAULT_PRO_MODEL, DEFAULT_FLASH_MODEL, DEFAULT_FLASH_LITE_MODEL


class SearchMode(str, Enum):
    DIRECT_LOOKUP = "Mode 1: Direct Lookup"
    STRUCTURED_SEARCH = "Mode 2: Structured Search"
    RECURSIVE_EVIDENCE_SEARCH = "Mode 3: Recursive Evidence Search"


class ExecutionMode(str, Enum):
    LIVE = "LIVE_RETRIEVAL"
    MOCK = "MOCK_SIMULATION"


class VerificationStatus(str, Enum):
    VERIFIED_PRIMARY = "VERIFIED_PRIMARY"
    VERIFIED_SECONDARY = "VERIFIED_SECONDARY"
    UNVERIFIED_MOCK = "UNVERIFIED_MOCK"
    UNVERIFIED_CLAIM = "UNVERIFIED_CLAIM"
    REFUTED = "REFUTED"


class ModelTier(str, Enum):
    PRO = DEFAULT_PRO_MODEL
    FLASH = DEFAULT_FLASH_MODEL
    FLASH_LITE = DEFAULT_FLASH_LITE_MODEL


class PrecisionLevel(str, Enum):
    EXPLORATORY = "Exploratory"
    STANDARD = "Standard"
    HIGH = "High"
    HIGH_PRECISION_STRATEGIC = "High-Precision Strategic Evidence"
    AUDIT_GRADE = "Audit-Grade"
    STRICT = "Strict"
    STRATEGIC = "Strategic"
    UNKNOWN_FAIL_CLOSED = "UNKNOWN_FAIL_CLOSED"

    @classmethod
    def from_string(cls, val: Any) -> "PrecisionLevel":
        if isinstance(val, PrecisionLevel):
            return val
        if not val or not isinstance(val, str):
            return cls.UNKNOWN_FAIL_CLOSED
        normalized = val.strip().lower()
        if normalized in ["exploratory", "low", "minimal", "quick"]:
            return cls.EXPLORATORY
        elif normalized in ["standard", "medium", "normal", "default"]:
            return cls.STANDARD
        elif normalized in [
            "high", "high-precision", "high precision", "high-precision strategic evidence",
            "high_precision_strategic_evidence", "high precision strategic evidence",
            "high-precision strategic", "high_precision"
        ]:
            return cls.HIGH
        elif normalized in ["strict", "audit", "audit-grade", "audit_grade", "strategic", "maximum"]:
            return cls.AUDIT_GRADE
        else:
            return cls.UNKNOWN_FAIL_CLOSED


@dataclass
class EvidenceRequirements:
    min_independent_roots_h1: int = 3
    min_independent_roots_h2: int = 1
    min_independent_roots_h0: int = 1
    min_primary_roots_h1: int = 0
    min_primary_roots_h2: int = 0
    min_primary_roots_h0: int = 0
    min_primary_ratio: float = 0.0
    require_all_risks_assessed: bool = True
    require_counterevidence_search: bool = True
    allow_unverified_mock: bool = False
    is_fail_closed: bool = False

    @classmethod
    def for_precision(cls, precision: PrecisionLevel, execution_mode: ExecutionMode = ExecutionMode.LIVE) -> "EvidenceRequirements":
        is_mock = (execution_mode == ExecutionMode.MOCK)
        if precision == PrecisionLevel.EXPLORATORY:
            return cls(
                min_independent_roots_h1=1,
                min_independent_roots_h2=1,
                min_independent_roots_h0=0,
                min_primary_roots_h1=0,
                min_primary_roots_h2=0,
                min_primary_roots_h0=0,
                min_primary_ratio=0.0,
                require_all_risks_assessed=False,
                require_counterevidence_search=False,
                allow_unverified_mock=is_mock
            )
        elif precision == PrecisionLevel.STANDARD:
            return cls(
                min_independent_roots_h1=2,
                min_independent_roots_h2=1,
                min_independent_roots_h0=1,
                min_primary_roots_h1=0,
                min_primary_roots_h2=0,
                min_primary_roots_h0=0,
                min_primary_ratio=0.0,
                require_all_risks_assessed=True,
                require_counterevidence_search=True,
                allow_unverified_mock=is_mock
            )
        elif precision in [PrecisionLevel.HIGH, PrecisionLevel.HIGH_PRECISION_STRATEGIC]:
            return cls(
                min_independent_roots_h1=3,
                min_independent_roots_h2=1,
                min_independent_roots_h0=1,
                min_primary_roots_h1=1,   # H1 strictly requires >= 1 verified primary root!
                min_primary_roots_h2=0,
                min_primary_roots_h0=0,
                min_primary_ratio=0.01,
                require_all_risks_assessed=True,
                require_counterevidence_search=True,
                allow_unverified_mock=is_mock
            )
        elif precision in [PrecisionLevel.AUDIT_GRADE, PrecisionLevel.STRICT, PrecisionLevel.STRATEGIC]:
            return cls(
                min_independent_roots_h1=3,
                min_independent_roots_h2=1,
                min_independent_roots_h0=1,
                min_primary_roots_h1=1,
                min_primary_roots_h2=1,
                min_primary_roots_h0=0,
                min_primary_ratio=0.10,
                require_all_risks_assessed=True,
                require_counterevidence_search=True,
                allow_unverified_mock=is_mock
            )
        elif precision in [PrecisionLevel.AUDIT_GRADE, PrecisionLevel.STRICT, PrecisionLevel.STRATEGIC]:
            return cls(
                min_independent_roots_h1=3,
                min_independent_roots_h2=1,
                min_independent_roots_h0=1,
                min_primary_roots_h1=1,
                min_primary_roots_h2=1,
                min_primary_roots_h0=0,
                min_primary_ratio=0.10,
                require_all_risks_assessed=True,
                require_counterevidence_search=True,
                allow_unverified_mock=is_mock
            )
        elif precision in [PrecisionLevel.AUDIT_GRADE, PrecisionLevel.STRICT, PrecisionLevel.STRATEGIC]:
            return cls(
                min_independent_roots_h1=3,
                min_independent_roots_h2=1,
                min_independent_roots_h0=1,
                min_primary_roots_h1=1,
                min_primary_roots_h2=1,
                min_primary_roots_h0=0,
                min_primary_ratio=0.10,
                require_all_risks_assessed=True,
                require_counterevidence_search=True,
                allow_unverified_mock=is_mock
            )
        else: # UNKNOWN_FAIL_CLOSED
            return cls(
                min_independent_roots_h1=999,
                min_independent_roots_h2=999,
                min_independent_roots_h0=999,
                min_primary_roots_h1=999,
                min_primary_roots_h2=999,
                min_primary_roots_h0=999,
                min_primary_ratio=1.0,
                require_all_risks_assessed=True,
                require_counterevidence_search=True,
                allow_unverified_mock=False,
                is_fail_closed=True
            )


@dataclass
class ResearchContract:
    question: str
    decision_context: str
    target_object: str
    required_precision: str
    output_format: str
    search_mode: SearchMode
    execution_mode: ExecutionMode = ExecutionMode.MOCK
    time_frame: Optional[str] = None
    geography: Optional[str] = None
    allowed_sources: List[str] = field(default_factory=list)
    stopping_criteria: List[str] = field(default_factory=list)
    precision_level: Optional[PrecisionLevel] = None
    evidence_requirements: Optional[EvidenceRequirements] = None

    def __post_init__(self):
        if self.precision_level is None:
            self.precision_level = PrecisionLevel.from_string(self.required_precision)
        if self.evidence_requirements is None:
            self.evidence_requirements = EvidenceRequirements.for_precision(
                self.precision_level, self.execution_mode
            )

    def dict(self) -> Dict[str, Any]:
        res = asdict(self)
        res["search_mode"] = self.search_mode.value if isinstance(self.search_mode, SearchMode) else str(self.search_mode)
        res["execution_mode"] = self.execution_mode.value if isinstance(self.execution_mode, ExecutionMode) else str(self.execution_mode)
        res["precision_level"] = self.precision_level.value if isinstance(self.precision_level, PrecisionLevel) else str(self.precision_level)
        return res


from types import MappingProxyType
import dataclasses


@dataclass(frozen=True)
class GateDecision:
    is_stopping_allowed: bool
    synthesis_status: str           # "CONCLUSIVE_RECOMMENDATION" | "CONDITIONAL_RECOMMENDATION" | "INSUFFICIENT_EVIDENCE_SAFETY_BLOCK" | "SIMULATION_PROTOTYPE_ONLY"
    reason: str
    is_fail_closed: bool
    unresolved_material_risks: Tuple[str, ...] = field(default_factory=tuple)
    action_required: str = ""
    can_synthesize_conditional: bool = False

    # Canonical Audit Facts directly computed during policy evaluation
    counterevidence_searched: bool = False
    all_risk_searches_completed: bool = True
    all_material_risks_assessed: bool = True
    searched_classes_count: int = 0
    executed_queries_count: int = 0
    reliability_score: float = 0.0
    novelty_score: float = 0.0
    calibration_score: float = 0.85

    def __post_init__(self):
        if not isinstance(self.unresolved_material_risks, tuple):
            object.__setattr__(self, "unresolved_material_risks", tuple(self.unresolved_material_risks or ()))

    def dict(self) -> Dict[str, Any]:
        return {
            "is_stopping_allowed": self.is_stopping_allowed,
            "synthesis_status": self.synthesis_status,
            "reason": self.reason,
            "is_fail_closed": self.is_fail_closed,
            "unresolved_material_risks": list(self.unresolved_material_risks),
            "action_required": self.action_required,
            "can_synthesize_conditional": self.can_synthesize_conditional,
            "counterevidence_searched": self.counterevidence_searched,
            "all_risk_searches_completed": self.all_risk_searches_completed,
            "all_material_risks_assessed": self.all_material_risks_assessed,
            "searched_classes_count": self.searched_classes_count,
            "executed_queries_count": self.executed_queries_count,
            "reliability_score": self.reliability_score,
            "novelty_score": self.novelty_score,
            "calibration_score": self.calibration_score
        }


# =====================================================================
# IMMUTABLE NORMALIZED SOURCE & VALIDATED CLAIM SCHEMAS
# =====================================================================

class EligibilityStatus(Enum):
    ELIGIBLE = "ELIGIBLE"
    REJECTED = "REJECTED"


class RejectionReasonCode(Enum):
    ALLOWED_SOURCE_MISMATCH = "REJECTED_DISALLOWED_SOURCE"
    UNVERIFIED_MOCK = "REJECTED_UNVERIFIED_MOCK"
    UNVERIFIED_CLAIM = "REJECTED_UNVERIFIED_CLAIM"
    REFUTED = "REJECTED_REFUTED"
    UNRECOGNIZED_STATUS = "REJECTED_UNRECOGNIZED_STATUS"
    MALFORMED_URI = "REJECTED_MALFORMED_URI"
    UNKNOWN_QUERY_ID = "REJECTED_UNKNOWN_QUERY_ID"
    FAILED_QUERY_LINEAGE = "REJECTED_FAILED_QUERY_LINEAGE"
    QUERY_HYPOTHESIS_MISMATCH = "REJECTED_QUERY_HYPOTHESIS_MISMATCH"
    QUERY_RISK_LENS_MISMATCH = "REJECTED_QUERY_RISK_LENS_MISMATCH"
    QUERY_CONCEPT_MISMATCH = "REJECTED_QUERY_CONCEPT_MISMATCH"
    NONE = "NONE"


@dataclass(frozen=True)
class NormalizedSource:
    raw_url: str
    raw_domain: str
    canonical_url: str
    hostname: str
    normalized_path: str
    is_primary_authority: bool
    authority_type: Optional[str] = None
    authority_reason: str = ""

    def dict(self) -> Dict[str, Any]:
        return {
            "raw_url": self.raw_url,
            "raw_domain": self.raw_domain,
            "canonical_url": self.canonical_url,
            "hostname": self.hostname,
            "normalized_path": self.normalized_path,
            "is_primary_authority": self.is_primary_authority,
            "authority_type": self.authority_type,
            "authority_reason": self.authority_reason
        }


@dataclass(frozen=True)
class ValidatedClaim:
    id: str
    subject: str
    predicate: str
    object: str
    normalized_source: NormalizedSource
    effective_verification_status: VerificationStatus
    is_primary_source: bool
    authority_decision: bool
    authority_type: Optional[str]
    authority_reason: str
    eligibility_status: EligibilityStatus
    rejection_reason_code: Optional[str]
    confidence: float
    target_hypothesis: str
    source_title: str = "Document"
    locator: str = ""
    retrieval_timestamp: str = ""
    subject_entity_id: Optional[str] = None
    target_concept: Optional[str] = None
    covered_ontology_classes: Tuple[str, ...] = field(default_factory=tuple)
    grounded_summary: Optional[str] = None
    verbatim_quote: Optional[str] = None
    is_llm_grounded_summary: bool = False
    target_risk_lens_id: Optional[str] = None
    inconsistency_ratings: Mapping[str, float] = field(default_factory=dict)
    query_id: Optional[str] = None
    risk_stance: Optional[str] = None
    risk_impact: Optional[str] = None
    risk_likelihood: Optional[str] = None
    provenance_root_id: Optional[str] = None
    upstream_origin_id_val: Optional[str] = None

    def __post_init__(self):
        if not isinstance(self.inconsistency_ratings, MappingProxyType):
            object.__setattr__(
                self,
                "inconsistency_ratings",
                MappingProxyType(dict(self.inconsistency_ratings or {}))
            )
        if not isinstance(self.covered_ontology_classes, tuple):
            object.__setattr__(
                self,
                "covered_ontology_classes",
                tuple(self.covered_ontology_classes or ())
            )

    # Helper properties for backwards compatibility with AtomicClaim interface
    @property
    def source_url(self) -> str:
        return self.normalized_source.raw_url

    @property
    def source_domain(self) -> str:
        return self.normalized_source.hostname or self.normalized_source.raw_domain

    @property
    def verification_status(self) -> VerificationStatus:
        return self.effective_verification_status

    @property
    def upstream_origin_id(self) -> str:
        return self.provenance_root_id or self.upstream_origin_id_val or self.normalized_source.hostname

    def dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "subject": self.subject,
            "predicate": self.predicate,
            "object": self.object,
            "normalized_source": self.normalized_source.dict(),
            "effective_verification_status": (
                self.effective_verification_status.value
                if isinstance(self.effective_verification_status, VerificationStatus)
                else str(self.effective_verification_status)
            ),
            "is_primary_source": self.is_primary_source,
            "authority_decision": self.authority_decision,
            "authority_type": self.authority_type,
            "authority_reason": self.authority_reason,
            "eligibility_status": (
                self.eligibility_status.value
                if isinstance(self.eligibility_status, EligibilityStatus)
                else str(self.eligibility_status)
            ),
            "rejection_reason_code": self.rejection_reason_code,
            "confidence": self.confidence,
            "target_hypothesis": self.target_hypothesis,
            "source_title": self.source_title,
            "locator": self.locator,
            "retrieval_timestamp": self.retrieval_timestamp,
            "subject_entity_id": self.subject_entity_id,
            "target_concept": self.target_concept,
            "covered_ontology_classes": list(self.covered_ontology_classes),
            "grounded_summary": self.grounded_summary,
            "verbatim_quote": self.verbatim_quote,
            "is_llm_grounded_summary": self.is_llm_grounded_summary,
            "target_risk_lens_id": self.target_risk_lens_id,
            "inconsistency_ratings": dict(self.inconsistency_ratings),
            "query_id": self.query_id,
            "risk_stance": self.risk_stance,
            "risk_impact": self.risk_impact,
            "risk_likelihood": self.risk_likelihood,
            "provenance_root_id": self.provenance_root_id,
            "upstream_origin_id_val": self.upstream_origin_id_val,
            # Backwards compatibility keys
            "source_url": self.source_url,
            "source_domain": self.source_domain,
            "verification_status": (
                self.effective_verification_status.value
                if isinstance(self.effective_verification_status, VerificationStatus)
                else str(self.effective_verification_status)
            ),
            "upstream_origin_id": self.upstream_origin_id
        }


@dataclass(frozen=True)
class ValidatedEvidenceSet:
    eligible_claims: Tuple[ValidatedClaim, ...]
    rejected_claims: Tuple[Tuple[ValidatedClaim, str], ...]
    provenance_clusters: Tuple[Tuple[ValidatedClaim, ...], ...]
    h1_diagnostic_origins_count: int
    h2_diagnostic_origins_count: int
    h0_diagnostic_origins_count: int
    h1_primary_roots_count: int
    h2_primary_roots_count: int
    h0_primary_roots_count: int
    primary_claims_count: int
    secondary_claims_count: int
    primary_source_ratio: float
    evidenced_classes: Tuple[str, ...]
    unresolved_coverage_debt: Tuple[str, ...]
    gate_decision: GateDecision
    contract_stopping_criteria_met: bool

    def __post_init__(self):
        if not isinstance(self.eligible_claims, tuple):
            object.__setattr__(self, "eligible_claims", tuple(self.eligible_claims or ()))
        if not isinstance(self.rejected_claims, tuple):
            object.__setattr__(self, "rejected_claims", tuple(self.rejected_claims or ()))
        if not isinstance(self.provenance_clusters, tuple):
            object.__setattr__(
                self,
                "provenance_clusters",
                tuple(tuple(cl) if not isinstance(cl, tuple) else cl for cl in (self.provenance_clusters or ()))
            )
        if not isinstance(self.evidenced_classes, tuple):
            object.__setattr__(self, "evidenced_classes", tuple(self.evidenced_classes or ()))
        if not isinstance(self.unresolved_coverage_debt, tuple):
            object.__setattr__(self, "unresolved_coverage_debt", tuple(self.unresolved_coverage_debt or ()))

    def replace_decision(self, gate_decision: GateDecision) -> "ValidatedEvidenceSet":
        """Pure functional update returning a new frozen ValidatedEvidenceSet instance."""
        return dataclasses.replace(
            self,
            gate_decision=gate_decision,
            contract_stopping_criteria_met=gate_decision.is_stopping_allowed
        )

    @property
    def is_fail_closed(self) -> bool:
        return self.gate_decision.is_fail_closed if self.gate_decision else False

    @property
    def fail_closed_reason(self) -> Optional[str]:
        return self.gate_decision.reason if (self.gate_decision and self.gate_decision.is_fail_closed) else None

    @property
    def unique_origins_count(self) -> int:
        return len(self.provenance_clusters)

    @property
    def coverage_score(self) -> float:
        total = len(self.evidenced_classes) + len(self.unresolved_coverage_debt)
        return round(len(self.evidenced_classes) / (total or 1), 2)

    @property
    def recommended_action(self) -> str:
        return self.gate_decision.action_required if self.gate_decision else "Continue search"

    def dict(self) -> Dict[str, Any]:
        return {
            "eligible_claims": [c.dict() for c in self.eligible_claims],
            "rejected_claims": [[c.dict(), reason] for c, reason in self.rejected_claims],
            "provenance_clusters": [[c.dict() for c in cl] for cl in self.provenance_clusters],
            "h1_diagnostic_origins_count": self.h1_diagnostic_origins_count,
            "h2_diagnostic_origins_count": self.h2_diagnostic_origins_count,
            "h0_diagnostic_origins_count": self.h0_diagnostic_origins_count,
            "h1_primary_roots_count": self.h1_primary_roots_count,
            "h2_primary_roots_count": self.h2_primary_roots_count,
            "h0_primary_roots_count": self.h0_primary_roots_count,
            "primary_claims_count": self.primary_claims_count,
            "secondary_claims_count": self.secondary_claims_count,
            "primary_source_ratio": self.primary_source_ratio,
            "evidenced_classes": list(self.evidenced_classes),
            "unresolved_coverage_debt": list(self.unresolved_coverage_debt),
            "gate_decision": self.gate_decision.dict() if self.gate_decision else None,
            "contract_stopping_criteria_met": self.contract_stopping_criteria_met
        }


@dataclass
class EntityDefinition:
    id: str
    name: str
    aliases: List[str] = field(default_factory=list)
    description: Optional[str] = None

    def dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ComparisonIntent:
    e1: EntityDefinition
    e2: Optional[EntityDefinition] = None
    domain_context: str = "Strategic Architecture"
    is_comparison: bool = True

    def __iter__(self):
        # Enables backwards-compatible 3-tuple unpacking: e1, e2, domain_context = intent
        fallback_e2 = self.e2 if self.e2 else EntityDefinition(id="alternative", name="Alternative Architecture", aliases=["Alternative Architecture", "Alternative"])
        return iter((self.e1, fallback_e2, self.domain_context))

    def dict(self) -> Dict[str, Any]:
        return {
            "e1": self.e1.dict() if hasattr(self.e1, "dict") else asdict(self.e1),
            "e2": self.e2.dict() if (self.e2 and hasattr(self.e2, "dict")) else (asdict(self.e2) if self.e2 else None),
            "domain_context": self.domain_context,
            "is_comparison": self.is_comparison
        }


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
    relation_type: str
    target_entity: str

    def dict(self) -> Dict[str, Any]:
        return asdict(self)


# =====================================================================
# BACKWARD COMPATIBILITY LEGACY TYPES (For V1 Orchestrator & Legacy Callers)
# =====================================================================

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


# =====================================================================
# DYNAMIC ONTOLOGY & HYPOTHESIS SCHEMAS (V2.1 Core)
# =====================================================================

@dataclass
class DynamicOntology:
    version: int = 2
    domain_name: str = "Auto-Induced Domain"
    classes: List[str] = field(default_factory=list)
    dynamic_relations: List[Relation] = field(default_factory=list)
    extracted_vocabulary: List[str] = field(default_factory=list)
    coverage_debt: List[str] = field(default_factory=list)  # Classes still needing evidence
    shacl_validated: bool = True
    validation_report: Optional[Dict[str, Any]] = None

    def dict(self) -> Dict[str, Any]:
        res = asdict(self)
        res["dynamic_relations"] = [r.dict() if isinstance(r, Relation) else r for r in self.dynamic_relations]
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
    confidence: float = 0.5
    status: str = "UNTESTED"

    def dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class RiskLens:
    id: str
    name: str
    description: str
    associated_evidence: List[str] = field(default_factory=list)
    risk_level: str = "LOW"  # LOW, MEDIUM, HIGH, CRITICAL

    def dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class HypothesisSet:
    primary_h1: SingleHypothesis
    alternative_h2: SingleHypothesis
    null_h0: SingleHypothesis
    risk_lenses: List[RiskLens] = field(default_factory=list)
    visibility_hv: Optional[Any] = None
    entity_registry: Dict[str, EntityDefinition] = field(default_factory=dict)

    def __post_init__(self):
        if self.visibility_hv and not self.risk_lenses:
            stmt = getattr(self.visibility_hv, "statement", str(self.visibility_hv))
            self.risk_lenses = [
                RiskLens(id="VISIBILITY_HV", name="Hidden Risk & Marketing Hype Filter", description=stmt)
            ]

    def dict(self) -> Dict[str, Any]:
        return {
            "primary_h1": self.primary_h1.dict() if hasattr(self.primary_h1, "dict") else asdict(self.primary_h1),
            "alternative_h2": self.alternative_h2.dict() if hasattr(self.alternative_h2, "dict") else asdict(self.alternative_h2),
            "null_h0": self.null_h0.dict() if hasattr(self.null_h0, "dict") else asdict(self.null_h0),
            "risk_lenses": [r.dict() if hasattr(r, "dict") else asdict(r) for r in self.risk_lenses],
            "visibility_hv": self.visibility_hv.dict() if hasattr(self.visibility_hv, "dict") else (asdict(self.visibility_hv) if self.visibility_hv else None),
            "entity_registry": {k: v.dict() if hasattr(v, "dict") else v for k, v in self.entity_registry.items()}
        }


@dataclass
class QueryItem:
    text: str
    strategy: str  # Direct, Ontological, Artifact, Lifecycle, Bottleneck, Disproving, Regulatory
    target_hypothesis: str  # H1, H2, H0, RISK_LENS
    target_concept: Optional[str] = None
    target_risk_lens_id: Optional[str] = None
    language: str = "en"
    query_id: str = field(default_factory=lambda: f"q_{uuid.uuid4().hex[:6]}")

    def dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class QueryPortfolio:
    queries: List[QueryItem] = field(default_factory=list)

    def dict(self) -> Dict[str, Any]:
        return {"queries": [q.dict() if isinstance(q, QueryItem) else q for q in self.queries]}


# =====================================================================
# ATOMIC CLAIM WITH STRICT GROUNDING & PROVENANCE (v2.1 Core)
# =====================================================================

@dataclass
class AtomicClaim:
    id: str
    subject: str
    predicate: str
    object: str
    source_url: str              # URL or local locator
    source_title: str            # Document/Article Title
    source_domain: str           # Domain name
    locator: str                 # Paragraph/section locator
    retrieval_timestamp: str     # ISO Timestamp
    upstream_origin_id: str      # Upstream publisher cluster ID
    verification_status: VerificationStatus
    is_primary_source: bool
    confidence: float
    target_hypothesis: str
    subject_entity_id: Optional[str] = None      # e.g. "postgresql", "cockroachdb", "rust", "go", "competitor"
    target_concept: Optional[str] = None         # Queried domain concept/class (e.g. "RelationalDatabaseEngine")
    covered_ontology_classes: List[str] = field(default_factory=list) # Classes resolved by this claim
    grounded_summary: Optional[str] = None       # LLM synthesized grounding segment
    verbatim_quote: Optional[str] = None         # Exact raw text quote (if fetched directly)
    is_llm_grounded_summary: bool = False
    target_risk_lens_id: Optional[str] = None
    inconsistency_ratings: Dict[str, float] = field(default_factory=dict)
    query_id: Optional[str] = None
    risk_stance: Optional[str] = None            # "SUPPORTS" | "REFUTES" | "NEUTRAL" | "UNKNOWN"
    risk_impact: Optional[str] = None            # "CRITICAL" | "HIGH" | "MEDIUM" | "LOW" | "UNKNOWN"
    risk_likelihood: Optional[str] = None        # "HIGH" | "MEDIUM" | "LOW" | "UNKNOWN"
    primary_authority_type: Optional[str] = None # e.g. "OFFICIAL_PROJECT_DOCUMENTATION", "STANDARDS_BODY_SPECIFICATION"
    primary_status_reason: Optional[str] = None  # Exact justification code from authority registry

    def dict(self) -> Dict[str, Any]:
        res = asdict(self)
        res["verification_status"] = self.verification_status.value if isinstance(self.verification_status, VerificationStatus) else str(self.verification_status)
        return res


@dataclass
class ACHMatrixRow:
    claim_id: str
    statement: str
    source_domain: str
    upstream_origin_id: str
    diagnosticity: float
    h1_score: float
    h2_score: float
    h0_score: float
    grounded_summary: Optional[str] = None
    verbatim_quote: Optional[str] = None
    source_url: str = ""
    source_title: str = "Document"
    locator: str = ""
    retrieval_timestamp: str = ""

    def dict(self) -> Dict[str, Any]:
        return {
            "claim_id": self.claim_id,
            "statement": self.statement,
            "source_domain": self.source_domain,
            "source_url": self.source_url,
            "source_title": self.source_title,
            "locator": self.locator,
            "retrieval_timestamp": self.retrieval_timestamp,
            "upstream_origin_id": self.upstream_origin_id,
            "diagnosticity": self.diagnosticity,
            "h1_score": self.h1_score,
            "h2_score": self.h2_score,
            "h0_score": self.h0_score,
            "grounded_summary": self.grounded_summary,
            "verbatim_quote": self.verbatim_quote
        }


@dataclass
class ACHMatrix:
    rows: List[ACHMatrixRow] = field(default_factory=list)
    h1_net_score: float = 0.0
    h2_net_score: float = 0.0
    h0_net_score: float = 0.0
    h1_inconsistency_penalty: float = 0.0
    h2_inconsistency_penalty: float = 0.0
    h0_inconsistency_penalty: float = 0.0
    h1_positive_support: float = 0.0
    h2_positive_support: float = 0.0
    h0_positive_support: float = 0.0
    winning_hypothesis: str = "INCONCLUSIVE_EVIDENCE"
    decision_rationale: str = ""
    is_inconclusive: bool = True
    evaluated_risk_lenses: List[Dict[str, Any]] = field(default_factory=list)

    def dict(self) -> Dict[str, Any]:
        return {
            "rows": [r.dict() for r in self.rows],
            "h1_net_score": self.h1_net_score,
            "h2_net_score": self.h2_net_score,
            "h0_net_score": self.h0_net_score,
            "h1_inconsistency_penalty": round(self.h1_inconsistency_penalty, 3),
            "h2_inconsistency_penalty": round(self.h2_inconsistency_penalty, 3),
            "h0_inconsistency_penalty": round(self.h0_inconsistency_penalty, 3),
            "h1_positive_support": round(self.h1_positive_support, 3),
            "h2_positive_support": round(self.h2_positive_support, 3),
            "h0_positive_support": round(self.h0_positive_support, 3),
            "winning_hypothesis": self.winning_hypothesis,
            "decision_rationale": self.decision_rationale,
            "is_inconclusive": self.is_inconclusive,
            "evaluated_risk_lenses": self.evaluated_risk_lenses
        }


@dataclass
class SearchQueryRecord:
    query_id: str
    query_text: str
    target_hypothesis: str           # "H1", "H2", "H0", "RISK_LENS", "ONTOLOGY_CLASS"
    target_concept: Optional[str] = None
    target_risk_lens_id: Optional[str] = None
    search_strategy: str = "Direct"
    depth: int = 1
    timestamp: str = ""
    status: str = "EXECUTED"         # "EXECUTED", "FAILED", "NO_RESULTS"
    retrieved_docs_count: int = 0
    extracted_claims_count: int = 0
    error_message: Optional[str] = None

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
    unique_upstream_origins_count: int = 0
    primary_source_ratio: float = 0.0
    current_search_depth: int = 1
    unresolved_coverage_debt_count: int = 0
    searched_classes_count: int = 0
    evidenced_classes_count: int = 0
    h1_diagnostic_origins_count: int = 0
    h2_diagnostic_origins_count: int = 0
    h0_diagnostic_origins_count: int = 0
    all_risk_lenses_assessed: bool = False
    all_risk_searches_completed: bool = False
    all_material_risks_sufficiently_assessed: bool = False
    unresolved_material_risks: List[str] = field(default_factory=list)
    executed_queries_count: int = 0

    def dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class SynthesisBrief:
    confirmed_facts: List[str] = field(default_factory=list)
    strong_inferences: List[str] = field(default_factory=list)
    working_hypotheses: List[str] = field(default_factory=list)
    contradictions: List[str] = field(default_factory=list)
    knowledge_gaps: List[str] = field(default_factory=list)
    update_triggers: List[str] = field(default_factory=list)
    overall_confidence: float = 0.5
    decision_recommendation: str = ""
    status: str = "CONCLUSIVE_RECOMMENDATION"
    risk_factors: List[str] = field(default_factory=list)
    alternative_explanations: List[str] = field(default_factory=list)
    coverage_debt_action_plan: List[str] = field(default_factory=list)
    rejected_evidence_audit: List[str] = field(default_factory=list)

    def __post_init__(self):
        if self.alternative_explanations and not self.risk_factors:
            self.risk_factors = list(self.alternative_explanations)

    def dict(self) -> Dict[str, Any]:
        return asdict(self)
