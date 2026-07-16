#!/usr/bin/env python3
"""Reject or remove saved Google Colab output that is unsafe in MyST/Thebe."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


COLAB_MIME_PREFIX = "application/vnd.google.colaboratory"
COLAB_HTML_MARKERS = ("google.colab", "colab-df-")


def tracked_notebooks() -> list[Path]:
    output = subprocess.check_output(["git", "ls-files", "*.ipynb"], text=True)
    return [
        Path(line)
        for line in output.splitlines()
        if "/.ipynb_checkpoints/" not in line
    ]


def html_text(value: object) -> str:
    if isinstance(value, list):
        return "".join(item for item in value if isinstance(item, str))
    return value if isinstance(value, str) else ""


def process_notebook(path: Path, fix: bool) -> list[str]:
    notebook = json.loads(path.read_text())
    issues: list[str] = []
    changed = False

    for cell_index, cell in enumerate(notebook.get("cells", [])):
        for output_index, output in enumerate(cell.get("outputs", [])):
            data = output.get("data")
            if not isinstance(data, dict):
                continue

            location = f"{path}: cell {cell_index}, output {output_index}"
            bad_mime_types = [
                mime_type
                for mime_type in data
                if mime_type.startswith(COLAB_MIME_PREFIX)
            ]
            for mime_type in bad_mime_types:
                issues.append(f"{location}: Colab-only MIME type {mime_type}")
                if fix:
                    del data[mime_type]
                    changed = True

            html = html_text(data.get("text/html"))
            if html and any(marker in html for marker in COLAB_HTML_MARKERS):
                issues.append(f"{location}: Colab-only executable HTML")
                if fix:
                    del data["text/html"]
                    changed = True

    if fix and changed:
        path.write_text(json.dumps(notebook, separators=(",", ":")))

    return issues


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--fix",
        action="store_true",
        help="Remove Colab-only MIME and HTML while preserving portable outputs.",
    )
    args = parser.parse_args()

    issues: list[str] = []
    for notebook_path in tracked_notebooks():
        issues.extend(process_notebook(notebook_path, args.fix))

    if issues:
        heading = "Removed unsafe Colab notebook output:" if args.fix else "Unsafe Colab notebook output:"
        print(heading)
        for issue in issues:
            print(f"- {issue}")
        return 0 if args.fix else 1

    print("No unsafe Colab notebook output found.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
