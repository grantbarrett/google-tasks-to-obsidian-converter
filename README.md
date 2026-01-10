# Google Tasks to Obsidian Converter

This Python script converts **Google Tasks** data (exported as JSON via Google Takeout) into **Markdown files** compatible with **[Obsidian](https://obsidian.md/)**, a knowledge management application.

The script has evolved from a simple converter into a fully featured, CLI-driven tool that preserves task structure, metadata, and status, while remaining safe and predictable to use.

---

## Features

- Processes Google Tasks JSON export files containing multiple task lists
- Converts each task list into a separate Markdown file (default)
- Optional single consolidated Markdown file
- **Obsidian-locked output by default**
  - YAML frontmatter
  - Metadata properties
  - Tags for filtering
- Optional **generic Markdown** output (no YAML, no tags)
- Maintains task status using checkbox syntax (`[ ]` / `[x]`)
- Preserves **hierarchical structure** of tasks and subtasks
- Handles **nested tasks with proper indentation**
- Includes **created** and **updated** timestamps
- Optional handling of completed tasks:
  - skip (default)
  - keep
  - only completed
- Optionally skips empty or whitespace-only tasks
- Sanitizes file names for filesystem safety
- Dry-run mode for safe previewing

---

## Requirements

- Python **3.10+**
- `unidecode` library

Install dependencies (recommended inside a virtual environment):

```bash
python -m venv .venv
source .venv/bin/activate
pip install unidecode
```

---

## Usage

```text
usage: google-tasks-to-obsidian-converter.py [--help]
       [-i INPUT] [-o OUTPUT]
       [--obsidian (default) | --md]
       [--collapse] [--single-file] [--dry-run] [--info]
       [--completed {skip,keep,only}] [--clean]
```
### Basic example

```bash
python google-tasks-to-obsidian-converter.py   -i ~/Takeout/Tasks/Tasks.json   -o ~/Obsidian/Tasks
```

---

## Workflow

1. Export your Google Tasks data using Google Takeout (instructions below).
2. Place the exported JSON file in a known location on your computer.
3. Decide which options to use for your export by studying the section "Command-line Options" below.
4. Run the script using: `python google-tasks-to-obsidian-converter.py -i YourInputFile -o YourDestinationDirectory [List Your Options]`


## How to Export Google Tasks Data

To obtain your Google Tasks data:

1. Go to [Google Takeout](https://takeout.google.com/).
2. Sign in to your Google account if you haven't already.
3. Deselect all products, then scroll down and select only "Tasks".
4. Click "Next step" and choose your delivery method (e.g., "Send download link via email").
5. Click "Create export".
6. Wait for the export to complete (you'll receive an email when it's ready).
7. Download the exported file and extract the JSON file containing your tasks data.

---

## Command-line Options

### Input / Output

| Option | Description |
|------|------------|
| `-i, --input` | Path to Google Tasks Takeout JSON file |
| `-o, --output` | Output directory (or file with `--single-file`) |

### Output Mode

| Option | Description |
|------|------------|
| `--obsidian` | Obsidian-locked formatting (default) |
| `--md` | Generic Markdown output |

### Task Handling

| Option | Description |
|------|------------|
| `--completed skip` | Skip completed tasks (default) |
| `--completed keep` | Include completed and open tasks |
| `--completed only` | Export only completed tasks |
| `--clean` | Skip tasks with empty titles, notes, and links |

### Other Options

| Option | Description |
|------|------------|
| `--collapse` | Collapse multi-line notes into one line |
| `--single-file` | Write all task lists into one Markdown file |
| `--dry-run` | Preview output without writing files |
| `--info` | Warn when task list titles are modified |


---

## Input Format

The script expects a JSON file with the following structure:

```json
{
  "kind": "tasks#taskLists",
  "items": [
    {
      "kind": "tasks#tasks",
      "id": "...",
      "title": "List Title 1",
      "updated": "...",
      "items": [
        {
          "kind": "tasks#task",
          "id": "...",
          "title": "Task Title",
          "updated": "...",
          "status": "needsAction",
          "parent": "..." // Optional
        },
        // More tasks...
      ]
    },
    // More task lists...
  ]
}
```

## Output

The script generates Markdown files in the specified output folder. Each task list becomes a separate `.md` file (unless --single-file was specified), with tasks represented as checkboxes. The hierarchical structure of tasks is maintained through indentation.

Example output:

```markdown
- [ ] Top-level Task 1
  - [ ] Subtask 1.1
  - [ ] Subtask 1.2
    - [ ] Sub-subtask 1.2.1
- [ ] Top-level Task 2
```

In **Obsidian mode**, files include YAML frontmatter and metadata:

```yaml
---
source: google-tasks
task_list: "Personal Tasks"
task_list_id: "MDg1MDkx..."
exported: 2026-01-10T06:15:00+00:00
---
```

---

## Filename Safety

Task list titles may contain characters that are illegal in filenames.

The script automatically replaces:

```
/ : * ? " < > | '
```

with underscores.

Example:

```
Richard's Tasks / Inbox
→ Richard_s_Tasks_Inbox_<id>.md
```

Use `--info` to print warnings when this occurs.

---

## Notes

- The script is designed for **command-line usage**; no in-file configuration is required
- Task hierarchy is preserved when parent/child relationships exist in the export
- The script is intentionally conservative and will not guess missing data

---

## License

See repository license.
