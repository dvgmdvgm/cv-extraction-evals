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

**Datasets** — two sets of fully synthetic CVs, no real person's data. Each CV is generated as JSON first and
then rendered, so the JSON *is* the gold label. They are scored and reported separately.

*Standard* — 40 clean CVs ([`data/cvs`](data/cvs)):

| | |
|---|---|
| Languages | 20 English, 20 Spanish |
| Formats | 14 PDF one-column, 14 PDF two-column (sidebar), 6 scanned PDF (image only, no text layer), 6 DOCX |
| Edge cases | no email (5), two phone numbers (5), year-only dates "2019 – present" (4), Spanish month abbreviations "ene. 2021", phones with and without country code, no headline (10), not currently employed (4) |

*Hard* — 40 CVs ([`data/hard`](data/hard), [generator](src/cv_evals/generate_hard.py)), each built around one
failure mode. All PDF; 10 are image-only scans.

| Case | CVs | What it looks like |
|---|---|---|
| Phone photo | 4 (+2) | printed page photographed on a desk: perspective, 2.5–5.5° rotation, uneven light, low contrast, blur, JPEG artefacts |
| Fax | 3 (+1) | bitonal, coarse vertical resolution, skew, speckles, a streak across the page |
| Rating tables | 4 | skills as dots / bars / squares in 1–3-column grids, languages as bars, experience as a table, experience and education in one table |
| Three columns | 4 | three narrow columns in four different section orders, contact in the left or right column |
| Contact on page 2 | 4 | two-page CV, email and phone only at the end of page 2, name in the footer of each page |
| Distractors | 4 | headshot, company logos (in one CV the company name exists only inside the logo), QR code, icons instead of labels, a referee's email and phone |
| Mixed language | 4 | Spanish CV with English titles, an all-Catalan CV, a Spanish CV with a Portuguese job and degree, an English CV with Spanish degrees |
| Ambiguous dates | 5 | overlapping jobs (two current), "Summer 2019" / "Autumn 2023 – Spring 2026", academic years "2018–19", month names in four languages in one CV, DD/MM/YYYY |
| Non-Latin names | 4 | Ukrainian (Cyrillic) x2, Greek, Chinese, each with a Latin transliteration |
| Personal contact | 4 | work and personal emails / phones side by side, the personal one usually second |

(+n): CVs of another case that are also scanned (a rating table and a three-column CV photographed, the
distractor CV with photo and QR code faxed).

**Gold rules for the hard set.** Where a document does not settle a field, the gold follows a written rule
or the field is not scored for that CV; models are never scored against a guess. The rules are stored in each
gold file and applied by the scorer:

1. Names, titles, companies, institutions and locations are gold as written, in the CV's language and script.
2. Several emails or phones: the one marked personal / private, otherwise the first one listed (this is in the
   prompt).
3. A name shown in two scripts: the Latin form is gold; the native form, or both with one in brackets, also
   count. Another transliteration is wrong.
4. Seasons and academic years ("Summer 2019", "2018–19") give no month: the gold is year-only and any month
   in the right year counts. Month-precise dates in the same CV stay exact.
5. "03/04/2023" in a Spanish CV is April: the same CV has days above 12 ("16/10/2021"), which settles DD/MM.
6. Two current jobs and no headline: `current_title` is not scored for that CV. Languages drawn as bars with no
   CEFR level: `languages` is not scored for that CV. One field in each of two CVs is excluded this way.
7. Years of experience are always stated in the CV's profile line.

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

Both datasets were run on 2026-11-05 with the same prompt, all five models. Overall = mean of the 11 field scores.

### Standard (40 clean CVs)

<!-- results:start -->
_Run of 2026-11-05, 40 CVs. Full breakdown in [RESULTS.md](RESULTS.md)._

| Model | Overall | Cost / 40 CVs | p50 latency | p95 latency | Errors |
|---|---|---|---|---|---|
| gemini-3.8-flash | **100.0** | $0.141 | 7.16 s | 9.43 s | 0 |
| gemini-3.1-pro | **100.0** | $0.901 | 12.67 s | 15.71 s | 0 |
| claude-haiku-5.5 | **100.0** | $0.025 | 2.89 s | 4.27 s | 0 |
| claude-sonnet-5.5 | **100.0** | $0.414 | 2.81 s | 3.74 s | 0 |
| claude-opus-5.5 | **100.0** | $0.833 | 3.76 s | 5.19 s | 0 |
<!-- results:end -->

### Hard (40 CVs built around failure modes)

<!-- results-hard:start -->
_Run of 2026-11-05, 40 CVs. Full breakdown in [RESULTS-hard.md](RESULTS-hard.md)._

| Model | Overall | Cost / 40 CVs | p50 latency | p95 latency | Errors |
|---|---|---|---|---|---|
| claude-opus-5.5 | **100.0** | $0.914 | 3.99 s | 5.09 s | 0 |
| claude-haiku-5.5 | **99.8** | $0.027 | 3.17 s | 4.32 s | 0 |
| claude-sonnet-5.5 | **99.8** | $0.450 | 2.95 s | 3.66 s | 0 |
| gemini-3.8-flash | **99.7** | $0.173 | 8.24 s | 18.59 s | 0 |
| gemini-3.1-pro | **98.9** | $0.973 | 13.34 s | 17.34 s | 0 |
<!-- results-hard:end -->

The fields that separate the models on the hard set (all other fields: 100 for every model):

| Field | Opus 5.5 | Sonnet 5.5 | Haiku 5.5 | Gemini 3.8 Flash | Gemini 3.1 Pro |
|---|---|---|---|---|---|
| phone | 100 | 100 | 97.5 | 97.5 | 90.0 |
| experience_dates | 100 | 98.3 | 100 | 99.4 | 98.1 |
| overall on the 10 scanned CVs | 100 | 100 | 99.1 | 98.9 | 95.7 |

## Findings

From the two 2026-11-05 runs (per-field, per-layout and per-case tables in [RESULTS.md](RESULTS.md) and
[RESULTS-hard.md](RESULTS-hard.md)):

1. **The standard set is saturated: all five models score 100.** Every field, every layout (two-column,
   scanned, DOCX), both languages, zero errors. On clean synthetic CVs this eval cannot rank Gemini against
   Claude on accuracy.
2. **The hard set barely moves them: 98.9–100.** Opus 5.5 is the only model with a perfect score on both sets;
   Gemini 3.1 Pro is last at 98.9. Three columns, rating grids, experience and education in one table,
   contact details only on page 2, logos, a QR code, a referee's phone number, Catalan and Portuguese
   sections, DD/MM dates, month names in four languages, overlapping jobs, Cyrillic, Greek and Chinese names,
   and work-vs-personal contacts: **every model got every one of these right.** No model translated a title,
   picked the referee's phone, or took the work email over the personal one. The layout traps that break
   classic parsers do not break current multimodal LLMs.
3. **What does break them is pixels: digits on degraded scans.** 9 of the 10 field errors on the hard set are on the
   10 image-only CVs, and they are misread digits, not misunderstood structure:
   - Gemini 3.1 Pro read 4 of the 10 scanned phone numbers wrong: `+44 7700 900539` for `900639`,
     `652671329` for `662671329`, `648 250 599` for `648 280 599`, and on the fax `662 41 79 97` for
     `682 41 79 97`. It also read a start date `abr. 2019` as 2016.
   - Claude Haiku 5.5 made the same fax error (`662` for `682`); this is the most degraded digit in the set
     and is hard for a human too. Gemini 3.8 Flash read `671455234` as `671465234` on a photographed CV and one
     `2020-06` as `2020-05`.
   - Claude Sonnet and Opus read every digit on every scan correctly.
   A wrong digit in a phone number is the worst kind of extraction error: it looks valid and nobody checks it.
4. **Sonnet 5.5's one error is a refusal to guess.** For "Summer 2026 – present" and "Autumn 2023 – Spring
   2026" it returned no dates at all (start and end null, which also marks the old job as current). The prompt
   asks for `YYYY` when only the year is known, and the gold accepts any month of the right year, so this is
   scored wrong. The other four models returned the year (or a month in it).
5. **Claude Haiku 5.5 is the cheapest by a wide margin**: $0.025 per 40 standard CVs and $0.027 per 40 hard
   ones, about 1/6 of Gemini 3.8 Flash and 1/36 of Gemini 3.1 Pro. It scores 99.8 on the hard set, level with
   Sonnet at 1/17 of the price. Per 1,000 CVs: about $0.65 vs $3.80 vs $23.
6. **Claude is two to four times faster than Gemini.** p50 2.8–4.0 s for all three Claude models vs 7–8 s for
   Flash and 13 s for Pro on both sets; on the hard set Flash's p95 is 18.6 s. One run from one location
   (Spain), so treat the latency gap as indicative, not as a benchmark of either API.
7. **The two providers spend tokens in opposite places.** Claude reads a one-page CV PDF as about 3,400 input
   tokens (page image plus text) vs about 790 for Gemini, but writes fewer output tokens: about 360 for Sonnet
   and Opus vs 780 for Flash and 1,750 for Pro, whose thinking tokens are billed as output. This is why Opus at
   twice Sonnet's list price ($0.83) still costs slightly less than Gemini 3.1 Pro ($0.90).
8. **Normalisation made the phone score.** All five models copied phone numbers as printed
   (`(+34) 686502464`, `+44 (0)7700 900132`, `659 16 23 74`). A naive string comparison against the E.164
   gold would report close to 0% phone accuracy for every model; after normalisation the only phone errors
   left are the misread digits above. Metric design matters as much as the model.
9. **The judge was validated but never needed.** Claude Opus 5.5 agreed with all 10 human labels on the spot
   check, but every extracted job title, Catalan and Portuguese ones included, matched the gold title, so the
   judge made no scoring calls.

The standard set was re-run on 2026-11-05 after the prompt gained the "personal email / phone" rule; against
the earlier run of the same day it showed no regression (all fields 100 in both). The previous Gemini-only run
(2026-10-08, [`results/2026-10-08.json`](results/2026-10-08.json)) gave the same Gemini scores and costs within
a few percent, so run-to-run variation on the standard set is small.

### What would make it discriminate further

The hard set shows where the remaining errors are: degraded images, not document structure. Next steps, in
order of expected payoff:

- **More and worse scans:** lower resolution, heavier JPEG compression, handwriting or a stamp over text,
  real phone-camera photos of printed synthetic CVs. Report the phone and date fields on scans separately.
- **Repeated runs:** with one run per model, 1–2 errors per 40 CVs is within noise. Five runs per model would
  turn "Pro misread 4 phones" into a rate with an interval.
- **Contact details only in a QR code or an image**, a page break in the middle of a job, and
  "2019–2021, 2022–present" at one company (needs a written gold rule first).

## Reproduce

Needs Python 3.12 and [uv](https://docs.astral.sh/uv/). Each provider runs only if its key is set; missing ones are skipped and listed in the report.

```bash
export GEMINI_API_KEY=... ANTHROPIC_API_KEY=...
uv run evals run                 # all 5 models x 40 CVs -> results/<date>.json, RESULTS.md, this README's table
uv run evals run --dataset hard  # the hard subset -> results/<date>-hard.json, RESULTS-hard.md, its own table
```

The exact spend is printed at the end. A full five-model run cost $2.33 on the standard set and $2.56 on the
hard set (judge included). If your Anthropic
key is not scoped to a workspace, also set `ANTHROPIC_WORKSPACE_ID`. Useful variants:

```bash
uv run evals run --limit 3                               # smoke test on 3 CVs, cents
uv run evals run --models claude-haiku-5.5,gemini-3.8-flash    # a subset
uv run evals run --fake                                  # offline dry run, no keys, no cost
uv run pytest                                            # unit tests (what CI runs)
uv run --extra render evals generate                     # re-render the standard dataset
uv run --extra render evals generate --dataset hard      # re-render the hard subset (needs Windows fonts: Arial, YaHei)
```

### Regression mode: evals as CI tests for prompts

```bash
uv run evals run --baseline results/2026-11-05.json
uv run evals run --dataset hard --baseline results/2026-11-05-hard.json
```

Exits non-zero if any field of any model drops more than 2 points against the baseline. Each dataset has its
own baseline; a baseline from the other dataset is refused. Change the prompt in
[`schema.py`](src/cv_evals/schema.py), run this, and the diff is a number per field rather than an impression.

## Layout

```
src/cv_evals/
  schema.py      Pydantic schema + the extraction prompt (shared by all providers)
  generate.py    synthetic gold JSON -> PDF / scanned PDF / DOCX (standard set)
  generate_hard.py  hard subset: three columns, rating tables, graphics, phone-photo and fax scans
  providers.py   one thin adapter per provider, price table, offline fake provider
  scoring.py     normalisation + per-field metrics (unit-tested)
  judge.py       LLM judge for titles + human-agreement spot check
  report.py      aggregation, RESULTS.md, regression comparison
  cli.py         `evals run` / `evals generate`
```

Plain Python: no LangChain or other frameworks, about 1,600 lines including both dataset generators.

## Limitations

- Synthetic CVs are cleaner than real ones. The hard set adds photos, rating tables and odd layouts, but every
  CV still comes from one generator with a handful of fonts and templates. The phone photos and faxes are
  simulated degradations of a render, not photographs of paper.
- The hard set has 3–5 CVs per case, so a per-case score is a smoke signal, not a rate.
- One run per model, no repeated sampling, so differences of a point or two are noise. The regression
  threshold is 2 points for this reason.
- The judge is one of the models under test. It only sees title pairs, never the CV, and its agreement with
  human labels is reported, but 10 items is a sanity check, not a calibration.
- Prices are hard-coded list prices ([providers.py](src/cv_evals/providers.py)): Gemini checked on 2026-10-07
  (Flash at its introductory price, valid until 2026-12-31), Claude checked on 2026-11-05 on Anthropic's pricing
  page. Haiku 5.5 is priced at its rate for prompts up to 100k tokens; every CV here is far below that.
- OpenAI models are not part of this comparison.
