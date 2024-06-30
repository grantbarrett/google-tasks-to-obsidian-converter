import json
import os
import re
from unidecode import unidecode

def sanitize_filename(filename):
    """
    Sanitize the filename by converting non-ASCII characters and removing invalid characters.
    """
    filename = unidecode(filename)
    sanitized = re.sub(r'[<>:"/\\|?*]', '_', filename)
    sanitized = sanitized.strip('. ')
    return sanitized if sanitized else 'Untitled'

def process_tasks(tasks, parent_id=None, indent=0):
    """
    Recursively process tasks and their subtasks.
    """
    task_lines = []
    for task in tasks:
        if task.get('parent') != parent_id:
            continue
        
        title = task.get('title', '').strip()
        if not title:
            continue

        status = '- [x]' if task.get('status') == 'completed' else '- [ ]'
        task_line = f"{'  ' * indent}{status} {title}\n"
        task_lines.append(task_line)

        # Recursively process subtasks
        subtasks = process_tasks(tasks, task['id'], indent + 1)
        task_lines.extend(subtasks)

    return task_lines

def convert_google_tasks_to_obsidian(json_file_path, output_folder):
    """
    Convert Google Tasks JSON to Obsidian markdown files.
    
    :param json_file_path: Path to the input JSON file
    :param output_folder: Path to the output folder for markdown files
    """
    try:
        with open(json_file_path, 'r') as file:
            data = json.load(file)

        os.makedirs(output_folder, exist_ok=True)

        task_lists = data.get('items', [])

        for task_list in task_lists:
            list_title = task_list.get('title', 'Untitled List')
            tasks = task_list.get('items', [])

            sanitized_title = sanitize_filename(list_title)
            file_name = f"{sanitized_title}.md"
            file_path = os.path.join(output_folder, file_name)

            with open(file_path, 'w') as md_file:
                task_lines = process_tasks(tasks)
                md_file.writelines(task_lines)

            print(f"Conversion complete. Obsidian file created: {file_path}")

    except FileNotFoundError:
        print(f"Error: The file {json_file_path} was not found.")
    except json.JSONDecodeError:
        print(f"Error: The file {json_file_path} is not a valid JSON file.")
    except PermissionError:
        print(f"Error: Permission denied when trying to create or write to {output_folder}")
    except Exception as e:
        print(f"An unexpected error occurred: {str(e)}")

# Example usage with the provided file path
json_file_path = '/Users/grantbarrett/Desktop/Tasks.json'
output_folder = '/Users/grantbarrett/Documents/General'

# CHANGE HERE: Modify these paths to match your system
convert_google_tasks_to_obsidian(json_file_path, output_folder)
