"""LLM-as-judge for job titles, where string similarity fails ("Ingeniera de Datos" vs
"Data Engineer"). Only called when the fuzzy match has already failed, and validated
against human labels on a fixed spot-check set before its verdicts are trusted."""

import json
from pathlib import Path

from pydantic import BaseModel

from .providers import MODELS, complete, cost
from .scoring import norm_text

SPOT_CHECK = Path("data/judge_spotcheck.json")
# The strongest available model judges. It is also under test; the judge only sees
# title pairs, never the CV, so self-preference has little to act on.
PREFERENCE = ["claude-opus-5.5", "claude-sonnet-5.5", "gemini-3.1-pro"]

JUDGE_PROMPT = """You check a CV extraction system. You get the job title written in a CV (reference) and the title the system extracted.
Decide whether both name the same role at the same seniority.
Translations, abbreviations, word order, punctuation and gendered word forms do not matter.
A different seniority level (e.g. "Senior" missing or added) or a different function is a different role."""


class Verdict(BaseModel):
    same_role: bool


class Judge:
    def __init__(self, model):
        self.model, self.cache, self.calls, self.cost = model, {}, 0, 0.0

    def __call__(self, reference, extracted):
        key = (reference, extracted)
        if key not in self.cache:
            if MODELS[self.model][0] == "fake":
                a, b = set(norm_text(reference).split()), set(norm_text(extracted).split())
                self.cache[key] = len(a & b) / max(len(a | b), 1) >= 0.5
            else:
                try:
                    v, t_in, t_out = complete(self.model, JUDGE_PROMPT, f"Reference: {reference}\nExtracted: {extracted}", Verdict)
                except Exception as e:  # a failed judge call counts as "different role"; not cached
                    print(f"judge error: {type(e).__name__}: {e}"[:300])
                    return False
                self.cost += cost(self.model, t_in, t_out)
                self.cache[key] = v.same_role
            self.calls += 1
        return self.cache[key]


def pick_judge(models):
    if "fake" in models:
        return Judge("fake")
    return next((Judge(m) for m in PREFERENCE if m in models), None)


def spot_check(judge):
    """Judge-human agreement on hand-labelled title pairs."""
    items = json.loads(SPOT_CHECK.read_text(encoding="utf-8"))
    rows = [dict(item, judge=judge(item["reference"], item["extracted"])) for item in items]
    agree = sum(r["judge"] == r["human"] for r in rows)
    return dict(model=judge.model, agree=agree, n=len(rows), disagreements=[r for r in rows if r["judge"] != r["human"]])
