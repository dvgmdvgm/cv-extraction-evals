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

**Models** — a Gemini vs Claude comparison: Gemini 3.8 Flash and 3.1 Pro, Claude Haiku 5.5, Sonnet 5.5 and
Opus 5.5. Same prompt, native structured output on each provider, PDFs sent as documents (scans included), DOCX
sent as extracted text.

## Results

<!-- results:start -->
_Run of 2026-11-05, 40 CVs. Full breakdown in [RESULTS.md](RESULTS.md)._

| Model | Overall | Cost / 40 CVs | p50 latency | p95 latency | Errors |
|---|---|---|---|---|---|
| gemini-3.8-flash | **100.0** | $0.129 | 7.07 s | 9.48 s | 0 |
| gemini-3.1-pro | **100.0** | $0.878 | 13.07 s | 17.57 s | 0 |
| claude-haiku-5.5 | **100.0** | $0.024 | 2.9 s | 3.82 s | 0 |
| claude-sonnet-5.5 | **100.0** | $0.412 | 2.99 s | 5.0 s | 0 |
| claude-opus-5.5 | **100.0** | $0.820 | 3.83 s | 4.9 s | 0 |
<!-- results:end -->

## Findings

From the 2026-11-05 run, all five models on the same day (per-field, per-layout and per-language tables in
[RESULTS.md](RESULTS.md)):

1. **The dataset is saturated: all five models scored 100.** Every field, every layout (two-column, scanned,
   DOCX), both languages, zero errors — Spanish month abbreviations, "present" end dates, year-only dates and
   two-phone CVs included. On clean synthetic CVs this eval cannot rank Gemini against Claude on accuracy.
   What it does separate is cost and latency, below. The next step is a harder subset (see
   [What would make it discriminate](#what-would-make-it-discriminate)).
2. **Claude Haiku 5.5 is the cheapest by a wide margin: $0.024 per 40 CVs**, about 1/5 of Gemini 3.8 Flash
   ($0.129) and 1/36 of Gemini 3.1 Pro ($0.878). Per 1,000 CVs: about $0.60 vs $3.20 vs $22.
3. **Claude is about twice as fast as Gemini Flash.** p50 2.9–3.8 s for all three Claude models vs 7.1 s for
   Flash and 13.1 s for Pro; p95 at most 5.0 s for Claude vs 9.5 s and 17.6 s. One run from one location
   (Spain), so treat the latency gap as indicative, not as a benchmark of either API.
4. **The two providers spend tokens in opposite places.** Claude reads a CV PDF as about 3,360 input tokens
   (page image plus text) vs about 770 for Gemini, but writes fewer output tokens: about 350 for Sonnet and
   Opus vs 710 for Flash and 1,700 for Pro, whose thinking tokens are billed as output. This is why Opus at
   twice Sonnet's list price ($0.82) still costs slightly less than Gemini 3.1 Pro ($0.88) here.
5. **Normalisation made the phone score.** All five models copied every phone number as printed
   (`(+34) 686502464`, `+44 (0)7700 900132`, `659 16 23 74`). None of the 200 extracted numbers matched the
   E.164 gold string verbatim, so a naive string comparison would report 0% phone accuracy for every model.
   After normalisation all were correct. Metric design matters as much as the model.
6. **The judge was validated but never needed.** Claude Opus 5.5 agreed with all 10 human labels on the spot
   check, but every extracted job title matched the gold title exactly, so the judge made no scoring calls.
   No model translated titles.

The previous Gemini-only run (2026-10-08, [`results/2026-10-08.json`](results/2026-10-08.json)) gave the same
Gemini scores and costs within a few percent, so run-to-run variation on this dataset is small.

### What would make it discriminate

Not built yet. A hard subset of about 40 more CVs, each case chosen because it breaks a specific field:

- **Real scan noise:** phone photos of printed CVs (skew, perspective, shadows, JPEG artefacts, low DPI),
  fax-quality bitonal scans, a stamp or handwritten note over text.
- **Tables:** skills as rating grids (dots, bars, 1–5 stars), experience laid out as a table with merged
  cells, education and experience in one table.
- **Photos and graphics:** headshot in the header, logos instead of company names, icons instead of labels
  for email / phone / location, contact details only in a QR code or an image.
- **Mixed language:** Spanish CV with English job titles, Catalan or Portuguese sections, English CV with
  Spanish university names, titles that must not be translated.
- **Layout traps:** three columns, text boxes read out of order, a page break mid-job, headers and footers
  repeated on each page, a two-page CV with the contact block on page 2.
- **Ambiguous facts:** overlapping jobs, freelance periods, gaps, "2019–2021, 2022–present" at one company,
  dates in `MM/YYYY` vs `DD/MM/YYYY`, phone numbers without country code in a non-Spanish CV.

## Reproduce

Needs Python 3.12 and [uv](https://docs.astral.sh/uv/). Each provider runs only if its key is set; missing ones are skipped and listed in the report.

```bash
export GEMINI_API_KEY=... ANTHROPIC_API_KEY=...
uv run evals run                 # all 5 models x 40 CVs -> results/<date>.json, RESULTS.md, this README's table
```

The exact spend is printed at the end. The full five-model run cost $2.28 (judge included). If your Anthropic
key is not scoped to a workspace, also set `ANTHROPIC_WORKSPACE_ID`. Useful variants:

```bash
uv run evals run --limit 3                               # smoke test on 3 CVs, cents
uv run evals run --models claude-haiku-5.5,gemini-3.8-flash    # a subset
uv run evals run --fake                                  # offline dry run, no keys, no cost
uv run pytest                                            # unit tests (what CI runs)
uv run --extra render evals generate                     # re-render the dataset
```

### Regression mode: evals as CI tests for prompts

```bash
uv run evals run --baseline results/2026-11-05.json
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
- Prices are hard-coded list prices ([providers.py](src/cv_evals/providers.py)): Gemini checked on 2026-10-07
  (Flash at its introductory price, valid until 2026-12-31), Claude checked on 2026-11-05 on Anthropic's pricing
  page. Haiku 5.5 is priced at its rate for prompts up to 100k tokens; every CV here is far below that.
- OpenAI models are not part of this comparison.
