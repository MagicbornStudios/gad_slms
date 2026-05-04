from __future__ import annotations

from textual.widgets import Button

from . import icons


class VcsTag(Button):
    def __init__(self, target_id: str, route: str) -> None:
        del route
        super().__init__(
            f"{icons.CODE} id: {target_id}",
            id=f"vcs-tag-{target_id}",
            classes="vcs-id-tag",
            compact=True,
            flat=True,
        )
