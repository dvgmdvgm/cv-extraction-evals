"""Single entry point.

    evals run [--baseline results/<date>.json] [--models a,b] [--limit N] [--fake]
    evals generate        # re-render the synthetic dataset (needs: uv sync --extra render)
"""

import argparse
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path

from .judge import pick_judge, spot_check
from .providers import MODELS, available_models, cost, extract
from .report import markdown, regressions, summary_table, update_readme, aggregate
from .schema import CV
from .scoring import score_cv

DATA = Path("data/cvs")
RESULTS = Path("results")


def load_dataset():
    out = []
    for p in sorted(DATA.glob("cv_*.json")):
        doc = next(p.with_suffix(s) for s in (".pdf", ".docx") if p.with_suffix(s).exists())
        out.append((json.loads(p.read_text(encoding="utf-8")), doc))
    return out


def run_one(model, gold, doc):
    t0 = time.perf_counter()
    try:
        pred, t_in, t_out = extract(model, doc)
        error = None
    except Exception as e:  # one bad call is a scored failure, not a crashed run
        pred, t_in, t_out, error = None, 0, 0, f"{type(e).__name__}: {e}"[:500]
    return dict(id=gold["id"], meta=gold["meta"], pred=pred, error=error, tokens=[t_in, t_out],
                latency=round(time.perf_counter() - t0, 3), cost=cost(model, t_in, t_out))


def cmd_run(args):
    if args.fake:
        models, skipped = ["fake"], {}
    else:
        models, skipped = available_models()
        if args.models:
            models = [m for m in models if m in args.models.split(",")]
        if not models:
            print("No provider API key set (GEMINI_API_KEY / ANTHROPIC_API_KEY). "
                  "Set at least one, or use --fake for an offline dry run.")
            return 2
    dataset = load_dataset()[: args.limit]
    judge = pick_judge(models)
    check = spot_check(judge) if judge else None
    if check:
        print(f"judge {judge.model}: {check['agree']}/{check['n']} agreement with human labels")

    scored, per_cv = {}, {}
    for m in models:
        print(f"{m}: extracting {len(dataset)} CVs ...", flush=True)
        with ThreadPoolExecutor(args.workers) as pool:
            rows = list(pool.map(lambda gd: run_one(m, *gd), dataset))
        for row, (gold, _) in zip(rows, dataset):
            row["scores"], row["pr"] = score_cv(CV.model_validate(gold["cv"]), row["pred"], judge)
            row["pred"] = row["pred"].model_dump() if row["pred"] else None
        scored[m] = aggregate(rows) | {"model_id": MODELS[m][1]}
        per_cv[m] = rows
        print(f"  overall {scored[m]['overall']}  cost ${scored[m]['cost_usd']:.3f}  errors {scored[m]['errors']}")

    judge_info = check and check | {"calls": judge.calls, "cost_usd": round(judge.cost, 4)}
    res = dict(date=date.today().isoformat(), dry_run=args.fake, n_cvs=len(dataset), models=scored, skipped=skipped,
               judge=judge_info, total_cost_usd=round(sum(s["cost_usd"] for s in scored.values()) + (judge.cost if judge else 0), 4),
               per_cv=per_cv)
    RESULTS.mkdir(exist_ok=True)
    out = RESULTS / f"{res['date']}{'-fake' if args.fake else ''}.json"
    out.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    Path("RESULTS-fake.md" if args.fake else "RESULTS.md").write_text(markdown(res), encoding="utf-8")
    if not args.fake:
        update_readme(res)
    print("\n" + summary_table(res))
    print(f"\nwrote {out}. Total API spend: ${res['total_cost_usd']:.2f}")

    if args.baseline:
        failed = regressions(json.loads(Path(args.baseline).read_text(encoding="utf-8")), res)
        for line in failed:
            print("REGRESSION", line)
        if failed:
            return 1
        print(f"no field dropped more than 2 points vs {args.baseline}")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(prog="evals", description="CV extraction evals")
    sub = ap.add_subparsers(dest="cmd", required=True)
    run = sub.add_parser("run", help="extract, score, write results/<date>.json and RESULTS.md")
    run.add_argument("--baseline", help="previous results JSON; exit 1 if any field drops > 2 points")
    run.add_argument("--models", help="comma-separated subset of: " + ", ".join(m for m in MODELS if m != "fake"))
    run.add_argument("--limit", type=int, help="only the first N CVs (cheap smoke test)")
    run.add_argument("--workers", type=int, default=4, help="parallel calls per model")
    run.add_argument("--fake", action="store_true", help="offline dry run with a fake provider, no API keys")
    sub.add_parser("generate", help="re-render the synthetic CVs in data/cvs")
    args = ap.parse_args(argv)
    if args.cmd == "generate":
        from .generate import main as generate
        generate()
        return 0
    return cmd_run(args)


if __name__ == "__main__":
    sys.exit(main())
