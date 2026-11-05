"""The extraction target. The same model is the gold label format and the LLM output format."""

from pydantic import BaseModel

# Every field is required (nullable where it can be absent): strict structured-output
# modes (OpenAI, Anthropic) want all properties listed as required.


class Language(BaseModel):
    name: str  # English name, e.g. "Spanish"
    level: str  # CEFR "A1".."C2" or "native"


class Job(BaseModel):
    company: str
    title: str
    start: str | None  # "YYYY-MM", or "YYYY" when the CV gives only the year
    end: str | None  # same format; None = current job


class Education(BaseModel):
    institution: str
    degree: str


class CV(BaseModel):
    name: str
    email: str | None
    phone: str | None  # the one marked personal, else the first listed
    location: str | None
    current_title: str | None
    years_experience: int | None
    skills: list[str]
    languages: list[Language]
    experience: list[Job]
    education: list[Education]


PROMPT = """You extract structured data from a CV (résumé). Fill the JSON schema from the document.

Rules:
- Copy names, job titles, company names, institutions and the location as written in the CV. Do not translate them.
- email, phone, location: the candidate's own, null if the CV does not show them. If several emails or phone numbers are listed and one is marked personal or private, return that one; otherwise return the first one listed. Phone with its country code if shown.
- current_title: the professional title the candidate uses for themselves, usually right under the name. If there is none, the title of the most recent job.
- years_experience: total years of professional experience as stated in the CV, as an integer.
- skills: each item from the skills section, as written.
- languages: spoken languages only. name in English (e.g. "Spanish"); level as a CEFR level (A1, A2, B1, B2, C1, C2) or "native".
- experience: every job, most recent first. Dates as "YYYY-MM"; use "YYYY" if the CV gives only the year. end is null if the job is current.
- education: one entry per degree, with institution and degree as written.
- Never invent information that is not in the document."""
