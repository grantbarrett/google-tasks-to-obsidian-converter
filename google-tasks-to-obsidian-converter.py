#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
google-tasks-to-obsidian-converter.py

Convert a Google Tasks Takeout JSON export to Markdown files suitable for Obsidian.

Key features
- One file per task list (default) OR a single consolidated file (--single-file)
- Obsidian-locked formatting by default (--obsidian) including YAML frontmatter + tags
- Generic Markdown output available (--md)
- Preserves task notes (second line and beyond) and links metadata
- Includes created/updated timestamps
- Safe filename generation (prevents "/" and other illegal filename chars)
- Optional warnings/info output when titles are modified (--info)
- Dry-run mode to preview outputs without writing (--dry-run)
- Optional note collapsing (--collapse)

Dependency
- unidecode (install inside your venv):  pip install unidecode
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import textwrap
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from unidecode import unidecode


# -----------------------------
# Filename / path safety
# -----------------------------

# Illegal on Windows; "/" breaks paths on Unix/macOS; "'" is annoying in shells/URLs
_ILLEGAL_FILENAME_CHARS = r"[\/:*?\"<>|']"


def safe_filename(name: str) -> tuple[str, bool]:
    """
    Convert arbitrary text into a filesystem-safe filename.

    Returns (safe_name, was_modified).
    
	Notes
    -----
    - Replaces characters illegal on Windows and problematic on Unix (including '/')
    - Collapses whitespace to underscores
    - Uses unidecode to normalize unicode for portability
    Example: "Richard's File" -> ("Richard_s_File", True)
    """
    original = name
    safe = unidecode(name).strip()
    safe = re.sub(_ILLEGAL_FILENAME_CHARS, "_", safe)
    safe = re.sub(r"\s+", "_", safe)
    safe = safe.strip("._")  # avoid awkward trailing dots/underscores
    if not safe:
        safe = "Untitled"
    return safe, (safe != original)


# Illegal on Windows; "/" also breaks paths on Unix/macOS.
_ILLEGAL_FILENAME_CHARS = r"[\/:*?\"<>|']"




# -----------------------------
# Date handling
# -----------------------------

def _parse_google_rfc3339(ts: str) -> Optional[datetime]:
    """
    Parse a Google-style RFC3339 timestamp like '2025-05-22T15:08:08.148505Z'.

    Returns a timezone-aware datetime in UTC, or None if parsing fails.
    """
    if not ts:
        return None
    try:
        # Google uses trailing 'Z' for UTC; Python's fromisoformat prefers '+00:00'
        if ts.endswith("Z"):
            ts = ts[:-1] + "+00:00"
        return datetime.fromisoformat(ts).astimezone(timezone.utc)
    except Exception:
        return None


def _fmt_dt(dt: Optional[datetime]) -> str:
    """
    Format a datetime consistently as ISO-8601 with timezone, e.g. 2026-01-10T06:15:00+00:00.
    """
    if dt is None:
        return ""
    return dt.isoformat(timespec="seconds")


# -----------------------------
# Output formatting
# -----------------------------

@dataclass
class FormatOptions:
    obsidian: bool = True
    collapse_notes: bool = False
    info: bool = False


# Collapse policy: single line, and truncate if too long.
_COLLAPSE_MAX_CHARS = 240


def _collapse_text(text: str) -> str:
    """
    Collapse multi-line notes into a single line and truncate to a sane length.

    This prevents extremely long notes from producing huge multi-line task blocks.
    """
    one_line = " / ".join([ln.strip() for ln in text.splitlines() if ln.strip()])
    one_line = re.sub(r"\s+", " ", one_line).strip()
    if len(one_line) > _COLLAPSE_MAX_CHARS:
        one_line = one_line[: _COLLAPSE_MAX_CHARS].rstrip() + "…"
    return one_line


def _derive_tags(task: Dict[str, Any]) -> List[str]:
    """
    Derive simple Obsidian tags based on task metadata (conservative, low-noise).
    """
    tags = ["#google-task"]
    links = task.get("links") or []
    link_types = {str(l.get("type", "")).lower() for l in links if isinstance(l, dict)}
    if "email" in link_types:
        tags.append("#email")
    if "chat" in link_types:
        tags.append("#chat")
    if "drive" in link_types:
        tags.append("#drive")
    return tags


def format_task(task: Dict[str, Any], fmt: FormatOptions) -> str:
    """
    Format one Google task as Markdown.

    Output structure (Obsidian-locked)
    - [ ] Title
      Notes line(s)...
      links:: <url> (desc)
      created:: <iso>
      updated:: <iso>
      #google-task #chat ...

    Output structure (Generic Markdown)
    - [ ] Title
      Notes line(s)...
      Link: <url> (desc)
      Created: <iso>
      Updated: <iso>
    """
    lines: List[str] = []

    title = unidecode(str(task.get("title", "")).strip())
    if not title:
        title = "Untitled task"
    status = task.get("status", "needsAction")
    checkbox = "x" if status == "completed" else " "
    lines.append(f"- [{checkbox}] {title}")

    # Notes: must appear on 2nd line and beyond
    notes = task.get("notes") or ""
    notes = str(notes)
    if notes.strip():
        if fmt.collapse_notes:
            lines.append(f"  {unidecode(_collapse_text(notes))}")
        else:
            for ln in notes.strip().splitlines():
                lines.append(f"  {unidecode(ln.strip())}")

    # Links / metadata
    links = task.get("links") or []
    for link in links:
        if not isinstance(link, dict):
            continue
        url = str(link.get("link", "")).strip()
        desc = str(link.get("desc", "")).strip()
        ltype = str(link.get("type", "")).strip()
        if not url:
            continue

        if fmt.obsidian:
            # Dataview-friendly key:: value format
            if desc:
                lines.append(f"  link:: {url} ({desc})")
            elif ltype:
                lines.append(f"  link:: {url} ({ltype})")
            else:
                lines.append(f"  link:: {url}")
        else:
            if desc:
                lines.append(f"  Link: {url} ({desc})")
            elif ltype:
                lines.append(f"  Link: {url} ({ltype})")
            else:
                lines.append(f"  Link: {url}")

    # Timestamps
    created_dt = _parse_google_rfc3339(str(task.get("created", "")).strip())
    updated_dt = _parse_google_rfc3339(str(task.get("updated", "")).strip())
    created_s = _fmt_dt(created_dt) if created_dt else ""
    updated_s = _fmt_dt(updated_dt) if updated_dt else ""

    if fmt.obsidian:
        if created_s:
            lines.append(f"  created:: {created_s}")
        if updated_s:
            lines.append(f"  updated:: {updated_s}")
        # Tags last (on their own indented line so Tasks plugin still sees the task)
        lines.append(f"  {' '.join(_derive_tags(task))}")
    else:
        if created_s:
            lines.append(f"  Created: {created_s}")
        if updated_s:
            lines.append(f"  Updated: {updated_s}")

    return "\n".join(lines)


def format_file_header(
    *,
    fmt: FormatOptions,
    exported_at: datetime,
    input_path: Path,
    list_title: Optional[str] = None,
    list_id: Optional[str] = None,
    consolidated: bool = False,
    list_count: Optional[int] = None,
) -> str:
    """
    Create a file header.

    Obsidian mode: YAML frontmatter with consistent properties.
    Generic mode: simple Markdown heading.
    """
    exported_s = _fmt_dt(exported_at.astimezone(timezone.utc))

    if fmt.obsidian:
        props: List[str] = ["---", "source: google-tasks", f"exported: {exported_s}", f"input_file: {str(input_path)}"]
        if consolidated and list_count is not None:
            props.append(f"lists: {list_count}")
        if list_title is not None:
            props.append(f'task_list: "{list_title}"')
        if list_id is not None:
            props.append(f'task_list_id: "{list_id}"')
        props.append("---")
        body_title = ""
        if list_title and not consolidated:
            body_title = f"# {list_title}\n"
        elif consolidated:
            body_title = "# Google Tasks Export\n"
        return "\n".join(props) + "\n\n" + body_title
    else:
        if consolidated:
            return "# Google Tasks Export\n\n"
        if list_title:
            return f"# {list_title}\n\n"
        return ""


# -----------------------------
# Conversion logic
# -----------------------------

def _iter_tasklists(data: Dict[str, Any]) -> Iterable[Dict[str, Any]]:
    """
    Yield task list objects from the Takeout JSON structure.
    """
    for tl in data.get("items", []) or []:
        if isinstance(tl, dict):
            yield tl


def _ensure_output_parent(path: Path) -> None:
    """
    Create parent directories for a file path.
    """
    path.parent.mkdir(parents=True, exist_ok=True)


def convert_tasks(
    *,
    input_path: Path,
    output_path: Path,
    fmt: FormatOptions,
    single_file: bool,
    dry_run: bool,
) -> None:
    """
    Convert the Takeout JSON into markdown outputs.

    - If single_file is False: output_path is treated as a directory.
    - If single_file is True: output_path is treated as a file if it ends with '.md';
      otherwise it's treated as a directory and a default filename is created inside it.
    """
    with input_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    exported_at = datetime.now(timezone.utc)
    tasklists = list(_iter_tasklists(data))

    if single_file:
        if output_path.suffix.lower() != ".md":
            output_path = output_path / "google-tasks-export.md"

        if dry_run:
            print(f"DRY-RUN: would write single file: {output_path}")
        else:
            _ensure_output_parent(output_path)

        # Build full content in memory (safe and simple at this scale)
        parts: List[str] = [
            format_file_header(
                fmt=fmt,
                exported_at=exported_at,
                input_path=input_path,
                consolidated=True,
                list_count=len(tasklists),
            )
        ]

        for tl in tasklists:
            raw_title = str(tl.get("title", "Unnamed List"))
            list_id = str(tl.get("id", "noid"))
            section_title = raw_title.strip() or "Unnamed List"

            if fmt.obsidian:
                parts.append(f"## {section_title}\n")
            else:
                parts.append(f"## {section_title}\n")

            # List-level context can be useful in a consolidated file
            if fmt.obsidian:
                parts.append(f"task_list_id:: {list_id}\n")

            for task in tl.get("items", []) or []:
                if not isinstance(task, dict):
                    continue
                if task.get("status") == "completed":
                    continue
                parts.append(format_task(task, fmt) + "\n")

            parts.append("\n")

        content = "".join(parts)

        if dry_run:
            print("DRY-RUN: content generation completed (not writing).")
        else:
            output_path.write_text(content, encoding="utf-8")

        return

    # Per-list files
    output_dir = output_path
    if dry_run:
        print(f"DRY-RUN: would write per-list files to directory: {output_dir}")
    else:
        output_dir.mkdir(parents=True, exist_ok=True)

    for tl in tasklists:
        raw_title = str(tl.get("title", "Unnamed List"))
        list_id = str(tl.get("id", "noid"))

        safe_title, modified = safe_filename(raw_title)
        if fmt.info and modified:
            print("INFO: task list title modified for filename safety")
            print(f'  original: "{raw_title}"')
            print(f'  safe:     "{safe_title}"')

        out_file = output_dir / f"{safe_title}_{list_id}.md"

        header = format_file_header(
            fmt=fmt,
            exported_at=exported_at,
            input_path=input_path,
            list_title=raw_title.strip() or "Unnamed List",
            list_id=list_id,
            consolidated=False,
        )

        body_parts: List[str] = [header]
        for task in tl.get("items", []) or []:
            if not isinstance(task, dict):
                continue
            if task.get("status") == "completed":
                continue
            body_parts.append(format_task(task, fmt) + "\n\n")

        content = "".join(body_parts)

        if dry_run:
            print(f"DRY-RUN: would write {out_file} ({len(content)} chars)")
        else:
            _ensure_output_parent(out_file)
            out_file.write_text(content, encoding="utf-8")


# -----------------------------
# CLI
# -----------------------------

def build_arg_parser() -> argparse.ArgumentParser:
    epilog = textwrap.dedent(
        """
        Examples

          # Default (Obsidian-locked): one file per task list into ./obsidian_output
          python google-tasks-to-obsidian-converter.py -i ~/Takeout/Tasks/Tasks.json

          # Choose output directory (per-list files)
          python google-tasks-to-obsidian-converter.py -i Tasks.json -o ~/Tasks-Converted

          # Single consolidated file (if -o is a directory, a default filename is used)
          python google-tasks-to-obsidian-converter.py -i Tasks.json -o ~/Tasks-Converted --single-file

          # Single consolidated file (explicit filename)
          python google-tasks-to-obsidian-converter.py -i Tasks.json -o ~/Tasks-Converted/tasks.md --single-file

          # Generic markdown (no YAML / tags)
          python google-tasks-to-obsidian-converter.py -i Tasks.json --md

          # Collapse long notes into a single line (and truncate)
          python google-tasks-to-obsidian-converter.py -i Tasks.json --collapse

          # Preview what would be generated without writing files
          python google-tasks-to-obsidian-converter.py -i Tasks.json --dry-run

          # Print warnings when a task list title is modified for filename safety
          python google-tasks-to-obsidian-converter.py -i Tasks.json --info

        Notes

        - --obsidian is the default output mode. Use --md if you want plain markdown.
        - In Obsidian mode, each output file starts with YAML frontmatter and each task ends with tags.
        - Tasks are exported as Markdown checkboxes compatible with Obsidian's Tasks plugin.
        """
    ).strip()

    parser = argparse.ArgumentParser(
        prog="google-tasks-to-obsidian-converter.py",
        usage=(
            "google-tasks-to-obsidian-converter.py [--help] "
            "[-i INPUT] [-o OUTPUT] "
            "[--obsidian (default) | --md] "
            "[--collapse] [--single-file] [--dry-run] [--info]"
        ),
        description="Convert Google Tasks Takeout JSON to Markdown (Obsidian-ready by default).",
        epilog=epilog,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "-i",
        "--input",
        default="/Users/richard/Google-Tasks-Takeout-2025-05-22/Tasks.json",
        help="Path to Google Tasks Takeout JSON file (default: %(default)s).",
    )
    parser.add_argument(
        "-o",
        "--output",
        default="./obsidian_output",
        help=(
            "Output path. In per-list mode, this is a directory. "
            "In --single-file mode, this may be a file path (.md) or a directory."
            " (default: %(default)s)"
        ),
    )

    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--obsidian",
        action="store_true",
        help="Generate Obsidian-locked output with YAML frontmatter and tags (default).",
    )
    mode.add_argument(
        "--md",
        action="store_true",
        help="Generate generic markdown without Obsidian YAML/tags.",
    )

    parser.add_argument(
        "--collapse",
        action="store_true",
        help=f"Collapse multi-line notes into one line and truncate at {_COLLAPSE_MAX_CHARS} chars.",
    )
    parser.add_argument(
        "--single-file",
        action="store_true",
        help="Write all task lists into a single consolidated Markdown file.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Do not write files; print what would be created.",
    )
    parser.add_argument(
        "--info",
        action="store_true",
        help="Print warnings/info when task list titles are modified for filename safety.",
    )

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    input_path = Path(args.input).expanduser()
    output_path = Path(args.output).expanduser()

    if not input_path.exists():
        parser.error(f"Input file not found: {input_path}")

    # Default is obsidian unless --md is explicitly requested.
    obsidian_mode = True
    if args.md:
        obsidian_mode = False
    if args.obsidian:
        obsidian_mode = True

    fmt = FormatOptions(
        obsidian=obsidian_mode,
        collapse_notes=bool(args.collapse),
        info=bool(args.info),
    )

    convert_tasks(
        input_path=input_path,
        output_path=output_path,
        fmt=fmt,
        single_file=bool(args.single_file),
        dry_run=bool(args.dry_run),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
