"""Hard subset: synthetic CVs, each built around one failure mode the standard set does not exercise.

Same method as generate.py: the gold JSON is built first, then rendered, so the JSON is the label.
Where the document cannot settle a field, the gold file carries `rules` (see SPEC.md "Gold rules"):
the field is excluded, or alternatives / year-level dates are accepted. Everything is fictional.

Run with: uv run --extra render evals generate --dataset hard
Needs Arial and Microsoft YaHei from C:/Windows/Fonts (non-Latin names). The rendered files are committed.
"""

import io
import json
import random
import re
import time
from pathlib import Path
from xml.sax.saxutils import escape

from .generate import (BULLETS, EN_COMPANIES, EN_UNIS, ES_COMPANIES, ES_FIRST_F, ES_UNIS, HEAD, MONTHS_EN, MONTHS_ES,
                       ROLES, ascii_slug, make_gold, pdf_bytes, surface)
from .schema import Education, Job, Language

OUT = Path("data/hard")
FONTS = Path("C:/Windows/Fonts")
NOW = 2026 * 12 + 9  # month index of generate.TODAY (2026-10)

# (case, number of CVs). Three CVs also get a scan on top of their own case (see the builders).
CASES = [("phone_photo", 4), ("fax_scan", 3), ("rating_tables", 4), ("three_column", 4), ("contact_page2", 4),
         ("distractors", 4), ("mixed_language", 4), ("ambiguous_dates", 5), ("non_latin_name", 4), ("personal_contact", 4)]

MONTHS_CA = ["gener", "febrer", "març", "abril", "maig", "juny", "juliol", "agost", "setembre", "octubre", "novembre", "desembre"]
MONTHS_PT = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro",
             "dezembro"]

ym = lambda m: f"{m // 12}-{m % 12 + 1:02d}"
mon = lambda names, m, fmt="{mo} {y}": fmt.format(mo=names[m % 12], y=m // 12)


# --- gold helpers --------------------------------------------------------------------

def base(i, rng, lang, case, layout="one_col"):
    """A standard gold CV (generate.make_gold) to start from, plus the meta of the hard CV."""
    cv, extra = make_gold(i, dict(lang="en" if lang == "en" else "es", edge_cases=[]), rng)
    return dict(lang=lang, format="pdf", layout=layout, edge_cases=[case]), cv, extra


def strings(cv, meta, extra, rng):
    """Display strings via generate.surface, for the CV's base language."""
    return surface(cv, dict(lang="en" if meta["lang"] == "en" else "es", edge_cases=[]), extra, rng)


def timeline(rng, n, current=True):
    """n (start, end) month indexes, most recent first; end None = current job."""
    end, out = NOW - (0 if current else rng.randint(2, 6)), []
    for k in range(n):
        start = end - rng.randint(14, 40)
        out.append((start, None if k == 0 and current else end))
        end = start - rng.randint(0, 3)
    return out


def set_jobs(cv, jobs, first_start_month):
    cv.experience = jobs
    cv.current_title = jobs[0].title
    cv.years_experience = (NOW - first_start_month) // 12


def gender(cv):
    """Spanish word endings for the CV's (fictional) person: {o} -> o/a, {a} -> ""/a."""
    return dict(o="a", a="a") if cv.name.split()[0] in ES_FIRST_F else dict(o="o", a="")


def role_level(role, title):
    """Index of `title` in the role's ladder (either gender), to translate it to another language."""
    for lang in ("en", "es"):
        for g in (dict(o="o", a=""), dict(o="a", a="a")):
            ladder = [t.format(**g) for t in role[lang]]
            if title in ladder:
                return ladder.index(title)
    raise ValueError(title)


# --- builders: one per case, (k, i, rng) -> (meta, cv, strings, render options | None, rules) ---

def scan_case(case):
    def build(k, i, rng):
        meta, cv, extra = base(i, rng, "en" if k % 2 == 0 else "es", case, ["one_col", "two_col"][k % 2])
        return meta, cv, strings(cv, meta, extra, rng), None, {}  # None: the standard renderer
    return build


def rating_tables(k, i, rng):
    lang = "en" if k % 2 == 0 else "es"
    meta, cv, extra = base(i, rng, lang, "rating_tables", "two_col" if k == 1 else "one_col")
    cv.skills = rng.sample(extra["role"]["skills"], min(8, len(extra["role"]["skills"])))
    s = strings(cv, meta, extra, rng)
    levels = [rng.randint(2, 5) for _ in cv.skills]
    o = dict(layout=meta["layout"], skills=dict(kind=["dots", "bars", "squares", "dots"][k], levels=levels,
                                                 per_row=[2, 1, 3, 2][k]))
    rules = {}
    cefr_n = dict(native=5, C2=5, C1=4, B2=3, B1=2, A2=1)
    if k == 1:  # language levels drawn as bars only: no CEFR level in the document
        o["langs"] = dict(kind="bars", cefr=False, levels=[cefr_n[l.level] for l in cv.languages])
        rules["exclude"] = ["languages"]
    elif k == 2:
        o["langs"] = dict(kind="dots", cefr=True, levels=[cefr_n[l.level] for l in cv.languages])
    if k == 0:
        o["exp_table"] = True
    if k == 3:  # experience and education in one table
        o["exp_table"] = "with_education"
        meta["edge_cases"].append("phone_photo")
    return meta, cv, s, o, rules


def three_column(k, i, rng):
    lang = "en" if k % 2 == 0 else "es"
    meta, cv, extra = base(i, rng, lang, "three_column", "three_col")
    cv.experience = cv.experience[:3]
    first = cv.experience[-1].start
    cv.years_experience = (NOW - (int(first[:4]) * 12 + int(first[5:]) - 1)) // 12
    s = strings(cv, meta, extra, rng)
    for j in s["jobs"]:
        j["bullets"] = j["bullets"][:1]
    cols = [[["contact", "skills", "languages"], ["profile", "experience"], ["education"]],
            [["profile", "experience"], ["education", "skills"], ["contact", "languages"]],
            [["experience"], ["profile", "education"], ["contact", "skills", "languages"]],
            [["languages", "skills"], ["experience"], ["contact", "profile", "education"]]][k]
    if k == 3:
        meta["edge_cases"].append("phone_photo")
    return meta, cv, s, dict(layout="three_col", cols=cols), {}


PROJECTS = {"en": ["Rebuilt the onboarding flow; activation up {n}%.", "Led a vendor migration with zero downtime.",
                   "Wrote the internal style guide used by {n} teams.", "Ran a quarterly hackathon for {n} engineers."],
            "es": ["Rediseñé el proceso de alta; activación +{n}%.", "Lideré una migración de proveedor sin cortes de servicio.",
                   "Redacté la guía interna usada por {n} equipos.", "Organicé un hackathon trimestral para {n} personas."]}


def contact_page2(k, i, rng):
    lang = "en" if k % 2 == 0 else "es"
    meta, cv, extra = base(i, rng, lang, "contact_page2")
    s = strings(cv, meta, extra, rng)
    for j in s["jobs"]:
        j["bullets"] = [b.format(n=rng.randint(2, 40)) for b in BULLETS[lang]]
    title = ("Contact", "Contacto")[lang == "es"] if k < 2 else ("Contact details", "Datos de contacto")[lang == "es"]
    header_bits = [cv.location] if k == 2 else []  # only the city on page 1, email and phone on page 2
    o = dict(layout="one_col", contact_inline=False, footer=True, header_bits=header_bits, contact_title=title,
             extras=[(("Projects", "Proyectos")[lang == "es"], [p.format(n=rng.randint(3, 30)) for p in PROJECTS[lang]])],
             order=["profile", "experience", "extras", "pagebreak", "education", "skills", "languages", "contact"])
    return meta, cv, s, o, {}


def referee(lang, rng):
    first, last = rng.choice(["Ruth", "Martin", "Helen", "Carmen", "Andrés", "Pilar"]), rng.choice(["Ashdown", "Ruiz", "Calloway", "Prieto"])
    phone = f"+44 7700 900{rng.randint(0, 999):03d}" if lang == "en" else f"+34 6{rng.randint(10, 99)} {rng.randint(100, 999)} {rng.randint(100, 999)}"
    head, pos = ("References", "Head of Engineering") if lang == "en" else ("Referencias", "Responsable de Operaciones")
    return head, [f"{first} {last}, {pos} — {ascii_slug(first)}.{ascii_slug(last)}@example.org — {phone}"]


def distractors(k, i, rng):
    lang = "en" if k % 2 == 0 else "es"
    meta, cv, extra = base(i, rng, lang, "distractors")
    s = strings(cv, meta, extra, rng)
    o = dict(layout="one_col", photo=k in (0, 1, 3), logos=["initials", None, "name_only", "initials"][k],
             qr=f"https://example.com/cv/{ascii_slug(cv.name.split()[0])}-{i}" if k != 2 else None,
             icons=k == 0, extras=[referee(lang, rng)] if k in (1, 2) else [])
    if k == 3:
        meta["edge_cases"].append("fax_scan")
    return meta, cv, s, o, {}


CA = dict(titles=["Analista de Dades Júnior", "Analista de Dades", "Enginyer{a} de Dades", "Enginyer{a} de Dades Sènior"],
          companies=["Serveis Digitals Montseny", "Laboratoris Canigó", "Cooperativa Garbí", "Xarxa Logística Empordà"],
          h=dict(profile="Perfil", exp="Experiència professional", edu="Formació", skills="Competències", langs="Idiomes"),
          bullets=["Vaig liderar la migració de la plataforma de dades al núvol.", "Vaig reduir un {n}% el temps de càrrega dels informes.",
                   "Vaig formar {n} companys en bones pràctiques de SQL."])


def mixed_language(k, i, rng):
    meta, cv, extra = base(i, rng, ["es", "ca", "es", "en"][k], "mixed_language")
    role = extra["role"]
    female = gender(cv)["a"] == "a"
    if k == 0:  # Spanish CV, English titles at international employers, a UK degree
        for j, comp in zip(cv.experience[:2], rng.sample(EN_COMPANIES, 2)):
            j.company, j.title = comp, role["en"][role_level(role, j.title)]
        cv.current_title = cv.experience[0].title
        cv.education[0] = Education(institution=rng.choice(EN_UNIS), degree=role["degree"][0])
        s = strings(cv, meta, extra, rng)
        s["headline"] = cv.current_title
        return meta, cv, s, dict(layout="one_col"), {}
    if k == 1:  # all Catalan: headings, titles, months, language names
        cv.skills = rng.sample(ROLES["data"]["skills"], 6)
        tl = timeline(rng, 3)
        g = "a" if female else ""
        jobs = [Job(company=c, title=CA["titles"][3 - n].format(a=g), start=ym(a), end=b and ym(b))
                for n, ((a, b), c) in enumerate(zip(tl, rng.sample(CA["companies"], 3)))]
        set_jobs(cv, jobs, tl[-1][0])
        cv.location = "Girona, Catalunya"
        cv.languages = [Language(name="Catalan", level="native"), Language(name="Spanish", level="native"),
                        Language(name="English", level=rng.choice(["B2", "C1"])), Language(name="French", level="B1")]
        cv.education = [Education(institution="Universitat Politècnica de Catalunya", degree="Grau en Enginyeria Informàtica"),
                        Education(institution="Universitat de Girona", degree="Màster en Ciència de Dades")]
        s = strings(cv, meta, extra, rng)
        s["h"], s["headline"] = CA["h"], cv.current_title
        s["summary"] = f"Professional amb {cv.years_experience} anys d'experiència en plataformes de dades."
        for sj, (a, b) in zip(s["jobs"], tl):
            sj["dates"] = f"{mon(MONTHS_CA, a)} – {'actualitat' if b is None else mon(MONTHS_CA, b)}"
            sj["bullets"] = [x.format(n=rng.randint(5, 40)) for x in rng.sample(CA["bullets"], 2)]
        s["langs"] = ["Català — llengua materna", "Castellà — llengua materna", f"Anglès — {cv.languages[2].level}", "Francès — B1"]
        return meta, cv, s, dict(layout="two_col"), {}
    if k == 2:  # Spanish CV whose latest job and master's are in Portugal, written in Portuguese
        a = int(cv.experience[0].start[:4]) * 12 + int(cv.experience[0].start[5:]) - 1
        cv.experience[0].company = "Sistemas Tejo, Lda."
        cv.experience[0].title = f"Engenheir{'a' if female else 'o'} de Software Sénior"
        cv.current_title, cv.location = cv.experience[0].title, "Lisboa, Portugal"
        cv.education[0] = Education(institution="Universidade de Lisboa", degree="Mestrado em Engenharia Informática")
        cv.languages = [l for l in cv.languages if l.name != "Portuguese"] + [Language(name="Portuguese", level="C1")]
        s = strings(cv, meta, extra, rng)
        s["headline"] = cv.current_title
        s["jobs"][0]["dates"] = f"{mon(MONTHS_PT, a, '{mo} de {y}')} – presente"
        s["jobs"][0]["bullets"] = ["Liderei a migração dos serviços de pagamentos para Kubernetes.",
                                   f"Reduzi em {rng.randint(10, 40)}% o tempo de resposta da API principal."]
        return meta, cv, s, dict(layout="one_col"), {}
    # English CV, Spanish degrees and one Spanish job title kept as written
    cv.education = [Education(institution=rng.choice(ES_UNIS), degree=role["degree"][1])]
    last = cv.experience[-1]
    last.company, last.title = rng.choice(ES_COMPANIES), role["es"][role_level(role, last.title)].format(o="o", a="")  # EN names: male forms
    s = strings(cv, meta, extra, rng)
    return meta, cv, s, dict(layout="two_col"), {}


def ambiguous_dates(k, i, rng):
    lang = ["en", "en", "es", "es", "es"][k]
    meta, cv, extra = base(i, rng, lang, "ambiguous_dates")
    role, rules = extra["role"], {}
    lvl, g = role_level(role, cv.experience[0].title), gender(cv)
    titles = lambda n: [role[lang][max(0, lvl - x)].format(**g) for x in range(n)]  # most senior first
    comps = rng.sample(EN_COMPANIES if lang == "en" else ES_COMPANIES, 4)
    if k == 0:  # overlapping jobs, two of them current, no headline: current_title is not settled
        a0, a1, a2 = NOW - rng.randint(20, 30), NOW - rng.randint(36, 50), NOW - rng.randint(80, 100)
        b2 = a0 + rng.randint(2, 5)  # previous job ends after the new one started
        uni = rng.choice(EN_UNIS)
        jobs = [Job(company=comps[0], title=titles(1)[0], start=ym(a0), end=None),
                Job(company=uni, title="Part-time Lecturer", start=ym(a1), end=None),
                Job(company=comps[1], title=role["en"][max(0, lvl - 1)], start=ym(a2), end=ym(b2))]
        set_jobs(cv, jobs, a2)
        rules["exclude"] = ["current_title"]
        shown = [f"{MONTHS_EN[a0 % 12]} {a0 // 12} – Present", f"{MONTHS_EN[a1 % 12]} {a1 // 12} – Present",
                 f"{MONTHS_EN[a2 % 12]} {a2 // 12} – {MONTHS_EN[b2 % 12]} {b2 // 12}"]
    elif k == 1:  # seasons: the month is not stated
        y = 2026 - rng.randint(0, 2)
        spans = [(("Summer", y), None), (("Autumn", y - 3), ("Spring", y)), (("Summer", y - 4), ("Summer", y - 4))]
        jobs = [Job(company=c, title=t, start=str(a[1]), end=b and str(b[1]))
                for (a, b), c, t in zip(spans, comps, titles(2) + ["Summer Intern"])]
        set_jobs(cv, jobs, (y - 4) * 12)
        rules["year_level_dates"] = True
        shown = [f"Summer {y} – present", f"Autumn {y - 3} – Spring {y}", f"Summer {y - 4}"]
    elif k == 2:  # academic years "2017–18"
        y = 2026 - rng.randint(5, 7)
        uni = rng.choice(ES_UNIS)
        jobs = [Job(company=comps[0], title=titles(1)[0], start=f"{y}-09", end=None),
                Job(company=uni, title="Profesor{a} Asociad{o}".format(**g), start=str(y - 2), end=str(y)),
                Job(company=uni.replace("Universidad", "Fundación Universidad"), title="Becari{o} de Investigación".format(**g),
                    start=str(y - 3), end=str(y - 2))]
        set_jobs(cv, jobs, (y - 3) * 12)
        rules["year_level_dates"] = True
        shown = [f"sept. {y} – actualidad", f"cursos {y - 2}–{str(y - 1)[2:]} y {y - 1}–{str(y)[2:]}", f"curso {y - 3}–{str(y - 2)[2:]}"]
    elif k == 3:  # month names in four languages in one CV
        tl = timeline(rng, 4)
        jobs = [Job(company=c, title=t, start=ym(a), end=b and ym(b)) for (a, b), c, t in
                zip(tl, comps, titles(4))]
        jobs[2].company = "Sistemas Tejo, Lda."
        set_jobs(cv, jobs, tl[-1][0])
        fmts = [lambda m: f"{MONTHS_EN[m % 12]} {m // 12}", lambda m: mon(MONTHS_CA, m),
                lambda m: mon(MONTHS_PT, m, "{mo} de {y}"), lambda m: mon(MONTHS_ES, m)]
        shown = [f"{f(a)} – {'present' if b is None else f(b)}" for f, (a, b) in zip(fmts, tl)]
    else:  # DD/MM/YYYY; days above 12 in the same CV settle the convention
        tl = timeline(rng, 3)
        jobs = [Job(company=c, title=t, start=ym(a), end=b and ym(b)) for (a, b), c, t in zip(tl, comps, titles(3))]
        set_jobs(cv, jobs, tl[-1][0])
        d = lambda m, day: f"{day:02d}/{m % 12 + 1:02d}/{m // 12}"
        (a0, _), (a1, b1), (a2, b2) = tl
        shown = [f"{d(a0, 3)} – actualidad", f"{d(a1, 16)} – {d(b1, 2)}", f"{d(a2, 7)} – {d(b2, 28)}"]
    s = strings(cv, meta, extra, rng)
    for sj, txt in zip(s["jobs"], shown):
        sj["dates"] = txt
    if k == 0:
        s["headline"] = None
        s["summary"] = f"Data professional with {cv.years_experience} years of experience, currently combining industry and teaching."
    return meta, cv, s, dict(layout=["one_col", "two_col"][k % 2]), rules


NON_LATIN = [("Олена Гарбузенко", "Olena Harbuzenko", "en", "native_first"),
             ("Андрій Ковтуненко", "Andrii Kovtunenko", "es", "latin_first"),
             ("Νίκος Παπαδάκης", "Nikos Papadakis", "en", "native_first"),
             ("林雨桐", "Yutong Lin", "en", "inline")]


def non_latin_name(k, i, rng):
    native, latin, lang, style = NON_LATIN[k]
    meta, cv, extra = base(i, rng, lang, "non_latin_name")
    first, last = latin.split()
    cv.name = latin
    if cv.email:
        cv.email = f"{ascii_slug(first)}.{ascii_slug(last)}@example.com"
    s = strings(cv, meta, extra, rng)
    s["name"], s["name_alt"] = {"native_first": (native, latin), "latin_first": (latin, native),
                                "inline": (f"{native} ({latin})", None)}[style]
    rules = dict(accept=dict(name=[native, f"{latin} ({native})", f"{native} ({latin})"]))
    return meta, cv, s, dict(layout=["one_col", "two_col"][k % 2]), rules


def personal_contact(k, i, rng):
    lang = "en" if k % 2 == 0 else "es"
    meta, cv, extra = base(i, rng, lang, "personal_contact")
    first, *last = cv.name.split()
    work_email = f"{ascii_slug(first)[0]}.{ascii_slug(last[0])}@{re.sub('[^a-z0-9]', '', ascii_slug(cv.experience[0].company))[:12]}.example.com"
    personal_email = f"{ascii_slug(first)}{ascii_slug(last[0])[:3]}{rng.randint(10, 99)}@example.net"
    mobile = extra["phones"][0]
    office = f"+44 20 7946 0{rng.randint(0, 999):03d}" if lang == "en" else f"+34 91 {rng.randint(100, 999)} {rng.randint(10, 99)} {rng.randint(10, 99)}"
    cv.email, cv.phone = personal_email, mobile.replace(" ", "")
    s = strings(cv, meta, extra, rng)
    s["contact"] = [
        [f"Work: {work_email}  ·  Personal: {personal_email}", f"Office: {office}  ·  Personal mobile: {mobile}"],
        [f"Correo (trabajo): {work_email}  ·  Correo personal: {personal_email}", f"Tel. oficina: {office}  ·  Móvil personal: {mobile}"],
        [f"{work_email} (work), {personal_email} (private)", f"Mobile: {mobile}  ·  Office: {office}"],  # no phone marked personal: first
        [f"Correo personal: {personal_email}  ·  Correo corporativo: {work_email}", f"Fijo (empresa): {office}  ·  Móvil personal: {mobile}"],
    ][k] + [cv.location]
    return meta, cv, s, dict(layout=["one_col", "two_col"][k % 2]), {}


BUILDERS = dict(phone_photo=scan_case("phone_photo"), fax_scan=scan_case("fax_scan"), rating_tables=rating_tables,
                three_column=three_column, contact_page2=contact_page2, distractors=distractors,
                mixed_language=mixed_language, ambiguous_dates=ambiguous_dates, non_latin_name=non_latin_name,
                personal_contact=personal_contact)


# --- renderer ------------------------------------------------------------------------

def register_fonts():
    from reportlab.lib.fonts import addMapping
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    if "Sans" in pdfmetrics.getRegisteredFontNames():
        return
    pdfmetrics.registerFont(TTFont("Sans", str(FONTS / "arial.ttf")))
    pdfmetrics.registerFont(TTFont("Sans-Bold", str(FONTS / "arialbd.ttf")))
    pdfmetrics.registerFont(TTFont("CJK", str(FONTS / "msyh.ttc"), subfontIndex=0))
    for bold in (0, 1):
        for italic in (0, 1):
            addMapping("Sans", bold, italic, "Sans-Bold" if bold else "Sans")


def render(s, o):
    """Layouts the standard renderer has no room for: three columns, rating tables, graphics, page-2 contact."""
    from reportlab import rl_config
    from reportlab.graphics.barcode.qr import QrCodeWidget
    from reportlab.graphics.shapes import Circle, Drawing, Ellipse, Line, Rect, String
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.pdfbase.pdfmetrics import stringWidth
    from reportlab.platypus import BaseDocTemplate, Frame, FrameBreak, PageBreak, PageTemplate, Paragraph, Spacer, Table, TableStyle

    rl_config.invariant = 1
    register_fonts()
    st = lambda size, bold=False, **kw: ParagraphStyle("x", fontName="Sans-Bold" if bold else "Sans", fontSize=size,
                                                        leading=size * 1.3, **kw)
    cjk = lambda t: re.sub(r"([\u4e00-\u9fff]+)", r'<font name="CJK">\1</font>', t)
    P = lambda text, style: Paragraph(cjk(escape(text)), style)
    name_st, head, body, h2, small = st(20, True), st(12, textColor=colors.HexColor("#444444")), st(9.5), \
        st(11, True, spaceBefore=8, spaceAfter=3), st(8.5, textColor=colors.HexColor("#555555"))
    ink, pale = colors.HexColor("#2b3a55"), colors.HexColor("#d5dbe5")
    plain = TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 2), ("TOPPADDING", (0, 0), (-1, -1), 1)])
    W, H = A4
    h = s["h"]

    def rating(n, kind):
        d = Drawing(50, 8)
        if kind == "bars":
            d.add(Rect(0, 1, 50, 6, fillColor=pale, strokeColor=None))
            d.add(Rect(0, 1, 10 * n, 6, fillColor=ink, strokeColor=None))
        for j in range(5) if kind != "bars" else []:
            fill = ink if j < n else pale
            d.add(Circle(j * 10 + 4, 4, 3.2, fillColor=fill, strokeColor=None) if kind == "dots"
                  else Rect(j * 10 + 1, 1, 6.5, 6.5, fillColor=fill, strokeColor=None))
        return d

    def logo(company, mode):
        hue = colors.HexColor(["#1f6f8b", "#99582a", "#5a189a", "#2d6a4f", "#9d0208"][sum(map(ord, company)) % 5])
        if mode == "initials":
            d = Drawing(24, 24)
            d.add(Rect(0, 0, 24, 24, rx=4, ry=4, fillColor=hue, strokeColor=None))
            d.add(String(12, 8, "".join(w[0] for w in company.split()[:2]).upper(), fontName="Sans-Bold", fontSize=10,
                         fillColor=colors.white, textAnchor="middle"))
            return d
        w = stringWidth(company.upper(), "Sans-Bold", 8) + 12
        d = Drawing(w, 16)
        d.add(Rect(0, 0, w, 16, rx=3, ry=3, fillColor=hue, strokeColor=None))
        d.add(String(6, 5, company.upper(), fontName="Sans-Bold", fontSize=8, fillColor=colors.white))
        return d

    def photo():
        d = Drawing(64, 78)
        d.add(Rect(0, 0, 64, 78, fillColor=colors.HexColor("#c9ced6"), strokeColor=None))
        d.add(Ellipse(32, 16, 24, 15, fillColor=colors.HexColor("#6c757d"), strokeColor=None))
        d.add(Circle(32, 48, 13, fillColor=colors.HexColor("#6c757d"), strokeColor=None))
        return d

    def qr(url):
        w = QrCodeWidget(url)
        x0, y0, x1, y1 = w.getBounds()
        d = Drawing(58, 58, transform=[58 / (x1 - x0), 0, 0, 58 / (y1 - y0), 0, 0])
        d.add(w)
        return d

    def icon(kind):
        d = Drawing(9, 9)
        if kind == 0:  # envelope
            d.add(Rect(0, 1, 9, 6.5, fillColor=None, strokeColor=ink, strokeWidth=0.8))
            d.add(Line(0, 7.5, 4.5, 3.5, strokeColor=ink, strokeWidth=0.8))
            d.add(Line(9, 7.5, 4.5, 3.5, strokeColor=ink, strokeWidth=0.8))
        elif kind == 1:  # handset
            d.add(Rect(2, 0, 5, 9, rx=1.2, ry=1.2, fillColor=ink, strokeColor=None))
        else:  # pin
            d.add(Circle(4.5, 5.5, 3.2, fillColor=ink, strokeColor=None))
            d.add(Circle(4.5, 5.5, 1.1, fillColor=colors.white, strokeColor=None))
        return d

    def items(names, spec, w):
        if not spec:
            return [P(", ".join(names), body)] if w > 8 * cm else [P(n, body) for n in names]
        cells = [[P(n, body), rating(lv, spec["kind"])] + ([P(spec["cefr_text"][j], small)] if spec.get("cefr") else [])
                 for j, (n, lv) in enumerate(zip(names, spec["levels"]))]
        per = spec.get("per_row", 1)
        rows = [sum(cells[r:r + per], []) for r in range(0, len(cells), per)]
        rows[-1] += [""] * (len(rows[0]) - len(rows[-1]))
        unit = [None, 56] + ([48] if spec.get("cefr") else [])
        cw = (w - (sum(unit[1:])) * per) / per
        t = Table(rows, colWidths=[cw if x is None else x for x in unit] * per, hAlign="LEFT")
        t.setStyle(plain)
        return [t]

    def job_rows(w):
        if o.get("exp_table"):
            rows = [[P(j["dates"], small), P(j["company"], body), P(j["title"], body)] for j in s["jobs"]]
            if o["exp_table"] == "with_education":
                rows += [[P(f"{2026 - 9 - 4 * n} – {2026 - 9 - 4 * n + 2}", small), P(e.split(" — ")[1], body),
                          P(e.split(" — ")[0], body)] for n, e in enumerate(s["edu"])]
            t = Table([[P(x, st(9, True)) for x in
                        (["Period", "Company", "Role"] if s["h"] is HEAD["en"] else ["Periodo", "Empresa / centro", "Puesto / titulación"])]]
                      + rows, colWidths=[3.6 * cm, (w - 3.6 * cm) * 0.45, (w - 3.6 * cm) * 0.55], repeatRows=1)
            t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.5, pale), ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eef1f5")),
                                   ("VALIGN", (0, 0), (-1, -1), "TOP")]))
            return [t]
        out = []
        for j in s["jobs"]:
            mode = o.get("logos")
            first = P(j["title"], st(9.5, True)) if mode == "name_only" else \
                Paragraph(f"<b>{cjk(escape(j['title']))}</b> — {cjk(escape(j['company']))}", body)
            block = [first, P(j["dates"], small)] + [P("• " + b, body) for b in j["bullets"]]
            if mode == "initials":
                t = Table([[logo(j["company"], mode), block]], colWidths=[1.1 * cm, w - 1.1 * cm])
                t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0)]))
                block = [t]
            elif mode == "name_only":  # the company name exists only inside the logo
                block = [logo(j["company"], mode), Spacer(1, 2)] + block
            out += block + [Spacer(1, 4)]
        return out

    def section(name, w):
        if name == "pagebreak":
            return [PageBreak()]
        if name == "header":
            out = [P(s["name"], name_st)] + ([P(s["name_alt"], head)] if s.get("name_alt") else [])
            out += [P(s["headline"], head)] if s["headline"] else []
            if o.get("header_bits"):
                out.append(P("  ·  ".join(o["header_bits"]), small))
            if o.get("contact_inline", o.get("layout", "one_col") == "one_col"):
                if o.get("icons"):
                    t = Table([[icon(n), P(c, small)] for n, c in enumerate(s["contact"])], colWidths=[0.45 * cm, None], hAlign="LEFT")
                    t.setStyle(plain)
                    out.append(t)
                else:
                    out.append(P("  ·  ".join(s["contact"]), small))
            side = ([photo()] if o.get("photo") else []) + ([qr(o["qr"]), P("Portfolio", small)] if o.get("qr") else [])
            if side:
                t = Table([[out, side]], colWidths=[w - 2.6 * cm, 2.6 * cm])
                t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("ALIGN", (1, 0), (1, 0), "RIGHT")]))
                out = [t]
            return out + [Spacer(1, 4)]
        if name == "contact":
            return [P(o.get("contact_title", "Contact"), h2)] + [P(c, small if w < 8 * cm else body) for c in s["contact"]]
        if name == "profile":
            return [P(h["profile"], h2), P(s["summary"], body)]
        if name == "experience":
            both = o.get("exp_table") == "with_education"
            return [P(("Career and education", "Trayectoria")[h is not HEAD["en"]] if both else h["exp"], h2)] + job_rows(w)
        if name == "education":
            return [P(h["edu"], h2)] + [P(e, body) for e in s["edu"]] if o.get("exp_table") != "with_education" else []
        if name == "skills":
            return [P(h["skills"], h2)] + items(s["skills"], o.get("skills"), w)
        if name == "languages":
            spec = o.get("langs")
            if not spec:
                return [P(h["langs"], h2)] + ([P("  ·  ".join(s["langs"]), body)] if w > 8 * cm else [P(l, body) for l in s["langs"]])
            names = [re.split(r" — |: | - ", l)[0] for l in s["langs"]]
            spec = dict(spec, cefr_text=[re.split(r" — |: | - ", l)[1] for l in s["langs"]])
            return [P(h["langs"], h2)] + items(names, spec, w)
        if name == "extras":
            return sum(([P(t, h2)] + [P("• " + x, body) for x in lines] for t, lines in o.get("extras", [])), [])
        raise ValueError(name)

    layout = o.get("layout", "one_col")
    if layout == "one_col":
        frames = [Frame(2 * cm, 2 * cm, W - 4 * cm, H - 4 * cm)]
        cols = [["header"] + o.get("order", ["profile", "experience", "education", "skills", "languages", "extras"])]
    elif layout == "two_col":
        frames = [Frame(1.2 * cm, 1.5 * cm, 5.6 * cm, H - 3 * cm), Frame(7.4 * cm, 1.5 * cm, W - 8.6 * cm, H - 3 * cm)]
        cols = [["header", "contact", "skills", "languages"], ["profile", "experience", "education", "extras"]]
    else:
        cw, top = (W - 3 * cm - 1.2 * cm) / 3, H - 4.2 * cm
        frames = [Frame(1.5 * cm, top, W - 3 * cm, 3 * cm)] + [Frame(1.5 * cm + n * (cw + 0.6 * cm), 1.5 * cm, cw, top - 1.7 * cm)
                                                              for n in range(3)]
        cols = [["header"]] + o["cols"]
    o = dict(o, contact_title=o.get("contact_title", ("Contact", "Contacto")[h is not HEAD["en"]]))
    story = []
    for n, (frame, secs) in enumerate(zip(frames, cols)):
        story += ([FrameBreak()] if n else []) + sum((section(x, frame._width) for x in secs), [])

    def deco(c, doc):
        if layout == "two_col":
            c.setFillColor(colors.HexColor("#eef1f5"))
            c.rect(0, 0, 7.0 * cm, H, stroke=0, fill=1)
        if o.get("footer"):
            c.setFont("Sans", 7.5)
            c.setFillColor(colors.HexColor("#888888"))
            c.drawCentredString(W / 2, 1.2 * cm, f"{s['name']} · CV · {doc.page}")
    buf = io.BytesIO()
    doc = BaseDocTemplate(buf, pagesize=A4, title="CV")
    doc.addPageTemplates([PageTemplate(frames=frames, onPage=deco)])
    doc.build(story)
    return buf.getvalue()


# --- scan degradation ----------------------------------------------------------------

FIXED = time.gmtime(1767225600)  # 2026-01-01, reproducible bytes


def phone_photo(pdf, path, rng):
    """A phone photo of a printed page: on a desk, perspective, rotation, uneven light, blur, JPEG."""
    import pypdfium2 as pdfium
    from PIL import Image, ImageChops, ImageEnhance, ImageFilter

    pages = []
    for page in pdfium.PdfDocument(pdf):
        img = page.render(scale=2.8).to_pil().convert("RGB")
        w, h = img.size
        pad = int(w * 0.07)
        desk = tuple(rng.randint(70, 110) - d for d in (0, 12, 25))
        canvas = Image.new("RGB", (w + 2 * pad, h + 2 * pad), desk)
        canvas.paste(img, (pad, pad))
        W, H = canvas.size
        j = lambda: rng.uniform(-0.035, 0.035) * W  # corners pulled in or out: a camera not parallel to the page
        img = canvas.transform(canvas.size, Image.QUAD, (j(), j(), j(), H + j(), W + j(), H + j(), W + j(), j()),
                               resample=Image.BICUBIC, fillcolor=desk)
        img = img.rotate(rng.choice([-1, 1]) * rng.uniform(2.5, 5.5), expand=True, fillcolor=desk, resample=Image.BICUBIC)
        light = Image.linear_gradient("L").rotate(rng.uniform(0, 360)).resize(img.size).point(lambda v: 150 + v * 105 // 255)
        img = ImageChops.multiply(img, Image.merge("RGB", [light] * 3))
        img = ImageEnhance.Contrast(img).enhance(rng.uniform(0.6, 0.75))
        noise = Image.frombytes("L", img.size, rng.randbytes(img.size[0] * img.size[1])).convert("RGB")
        img = Image.blend(img, noise, 0.07).filter(ImageFilter.GaussianBlur(rng.uniform(1.0, 1.4)))
        img = img.resize((img.size[0] * 3 // 4, img.size[1] * 3 // 4), Image.BILINEAR)  # ~150 dpi
        jpg = io.BytesIO()
        img.save(jpg, "JPEG", quality=rng.randint(30, 40))
        pages.append(Image.open(jpg).convert("RGB"))
    pages[0].save(path, "PDF", resolution=100, save_all=True, append_images=pages[1:], creationDate=FIXED, modDate=FIXED)


def fax_scan(pdf, path, rng):
    """A fax: bitonal, coarse vertical resolution, slight skew, speckles and a streak."""
    import pypdfium2 as pdfium
    from PIL import Image, ImageDraw

    pages = []
    for page in pdfium.PdfDocument(pdf):
        img = page.render(scale=2.2).to_pil().convert("L")
        img = img.rotate(rng.uniform(-1.8, 1.8), expand=True, fillcolor=255, resample=Image.BICUBIC)
        w, h = img.size
        img = img.resize((w, h * 6 // 10), Image.BILINEAR).resize((w, h), Image.NEAREST)  # coarse vertical resolution
        noise = Image.frombytes("L", img.size, rng.randbytes(w * h))
        img = Image.blend(img, noise, 0.10).point(lambda v: 255 if v > 190 else 0)
        draw = ImageDraw.Draw(img)
        for _ in range(int(w * h * 0.0004)):
            x, y = rng.randrange(w), rng.randrange(h)
            draw.point((x, y), 0)
        y = rng.randrange(h // 4, h)
        draw.line((0, y, w, y), fill=0, width=1)
        pages.append(img.convert("1"))
    pages[0].save(path, "PDF", resolution=158, save_all=True, append_images=pages[1:], creationDate=FIXED, modDate=FIXED)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    i = 0
    for case, n in CASES:
        for k in range(n):
            rng = random.Random(5000 + i)
            meta, cv, s, opts, rules = BUILDERS[case](k, i, rng)
            cid = f"hard_{i + 1:03d}"
            if opts is not None:
                meta["layout"] = opts.get("layout", "one_col")
            pdf = pdf_bytes(s, meta["layout"]) if opts is None else render(s, opts)
            scan = next((e for e in meta["edge_cases"] if e in ("phone_photo", "fax_scan")), None)
            if scan:
                meta["format"] = "scanned"
                {"phone_photo": phone_photo, "fax_scan": fax_scan}[scan](pdf, OUT / f"{cid}.pdf", rng)
            else:
                (OUT / f"{cid}.pdf").write_bytes(pdf)
            gold = {"id": cid, "meta": meta, "cv": cv.model_dump()} | ({"rules": rules} if rules else {})
            (OUT / f"{cid}.json").write_text(json.dumps(gold, ensure_ascii=False, indent=2), encoding="utf-8")
            i += 1
    print(f"wrote {i} CVs to {OUT}/")


if __name__ == "__main__":
    main()
