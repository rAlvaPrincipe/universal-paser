import sys
import os

from dotenv import load_dotenv
load_dotenv()

from src.agent import get_config
from src.doc_parser import build_tree, print_tree


def main():
    args = sys.argv[1:]
    if not args or args[0] in ("-h", "--help"):
        print("Usage: python main.py <pdf_path> [--refresh] [--no-body] [--body-snippet N]")
        sys.exit(0)

    pdf_path = args[0]
    force = "--refresh" in args
    include_body = "--no-body" not in args

    body_snippet = 300
    if "--body-snippet" in args:
        idx = args.index("--body-snippet")
        body_snippet = int(args[idx + 1])

    if not os.path.exists(pdf_path):
        print(f"Error: file not found: {pdf_path}")
        sys.exit(1)

    config = get_config(pdf_path, force=force, include_body=include_body, body_snippet=body_snippet)
    roots = build_tree(pdf_path, config)
    print_tree(roots)


if __name__ == "__main__":
    main()
