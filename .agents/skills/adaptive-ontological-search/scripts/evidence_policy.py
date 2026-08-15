"""
Centralized Evidence Policy & Validation Engine (v2.1 Core — Architectural Refactor).
Implements:
1. Deep Immutability & Pure Trust Boundary: Never mutates input AtomicClaim objects.
   Produces frozen ValidatedClaim and frozen ValidatedEvidenceSet.
2. NormalizedSource: Strict URI/host parsing, trailing dot removal, posix path normalization, authority auditing.
3. Strict Allowlist Auditing: Exact host and true subdomain matching. Rejects query/path spoofing. Malformed allowlist fails closed.
4. Two-Phase Architecture:
   - Phase 1: validate_claims(...) -> frozen ValidatedEvidenceSet (sources, claims, provenance roots, coverage debt)
   - Phase 2: ACH & Risk Evaluation (consumes only eligible ValidatedClaim instances from ValidatedEvidenceSet)
   - Phase 3: evaluate_gate_decision(...) -> Single canonical frozen GateDecision with audit facts
5. Dimensional Relevancy: Hypothesis-specific Primary Authority and Root Floor Verification.
"""

import re
import urllib.parse
import posixpath
import dataclasses
from types import MappingProxyType
from typing import List, Dict, Tuple, Set, Optional, Any, Sequence, Mapping

from models import (
    AtomicClaim, VerificationStatus, ExecutionMode, DynamicOntology, HypothesisSet,
    PrecisionLevel, EvidenceRequirements, ResearchContract, GateDecision,
    NormalizedSource, ValidatedClaim, EligibilityStatus, RejectionReasonCode, ValidatedEvidenceSet
)


# =====================================================================
# EXACT NORMALIZED PRIMARY AUTHORITY REGISTRY & ENTITY REPOSITORY MAPPING
# =====================================================================

STANDALONE_AUTHORITY_REGISTRY: Dict[str, Dict[str, Any]] = {
    # Standards Bodies & Specifications
    "w3.org": {"type": "STANDARDS_BODY_SPECIFICATION", "subdomains_allowed": True},
    "ietf.org": {"type": "RFC_STANDARDS_SPECIFICATION", "subdomains_allowed": True},
    "rfc-editor.org": {"type": "RFC_STANDARDS_SPECIFICATION", "subdomains_allowed": True},
    "iso.org": {"type": "INTERNATIONAL_STANDARDS", "subdomains_allowed": True},
    "nist.gov": {"type": "GOVERNMENT_SECURITY_STANDARDS", "subdomains_allowed": True},
    "sec.gov": {"type": "REGULATORY_FILINGS", "subdomains_allowed": True},
    "europa.eu": {"type": "REGULATORY_FRAMEWORK", "subdomains_allowed": True},
    "gov.uk": {"type": "REGULATORY_FRAMEWORK", "subdomains_allowed": True},

    # Canonical Engineering & Database Projects
    "postgresql.org": {"type": "OFFICIAL_PROJECT_DOCUMENTATION", "subdomains_allowed": True},
    "cockroachlabs.com": {"type": "OFFICIAL_VENDOR_DOCUMENTATION", "subdomains_allowed": True},
    "mysql.com": {"type": "OFFICIAL_VENDOR_DOCUMENTATION", "subdomains_allowed": True},
    "oracle.com": {"type": "OFFICIAL_VENDOR_DOCUMENTATION", "subdomains_allowed": True},
    "rust-lang.org": {"type": "OFFICIAL_LANGUAGE_DOCUMENTATION", "subdomains_allowed": True},
    "go.dev": {"type": "OFFICIAL_LANGUAGE_DOCUMENTATION", "subdomains_allowed": True},
    "golang.org": {"type": "OFFICIAL_LANGUAGE_DOCUMENTATION", "subdomains_allowed": True},
    "python.org": {"type": "OFFICIAL_LANGUAGE_DOCUMENTATION", "subdomains_allowed": True},
    "apache.org": {"type": "OFFICIAL_PROJECT_DOCUMENTATION", "subdomains_allowed": True},
    "kubernetes.io": {"type": "OFFICIAL_PROJECT_DOCUMENTATION", "subdomains_allowed": True},
    "linuxfoundation.org": {"type": "OFFICIAL_PROJECT_DOCUMENTATION", "subdomains_allowed": True},
    "kernel.org": {"type": "OFFICIAL_KERNEL_SOURCE", "subdomains_allowed": True},
    "solarcouncil.org": {"type": "OFFICIAL_INDUSTRY_STANDARD", "subdomains_allowed": True},
}

PRIMARY_AUTHORITY_REGISTRY = STANDALONE_AUTHORITY_REGISTRY

PLATFORM_HOSTS: Set[str] = {
    "github.com", "gitlab.com", "bitbucket.org", "raw.githubusercontent.com"
}

CANONICAL_PLATFORM_ORGANIZATIONS: Set[str] = {
    "postgres", "cockroachdb", "mysql", "rust-lang", "golang", "python",
    "apache", "kubernetes", "torvalds", "ietf-tools", "w3c", "solarcouncil",
    "linuxfoundation", "opencomputeproject", "grpc", "envoyproxy"
}


# =====================================================================
# URI & SOURCE NORMALIZATION HELPERS (Pure Functions)
# =====================================================================

def normalize_allowlist_entry(entry: str) -> Optional[str]:
    """
    Parses and extracts canonical hostname from an allowed_sources entry.
    Supports both 'example.org' and 'https://example.org/path'.
    Rejects malformed entries (port spoofing, userinfo, empty, invalid chars, non-http/https schemes).
    """
    if not entry or not isinstance(entry, str):
        return None
    raw = entry.strip().lower()
    if not raw or "@" in raw or " " in raw:
        return None
    if "://" in raw:
        scheme = raw.split("://")[0].strip().lower()
        if scheme not in ["http", "https"]:
            return None
    else:
        raw = "https://" + raw

    try:
        parsed = urllib.parse.urlparse(raw)
        if parsed.scheme not in ["http", "https"]:
            return None
        if parsed.username or parsed.password or parsed.port:
            return None
        host = (parsed.hostname or "").strip().lower()
        if host.endswith("."):
            host = host[:-1]
        if not host or ":" in host or "@" in host:
            return None
        if not re.match(r"^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?(\.[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?)*$", host):
            return None
        return host
    except Exception:
        return None


def is_source_url_allowed(claim_url: str, claim_domain: str, raw_allowed_sources: List[str]) -> Tuple[bool, str]:
    """
    Strictly audits a claim's source URL and domain against the allowlist.
    Returns: (is_allowed, reason).
    Fails closed if allowlist contains malformed entries, non-http/https schemes, or claim host doesn't match exact host / true subdomain.
    """
    if claim_url:
        try:
            parsed = urllib.parse.urlparse(claim_url)
            scheme = (parsed.scheme or "").lower().strip()
            if scheme and scheme not in ["http", "https"]:
                return False, f"DISALLOWED_CLAIM_URI_SCHEME: '{scheme}'"
        except Exception:
            return False, "MALFORMED_CLAIM_URL"

    if not raw_allowed_sources:
        return True, "NO_ALLOWLIST_SPECIFIED"

    canonical_allowed_hosts: List[str] = []
    for s in raw_allowed_sources:
        norm_s = normalize_allowlist_entry(s)
        if not norm_s:
            return False, f"MALFORMED_ALLOWLIST_ENTRY: '{s}'"
        canonical_allowed_hosts.append(norm_s)

    claim_host = ""
    if claim_url:
        try:
            parsed = urllib.parse.urlparse(claim_url)
            claim_host = (parsed.hostname or "").strip().lower()
            if claim_host.endswith("."):
                claim_host = claim_host[:-1]
        except Exception:
            claim_host = ""

    if not claim_host and claim_domain:
        claim_host = claim_domain.strip().lower().split(":")[0]
        if claim_host.endswith("."):
            claim_host = claim_host[:-1]

    if not claim_host:
        return False, "MISSING_OR_MALFORMED_CLAIM_HOSTNAME"

    for allowed_host in canonical_allowed_hosts:
        if claim_host == allowed_host:
            return True, f"EXACT_MATCH: {allowed_host}"
        if claim_host.endswith("." + allowed_host):
            return True, f"SUBDOMAIN_MATCH: {allowed_host}"

    return False, f"DISALLOWED_HOST: '{claim_host}' not in {canonical_allowed_hosts}"


def check_primary_authority(uri: str, domain: str) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Validates primary authority against exact registered domain registry and verified entity namespaces.
    Requires http or https scheme for web sources, and requires non-empty repository name for platform hosts.
    Returns: (is_primary, primary_authority_type, primary_status_reason)
    """
    if not uri and not domain:
        return False, None, "MISSING_URI_AND_DOMAIN"

    raw_host = ""
    clean_path = ""
    if uri:
        try:
            parsed = urllib.parse.urlparse(uri)
            scheme = (parsed.scheme or "").lower().strip()
            if scheme and scheme not in ["http", "https"]:
                return False, None, f"DISALLOWED_URI_SCHEME: '{scheme}' (only http/https permitted)"
            raw_host = (parsed.hostname or "").lower().strip()
            if raw_host.endswith("."):
                raw_host = raw_host[:-1]
            norm_p = posixpath.normpath(parsed.path or "/")
            clean_path = norm_p.strip("/")
        except Exception:
            raw_host = ""
            clean_path = ""
    if not raw_host and domain:
        raw_host = domain.lower().split(":")[0].strip()
        if raw_host.endswith("."):
            raw_host = raw_host[:-1]

    clean_host = raw_host

    if clean_host in ["", "example.com", "simulation.local", "web.grounded", "unknown"]:
        return False, None, "GENERIC_OR_SIMULATION_DOMAIN"

    # 1. Check Multi-Tenant Code Platforms (e.g. github.com)
    if clean_host in PLATFORM_HOSTS:
        path_parts = [p.lower() for p in clean_path.split("/") if p]
        if len(path_parts) >= 2:
            org_namespace = path_parts[0]
            repo_name = path_parts[1]
            if org_namespace in CANONICAL_PLATFORM_ORGANIZATIONS and repo_name:
                repo_id = f"{org_namespace}/{repo_name}"
                return True, "OFFICIAL_CODE_REPOSITORY", f"VERIFIED_CANONICAL_ORGANIZATION: {clean_host}/{repo_id}"
            else:
                return False, None, f"UNVERIFIED_PLATFORM_REPOSITORY: {clean_host}/{org_namespace}/{repo_name} (unauthorized namespace)"
        elif len(path_parts) == 1:
            org_namespace = path_parts[0]
            return False, None, f"UNVERIFIED_PLATFORM_ORGANIZATION_ROOT: {clean_host}/{org_namespace} (missing repository name)"
        return False, None, f"GENERIC_PLATFORM_ROOT: {clean_host}"

    # 2. Check Standalone Canonical Authorities & Legitimate Subdomains
    for auth_domain, auth_meta in STANDALONE_AUTHORITY_REGISTRY.items():
        if clean_host == auth_domain:
            return True, auth_meta["type"], f"EXACT_AUTHORITY_REGISTRY: {auth_domain} ({auth_meta['type']})"
        
        if auth_meta.get("subdomains_allowed", False):
            if clean_host.endswith("." + auth_domain):
                prefix = clean_host[:-len(auth_domain)]
                if prefix.endswith("."):
                    return True, auth_meta["type"], f"VERIFIED_SUBDOMAIN_AUTHORITY: {clean_host} -> {auth_domain} ({auth_meta['type']})"

    return False, None, "UNREGISTERED_SECONDARY_SOURCE"


def normalize_source(raw_url: str, raw_domain: str) -> NormalizedSource:
    """
    Pure parser and normalizer for source URLs and domains.
    Extracts canonical hostname, normalized posix path, and audits authority against registry.
    """
    clean_url = (raw_url or "").strip()
    clean_domain = (raw_domain or "").strip().lower()

    hostname = ""
    norm_path = "/"
    canonical_url = clean_url

    if clean_url:
        try:
            parsed = urllib.parse.urlparse(clean_url)
            scheme = (parsed.scheme or "").lower().strip()
            if scheme and scheme not in ["http", "https"]:
                if scheme in ["simulation", "mock"]:
                    hostname = clean_domain or "simulation.local"
                    norm_path = "/"
                    canonical_url = f"simulation://{hostname}/"
                else:
                    return NormalizedSource(
                        raw_url=clean_url,
                        raw_domain=clean_domain,
                        canonical_url=clean_url,
                        hostname="",
                        normalized_path="/",
                        is_primary_authority=False,
                        authority_type=None,
                        authority_reason=f"DISALLOWED_URI_SCHEME: '{scheme}'"
                    )
            else:
                hostname = (parsed.hostname or "").strip().lower()
                if hostname.endswith("."):
                    hostname = hostname[:-1]
                raw_path = parsed.path or "/"
                norm_path = posixpath.normpath(raw_path)
                eff_scheme = scheme or "https"
                canonical_url = f"{eff_scheme}://{hostname}{norm_path}"
                if parsed.query:
                    canonical_url += f"?{parsed.query}"
        except Exception:
            hostname = clean_domain
            norm_path = "/"
    elif clean_domain:
        hostname = clean_domain.split(":")[0].strip()
        canonical_url = f"https://{hostname}/"

    is_primary, auth_type, auth_reason = check_primary_authority(clean_url, clean_domain)

    return NormalizedSource(
        raw_url=clean_url,
        raw_domain=clean_domain,
        canonical_url=canonical_url,
        hostname=hostname,
        normalized_path=norm_path,
        is_primary_authority=is_primary,
        authority_type=auth_type,
        authority_reason=auth_reason or ""
    )


def cluster_claims_by_provenance(claims: Sequence[Any]) -> List[List[Any]]:
    """
    Clusters atomic or validated claims into independent provenance roots using Disjoint-Set Union (Union-Find).
    Claims are clustered together if they share:
    1. The same explicit upstream_origin_id
    2. The same source_domain / canonical host
    """
    if not claims:
        return []

    parent = list(range(len(claims)))

    def find(i: int) -> int:
        if parent[i] == i:
            return i
        parent[i] = find(parent[i])
        return parent[i]

    def union(i: int, j: int):
        root_i = find(i)
        root_j = find(j)
        if root_i != root_j:
            parent[root_i] = root_j

    origin_map: Dict[str, int] = {}
    domain_map: Dict[str, int] = {}

    generic_domains = {"example.com", "simulation.local", "web.grounded", "unknown_origin", ""}

    for idx, c in enumerate(claims):
        orig_id = getattr(c, "upstream_origin_id", None) or getattr(c, "provenance_root_id", None)
        domain = getattr(c, "source_domain", "") or ""

        # 1. Cluster by upstream_origin_id
        if orig_id and orig_id not in ["unknown_origin", "domain_origin", ""]:
            if orig_id in origin_map:
                union(idx, origin_map[orig_id])
            else:
                origin_map[orig_id] = idx

        # 2. Cluster by domain
        if domain and domain.lower() not in generic_domains:
            dom = domain.lower().split(":")[0].strip()
            if dom in domain_map:
                union(idx, domain_map[dom])
            else:
                domain_map[dom] = idx

    clusters_dict: Dict[int, List[Any]] = {}
    for idx, c in enumerate(claims):
        root = find(idx)
        clusters_dict.setdefault(root, []).append(c)

    return list(clusters_dict.values())


# =====================================================================
# EVIDENCE POLICY ENGINE (Two-Phase Pure Architecture)
# =====================================================================

class EvidencePolicy:
    """
    Centralized Evidence Policy Authority (Pure Trust Boundary).
    Does NOT mutate input AtomicClaim objects in place.
    Produces immutable ValidatedClaim representations and frozen ValidatedEvidenceSet.
    """

    is_source_url_allowed = staticmethod(is_source_url_allowed)
    check_primary_authority = staticmethod(check_primary_authority)
    normalize_source = staticmethod(normalize_source)
    cluster_claims_by_provenance = staticmethod(cluster_claims_by_provenance)

    @classmethod
    def validate_claims(
        cls,
        contract: Any,
        ontology: DynamicOntology,
        claims: Sequence[AtomicClaim],
        hypotheses: HypothesisSet,
        current_depth: int = 1,
        effective_max_depth: int = 3,
        query_ledger: Optional[List[Any]] = None
    ) -> ValidatedEvidenceSet:
        """
        Phase 1: Pure Source & Claim Validation.
        Transforms raw claims into immutable ValidatedClaim objects, audits allowlist,
        verifies authority, performs provenance clustering, and evaluates coverage debt.
        """
        is_mock = (contract.execution_mode == ExecutionMode.MOCK)
        precision = getattr(contract, "precision_level", None)
        if precision is None or precision == PrecisionLevel.UNKNOWN_FAIL_CLOSED:
            precision = PrecisionLevel.from_string(getattr(contract, "required_precision", ""))

        requirements = getattr(contract, "evidence_requirements", None)
        if requirements is None:
            requirements = EvidenceRequirements.for_precision(precision, contract.execution_mode)

        allowed_sources = getattr(contract, "allowed_sources", []) or []

        # Build query ledger lookup if ledger is supplied
        ledger_lookup: Dict[str, Any] = {}
        if query_ledger is not None:
            for q in query_ledger:
                qid = getattr(q, "query_id", None) or (q.get("query_id") if isinstance(q, dict) else None)
                if qid:
                    ledger_lookup[qid] = q

        eligible_claims: List[ValidatedClaim] = []
        rejected_claims: List[Tuple[ValidatedClaim, str]] = []

        for c in claims:
            norm_source = normalize_source(getattr(c, "source_url", ""), getattr(c, "source_domain", ""))

            # 1. Allowlist Audit
            if is_mock:
                is_allowed = True
                allow_reason = "MOCK_SIMULATION_ALLOWLIST_BYPASS"
            else:
                is_allowed, allow_reason = is_source_url_allowed(
                    norm_source.raw_url, norm_source.raw_domain, allowed_sources
                )
            if not is_allowed:
                v_claim = ValidatedClaim(
                    id=c.id,
                    subject=c.subject,
                    predicate=c.predicate,
                    object=c.object,
                    normalized_source=norm_source,
                    effective_verification_status=VerificationStatus.REFUTED,
                    is_primary_source=False,
                    authority_decision=False,
                    authority_type=None,
                    authority_reason=allow_reason,
                    eligibility_status=EligibilityStatus.REJECTED,
                    rejection_reason_code="REJECTED_DISALLOWED_SOURCE",
                    confidence=0.0,
                    target_hypothesis=c.target_hypothesis,
                    source_title=getattr(c, "source_title", "") or norm_source.raw_domain or "Document",
                    locator=getattr(c, "locator", "") or "",
                    retrieval_timestamp=getattr(c, "retrieval_timestamp", "") or "",
                    subject_entity_id=getattr(c, "subject_entity_id", None),
                    target_concept=getattr(c, "target_concept", None),
                    covered_ontology_classes=tuple(getattr(c, "covered_ontology_classes", []) or []),
                    grounded_summary=c.grounded_summary,
                    verbatim_quote=c.verbatim_quote,
                    is_llm_grounded_summary=getattr(c, "is_llm_grounded_summary", False),
                    target_risk_lens_id=getattr(c, "target_risk_lens_id", None),
                    inconsistency_ratings=MappingProxyType(dict(getattr(c, "inconsistency_ratings", {}) or {})),
                    query_id=getattr(c, "query_id", None),
                    risk_stance=getattr(c, "risk_stance", None),
                    risk_impact=getattr(c, "risk_impact", None),
                    risk_likelihood=getattr(c, "risk_likelihood", None),
                    provenance_root_id=None,
                    upstream_origin_id_val=getattr(c, "upstream_origin_id", None)
                )
                rejected_claims.append((v_claim, "REJECTED_DISALLOWED_SOURCE"))
                continue

            # 2. Query Ledger Lineage & Consistency Audit (LIVE Mode with supplied ledger)
            query_lineage_rejection: Optional[str] = None
            if not is_mock and query_ledger is not None:
                claim_qid = getattr(c, "query_id", None)
                if not claim_qid or claim_qid not in ledger_lookup:
                    query_lineage_rejection = "REJECTED_UNKNOWN_QUERY_ID"
                else:
                    rec = ledger_lookup[claim_qid]
                    rec_status = getattr(rec, "status", "EXECUTED") or (rec.get("status") if isinstance(rec, dict) else "EXECUTED")
                    if rec_status != "EXECUTED":
                        query_lineage_rejection = "REJECTED_FAILED_QUERY_LINEAGE"
                    else:
                        # Check dimensional lineage consistency
                        rec_hyp = getattr(rec, "target_hypothesis", None) or (rec.get("target_hypothesis") if isinstance(rec, dict) else None)
                        rec_lens = getattr(rec, "target_risk_lens_id", None) or (rec.get("target_risk_lens_id") if isinstance(rec, dict) else None)
                        rec_concept = getattr(rec, "target_concept", None) or (rec.get("target_concept") if isinstance(rec, dict) else None)

                        # Hypothesis matching
                        if rec_hyp in ["H1", "H2", "H0", "SKEPTIC", "DISPROVING"]:
                            if rec_hyp == "H1" and c.target_hypothesis != "H1":
                                query_lineage_rejection = "REJECTED_QUERY_HYPOTHESIS_MISMATCH"
                            elif rec_hyp == "H2" and c.target_hypothesis != "H2":
                                query_lineage_rejection = "REJECTED_QUERY_HYPOTHESIS_MISMATCH"
                            elif rec_hyp in ["H0", "SKEPTIC", "DISPROVING"] and c.target_hypothesis not in ["H0", "SKEPTIC", "DISPROVING"]:
                                query_lineage_rejection = "REJECTED_QUERY_HYPOTHESIS_MISMATCH"
                        
                        # Risk lens matching
                        if not query_lineage_rejection and (rec_hyp == "RISK_LENS" or rec_lens):
                            claim_lens = getattr(c, "target_risk_lens_id", None)
                            if rec_lens and claim_lens and rec_lens.lower() != claim_lens.lower():
                                query_lineage_rejection = "REJECTED_QUERY_RISK_LENS_MISMATCH"

                        # Concept matching
                        if not query_lineage_rejection and rec_concept:
                            claim_concept = getattr(c, "target_concept", None)
                            claim_classes = [cls.lower() for cls in getattr(c, "covered_ontology_classes", ()) if cls]
                            claim_subj = (getattr(c, "subject", "") or "").lower()
                            claim_obj = (getattr(c, "object", "") or "").lower()
                            if claim_concept and claim_concept.lower() != rec_concept.lower():
                                if rec_concept.lower() not in claim_classes and rec_concept.lower() not in claim_subj and rec_concept.lower() not in claim_obj:
                                    query_lineage_rejection = "REJECTED_QUERY_CONCEPT_MISMATCH"

            if query_lineage_rejection:
                v_claim = ValidatedClaim(
                    id=c.id,
                    subject=c.subject,
                    predicate=c.predicate,
                    object=c.object,
                    normalized_source=norm_source,
                    effective_verification_status=VerificationStatus.REFUTED,
                    is_primary_source=False,
                    authority_decision=False,
                    authority_type=None,
                    authority_reason=query_lineage_rejection,
                    eligibility_status=EligibilityStatus.REJECTED,
                    rejection_reason_code=query_lineage_rejection,
                    confidence=0.0,
                    target_hypothesis=c.target_hypothesis,
                    source_title=getattr(c, "source_title", "") or norm_source.raw_domain or "Document",
                    locator=getattr(c, "locator", "") or "",
                    retrieval_timestamp=getattr(c, "retrieval_timestamp", "") or "",
                    subject_entity_id=getattr(c, "subject_entity_id", None),
                    target_concept=getattr(c, "target_concept", None),
                    covered_ontology_classes=tuple(getattr(c, "covered_ontology_classes", []) or []),
                    grounded_summary=c.grounded_summary,
                    verbatim_quote=c.verbatim_quote,
                    is_llm_grounded_summary=getattr(c, "is_llm_grounded_summary", False),
                    target_risk_lens_id=getattr(c, "target_risk_lens_id", None),
                    inconsistency_ratings=MappingProxyType(dict(getattr(c, "inconsistency_ratings", {}) or {})),
                    query_id=getattr(c, "query_id", None),
                    risk_stance=getattr(c, "risk_stance", None),
                    risk_impact=getattr(c, "risk_impact", None),
                    risk_likelihood=getattr(c, "risk_likelihood", None),
                    provenance_root_id=None,
                    upstream_origin_id_val=getattr(c, "upstream_origin_id", None)
                )
                rejected_claims.append((v_claim, query_lineage_rejection))
                continue

            # 3. Authority & Status Auditing
            is_auth_primary = norm_source.is_primary_authority
            auth_type = norm_source.authority_type
            auth_reason = norm_source.authority_reason

            raw_status = c.verification_status
            if is_mock:
                eff_status = VerificationStatus.UNVERIFIED_MOCK
                is_eligible = True
                rejection_code = None
            else:
                if raw_status in [VerificationStatus.UNVERIFIED_MOCK, VerificationStatus.UNVERIFIED_CLAIM, VerificationStatus.REFUTED]:
                    eff_status = raw_status if isinstance(raw_status, VerificationStatus) else VerificationStatus.UNVERIFIED_CLAIM
                    is_eligible = False
                    rejection_code = f"REJECTED_{raw_status.name if hasattr(raw_status, 'name') else str(raw_status)}"
                elif raw_status in [VerificationStatus.VERIFIED_PRIMARY, VerificationStatus.VERIFIED_SECONDARY, "VERIFIED_PRIMARY", "VERIFIED_SECONDARY"]:
                    eff_status = VerificationStatus.VERIFIED_PRIMARY if is_auth_primary else VerificationStatus.VERIFIED_SECONDARY
                    is_eligible = True
                    rejection_code = None
                else:
                    eff_status = VerificationStatus.REFUTED
                    is_eligible = False
                    rejection_code = "REJECTED_UNRECOGNIZED_STATUS"

            v_claim = ValidatedClaim(
                id=c.id,
                subject=c.subject,
                predicate=c.predicate,
                object=c.object,
                normalized_source=norm_source,
                effective_verification_status=eff_status,
                is_primary_source=is_auth_primary if is_eligible else False,
                authority_decision=is_auth_primary,
                authority_type=auth_type,
                authority_reason=auth_reason,
                eligibility_status=EligibilityStatus.ELIGIBLE if is_eligible else EligibilityStatus.REJECTED,
                rejection_reason_code=rejection_code,
                confidence=c.confidence if is_eligible else 0.0,
                target_hypothesis=c.target_hypothesis,
                source_title=getattr(c, "source_title", "") or norm_source.raw_domain or "Document",
                locator=getattr(c, "locator", "") or "",
                retrieval_timestamp=getattr(c, "retrieval_timestamp", "") or "",
                subject_entity_id=getattr(c, "subject_entity_id", None),
                target_concept=getattr(c, "target_concept", None),
                covered_ontology_classes=tuple(getattr(c, "covered_ontology_classes", []) or []),
                grounded_summary=c.grounded_summary,
                verbatim_quote=c.verbatim_quote,
                is_llm_grounded_summary=getattr(c, "is_llm_grounded_summary", False),
                target_risk_lens_id=getattr(c, "target_risk_lens_id", None),
                inconsistency_ratings=MappingProxyType(dict(getattr(c, "inconsistency_ratings", {}) or {})),
                query_id=getattr(c, "query_id", None),
                risk_stance=getattr(c, "risk_stance", None),
                risk_impact=getattr(c, "risk_impact", None),
                risk_likelihood=getattr(c, "risk_likelihood", None),
                provenance_root_id=None,
                upstream_origin_id_val=getattr(c, "upstream_origin_id", None)
            )

            if is_eligible:
                eligible_claims.append(v_claim)
            else:
                rejected_claims.append((v_claim, rejection_code or "REJECTED"))

        # 3. Provenance Clustering (Union-Find) over Eligible Claims ONLY
        raw_clusters = cluster_claims_by_provenance(eligible_claims)
        provenance_clusters: List[Tuple[ValidatedClaim, ...]] = []
        
        for cluster_idx, cluster_items in enumerate(raw_clusters):
            root_id = getattr(cluster_items[0], "upstream_origin_id", None) or cluster_items[0].normalized_source.hostname or f"root_{cluster_idx}"
            updated_cluster = [
                dataclasses.replace(item, provenance_root_id=root_id)
                for item in cluster_items
            ]
            provenance_clusters.append(tuple(updated_cluster))

        final_eligible_claims = [c for cl in provenance_clusters for c in cl]

        unique_origins_count = len(provenance_clusters)
        total_claims_count = len(final_eligible_claims) or 1

        primary_claims_count = sum(
            1 for c in final_eligible_claims
            if c.is_primary_source and c.effective_verification_status in [VerificationStatus.VERIFIED_PRIMARY, "VERIFIED_PRIMARY"]
        )
        secondary_claims_count = len(final_eligible_claims) - primary_claims_count
        primary_source_ratio = round(primary_claims_count / total_claims_count, 2)

        # 4. Hypothesis-Specific Diagnostic Roots & Primary Authority Roots
        h1_clusters = [
            cl for cl in provenance_clusters
            if any(
                c.target_hypothesis == "H1"
                and (c.inconsistency_ratings.get("H1", 0.0) > 0 or is_mock)
                and c.subject not in ["UNKNOWN", "unknown", "GeneralConcept"]
                and not c.target_risk_lens_id
                for c in cl
            )
        ]
        h1_diagnostic_origins_count = len(h1_clusters)
        h1_primary_clusters = [
            cl for cl in h1_clusters
            if any(
                c.target_hypothesis == "H1"
                and c.inconsistency_ratings.get("H1", 0.0) > 0
                and c.subject not in ["UNKNOWN", "unknown", "GeneralConcept"]
                and not c.target_risk_lens_id
                and c.is_primary_source
                and c.effective_verification_status in [VerificationStatus.VERIFIED_PRIMARY, "VERIFIED_PRIMARY"]
                for c in cl
            )
        ]
        h1_primary_roots_count = len(h1_primary_clusters)

        h2_clusters = [
            cl for cl in provenance_clusters
            if any(
                c.target_hypothesis == "H2"
                and (abs(c.inconsistency_ratings.get("H2", 0.0)) > 0 or is_mock)
                and c.subject not in ["UNKNOWN", "unknown", "GeneralConcept"]
                and not c.target_risk_lens_id
                for c in cl
            )
        ]
        h2_diagnostic_origins_count = len(h2_clusters)
        h2_primary_clusters = [
            cl for cl in h2_clusters
            if any(
                c.target_hypothesis == "H2"
                and abs(c.inconsistency_ratings.get("H2", 0.0)) > 0
                and c.subject not in ["UNKNOWN", "unknown", "GeneralConcept"]
                and not c.target_risk_lens_id
                and c.is_primary_source
                and c.effective_verification_status in [VerificationStatus.VERIFIED_PRIMARY, "VERIFIED_PRIMARY"]
                for c in cl
            )
        ]
        h2_primary_roots_count = len(h2_primary_clusters)

        h0_clusters = [
            cl for cl in provenance_clusters
            if any(
                c.target_hypothesis in ["H0", "SKEPTIC", "DISPROVING"]
                and (abs(c.inconsistency_ratings.get("H0", 0.0)) > 0 or is_mock)
                and c.subject not in ["UNKNOWN", "unknown", "GeneralConcept"]
                and not c.target_risk_lens_id
                for c in cl
            )
        ]
        h0_diagnostic_origins_count = len(h0_clusters)
        h0_primary_clusters = [
            cl for cl in h0_clusters
            if any(
                c.target_hypothesis in ["H0", "SKEPTIC", "DISPROVING"]
                and abs(c.inconsistency_ratings.get("H0", 0.0)) > 0
                and c.subject not in ["UNKNOWN", "unknown", "GeneralConcept"]
                and not c.target_risk_lens_id
                and c.is_primary_source
                and c.effective_verification_status in [VerificationStatus.VERIFIED_PRIMARY, "VERIFIED_PRIMARY"]
                for c in cl
            )
        ]
        h0_primary_roots_count = len(h0_primary_clusters)

        # 5. Coverage Debt & Evidenced Classes
        evidenced_classes: Set[str] = set()
        for c in final_eligible_claims:
            is_diag = any(abs(v) > 0 for v in c.inconsistency_ratings.values()) if c.inconsistency_ratings else True
            if is_mock or is_diag:
                for cls_name in c.covered_ontology_classes:
                    if cls_name in ontology.classes:
                        evidenced_classes.add(cls_name)
                if c.target_concept and c.target_concept in ontology.classes:
                    evidenced_classes.add(c.target_concept)
                if getattr(c, "subject", None) and c.subject in ontology.classes:
                    evidenced_classes.add(c.subject)

        unresolved_coverage_debt = [cls_name for cls_name in ontology.classes if cls_name not in evidenced_classes]

        default_gate = GateDecision(
            is_stopping_allowed=False,
            synthesis_status="INSUFFICIENT_EVIDENCE_SAFETY_BLOCK",
            reason="Claims validated; awaiting ACH and risk evaluation.",
            is_fail_closed=False,
            unresolved_material_risks=(),
            action_required="Evaluate ACH and Risk Lenses",
            can_synthesize_conditional=False
        )

        return ValidatedEvidenceSet(
            eligible_claims=tuple(final_eligible_claims),
            rejected_claims=tuple(rejected_claims),
            provenance_clusters=tuple(provenance_clusters),
            h1_diagnostic_origins_count=h1_diagnostic_origins_count,
            h2_diagnostic_origins_count=h2_diagnostic_origins_count,
            h0_diagnostic_origins_count=h0_diagnostic_origins_count,
            h1_primary_roots_count=h1_primary_roots_count,
            h2_primary_roots_count=h2_primary_roots_count,
            h0_primary_roots_count=h0_primary_roots_count,
            primary_claims_count=primary_claims_count,
            secondary_claims_count=secondary_claims_count,
            primary_source_ratio=primary_source_ratio,
            evidenced_classes=tuple(sorted(evidenced_classes)),
            unresolved_coverage_debt=tuple(sorted(unresolved_coverage_debt)),
            gate_decision=default_gate,
            contract_stopping_criteria_met=False
        )

    @classmethod
    def evaluate_gate_decision(
        cls,
        contract: Any,
        ontology: DynamicOntology,
        hypotheses: HypothesisSet,
        validated_evidence_set: ValidatedEvidenceSet,
        ach_matrix: Any,
        query_ledger: Optional[List[Any]] = None,
        current_depth: int = 1,
        effective_max_depth: int = 3
    ) -> GateDecision:
        """
        Phase 3: Pure Single GateDecision Evaluation.
        Synthesizes contract requirements, validated evidence floors, query ledger status,
        and orthogonal risk evaluations into a single canonical GateDecision with audit facts.
        """
        precision = getattr(contract, "precision_level", None)
        if precision is None or precision == PrecisionLevel.UNKNOWN_FAIL_CLOSED:
            precision = PrecisionLevel.from_string(getattr(contract, "required_precision", ""))

        requirements = getattr(contract, "evidence_requirements", None)
        if requirements is None:
            requirements = EvidenceRequirements.for_precision(precision, contract.execution_mode)

        is_fail_closed = False
        fail_closed_reason = None
        if precision == PrecisionLevel.UNKNOWN_FAIL_CLOSED:
            is_fail_closed = True
            fail_closed_reason = f"UNKNOWN_PRECISION_LEVEL: '{getattr(contract, 'required_precision', '')}'. Failing closed."
        elif requirements.is_fail_closed:
            is_fail_closed = True
            fail_closed_reason = "EVIDENCE_REQUIREMENTS_FAIL_CLOSED"

        # Search Query Ledger Auditing
        if query_ledger:
            h0_search_attempted = any(
                q.target_hypothesis in ["H0", "SKEPTIC", "DISPROVING"] and q.status in ["EXECUTED", "NO_RESULTS"]
                for q in query_ledger
            )
            all_risk_searches_completed = all(
                any(
                    q.target_risk_lens_id == r.id and q.status in ["EXECUTED", "NO_RESULTS"]
                    for q in query_ledger
                )
                for r in hypotheses.risk_lenses
            ) if hypotheses.risk_lenses else True
        else:
            h0_search_attempted = any(
                getattr(c, "target_hypothesis", None) in ["H0", "SKEPTIC", "DISPROVING"]
                for c in validated_evidence_set.eligible_claims
            )
            all_risk_searches_completed = all(
                any(getattr(c, "target_risk_lens_id", None) == r.id for c in validated_evidence_set.eligible_claims)
                for r in hypotheses.risk_lenses
            ) if hypotheses.risk_lenses else True

        h0_search_met = h0_search_attempted if requirements.require_counterevidence_search else True

        # Evidence root floors
        has_h1_roots = (validated_evidence_set.h1_diagnostic_origins_count >= requirements.min_independent_roots_h1)
        has_h2_roots = (validated_evidence_set.h2_diagnostic_origins_count >= requirements.min_independent_roots_h2)
        has_h0_roots = (validated_evidence_set.h0_diagnostic_origins_count >= requirements.min_independent_roots_h0) if requirements.require_counterevidence_search else True

        has_h1_primary = (validated_evidence_set.h1_primary_roots_count >= requirements.min_primary_roots_h1)
        has_h2_primary = (validated_evidence_set.h2_primary_roots_count >= requirements.min_primary_roots_h2)
        has_h0_primary = (validated_evidence_set.h0_primary_roots_count >= requirements.min_primary_roots_h0)
        has_primary_ratio = (validated_evidence_set.primary_source_ratio >= requirements.min_primary_ratio)

        zero_coverage_debt = (len(validated_evidence_set.unresolved_coverage_debt) == 0)

        # Risk lenses evaluation
        unresolved_material_risks: List[str] = []
        all_material_risks_assessed = True

        evaluated_risk_lenses = getattr(ach_matrix, "evaluated_risk_lenses", [])
        if hypotheses.risk_lenses:
            if not evaluated_risk_lenses:
                all_material_risks_assessed = False
                unresolved_material_risks = [lens.name for lens in hypotheses.risk_lenses]
            else:
                evaluated_dict = {r.get("lens_id"): r for r in evaluated_risk_lenses if isinstance(r, dict)}
                for lens in hypotheses.risk_lenses:
                    eval_item = evaluated_dict.get(lens.id)
                    if not eval_item or eval_item.get("assessment_status") != "ASSESSED":
                        all_material_risks_assessed = False
                        unresolved_material_risks.append(lens.name)
        else:
            all_material_risks_assessed = True
            unresolved_material_risks = []

        is_exploratory = (precision == PrecisionLevel.EXPLORATORY)
        is_ach_conclusive = not getattr(ach_matrix, "is_inconclusive", True) if not is_exploratory else True

        core_evidence_gates_met = (
            not is_fail_closed
            and zero_coverage_debt
            and h0_search_met
            and has_h1_roots
            and has_h2_roots
            and has_h0_roots
            and has_h1_primary
            and has_h2_primary
            and has_h0_primary
            and has_primary_ratio
            and all_risk_searches_completed
            and (contract.execution_mode == ExecutionMode.LIVE)
        )

        contract_met = (core_evidence_gates_met and all_material_risks_assessed and is_ach_conclusive)

        # Canonical audit facts
        executed_queries_count = len(query_ledger) if query_ledger is not None else 0
        searched_classes_set = set()
        for c in validated_evidence_set.eligible_claims:
            if c.target_concept and c.target_concept in ontology.classes:
                searched_classes_set.add(c.target_concept)
            elif c.subject and c.subject in ontology.classes:
                searched_classes_set.add(c.subject)
        searched_classes_count = len(searched_classes_set)

        avg_conf = sum(c.confidence for c in validated_evidence_set.eligible_claims) / (len(validated_evidence_set.eligible_claims) or 1)
        reliability_score = round(avg_conf, 2) if validated_evidence_set.eligible_claims else 0.0
        total_claims_denom = len(validated_evidence_set.eligible_claims) + len(validated_evidence_set.rejected_claims)
        novelty_score = min(0.95, max(0.50, len(validated_evidence_set.provenance_clusters) / (total_claims_denom + 1)))
        calibration_score = 0.85 if is_ach_conclusive else 0.45

        common_audit_facts = {
            "counterevidence_searched": h0_search_attempted,
            "all_risk_searches_completed": all_risk_searches_completed,
            "all_material_risks_assessed": all_material_risks_assessed,
            "searched_classes_count": searched_classes_count,
            "executed_queries_count": executed_queries_count,
            "reliability_score": reliability_score,
            "novelty_score": novelty_score,
            "calibration_score": calibration_score,
            "unresolved_material_risks": tuple(unresolved_material_risks)
        }

        if contract_met:
            return GateDecision(
                is_stopping_allowed=True,
                synthesis_status="CONCLUSIVE_RECOMMENDATION",
                reason="All ontological, provenance, primary-source, and risk contract gates fully satisfied.",
                is_fail_closed=False,
                action_required="Publish Conclusive Recommendation",
                can_synthesize_conditional=False,
                **common_audit_facts
            )
        elif is_fail_closed:
            return GateDecision(
                is_stopping_allowed=False,
                synthesis_status="INSUFFICIENT_EVIDENCE_SAFETY_BLOCK",
                reason=fail_closed_reason or "FAIL_CLOSED",
                is_fail_closed=True,
                action_required="Halt: UNKNOWN_PRECISION_LEVEL. Categorical and conditional decisions strictly blocked.",
                can_synthesize_conditional=False,
                **common_audit_facts
            )
        elif core_evidence_gates_met and (not all_material_risks_assessed or not is_ach_conclusive):
            return GateDecision(
                is_stopping_allowed=False,
                synthesis_status="CONDITIONAL_RECOMMENDATION",
                reason=f"Core evidence gates satisfied; material risk gaps remain: {', '.join(unresolved_material_risks)}",
                is_fail_closed=False,
                action_required="Resolve material risk gaps prior to production rollout.",
                can_synthesize_conditional=True,
                **common_audit_facts
            )
        elif current_depth >= effective_max_depth:
            return GateDecision(
                is_stopping_allowed=False,
                synthesis_status="INSUFFICIENT_EVIDENCE_SAFETY_BLOCK",
                reason="Search reached mode depth limit with unmet contract gates.",
                is_fail_closed=False,
                action_required="Halt search at mode depth limit. Perform manual review.",
                can_synthesize_conditional=False,
                **common_audit_facts
            )
        elif not h0_search_met:
            msg = "Continue recursive pass to search for counterevidence and H0 null hypothesis."
            return GateDecision(
                is_stopping_allowed=False,
                synthesis_status="INSUFFICIENT_EVIDENCE_SAFETY_BLOCK",
                reason="Counterevidence / H0 search requirement unmet.",
                is_fail_closed=False,
                action_required=msg,
                can_synthesize_conditional=False,
                **common_audit_facts
            )
        elif not has_h1_primary:
            msg = f"High-precision contract requires at least {requirements.min_primary_roots_h1} verified primary source specifically for H1 (current: {validated_evidence_set.h1_primary_roots_count})"
            return GateDecision(
                is_stopping_allowed=False,
                synthesis_status="INSUFFICIENT_EVIDENCE_SAFETY_BLOCK",
                reason=msg,
                is_fail_closed=False,
                action_required=msg,
                can_synthesize_conditional=False,
                **common_audit_facts
            )
        elif not has_primary_ratio:
            msg = f"Contract requires primary source ratio >= {requirements.min_primary_ratio:.2f} (current: {validated_evidence_set.primary_source_ratio:.2f})"
            return GateDecision(
                is_stopping_allowed=False,
                synthesis_status="INSUFFICIENT_EVIDENCE_SAFETY_BLOCK",
                reason=msg,
                is_fail_closed=False,
                action_required=msg,
                can_synthesize_conditional=False,
                **common_audit_facts
            )
        else:
            msg = f"Resolve {len(validated_evidence_set.unresolved_coverage_debt)} debt items and contractual requirements"
            return GateDecision(
                is_stopping_allowed=False,
                synthesis_status="INSUFFICIENT_EVIDENCE_SAFETY_BLOCK",
                reason=f"Deficit in contract requirements (Coverage debt: {len(validated_evidence_set.unresolved_coverage_debt)})",
                is_fail_closed=False,
                action_required=msg,
                can_synthesize_conditional=False,
                **common_audit_facts
            )

    @classmethod
    def evaluate_evidence(
        cls,
        contract: Any,
        ontology: DynamicOntology,
        claims: Sequence[AtomicClaim],
        hypotheses: HypothesisSet,
        current_depth: int = 1,
        effective_max_depth: int = 3,
        query_ledger: Optional[List[Any]] = None,
        evaluated_risk_lenses: Optional[List[Dict[str, Any]]] = None
    ) -> ValidatedEvidenceSet:
        """
        Pure convenience orchestrator running validate_claims + evaluate_gate_decision.
        Returns a new immutable ValidatedEvidenceSet without mutating any attributes.
        """
        evidence_set = cls.validate_claims(
            contract=contract,
            ontology=ontology,
            claims=claims,
            hypotheses=hypotheses,
            current_depth=current_depth,
            effective_max_depth=effective_max_depth,
            query_ledger=query_ledger
        )

        from ach_engine import ACHHeuerEngine
        engine = ACHHeuerEngine()
        ach_matrix = engine.evaluate_matrix(hypotheses, evidence_set)

        if evaluated_risk_lenses is not None:
            ach_matrix.evaluated_risk_lenses = evaluated_risk_lenses

        gate_decision = cls.evaluate_gate_decision(
            contract=contract,
            ontology=ontology,
            hypotheses=hypotheses,
            validated_evidence_set=evidence_set,
            ach_matrix=ach_matrix,
            query_ledger=query_ledger,
            current_depth=current_depth,
            effective_max_depth=effective_max_depth
        )

        return evidence_set.replace_decision(gate_decision)
