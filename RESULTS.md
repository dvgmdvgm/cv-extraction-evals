# Results — 2026-11-05

40 synthetic CVs. Scores are 0–100 (exact / fuzzy match rate, F1 for list fields). Overall = mean of the field scores.

| Model | Overall | Cost / 40 CVs | p50 latency | p95 latency | Errors |
|---|---|---|---|---|---|
| gemini-3.8-flash | **100.0** | $0.129 | 7.07 s | 9.48 s | 0 |
| gemini-3.1-pro | **100.0** | $0.878 | 13.07 s | 17.57 s | 0 |
| claude-haiku-5.5 | **100.0** | $0.024 | 2.9 s | 3.82 s | 0 |
| claude-sonnet-5.5 | **100.0** | $0.412 | 2.99 s | 5.0 s | 0 |
| claude-opus-5.5 | **100.0** | $0.820 | 3.83 s | 4.9 s | 0 |

## Per field

| Field | gemini-3.8-flash | gemini-3.1-pro | claude-haiku-5.5 | claude-sonnet-5.5 | claude-opus-5.5 |
|---|---|---|---|---|---|
| name | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |
| email | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |
| phone | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |
| location | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |
| current_title | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |
| years_experience | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |
| skills | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |
| languages | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |
| experience | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |
| experience_dates | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |
| education | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |

## Overall by document type and language

| Slice | gemini-3.8-flash | gemini-3.1-pro | claude-haiku-5.5 | claude-sonnet-5.5 | claude-opus-5.5 |
|---|---|---|---|---|---|
| DOCX | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |
| PDF one-column | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |
| PDF two-column | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |
| scanned PDF | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |
| lang: EN | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |
| lang: ES | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |

## List fields: precision / recall

| Field | gemini-3.8-flash | gemini-3.1-pro | claude-haiku-5.5 | claude-sonnet-5.5 | claude-opus-5.5 |
|---|---|---|---|---|---|
| skills | 100.0 / 100.0 | 100.0 / 100.0 | 100.0 / 100.0 | 100.0 / 100.0 | 100.0 / 100.0 |
| languages | 100.0 / 100.0 | 100.0 / 100.0 | 100.0 / 100.0 | 100.0 / 100.0 | 100.0 / 100.0 |
| experience | 100.0 / 100.0 | 100.0 / 100.0 | 100.0 / 100.0 | 100.0 / 100.0 | 100.0 / 100.0 |
| education | 100.0 / 100.0 | 100.0 / 100.0 | 100.0 / 100.0 | 100.0 / 100.0 | 100.0 / 100.0 |

## Judge

Job titles that fail the fuzzy match go to an LLM judge (`claude-opus-5.5`). Agreement with human labels on the spot check: **10/10**. Judge calls (spot check + scoring, cached per title pair): 10, cost $0.0200.


**Total API spend for this run: $2.28**
