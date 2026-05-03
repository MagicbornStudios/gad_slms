from __future__ import annotations

from textual.widgets import Static

from . import icons
from .local_speech import describe_default_input


class AppBanner(Static):
    def __init__(self, route: str, label: str) -> None:
        device = describe_default_input()
        super().__init__(
            f"{icons.APP} {label}  |  route: {route}  |  mic: {device}  |  Esc exits",
            id="app-banner",
        )
