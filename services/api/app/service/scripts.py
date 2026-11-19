"""Bundled conversation scripts the test agent speaks.

The JSON files live with the agent (`services/agent/scripts/`), which reads the
same files to know what to say. This module reads them to list the choices and
to score transcripts against the reference text.
"""

import json
from dataclasses import dataclass
from pathlib import Path

from app.config import settings
from app.types import ScriptInfo

_REPO_ROOT = Path(__file__).resolve().parents[4]
_WORDS_PER_SECOND = 2.6  # espeak-ng at its default rate


@dataclass(frozen=True)
class Script:
    id: str
    title: str
    description: str
    lines: list[str]
    expected_phrases: list[str]
    pause_s: float

    @property
    def reference_text(self) -> str:
        return " ".join(self.lines)

    def info(self) -> ScriptInfo:
        words = len(self.reference_text.split())
        duration = words / _WORDS_PER_SECOND + self.pause_s * len(self.lines)
        return ScriptInfo(
            id=self.id,
            title=self.title,
            description=self.description,
            line_count=len(self.lines),
            expected_duration_s=round(duration, 1),
        )


class ScriptNotFound(LookupError):
    pass


def scripts_dir() -> Path:
    configured = Path(settings.session_scripts_dir)
    return configured if configured.is_absolute() else _REPO_ROOT / configured


def _load(path: Path) -> Script:
    data = json.loads(path.read_text(encoding="utf-8"))
    return Script(
        id=data["id"],
        title=data["title"],
        description=data.get("description", ""),
        lines=list(data["lines"]),
        expected_phrases=list(data.get("expected_phrases", [])),
        pause_s=float(data.get("pause_s", 0.6)),
    )


def list_scripts() -> list[Script]:
    directory = scripts_dir()
    if not directory.is_dir():
        return []
    return sorted((_load(p) for p in directory.glob("*.json")), key=lambda s: s.id)


def get_script(script_id: str) -> Script:
    for script in list_scripts():
        if script.id == script_id:
            return script
    raise ScriptNotFound(script_id)
