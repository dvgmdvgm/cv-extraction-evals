"""End-to-end with the offline fake provider: dataset -> extraction -> scoring -> report -> regression gate."""

import json
import shutil
from pathlib import Path

from cv_evals.cli import main
from cv_evals.schema import CV

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
