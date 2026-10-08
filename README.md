# CV extraction evals

How well do current LLMs turn a CV (PDF or DOCX) into structured JSON, what does it cost, and how fast is it?
This repo measures it instead of eyeballing it: a labelled dataset, per-field metrics, an LLM judge that is
itself validated, and a regression gate that fails CI when a prompt or model change makes things worse.

## Why

Document extraction (invoices, contracts, claims, CVs) is the most common enterprise LLM use case, and the
one where "looks right in the demo" fails quietly in production: a phone number without its country code, a
job that ends "2019 – present" read as ended, a two-column layout read in the wrong order. Those are field-level
errors, so this eval scores every field separately and slices the results by document type and language.

## What is measured

**Dataset** — 40 fully synthetic CVs ([`data/cvs`](data/cvs)), no real person's data. Each CV is generated as
JSON first and then rendered, so the JSON *is* the gold label:

| | |
|---|---|
| Languages | 20 English, 20 Spanish |
| Formats | 14 PDF one-column, 14 PDF two-column (sidebar), 6 scanned PDF (image only, no text layer), 6 DOCX |
| Edge cases | no email (5), two phone numbers (5), year-only dates "2019 – present" (4), Spanish month abbreviations "ene. 2021", phones with and without country code, no headline (10), not currently employed (4) |

**Fields** — name, email, phone, location, current_title, years_experience, skills, languages, experience
(company + title), experience dates, education ([schema](src/cv_evals/schema.py)).

**Metrics** ([scoring.py](src/cv_evals/scoring.py))
- Exact match after normalisation: email, phone (E.164), years of experience, dates (`YYYY-MM`, current job = null).
- Fuzzy match ≥ 0.9 (accent- and case-insensitive): names, locations, companies, institutions, titles.
- Precision / recall / F1 for list fields: skills, languages (name + CEFR level), experience, education.
- **LLM-as-judge** only for job titles that fail the fuzzy match ("Ingeniera de Datos" vs "Data Engineer").
  Before its verdicts count, the judge is checked against 10 hand-labelled title pairs
  ([`data/judge_spotcheck.json`](data/judge_spotcheck.json)) and the agreement is printed in the report.
- Cost from token usage × list price, p50 / p95 latency per call.

**Models** — Gemini 3.8 Flash and 3.1 Pro, Claude Haiku 4.5 and Sonnet 5.5, GPT-6 Luna and GPT-6.1 Sol. Same prompt,
native structured output on each provider, PDFs sent as documents (scans included), DOCX sent as extracted text.

## Results

> **This run covers Gemini only.** The Claude (Haiku 4.5, Sonnet 5.5) and OpenAI (GPT-6 Luna, GPT-6.1 Sol)
> adapters are included and tested against mocked HTTP, but have not been run yet: no API keys were
> available. Setting `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` and re-running adds them to this table.

<!-- results:start -->
_Run of 2026-10-08, 40 CVs. Full breakdown in [RESULTS.md](RESULTS.md)._

| Model | Overall | Cost / 40 CVs | p50 latency | p95 latency | Errors |
|---|---|---|---|---|---|
| gemini-3.8-flash | **100.0** | $0.136 | 6.95 s | 11.92 s | 0 |
| gemini-3.1-pro | **100.0** | $0.876 | 13.66 s | 18.95 s | 0 |
<!-- results:end -->

## Findings

From the 2026-10-08 Gemini run (per-field, per-layout and per-language tables in [RESULTS.md](RESULTS.md)):

1. **This dataset is saturated for current Gemini models.** Both scored 100 on every field, every layout
   (two-column, scanned, DOCX) and both languages: Spanish month abbreviations, "present" end dates, year-only
   dates and CVs with two phone numbers included. On clean synthetic CVs the eval cannot separate these
   models any more; it needs harder cases (real-world scan noise, tables, photos, mixed-language CVs).
2. **Flash matches Pro at 1/6 of the cost and half the latency.** $0.14 vs $0.88 per 40 CVs ($3.40 vs
   $21.90 per 1,000), p50 7.0 s vs 13.7 s. Since quality is the same here, Flash is the obvious pick for
   this task.
3. **Normalisation made the phone score.** Both models copied every phone number exactly as printed
   (`(+34) 686502464`, `+44 (0)7700 900132`, `659 16 23 74`). Not one of the 80 matched the E.164 gold string
   verbatim, so a naive string comparison would have reported 0% phone accuracy. After normalisation all
   80 were correct. Metric design matters as much as the model.
4. **The judge was validated but never needed.** Gemini 3.1 Pro agreed with all 10 human labels on the
   spot check, but every extracted job title passed the fuzzy match, so the judge made no scoring calls.
   Models copied titles verbatim and did not translate them.

## Reproduce

Needs Python 3.12 and [uv](https://docs.astral.sh/uv/). Each provider runs only if its key is set; missing ones are skipped and listed in the report.

```bash
export GEMINI_API_KEY=... ANTHROPIC_API_KEY=... OPENAI_API_KEY=...
uv run evals run                 # all 6 models x 40 CVs -> results/<date>.json, RESULTS.md, this README's table
```

The exact spend is printed at the end. The Gemini-only run cost $1.03 (judge included); with all six models,
budget about $5. Useful variants:

```bash
uv run evals run --limit 3                               # smoke test on 3 CVs, cents
uv run evals run --models claude-haiku-4.5,gpt-6-luna    # a subset
uv run evals run --fake                                  # offline dry run, no keys, no cost
uv run pytest                                            # unit tests (what CI runs)
uv run --extra render evals generate                     # re-render the dataset
```

### Regression mode: evals as CI tests for prompts

```bash
uv run evals run --baseline results/2026-10-08.json
```

Exits non-zero if any field of any model drops more than 2 points against the baseline. Change the prompt in
[`schema.py`](src/cv_evals/schema.py), run this, and the diff is a number per field rather than an impression.

## Layout

```
src/cv_evals/
  schema.py      Pydantic schema + the extraction prompt (shared by all providers)
  generate.py    synthetic gold JSON -> PDF / scanned PDF / DOCX
  providers.py   one thin adapter per provider, price table, offline fake provider
  scoring.py     normalisation + per-field metrics (unit-tested)
  judge.py       LLM judge for titles + human-agreement spot check
  report.py      aggregation, RESULTS.md, regression comparison
  cli.py         `evals run` / `evals generate`
```

Plain Python: no LangChain or other frameworks, about 1,000 lines including the dataset generator.

## Limitations

- Synthetic CVs are cleaner than real ones (consistent fonts, no photos, no tables of skills with ratings).
  The scanned PDFs are degraded renders, not real phone photos.
- One run per model, no repeated sampling, so differences of a point or two are noise. The regression
  threshold is 2 points for this reason.
- The judge is one of the models under test. It only sees title pairs, never the CV, and its agreement with
  human labels is reported, but 10 items is a sanity check, not a calibration.
- Prices are hard-coded list prices checked on 2026-10-07 ([providers.py](src/cv_evals/providers.py)).
