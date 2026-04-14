# pdf-structure

Parses the hierarchical structure of any PDF.  
An LLM agent infers document-specific rules once; subsequent runs are fully deterministic.

## Setup

```bash
pip install docling anthropic openai google-generativeai python-dotenv
cp .env.example .env   # fill in your key
```

## Usage

```bash
python main.py document.pdf            # infer rules + parse
python main.py document.pdf --refresh  # re-run agent (ignore cached config)
```

The agent generates `document.config.json` on first run and reuses it afterwards.

## Providers

Set `LLM_PROVIDER` in `.env`:

| Value | Key needed | Default model |
|---|---|---|
| `anthropic` (default) | `ANTHROPIC_API_KEY` | `claude-opus-4-6` |
| `openai` | `OPENAI_API_KEY` | `gpt-4o` |
| `gemini` | `GEMINI_API_KEY` | `gemini-1.5-pro` |

Override the model with `LLM_MODEL`.

## Graph (future)

`doc_parser.Node` already exposes `all_text()` — the concatenated text of a node and all its descendants — ready for graph generation.
