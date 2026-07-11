import json
import os

def load_config(path):
    if not os.path.exists(path):
        raise FileNotFoundError(f"The file {path} does not exist.")
    with open(path) as f:
        return json.load(f)

def save_config(path, config, ensure_indent=True):
    if not os.path.dirname(path):  # Check if path is just a filename without directory
        path = os.path.join(os.getcwd(), path)
    indent = None if not ensure_indent else 4
    with open(path, "w") as f:
        json.dump(config, f, indent=indent)

if __name__ == "__main__":
    try:
        cfg = load_config("config.json")
        print(cfg)
        save_config("new_config.json", cfg, ensure_indent=True)
    except Exception as e:
        print(e)