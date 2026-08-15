---
name: adaptive-ontological-search
description: Adaptive Ontology-Driven Evidence Search Framework & Agentic Orchestrator (Version 2.1 Core). Integrates AutoSchemaKG, LightRAG dual-level retrieval, Skeptic Disproving Subagent, Grounded Atomic Claim Extraction, Richards Heuer Inconsistency ACH Engine, and Safety-Gated Synthesis.
---

# Adaptive Ontology-Driven Evidence Search 2.1 Core

## Overview & Purpose
This skill provides an advanced framework and agentic orchestrator for deep information discovery, evidence verification, and strategic analysis in complex domains.

Goal: Move beyond basic search to construct minimal sufficient ontologies, model information visibility, test competing hypotheses ($H_1, H_2, H_0$) with orthogonal risk lenses ($L_{risk}$), evaluate grounded atomic claims with quotes and locators, deduplicate root provenance, and stop when verified stopping criteria are met.

---

## Key Features (Version 2.1 Core)

1. **AutoSchemaKG & Coverage Debt Tracking**:
   - Dynamically induces domain classes, relations, and vocabulary on-the-fly.
   - Tracks `coverage_debt` and dynamically generates targeted follow-up queries across recursive search depths.

2. **Strict MOCK vs LIVE Execution Isolation**:
   - `LIVE_RETRIEVAL`: Ingests and extracts grounded atomic claims with `grounded_summary` (LLM-grounded segment), `verbatim_quote` (direct page extract when available), `source_url`, `locator`, and `retrieval_timestamp`.
   - `MOCK_SIMULATION`: Explicitly marks all simulation data with `UNVERIFIED_MOCK` status and blocks fabrication of fake primary sources.

3. **Richards Heuer ACH Engine (v2.1)**:
   - Evaluates weighted inconsistency penalties ($InconsistencyPenalty = \sum |score| \times Conf \times D_i \times w_{cluster}$).
   - **Root Provenance Clustering**: Collapses duplicate downstream reports sharing the same upstream origin wire into a single cluster with total weight $\le 1.0$.
   - **Minimum Corroboration Gate**: Hypotheses without positive corroboration ($SupportScore < \tau_{min}$) cannot win merely due to zero penalties.
   - **Orthogonal Risk Lenses**: Evaluates regulatory, licensing, and operational factors independently from technical hypotheses.

4. **Strict Safety-Gated Synthesis**:
   - Automatically blocks categorical architectural recommendations if ACH is `INCONCLUSIVE_EVIDENCE`, stopping rules are unmet, or execution ran in simulation mode.

---

## File Structure & References

```
.agents/skills/adaptive-ontological-search/
├── SKILL.md                          # Skill specification (V2.1 Core)
├── references/
│   ├── search_modes.md              # Search Mode Gate specifications
│   ├── evidence_schema.md           # Claim, Hypothesis, Evaluation JSON schemas
│   └── spark_gemini_integration.md  # PySpark + Dataproc + BigFrames guide
└── scripts/
    ├── config.py                    # Central model registry & execution mode config
    ├── models.py                    # V2.1 Data models (AtomicClaim, ACHMatrix, DynamicOntology, RiskLens)
    ├── ach_engine.py                # Richards Heuer ACH Inconsistency & Diagnosticity Engine
    ├── deep_research_adapter.py     # Grounded search & simulation adapter
    ├── orchestrator.py              # Legacy V1 Orchestrator
    ├── orchestrator_v2.py           # Ontological Search 2.1 Core Orchestrator
    ├── compare_v1_v2.py             # Side-by-side benchmark script
    ├── vc_due_diligence_orchestrator.py # Hardened VC diligence with synthetic demo tags
    ├── spark_gemini_pipeline.py     # PySpark distributed evidence pipeline
    └── main.py                      # CLI entrypoint (Runs V2.1 Core)
```

---

## Automated Test Suite

Run unit tests directly:
```bash
python3 -m unittest discover tests
```

---

## How to Run & Invoke

### 1. CLI Execution (Ontological Search 2.1 Core)
```bash
python3 .agents/skills/adaptive-ontological-search/scripts/main.py "Your research question here"
```

### 2. Comparative Benchmark Execution (V1 vs V2.1)
```bash
python3 .agents/skills/adaptive-ontological-search/scripts/compare_v1_v2.py "Your research question here"
```
