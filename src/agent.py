import json
import os
import re
import logging
from datetime import datetime, timezone
from pathlib import Path

logging.disable(logging.CRITICAL)

RUNS_DIR = Path(__file__).parent.parent / "runs"


def _save_run(run_dir: Path, **artifacts):
    """Write each artifact to run_dir. Values are str, dict, or list."""
    run_dir.mkdir(parents=True, exist_ok=True)
    for name, value in artifacts.items():
        path = run_dir / name
        if isinstance(value, (dict, list)):
            path.write_text(json.dumps(value, indent=2, ensure_ascii=False))
        else:
            path.write_text(str(value))

from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.datamodel.pipeline_options import PdfPipelineOptions

STRUCTURAL = {"section_header", "title", "chapter", "page_header"}

_PROMPTS_DIR = Path(__file__).parent / "prompts"
SYSTEM_PROMPT = (_PROMPTS_DIR / "system.txt").read_text()
USER_PROMPT = (_PROMPTS_DIR / "user.txt").read_text()


BODY_LABELS = {"text", "paragraph", "list_item", "caption", "footnote"}


def _extract_sample(pdf_path: str, include_body: bool = True, body_snippet: int = 300) -> list[dict]:
    opts = PdfPipelineOptions()
    opts.do_ocr = False
    opts.do_table_structure = False
    converter = DocumentConverter(
        format_options={"pdf": PdfFormatOption(pipeline_options=opts)}
    )
    doc = converter.convert(pdf_path).document

    items = []
    for item, level in doc.iterate_items():
        label = item.label.value if hasattr(item.label, "value") else str(item.label)
        text = item.text.strip().replace("\n", " ") if getattr(item, "text", None) else ""
        if label in STRUCTURAL:
            items.append({"label": label, "docling_level": level, "text": text})
        elif include_body and label in BODY_LABELS and text:
            snippet = text[:body_snippet] + ("…" if len(text) > body_snippet else "")
            items.append({"label": label, "docling_level": level, "text": snippet})
    return items


def _call_llm(prompt: str) -> str:
    provider = os.getenv("LLM_PROVIDER", "anthropic").lower()

    if provider == "openai":
        from openai import OpenAI
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        resp = client.chat.completions.create(
            model=os.getenv("LLM_MODEL", "gpt-4o-mini"),
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
        )
        return resp.choices[0].message.content.strip()

    if provider == "gemini":
        import google.generativeai as genai
        genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
        model = genai.GenerativeModel(
            model_name=os.getenv("LLM_MODEL", "gemini-1.5-pro"),
            system_instruction=SYSTEM_PROMPT,
        )
        return model.generate_content(prompt).text.strip()

    raise ValueError(
        f"Unknown LLM_PROVIDER '{provider}'. Choose: anthropic | openai | gemini"
    )


def _parse_json(raw: str) -> dict:
    raw = re.sub(r"^```(?:json)?\n?", "", raw)
    raw = re.sub(r"\n?```$", "", raw)
    return json.loads(raw)


def infer_config(pdf_path: str, include_body: bool = True, body_snippet: int = 300) -> dict:
    provider = os.getenv("LLM_PROVIDER", "anthropic").lower()
    model = os.getenv("LLM_MODEL", {"anthropic": "claude-opus-4-6", "openai": "gpt-4o-mini", "gemini": "gemini-1.5-pro"}.get(provider, "unknown"))
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    run_dir = RUNS_DIR / f"{Path(pdf_path).stem}_{ts}"

    sample = _extract_sample(pdf_path, include_body=include_body, body_snippet=body_snippet)
    sample_text = "\n".join(
        f"[{i+1}] label={s['label']}, docling_level={s['docling_level']}, text=\"{s['text']}\""
        for i, s in enumerate(sample)
    )
    prompt = USER_PROMPT.replace("{sample}", sample_text)
    llm_raw = _call_llm(prompt)
    config = _parse_json(llm_raw)

    _save_run(
        run_dir,
        **{
            "meta.json": {
                "pdf": str(Path(pdf_path).resolve()),
                "timestamp": ts,
                "provider": provider,
                "model": model,
                "include_body": include_body,
                "body_snippet": body_snippet,
            },
            "sample.json": sample,
            "prompt.txt": f"[SYSTEM]\n{SYSTEM_PROMPT}\n\n[USER]\n{prompt}",
            "llm_raw.txt": llm_raw,
            "config.json": config,
        },
    )
    print(f"[agent] Run log  → {run_dir}")
    return config


OUTPUTS_DIR = Path(__file__).parent.parent / "outputs"


def get_config(pdf_path: str, force: bool = False, include_body: bool = True, body_snippet: int = 300) -> dict:
    OUTPUTS_DIR.mkdir(exist_ok=True)
    config_path = OUTPUTS_DIR / (Path(pdf_path).stem + ".config.json")

    if config_path.exists() and not force:
        with open(config_path) as f:
            return json.load(f)

    print(f"[agent] Inferring structure: {pdf_path}")
    config = infer_config(pdf_path, include_body=include_body, body_snippet=body_snippet)

    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)

    print(f"[agent] Domain  : {config['domain']}")
    if config.get("notes"):
        print(f"[agent] Notes   : {config['notes']}")
    print(f"[agent] Config  → {config_path}")
    return config
