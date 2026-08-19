import json
import os
import uuid
from datetime import datetime

import bpy


# -----------------------------------------------------------------------------
# Project Manager JSON storage
# -----------------------------------------------------------------------------


def get_data_dir():
    path = bpy.utils.user_resource('CONFIG', path="tsg", create=True)
    if not path:
        path = os.path.join(os.path.expanduser("~"), ".tsg")
        os.makedirs(path, exist_ok=True)
    return path


def get_projects_json_path():
    return os.path.join(get_data_dir(), "projects.json")


def _default_data():
    return {"projects": []}


def load_projects_data():
    path = get_projects_json_path()
    if not os.path.exists(path):
        data = _default_data()
        save_projects_data(data)
        return data

    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return _default_data()

    if not isinstance(data, dict):
        return _default_data()
    if not isinstance(data.get("projects"), list):
        data["projects"] = []

    changed = False
    for project in data["projects"]:
        if "id" not in project:
            project["id"] = str(uuid.uuid4())
            changed = True
        project.setdefault("name", "Unnamed Project")
        project.setdefault("folder_path", "")
        project.setdefault("status", "ACTIVE")
        project.setdefault("pinned", False)
        project.setdefault("created_at", None)
        project.setdefault("last_opened", None)

        # compatibility with the old lowercase values
        status = str(project.get("status", "ACTIVE")).upper()
        project["status"] = "ARCHIVED" if status == "ARCHIVED" else "ACTIVE"

    if changed:
        save_projects_data(data)
    return data


def save_projects_data(data):
    path = get_projects_json_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    temp_path = path + ".tmp"
    with open(temp_path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, ensure_ascii=False)
    os.replace(temp_path, path)


def get_current_time_string():
    return datetime.now().isoformat(timespec="seconds")


def normalize_path(path):
    if not path:
        return ""
    return os.path.normcase(os.path.realpath(bpy.path.abspath(path)))


def is_same_file(path_a, path_b):
    if not path_a or not path_b:
        return False
    return normalize_path(path_a) == normalize_path(path_b)


def get_latest_blend_file(folder_path):
    folder = bpy.path.abspath(folder_path)
    if not os.path.isdir(folder):
        return None

    candidates = []
    try:
        for filename in os.listdir(folder):
            if filename.lower().endswith(".blend"):
                full_path = os.path.join(folder, filename)
                if os.path.isfile(full_path):
                    candidates.append(full_path)
    except OSError:
        return None

    if not candidates:
        return None

    latest = max(candidates, key=os.path.getmtime)
    return {
        "path": latest,
        "mtime": os.path.getmtime(latest),
    }


def get_project_by_id(project_id):
    data = load_projects_data()
    for project in data.get("projects", []):
        if project.get("id") == project_id:
            return data, project
    return data, None
