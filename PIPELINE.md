# Pipeline — come funziona

## Idea centrale

Il problema di parsare la struttura gerarchica di un PDF generico è che ogni documento ha convenzioni diverse: un testo legislativo usa `CHAPTER > Article`, un paper accademico usa `1 > 1.1 > 1.1.1`, un manuale tecnico usa `Part > Section > Subsection`. Nessuna regola hardcodata funziona universalmente.

La soluzione è separare due responsabilità:

1. **Inferenza** — un LLM osserva il documento e deduce le regole gerarchiche specifiche per quel documento
2. **Parsing** — uno script deterministico applica quelle regole a tutto il documento

L'inferenza avviene una sola volta e il risultato viene cachato. Il parsing è sempre deterministico e gratuito.

---

## Architettura

```
                    prima esecuzione
                   ┌─────────────────────────────────────────┐
                   │                                         │
  document.pdf ──► docling ──► elementi strutturali + body ──► LLM
                                                              │
                                                              ▼
                                                    outputs/document.config.json
                   └─────────────────────────────────────────┘

                    ogni esecuzione
                   ┌──────────────────────────────────────────────────┐
                   │                                                  │
  document.pdf ──► docling ──► tutti gli elementi ──► match su config ──► Node tree ──► stampa
                   └──────────────────────────────────────────────────┘
```

---

## Fase 1 — Inferenza (`src/agent.py`)

### Cosa fa docling qui

Docling legge il PDF e classifica ogni elemento con una `label`:
- **Strutturali**: `section_header`, `title`, `chapter`, `page_header`
- **Body**: `paragraph`, `text`, `list_item`, `caption`, `footnote`

Per ogni elemento restituisce anche un `docling_level` (livello interno basato sulla posizione nel documento) e il testo estratto.

### Cosa riceve l'LLM

Una lista di tutti gli elementi del documento in forma testuale:

```
[1]  label=title,          docling_level=1, text="REGULATION (EU) 2022/868..."
[2]  label=section_header, docling_level=1, text="CHAPTER I"
[3]  label=section_header, docling_level=1, text="General provisions"
[4]  label=paragraph,      docling_level=1, text="This Regulation lays down rules on..."
[5]  label=section_header, docling_level=1, text="Article 1"
...
```

Gli elementi strutturali vengono passati integralmente. Il testo body viene troncato a `--body-snippet` caratteri (default 300) per contenere i token. Con `--no-body` il body viene escluso del tutto.

### Cosa produce l'LLM

Un oggetto JSON con le regole di gerarchia, salvato in `outputs/`:

```json
{
  "domain": "EU regulation — data governance legislation",
  "rules": [
    { "pattern": "CHAPTER",  "type": "prefix", "depth": 0 },
    { "pattern": "Section",  "type": "prefix", "depth": 1 },
    { "pattern": "Article",  "type": "prefix", "depth": 2 }
  ],
  "notes": "Subtitles following Article headings are depth 3"
}
```

Il campo `domain` descrive la natura del documento. L'LLM lo usa internamente per applicare convenzioni di settore (diritto EU, paper accademico, ecc.) prima di definire le regole. Le `rules` sono ordinate dalla più specifica alla meno specifica: vince la prima che matcha.

### Caching

Il config viene salvato in `outputs/<nome_pdf>.config.json`. Nelle esecuzioni successive viene caricato direttamente — nessuna chiamata LLM, nessun costo. Per forzare una nuova inferenza: `--refresh`.

---

## Fase 2 — Parsing deterministico (`src/doc_parser.py`)

### Cosa fa docling qui

Stessa estrazione della fase 1, ma questa volta vengono considerati solo gli elementi strutturali di tutto il documento (nessun limite, nessun troncamento).

### Match delle regole

Per ogni elemento strutturale, viene applicato il config in ordine:
- `prefix` — controlla se il testo inizia con il pattern (case-insensitive)
- `regex` — applica un pattern Python con `re.IGNORECASE`
- `exact` — match esatto della stringa

Se nessuna regola matcha, l'elemento viene scartato silenziosamente.

### Costruzione del tree

Gli elementi matchati vengono assemblati in un albero di `Node` tramite uno stack:

```
stack = [(depth, node), ...]

per ogni nuovo nodo:
  - pop dallo stack tutti i nodi con depth >= depth corrente
  - se stack non vuoto → aggiungi come figlio del top
  - se stack vuoto → aggiungi come root
  - push del nuovo nodo
```

Questo garantisce che la struttura gerarchica sia corretta indipendentemente da salti di livello nel documento (es. da depth 0 a depth 2 senza un depth 1 intermedio).

### Struttura Node

```python
@dataclass
class Node:
    text: str       # testo dell'heading
    label: str      # label docling originale
    depth: int      # profondità nella gerarchia
    children: list  # nodi figli

    def all_text() -> str
        # testo di questo nodo + tutti i discendenti, concatenati
        # usato per la futura generazione del grafo
```

---

## Struttura del repository

```
├── main.py                  # entry point
├── src/
│   ├── agent.py             # fase 1: inferenza LLM
│   └── doc_parser.py        # fase 2: parsing deterministico
├── data/                    # PDF di input (gitignored)
├── outputs/                 # config JSON generati (gitignored)
├── .env                     # chiavi API (gitignored)
└── .env.example             # template
```

---

## Opzioni CLI

```
python main.py <pdf> [opzioni]

  --refresh          forza re-inferenza anche se il config esiste
  --no-body          passa all'LLM solo gli elementi strutturali (no body text)
  --body-snippet N   tronca il body a N caratteri per elemento (default: 300)
```

---

## Estensione futura: grafo

Il tree di `Node` è già la struttura dati corretta per un grafo. Ogni nodo ha:
- il proprio testo (`node.text`)
- il testo aggregato di sé stesso e tutti i discendenti (`node.all_text()`)
- i figli (`node.children`)

Per generare un grafo (es. NetworkX, GraphML, JSON-LD) basterà aggiungere una funzione `build_graph(roots)` in `doc_parser.py` che visita il tree e costruisce gli archi.
