# Results (hard subset) — 2026-11-05

Hard subset ([`data/hard`](data/hard)): each CV is built around one failure mode (`case:` rows below). A few fields are excluded per CV where the document does not settle them; see the gold rules in the README.

40 synthetic CVs. Scores are 0–100 (exact / fuzzy match rate, F1 for list fields). Overall = mean of the field scores.

| Model | Overall | Cost / 40 CVs | p50 latency | p95 latency | Errors |
|---|---|---|---|---|---|
| claude-opus-5.5 | **100.0** | $0.914 | 3.99 s | 5.09 s | 0 |
| claude-haiku-5.5 | **99.8** | $0.027 | 3.17 s | 4.32 s | 0 |
| claude-sonnet-5.5 | **99.8** | $0.450 | 2.95 s | 3.66 s | 0 |
| gemini-3.8-flash | **99.7** | $0.173 | 8.24 s | 18.59 s | 0 |
| gemini-3.1-pro | **98.9** | $0.973 | 13.34 s | 17.34 s | 0 |

## Per field

| Field | claude-opus-5.5 | claude-haiku-5.5 | claude-sonnet-5.5 | gemini-3.8-flash | gemini-3.1-pro |
|---|---|---|---|---|---|
| name | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |
| email | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |
| phone | 100.0 | 97.5 | 100.0 | 97.5 | 90.0 |
| location | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |
| current_title | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |
| years_experience | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |
| skills | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |
| languages | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |
| experience | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |
| experience_dates | 100.0 | 100.0 | 98.3 | 99.4 | 98.1 |
| education | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |

## Overall by document type, language and case

| Slice | claude-opus-5.5 | claude-haiku-5.5 | claude-sonnet-5.5 | gemini-3.8-flash | gemini-3.1-pro |
|---|---|---|---|---|---|
| PDF one-column | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |
| PDF three-column | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |
| PDF two-column | 100.0 | 100.0 | 99.3 | 100.0 | 100.0 |
| scanned PDF | 100.0 | 99.1 | 100.0 | 98.9 | 95.7 |
| lang: CA | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |
| lang: EN | 100.0 | 100.0 | 99.7 | 99.9 | 99.4 |
| lang: ES | 100.0 | 99.5 | 100.0 | 99.5 | 98.3 |
| case: ambiguous_dates | 100.0 | 100.0 | 98.8 | 100.0 | 100.0 |
| case: contact_page2 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |
| case: distractors | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |
| case: fax_scan | 100.0 | 97.7 | 100.0 | 100.0 | 97.7 |
| case: mixed_language | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |
| case: non_latin_name | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |
| case: personal_contact | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |
| case: phone_photo | 100.0 | 100.0 | 100.0 | 98.1 | 94.3 |
| case: rating_tables | 100.0 | 100.0 | 100.0 | 97.7 | 100.0 |
| case: three_column | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |

## List fields: precision / recall

| Field | claude-opus-5.5 | claude-haiku-5.5 | claude-sonnet-5.5 | gemini-3.8-flash | gemini-3.1-pro |
|---|---|---|---|---|---|
| skills | 100.0 / 100.0 | 100.0 / 100.0 | 100.0 / 100.0 | 100.0 / 100.0 | 100.0 / 100.0 |
| languages | 100.0 / 100.0 | 100.0 / 100.0 | 100.0 / 100.0 | 100.0 / 100.0 | 100.0 / 100.0 |
| experience | 100.0 / 100.0 | 100.0 / 100.0 | 100.0 / 100.0 | 100.0 / 100.0 | 100.0 / 100.0 |
| education | 100.0 / 100.0 | 100.0 / 100.0 | 100.0 / 100.0 | 100.0 / 100.0 | 100.0 / 100.0 |

## Judge

Job titles that fail the fuzzy match go to an LLM judge (`claude-opus-5.5`). Agreement with human labels on the spot check: **10/10**. Judge calls (spot check + scoring, cached per title pair): 10, cost $0.0191.


**Total API spend for this run: $2.56**
