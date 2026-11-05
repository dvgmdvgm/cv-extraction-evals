"""Aggregate per-CV rows into model scores, render RESULTS.md, and compare against a baseline."""

import math
import statistics
from collections import defaultdict
from pathlib import Path

from .scoring import FIELDS, LIST_FIELDS

REGRESSION_POINTS = 2.0
README_START, README_END = "<!-- results:start -->", "<!-- results:end -->"


def slice_name(meta):
    return {"docx": "DOCX", "scanned": "scanned PDF"}.get(meta["format"], "PDF " + meta["layout"].replace("_col", "-column"))


def p95(xs):
    return sorted(xs)[math.ceil(0.95 * len(xs)) - 1]  # nearest rank


def aggregate(rows):
    """rows: [{id, meta, scores, pr, latency, cost, error}] for one model."""
    pct = lambda xs: round(100 * statistics.mean(xs), 1)
    # A field excluded for a CV by its gold rules is missing from that row and averaged over the rest.
    fields = {f: pct([r["scores"][f] for r in rows if f in r["scores"]]) for f in FIELDS}
    by_slice = defaultdict(list)
    for r in rows:
        overall = statistics.mean(r["scores"].values())
        by_slice[slice_name(r["meta"])].append(overall)
        by_slice["lang: " + r["meta"]["lang"].upper()].append(overall)
        for e in r["meta"]["edge_cases"]:
            by_slice["case: " + e].append(overall)
    ok = [r["latency"] for r in rows if not r["error"]]
    return dict(
        n=len(rows),
        errors=sum(bool(r["error"]) for r in rows),
        overall=round(statistics.mean(fields.values()), 1),
        fields=fields,
        precision_recall={f: dict(p=pct([r["pr"][f][0] for r in rows if f in r["pr"]]),
                                  r=pct([r["pr"][f][1] for r in rows if f in r["pr"]])) for f in LIST_FIELDS},
        by_slice={k: pct(v) for k, v in sorted(by_slice.items())},
        cost_usd=round(sum(r["cost"] for r in rows), 4),
        latency_p50_s=round(statistics.median(ok), 2) if ok else None,
        latency_p95_s=round(p95(ok), 2) if ok else None,
    )


def table(header, rows):
    lines = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    return "\n".join(lines + ["| " + " | ".join(str(c) for c in r) + " |" for r in rows])


def summary_table(res):
    ms = res["models"]
    return table(["Model", "Overall", f"Cost / {res['n_cvs']} CVs", "p50 latency", "p95 latency", "Errors"],
                 [[m, f"**{s['overall']}**", f"${s['cost_usd']:.3f}", f"{s['latency_p50_s']} s", f"{s['latency_p95_s']} s",
                   s["errors"]] for m, s in sorted(ms.items(), key=lambda kv: -kv[1]["overall"])])


def markdown(res):
    ms = res["models"]
    names = sorted(ms, key=lambda m: -ms[m]["overall"])
    slices = sorted({k for m in names for k in ms[m]["by_slice"]}, key=lambda s: (s.startswith("case"), s.startswith("lang"), s))
    j = res["judge"]
    hard = res.get("dataset") == "hard"
    out = [f"# Results{' (hard subset)' if hard else ''} — {res['date']}", ""]
    if res["dry_run"]:
        out += ["> **Dry run with the offline fake provider.** Numbers only prove the pipeline works.", ""]
    if hard:
        out += ["Hard subset ([`data/hard`](data/hard)): each CV is built around one failure mode (`case:` rows below). "
                "A few fields are excluded per CV where the document does not settle them; see the gold rules in the README.", ""]
    out += [f"{res['n_cvs']} synthetic CVs. Scores are 0–100 (exact / fuzzy match rate, F1 for list fields). "
            "Overall = mean of the field scores.", "", summary_table(res), ""]
    if res["skipped"]:
        out += ["Skipped providers: " + ", ".join(f"{p} ({why})" for p, why in res["skipped"].items()), ""]
    out += ["## Per field", "", table(["Field"] + names, [[f] + [ms[m]["fields"][f] for m in names] for f in FIELDS]), "",
            "## Overall by document type, language and case", "",
            table(["Slice"] + names, [[s] + [ms[m]["by_slice"].get(s, "–") for m in names] for s in slices]), "",
            "## List fields: precision / recall", "",
            table(["Field"] + names, [[f] + [f"{ms[m]['precision_recall'][f]['p']} / {ms[m]['precision_recall'][f]['r']}"
                                             for m in names] for f in LIST_FIELDS]), "",
            "## Judge", ""]
    if j:
        out += [f"Job titles that fail the fuzzy match go to an LLM judge (`{j['model']}`). "
                f"Agreement with human labels on the spot check: **{j['agree']}/{j['n']}**. "
                f"Judge calls (spot check + scoring, cached per title pair): {j['calls']}, cost ${j['cost_usd']:.4f}.", ""]
        out += [f"- disagreement: `{d['reference']}` vs `{d['extracted']}` — human {d['human']}, judge {d['judge']}"
                for d in j["disagreements"]]
    else:
        out += ["No judge available: titles were scored with fuzzy matching only."]
    out += ["", f"**Total API spend for this run: ${res['total_cost_usd']:.2f}**", ""]
    return "\n".join(out)


def results_md(dataset):
    return "RESULTS.md" if dataset == "standard" else f"RESULTS-{dataset}.md"


def update_readme(res, path=Path("README.md")):
    """Replace the dataset's results block in the README with the summary table."""
    ds = res.get("dataset", "standard")
    start, end = (README_START, README_END) if ds == "standard" else (f"<!-- results-{ds}:start -->", f"<!-- results-{ds}:end -->")
    text = path.read_text(encoding="utf-8")
    if start not in text:
        return
    head, rest = text.split(start, 1)
    tail = rest.split(end, 1)[1]
    md = results_md(ds)
    block = f"\n_Run of {res['date']}, {res['n_cvs']} CVs. Full breakdown in [{md}]({md})._\n\n{summary_table(res)}\n"
    path.write_text(head + start + block + end + tail, encoding="utf-8")


def regressions(baseline, current, points=REGRESSION_POINTS):
    """Fields that dropped by more than `points` for a model present in both runs.
    Comparing runs on different datasets is meaningless, so it raises."""
    b_ds, c_ds = baseline.get("dataset", "standard"), current.get("dataset", "standard")
    if b_ds != c_ds:
        raise ValueError(f"baseline is a {b_ds!r} run, this is a {c_ds!r} run: pass a baseline of the same dataset")
    out = []
    for model, cur in current["models"].items():
        base = baseline["models"].get(model)
        for f in FIELDS if base else []:
            drop = base["fields"][f] - cur["fields"][f]
            if drop > points:
                out.append(f"{model}.{f}: {base['fields'][f]} -> {cur['fields'][f]} (-{drop:.1f})")
    return out
