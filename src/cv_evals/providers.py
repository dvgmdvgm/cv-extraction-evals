"""One thin adapter per provider, all with the same shape:

    call(model_id, system, text, schema, pdf_bytes | None) -> (parsed schema instance, input_tokens, output_tokens)

PDFs go to every provider as native document input (this covers the scanned ones too);
DOCX is not accepted natively by any of them, so it is sent as extracted text.
"""

import base64
import hashlib
import json
import os
from pathlib import Path

from .schema import CV, PROMPT

# name: (provider, model id, USD per 1M input tokens, USD per 1M output tokens).
# Standard list prices checked 2026-10-07. Thinking/reasoning tokens are billed as output.
MODELS = {
    "gemini-3.8-flash": ("gemini", "gemini-3.8-flash", 0.75, 3.75),  # intro price until 2026-12-31
    "gemini-3.1-pro": ("gemini", "gemini-3.1-pro-preview", 2.00, 12.00),
    "claude-haiku-4.5": ("anthropic", "claude-haiku-4-5", 1.00, 5.00),
    "claude-sonnet-5.5": ("anthropic", "claude-sonnet-5-5", 2.00, 10.00),
    "gpt-6-luna": ("openai", "gpt-6-luna", 0.10, 0.50),
    "gpt-6.1-sol": ("openai", "gpt-6.1-sol", 2.00, 10.00),
    "fake": ("fake", "fake", 0.0, 0.0),  # offline dry run, see fake_extract()
}
KEYS = {"gemini": "GEMINI_API_KEY", "anthropic": "ANTHROPIC_API_KEY", "openai": "OPENAI_API_KEY"}
MAX_OUTPUT_TOKENS = 16000


def call_anthropic(model, system, text, schema, pdf=None):
    import anthropic

    content = [{"type": "document", "source": {"type": "base64", "media_type": "application/pdf",
                                               "data": base64.b64encode(pdf).decode()}}] if pdf else []
    content.append({"type": "text", "text": text})
    r = anthropic.Anthropic().messages.parse(model=model, max_tokens=MAX_OUTPUT_TOKENS, system=system,
                                             messages=[{"role": "user", "content": content}], output_format=schema)
    if r.parsed_output is None:
        raise ValueError(f"no parsed output (stop_reason={r.stop_reason})")
    return r.parsed_output, r.usage.input_tokens, r.usage.output_tokens


def call_openai(model, system, text, schema, pdf=None):
    import openai

    content = [{"type": "input_file", "filename": "cv.pdf",
                "file_data": "data:application/pdf;base64," + base64.b64encode(pdf).decode()}] if pdf else []
    content.append({"type": "input_text", "text": text})
    r = openai.OpenAI().responses.parse(model=model, instructions=system, max_output_tokens=MAX_OUTPUT_TOKENS,
                                        input=[{"role": "user", "content": content}], text_format=schema)
    if r.output_parsed is None:
        raise ValueError(f"no parsed output (status={r.status})")
    return r.output_parsed, r.usage.input_tokens, r.usage.output_tokens


def call_gemini(model, system, text, schema, pdf=None):
    from google import genai
    from google.genai import types

    parts = [types.Part.from_bytes(data=pdf, mime_type="application/pdf")] if pdf else []
    parts.append(text)
    r = genai.Client().models.generate_content(
        model=model, contents=parts,
        config=types.GenerateContentConfig(system_instruction=system, response_mime_type="application/json",
                                           response_schema=schema, max_output_tokens=MAX_OUTPUT_TOKENS,
                                           automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True)))
    u = r.usage_metadata
    return schema.model_validate_json(r.text), u.prompt_token_count, (u.candidates_token_count or 0) + (u.thoughts_token_count or 0)


CALLS = {"anthropic": call_anthropic, "openai": call_openai, "gemini": call_gemini}


def available_models():
    """Models whose provider key is set, and {provider: reason} for the rest."""
    have = [m for m, (prov, *_) in MODELS.items() if prov in KEYS and os.environ.get(KEYS[prov])]
    skipped = {p: f"{k} not set" for p, k in KEYS.items() if not os.environ.get(k)}
    return have, skipped


def cost(model, tokens_in, tokens_out):
    _, _, p_in, p_out = MODELS[model]
    return (tokens_in * p_in + tokens_out * p_out) / 1e6


def complete(model, system, text, schema, pdf=None):
    """Call `model` by its name in MODELS. Returns (parsed, tokens_in, tokens_out)."""
    provider, model_id, *_ = MODELS[model]
    return CALLS[provider](model_id, system, text, schema, pdf)


def docx_text(path):
    import docx

    lines = []
    for block in docx.Document(path).iter_inner_content():
        if hasattr(block, "rows"):  # table: read cell by cell (two-column layouts)
            lines += [p.text for row in block.rows for cell in row.cells for p in cell.paragraphs]
        else:
            lines.append(block.text)
    return "\n".join(l for l in lines if l.strip())


def extract(model, doc: Path):
    """Extract a CV from a .pdf or .docx file. Returns (CV, tokens_in, tokens_out)."""
    if MODELS[model][0] == "fake":
        return fake_extract(doc)
    if doc.suffix == ".pdf":
        return complete(model, PROMPT, "Extract the CV in the attached PDF.", CV, doc.read_bytes())
    return complete(model, PROMPT, "Extract this CV (text of a DOCX file):\n\n" + docx_text(doc), CV)


def fake_extract(doc: Path):
    """Offline stand-in for a model: the gold label with deterministic, realistic mistakes.
    Lets the whole pipeline (scoring, report, regression gate) run in CI with no keys."""
    gold = json.loads(doc.with_suffix(".json").read_text(encoding="utf-8"))
    cv = CV.model_validate(gold["cv"])
    h = int(hashlib.md5(doc.stem.encode()).hexdigest(), 16)
    if cv.phone and cv.phone.startswith("+34"):
        cv.phone = cv.phone[3:]  # national format: normalisation must still match
    if h % 3 == 0:
        cv.skills = cv.skills[:-1]
    if h % 4 == 0 and cv.experience:
        cv.experience[0].start = cv.experience[0].start[:4]  # lost the month
    if h % 5 == 0 and cv.current_title:
        cv.current_title = cv.current_title.upper().replace("SENIOR", "SR.")
    return cv, 0, 0
