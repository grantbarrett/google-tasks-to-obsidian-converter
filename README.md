# Google Tasks to Obsidian Converter

This Python script converts Google Tasks data (exported as JSON) into Markdown files compatible with Obsidian, a knowledge management application.

## Features

- Processes Google Tasks JSON export files containing multiple task lists
- Converts each task list into a separate Markdown file
- Optionally maintains task status (completed/not completed) and "Updated" timestamp using checkbox syntax.
- Preserves hierarchical structure of tasks and subtasks
- Handles nested tasks with proper indentation
- Skips empty tasks or tasks with only whitespace
- Sanitizes file names to ensure compatibility with various operating systems

## Requirements

- Python 3.x
- `unidecode` library (install with `pip install unidecode`)

## Usage

1. Export your Google Tasks data using Google Takeout (instructions below).
2. Place the exported JSON file in a known location on your computer.
3. Modify the `json_file_path` and `output_folder` variables in the script to match your file locations.
4. Run the script using: `python google_tasks_to_obsidian.py`

## How to Export Google Tasks Data

To obtain your Google Tasks data:

1. Go to [Google Takeout](https://takeout.google.com/).
2. Sign in to your Google account if you haven't already.
3. Deselect all products, then scroll down and select only "Tasks".
4. Click "Next step" and choose your delivery method (e.g., "Send download link via email").
5. Click "Create export".
6. Wait for the export to complete (you'll receive an email when it's ready).
7. Download the exported file and extract the JSON file containing your tasks data.

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

The script generates Markdown files in the specified output folder. Each task list becomes a separate `.md` file, with tasks represented as checkboxes. The hierarchical structure of tasks is maintained through indentation.

Example output:

```markdown
- [ ] Top-level Task 1
  - [ ] Subtask 1.1
  - [ ] Subtask 1.2
    - [ ] Sub-subtask 1.2.1
- [ ] Top-level Task 2
```

## Customization

You can easily modify the script to change the output format or add additional task properties to the Markdown files.

## Notes

- The script skips completed tasks and "Updated" timestamps by default. If you want to include completed tasks, remove or comment out the relevant check in the `convert_google_tasks_to_obsidian` function.
- Make sure you have write permissions for the output folder.

For any issues or feature requests, please open an issue on the GitHub repository.
