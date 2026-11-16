import json, os

_DIR = os.getenv("ANDROID_PRIVATE") or os.path.expanduser("~")
P = os.path.join(_DIR, ".scootunlock.json")


def load():
    try:
        with open(P) as f:
            return json.load(f)
    except Exception:
        return {}


def save(d):
    try:
        with open(P, "w") as f:
            json.dump(d, f, indent=2)
    except Exception:
        pass