# Results — 2026-10-08

40 synthetic CVs. Scores are 0–100 (exact / fuzzy match rate, F1 for list fields). Overall = mean of the field scores.

| Model | Overall | Cost / 40 CVs | p50 latency | p95 latency | Errors |
|---|---|---|---|---|---|
| gemini-3.8-flash | **100.0** | $0.136 | 6.95 s | 11.92 s | 0 |
| gemini-3.1-pro | **100.0** | $0.876 | 13.66 s | 18.95 s | 0 |

Skipped providers: anthropic (ANTHROPIC_API_KEY not set), openai (OPENAI_API_KEY not set)

## Per field

| Field | gemini-3.8-flash | gemini-3.1-pro |
|---|---|---|
| name | 100.0 | 100.0 |
| email | 100.0 | 100.0 |
| phone | 100.0 | 100.0 |
| location | 100.0 | 100.0 |
| current_title | 100.0 | 100.0 |
| years_experience | 100.0 | 100.0 |
| skills | 100.0 | 100.0 |
| languages | 100.0 | 100.0 |
| experience | 100.0 | 100.0 |
| experience_dates | 100.0 | 100.0 |
| education | 100.0 | 100.0 |

## Overall by document type and language

| Slice | gemini-3.8-flash | gemini-3.1-pro |
|---|---|---|
| DOCX | 100.0 | 100.0 |
| PDF one-column | 100.0 | 100.0 |
| PDF two-column | 100.0 | 100.0 |
| scanned PDF | 100.0 | 100.0 |
| lang: EN | 100.0 | 100.0 |
| lang: ES | 100.0 | 100.0 |

## List fields: precision / recall

| Field | gemini-3.8-flash | gemini-3.1-pro |
|---|---|---|
| skills | 100.0 / 100.0 | 100.0 / 100.0 |
| languages | 100.0 / 100.0 | 100.0 / 100.0 |
| experience | 100.0 / 100.0 | 100.0 / 100.0 |
| education | 100.0 / 100.0 | 100.0 / 100.0 |

## Judge

Job titles that fail the fuzzy match go to an LLM judge (`gemini-3.1-pro`). Agreement with human labels on the spot check: **10/10**. Judge calls (spot check + scoring, cached per title pair): 10, cost $0.0199.


**Total API spend for this run: $1.03**
