from __future__ import annotations

import asyncio
import shlex
from typing import Sequence

from rich.markdown import Markdown as RichMarkdown
from rich.syntax import Syntax
from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Input, LoadingIndicator, RichLog, Static

from . import icons
from .app_banner import AppBanner
from .models import Lesson, VisualContextTarget
from .settings import ROOT
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
        self.active_result_tab = "output"
        self.vcs_route = f"/lessons/{lesson.id}"
        self.vcs_targets = (
            VisualContextTarget("lesson-chat", "Main Chat Window", "pattern anchor: Claude-style lesson transcript", "scripts/learning_tui/lesson_screen.py"),
            VisualContextTarget("lesson-composer", "Lesson Composer", "pattern anchor: lesson slash command composer", "scripts/learning_tui/lesson_screen.py"),
            VisualContextTarget("artifact-rail", "Results Panel", "pattern anchor: lesson output context panel", "scripts/learning_tui/lesson_screen.py"),
            VisualContextTarget("lesson-output", "Command Output", "pattern anchor: lesson command RichLog output", "scripts/learning_tui/lesson_screen.py"),
            VisualContextTarget("lesson-command", "Command Preview", "pattern anchor: lesson command preview tab", "scripts/learning_tui/lesson_screen.py"),
        )
        self._setup_visual_context()

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Button(f"{icons.DELETE}", id="app-exit", classes="header-exit")
        yield AppBanner(self.vcs_route, self.lesson.title)
        with Vertical(id="lesson-main"):
            with Vertical(id="lesson-workspace"):
                with Vertical(id="lesson-chat-pane"):
                    yield VcsTag("lesson-chat", self.vcs_route)
                    yield RichLog(id="lesson-chat", highlight=True, markup=True, wrap=True)
                    yield VcsTag("lesson-composer", self.vcs_route)
                    yield Input(
                        placeholder="/run, /stop, /clear, /back, /vcs, /help",
                        id="lesson-composer",
                    )
                with Vertical(id="artifact-rail"):
                    yield VcsTag("artifact-rail", self.vcs_route)
                    with Horizontal(id="lesson-result-bar"):
                        yield Static(f"{icons.CODE} [Output] | command", id="lesson-result-tabs", classes="rail-title")
                        yield LoadingIndicator(id="run-spinner")
                    yield VcsTag("lesson-output", self.vcs_route)
                    yield RichLog(id="lesson-output", highlight=True, markup=True, wrap=True)
                    yield VcsTag("lesson-command", self.vcs_route)
                    yield RichLog(id="lesson-command", highlight=True, markup=True, wrap=True)
        yield Footer(id="textual-footer")

    def on_mount(self) -> None:
        chat = self.query_one("#lesson-chat", RichLog)
        chat.write(RichMarkdown(self.lesson.body))
        self._write_assistant(
            "Commands: /run /stop /clear /back /vcs /output /command /help"
        )
        output = self.query_one("#lesson-output", RichLog)
        output.write(f"{icons.APP} Ready: {self.lesson.title}")
        output.write(f"Goal: {self.lesson.goal}")
        command_log = self.query_one("#lesson-command", RichLog)
        command_log.write(Syntax(self.lesson.command_text, "bash", theme="monokai", word_wrap=True))
        self.query_one("#run-spinner", LoadingIndicator).display = False
        self._sync_result_tab()
        self._sync_visual_context()

    def _write_assistant(self, message: str, border_style: str = "green") -> None:
        del border_style
        self.query_one("#lesson-chat", RichLog).write(Text(f"{icons.APP} Assistant: {message}", style="bright_white"))

    def _write_user(self, message: str) -> None:
        self.query_one("#lesson-chat", RichLog).write(Text(f"You: {message}", style="bright_white"))

    def _write_artifact_status(self, message: str) -> None:
        self.query_one("#lesson-output", RichLog).write(f"{icons.APP} {message}")

    def _sync_result_tab(self) -> None:
        output_active = self.active_result_tab == "output"
        self.query_one("#lesson-output", RichLog).display = output_active
        self.query_one("#lesson-command", RichLog).display = not output_active
        tabs = self.query_one("#lesson-result-tabs", Static)
        tabs.update(f"{icons.CODE} [{'Output' if output_active else 'output'}] | [{'Command' if not output_active else 'command'}]")

    def _set_result_tab(self, tab: str) -> None:
        self.active_result_tab = tab
        self._sync_result_tab()

    def action_back(self) -> None:
        self._stop_process(quiet=True)
        self.app.pop_screen()

    def action_run(self) -> None:
        self._start_run()

    def action_stop(self) -> None:
        self._stop_process()

    def action_clear_output(self) -> None:
        self.query_one("#lesson-output", RichLog).clear()
        self._write_assistant("Artifact output cleared.")

    def action_toggle_visual_context(self) -> None:
        self._toggle_visual_context()

    def action_toggle_vcs_lock(self) -> None:
        self._toggle_vcs_lock()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        if self._handle_vcs_button(event.button.id):
            return
        if event.button.id == "app-exit":
            self._stop_process(quiet=True)
            self.app.exit()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id != "lesson-composer":
            return
        event.stop()
        command = event.value.strip()
        event.input.value = ""
        self._handle_lesson_command(command)

    def _handle_lesson_command(self, command: str) -> None:
        if command == "":
            return
        self._write_user(command)
        normalized = command.lower()
        if normalized in {"/run", "run", "r"}:
            self.action_run()
        elif normalized in {"/stop", "stop", "s"}:
            self.action_stop()
        elif normalized in {"/clear", "clear", "c"}:
            self.action_clear_output()
        elif normalized in {"/back", "back", "b"}:
            self.action_back()
        elif normalized in {"/vcs", "vcs"}:
            self.vcs_selected_target_id = "lesson-chat"
            self._copy_vcs_prompt()
            self._write_assistant("Copied a VCS quick prompt for the lesson chat.")
        elif normalized in {"/output", "output"}:
            self._set_result_tab("output")
            self._write_assistant("Showing output results.")
        elif normalized in {"/command", "command"}:
            self._set_result_tab("command")
            self._write_assistant("Showing command preview.")
        elif normalized in {"/help", "help"}:
            self._write_assistant("/run /stop /clear /back /vcs /output /command /help")
        else:
            self._write_assistant("Unknown lesson command. Try /help.", border_style="yellow")

    def _start_run(self) -> None:
        if self.lesson.command is None:
            self._write_assistant("No command is attached to this lesson.", border_style="yellow")
            self._write_artifact_status("No command attached to this lesson.")
            return
        if self.running_task is not None and not self.running_task.done():
            self._write_assistant("A command is already running. Stop it first.", border_style="yellow")
            self._write_artifact_status("A command is already running.")
            return
        self._set_result_tab("output")
        self._write_assistant(f"Starting {self.lesson.title}. Output will stream into the context panel.")
        self.running_task = asyncio.create_task(self._run_command(self.lesson.command))

    def _stop_process(self, quiet: bool = False) -> None:
        if self.process is None:
            if not quiet:
                self._write_assistant("No running process to stop.", border_style="yellow")
            return
        if self.process.returncode is None:
            self._write_assistant("Stopping the running lesson process.")
            self._write_artifact_status(f"{icons.STOP} Stopping process...")
            self.process.terminate()

    async def _run_command(self, command: Sequence[str]) -> None:
        output = self.query_one("#lesson-output", RichLog)
        spinner = self.query_one("#run-spinner", LoadingIndicator)
        spinner.display = True
        output.write(f"{icons.RUN} Running: {' '.join(shlex.quote(part) for part in command)}")

        try:
            self.process = await asyncio.create_subprocess_exec(
                *command,
                cwd=str(ROOT),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
        except FileNotFoundError as error:
            self._write_assistant(f"Failed to start process: {error}", border_style="red")
            self._write_artifact_status(f"Failed to start process: {error}")
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
        output.write(f"{icons.APP} Complete: exit code {return_code}")
        self._write_assistant(
            f"Run finished with exit code {return_code}. The context panel has the latest output.",
            border_style="green" if return_code == 0 else "yellow",
        )
        self.process = None
        spinner.display = False
