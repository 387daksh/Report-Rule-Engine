"""CLI for optional ColQwen/ColPali page retrieval from local images."""

from __future__ import annotations

import argparse
from pathlib import Path

from advanced_retrieval import ColQwenPageIndex


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True, help="Local ColQwen2/ColPali model directory")
    parser.add_argument("--images", nargs="+", required=True, help="Rendered report page images")
    parser.add_argument("--query", required=True)
    parser.add_argument("--device", default="cuda:0")
    args = parser.parse_args()
    index = ColQwenPageIndex.from_local(args.model, device=args.device)
    index.add(args.images)
    for path, score in index.search(args.query):
        print(f"{score:.6f}\t{path}")


if __name__ == "__main__":
    main()
