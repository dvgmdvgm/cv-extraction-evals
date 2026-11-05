import pytest

from cv_evals.schema import CV, Education, Job, Language
from cv_evals.scoring import FIELDS, fuzzy, norm_date, norm_email, norm_language, norm_phone, norm_text, prf, score_cv


@pytest.mark.parametrize("raw", ["+34 612 345 678", "612 34 56 78", "(+34) 612345678", "0034 612 345 678", "+34612345678"])
def test_phone_spanish_formats_to_e164(raw):
    assert norm_phone(raw) == "+34612345678"


@pytest.mark.parametrize("raw", ["+44 7700 900123", "+44 (0)7700 900123", "0044 7700 900123"])
def test_phone_uk_formats_to_e164(raw):
    assert norm_phone(raw) == "+447700900123"


def test_phone_missing():
    assert norm_phone(None) is None and norm_phone("") is None


@pytest.mark.parametrize("raw, expected", [
    ("2019-03", "2019-03"), ("Mar 2019", "2019-03"), ("March 2019", "2019-03"), ("03/2019", "2019-03"),
    ("2019-03-01", "2019-03"), ("01/03/2019", "2019-03"), ("ene. 2021", "2021-01"), ("enero de 2021", "2021-01"),
    ("sept. 2020", "2020-09"), ("ago. 2018", "2018-08"), ("dic. 2022", "2022-12"), ("2019", "2019"),
])
def test_dates_to_year_month(raw, expected):
    assert norm_date(raw) == expected


@pytest.mark.parametrize("raw", [None, "Present", "present", "actualidad", "Hoy", "now"])
def test_current_job_end_is_none(raw):
    assert norm_date(raw) is None


def test_unparseable_date_never_matches_a_real_one():
    assert norm_date("sometime") == "sometime"


def test_email_normalisation():
    assert norm_email(" Mailto:Ana.Gil@Example.com ") == "ana.gil@example.com"
    assert norm_email("") is None


@pytest.mark.parametrize("name, level, expected", [
    ("Español", "nativo", ("spanish", "native")), ("Inglés", "C1", ("english", "C1")),
    ("English", "Advanced (C1)", ("english", "C1")), ("Catalan", "lengua materna", ("catalan", "native")),
    ("french", "b2", ("french", "B2")),
])
def test_language_normalisation(name, level, expected):
    assert norm_language(name, level) == expected


def test_fuzzy_threshold():
    assert fuzzy("Lucía Ferrer Navarro", "Lucia Ferrer Navarro")  # accents
    assert fuzzy("Grupo Alcorza", "Grupo Alcorza S.A.") is False  # 0.84 < 0.9
    assert not fuzzy("Data Engineer", "Data Analyst")
    assert fuzzy(None, None) and not fuzzy("x", None)


def test_prf_counts_each_prediction_once():
    assert prf(["a", "b"], ["a", "a"], str.__eq__) == (0.5, 0.5, 0.5)
    assert prf([], [], str.__eq__) == (1.0, 1.0, 1.0)
    assert prf(["a"], [], str.__eq__) == (0.0, 0.0, 0.0)
    p, r, f = prf(["a", "b", "c", "d"], ["a", "b"], str.__eq__)
    assert (p, r) == (1.0, 0.5) and f == pytest.approx(2 / 3)


def gold_cv():
    return CV(
        name="Lucía Ferrer Navarro", email="lucia.ferrer@example.com", phone="+34612345678",
        location="Valencia, España", current_title="Ingeniera de Datos Senior", years_experience=7,
        skills=["Python", "SQL", "dbt"], languages=[Language(name="Spanish", level="native"), Language(name="English", level="C1")],
        experience=[Job(company="Datanova Ibérica", title="Ingeniera de Datos Senior", start="2022-03", end=None),
                    Job(company="Banca Mirador", title="Analista de Datos", start="2019-01", end="2022-02")],
        education=[Education(institution="Universidad de Sevilla", degree="Máster en Ciencia de Datos")],
    )


def test_perfect_prediction_scores_one_everywhere():
    scores, pr = score_cv(gold_cv(), gold_cv())
    assert all(v == 1.0 for v in scores.values()) and set(scores) == set(FIELDS)
    assert all(v == (1.0, 1.0) for v in pr.values())


def test_failed_call_scores_zero():
    scores, _ = score_cv(gold_cv(), None)
    assert all(v == 0.0 for v in scores.values())


def test_surface_variation_is_normalised_away():
    pred = gold_cv().model_copy(deep=True)
    pred.phone, pred.email = "612 34 56 78", "LUCIA.FERRER@EXAMPLE.COM"
    pred.languages = [Language(name="Español", level="Nativo"), Language(name="Inglés", level="C1")]
    pred.skills = ["sql", "python", "DBT"]
    pred.experience[1].start, pred.experience[1].end = "ene. 2019", "02/2022"
    scores, _ = score_cv(gold_cv(), pred)
    assert all(v == 1.0 for v in scores.values()), scores


def test_judge_only_called_when_fuzzy_fails():
    calls = []
    judge = lambda a, b: calls.append((a, b)) or True
    pred = gold_cv().model_copy(deep=True)
    pred.current_title = "Senior Data Engineer"  # translated: fuzzy fails, judge says same
    scores, _ = score_cv(gold_cv(), pred, judge)
    assert scores["current_title"] == 1.0
    assert calls == [("Ingeniera de Datos Senior", "Senior Data Engineer")]


def test_wrong_fields_lose_points():
    pred = gold_cv().model_copy(deep=True)
    pred.email, pred.years_experience = None, 8
    pred.experience[0].start = "2022"  # month dropped
    pred.skills = ["Python", "SQL", "dbt", "Excel"]  # one hallucinated
    scores, pr = score_cv(gold_cv(), pred)
    assert scores["email"] == 0 and scores["years_experience"] == 0
    assert scores["experience_dates"] == 0.5 and scores["experience"] == 1.0
    assert pr["skills"] == (0.75, 1.0)


# --- hard subset: gold rules, non-Latin text, month names in more languages ----------

@pytest.mark.parametrize("raw, expected", [
    ("gener 2020", "2020-01"), ("març 2021", "2021-03"), ("juny 2022", "2022-06"), ("setembre 2023", "2023-09"),
    ("desembre 2019", "2019-12"), ("março de 2017", "2017-03"), ("outubro de 2018", "2018-10"),
    ("dezembro de 2019", "2019-12"), ("Okt. 2019", "2019-10"), ("16/10/2021", "2021-10"),
])
def test_month_names_in_catalan_portuguese_german(raw, expected):
    assert norm_date(raw) == expected


def test_non_latin_text_is_kept_not_erased():
    assert norm_text("Олена Гарбузенко") == "олена гарбузенко"
    assert not fuzzy("Олена Гарбузенко", "Андрій Ковтуненко")  # used to normalise both to "" and match
    assert fuzzy("Νίκος Παπαδάκης", "ΝΙΚΟΣ ΠΑΠΑΔΑΚΗΣ")
    assert norm_text("Lucía_Ferrer") == "lucia ferrer"


def test_rules_exclude_fields_from_scoring():
    pred = gold_cv().model_copy(deep=True)
    pred.current_title, pred.languages = "Something else", []
    scores, pr = score_cv(gold_cv(), pred, rules={"exclude": ["current_title", "languages"]})
    assert "current_title" not in scores and "languages" not in scores and "languages" not in pr
    assert all(v == 1.0 for v in scores.values())
    failed, _ = score_cv(gold_cv(), None, rules={"exclude": ["languages"]})
    assert "languages" not in failed and set(failed.values()) == {0.0}


def test_rules_accept_alternative_name():
    gold = gold_cv().model_copy(update={"name": "Olena Harbuzenko"})
    rules = {"accept": {"name": ["Олена Гарбузенко"]}}
    for name, ok in [("Olena Harbuzenko", True), ("Олена Гарбузенко", True), ("Andrii Kovtunenko", False)]:
        pred = gold.model_copy(update={"name": name})
        assert score_cv(gold, pred, rules=rules)[0]["name"] == ok, name


def test_year_level_dates_only_when_the_rule_is_set():
    gold = gold_cv().model_copy(deep=True)
    gold.experience[1].start, gold.experience[1].end = "2019", "2022"  # "Summer 2019 – Spring 2022"
    pred = gold.model_copy(deep=True)
    pred.experience[1].start, pred.experience[1].end = "2019-06", "2022-03"
    assert score_cv(gold, pred)[0]["experience_dates"] == 0.5
    assert score_cv(gold, pred, rules={"year_level_dates": True})[0]["experience_dates"] == 1.0
    pred.experience[1].start = "2018-06"  # wrong year still fails
    assert score_cv(gold, pred, rules={"year_level_dates": True})[0]["experience_dates"] == 0.5
    gold.experience[0].start = "2022-03"  # month-precise gold stays exact under the rule
    pred.experience[0].start = "2022-04"
    assert score_cv(gold, pred, rules={"year_level_dates": True})[0]["experience_dates"] == 0.0
