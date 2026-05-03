from __future__ import annotations

from rich.panel import Panel
from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Input, Label, ListItem, ListView, RichLog, Static

from . import icons
from .app_banner import AppBanner
from .lesson_screen import LessonScreen
from .lessons import LESSONS
from .models import VisualContextTarget
from .vcs_tag import VcsTag
from .visual_context import VisualContextMixin


class MenuScreen(VisualContextMixin, Screen):
    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("escape", "quit", "Quit"),
        Binding("enter", "open_highlighted", "Open"),
        Binding("alt+i", "toggle_visual_context", "VCS"),
    ]

    vcs_route = "/"
    vcs_targets = (
        VisualContextTarget("menu-shell", "Menu Shell", "pattern anchor: Small Language Model Lessons", "scripts/learning_tui/menu_screen.py"),
        VisualContextTarget("menu-sidebar", "Menu Sidebar", "pattern anchor: lesson navigation column", "scripts/learning_tui/menu_screen.py"),
        VisualContextTarget("lesson-list", "Lesson List", "pattern anchor: lesson selection list", "scripts/learning_tui/menu_screen.py"),
        VisualContextTarget("menu-details", "Main Chat Interface", "pattern anchor: Dr. Stein chat shell", "scripts/learning_tui/menu_screen.py"),
        VisualContextTarget("menu-chat", "Menu Chat Transcript", "pattern anchor: scripted chat/typewriter transcript", "scripts/learning_tui/menu_screen.py"),
        VisualContextTarget("menu-composer", "Slash Command Composer", "pattern anchor: slash command lesson input", "scripts/learning_tui/menu_screen.py"),
        VisualContextTarget("vcs-footer", "Visual Context Footer", "pattern anchor: bottom VCS capture footer", "scripts/learning_tui/vcs_footer.py"),
        VisualContextTarget("vcs-footer-status", "Visual Context Footer Status", "pattern anchor: selected VCS target summary", "scripts/learning_tui/vcs_footer.py"),
        VisualContextTarget("vcs-footer-actions", "Visual Context Footer Actions", "pattern anchor: VCS quick prompt action row", "scripts/learning_tui/vcs_footer.py"),
        VisualContextTarget("vcs-quick-prompt", "VCS Quick Prompt Button", "pattern anchor: recorder-first quick prompt button", "scripts/learning_tui/vcs_footer.py"),
    )

    def __init__(self) -> None:
        super().__init__()
        self._typewriter_text = (
            "Dr. Stein: I build the small mind in public. "
            "Use /lesson tokenizer, /lesson 1, or /help to steer the lab."
        )
        self._typewriter_index = 0
        self._typewriter_timer = None
        self._setup_visual_context()

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Button(f"{icons.DELETE}", id="app-exit", classes="header-exit")
        yield AppBanner(self.vcs_route, "SLM Learning")
        yield VcsTag("menu-shell", self.vcs_route)
        with Horizontal(id="menu-main"):
            with Vertical(id="menu-sidebar"):
                yield VcsTag("menu-sidebar", self.vcs_route)
                yield Static(f"{icons.APP} Small Language Model Lessons", classes="lesson-title")
                yield Static("Select a lesson. Press Enter or click to open.", classes="hint")
                yield VcsTag("lesson-list", self.vcs_route)
                yield ListView(
                    *[
                        ListItem(Label(f"{index + 1}. {icons.CHAT} {lesson.title}"), id=f"lesson-{index}")
                        for index, lesson in enumerate(LESSONS)
                    ],
                    id="lesson-list",
                )
            with Vertical(id="menu-details"):
                yield VcsTag("menu-details", self.vcs_route)
                yield VcsTag("menu-chat", self.vcs_route)
                yield RichLog(id="menu-chat", highlight=True, markup=True, wrap=True)
                yield Static("", id="menu-typewriter", classes="chat-stream")
                yield VcsTag("menu-composer", self.vcs_route)
                yield Input(
                    placeholder="/lesson tokenizer, /lesson 1, /help",
                    id="menu-composer",
                )
        yield from self._compose_visual_context_footer()
        yield Footer(id="textual-footer")

    def on_mount(self) -> None:
        self._seed_menu_chat()
        self._typewriter_timer = self.set_interval(0.035, self._tick_typewriter)
        self._sync_visual_context()

    def _menu_markdown(self) -> str:
        lesson_lines = "\n".join(
            f"- **{index + 1}. {lesson.title}** — {lesson.goal}" for index, lesson in enumerate(LESSONS)
        )
        return f"""
# {icons.APP} SLM Learning Terminal

This is the guided terminal UI for the small language model project.

## Flow

{lesson_lines}

## Keys

- `Enter` opens the highlighted lesson.
- `Alt+i` toggles the visual context system.
- `q` quits.
- Inside a lesson, `r` runs it and `b` goes back.

## Recommended order

Run Lessons 1–6 in order. Lesson 7 is a code reading checkpoint.
""".strip()

    def _seed_menu_chat(self) -> None:
        chat = self.query_one("#menu-chat", RichLog)
        chat.write(
            Panel(
                Text(
                    "Welcome to Dr. Stein's SLM lab. This project teaches a small language model from scratch, "
                    "then turns the model back on the GAD project that created it.",
                    style="bright_white",
                ),
                title=f"{icons.CHAT} Dr. Stein",
                border_style="cyan",
            )
        )
        chat.write(
            Panel(
                Text(
                    "Slash commands are the lesson routes: /lesson 1, /lesson tokenizer, /lesson train-smoke, /help.",
                    style="bright_white",
                ),
                title=f"{icons.CODE} Composer",
                border_style="green",
            )
        )

    def _tick_typewriter(self) -> None:
        if self._typewriter_index >= len(self._typewriter_text):
            if self._typewriter_timer is not None:
                self._typewriter_timer.pause()
            return
        self._typewriter_index += 1
        self.query_one("#menu-typewriter", Static).update(self._typewriter_text[: self._typewriter_index])

    def _selected_index(self) -> int:
        list_view = self.query_one("#lesson-list", ListView)
        index = list_view.index
        if index is None:
            return 0
        return max(0, min(index, len(LESSONS) - 1))

    def action_open_highlighted(self) -> None:
        self.app.push_screen(LessonScreen(LESSONS[self._selected_index()]))

    def action_toggle_visual_context(self) -> None:
        self._toggle_visual_context()

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        event.stop()
        item_id = event.item.id or "lesson-0"
        try:
            index = int(item_id.rsplit("-", 1)[1])
        except (IndexError, ValueError):
            index = self._selected_index()
        self.app.push_screen(LessonScreen(LESSONS[index]))

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id != "menu-composer":
            return
        event.stop()
        command = event.value.strip()
        event.input.value = ""
        self._handle_composer_command(command)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        if self._handle_vcs_button(event.button.id):
            return
        if event.button.id == "app-exit":
            self.app.exit()

    def _handle_composer_command(self, command: str) -> None:
        chat = self.query_one("#menu-chat", RichLog)
        if command == "":
            return
        chat.write(Panel(Text(command, style="bright_white"), title="You", border_style="magenta"))
        if command in {"/help", "help"}:
            chat.write(
                Panel(
                    Text("/lesson 1\n/lesson tokenizer\n/lesson train-smoke\n/help", style="bright_white"),
                    title=f"{icons.CHAT} Dr. Stein",
                    border_style="cyan",
                )
            )
            return
        if command.startswith("/lesson "):
            lesson = self._lesson_from_token(command.removeprefix("/lesson ").strip())
            if lesson is not None:
                chat.write(
                    Panel(
                        Text(f"Opening {lesson.title}.", style="bright_white"),
                        title=f"{icons.CHAT} Dr. Stein",
                        border_style="cyan",
                    )
                )
                self.app.push_screen(LessonScreen(lesson))
                return
        chat.write(
            Panel(
                Text("Unknown command. Try /help or /lesson tokenizer.", style="bright_white"),
                title=f"{icons.CHAT} Dr. Stein",
                border_style="yellow",
            )
        )

    def _lesson_from_token(self, token: str):
        if token.isdigit():
            index = int(token) - 1
            if 0 <= index < len(LESSONS):
                return LESSONS[index]
        normalized = token.lower().replace(" ", "-")
        for lesson in LESSONS:
            if lesson.id == normalized or normalized in lesson.title.lower().replace(" ", "-"):
                return lesson
        return None
