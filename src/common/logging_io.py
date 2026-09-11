import json
from dataclasses import asdict, is_dataclass
from pathlib import Path
import numpy as np


def serializable(value):
    if is_dataclass(value):
        return serializable(asdict(value))
    if isinstance(value, dict):
        return {str(k): serializable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set, np.ndarray)):
        return [serializable(v) for v in value]
    if isinstance(value, np.generic):
        return serializable(value.item())
    if isinstance(value, float) and not np.isfinite(value):
        return "Infinity" if value > 0 else "-Infinity" if value < 0 else None
    return value


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(serializable(value), ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def save_run(path, result):
    write_json(path, result)
    events_path = Path(path).with_suffix(".jsonl")
    with events_path.open("w", encoding="utf-8") as f:
        for event in result.events:
            f.write(json.dumps(serializable(event), ensure_ascii=False, allow_nan=False) + "\n")
