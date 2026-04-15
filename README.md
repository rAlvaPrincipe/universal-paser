# universal-paser

Parses the hierarchical structure of any PDF into an interactive tree.

## How it works

Parsing a generic PDF is hard because every document uses different conventions — a thesis uses `1 > 1.1 > 1.1.1`, an EU regulation uses `CHAPTER > Article`, a technical manual uses `Part > Section`. No hardcoded rules work universally.

Two methods are available:

- **Agent**: docling extracts structural elements, the LLM infers matching rules with depth assignments, and the parser builds the tree deterministically. Each run is logged under `runs/`.
- **Baseline**: the full PDF text is sent directly to GPT-4o-mini, which returns a flat list of headings with their depths. These become exact-match rules fed into the same parser.

Both methods produce the same output: a tree of nodes, each with its heading text and the body paragraphs beneath it.

## Setup

```bash
pip install docling openai google-generativeai python-dotenv streamlit
cp .env.example .env   # fill in your API keys
```

## Usage

### Interactive app

```bash
streamlit run app.py
```

Upload a PDF, choose a method (Agent or Baseline), and explore the document tree. Expanding a heading reveals the body text under that section.

### CLI — Agent

```bash
python main.py document.pdf
python main.py document.pdf --no-body           # exclude body text from the LLM sample
python main.py document.pdf --body-snippet 150  # truncate body text to 150 chars (default: 300)
```

### CLI — Baseline

```bash
python baseline.py document.pdf                 # text mode (default)
python baseline.py document.pdf --mode pdf      # vision mode: send pages as images (requires pymupdf)
```
