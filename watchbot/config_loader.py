from __future__ import annotations
import os
import re
import yaml
from watchbot.models import TargetWatch


def _expand_env(value: str) -> str:
    return re.sub(r'\$\{(\w+)\}', lambda m: os.environ.get(m.group(1), m.group(0)), value)


def _expand_dict(d: dict) -> dict:
    result = {}
    for k, v in d.items():
        if isinstance(v, str):
            result[k] = _expand_env(v)
        elif isinstance(v, dict):
            result[k] = _expand_dict(v)
        elif isinstance(v, list):
            result[k] = [_expand_env(i) if isinstance(i, str) else i for i in v]
        else:
            result[k] = v
    return result


def load_watches(path: str = "config/watches.yaml") -> list[TargetWatch]:
    with open(path) as f:
        data = yaml.safe_load(f)
    watches = []
    for w in data.get("watches", []):
        watches.append(TargetWatch(
            brand=w["brand"],
            model=w["model"],
            reference=w["reference"],
            aliases=w.get("aliases", []),
            prefer_full_set=w.get("prefer_full_set", False),
        ))
    return watches


def load_settings(path: str = "config/settings.yaml") -> dict:
    with open(path) as f:
        raw = yaml.safe_load(f)
    return _expand_dict(raw)
