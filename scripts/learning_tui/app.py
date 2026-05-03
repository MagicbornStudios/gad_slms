from __future__ import annotations

from textual.app import App
from textual.binding import Binding

from .menu_screen import MenuScreen
from .settings import ROOT


class SLMLearningApp(App[None]):
    CSS_PATH = ROOT / "scripts/06_learning_tui.css"
    TITLE = "SLM Learning"
    SUB_TITLE = "Build a small reasoning language model step by step"
    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("escape", "quit", "Quit"),
        Binding("alt+i", "toggle_visual_context", "VCS"),
    ]

    def on_mount(self) -> None:
        self.push_screen(MenuScreen())

    def action_toggle_visual_context(self) -> None:
        screen = self.screen
        toggle = getattr(screen, "action_toggle_visual_context", None)
        if toggle is not None:
            toggle()
