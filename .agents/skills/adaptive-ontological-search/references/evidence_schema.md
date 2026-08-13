# Evidence & Claims Schema Reference

## Atomic Unit of Analysis: Claims, Not Documents
In the Adaptive Ontology-Driven Evidence Search framework, raw documents are decomposed into atomic **Claims**. A single document may contain factual claims, PR hype, projections, and third-party quotes. Evaluating the document as a whole leads to bias; each claim must be evaluated individually.

---

## Claim Data Model

```json
{
  "id": "claim_1029",
  "statement": "Company X has acquired 50,000 custom FPGA accelerator chips from Vendor Y",
  "entity": "Company X",
  "event_date": "2026-01-10",
  "publication_date": "2026-01-14",
  "source_url": "https://example.com/sec_filing_q1",
  "source_type": "regulatory_filing",
  "primary_or_secondary": "primary",
  "independence_group": "provenance_cluster_alpha",
  "evidence_status": "confirmed",
  "supports_hypothesis": "H1",
  "contradicts_hypothesis": "H0",
  "alternative_interpretation": "Chips acquired for legacy infrastructure rather than new AI project",
  "confidence": 0.92
}
```

---

## 8-Factor Evidence Criticism Criteria

1. **Relevance**: Direct alignment with the research question and target hypothesis.
2. **Reliability**: Primary source vs secondary reporting; source track record.
3. **Independence**: Provenance cluster identification; verifying whether multiple articles trace back to a single PR press release.
4. **Specificity**: Presence of verifiable dates, part numbers, quantities, or financial figures.
5. **Recency**: Timeliness of evidence relative to the target time frame.
6. **Novelty**: Information gain relative to existing knowledge base.
7. **Actionability**: Impact on decision-making or strategic choice.
8. **Visibility Bias Risk**: Potential distortion caused by public relations, marketing hype, or selective disclosure.
