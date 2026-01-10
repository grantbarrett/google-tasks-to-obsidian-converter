#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
google-tasks-to-obsidian-converter.py

Convert a Google Tasks Takeout JSON export to Markdown files suitable for Obsidian.

Highlights
- One file per task list (default) OR a single consolidated file (--single-file)
- Obsidian-locked formatting by default (--obsidian) including YAML frontmatter + tags
- Generic Markdown output available (--md)
- Preserves task notes (second line and beyond) and links metadata
- Includes created/updated timestamps
- Safe filename generation (prevents '/' and other illegal filename chars, incl. "'")
- Optional warnings/info output when titles are modified (--info)
- Dry-run mode to preview outputs without writing (--dry-run)
- Optional note collapsing (--collapse)
- NEW: Keep/skip completed tasks via --completed {skip,keep,only} (default: skip)
- NEW: Preserve hierarchical structure of tasks/subtasks (nested indentation)
- NEW: Skip empty/whitespace-only tasks via --clean

Dependency
- unidecode (install inside your venv):  pip install unidecode
"""

from __future__ import annotations

import argparse
import json
import re
import textwrap
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from unidecode import unidecode


# -----------------------------
# Filename / path safety
# -----------------------------

# Illegal on Windows; '/' breaks paths on Unix/macOS; "'" is annoying in shells/URLs.
_ILLEGAL_FILENAME_CHARS = r"[\/:*?\"<>|']"


def safe_filename(name: str) -> tuple[str, bool]:
    """
    Convert arbitrary text into a filesystem-safe filename.

    Returns (safe_name, was_modified).

    Example:
      "Richard's File" -> ("Richard_s_File", True)
    """
    original = name
    safe = unidecode(name).strip()
    safe = re.sub(_ILLEGAL_FILENAME_CHARS, "_", safe)
    safe = re.sub(r"\s+", "_", safe)
    safe = safe.strip("._")  # avoid awkward trailing dots/underscores
    if not safe:
        safe = "Untitled"
    return safe, (safe != original)


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
    """Collapse multi-line notes into a single line and truncate."""
    one_line = " / ".join([ln.strip() for ln in text.splitlines() if ln.strip()])
    one_line = re.sub(r"\s+", " ", one_line).strip()
    if len(one_line) > _COLLAPSE_MAX_CHARS:
        one_line = one_line[:_COLLAPSE_MAX_CHARS].rstrip() + "…"
    return one_line


def _derive_tags(task: Dict[str, Any]) -> List[str]:
    """Derive conservative Obsidian tags based on task metadata."""
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


def _is_effectively_empty_task(task: Dict[str, Any]) -> bool:
    """
    True if the task contains no meaningful content:
    - title empty/whitespace
    - notes empty/whitespace
    - no links
    """
    title = str(task.get("title", "")).strip()
    notes = str(task.get("notes", "") or "").strip()
    links = task.get("links") or []
    has_links = any(isinstance(l, dict) and str(l.get("link", "")).strip() for l in links)
    return (not title) and (not notes) and (not has_links)


def format_task(task: Dict[str, Any], fmt: FormatOptions, level: int = 0, clean: bool = False) -> str:
    """
    Format one task as Markdown.

    - Maintains task status using checkbox syntax: [ ] vs [x]
    - Supports nested indentation (level >= 0)

    If clean=True, tasks should already have been filtered; the function still
    behaves safely if called on an empty task.
    """
    lines: List[str] = []

    base_indent = "  " * level  # 2 spaces per nesting level
    meta_indent = base_indent + "  "  # metadata lines are indented under the bullet

    title = unidecode(str(task.get("title", "")).strip())
    if not title:
        title = "Untitled task"  # only used if --clean is NOT filtering it out

    status = str(task.get("status", "needsAction"))
    checkbox = "x" if status == "completed" else " "
    lines.append(f"{base_indent}- [{checkbox}] {title}")

    # Notes: must appear on 2nd line and beyond
    notes = str(task.get("notes", "") or "")
    if notes.strip():
        if fmt.collapse_notes:
            lines.append(f"{meta_indent}{unidecode(_collapse_text(notes))}")
        else:
            for ln in notes.strip().splitlines():
                ln = ln.strip()
                if ln:
                    lines.append(f"{meta_indent}{unidecode(ln)}")

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
            if desc:
                lines.append(f"{meta_indent}link:: {url} ({desc})")
            elif ltype:
                lines.append(f"{meta_indent}link:: {url} ({ltype})")
            else:
                lines.append(f"{meta_indent}link:: {url}")
        else:
            if desc:
                lines.append(f"{meta_indent}Link: {url} ({desc})")
            elif ltype:
                lines.append(f"{meta_indent}Link: {url} ({ltype})")
            else:
                lines.append(f"{meta_indent}Link: {url}")

    # Timestamps
    created_dt = _parse_google_rfc3339(str(task.get("created", "")).strip())
    updated_dt = _parse_google_rfc3339(str(task.get("updated", "")).strip())
    created_s = _fmt_dt(created_dt) if created_dt else ""
    updated_s = _fmt_dt(updated_dt) if updated_dt else ""

    if fmt.obsidian:
        if created_s:
            lines.append(f"{meta_indent}created:: {created_s}")
        if updated_s:
            lines.append(f"{meta_indent}updated:: {updated_s}")
        lines.append(f"{meta_indent}{' '.join(_derive_tags(task))}")
    else:
        if created_s:
            lines.append(f"{meta_indent}Created: {created_s}")
        if updated_s:
            lines.append(f"{meta_indent}Updated: {updated_s}")

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
    """Create a file header."""
    exported_s = _fmt_dt(exported_at.astimezone(timezone.utc))

    if fmt.obsidian:
        props: List[str] = [
            "---",
            "source: google-tasks",
            f"exported: {exported_s}",
            f"input_file: {str(input_path)}",
        ]
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

    # Generic Markdown
    if consolidated:
        return "# Google Tasks Export\n\n"
    if list_title:
        return f"# {list_title}\n\n"
    return ""


# -----------------------------
# Conversion logic
# -----------------------------

def _iter_tasklists(data: Dict[str, Any]) -> Iterable[Dict[str, Any]]:
    """Yield task list objects from the Takeout JSON structure."""
    for tl in data.get("items", []) or []:
        if isinstance(tl, dict):
            yield tl


def _ensure_output_parent(path: Path) -> None:
    """Create parent directories for a file path."""
    path.parent.mkdir(parents=True, exist_ok=True)


def _task_sort_key(task: Dict[str, Any], fallback_index: int) -> tuple:
    """
    Sort key to keep stable ordering:
    - Google Tasks may include 'position' (a sortable string)
    - otherwise use original appearance order
    """
    pos = task.get("position")
    if isinstance(pos, str) and pos:
        return (0, pos, fallback_index)
    return (1, "", fallback_index)


def _build_task_tree(
    tasks: List[Dict[str, Any]],
    *,
    completed_mode: str,
    clean: bool,
) -> List[Dict[str, Any]]:
    """
    Build a hierarchical forest of tasks based on id/parent relationships.

    Returns a list of root tasks, where each task may have an injected key:
      '_children': List[task]

    completed_mode:
      - 'skip' : exclude completed tasks
      - 'keep' : include both completed and incomplete tasks
      - 'only' : include only completed tasks

    clean:
      - if True, drop tasks that are empty/whitespace-only (title+notes+links empty)
    """
    filtered: List[Dict[str, Any]] = []
    for idx, t in enumerate(tasks):
        if not isinstance(t, dict):
            continue

        if clean and _is_effectively_empty_task(t):
            continue

        status = str(t.get("status", "needsAction"))
        is_completed = (status == "completed")

        if completed_mode == "skip" and is_completed:
            continue
        if completed_mode == "only" and not is_completed:
            continue

        # Store original ordering index for stable sorting
        t["_orig_index"] = idx
        t["_children"] = []
        filtered.append(t)

    by_id: Dict[str, Dict[str, Any]] = {}
    for t in filtered:
        tid = str(t.get("id", "")).strip()
        if tid:
            by_id[tid] = t

    roots: List[Dict[str, Any]] = []
    for t in filtered:
        parent_id = str(t.get("parent", "") or "").strip()
        if parent_id and parent_id in by_id:
            by_id[parent_id]["_children"].append(t)
        else:
            roots.append(t)

    def sort_recursive(node_list: List[Dict[str, Any]]) -> None:
        node_list.sort(key=lambda n: _task_sort_key(n, int(n.get("_orig_index", 0))))
        for n in node_list:
            sort_recursive(n.get("_children", []))

    sort_recursive(roots)
    return roots


def _render_task_tree(
    roots: List[Dict[str, Any]],
    fmt: FormatOptions,
    *,
    clean: bool,
    level: int = 0,
) -> str:
    """Render root nodes (each may contain '_children') into nested markdown."""
    parts: List[str] = []

    def walk(node: Dict[str, Any], lvl: int) -> None:
        parts.append(format_task(node, fmt, level=lvl, clean=clean))
        for child in node.get("_children", []) or []:
            if isinstance(child, dict):
                walk(child, lvl + 1)

    for r in roots:
        walk(r, level)

    return "\n\n".join(parts) + ("\n" if parts else "")


def convert_tasks(
    *,
    input_path: Path,
    output_path: Path,
    fmt: FormatOptions,
    single_file: bool,
    dry_run: bool,
    completed_mode: str,
    clean: bool,
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

            parts.append(f"## {section_title}\n")
            if fmt.obsidian:
                parts.append(f"task_list_id:: {list_id}\n")

            items = tl.get("items", []) or []
            tree_roots = _build_task_tree(items, completed_mode=completed_mode, clean=clean)
            parts.append(_render_task_tree(tree_roots, fmt, clean=clean, level=0))
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

        items = tl.get("items", []) or []
        tree_roots = _build_task_tree(items, completed_mode=completed_mode, clean=clean)
        body = _render_task_tree(tree_roots, fmt, clean=clean, level=0)

        content = header + body + ("\n" if body and not body.endswith("\n") else "")

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

          # Include completed tasks too
          python google-tasks-to-obsidian-converter.py -i Tasks.json --completed keep

          # Export ONLY completed tasks
          python google-tasks-to-obsidian-converter.py -i Tasks.json --completed only

          # Skip empty/whitespace-only tasks
          python google-tasks-to-obsidian-converter.py -i Tasks.json --clean

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
        - Nested tasks/subtasks are exported with indentation where parent/child relationships exist.
        - --completed controls whether completed tasks are exported:
            skip (default), keep, only
        - --clean drops tasks whose title, notes, and links are all empty/whitespace.
        """
    ).strip()

    parser = argparse.ArgumentParser(
        prog="google-tasks-to-obsidian-converter.py",
        usage=(
            "google-tasks-to-obsidian-converter.py [--help] "
            "[-i INPUT] [-o OUTPUT] "
            "[--obsidian (default) | --md] "
            "[--collapse] [--single-file] [--dry-run] [--info] "
            "[--completed {skip,keep,only}] [--clean]"
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
    parser.add_argument(
        "--completed",
        choices=["skip", "keep", "only"],
        default="skip",
        help="How to handle completed tasks: skip (default), keep, or only.",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Skip tasks that are empty/whitespace-only (title+notes+links).",
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
        completed_mode=str(args.completed),
        clean=bool(args.clean),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
