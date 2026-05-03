from __future__ import annotations

import asyncio
import shlex
from typing import Sequence

from rich.console import Group
from rich.markdown import Markdown as RichMarkdown
from rich.panel import Panel
from rich.syntax import Syntax
from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, LoadingIndicator, RichLog, Static

from . import icons
from .app_banner import AppBanner
from .models import Lesson, VisualContextTarget
from .settings import ROOT, VCS_ENABLED
from .vcs_tag import VcsTag
from .visual_context import VisualContextMixin


class LessonScreen(VisualContextMixin, Screen):
    BINDINGS = [
        Binding("b", "back", "Back"),
        Binding("r", "run", "Run"),
        Binding("s", "stop", "Stop"),
        Binding("c", "clear_output", "Clear"),
        Binding("alt+i", "toggle_visual_context", "VCS"),
        Binding("l", "toggle_vcs_lock", "Lock VCS"),
        Binding("q", "quit", "Quit"),
        Binding("escape", "quit", "Quit"),
    ]

    def __init__(self, lesson: Lesson) -> None:
        super().__init__()
        self.lesson = lesson
        self.process: asyncio.subprocess.Process | None = None
        self.running_task: asyncio.Task[None] | None = None
        self.vcs_route = f"/lessons/{lesson.id}"
        self.vcs_targets = (
            VisualContextTarget("lesson-toolbar", "Lesson Toolbar", "pattern anchor: Back / Run Lesson controls", "scripts/learning_tui/lesson_screen.py"),
            VisualContextTarget("lesson-chat", "Main Chat Window", "pattern anchor: Claude-style lesson transcript", "scripts/learning_tui/lesson_screen.py"),
            VisualContextTarget("lesson-prompt-actions", "Quick Prompt Actions", "pattern anchor: CRUD prompt buttons", "scripts/learning_tui/lesson_screen.py"),
            VisualContextTarget("artifact-rail", "Artifact Rail", "pattern anchor: right-side output and code rail", "scripts/learning_tui/lesson_screen.py"),
            VisualContextTarget("lesson-output", "Command Output", "pattern anchor: lesson command RichLog output", "scripts/learning_tui/lesson_screen.py"),
            VisualContextTarget("vcs-footer", "Visual Context Footer", "pattern anchor: bottom capture bar", "scripts/learning_tui/vcs_footer.py"),
            VisualContextTarget("vcs-footer-status", "Visual Context Footer Status", "pattern anchor: selected VCS target summary", "scripts/learning_tui/vcs_footer.py"),
            VisualContextTarget("vcs-footer-actions", "Visual Context Footer Actions", "pattern anchor: VCS quick prompt action row", "scripts/learning_tui/vcs_footer.py"),
            VisualContextTarget("vcs-quick-prompt", "VCS Quick Prompt Button", "pattern anchor: recorder-first quick prompt button", "scripts/learning_tui/vcs_footer.py"),
        )
        self._setup_visual_context()

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Button(f"{icons.DELETE}", id="app-exit", classes="header-exit")
        yield AppBanner(self.vcs_route, self.lesson.title)
        with Vertical(id="lesson-main"):
            with Horizontal(id="button-row"):
                yield VcsTag("lesson-toolbar", self.vcs_route)
                yield Button(f"{icons.BACK} Back", id="back", variant="default")
                yield Button(f"{icons.RUN} Run Lesson", id="run", variant="success", disabled=self.lesson.command is None)
                yield Button(f"{icons.STOP} Stop", id="stop", variant="error")
                yield Button(f"{icons.CLEAR} Clear Output", id="clear", variant="primary")
                yield Button(f"{icons.VCS} VCS", id="vcs-toggle", variant="warning", disabled=not VCS_ENABLED)
                yield Static(f"{icons.CHAT} {self.lesson.title}", classes="status")
            with Horizontal(id="lesson-workspace"):
                with Vertical(id="lesson-chat-pane"):
                    yield VcsTag("lesson-chat", self.vcs_route)
                    yield RichLog(id="lesson-chat", highlight=True, markup=True, wrap=True)
                    yield VcsTag("lesson-prompt-actions", self.vcs_route)
                    with Horizontal(id="lesson-prompt-actions"):
                        yield Button(f"{icons.RECORD} VCS Quick Prompt", id="quick-vcs-prompt", variant="warning")
                with Vertical(id="artifact-rail"):
                    yield VcsTag("artifact-rail", self.vcs_route)
                    yield Static(f"{icons.CODE} Artifacts / Output   tag: artifact-rail", classes="rail-title")
                    yield LoadingIndicator(id="run-spinner")
                    yield VcsTag("lesson-output", self.vcs_route)
                    yield RichLog(id="lesson-output", highlight=True, markup=True, wrap=True)
            yield from self._compose_visual_context_footer()
        yield Footer(id="textual-footer")

    def on_mount(self) -> None:
        chat = self.query_one("#lesson-chat", RichLog)
        chat.write(
            Panel(
                Group(
                    RichMarkdown(self.lesson.body),
                    Syntax(self.lesson.command_text, "bash", theme="monokai", word_wrap=True),
                ),
                title=f"{icons.CHAT} Lesson Chat: {self.lesson.title}",
                border_style="cyan",
            )
        )
        chat.write(
            Panel(
                Text(
                    "Run the lesson to stream terminal output into the artifact rail. "
                    "Use VCS to copy a target-aware prompt for any visible region.",
                    style="bright_white",
                ),
                title=f"{icons.APP} Assistant",
                border_style="green",
            )
        )
        output = self.query_one("#lesson-output", RichLog)
        output.write(Panel(Text(f"Ready: {self.lesson.title}\n\nGoal: {self.lesson.goal}"), title=f"{icons.APP} Status"))
        output.write(Panel(Syntax(self.lesson.command_text, "bash", theme="monokai", word_wrap=True), title=f"{icons.CODE} Command"))
        self.query_one("#run-spinner", LoadingIndicator).display = False
        self._sync_visual_context()

    def action_back(self) -> None:
        self._stop_process()
        self.app.pop_screen()

    def action_run(self) -> None:
        self._start_run()

    def action_stop(self) -> None:
        self._stop_process()

    def action_clear_output(self) -> None:
        self.query_one("#lesson-output", RichLog).clear()

    def action_toggle_visual_context(self) -> None:
        self._toggle_visual_context()

    def action_toggle_vcs_lock(self) -> None:
        self._toggle_vcs_lock()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        if self._handle_vcs_button(event.button.id):
            return
        if event.button.id == "back":
            self.action_back()
        elif event.button.id == "app-exit":
            self._stop_process()
            self.app.exit()
        elif event.button.id == "run":
            self.action_run()
        elif event.button.id == "stop":
            self.action_stop()
        elif event.button.id == "clear":
            self.action_clear_output()
        elif event.button.id == "vcs-toggle":
            self.action_toggle_visual_context()
        elif event.button.id == "quick-vcs-prompt":
            self.vcs_selected_target_id = "lesson-chat"
            self._copy_vcs_prompt()

    def _start_run(self) -> None:
        output = self.query_one("#lesson-output", RichLog)
        if self.lesson.command is None:
            output.write("No command attached to this lesson.")
            return
        if self.running_task is not None and not self.running_task.done():
            output.write("A command is already running. Stop it first.")
            return
        self.running_task = asyncio.create_task(self._run_command(self.lesson.command))

    def _stop_process(self) -> None:
        output = self.query_one("#lesson-output", RichLog)
        if self.process is None:
            return
        if self.process.returncode is None:
            output.write(f"{icons.STOP} Stopping process...")
            self.process.terminate()

    async def _run_command(self, command: Sequence[str]) -> None:
        output = self.query_one("#lesson-output", RichLog)
        spinner = self.query_one("#run-spinner", LoadingIndicator)
        spinner.display = True
        output.write(Panel(Syntax(" ".join(shlex.quote(part) for part in command), "bash", theme="monokai"), title=f"{icons.RUN} Running"))

        try:
            self.process = await asyncio.create_subprocess_exec(
                *command,
                cwd=str(ROOT),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
        except FileNotFoundError as error:
            output.write(f"Failed to start process: {error}")
            self.process = None
            spinner.display = False
            return

        assert self.process.stdout is not None
        while True:
            line = await self.process.stdout.readline()
            if not line:
                break
            output.write(line.decode(errors="replace").rstrip("\n"))

        return_code = await self.process.wait()
        output.write(Panel(Text(f"Command finished with exit code {return_code}"), title=f"{icons.APP} Complete"))
        chat = self.query_one("#lesson-chat", RichLog)
        chat.write(
            Panel(
                Text(f"The artifact rail has the latest run output for {self.lesson.title}.", style="bright_white"),
                title=f"{icons.APP} Assistant",
                border_style="green",
            )
        )
        self.process = None
        spinner.display = False
