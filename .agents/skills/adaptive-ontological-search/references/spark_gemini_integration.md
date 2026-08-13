# Spark Gemini Integration Architecture

## Overview
When scaling the **Adaptive Ontology-Driven Evidence Search** framework to massive datasets (terabyte/petabyte scale web crawls, patent archives, news streams, corporate filings), individual LLM calls become a bottleneck. 

Integrating **Spark Gemini** (PySpark on Google Cloud Dataproc + BigQuery BigFrames + Gemini API) enables distributed, high-throughput evidence extraction and graph construction.

---

## Technical Architecture

```
[Raw GCS Web Crawls / Archives]
           │
           ▼
[Google Cloud Dataproc (PySpark Cluster)]
  ├── Partition Data across Worker Nodes
  ├── Run Gemini 3.6 Flash via `pandas_udf` / `dataproc-ml`
  └── Extract Atomic Claims & Source Provenance Metadata
           │
           ▼
[BigQuery Evidence Store & GraphFrames]
  ├── PageRank & Independence Clustering
  └── Query via BigQuery BigFrames (`bigframes.ml.llm`)
           │
           ▼
[Agentic Orchestrator - Pro Model Synthesis]
```

---

## Key Components

### 1. PySpark `pandas_udf` with Gemini Batch API
Distributes raw text blocks to worker nodes, where vectorized Python UDFs call Gemini 3.6 Flash in parallel batches. This achieves up to 100x throughput compared to sequential API calls.

### 2. PySpark GraphFrames for Provenance & Independence
Calculates connected components and graph paths across documents:
- **News Republishing Detection**: Identifies whether 50 news articles originate from a single wire service press release.
- **PageRank for Evidence Strength**: Ranks claims based on primary source citations and cross-verification links.

### 3. BigQuery BigFrames Integration
Enables data scientists and the agentic orchestrator to interact with massive evidence graphs using Pandas-like syntax:
```python
import bigframes.pandas as bpd
from bigframes.ml.llm import GeminiTextGenerator

# Load BigQuery evidence store
df = bpd.read_gbq("my_project.evidence_store.claims_graph")

# Filter high-confidence primary evidence
primary_claims = df[df["primary_or_secondary"] == "primary"]

# Run Gemini model directly in BigQuery
model = GeminiTextGenerator(model_name="gemini-3.6-pro")
synthesis = model.predict(primary_claims["statement"], prompt="Synthesize key findings:")
```
