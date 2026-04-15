# universal-paser

Parses the hierarchical structure of any PDF into an interactive tree.

## How it works

Parsing a generic PDF is hard because every document uses different conventions — a thesis uses `1 > 1.1 > 1.1.1`, an EU regulation uses `CHAPTER > Article`, a technical manual uses `Part > Section`. No hardcoded rules work universally.

The approach separates two responsibilities:

1. **Inference** — an LLM reads the document and infers the hierarchy rules specific to that document
2. **Parsing** — deterministic code applies those rules to build the tree

Two methods are available, selectable from the app:

- **Agent**: docling extracts structural elements (`section_header`, `title`, etc.), the LLM infers `prefix`/`regex` rules with depth assignments, and the parser builds the tree. Each run logs the full LLM interaction under `runs/`.
- **Baseline**: the full PDF text is sent to GPT-4o-mini, which returns a flat list of headings with their depths. These become `exact`-match rules fed into the same parser.

Both methods produce the same data structure: a tree of nodes, each carrying its heading text and the body paragraphs beneath it.

## Setup

```bash
pip install docling openai google-generativeai python-dotenv streamlit
cp .env.example .env   # fill in your key
```

## Usage

### Interactive app

```bash
streamlit run app.py
```

Upload a PDF, choose a method, and explore the document tree. Expanding a heading reveals the body text under that section.

### CLI (agent method only)

```bash
python main.py document.pdf                     # infer rules + parse
python main.py document.pdf --no-body           # exclude body text from the LLM sample
python main.py document.pdf --body-snippet 150  # truncate body text to 150 chars (default: 300)
```

## Providers (agent method)

Set `LLM_PROVIDER` in `.env`:

| Value | Key needed | Default model |
|---|---|---|
| `anthropic` (default) | `ANTHROPIC_API_KEY` | `claude-opus-4-6` |
| `openai` | `OPENAI_API_KEY` | `gpt-4o` |
| `gemini` | `GEMINI_API_KEY` | `gemini-1.5-pro` |

Override the model with `LLM_MODEL`. The baseline always uses `OPENAI_API_KEY`.
