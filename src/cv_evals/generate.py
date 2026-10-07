"""Synthetic CV generator.

Builds each CV as a gold JSON first, then renders it to PDF / scanned PDF / DOCX.
The JSON *is* the label, so there is no hand-labelling. All people, companies and
contacts are fictional (emails on example.* domains, UK phones in the Ofcom drama range).

Run with: uv run --extra render evals generate
"""

import io
import json
import random
import unicodedata
import zipfile
from datetime import date
from pathlib import Path
from xml.sax.saxutils import escape

from .schema import CV, Education, Job, Language

OUT = Path("data/cvs")
TODAY = date(2026, 10, 1)  # fixed so years_experience stays stable
N_CVS = 40

# --- pools ---------------------------------------------------------------------------

# Spanish titles use {o} -> o/a and {a} -> ""/a for grammatical gender.
ROLES = {
    "data": dict(
        en=["Junior Data Analyst", "Data Analyst", "Data Engineer", "Senior Data Engineer", "Lead Data Engineer"],
        es=["Analista de Datos Junior", "Analista de Datos", "Ingenier{o} de Datos", "Ingenier{o} de Datos Senior", "Responsable de Ingeniería de Datos"],
        skills=["Python", "SQL", "Apache Spark", "Airflow", "dbt", "Snowflake", "Kafka", "Docker", "AWS", "Tableau"],
        area=("data platforms", "plataformas de datos"),
        degree=("MSc Data Science", "Máster en Ciencia de Datos"),
    ),
    "backend": dict(
        en=["Junior Developer", "Software Developer", "Backend Engineer", "Senior Backend Engineer", "Staff Engineer"],
        es=["Desarrollador{a} Junior", "Desarrollador{a} de Software", "Desarrollador{a} Backend", "Desarrollador{a} Backend Senior", "Arquitect{o} de Software"],
        skills=["Java", "Spring Boot", "Go", "PostgreSQL", "Redis", "Kubernetes", "gRPC", "Terraform", "GCP", "REST APIs"],
        area=("distributed backend systems", "sistemas backend distribuidos"),
        degree=("BSc Computer Science", "Grado en Ingeniería Informática"),
    ),
    "frontend": dict(
        en=["Web Developer", "Frontend Developer", "Senior Frontend Developer", "Frontend Tech Lead", "Head of Frontend"],
        es=["Desarrollador{a} Web", "Desarrollador{a} Frontend", "Desarrollador{a} Frontend Senior", "Líder Técnico Frontend", "Responsable de Frontend"],
        skills=["TypeScript", "React", "Next.js", "CSS", "Vite", "Jest", "Storybook", "Figma", "Accessibility", "GraphQL"],
        area=("web applications", "aplicaciones web"),
        degree=("BSc Software Engineering", "Grado en Ingeniería del Software"),
    ),
    "product": dict(
        en=["Business Analyst", "Associate Product Manager", "Product Manager", "Senior Product Manager", "Head of Product"],
        es=["Analista de Negocio", "Product Manager Junior", "Product Manager", "Product Manager Senior", "Director{a} de Producto"],
        skills=["Roadmapping", "Jira", "A/B Testing", "Amplitude", "SQL", "User Research", "OKRs", "Stakeholder Management"],
        area=("B2B SaaS products", "productos SaaS B2B"),
        degree=("BA Business Administration", "Grado en Administración y Dirección de Empresas"),
    ),
    "marketing": dict(
        en=["Marketing Assistant", "Marketing Executive", "Digital Marketing Specialist", "Digital Marketing Manager", "Head of Growth"],
        es=["Asistente de Marketing", "Técnic{o} de Marketing", "Especialista en Marketing Digital", "Responsable de Marketing Digital", "Director{a} de Crecimiento"],
        skills=["SEO", "Google Ads", "HubSpot", "Google Analytics", "Copywriting", "Meta Ads", "Email Marketing", "Looker Studio"],
        area=("digital acquisition", "captación digital"),
        degree=("BA Marketing", "Grado en Marketing"),
    ),
    "finance": dict(
        en=["Accounts Assistant", "Accountant", "Senior Accountant", "Finance Manager", "Financial Controller"],
        es=["Auxiliar Contable", "Contable", "Contable Senior", "Responsable Financier{o}", "Controller Financier{o}"],
        skills=["IFRS", "SAP FI", "Excel", "Power BI", "Budgeting", "Month-end Close", "Audit", "Treasury"],
        area=("corporate finance", "finanzas corporativas"),
        degree=("BSc Accounting and Finance", "Grado en Finanzas y Contabilidad"),
    ),
    "ml": dict(
        en=["Research Assistant", "Machine Learning Engineer", "Senior Machine Learning Engineer", "ML Tech Lead", "Head of AI"],
        es=["Asistente de Investigación", "Ingenier{o} de Machine Learning", "Ingenier{o} de Machine Learning Senior", "Líder Técnico de ML", "Responsable de IA"],
        skills=["Python", "PyTorch", "scikit-learn", "MLflow", "LLM Evaluation", "NLP", "Docker", "Vertex AI", "Pandas"],
        area=("applied machine learning", "machine learning aplicado"),
        degree=("MSc Artificial Intelligence", "Máster en Inteligencia Artificial"),
    ),
}

EN_FIRST = ["Oliver", "Amelia", "Jack", "Isla", "Harry", "Freya", "Noah", "Grace", "Leo", "Ruby", "Ethan", "Chloe"]
EN_LAST = ["Whitcombe", "Harland", "Pennock", "Ashdown", "Brierley", "Calloway", "Thursby", "Fenwick", "Marlowe", "Kesteven"]
ES_FIRST_M = ["Javier", "Álvaro", "Pablo", "Sergio", "Diego", "Mateo"]
ES_FIRST_F = ["Lucía", "Marta", "Elena", "Irene", "Paula", "Nerea"]
ES_LAST = ["García", "Martínez", "Lozano", "Ferrer", "Navarro", "Iglesias", "Beltrán", "Cortés", "Soler", "Vidal"]

EN_COMPANIES = ["Northwind Analytics", "Bluepeak Software", "Harbor & Finch", "Quantel Systems", "Meridian Retail Group",
                "Copperleaf Health", "Tidewater Logistics", "Brightlane Media", "Stonebridge Capital", "Lumen Mobility"]
ES_COMPANIES = ["Grupo Alcorza", "Tecnologías Albera", "Datanova Ibérica", "Logística Sorolla", "Banca Mirador",
                "Viñedos Altamar", "Soluciones Turia", "Clínica Levante", "Editorial Maranta", "Movilidad Ebro"]
EN_CITIES = ["London, UK", "Manchester, UK", "Edinburgh, UK", "Bristol, UK", "Barcelona, Spain", "Madrid, Spain"]
ES_CITIES = ["Madrid, España", "Valencia, España", "Sevilla, España", "Bilbao, España", "Zaragoza, España", "Málaga, España"]
EN_UNIS = ["University of Manchester", "University of Leeds", "University of Bristol", "King's College London", "University of Glasgow"]
ES_UNIS = ["Universidad Politécnica de Valencia", "Universidad de Sevilla", "Universidad Complutense de Madrid",
           "Universidad de Zaragoza", "Universidad del País Vasco"]
EN_BACHELORS = ["BSc Mathematics", "BA Economics", "BSc Physics"]
ES_BACHELORS = ["Grado en Matemáticas", "Grado en Economía", "Grado en Física"]

LANG_NAMES_ES = {"English": "Inglés", "Spanish": "Español", "French": "Francés", "German": "Alemán",
                 "Italian": "Italiano", "Catalan": "Catalán", "Portuguese": "Portugués"}

MONTHS_EN = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
MONTHS_ES = ["ene.", "feb.", "mar.", "abr.", "may.", "jun.", "jul.", "ago.", "sept.", "oct.", "nov.", "dic."]
MONTHS_ES_FULL = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre",
                  "octubre", "noviembre", "diciembre"]

HEAD = {
    "en": dict(profile="Profile", exp="Experience", edu="Education", skills="Skills", langs="Languages",
               summary="{title} with {y} years of experience in {area}."),
    "es": dict(profile="Perfil", exp="Experiencia profesional", edu="Formación", skills="Habilidades", langs="Idiomas",
               summary="Profesional con {y} años de experiencia en {area}."),
}
BULLETS = {
    "en": ["Owned delivery of a cross-team project used by {n}k customers.", "Cut processing time by {n}% by redesigning a core workflow.",
           "Mentored {n} junior colleagues.", "Introduced a weekly review process adopted by the whole department."],
    "es": ["Lideré un proyecto transversal usado por {n} mil clientes.", "Reduje un {n}% el tiempo de proceso rediseñando un flujo clave.",
           "Mentoricé a {n} compañeros junior.", "Implanté una revisión semanal adoptada por todo el departamento."],
}


# --- gold ----------------------------------------------------------------------------

def ascii_slug(s):
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower().replace(" ", "")


def plan(i):
    """Decide language, file format and edge cases for CV number i (deterministic)."""
    fmt, layout = ("pdf", "one_col") if i < 14 else ("pdf", "two_col") if i < 28 else \
        ("scanned", ["one_col", "two_col"][i % 2]) if i < 34 else ("docx", ["one_col", "two_col"][i % 2])
    edges = [e for e, hit in [("no_email", i % 8 == 3), ("two_phones", i % 8 == 5), ("year_only_dates", i % 10 == 7),
                              ("no_headline", i % 4 == 1), ("not_currently_employed", i % 9 == 4)] if hit]
    return dict(lang="en" if i % 2 == 0 else "es", format=fmt, layout=layout, edge_cases=edges)


def make_gold(i, meta, rng):
    lang, es = meta["lang"], meta["lang"] == "es"
    role = ROLES[rng.choice(sorted(ROLES))]
    female = rng.random() < 0.5
    g = dict(o="a", a="a") if female else dict(o="o", a="")
    if es:
        name = f"{rng.choice(ES_FIRST_F if female else ES_FIRST_M)} {' '.join(rng.sample(ES_LAST, 2))}"
    else:
        name = f"{rng.choice(EN_FIRST)} {rng.choice(EN_LAST)}"

    # Jobs, built backwards from today. Month index = year*12 + month-1.
    n_jobs = rng.randint(2, 4)
    end = TODAY.year * 12 + TODAY.month - 1 - (rng.randint(2, 6) if "not_currently_employed" in meta["edge_cases"] else 0)
    level0 = rng.randint(0, 5 - n_jobs)
    companies = rng.sample(ES_COMPANIES if es else EN_COMPANIES, n_jobs)
    year_only = "year_only_dates" in meta["edge_cases"]
    ym = lambda m: f"{m // 12}" if year_only else f"{m // 12}-{m % 12 + 1:02d}"
    jobs, cur_end = [], None if "not_currently_employed" not in meta["edge_cases"] else end
    for k in range(n_jobs):  # most recent first
        start = end - rng.randint(12, 48)
        title = role[lang][level0 + n_jobs - 1 - k].format(**g)
        jobs.append(Job(company=companies[k], title=title, start=ym(start), end=ym(cur_end) if cur_end else None))
        end = start - rng.randint(0, 3)
        cur_end = end
    first_start = int(jobs[-1].start[:4]) * 12 + (int(jobs[-1].start[5:]) - 1 if not year_only else 0)
    years = (TODAY.year * 12 + TODAY.month - 1 - first_start) // 12

    langs = [Language(name="Spanish" if es else "English", level="native")]
    if es and rng.random() < 0.4:
        langs.append(Language(name="Catalan", level="native"))
    langs.append(Language(name="English" if es else "Spanish", level=rng.choice(["B1", "B2", "C1", "C2"])))
    if rng.random() < 0.5:
        langs.append(Language(name=rng.choice(["French", "German", "Italian", "Portuguese"]), level=rng.choice(["A2", "B1", "B2"])))

    edu = [Education(institution=rng.choice(ES_UNIS if es else EN_UNIS), degree=role["degree"][es])]
    if rng.random() < 0.5:
        edu.append(Education(institution=rng.choice(ES_UNIS if es else EN_UNIS),
                             degree=rng.choice(ES_BACHELORS if es else EN_BACHELORS)))

    first, *last = name.split()
    domain = rng.choice(["example.com", "example.org", "example.net"])
    phones = [f"+44 7700 900{rng.randint(0, 999):03d}" if not es else f"+34 6{rng.randint(10, 99)} {rng.randint(100, 999)} {rng.randint(100, 999)}"
              for _ in range(2)]
    return CV(
        name=name,
        email=None if "no_email" in meta["edge_cases"] else f"{ascii_slug(first)}.{ascii_slug(last[0])}@{domain}",
        phone=phones[0].replace(" ", ""),
        location=rng.choice(ES_CITIES if es else EN_CITIES),
        current_title=jobs[0].title,
        years_experience=years,
        skills=rng.sample(role["skills"], rng.randint(5, 7)),
        languages=langs,
        experience=jobs,
        education=edu,
    ), dict(role=role, phones=phones)


# --- surface text (how things look on the page) --------------------------------------

def fmt_phone(e164, lang, rng):
    if lang == "en":
        return rng.choice([lambda p: f"{p[:3]} {p[3:7]} {p[7:]}", lambda p: f"{p[:3]} (0){p[3:7]} {p[7:]}"])(e164)
    n = e164[3:]
    return rng.choice([f"+34 {n[:3]} {n[3:6]} {n[6:]}", f"{n[:3]} {n[3:5]} {n[5:7]} {n[7:]}", f"(+34) {n}", f"0034 {n[:3]} {n[3:6]} {n[6:]}"])


def date_style(lang, year_only, rng):
    present = rng.choice(["Present", "present", "now"] if lang == "en" else ["actualidad", "presente", "hoy"])
    sep = rng.choice([" – ", " - "] + ([" to "] if lang == "en" else [" a "]))
    if year_only:
        styles = [lambda y, m: f"{y}"]
    elif lang == "en":
        styles = [lambda y, m: f"{MONTHS_EN[m - 1]} {y}", lambda y, m: f"{m:02d}/{y}", lambda y, m: f"{y}-{m:02d}"]
    else:
        abbr = lambda y, m: f"{MONTHS_ES[m - 1]} {y}"  # "ene. 2021", weighted up: the classic parser trap
        styles = [abbr, abbr, lambda y, m: f"{m:02d}/{y}", lambda y, m: f"{MONTHS_ES_FULL[m - 1]} de {y}"]
    style = rng.choice(styles)

    def render(job):
        part = lambda d: present if d is None else style(int(d[:4]), int(d[5:]) if len(d) > 4 else 1)
        return f"{part(job.start)}{sep}{part(job.end)}"
    return render


def surface(cv, meta, extra, rng):
    """Everything the renderers need, already as display strings."""
    lang = meta["lang"]
    h = HEAD[lang]
    contact = []
    if cv.email:
        contact.append(rng.choice(["", "Email: ", "E-mail: "] if lang == "en" else ["", "Email: ", "Correo: "]) + cv.email)
    p1 = fmt_phone(extra["phones"][0].replace(" ", ""), lang, rng)
    if "two_phones" in meta["edge_cases"]:
        p2 = fmt_phone(extra["phones"][1].replace(" ", ""), lang, rng)
        contact.append(f"Mobile: {p1} / Office: {p2}" if lang == "en" else f"Móvil: {p1} / Fijo: {p2}")
    else:
        contact.append(p1)
    contact.append(cv.location)
    dates = date_style(lang, "year_only_dates" in meta["edge_cases"], rng)
    sep = rng.choice([" — ", ": ", " - "])
    native = "Native" if lang == "en" else rng.choice(["nativo", "lengua materna"])
    lang_line = lambda l: (l.name if lang == "en" else LANG_NAMES_ES[l.name]) + sep + (native if l.level == "native" else l.level)
    return dict(
        h=h,
        name=cv.name,
        headline=None if "no_headline" in meta["edge_cases"] else cv.current_title,
        contact=contact,
        summary=h["summary"].format(title=cv.current_title, y=cv.years_experience, area=extra["role"]["area"][lang == "es"]),
        jobs=[dict(title=j.title, company=j.company, dates=dates(j),
                   bullets=[b.format(n=rng.randint(2, 40)) for b in rng.sample(BULLETS[lang], 2)]) for j in cv.experience],
        edu=[f"{e.degree} — {e.institution}" for e in cv.education],
        skills=cv.skills,
        langs=[lang_line(l) for l in cv.languages],
    )


# --- renderers -----------------------------------------------------------------------

def pdf_bytes(s, layout):
    from reportlab import rl_config
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.platypus import BaseDocTemplate, Frame, FrameBreak, PageTemplate, Paragraph, Spacer

    rl_config.invariant = 1  # reproducible bytes (no timestamps)
    st = lambda size, bold=False, **kw: ParagraphStyle("x", fontName="Helvetica-Bold" if bold else "Helvetica",
                                                        fontSize=size, leading=size * 1.3, **kw)
    P = lambda text, style: Paragraph(escape(text), style)
    name, head, body, h2 = st(20, True), st(12, textColor=colors.HexColor("#444444")), st(9.5), st(11, True, spaceBefore=8, spaceAfter=3)
    small = st(8.5, textColor=colors.HexColor("#555555"))

    side = [P(s["name"], name)]
    if s["headline"]:
        side.append(P(s["headline"], head))
    side.append(Spacer(1, 4))
    main = []
    if layout == "one_col":
        side.append(P("  ·  ".join(s["contact"]), small))
        main_target = side
    else:
        side += [P(c, small) for c in s["contact"]]
        side += [P(s["h"]["skills"], h2)] + [P(k, body) for k in s["skills"]]
        side += [P(s["h"]["langs"], h2)] + [P(l, body) for l in s["langs"]]
        main_target = main
    main_target += [P(s["h"]["profile"], h2), P(s["summary"], body), P(s["h"]["exp"], h2)]
    for j in s["jobs"]:
        main_target += [Paragraph(f"<b>{escape(j['title'])}</b> — {escape(j['company'])}", body), P(j["dates"], small)]
        main_target += [P("• " + b, body) for b in j["bullets"]] + [Spacer(1, 4)]
    main_target += [P(s["h"]["edu"], h2)] + [P(e, body) for e in s["edu"]]
    if layout == "one_col":
        main_target += [P(s["h"]["skills"], h2), P(", ".join(s["skills"]), body),
                        P(s["h"]["langs"], h2), P("  ·  ".join(s["langs"]), body)]

    buf = io.BytesIO()
    W, H = A4
    if layout == "one_col":
        frames = [Frame(2 * cm, 2 * cm, W - 4 * cm, H - 4 * cm)]
        story = side
        deco = lambda c, d: None
    else:
        frames = [Frame(1.2 * cm, 1.5 * cm, 5.6 * cm, H - 3 * cm, id="side"), Frame(7.4 * cm, 1.5 * cm, W - 8.6 * cm, H - 3 * cm, id="main")]
        story = side + [FrameBreak()] + main

        def deco(c, d):
            c.setFillColor(colors.HexColor("#eef1f5"))
            c.rect(0, 0, 7.0 * cm, H, stroke=0, fill=1)
    doc = BaseDocTemplate(buf, pagesize=A4, title="CV")
    doc.addPageTemplates([PageTemplate(frames=frames, onPage=deco)])
    doc.build(story)
    return buf.getvalue()


def scan(pdf, path, rng):
    """Rasterise a PDF and degrade it so it looks like a phone scan: no text layer."""
    import pypdfium2 as pdfium
    from PIL import Image, ImageFilter

    pages = []
    for page in pdfium.PdfDocument(pdf):
        img = page.render(scale=1.4).to_pil().convert("L")
        img = img.rotate(rng.uniform(-1.5, 1.5), expand=True, fillcolor=245, resample=Image.BICUBIC)
        noise = Image.frombytes("L", img.size, rng.randbytes(img.size[0] * img.size[1]))  # seeded, unlike effect_noise
        img = Image.blend(img, noise, 0.08).filter(ImageFilter.GaussianBlur(0.6))
        pages.append(img)
    import time

    fixed = time.gmtime(1767225600)  # 2026-01-01, so re-rendering gives identical bytes
    pages[0].save(path, "PDF", resolution=100, save_all=True, append_images=pages[1:], creationDate=fixed, modDate=fixed)


def write_docx(s, layout, path):
    from docx import Document
    from docx.shared import Pt

    from datetime import datetime

    doc = Document()
    props = doc.core_properties
    props.author, props.created, props.modified = "synthetic", datetime(2026, 1, 1), datetime(2026, 1, 1)

    def para(cell, text, size=10, bold=False):
        p = cell.add_paragraph()
        r = p.add_run(text)
        r.bold, r.font.size = bold, Pt(size)

    para(doc, s["name"], 20, True)
    if s["headline"]:
        para(doc, s["headline"], 12)
    if layout == "one_col":
        para(doc, "  ·  ".join(s["contact"]), 9)
        left = right = doc
    else:
        table = doc.add_table(rows=1, cols=2)
        left, right = table.rows[0].cells
        for c in s["contact"]:
            para(left, c, 9)
    blocks_left = [(s["h"]["skills"], s["skills"]), (s["h"]["langs"], s["langs"])]
    para(right, s["h"]["profile"], 12, True)
    para(right, s["summary"])
    para(right, s["h"]["exp"], 12, True)
    for j in s["jobs"]:
        para(right, f"{j['title']} — {j['company']}", 10, True)
        para(right, j["dates"], 9)
        for b in j["bullets"]:
            para(right, "• " + b)
    para(right, s["h"]["edu"], 12, True)
    for e in s["edu"]:
        para(right, e)
    for title, items in blocks_left:
        para(left, title, 12, True)
        if layout == "one_col":
            para(left, ", ".join(items))
        else:
            for it in items:
                para(left, it)
    buf = io.BytesIO()
    doc.save(buf)
    # Rewrite the zip with fixed entry timestamps so re-rendering gives identical bytes.
    with zipfile.ZipFile(buf) as src, zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as dst:
        for item in src.infolist():
            dst.writestr(zipfile.ZipInfo(item.filename, date_time=(2026, 1, 1, 0, 0, 0)), src.read(item.filename),
                         compress_type=zipfile.ZIP_DEFLATED)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for i in range(N_CVS):
        rng = random.Random(1000 + i)
        meta = plan(i)
        cv, extra = make_gold(i, meta, rng)
        s = surface(cv, meta, extra, rng)
        cid = f"cv_{i + 1:03d}"
        if meta["format"] == "docx":
            write_docx(s, meta["layout"], OUT / f"{cid}.docx")
        elif meta["format"] == "scanned":
            scan(pdf_bytes(s, meta["layout"]), OUT / f"{cid}.pdf", rng)
        else:
            (OUT / f"{cid}.pdf").write_bytes(pdf_bytes(s, meta["layout"]))
        gold = {"id": cid, "meta": meta, "cv": cv.model_dump()}
        (OUT / f"{cid}.json").write_text(json.dumps(gold, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {N_CVS} CVs to {OUT}/")


if __name__ == "__main__":
    main()
