"""
Baseline: ask GPT-4o-mini directly to produce the document tree.

Modes:
  --mode text   extract full text from PDF and pass as string
  --mode pdf    pass PDF pages as images (vision) — requires PyMuPDF: pip install pymupdf
"""

import sys
import os
import base64
import argparse
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

SYSTEM_PROMPT = """\
You are an expert document analyst.
Given a document, identify its hierarchical structure and produce a tree of headings only.
Format the output exactly like this example:

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Document Title
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  ┌─ Top-level section
    └─ Subsection
      └─ Sub-subsection

  ┌─ Another top-level section

Rules:
- include only structural headings, not body text or captions
- the first heading in the document gets the ━━━ style; all other top-level headings get ┌─
- indent each level with 2 additional spaces
- do not add any explanation or commentary, output only the tree\
"""

USER_PROMPT_TEXT = """\
Here is the text extracted from the PDF:

{text}

Produce the hierarchical tree of this document.\
"""

SYSTEM_PROMPT_CONFIG = """\
You are an expert document analyst.
Given the full text of a document, identify every structural heading and return ONLY a valid JSON array.
No explanation, no markdown fences — raw JSON only.\
"""

USER_PROMPT_CONFIG = """\
Here is the text extracted from the PDF:

{text}

List every structural heading in document order. Output ONLY a valid JSON array:
[
  {{"text": "exact heading text as it appears in the document", "depth": 0}},
  ...
]

Rules for "depth":
- depth 0 = top-level (document title, part, chapter, top-level section)
- depth increases by 1 for each nesting level
- for numeric dot notation: "1 Introduction" → 0, "1.1 Syntax" → 1, "1.1.1 Details" → 2

Rules for "text":
- copy the heading text exactly as it appears — do not paraphrase or shorten
- include the document title as the first entry at depth 0
- include every structural heading level observed in the document

Exclude: page headers/footers, author lines, journal/conference metadata, copyright notices, figure/table captions.\
"""

USER_PROMPT_PDF = "Produce the hierarchical tree of this document."


def _extract_text(pdf_path: str) -> str:
    from docling.document_converter import DocumentConverter, PdfFormatOption
    from docling.datamodel.pipeline_options import PdfPipelineOptions
    import logging
    logging.disable(logging.CRITICAL)

    opts = PdfPipelineOptions()
    opts.do_ocr = False
    opts.do_table_structure = False
    converter = DocumentConverter(format_options={"pdf": PdfFormatOption(pipeline_options=opts)})
    doc = converter.convert(pdf_path).document
    return doc.export_to_markdown()


def _pdf_to_images_b64(pdf_path: str) -> list[str]:
    try:
        import fitz
    except ImportError:
        print("Error: PDF mode requires PyMuPDF. Install it with: pip install pymupdf")
        sys.exit(1)

    pdf = fitz.open(pdf_path)
    images = []
    for page in pdf:
        pix = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5))
        images.append(base64.b64encode(pix.tobytes("png")).decode())
    return images


def run_text_mode(pdf_path: str) -> str:
    from openai import OpenAI
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    print("[baseline] Extracting text from PDF...")
    text = _extract_text(pdf_path)

    user_prompt = USER_PROMPT_TEXT.format(text=text)
    Path("baseline_prompt.txt").write_text(f"[SYSTEM]\n{SYSTEM_PROMPT}\n\n[USER]\n{user_prompt}")
    print("[baseline] Prompt saved → baseline_prompt.txt")

    print("[baseline] Asking GPT-4o-mini (text mode)...")
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
    )
    return resp.choices[0].message.content.strip()


def run_pdf_mode(pdf_path: str) -> str:
    from openai import OpenAI
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    print("[baseline] Converting PDF pages to images...")
    images = _pdf_to_images_b64(pdf_path)
    print(f"[baseline] {len(images)} page(s) — asking GPT-4o-mini (pdf/vision mode)...")

    content = [{"type": "text", "text": USER_PROMPT_PDF}]
    for img_b64 in images:
        content.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/png;base64,{img_b64}", "detail": "low"},
        })

    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": content},
        ],
    )
    return resp.choices[0].message.content.strip()


def get_config_baseline(pdf_path: str) -> dict:
    """Return a config dict (same shape as agent) by sending full PDF text to the LLM.

    The LLM returns a flat JSON array of {text, depth} entries (one per heading).
    These are converted to exact-match rules so build_tree can use them directly.
    """
    import json, re
    from openai import OpenAI
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    print("[baseline] Extracting text from PDF...")
    text = _extract_text(pdf_path)
    user_prompt = USER_PROMPT_CONFIG.format(text=text)

    print("[baseline] Asking GPT-4o-mini for heading list...")
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT_CONFIG},
            {"role": "user", "content": user_prompt},
        ],
    )
    raw = resp.choices[0].message.content.strip()
    raw = re.sub(r"^```(?:json)?\n?", "", raw)
    raw = re.sub(r"\n?```$", "", raw)
    headings = json.loads(raw)  # list of {"text": ..., "depth": ...}

    rules = [
        {"pattern": h["text"], "type": "exact", "depth": h["depth"]}
        for h in headings
    ]
    config = {"domain": "baseline (exact headings from LLM)", "rules": rules, "notes": ""}
    print(f"[baseline] {len(rules)} headings identified")
    return config


def main():
    parser = argparse.ArgumentParser(
        description="Baseline: LLM-only document tree (no docling structure analysis)"
    )
    parser.add_argument("pdf", help="Path to the PDF file")
    parser.add_argument(
        "--mode",
        choices=["text", "pdf"],
        default="text",
        help="text: pass extracted text (default); pdf: pass pages as images (requires pymupdf)",
    )
    args = parser.parse_args()

    if not Path(args.pdf).exists():
        print(f"Error: file not found: {args.pdf}")
        sys.exit(1)

    if args.mode == "text":
        result = run_text_mode(args.pdf)
    else:
        result = run_pdf_mode(args.pdf)

    print("\n" + result)


if __name__ == "__main__":
    main()
