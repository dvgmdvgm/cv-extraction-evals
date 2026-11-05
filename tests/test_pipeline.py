"""End-to-end with the offline fake provider: dataset -> extraction -> scoring -> report -> regression gate."""

import json
import shutil
from collections import Counter
from pathlib import Path

import pytest

from cv_evals.cli import main
from cv_evals.report import aggregate, regressions
from cv_evals.schema import CV
from cv_evals.scoring import FIELDS

ROOT = Path(__file__).resolve().parent.parent


def test_dataset_is_complete_and_valid():
    golds = sorted((ROOT / "data/cvs").glob("cv_*.json"))
    assert len(golds) == 40
    for p in golds:
        g = json.loads(p.read_text(encoding="utf-8"))
        CV.model_validate(g["cv"])
        assert p.with_suffix(".pdf").exists() or p.with_suffix(".docx").exists()
    metas = [json.loads(p.read_text(encoding="utf-8"))["meta"] for p in golds]
    for edge in ["no_email", "two_phones", "year_only_dates"]:
        assert any(edge in m["edge_cases"] for m in metas)
    assert {m["format"] for m in metas} == {"pdf", "scanned", "docx"} and {m["lang"] for m in metas} == {"en", "es"}


def test_fake_run_and_regression_gate(tmp_path, monkeypatch):
    shutil.copytree(ROOT / "data", tmp_path / "data")
    monkeypatch.chdir(tmp_path)

    assert main(["run", "--fake"]) == 0
    [result] = Path("results").glob("*-fake.json")
    res = json.loads(result.read_text(encoding="utf-8"))
    assert res["models"]["fake"]["errors"] == 0 and res["judge"]["n"] == 10
    assert Path("RESULTS-fake.md").read_text(encoding="utf-8").startswith("# Results")

    # Same run against itself: no regression.
    assert main(["run", "--fake", "--baseline", str(result)]) == 0

    # A baseline 3 points better on one field: the gate must fail.
    res["models"]["fake"]["fields"]["skills"] += 3
    better = tmp_path / "better.json"
    better.write_text(json.dumps(res), encoding="utf-8")
    assert main(["run", "--fake", "--baseline", str(better)]) == 1


def test_hard_dataset_is_complete_and_rules_are_valid():
    golds = sorted((ROOT / "data/hard").glob("*.json"))
    assert 30 <= len(golds) <= 40
    cases = Counter()
    for p in golds:
        g = json.loads(p.read_text(encoding="utf-8"))
        cv = CV.model_validate(g["cv"])
        assert p.with_suffix(".pdf").exists()
        cases.update(g["meta"]["edge_cases"])
        rules = g.get("rules", {})
        assert set(rules) <= {"exclude", "accept", "year_level_dates"}
        assert set(rules.get("exclude", [])) <= set(FIELDS) and set(rules.get("accept", {})) <= {"name", "location", "current_title"}
        if rules.get("year_level_dates"):  # only used where some date really is year-only
            assert any(len(d) == 4 for j in cv.experience for d in (j.start, j.end) if d)
    for case in ["phone_photo", "fax_scan", "rating_tables", "three_column", "contact_page2", "distractors",
                 "mixed_language", "ambiguous_dates", "non_latin_name", "personal_contact"]:
        assert cases[case] >= 3, case


def test_aggregate_skips_excluded_fields():
    row = lambda scores, pr: dict(meta=dict(format="pdf", layout="one_col", lang="en", edge_cases=["x"]),
                                  scores=scores, pr=pr, latency=1.0, cost=0.0, error=None)
    full = {f: 1.0 for f in FIELDS}
    part = {f: 0.0 for f in FIELDS if f != "languages"}
    pr = {f: (1.0, 1.0) for f in ("skills", "languages", "experience", "education")}
    agg = aggregate([row(full, pr), row(part, {k: v for k, v in pr.items() if k != "languages"})])
    assert agg["fields"]["languages"] == 100.0 and agg["fields"]["name"] == 50.0
    assert agg["by_slice"]["case: x"] == round(100 * (1 + 0) / 2, 1)


def test_regression_gate_refuses_a_baseline_from_another_dataset():
    run = lambda ds: dict(dataset=ds, models={"m": dict(fields={f: 100.0 for f in FIELDS})})
    assert regressions(run("hard"), run("hard")) == []
    assert regressions({"models": run("standard")["models"]}, run("standard")) == []  # old files have no dataset key
    with pytest.raises(ValueError):
        regressions(run("standard"), run("hard"))


def test_fake_run_on_hard_dataset_writes_its_own_files(tmp_path, monkeypatch):
    shutil.copytree(ROOT / "data", tmp_path / "data")
    monkeypatch.chdir(tmp_path)
    assert main(["run", "--fake", "--dataset", "hard"]) == 0
    [result] = Path("results").glob("*-hard-fake.json")
    res = json.loads(result.read_text(encoding="utf-8"))
    assert res["dataset"] == "hard" and res["n_cvs"] == len(list(Path("data/hard").glob("*.json")))
    assert Path("RESULTS-hard-fake.md").exists() and not Path("RESULTS-fake.md").exists()
    assert main(["run", "--fake", "--dataset", "hard", "--baseline", str(result)]) == 0
    assert main(["run", "--fake", "--baseline", str(result)]) == 2  # standard run vs hard baseline
