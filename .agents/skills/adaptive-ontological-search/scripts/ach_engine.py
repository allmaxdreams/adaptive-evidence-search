"""
Analysis of Competing Hypotheses (ACH) Engine — Richards Heuer Standard (v2.1 Core — Architectural Refactor).
Implements:
1. Hard Upstream Root Provenance Deduplication (1 upstream wire cluster = max weight 1.0)
2. Minimum Positive Corroboration Threshold (prevents 0-evidence hypotheses from winning)
3. Diagnosticity weighting across competing technical hypotheses (H1, H2, H0)
4. Orthogonal Risk Lens Evaluation (L_risk evaluated alongside hypotheses over validated claims only)
5. Strict Inconclusive Safety Protocol
6. Operates strictly over ValidatedEvidenceSet / eligible ValidatedClaim instances. Raw/rejected claims never enter matrix rows.
"""

import math
import re
from typing import List, Dict, Tuple, Any, Optional, Sequence, Union, Mapping
from models import (
    HypothesisSet, SingleHypothesis, RiskLens, AtomicClaim, ACHMatrix, ACHMatrixRow,
    VerificationStatus, ValidatedClaim, EligibilityStatus, ValidatedEvidenceSet
)
from config import config
import hashlib

from evidence_policy import cluster_claims_by_provenance


class ACHHeuerEngine:
    """
    Richards Heuer ACH Consistency & Inconsistency Engine v2.1.
    Evaluates evidence against hypotheses through weighted contradiction elimination,
    strict root provenance clustering, and minimum positive corroboration gates.
    Operates strictly on validated evidence.
    """

    def __init__(
        self,
        inconclusive_threshold: float = 0.40,
        min_corroboration_support: float = 0.30
    ):
        self.inconclusive_threshold = inconclusive_threshold
        self.min_corroboration_support = min_corroboration_support

    def calculate_diagnosticity(self, ratings: Mapping[str, float]) -> float:
        """
        Diagnosticity measures how well a piece of evidence discriminates among competing hypotheses (H1, H2, H0).
        Evidence consistent with all hypotheses has near-zero diagnosticity.
        """
        competing_keys = [k for k in ["H1", "H2", "H0"] if k in ratings]
        if not competing_keys:
            return 0.15
        
        values = [ratings[k] for k in competing_keys]
        mean_val = sum(values) / len(values)
        variance = sum((v - mean_val) ** 2 for v in values) / len(values)
        std_dev = math.sqrt(variance)
        return min(1.0, max(0.15, std_dev * 1.25))

    @staticmethod
    def classify_claim_risk_stance(claim: Any) -> str:
        """
        Classifies individual claim stance regarding a risk lens:
        Returns: 'REFUTES' | 'SUPPORTS' | 'NEUTRAL' | 'UNKNOWN'
        Prioritizes structured claim.risk_stance if already populated during claim extraction.
        """
        if getattr(claim, "risk_stance", None) in ["SUPPORTS", "REFUTES", "NEUTRAL", "UNKNOWN"]:
            return claim.risk_stance

        raw_blob = f"{claim.predicate} {claim.object} {claim.grounded_summary or ''} {claim.verbatim_quote or ''}".lower()
        text_blob = re.sub(r'[_]+', ' ', raw_blob)

        # 1. NEGATED POSITIVE / NON-COMPLIANCE PATTERNS -> SUPPORTS RISK!
        negated_positive_pattern = (
            r'\b(?:not|never|no\s+longer|cannot\s+be|fails\s+to\s+be|was\s+not|were\s+not|is\s+not|are\s+not|has\s+not\s+been|have\s+not\s+been)\s+'
            r'(?:fully\s+|yet\s+|currently\s+|materially\s+|directly\s+)?'
            r'(?:certified|compliant|approved|cleared|resilient|mitigated|cost-effective|verified|authorized|licensed|passed)\b'
        )
        non_compliance_prefix_pattern = (
            r'\b(?:non-?compliant|un-?certified|un-?approved|un-?authorized|non-?resilient|un-?mitigated|un-?licensed|not\s+approved\s+by|not\s+by\s+the\s+regulator)\b'
        )
        if re.search(negated_positive_pattern, text_blob, re.IGNORECASE) or re.search(non_compliance_prefix_pattern, text_blob, re.IGNORECASE):
            return "SUPPORTS"

        # 2. NO-EVIDENCE / LACK OF RISK CONSTRUCTIONS -> REFUTES
        no_evidence_pattern = (
            r'\b(?:there\s+is\s+|there\s+was\s+)?(?:no|without|zero|scant|little|lack\s+of)\s+'
            r'(?:direct\s+|conclusive\s+|empirical\s+|verifiable\s+|substantive\s+|credible\s+)?'
            r'(?:evidence|proof|indication|sign|record|trace|finding|report)\s+'
            r'(?:of|that|to\s+(?:suggest|show|indicate|prove|demonstrate|substantiate|reveal))\s+'
            r'(?:any\s+|material\s+|observable\s+|known\s+)?'
            r'(?:violations?|bottlenecks?|outages?|penalt(?:y|ies)|issues?|risks?|failures?|breach(?:es)?|sanctions?|downtime|flaws?)\b'
        )
        no_evidence_trailing_pattern = (
            r'\b(?:no|zero)\s+evidence\s+of\s+(?:any\s+|material\s+)?(?:violations?|bottlenecks?|outages?|penalt(?:y|ies)|issues?|risks?|failures?|breach(?:es)?|sanctions?|downtime|flaws?)\s+(?:was|were|has\s+been)\s+(?:found|detected|observed|reported|uncovered)\b'
        )
        if re.search(no_evidence_pattern, text_blob, re.IGNORECASE) or re.search(no_evidence_trailing_pattern, text_blob, re.IGNORECASE):
            return "REFUTES"

        # 3. VERB NEGATIONS -> REFUTES
        verb_negation_pattern = (
            r'\b(?:did\s+not|does\s+not|do\s+not|could\s+not|was\s+not|were\s+not|has\s+not|have\s+not|had\s+not|cannot|never|failed\s+to)\s+'
            r'(?:detect|find|identify|observe|encounter|reveal|show|experience|cause|produce|yield|suffer|exhibit|report|uncover)\s+'
            r'(?:any\s+|material\s+|evidence\s+of\s+)?'
            r'(?:violations?|bottlenecks?|outages?|penalt(?:y|ies)|issues?|risks?|failures?|breach(?:es)?|sanctions?|downtime|flaws?)\b'
        )
        noun_negated_was_not_pattern = (
            r'\b(?:bottlenecks?|outages?|violations?|penalt(?:y|ies)|issues?|risks?|failures?|breach(?:es)?)\s+(?:was|were|has\s+been)\s+not\s+(?:observed|detected|seen|found|encountered|reported|served)\b'
        )
        if re.search(verb_negation_pattern, text_blob, re.IGNORECASE) or re.search(noun_negated_was_not_pattern, text_blob, re.IGNORECASE):
            return "REFUTES"

        # 4. UNLIKELY PROBABILITY NEGATION -> REFUTES
        unlikely_risk_pattern = (
            r'\b(?:is|are|was|were)\s+(?:highly\s+|very\s+|extremely\s+)?(?:unlikely|improbable)\s+to\s+(?:experience|cause|suffer|produce|encounter|face)\s+'
            r'(?:an?\s+|any\s+|material\s+)?(?:violations?|bottlenecks?|outages?|penalt(?:y|ies)|issues?|risks?|failures?|breach(?:es)?|downtime)\b'
        )
        if re.search(unlikely_risk_pattern, text_blob, re.IGNORECASE):
            return "REFUTES"

        # 5. NO + NOUN PATTERNS -> REFUTES
        no_noun_pattern = (
            r'\b(?:no|zero|without)\s+(?:regulatory\s+|compliance\s+|security\s+|performance\s+|capacity\s+|material\s+|observable\s+)?'
            r'(?:violations?|bottlenecks?|outages?|penalt(?:y|ies)|issues?|risks?|failures?|breach(?:es)?|sanctions?|downtime|flaws?)\b'
        )
        if re.search(no_noun_pattern, text_blob, re.IGNORECASE):
            return "REFUTES"

        # 6. DIRECT SUPPORT FOR RISK (includes audits, violations, bottlenecks, notice)
        supports_risk_pattern = (
            r'\b(?:critical|severe|major|frequent|recurring|unresolved|high|serious|pending\s+audit|audit|investigation|violation|penalty|bottleneck|outage|failure|breach|vulnerability|flaw|sanction|defect|degradation|customer\s+harm|notice)\b'
        )
        if re.search(supports_risk_pattern, text_blob, re.IGNORECASE):
            return "SUPPORTS"

        # 7. EXPLICIT REFUTATION OF RISK
        refutes_risk_pattern = (
            r'\b(?:clean|passed|compliant|certified|zero\s+violations?|zero\s+bottlenecks?|optimal|no\s+defects?|fully\s+mitigated|remediated|resilient)\b'
        )
        if re.search(refutes_risk_pattern, text_blob, re.IGNORECASE):
            return "REFUTES"

        # 8. NEUTRAL / INCONCLUSIVE
        neutral_pattern = (
            r'\b(?:overview|no\s+conclusion|further\s+study|under\s+review|inconclusive|unclear|general\s+regulatory|informative)\b'
        )
        if re.search(neutral_pattern, text_blob, re.IGNORECASE):
            return "NEUTRAL"

        return "UNKNOWN"

    @staticmethod
    def classify_claim_risk_materiality(claim: Any) -> str:
        """
        Extracts highest materiality level from a claim.
        Structured risk_impact is the primary source of truth.
        """
        struct_impact = getattr(claim, "risk_impact", None)
        if struct_impact in ["CRITICAL", "HIGH", "MEDIUM", "LOW"]:
            return struct_impact

        blob = f"{getattr(claim, 'predicate', '')} {getattr(claim, 'object', '')} {getattr(claim, 'grounded_summary', '') or ''} {getattr(claim, 'verbatim_quote', '') or ''}".lower()
        if re.search(r'\b(critical|catastrophic|systemic|data\s+loss)\b', blob):
            return "CRITICAL"
        if re.search(r'\b(severe|major|serious|frequent|recurring|unresolved|sanction|customer\s+harm|bottleneck)\b', blob):
            return "HIGH"
        if re.search(r'\b(moderate|intermittent|degradation|partial)\b', blob):
            return "MEDIUM"
        if re.search(r'\b(minor|isolated|negligible|remediated|low)\b', blob):
            return "LOW"
        return "UNKNOWN"

    def evaluate_matrix(
        self,
        hypotheses: HypothesisSet,
        validated_evidence: Union[ValidatedEvidenceSet, Sequence[ValidatedClaim]],
        validated_evidence_set: Optional[ValidatedEvidenceSet] = None
    ) -> ACHMatrix:
        """
        Executes Heuer ACH Matrix evaluation and orthogonal risk lens scoring strictly
        over eligible ValidatedClaim instances from ValidatedEvidenceSet.
        Raw AtomicClaim instances or unvalidated collections are strictly rejected and
        fail closed to an empty inconclusive matrix.
        """
        evidence_set = validated_evidence_set or (
            validated_evidence if isinstance(validated_evidence, ValidatedEvidenceSet) else None
        )

        eligible_claims: List[ValidatedClaim] = []
        origin_clusters: List[List[ValidatedClaim]] = []

        if evidence_set is not None:
            eligible_claims = list(evidence_set.eligible_claims)
            origin_clusters = [list(cl) for cl in evidence_set.provenance_clusters]
        elif isinstance(validated_evidence, (list, tuple, Sequence)):
            # Strictly verify that all elements are ValidatedClaim instances
            if validated_evidence and all(isinstance(c, ValidatedClaim) for c in validated_evidence):
                eligible_claims = [c for c in validated_evidence if c.eligibility_status == EligibilityStatus.ELIGIBLE]
                origin_clusters = cluster_claims_by_provenance(eligible_claims)
            else:
                # Raw AtomicClaim or unvalidated objects fail closed
                eligible_claims = []
                origin_clusters = []
        else:
            eligible_claims = []
            origin_clusters = []

        if not eligible_claims:
            unassessed_risks = [
                {
                    "lens_id": lens.id,
                    "lens_name": lens.name,
                    "assessment_status": "UNASSESSED",
                    "risk_direction": "UNKNOWN",
                    "severity": "UNKNOWN_UNASSESSED",
                    "risk_level": "UNKNOWN",
                    "confidence": 0.0,
                    "independent_roots_count": 0,
                    "total_claims_count": 0,
                    "key_evidence": [],
                    "verdict_summary": f"No evidence retrieved for risk lens '{lens.name}'."
                }
                for lens in hypotheses.risk_lenses
            ]
            return ACHMatrix(
                winning_hypothesis="ALL_HYPOTHESES_UNTESTED",
                decision_rationale="No valid atomic claims retrieved. All hypotheses remain completely untested.",
                is_inconclusive=True,
                evaluated_risk_lenses=unassessed_risks
            )

        rows: List[ACHMatrixRow] = []
        penalties = {"H1": 0.0, "H2": 0.0, "H0": 0.0}
        positive_support = {"H1": 0.0, "H2": 0.0, "H0": 0.0}
        net_scores = {"H1": 0.0, "H2": 0.0, "H0": 0.0}

        for cluster_idx, cluster_claims in enumerate(origin_clusters):
            cluster_size = len(cluster_claims)
            split_weight = 1.0 / (cluster_size or 1)
            cluster_origin_id = (
                getattr(cluster_claims[0], "provenance_root_id", None)
                or getattr(cluster_claims[0], "upstream_origin_id", None)
                or getattr(cluster_claims[0], "source_domain", None)
                or f"cluster_{cluster_idx}"
            )

            for claim in cluster_claims:
                confidence = max(0.1, min(1.0, claim.confidence))
                ratings = claim.inconsistency_ratings or {
                    "H1": 0.5 if claim.target_hypothesis == "H1" else -1.0,
                    "H2": 0.5 if claim.target_hypothesis == "H2" else -1.0,
                    "H0": 0.5 if claim.target_hypothesis == "H0" else -1.0
                }

                diagnosticity = self.calculate_diagnosticity(ratings)

                stmt = f"{claim.subject} {claim.predicate} {claim.object}"
                rows.append(ACHMatrixRow(
                    claim_id=claim.id,
                    statement=stmt,
                    grounded_summary=claim.grounded_summary,
                    verbatim_quote=claim.verbatim_quote,
                    source_domain=claim.source_domain,
                    source_url=claim.source_url,
                    source_title=getattr(claim, "source_title", "Document") or "Document",
                    locator=getattr(claim, "locator", "") or "",
                    retrieval_timestamp=getattr(claim, "retrieval_timestamp", "") or "",
                    upstream_origin_id=cluster_origin_id,
                    diagnosticity=round(diagnosticity, 2),
                    h1_score=ratings.get("H1", 0.0),
                    h2_score=ratings.get("H2", 0.0),
                    h0_score=ratings.get("H0", 0.0)
                ))

                for hyp_id in ["H1", "H2", "H0"]:
                    score = ratings.get(hyp_id, 0.0)
                    effective_weight = confidence * diagnosticity * split_weight

                    if score < 0:
                        penalties[hyp_id] += abs(score) * effective_weight
                    elif score > 0:
                        positive_support[hyp_id] += score * effective_weight

                    net_scores[hyp_id] += score * effective_weight

        # 2. EVALUATE ORTHOGONAL RISK LENSES (Over Eligible Claims Only)
        evaluated_risks = []
        SEVERITY_RANKS = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1, "UNKNOWN": 0}

        for lens in hypotheses.risk_lenses:
            matched_claims = [
                c for c in eligible_claims
                if getattr(c, "target_risk_lens_id", None) == lens.id
                or (lens.id.lower() in getattr(c, "subject", "").lower())
                or (lens.name.lower() in getattr(c, "object", "").lower())
            ]
            risk_clusters = cluster_claims_by_provenance(matched_claims)
            independent_roots = len(risk_clusters)

            if independent_roots == 0 or not matched_claims:
                evaluated_risks.append({
                    "lens_id": lens.id,
                    "lens_name": lens.name,
                    "assessment_status": "UNASSESSED",
                    "risk_direction": "UNKNOWN",
                    "severity": "UNKNOWN_UNASSESSED",
                    "risk_level": "UNKNOWN",
                    "confidence": 0.0,
                    "independent_roots_count": 0,
                    "total_claims_count": 0,
                    "key_evidence": [],
                    "verdict_summary": f"Risk lens '{lens.name}' has 0 verified claims. Assessment status is strictly UNASSESSED."
                })
                continue

            risk_support_count = 0
            risk_refute_count = 0
            neutral_count = 0
            unknown_count = 0
            claim_severities: List[str] = []

            for c in matched_claims:
                stance = self.classify_claim_risk_stance(c)
                if stance == "SUPPORTS":
                    risk_support_count += 1
                elif stance == "REFUTES":
                    risk_refute_count += 1
                elif stance == "NEUTRAL":
                    neutral_count += 1
                else:
                    unknown_count += 1

                struct_impact = getattr(c, "risk_impact", None)
                if struct_impact in ["CRITICAL", "HIGH", "MEDIUM", "LOW"]:
                    claim_severities.append(struct_impact)
                else:
                    blob = f"{c.predicate} {c.object} {c.grounded_summary or ''}".lower()
                    has_critical = bool(re.search(r'\b(critical|catastrophic|systemic|data\s+loss)\b', blob))
                    has_high = bool(re.search(r'\b(severe|major|serious|frequent|recurring|unresolved|sanction|customer\s+harm|bottleneck)\b', blob))
                    has_medium = bool(re.search(r'\b(moderate|intermittent|degradation|partial)\b', blob))
                    has_low = bool(re.search(r'\b(minor|isolated|negligible|remediated|low)\b', blob))

                    if has_critical:
                        claim_severities.append("CRITICAL")
                    elif has_high:
                        claim_severities.append("HIGH")
                    elif has_medium:
                        claim_severities.append("MEDIUM")
                    elif has_low:
                        claim_severities.append("LOW")
                    else:
                        claim_severities.append("UNKNOWN")

            max_severity = "UNKNOWN"
            max_rank = 0
            for sev in claim_severities:
                rank = SEVERITY_RANKS.get(sev, 0)
                if rank > max_rank:
                    max_rank = rank
                    max_severity = sev

            if risk_support_count > risk_refute_count and risk_support_count > 0:
                direction = "SUPPORTS_RISK"
                final_severity = max_severity if max_severity != "UNKNOWN" else ("HIGH" if independent_roots >= 2 else "MEDIUM")
                assessment_status = "ASSESSED"
            elif risk_refute_count > risk_support_count and risk_refute_count > 0:
                direction = "REFUTES_RISK"
                final_severity = "LOW"
                assessment_status = "ASSESSED"
            elif neutral_count > 0 and risk_support_count == 0 and risk_refute_count == 0:
                direction = "NEUTRAL"
                final_severity = "UNKNOWN_UNASSESSED"
                assessment_status = "INSUFFICIENT"
            elif unknown_count > 0 and risk_support_count == 0 and risk_refute_count == 0:
                direction = "NEUTRAL"
                final_severity = "UNKNOWN_UNASSESSED"
                assessment_status = "INSUFFICIENT"
            else:
                direction = "CONFLICTING"
                final_severity = max_severity if max_severity != "UNKNOWN" else "MEDIUM"
                assessment_status = "ASSESSED"

            risk_level_value = "UNKNOWN" if final_severity == "UNKNOWN_UNASSESSED" else final_severity

            avg_conf = sum(c.confidence for c in matched_claims) / len(matched_claims)
            evidence_scaling = min(1.0, 0.4 + (independent_roots * 0.2))
            final_conf = round(avg_conf * evidence_scaling, 2)

            key_evidence = [
                c.verbatim_quote if c.verbatim_quote else c.grounded_summary
                for c in matched_claims[:3]
            ]

            evaluated_risks.append({
                "lens_id": lens.id,
                "lens_name": lens.name,
                "assessment_status": assessment_status,
                "risk_direction": direction,
                "severity": final_severity,
                "risk_level": risk_level_value,
                "confidence": final_conf,
                "independent_roots_count": independent_roots,
                "total_claims_count": len(matched_claims),
                "key_evidence": key_evidence,
                "verdict_summary": f"Assessed direction: {direction} (Severity: {final_severity}, Roots: {independent_roots})."
            })

        # 3. HEUER DECISION RULE: Minimum Contradiction + Minimum Corroboration
        candidates = ["H1", "H2", "H0"]
        corroborated_candidates = [
            h for h in candidates
            if positive_support[h] >= self.min_corroboration_support
        ]

        if not corroborated_candidates:
            winning_hypothesis = "INCONCLUSIVE_EVIDENCE"
            decision_rationale = (
                f"Safety Protocol Triggered: No hypothesis achieved minimum positive corroboration threshold "
                f"({self.min_corroboration_support}). Support scores: H1={positive_support['H1']:.2f}, "
                f"H2={positive_support['H2']:.2f}, H0={positive_support['H0']:.2f}."
            )
            is_inconclusive = True
        else:
            sorted_candidates = sorted(
                corroborated_candidates,
                key=lambda h: (penalties[h], -net_scores[h])
            )
            winner = sorted_candidates[0]

            if len(sorted_candidates) > 1:
                runner_up = sorted_candidates[1]
                penalty_diff = penalties[runner_up] - penalties[winner]
                net_diff = net_scores[winner] - net_scores[runner_up]

                if penalty_diff < self.inconclusive_threshold and net_diff < self.inconclusive_threshold:
                    winning_hypothesis = "INCONCLUSIVE_EVIDENCE"
                    decision_rationale = (
                        f"Safety Protocol Triggered: Inconclusive distinction between {winner} (Penalty={penalties[winner]:.2f}, Net={net_scores[winner]:.2f}) "
                        f"and {runner_up} (Penalty={penalties[runner_up]:.2f}, Net={net_scores[runner_up]:.2f})."
                    )
                    is_inconclusive = True
                else:
                    winning_hypothesis = winner
                    decision_rationale = (
                        f"Hypothesis {winner} selected based on Heuer's diagnostic inconsistency minimization "
                        f"(Penalty={penalties[winner]:.2f}, Net={net_scores[winner]:.2f}, Support={positive_support[winner]:.2f})."
                    )
                    is_inconclusive = False
            else:
                winning_hypothesis = winner
                decision_rationale = (
                    f"Hypothesis {winner} is the sole corroborated hypothesis "
                    f"(Penalty={penalties[winner]:.2f}, Net={net_scores[winner]:.2f}, Support={positive_support[winner]:.2f})."
                )
                is_inconclusive = False

        return ACHMatrix(
            rows=rows,
            h1_net_score=round(net_scores["H1"], 3),
            h2_net_score=round(net_scores["H2"], 3),
            h0_net_score=round(net_scores["H0"], 3),
            h1_inconsistency_penalty=penalties["H1"],
            h2_inconsistency_penalty=penalties["H2"],
            h0_inconsistency_penalty=penalties["H0"],
            h1_positive_support=positive_support["H1"],
            h2_positive_support=positive_support["H2"],
            h0_positive_support=positive_support["H0"],
            winning_hypothesis=winning_hypothesis,
            decision_rationale=decision_rationale,
            is_inconclusive=is_inconclusive,
            evaluated_risk_lenses=evaluated_risks
        )
