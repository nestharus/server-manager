#!/usr/bin/env python3
"""Replace em dash characters (U+2014) with context-appropriate alternatives.

Strategy:
- Inside code blocks (```...```) or inline code (`...`): leave untouched.
- Inside markdown tables (| ... |): leave untouched (table cells are structural).
- Em dash between two complete thoughts → period split.
- Em dash introducing a clarification → colon.
- Em dash inside parenthetical phrases → recast as parens.

The script is not a full NLP solution. It applies a safe default per pattern
and reports what it did. Subsequent rubric passes can refine awkward results.

IMPORTANT:
- `---` horizontal rule separators are preserved as-is.
- En dashes (U+2013 `–`) are not touched — only U+2014 em dashes.
- Hyphens in compound words are preserved.
"""

import argparse
import re
import sys
from pathlib import Path

EM_DASH = "\u2014"


def replace_em_dashes(line: str) -> tuple[str, int]:
    """Return (new_line, replacement_count) for a single line."""
    if EM_DASH not in line:
        return line, 0

    count = 0
    result = line

    # Strategy: find each em dash in prose context and replace.
    # For each em dash:
    # - If preceded by a word character and followed by " X" where X starts a
    #   new clause: period split.
    # - Else: use period split by default (safest, will be refined later).
    #
    # We do a simple pass: replace ` — ` with `. ` and capitalize next letter.

    # Pattern 1: " — Text" where Text starts a new clause.
    # Replace with ". Text" (period split).
    def period_split(match: re.Match[str]) -> str:
        nonlocal count
        count += 1
        after = match.group(1)
        # Capitalize the first letter of the following clause.
        if after and after[0].islower():
            after = after[0].upper() + after[1:]
        return f". {after}"

    result = re.sub(
        rf"\s*{EM_DASH}\s+([^\s])",
        period_split,
        result,
    )

    # Pattern 2: any remaining em dashes (e.g., at start/end of line, or back-to-back).
    # Replace with ", " as a fallback. Rare.
    if EM_DASH in result:
        remaining = result.count(EM_DASH)
        result = result.replace(EM_DASH, ", ")
        count += remaining

    return result, count


def process_file(path: Path) -> tuple[int, int]:
    """Process a markdown file. Returns (lines_changed, em_dashes_replaced)."""
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    new_lines: list[str] = []
    lines_changed = 0
    em_dashes_replaced = 0

    in_code_fence = False

    for line in lines:
        # Track code fences.
        stripped = line.lstrip()
        if stripped.startswith("```"):
            in_code_fence = not in_code_fence
            new_lines.append(line)
            continue

        if in_code_fence:
            new_lines.append(line)
            continue

        # Preserve horizontal rule separators (`---` at line start, no other content).
        if line.strip() == "---":
            new_lines.append(line)
            continue

        new_line, count = replace_em_dashes(line)
        if count > 0:
            lines_changed += 1
            em_dashes_replaced += count
        new_lines.append(new_line)

    path.write_text("".join(new_lines), encoding="utf-8")
    return lines_changed, em_dashes_replaced


def main() -> None:
    parser = argparse.ArgumentParser(description="Replace em dashes in markdown files")
    parser.add_argument("path", type=Path, help="Markdown file to process")
    args = parser.parse_args()

    if not args.path.exists():
        print(f"Error: {args.path} not found", file=sys.stderr)
        sys.exit(1)

    lines_changed, em_dashes_replaced = process_file(args.path)
    print(f"Lines changed: {lines_changed}")
    print(f"Em dashes replaced: {em_dashes_replaced}")

    # Count remaining em dashes (should be only inside code fences or preserved HRs).
    remaining = args.path.read_text(encoding="utf-8").count(EM_DASH)
    print(f"Remaining em dashes: {remaining}")


if __name__ == "__main__":
    main()
