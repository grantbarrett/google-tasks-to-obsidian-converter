# Google Tasks to Obsidian Converter

This Python script converts Google Tasks data (exported as JSON) into Markdown files compatible with Obsidian, a knowledge management application.

## Features

- Processes Google Tasks JSON export files
- Converts task lists into separate Markdown files
- Maintains task status (completed/not completed) using checkbox syntax
- Preserves task update timestamps
- Handles parent-child relationships between tasks
- Supports nested folder structures based on task list names
- Creates necessary subdirectories automatically

## Usage

1. Ensure you have Python 3.x installed on your system.
2. Place your Google Tasks JSON export file in a known location.
3. Modify the `json_file_path` and `output_folder` variables in the script to match your file locations.
4. Run the script using: `python google_tasks_to_obsidian.py`

## Input Format

The script expects a JSON file with the following structure:
```json
{
  "kind": "tasks#taskLists",
  "items": [
    {
      "kind": "tasks#tasks",
      "id": "...",
      "title": "List Title",
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

The script generates Markdown files in the specified output folder. Each task list becomes a separate `.md` file, with tasks represented as checkboxes. The file structure mirrors any nested folders in the task list titles.

Example output:
```markdown
# List Title

- [ ] Task 1
   Updated: 2023-06-29 14:30:00

- [x] Completed Task
   Updated: 2023-06-28 09:15:00
   Parent: parentTaskId

- [ ] Another Task
   Updated: 2023-06-29 16:45:00
```

## Customization

You can easily modify the script to change the output format or add additional task properties to the Markdown files.
