# Results — 2026-11-05

40 synthetic CVs. Scores are 0–100 (exact / fuzzy match rate, F1 for list fields). Overall = mean of the field scores.

| Model | Overall | Cost / 40 CVs | p50 latency | p95 latency | Errors |
|---|---|---|---|---|---|
| gemini-3.8-flash | **100.0** | $0.141 | 7.16 s | 9.43 s | 0 |
| gemini-3.1-pro | **100.0** | $0.901 | 12.67 s | 15.71 s | 0 |
| claude-haiku-5.5 | **100.0** | $0.025 | 2.89 s | 4.27 s | 0 |
| claude-sonnet-5.5 | **100.0** | $0.414 | 2.81 s | 3.74 s | 0 |
| claude-opus-5.5 | **100.0** | $0.833 | 3.76 s | 5.19 s | 0 |

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

## Overall by document type, language and case

| Slice | gemini-3.8-flash | gemini-3.1-pro | claude-haiku-5.5 | claude-sonnet-5.5 | claude-opus-5.5 |
|---|---|---|---|---|---|
| DOCX | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |
| PDF one-column | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |
| PDF two-column | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |
| scanned PDF | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |
| lang: EN | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |
| lang: ES | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |
| case: no_email | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |
| case: no_headline | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |
| case: not_currently_employed | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |
| case: two_phones | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |
| case: year_only_dates | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |

## List fields: precision / recall

| Field | gemini-3.8-flash | gemini-3.1-pro | claude-haiku-5.5 | claude-sonnet-5.5 | claude-opus-5.5 |
|---|---|---|---|---|---|
| skills | 100.0 / 100.0 | 100.0 / 100.0 | 100.0 / 100.0 | 100.0 / 100.0 | 100.0 / 100.0 |
| languages | 100.0 / 100.0 | 100.0 / 100.0 | 100.0 / 100.0 | 100.0 / 100.0 | 100.0 / 100.0 |
| experience | 100.0 / 100.0 | 100.0 / 100.0 | 100.0 / 100.0 | 100.0 / 100.0 | 100.0 / 100.0 |
| education | 100.0 / 100.0 | 100.0 / 100.0 | 100.0 / 100.0 | 100.0 / 100.0 | 100.0 / 100.0 |

## Judge

Job titles that fail the fuzzy match go to an LLM judge (`claude-opus-5.5`). Agreement with human labels on the spot check: **10/10**. Judge calls (spot check + scoring, cached per title pair): 10, cost $0.0188.


**Total API spend for this run: $2.33**
