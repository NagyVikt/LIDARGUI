# data/project_manager.py

import json
import os
import logging
import time
from tkinter import messagebox, filedialog
import asyncio
import aiofiles

async def backup_file_async(file_path):
    """Asynchronously create a backup of the specified file."""
    if not os.path.isfile(file_path):
        return
    backup_path = f"{file_path}.backup.{int(time.time())}"
    try:
        async with aiofiles.open(file_path, 'rb') as src, aiofiles.open(backup_path, 'wb') as dst:
            content = await src.read()
            await dst.write(content)
        logging.info(f"Created backup of {file_path} at {backup_path}")
    except Exception as e:
        logging.error(f"Failed to create backup for {file_path}: {e}")

def backup_file(file_path):
    """Create a backup of the specified file."""
    # Synchronous version for compatibility
    if not os.path.isfile(file_path):
        return
    backup_path = f"{file_path}.backup.{int(time.time())}"
    try:
        with open(file_path, 'rb') as src, open(backup_path, 'wb') as dst:
            dst.write(src.read())
        logging.info(f"Created backup of {file_path} at {backup_path}")
    except Exception as e:
        logging.error(f"Failed to create backup for {file_path}: {e}")

def get_available_projects(master_json_path="projects.json"):
    """Retrieve available project mappings from the master JSON file."""
    if not os.path.exists(master_json_path):
        # Initialize an empty master project file if it doesn't exist
        with open(master_json_path, 'w') as file:
            json.dump({}, file, indent=4)
        logging.info(f"Created master project file: {master_json_path}")
        return []

    try:
        with open(master_json_path, 'r') as file:
            projects = json.load(file)
            project_names = [f"Project {key}" for key in projects.keys()]
            return project_names
    except json.JSONDecodeError as e:
        messagebox.showerror("JSON Error", f"Failed to parse master project file:\n{e}")
        logging.error(f"Master project JSON parsing error: {e}")
        return []
    except Exception as e:
        messagebox.showerror("Error", f"An error occurred while loading the master project file:\n{e}")
        logging.error(f"Error loading master project file: {e}")
        return []

def load_project_mapping_sync(selected_project, base_dir):
    """Synchronous function to load project mapping."""
    master_json_path = os.path.join(base_dir, "projects.json")
    try:
        with open(master_json_path, 'r') as file:
            projects = json.load(file)
    except Exception as e:
        messagebox.showerror("Error", f"Failed to load master project file:\n{e}")
        logging.error(f"Error loading master project file: {e}")
        return {}

    # Extract the project number from the selected project name
    project_number = ''.join(filter(str.isdigit, selected_project))
    if not project_number:
        messagebox.showerror("Invalid Project", "Selected project name does not contain a number.")
        logging.error("Selected project name does not contain a number.")
        return {}

    project_key = project_number  # Assuming the key in master JSON is the number
    if project_key not in projects:
        messagebox.showerror("Project Not Found", f"No project found with key: {project_key}")
        logging.error(f"No project found with key: {project_key}")
        return {}

    data_file = projects[project_key].get("FILE", "")
    if not data_file:
        messagebox.showerror("Invalid Project Entry", f"No 'FILE' field found for project {selected_project}.")
        logging.error(f"No 'FILE' field in project {selected_project}.")
        return {}

    # Resolve the relative path to an absolute path
    absolute_data_file = os.path.join(base_dir, data_file)

    # Load the data file specified in the 'FILE' field
    if not os.path.isfile(absolute_data_file):
        messagebox.showerror("File Not Found", f"Data file for {selected_project} not found at {absolute_data_file}.")
        logging.error(f"Data file not found: {absolute_data_file}")
        return {}

    try:
        with open(absolute_data_file, 'r') as file:
            data = json.load(file)
            logging.info(f"Loaded data from {absolute_data_file}")
            led_data = {}
            for regal_name, leds in data.items():
                for led_id, attributes in leds.items():
                    unique_led_key = f"{regal_name}_{led_id}"
                    led_data[unique_led_key] = {
                        'FILE': attributes.get('FILE', ''),
                        'selected': attributes.get('selected', False),
                        'order': attributes.get('order', None)
                    }
            return led_data
    except json.JSONDecodeError as e:
        messagebox.showerror("JSON Error", f"Failed to parse data file:\n{e}")
        logging.error(f"Data file JSON parsing error: {e}")
        return {}
    except Exception as e:
        messagebox.showerror("Error", f"An error occurred while loading the data file:\n{e}")
        logging.error(f"Error loading data file: {e}")
        return {}

async def load_project_mapping_async(selected_project, base_dir):
    """Asynchronously load project mapping."""
    return await asyncio.to_thread(load_project_mapping_sync, selected_project, base_dir)

async def save_project_json_async(selected_project, led_data, base_dir):
    """Asynchronously save the current LED data back to the project's JSON file."""
    if not selected_project:
        messagebox.showwarning("No Project Selected", "Please select a project before saving.")
        return

    project_number = ''.join(filter(str.isdigit, selected_project))
    if not project_number:
        messagebox.showerror("Invalid Project", "Selected project name does not contain a number.")
        logging.error("Selected project name does not contain a number.")
        return

    # Get the master project file
    master_json_path = os.path.join(base_dir, "projects.json")
    try:
        with open(master_json_path, 'r') as file:
            projects = json.load(file)
    except Exception as e:
        messagebox.showerror("Error", f"Failed to load master project file:\n{e}")
        logging.error(f"Error loading master project file: {e}")
        return

    project_key = project_number
    if project_key not in projects:
        messagebox.showerror("Project Not Found", f"No project found with key: {project_key}")
        logging.error(f"No project found with key: {project_key}")
        return

    data_file = projects[project_key].get("FILE", "")
    if not data_file:
        messagebox.showerror("Invalid Project Entry", f"No 'FILE' field found for project {selected_project}.")
        logging.error(f"No 'FILE' field in project {selected_project}.")
        return

    # Resolve the relative path to an absolute path
    json_file_path = os.path.join(base_dir, data_file)

    try:
        # Ensure the directory exists
        os.makedirs(os.path.dirname(json_file_path), exist_ok=True)

        # Backup the existing project JSON if it exists
        if os.path.isfile(json_file_path):
            await backup_file_async(json_file_path)

        # Reconstruct the JSON structure based on regals with relative paths
        json_data = {}
        for led_key, attributes in led_data.items():
            regal_name, led_id = led_key.split('_')
            if regal_name not in json_data:
                json_data[regal_name] = {}
            # Compute relative path if necessary
            file_path = attributes.get('FILE', '')
            absolute_file_path = os.path.join(base_dir, file_path)
            relative_file_path = os.path.relpath(absolute_file_path, base_dir)
            # Normalize path to use forward slashes
            relative_file_path = relative_file_path.replace("\\", "/")
            json_data[regal_name][led_id] = {
                'FILE': relative_file_path,
                'selected': attributes.get('selected', False),
                'order': attributes.get('order', None)
            }

        async with aiofiles.open(json_file_path, 'w', encoding='utf-8') as file:
            await file.write(json.dumps(json_data, indent=4, ensure_ascii=False))
        messagebox.showinfo("Success", f"Project data saved successfully to {json_file_path}.")
        logging.info(f"Saved project data to {json_file_path}")
    except Exception as e:
        messagebox.showerror("Error", f"An error occurred while saving the JSON file:\n{e}")
        logging.error(f"Error saving JSON file: {e}")