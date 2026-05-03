from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Input, Static

from . import icons
from .models import VisualContextTarget
from .vcs_tag import VcsTag


class VcsFooter(Vertical):
    def __init__(self, targets: tuple[VisualContextTarget, ...], route: str) -> None:
        super().__init__(id="vcs-footer")
        self.targets = targets
        self.route = route

    def compose(self) -> ComposeResult:
        yield VcsTag("vcs-footer", self.route)
        yield VcsTag("vcs-footer-status", self.route)
        yield Static("", id="vcs-footer-status")
        yield Static("", id="vcs-speech-bridge", classes="vcs-live-line")
        yield Input(
            placeholder="Optional typed fallback.",
            id="vcs-recorder-input",
            disabled=True,
        )
        yield Static("", id="vcs-live-input", classes="vcs-live-line")
        with Horizontal(id="vcs-footer-actions"):
            yield Button(f"{icons.RECORD} Quick Prompt", id="vcs-quick-prompt", variant="warning")
            yield VcsTag("vcs-footer-actions", self.route)
            yield VcsTag("vcs-quick-prompt", self.route)
