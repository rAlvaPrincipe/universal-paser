import re
import logging
from dataclasses import dataclass, field

logging.disable(logging.CRITICAL)

from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.datamodel.pipeline_options import PdfPipelineOptions

STRUCTURAL = {"section_header", "title", "chapter", "page_header"}


@dataclass
class Node:
    text: str
    label: str
    depth: int
    children: list = field(default_factory=list)

    def all_text(self) -> str:
        """Text of this node + all descendants. Ready for graph generation."""
        parts = [self.text] + [c.all_text() for c in self.children]
        return "\n".join(filter(None, parts))


def _match_depth(text: str, rules: list[dict]) -> int | None:
    for rule in rules:
        pattern, rtype = rule["pattern"], rule.get("type", "prefix")
        if rtype == "prefix" and text.lower().startswith(pattern.lower()):
            return rule["depth"]
        if rtype == "regex" and re.match(pattern, text, re.IGNORECASE):
            return rule["depth"]
        if rtype == "exact" and text.strip().lower() == pattern.lower():
            return rule["depth"]
    return None


def build_tree(pdf_path: str, config: dict) -> list[Node]:
    opts = PdfPipelineOptions()
    opts.do_ocr = False
    opts.do_table_structure = False
    converter = DocumentConverter(
        format_options={"pdf": PdfFormatOption(pipeline_options=opts)}
    )
    doc = converter.convert(pdf_path).document

    rules = config["rules"]
    roots: list[Node] = []
    stack: list[tuple[int, Node]] = []

    for item, _ in doc.iterate_items():
        label = item.label.value if hasattr(item.label, "value") else str(item.label)
        if label not in STRUCTURAL:
            continue
        text = item.text.strip().replace("\n", " ") if getattr(item, "text", None) else ""
        if not text:
            continue

        depth = _match_depth(text, rules)
        if depth is None:
            continue

        node = Node(text=text, label=label, depth=depth)

        while stack and stack[-1][0] >= depth:
            stack.pop()

        if stack:
            stack[-1][1].children.append(node)
        else:
            roots.append(node)

        stack.append((depth, node))

    return roots


def print_tree(nodes: list[Node], indent: int = 0, _state: dict = None):
    if _state is None:
        _state = {"first": True}

    for node in nodes:
        if indent == 0 and _state["first"]:
            print(f"{'━' * 64}")
            print(f"  {node.text}")
            print(f"{'━' * 64}")
            _state["first"] = False
        elif indent == 0:
            print(f"\n  ┌─ {node.text}")
        else:
            prefix = "  " * (indent + 1)
            print(f"{prefix}└─ {node.text}")

        print_tree(node.children, indent + 1, _state)
