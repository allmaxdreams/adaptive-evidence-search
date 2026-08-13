---
name: adaptive-ontological-search
description: Adaptive Ontology-Driven Evidence Search Framework & Agentic Orchestrator. Integrates Gemini Deep Research, Model Tiering (Pro/Flash), 3 Search Modes (Direct Lookup, Structured Search, Recursive Evidence Search), and Spark Gemini distributed extraction.
---

# Adaptive Ontology-Driven Evidence Search

## Overview & Purpose
This skill provides an advanced framework and agentic orchestrator for deep information discovery, evidence verification, and strategic analysis in complex domains (technology R&D, competitive intelligence, geopolitical developments, supply chain vulnerabilities, covert maneuvers).

Goal: Move beyond basic search to construct minimal sufficient ontologies, model information visibility (traces & anti-traces), test competing hypotheses ($H_1, H_2, H_0, H_V$), evaluate claims rather than documents, group source independence, and stop when stopping rules are met.

---

## Key Features

1. **Search Mode Gate**:
   - **Mode 1 (Direct Lookup)**: Fact lookup from authoritative sources.
   - **Mode 2 (Structured Search)**: Multi-source trends, 2-3 hypotheses, light ontology.
   - **Mode 3 (Recursive Evidence Search)**: Hidden phenomena, dual ontologies (Domain & Information Visibility), 4 competing hypotheses ($H_1, H_2, H_0, H_V$), direct/indirect/counter/anti-evidence traces, query portfolio, discovery vs. verification split, and recursive stopping rules.

2. **Model Tiering Strategy**:
   - `Gemini 3.6 Pro`: Orchestrator, Search Mode Gate, Research Planner, Hypothesis Agent, Evidence Critic, Evaluator, Synthesizer.
   - `Gemini 3.6 Flash / Flash Lite`: Ontology & Visibility Agent, Query Portfolio Agent, Claim Extractor, Source Collectors.

3. **Gemini Deep Research Layer**:
   - Autonomous multi-hop research engine for web grounding, primary source discovery, and disproving query runs.

4. **Spark Gemini Integration**:
   - PySpark on Google Cloud Dataproc + BigQuery BigFrames (`bigframes.ml.llm`) for high-throughput distributed evidence extraction and GraphFrames provenance clustering.

---

## File Structure & References

```
.agents/skills/adaptive-ontological-search/
├── SKILL.md                          # Main Skill instructions
├── references/
│   ├── search_modes.md              # Search Mode Gate specifications
│   ├── evidence_schema.md           # Claim, Hypothesis, Evaluation JSON schemas
│   └── spark_gemini_integration.md  # PySpark + Dataproc + BigFrames guide
└── scripts/
    ├── models.py                    # Pydantic schemas
    ├── deep_research_adapter.py     # Gemini Deep Research layer interface
    ├── orchestrator.py              # Main Agentic Orchestrator
    ├── spark_gemini_pipeline.py     # PySpark distributed evidence pipeline
    └── main.py                      # CLI entrypoint
```

---

## How to Run

### Local Agentic Orchestrator
To execute the evidence search orchestrator on a research query:

```bash
python3 .agents/skills/adaptive-ontological-search/scripts/main.py "Identify hidden supply chain vulnerabilities and undisclosed FPGA R&D initiatives in next-gen autonomous drone platforms"
```

### Spark Gemini Pipeline (Dataproc / BigQuery)
To submit a distributed extraction job on GCP Dataproc:

```bash
gcloud dataproc jobs submit pyspark .agents/skills/adaptive-ontological-search/scripts/spark_gemini_pipeline.py \
    --cluster=my-spark-cluster \
    --region=us-central1 \
    -- "gs://my-evidence-bucket/raw_crawls/*.txt" "my_bq_dataset.evidence_store"
```

---

## Workflow Rules for Agents

1. **Gate First**: Always run Search Mode Gate before building ontologies or graph models. Do not over-engineer simple fact queries.
2. **Evaluate Claims, Not Documents**: Decompose findings into atomic `Claim` instances with explicit `independence_group` tags.
3. **Seek Counterevidence**: Never complete a Mode 3 search without executing dedicated disproving queries designed to refute $H_1$.
4. **Enforce Stopping Rules**: Terminate research loops when novelty score drops below threshold or primary claims are verified by $\ge 3$ independent primary evidence lines.
