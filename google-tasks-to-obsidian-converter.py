# This script converts the JSON file created by a Google Takeouts export to Obsidian .md files in the given vault folder. Before running, change the values for json_file_path and output_folder. You can create your Google Tasks export file here: https://takeout.google.com/settings/takeout

import json
import os
from datetime import datetime

def convert_google_tasks_to_obsidian(json_file_path, output_folder):
    # Read the JSON file
    with open(json_file_path, 'r') as file:
        tasks_data = json.load(file)

    # Create output folder if it doesn't exist
    os.makedirs(output_folder, exist_ok=True)

    # Process each task list
    for task_list in tasks_data.get('items', []):
        list_title = task_list.get('title', 'Untitled List')
        tasks = task_list.get('items', [])

        # Create a markdown file for each task list
        file_name = f"{list_title.replace(' ', '_')}.md"
        
        # Split the list_title to get potential subdirectories
        path_parts = list_title.split('/')
        
        # Construct the full path, creating subdirectories as needed
        current_path = output_folder
        for part in path_parts[:-1]:  # Exclude the last part (file name)
            current_path = os.path.join(current_path, part)
            os.makedirs(current_path, exist_ok=True)
        
        file_path = os.path.join(current_path, f"{path_parts[-1].replace(' ', '_')}.md")

        with open(file_path, 'w') as md_file:
            md_file.write(f"# {path_parts[-1]}\n\n")

            # Process each task in the list
            for task in tasks:
                title = task.get('title', 'Untitled Task')
                status = '- [x]' if task.get('status') == 'completed' else '- [ ]'
                updated = task.get('updated', '')
                
                # Write task to file
                md_file.write(f"{status} {title}\n")
                
                if updated:
                    try:
                        formatted_date = datetime.fromisoformat(updated.replace('Z', '+00:00')).strftime("%Y-%m-%d %H:%M:%S")
                        md_file.write(f"   Updated: {formatted_date}\n")
                    except ValueError:
                        md_file.write(f"   Updated: {updated}\n")
                
                # Handle parent-child relationship
                if 'parent' in task:
                    md_file.write(f"   Parent: {task['parent']}\n")
                
                md_file.write("\n")

    print(f"Conversion complete. Obsidian files created in {output_folder}")

# Example usage with the provided file paths
json_file_path = '/your/path/to/input/Tasks.json'
output_folder = '/your/path/to/Obsidian/Vault'
convert_google_tasks_to_obsidian(json_file_path, output_folder)