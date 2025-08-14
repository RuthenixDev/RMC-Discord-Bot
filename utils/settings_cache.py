import json
import os

SETTINGS_FILE = "settings.json"
_settings_cache = None  # Кэш настроек в памяти

def load_settings(force_reload=False):
    """Загружает настройки из кэша или файла (если force_reload=True)."""
    global _settings_cache

    if _settings_cache is None or force_reload:
        if not os.path.exists(SETTINGS_FILE):
            _settings_cache = {}
        else:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                _settings_cache = json.load(f)
    return _settings_cache

def save_settings(data):
    """Сохраняет данные в файл и обновляет кэш."""
    global _settings_cache
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
    _settings_cache = data

def reload_settings():
    """Принудительно перечитывает файл и обновляет кэш."""
    return load_settings(force_reload=True)
