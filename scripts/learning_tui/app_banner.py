from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Button, Static

from . import icons
from .local_speech import describe_default_input
from .settings import VCS_ENABLED


class AppBanner(Horizontal):
    def __init__(self, route: str, label: str) -> None:
        super().__init__(id="app-banner")
        self.route = route
        self.label = label
        self.device = describe_default_input()

    def compose(self) -> ComposeResult:
        yield Static(
            f"{icons.APP} {self.label} | route: {self.route} | mic: {self.device} | Esc exits",
            id="app-banner-label",
        )
        yield Static(f"{icons.VCS} VCS idle", id="app-banner-vcs-status")
        yield Button(
            f"{icons.RECORD} Quick Prompt",
            id="vcs-quick-prompt",
            compact=True,
            disabled=not VCS_ENABLED,
        )
