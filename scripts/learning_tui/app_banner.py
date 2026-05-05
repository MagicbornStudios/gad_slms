from __future__ import annotations

from rich.text import Text
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

    def _main_banner_text(self) -> Text:
        line = Text()
        line.append(f"{icons.APP} ", style="bold #d8a84d")
        line.append(f"{self.label}", style="bold #ebcb8b")
        line.append("   ", style="")
        line.append("route ", style="dim #8b6914")
        line.append(self.route, style="#f5ecd8")
        line.append("   ", style="")
        line.append("mic ", style="dim #8b6914")
        line.append(self.device, style="#f5ecd8")
        line.append("   ", style="")
        line.append("Esc", style="dim #8b6914")
        line.append(" exits", style="#c4a574")
        return line

    def compose(self) -> ComposeResult:
        yield Static(self._main_banner_text(), id="app-banner-label")
        with Horizontal(id="app-banner-vcs-strip"):
            yield Static("", id="app-banner-vcs-status")
            yield Button(
                f"{icons.RECORD} click to record",
                id="vcs-quick-prompt",
                compact=True,
                disabled=not VCS_ENABLED,
            )
