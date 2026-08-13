---
name: adaptive-ontological-search
description: Adaptive Ontology-Driven Evidence Search Framework & Agentic Orchestrator (Version 2.0). Integrates AutoSchemaKG, LightRAG dual-level retrieval, Skeptic Disproving Subagent, Claimify Atomic Claim Extraction, and Analysis of Competing Hypotheses (ACH) Matrix.
---

# Adaptive Ontology-Driven Evidence Search 2.0

## Overview & Purpose
This skill provides an advanced framework and agentic orchestrator for deep information discovery, evidence verification, and strategic analysis in complex domains (AI Agent architectures, technology R&D, competitive intelligence, geopolitical developments, supply chain vulnerabilities, covert maneuvers).

Goal: Move beyond basic search to construct minimal sufficient ontologies, model information visibility (traces & anti-traces), test competing hypotheses ($H_1, H_2, H_0, H_V$), evaluate claims rather than documents, group source independence, and stop when stopping rules are met.

---

## Key Features (Version 2.0)

1. **AutoSchemaKG (Dynamic Domain Ontology Induction)**:
   - Dynamically induces domain classes, relations, and vocabulary on-the-fly from unstructured initial retrieval without hardcoded static schemas.
   - Validated via SHACL/OWL semantic constraints.

2. **LightRAG Dual-Level Retrieval Paradigm**:
   - **Fine-grained Level**: Entity and relationship extraction for direct fact verification ($H_1$).
   - **Coarse-grained Level**: Community detection and thematic synthesis for macro trend discovery ($H_V$).

3. **Skeptic Subagent (Targeted Disproving Search)**:
   - Executes disproving search queries specifically tailored to refute $H_1$ and test $H_0$ (null hypothesis/prompt wrappers) and $H_V$ (marketing hype filter).

4. **Claimify Protocol (Atomic Claim Extraction)**:
   - Decomposes findings into atomic `(Subject, Predicate, Object)` claim tuples tagged with `source_domain` and `independence_group` clusters.

5. **ACH Consistency Matrix (Analysis of Competing Hypotheses)**:
   - Evaluates each atomic claim against $H_1, H_2, H_0, H_V$ with systematic consistency ratings (+1 supporting, -1 contradicting, 0 neutral) to derive an empirical winning hypothesis.

---

## File Structure & References

```
.agents/skills/adaptive-ontological-search/
├── SKILL.md                          # Main Skill instructions (V2.0)
├── references/
│   ├── search_modes.md              # Search Mode Gate specifications
│   ├── evidence_schema.md           # Claim, Hypothesis, Evaluation JSON schemas
│   └── spark_gemini_integration.md  # PySpark + Dataproc + BigFrames guide
└── scripts/
    ├── models.py                    # V2 Data models (AtomicClaim, ACHMatrix, DynamicOntology)
    ├── deep_research_adapter.py     # Gemini Deep Research adapter
    ├── orchestrator.py              # Legacy V1 Orchestrator
    ├── orchestrator_v2.py           # Ontological Search 2.0 Orchestrator
    ├── compare_v1_v2.py             # Side-by-side benchmark script
    ├── spark_gemini_pipeline.py     # PySpark distributed evidence pipeline
    └── main.py                      # CLI entrypoint (Runs V2.0 by default)
```

---

## How to Run & Invoke

### 1. Mention in Chat / IDE Prompt
Mention the skill name `@adaptive-ontological-search` or tell the agent:
> *"Проведи adaptive-ontological-search для [Запитання]"*

### 2. CLI Execution (Ontological Search 2.0)
```bash
python3 .agents/skills/adaptive-ontological-search/scripts/main.py "Your research question here"
```

### 3. Comparative Benchmark Execution (V1 vs V2)
```bash
python3 .agents/skills/adaptive-ontological-search/scripts/compare_v1_v2.py "Your research question here"
```

