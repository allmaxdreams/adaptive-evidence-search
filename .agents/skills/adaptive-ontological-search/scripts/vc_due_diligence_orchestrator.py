"""
VC & Startup Due Diligence Agentic Orchestrator (Version 2.1 Core).
Integrates AutoSchemaKG, LightRAG dual-level retrieval, Skeptic Disproving Subagent,
Claimify Atomic Claim Extraction, and Analysis of Competing Hypotheses (ACH) Matrix.

Zero Hardcoded Entity Scenarios:
All startup profiles (MilTech, Pharma, PropTech, Consumer, or unknown) route through
the unified dynamic ontology, evidence extraction, policy validation, and synthesis pipeline.
"""

import asyncio
import json
import uuid
import re
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Any, Optional

import sys
import os
sys.path.append(os.path.dirname(__file__))

from config import config, DEFAULT_PRO_MODEL, DEFAULT_FLASH_MODEL
from models import ExecutionMode
from orchestrator_v2 import OntologicalSearchOrchestratorV2


@dataclass
class StartupProfile:
    name: str
    category: str
    website: str
    founders: List[str] = field(default_factory=list)
    stated_mission: str = ""
    target_market: str = ""


@dataclass
class VCDueDiligenceReport:
    startup_name: str
    category: str
    framework_version: str  # "Institutional Due Diligence Brief"
    is_synthetic_demo: bool
    warning_notice: Optional[str]
    executive_summary: str
    investment_recommendation: str  # STRONG INVEST | PROCEED WITH CAUTION | DEEP AUDIT NEEDED | PASS
    conviction_score: float  # 0.0 to 1.0
    red_flags: List[Dict[str, str]]  # severity, title, evidence, source
    tech_moat_evaluation: Dict[str, Any]  # primary_source_ratio, h1_positive_support, unique_roots, coverage_score
    ach_hypotheses: Dict[str, Any]
    lightrag_dual_context: Dict[str, Any]
    claims_provenance: List[Dict[str, Any]]
    key_questions_for_founders: List[str]
    audit_metrics: Dict[str, Any]

    def dict(self) -> Dict[str, Any]:
        return asdict(self)


class VCDueDiligenceOrchestrator:
    """
    Agentic Orchestrator v2.1 for Startup & VC Due Diligence.
    Powered by Mode 3 Recursive Evidence Search, LightRAG Dual Retrieval,
    AutoSchemaKG, Skeptic Disproving Subagent, and ACH Matrix.
    100% Dynamic: Purely routes all profiles through OntologicalSearchOrchestratorV2.
    """

    def __init__(self, default_pro_model: str = DEFAULT_PRO_MODEL, default_flash_model: str = DEFAULT_FLASH_MODEL):
        self.pro_model = default_pro_model
        self.flash_model = default_flash_model
        self.version = "Ontological Search 2.1 Core (Dynamic VC Diligence)"
        self.v2_engine = OntologicalSearchOrchestratorV2(
            default_pro_model=self.pro_model,
            default_flash_model=self.flash_model
        )

    async def audit_startup(self, profile: StartupProfile, force_live: bool = False) -> VCDueDiligenceReport:
        """
        Executes full Mode 3 Dynamic Due Diligence Pipeline for any startup profile.
        Routes dynamically through OntologicalSearchOrchestratorV2.
        """
        print(f"\n[VCDiligenceEngine] >>> INITIALIZING DYNAMIC DUE DILIGENCE FOR: {profile.name} ({profile.category})")

        question = (
            f"VC Institutional Audit: Validate proprietary IP moat, product-market fit, "
            f"and disproving red flags for {profile.name} in {profile.category}. "
            f"Stated mission: '{profile.stated_mission or profile.name}'. "
            f"Target market: '{profile.target_market or profile.category}'."
        )

        mode_override = ExecutionMode.LIVE if force_live else None
        v2_result = await self.v2_engine.run(question, execution_mode_override=mode_override)

        contract = v2_result.get("contract", {})
        ontology = v2_result.get("ontology", {})
        hypotheses = v2_result.get("hypotheses", {})
        claims = v2_result.get("atomic_claims", [])
        matrix = v2_result.get("ach_matrix", {})
        metrics = v2_result.get("metrics", {})
        synthesis = v2_result.get("synthesis", {})

        is_synthetic = (
            synthesis.get("status") == "SIMULATION_PROTOTYPE_ONLY"
            or contract.get("execution_mode") in [ExecutionMode.MOCK.value, "MOCK_SIMULATION"]
        )

        warning_notice = None
        if is_synthetic:
            warning_notice = (
                "[SYNTHETIC DEMO NOTICE] This report ran in MOCK simulation mode without live web grounding. "
                "Real investment decisions require live verified search grounding."
            )

        recommendation = synthesis.get("decision_recommendation", "EVALUATING")
        conviction_score = synthesis.get("overall_confidence", 0.50)

        # Parse red flags from evaluated risk lenses
        red_flags: List[Dict[str, str]] = []
        for r in matrix.get("evaluated_risk_lenses", []):
            red_flags.append({
                "severity": r.get("severity", "MEDIUM"),
                "title": f"Risk Lens: {r.get('lens_name', 'Risk')}",
                "evidence": r.get("key_evidence") or f"Assessment Status: {r.get('assessment_status', 'UNASSESSED')}",
                "source": r.get("assessment_status", "POLICY_EVALUATION")
            })

        # Tech moat evaluation from verified ACH positive support & primary ratio
        tech_moat = {
            "primary_source_ratio": metrics.get("primary_source_ratio", 0.0),
            "h1_positive_support": matrix.get("h1_positive_support", 0.0),
            "unique_roots": metrics.get("unique_upstream_origins_count", 0),
            "coverage_score": metrics.get("coverage_score", 0.0),
            "h1_diagnostic_origins_count": metrics.get("h1_diagnostic_origins_count", 0),
            "h1_primary_roots_count": metrics.get("h1_primary_roots_count", 0)
        }

        # Context themes from ontology classes
        lightrag_context = {
            "low_level_entities": [profile.name] + ontology.get("classes", [])[:4],
            "high_level_themes": [f"{profile.category} Technology", "IP Defensibility", "Market Risk"]
        }

        # Knowledge gaps & action plans for founders
        questions = synthesis.get("knowledge_gaps", []) + [
            f"Action plan: {item}" for item in synthesis.get("coverage_debt_action_plan", [])
        ]

        exec_summary = (
            f"{profile.name} ({profile.category}) Due Diligence: "
            f"{synthesis.get('decision_recommendation', 'Audit complete.')} "
            f"Evaluated {len(claims)} atomic claims across {metrics.get('unique_upstream_origins_count', 0)} independent roots."
        )

        return VCDueDiligenceReport(
            startup_name=profile.name,
            category=profile.category,
            framework_version=self.version,
            is_synthetic_demo=is_synthetic,
            warning_notice=warning_notice,
            executive_summary=exec_summary,
            investment_recommendation=recommendation,
            conviction_score=conviction_score,
            red_flags=red_flags,
            tech_moat_evaluation=tech_moat,
            ach_hypotheses=hypotheses,
            lightrag_dual_context=lightrag_context,
            claims_provenance=claims,
            key_questions_for_founders=questions,
            audit_metrics=metrics
        )

    async def analyze_startup(self, profile: StartupProfile, force_live: bool = False) -> VCDueDiligenceReport:
        """Alias for audit_startup."""
        return await self.audit_startup(profile, force_live)
