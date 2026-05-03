from __future__ import annotations

from dataclasses import dataclass
import shlex


@dataclass(frozen=True)
class Lesson:
    id: str
    title: str
    goal: str
    body: str
    command: tuple[str, ...] | None = None

    @property
    def command_text(self) -> str:
        if self.command is None:
            return "No command for this lesson. Read the notes and inspect the referenced files."
        return " ".join(shlex.quote(part) for part in self.command)


@dataclass(frozen=True)
class VisualContextTarget:
    id: str
    anchor: str
    source_hint: str
    source_file: str
