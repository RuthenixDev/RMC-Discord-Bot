import json
from pathlib import Path

from utils import settings_cache as settings


STORAGE_FILE = Path("starboard_publications.json")
_storage_cache = None


def save_data(data):
    global _storage_cache
    temporary_file = STORAGE_FILE.with_suffix(".json.tmp")
    with temporary_file.open("w", encoding="utf-8") as file:
        json.dump(data, file, indent=4, ensure_ascii=False)
    temporary_file.replace(STORAGE_FILE)
    _storage_cache = data


def load_data():
    global _storage_cache
    if _storage_cache is not None:
        return _storage_cache

    if STORAGE_FILE.exists():
        with STORAGE_FILE.open(encoding="utf-8") as file:
            data = json.load(file)
    else:
        data = {}

    old_settings = settings.load_settings()
    keys = ("starboard_publications", "starboard_indexed_channels")
    if any(key in old_settings for key in keys):
        for channel_id, publications in old_settings.get(keys[0], {}).items():
            stored = data.setdefault(keys[0], {}).setdefault(channel_id, {})
            for source_id, post_id in publications.items():
                stored.setdefault(source_id, post_id)
        indexed = data.setdefault(keys[1], [])
        for channel_id in old_settings.get(keys[1], []):
            if channel_id not in indexed:
                indexed.append(channel_id)
        save_data(data)
        for key in keys:
            old_settings.pop(key, None)
        settings.save_settings(old_settings)

    _storage_cache = data
    return data
