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

def escape_markdown(text):
    """
    Escape Markdown-like syntax in the text while preserving URLs.
    """
    # First, we'll identify and temporarily replace URLs
    url_pattern = r'(https?://[^\s]+)'
    urls = re.findall(url_pattern, text)
    for i, url in enumerate(urls):
        placeholder = f'URLPLACEHOLDER{i}'
        text = text.replace(url, placeholder)
    
    # Now escape Markdown characters
    escape_chars = r'\\`*_{}[]()#+-.!'
    text = re.sub(f'([{re.escape(escape_chars)}])', r'\\\1', text)
    
    # Finally, replace URL placeholders with the original URLs
    for i, url in enumerate(urls):
        placeholder = f'URLPLACEHOLDER{i}'
        text = text.replace(placeholder, url)
    
    return text

def process_tasks(tasks):
    """
    Process tasks and their subtasks, maintaining correct hierarchy.
    """
    def process_task(task, indent=0):
        task_lines = []
        title = task.get('title', '').strip()
        if not title:
            return task_lines

        status = '- [x]' if task.get('status') == 'completed' else '- [ ]'
        escaped_title = escape_markdown(title)
        task_line = f"{'  ' * indent}{status} {escaped_title}\n"
        task_lines.append(task_line)

        # Process subtasks
        for subtask in tasks:
            if subtask.get('parent') == task['id']:
                task_lines.extend(process_task(subtask, indent + 1))

        return task_lines

    all_task_lines = []
    for task in tasks:
        if 'parent' not in task:
            all_task_lines.extend(process_task(task))

    return all_task_lines

def convert_google_tasks_to_obsidian(json_file_path, output_folder, include_completed=False, include_updated=False):
    """
    Convert Google Tasks JSON to Obsidian markdown files.
    
    :param json_file_path: Path to the input JSON file
    :param output_folder: Path to the output folder for markdown files
    :param include_completed: Whether to include completed tasks (default: False)
    :param include_updated: Whether to include "Updated" timestamps (default: False)
    """
    try:
        with open(json_file_path, 'r') as file:
            data = json.load(file)

        os.makedirs(output_folder, exist_ok=True)

        task_lists = data.get('items', [])

        for task_list in task_lists:
            list_title = task_list.get('title', 'Untitled List')
            tasks = task_list.get('items', [])

            if not include_completed:
                tasks = [task for task in tasks if task.get('status') != 'completed']

            sanitized_title = sanitize_filename(list_title)
            file_name = f"{sanitized_title}.md"
            file_path = os.path.join(output_folder, file_name)

            with open(file_path, 'w') as md_file:
                task_lines = process_tasks(tasks)
                md_file.writelines(task_lines)

                if include_updated:
                    for task in tasks:
                        updated = task.get('updated', '')
                        if updated:
                            md_file.write(f"Updated: {updated}\n")

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
# Set include_completed=True to include completed tasks
# Set include_updated=True to include "Updated" timestamps
convert_google_tasks_to_obsidian(json_file_path, output_folder, include_completed=False, include_updated=False)
