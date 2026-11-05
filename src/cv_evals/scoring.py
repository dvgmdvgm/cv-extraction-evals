"""Normalisation and per-CV metrics. Pure functions: no API calls except through the
optional `judge(gold_title, predicted_title) -> bool` callable."""

import re
import unicodedata
from difflib import SequenceMatcher

from .schema import CV

FUZZY_THRESHOLD = 0.9
FIELDS = ["name", "email", "phone", "location", "current_title", "years_experience",
          "skills", "languages", "experience", "experience_dates", "education"]
LIST_FIELDS = ["skills", "languages", "experience", "education"]

# First three letters of month names in English, Spanish, Catalan, Portuguese and German.
MONTHS = dict(jan=1, ene=1, gen=1, feb=2, fev=2, mar=3, apr=4, abr=4, may=5, mai=5, jun=6, jul=7,
              aug=8, ago=8, sep=9, set=9, oct=10, out=10, okt=10, nov=11, dec=12, dic=12, des=12, dez=12)
PRESENT = {"present", "now", "current", "today", "actualidad", "presente", "hoy", "actual"}
LANG_ALIASES = {"espanol": "spanish", "castellano": "spanish", "ingles": "english", "frances": "french",
                "aleman": "german", "italiano": "italian", "catala": "catalan", "portugues": "portuguese"}
NATIVE = {"native", "mother tongue", "bilingual", "nativo", "nativa", "lengua materna", "bilingue"}


# --- normalisation -------------------------------------------------------------------

def norm_text(s):
    """Lowercase, strip accents and punctuation, collapse whitespace. Non-Latin letters are kept."""
    if s is None:
        return ""
    s = "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c)).casefold()
    return " ".join(re.sub(r"[^\w+#]+|_", " ", s).split())


def norm_email(s):
    s = (s or "").strip().lower().removeprefix("mailto:")
    return s or None


def norm_phone(s, default_cc="34"):
    """To E.164. National numbers without a country code are assumed Spanish."""
    if not s:
        return None
    s = s.replace("(0)", "")  # UK "+44 (0)7700 ..." trunk prefix
    digits = re.sub(r"\D", "", s)
    if s.lstrip(" (").startswith("+"):
        return "+" + digits
    if digits.startswith("00"):
        return "+" + digits[2:]
    if len(digits) == 9:  # ponytail: Spanish-only national numbering; use the phonenumbers lib for more countries
        return "+" + default_cc + digits
    return "+" + digits


def norm_date(s):
    """To "YYYY-MM", or "YYYY" if no month is given. Current job ("present", "actualidad") -> None.
    Unparseable input is returned stripped so it can never accidentally match."""
    if s is None:
        return None
    toks = norm_text(s).split()
    if not toks or " ".join(toks) in PRESENT:
        return None
    years = [t for t in toks if re.fullmatch(r"\d{4}", t)]
    if not years:
        return s.strip()
    i = toks.index(years[0])
    month = next((MONTHS[t[:3]] for t in toks if t.isalpha() and t[:3] in MONTHS), None)
    if month is None:
        if i + 1 < len(toks) and re.fullmatch(r"\d{1,2}", toks[i + 1]):  # 2019-03(-01)
            month = int(toks[i + 1])
        elif i > 0 and re.fullmatch(r"\d{1,2}", toks[i - 1]):  # 03/2019, 01/03/2019
            month = int(toks[i - 1])
    return f"{years[0]}-{month:02d}" if month and 1 <= month <= 12 else years[0]


def norm_language(name, level):
    n = norm_text(name)
    lv = norm_text(level)
    cefr = re.search(r"\b([abc][12])\b", lv)
    lv = "native" if lv in NATIVE else cefr.group(1).upper() if cefr else lv
    return LANG_ALIASES.get(n, n), lv


def fuzzy(a, b, threshold=FUZZY_THRESHOLD):
    """Similarity >= threshold after normalisation. Two missing values match."""
    a, b = norm_text(a), norm_text(b)
    if not a or not b:
        return a == b
    return SequenceMatcher(None, a, b).ratio() >= threshold


# --- metrics -------------------------------------------------------------------------

def prf(gold, pred, same):
    """Precision, recall, F1 with greedy one-to-one matching under the `same` predicate."""
    if not gold and not pred:
        return 1.0, 1.0, 1.0
    free = list(range(len(pred)))
    tp = 0
    for g in gold:
        hit = next((j for j in free if same(g, pred[j])), None)
        if hit is not None:
            free.remove(hit)
            tp += 1
    if tp == 0:
        return 0.0, 0.0, 0.0
    p, r = tp / len(pred), tp / len(gold)
    return p, r, 2 * p * r / (p + r)


def same_date(gold, pred, year_level=False):
    """Dates equal after normalisation. With year_level, a year-only gold ("Summer 2019" -> "2019")
    matches any month of that year: the CV does not say which month, so the model may pick one."""
    g, p = norm_date(gold), norm_date(pred)
    if year_level and g is not None and len(g) == 4:
        return p is not None and p[:4] == g
    return g == p


def score_cv(gold: CV, pred: CV | None, judge=None, rules=None):
    """Return ({field: score 0..1}, {list_field: (precision, recall)}).

    Titles are compared fuzzily first; the LLM judge is asked only when that fails.
    `rules` (from the gold file, hard subset only; see SPEC.md "Gold rules"):
      exclude: fields not scored for this CV, because the document does not settle them;
      accept: {field: [alternatives]} also counted correct (a name written in two scripts);
      year_level_dates: year-only gold dates are compared at year precision."""
    rules = rules or {}
    keep = [f for f in FIELDS if f not in rules.get("exclude", ())]
    if pred is None:  # failed call: everything wrong
        return {f: 0.0 for f in keep}, {f: (0.0, 0.0) for f in LIST_FIELDS if f in keep}
    accept = rules.get("accept", {})
    year_level = rules.get("year_level_dates", False)

    def same_title(g, p):
        return fuzzy(g, p) or bool(g and p and judge and judge(g, p))

    lists = {
        "skills": prf([norm_text(s) for s in gold.skills], [norm_text(s) for s in pred.skills], str.__eq__),
        "languages": prf([norm_language(l.name, l.level) for l in gold.languages],
                         [norm_language(l.name, l.level) for l in pred.languages], tuple.__eq__),
        "experience": prf(gold.experience, pred.experience,
                          lambda g, p: fuzzy(g.company, p.company) and same_title(g.title, p.title)),
        "education": prf(gold.education, pred.education,
                         lambda g, p: fuzzy(g.institution, p.institution) and fuzzy(g.degree, p.degree)),
    }
    # Dates are scored separately, over the jobs whose company was found.
    dated = [(g, next((p for p in pred.experience if fuzzy(g.company, p.company)), None)) for g in gold.experience]
    dated = [(g, p) for g, p in dated if p is not None]
    dates_ok = sum(same_date(g.start, p.start, year_level) and same_date(g.end, p.end, year_level) for g, p in dated)
    any_of = lambda f, test: any(test(g, getattr(pred, f)) for g in [getattr(gold, f), *accept.get(f, [])])

    scores = {
        "name": any_of("name", fuzzy),
        "email": norm_email(gold.email) == norm_email(pred.email),
        "phone": norm_phone(gold.phone) == norm_phone(pred.phone),
        "location": any_of("location", fuzzy),
        "current_title": any_of("current_title", same_title),
        "years_experience": gold.years_experience == pred.years_experience,
        "experience_dates": dates_ok / len(gold.experience) if gold.experience else 1.0,
        **{f: v[2] for f, v in lists.items()},
    }
    return {f: float(scores[f]) for f in keep}, {f: v[:2] for f, v in lists.items() if f in keep}
