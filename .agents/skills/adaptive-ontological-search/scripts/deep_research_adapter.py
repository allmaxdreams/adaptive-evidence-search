"""
Deep Research & Retrieval Adapter (v2.1 Core).
Implements a strict, fail-closed LIVE adapter with real Google Gemini Search Grounding REST interface,
granular segment-level provenance parsing (groundingSupports -> segment -> chunk),
and transparent, honest MOCK simulation.

Rules:
1. In LIVE mode:
   - Connects to Google Gemini API with Google Search Grounding.
   - If API key is missing or invalid, or API returns empty text / no grounding citations,
     it FAILS CLOSED (raises RuntimeError). Never generates placeholder URIs.
   - Parses groundingSupports to map each grounded text segment to its exact source URI and chunk.
2. In MOCK mode:
   - Generates clearly marked UNVERIFIED_MOCK fixtures without claiming real primary sources.
"""

import asyncio
import datetime
import hashlib
import json
import os
import re
import urllib.request
import urllib.error
from typing import List, Dict, Any, Optional

from models import QueryPortfolio, QueryItem, ExecutionMode
from config import config, DEFAULT_PRO_MODEL
from evidence_policy import check_primary_authority, PRIMARY_AUTHORITY_REGISTRY


class GeminiDeepResearchAdapter:
    """
    Adapter layer for executing multi-step Deep Research.
    Guarantees strict mode isolation, fail-closed live execution,
    and granular groundingSupports segment extraction.
    """

    @staticmethod
    def is_primary_source(uri: str, domain: str, title: str = "") -> bool:
        """
        Classifies whether a source URL/domain qualifies as a Primary Authority:
        - Exact normalized domain registry match or verified subdomain authority.
        - Strictly rejects domain/path/title spoofing (e.g. notgithub.com, malicious.example/docs/fake).
        """
        is_primary, _, _ = check_primary_authority(uri, domain)
        return is_primary

    def __init__(self, model_name: str = DEFAULT_PRO_MODEL, api_key: Optional[str] = None):
        self.model_name = model_name
        self.api_key = api_key or config.gemini_api_key
        self.is_live = config.is_live

    async def execute_deep_research(
        self,
        research_question: str,
        portfolio: QueryPortfolio,
        current_depth: int = 1,
        execution_mode: Optional[ExecutionMode] = None
    ) -> Dict[str, Any]:
        """
        Executes search queries across portfolio. Fails closed if LIVE mode is requested without valid credentials.
        """
        timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
        
        is_live = (execution_mode == ExecutionMode.LIVE) if execution_mode is not None else self.is_live

        if is_live:
            if not self.api_key or self.api_key.strip() == "" or self.api_key.lower() == "dummy":
                raise RuntimeError(
                    "LIVE_RETRIEVAL execution failed-closed: Valid GEMINI_API_KEY required. "
                    "Refusing to fabricate live evidence. "
                    "To run in simulation mode, set EXECUTION_MODE=MOCK."
                )
            mode_str = "LIVE_RETRIEVAL"
        else:
            mode_str = "MOCK_SIMULATION"
        
        print(f"[DeepResearch | {self.model_name}] Depth {current_depth} ({mode_str}) for: '{research_question}'")

        raw_documents = []
        query_errors = {}
        for query in portfolio.queries:
            try:
                docs = await self._fetch_or_simulate_document(query, timestamp, is_live=is_live)
                if isinstance(docs, list):
                    raw_documents.extend(docs)
                else:
                    raw_documents.append(docs)
            except Exception as e:
                query_errors[query.query_id] = str(e)

        return {
            "status": "partial_failure" if query_errors else "success",
            "execution_mode": mode_str,
            "research_question": research_question,
            "current_depth": current_depth,
            "documents_retrieved": len(raw_documents),
            "raw_documents": raw_documents,
            "query_errors": query_errors
        }

    async def _fetch_or_simulate_document(self, query: QueryItem, timestamp: str, is_live: Optional[bool] = None) -> List[Dict[str, Any]]:
        """
        Builds raw document payloads. Performs real Gemini Grounding REST calls in LIVE mode.
        """
        eff_live = is_live if is_live is not None else self.is_live
        if eff_live:
            return await self._execute_live_gemini_grounding(query, timestamp)
        else:
            # MOCK Mode: Explicitly labeled simulation fixture
            concept = query.target_concept or "ArchitectureComponent"
            return [{
                "query_id": query.query_id,
                "query": query.text,
                "strategy": query.strategy,
                "target_hypothesis": query.target_hypothesis,
                "target_concept": concept,
                "target_risk_lens_id": query.target_risk_lens_id,
                "is_mock": True,
                "source_title": f"[SIMULATION FIXTURE] Mock Analysis on {concept}",
                "source_url": "simulation://local/mock_dataset",
                "source_domain": "simulation.local",
                "upstream_origin_id": f"mock_origin_{concept.lower()}",
                "locator": f"mock_section_{query.strategy.lower()}",
                "retrieval_timestamp": timestamp,
                "document_text": (
                    f"SIMULATION FIXTURE for concept '{concept}' under strategy '{query.strategy}'. "
                    f"Target: {query.target_hypothesis}. This payload is an UNVERIFIED test fixture."
                )
            }]

    async def _execute_live_gemini_grounding(self, query: QueryItem, timestamp: str) -> List[Dict[str, Any]]:
        """
        Executes a real REST call to Gemini API with Google Search Grounding tool enabled.
        Strictly parses groundingSupports to attribute text segments to their exact source chunks.
        Fails closed on any error, missing text, or absent grounding citations.
        """
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model_name}:generateContent?key={self.api_key}"
        
        payload = {
            "contents": [{
                "parts": [{"text": f"Search and summarize factual technical documentation, benchmarks, or regulatory filings for: '{query.text}'"}]
            }],
            "tools": [{"googleSearch": {}}]
        }
        
        headers = {"Content-Type": "application/json"}
        req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")

        try:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(None, lambda: urllib.request.urlopen(req, timeout=15))
            res_data = json.loads(response.read().decode("utf-8"))
            return self.parse_grounded_response(res_data, query, timestamp)
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="ignore")
            raise RuntimeError(
                f"LIVE_RETRIEVAL failed-closed: Gemini API returned HTTP {e.code}: {e.reason}. "
                f"Details: {err_body[:200]}. Refusing to fabricate live evidence."
            )
        except Exception as e:
            raise RuntimeError(
                f"LIVE_RETRIEVAL failed-closed: Error connecting to Gemini Grounding: {e}. "
                f"Refusing to fabricate live evidence."
            )

    def parse_grounded_response(self, res_data: Dict[str, Any], query: QueryItem, timestamp: str) -> List[Dict[str, Any]]:
        """
        Granular parser for Gemini Search Grounding API response.
        Extracts grounded segments via groundingSupports -> groundingChunks mapping.
        """
        candidate = res_data.get("candidates", [{}])[0]
        full_text = candidate.get("content", {}).get("parts", [{}])[0].get("text", "")
        grounding_meta = candidate.get("groundingMetadata", {})
        chunks = grounding_meta.get("groundingChunks", [])
        supports = grounding_meta.get("groundingSupports", [])

        # FAIL CLOSED: If no text, no chunks, or no segment-level groundingSupports
        if not full_text or not chunks:
            raise RuntimeError(
                f"LIVE_RETRIEVAL failed-closed: Gemini API returned no grounded search citations for query '{query.text}'. "
                f"Refusing to manufacture unverified citations."
            )

        if not supports:
            raise RuntimeError(
                f"LIVE_RETRIEVAL failed-closed: Gemini API response lacked segment-level 'groundingSupports'. "
                f"Refusing to fabricate unverified blanket attributions across chunks for query '{query.text}'."
            )

        grounded_docs = []

        # Parse each supported segment with its specific grounding chunks
        for i, supp in enumerate(supports):
            segment_info = supp.get("segment", {})
            start_idx = segment_info.get("startIndex", 0)
            end_idx = segment_info.get("endIndex", len(full_text))
            seg_text = full_text[start_idx:end_idx].strip()

            if not seg_text:
                continue

            chunk_indices = supp.get("groundingChunkIndices", [])
            # FAIL-SAFE: Do NOT default to chunk 0 if no chunk indices are provided
            if not chunk_indices:
                continue

            # Provenance Cluster: Multiple chunks supporting the SAME LLM segment belong to ONE evidence cluster
            norm_seg = re.sub(r'[\W_]+', ' ', seg_text.lower()).strip()
            seg_hash = hashlib.sha256(norm_seg.encode('utf-8')).hexdigest()[:12]
            segment_origin = f"seg_origin_{seg_hash}"

            for chunk_idx in chunk_indices:
                if chunk_idx < len(chunks):
                    web_src = chunks[chunk_idx].get("web", {})
                    uri = web_src.get("uri")
                    title = web_src.get("title") or f"Grounded Source for '{query.text[:30]}'"
                    
                    if uri:
                        domain = urllib.parse.urlparse(uri).netloc.lower() or "web.grounded"
                        is_primary, auth_type, status_reason = check_primary_authority(uri, domain)
                        
                        grounded_docs.append({
                            "query_id": query.query_id,
                            "query": query.text,
                            "strategy": query.strategy,
                            "target_hypothesis": query.target_hypothesis,
                            "target_concept": query.target_concept,
                            "target_risk_lens_id": query.target_risk_lens_id,
                            "is_mock": False,
                            "is_llm_grounded_summary": True,
                            "is_primary_source": is_primary,
                            "primary_authority_type": auth_type,
                            "primary_status_reason": status_reason,
                            "source_title": title,
                            "source_url": uri,
                            "source_domain": domain,
                            "upstream_origin_id": segment_origin,
                            "locator": f"segment_{i+1}_chunk_{chunk_idx}",
                            "retrieval_timestamp": timestamp,
                            "grounded_summary": seg_text,
                            "document_text": seg_text
                        })

        if not grounded_docs:
            raise RuntimeError(
                f"LIVE_RETRIEVAL failed-closed: No valid web URLs found in grounding metadata for query '{query.text}'."
            )

        return grounded_docs
