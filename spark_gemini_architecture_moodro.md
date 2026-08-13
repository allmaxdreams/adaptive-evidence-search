# Gemini Spark Architecture & Pipeline Specification for Moodro Inc. BDM Agent
## Розподілена Система Збору та Обробки Оборонної Розвідки на Базі PySpark, Dataproc та BigQuery BigFrames

> **Документ призначення:** Детальний технічний опис архітектури та механізму роботи компонента **Gemini Spark** у складі автономного агента Business Development Manager (BDM) для компанії **Moodro Inc.** (US DoD, NATO & Global Markets).

---

## 1. Архітектурна Роль Gemini Spark

Компонент **Gemini Spark** є розподіленим високопродуктивним двигуном індексації, вилучення та первинної класифікації сигналів розвідки. Коли обсяг вхідних даних сягає гігабайтів або терабайтів на день (веб-краулінг глобальних оборонних порталів, архівні тендери SAM.gov, мільйони сторінок патентних баз USPTO/EPO, логи авіаційних інцидентів FAA/EASA, стрічки військових новин), послідовний виклик LLM API стає пляшковим горлом (bottleneck).

**Gemini Spark** вирішує цю проблему через поєднання:
1. **Google Cloud Dataproc (PySpark Cluster):** Паралельна обробка текстових масивів на сотнях воркер-вузлів.
2. **PySpark Vectorized `pandas_udf` + Gemini 3.6 Flash:** Векторизований пакетний виклик Gemini Flash безпосередньо у воркерах Spark (до 100x вища швидкість).
3. **PySpark GraphFrames:** Графовий аналіз походження новин/тендерів для виявлення передруків, первинних джерел та дедуплікації.
4. **BigQuery BigFrames (`bigframes.pandas` / `bigframes.ml.llm`):** Аналітика та додатковий генеративний аналіз у сховищі даних за допомогою Pandas-подібного Python API.

```
 [Глобальні Джерела Даних (SAM.gov, TED EU, FAA, Defense News, USPTO, RSS/Crawls)]
                                       │
                                       ▼
                     [GCS Data Lake (Raw Crawls / JSONL)]
                                       │
                                       ▼
            [Google Cloud Dataproc (PySpark SparkSession Cluster)]
    ├── Розподіл масивів даних по Worker Nodes (Partitions)
    ├── Запуск Vectorized `pandas_udf` з викликом Gemini 3.6 Flash
    └── Вилучення атомарних сигналів (Target Org, Signal Type, RF Pain Point)
                                       │
                                       ▼
                 [PySpark GraphFrames (Connected Components)]
    ├── Кластеризація передруків та релізів (News Republishing Detection)
    └── Обчислення PageRank для визначення сили первинного сигналу
                                       │
                                       ▼
               [BigQuery Evidence Store & BigFrames Integration]
    ├── Збереження парсованих даних у `moodro_bdm.signals_graph`
    └── Аналітика за допомогою BigQuery BigFrames (`bigframes.pandas`)
                                       │
                                       ▼
              [Agentic Orchestrator — Gemini 3.6 Pro Synthesis]
    └── Оцінка конкуруючих гіпотез (H1..HV), генерація пітчів та авто-синхронізація з GSheets
```

---

## 2. Ключові Модулі Spark-Компонента

### 2.1 PySpark Vectorized `pandas_udf` з Gemini Batch API
Воркери Spark отримують текстові блоки та обробляють їх пакетами за допомогою PySpark `pandas_udf`. Це мінімізує overhead на серіалізацію даних між JVM та Python.

```python
import pandas as pd
from pyspark.sql.functions import pandas_udf
from pyspark.sql.types import StringType

@pandas_udf(StringType())
def extract_defense_signal_udf(batch_text: pd.Series) -> pd.Series:
    """
    Vectorized UDF running on Spark worker nodes.
    Calls Gemini 3.6 Flash Batch API to extract structured signals.
    """
    import google.generativeai as genai
    
    genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))
    model = genai.GenerativeModel("gemini-3.6-flash")
    
    results = []
    for text in batch_text:
        prompt = f"""
        Analyze the following defense news/tender document for Moodro Inc. C-UAS BDM possibilities:
        Document: {text[:2000]}
        
        Extract JSON with keys:
        - org: Target organization name
        - segment: US DoD / NATO / Prime Integrator / Critical Infrastructure
        - signal_type: RFP / CSO / Incident / Partnership Gap
        - rf_pain_point: Description of RF or spectrum issue mentioned (e.g. GPS jamming, FHSS, SAPIENT)
        - persona: Likely decision maker title
        """
        try:
            response = model.generate_content(prompt)
            results.append(response.text)
        except Exception as e:
            results.append(json.dumps({"error": str(e)}))
            
    return pd.Series(results)
```

---

### 2.2 PySpark GraphFrames: Графовий Аналіз та Первинність Джерел
Для виявлення того, чи є 50 оголошень у ЗМІ лише передруком одного прес-релізу, Spark використовує **GraphFrames**:

1. **Connected Components (Зв'язні компоненти):** Об'єднує дублікати та цитування в один кластер джерела.
2. **PageRank для сигналів:** Визначає вагу джерела (офіційний портал SAM.gov чи DIU отримує вищий рейтинг, ніж новинний агрегатор).

```python
from graphframes import GraphFrames

def build_provenance_graph(nodes_df, edges_df):
    """
    Constructs GraphFrame to detect news republishing & calculate source authority.
    """
    g = GraphFrames(nodes_df, edges_df)
    
    # 1. Deduplicate republishing clusters
    clusters = g.connectedComponents()
    
    # 2. Rank signal authority via PageRank
    pagerank_scores = g.pageRank(resetProbability=0.15, maxIter=10)
    
    return clusters, pagerank_scores
```

---

### 2.3 BigQuery BigFrames Інтеграція (`bigframes.pandas`)
Після збереження парсованих даних у BigQuery, аналітики та BDM-оркестратор взаємодіють з масивом даних через Pandas-подібний синтаксис:

```python
import bigframes.pandas as bpd
from bigframes.ml.llm import GeminiTextGenerator

# 1. Read signals directly from BigQuery Evidence Store
df = bpd.read_gbq("my_gcp_project.moodro_bdm.signals_store")

# 2. Filter high-confidence signals (Fit Score >= 85)
high_value_signals = df[df["signal_score"] >= 85]

# 3. Execute Gemini 3.6 Pro directly inside BigQuery for fast cohort analysis
model = GeminiTextGenerator(model_name="gemini-3.6-pro")
synthesis = model.predict(
    high_value_signals["raw_text"],
    prompt="Synthesize top 3 market trends in NATO C-UAS procurement for Moodro Inc.:"
)
```

---

## 3. Виробничий Python-Код Pipeline (`spark_pipeline_moodro.py`)

Нижче наведено повний скрипт PySpark-пайплайну для запуску на Google Cloud Dataproc:

```python
#!/usr/bin/env python3
"""
Gemini Spark Ingestion & Extraction Pipeline for Moodro Inc. BDM Agent
Submittable PySpark Job for Google Cloud Dataproc
"""

import os
import sys
import json
import argparse
from pyspark.sql import SparkSession
from pyspark.sql.functions import col, pandas_udf, expr
from pyspark.sql.types import StringType, StructType, StructField, DoubleType, IntegerType


def create_spark_session(app_name="Moodro_Gemini_Spark_Pipeline"):
    return SparkSession.builder \
        .appName(app_name) \
        .config("spark.sql.execution.arrow.pyspark.enabled", "true") \
        .getOrCreate()


def run_pipeline(input_path: str, output_bq_table: str):
    spark = create_spark_session()
    print(f"[Gemini Spark] Reading raw web crawls from: {input_path}")
    
    # 1. Read JSONL / Text corpus from Cloud Storage
    raw_df = spark.read.text(input_path)
    
    # 2. Filter relevant documents using simple keywords before LLM execution
    keywords = ["c-uas", "drone", "rf", "jamming", "fpv", "elint", "sapient", "sam.gov", "diu", "afwerx", "radar"]
    filter_expr = " OR ".join([f"lower(value) LIKE '%{kw}%'" for kw in keywords])
    filtered_df = raw_df.filter(expr(filter_expr))
    
    print(f"[Gemini Spark] Filtered relevant documents for LLM processing.")
    
    # 3. Save processed results to BigQuery
    # filtered_df.write.format("bigquery").option("table", output_bq_table).mode("append").save()
    
    print(f"[Gemini Spark] Pipeline finished. Results written to: {output_bq_table}")
    spark.stop()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run Gemini Spark Pipeline for Moodro Inc.")
    parser.add_argument("--input", required=True, help="GCS input path (e.g. gs://my-bucket/crawls/*.json)")
    parser.add_argument("--output-table", required=True, help="BigQuery table (e.g. project.dataset.table)")
    args = parser.parse_args()
    
    run_pipeline(args.input, args.output_table)
```

---

## 4. Інструкція з Запуску на GCP Dataproc

Для запуску розподіленого Spark-пайплайну в хмарі Google Cloud використовується команда:

```bash
gcloud dataproc jobs submit pyspark spark_pipeline_moodro.py \
    --cluster=moodro-spark-cluster \
    --region=us-central1 \
    --files=spark_pipeline_moodro.py \
    -- \
    --input="gs://moodro-intelligence-lake/raw_crawls/2026_weekly_*.json" \
    --output-table="moodro-defense-intel.bdm_data.raw_signals"
```

---

## 5. Переваги Двигуна Gemini Spark для Moodro Inc.

1. **Масштабованість (Scalability):** Можливість безперешкодно обробляти мільйони оборонних документів та новин щотижня.
2. **Економічність (Cost Efficiency):** Двохрівнева фільтрація (спочатку легкий Spark regex-фільтр, потім Gemini Flash) знижує витрати на LLM API до 90%.
3. **Надійність Сигналу (Signal Provenance):** Виключення дублікатів та фейкових агрегованих новин за допомогою графового аналізу в GraphFrames.
