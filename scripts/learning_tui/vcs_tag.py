from __future__ import annotations

from rich.text import Text
from textual.widgets import Button

from . import icons


class VcsTag(Button):
    def __init__(self, target_id: str, route: str) -> None:
        del route
        label = Text()
        label.append(f"{icons.CODE} ", style="bold #c9a227")
        label.append("id", style="dim #8b6914")
        label.append(" · ", style="dim #5c4a26")
        label.append(target_id, style="bold #ffd77a")
        super().__init__(
            label,
            id=f"vcs-tag-{target_id}",
            classes="vcs-id-tag",
            compact=True,
            flat=True,
        )
