from __future__ import annotations
import asyncio

from rich.text import Text
from textual import events
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Input, Label, ListItem, ListView, RichLog, Static

from . import icons
from .app_banner import AppBanner
from .lesson_screen import LessonScreen
from .lesson_search import format_lesson_suggestion, matching_lessons
from .models import VisualContextTarget
from .vcs_tag import VcsTag
from .visual_context import VisualContextMixin

from .slash_commands import SlashCommandParser
from .model_runner import ModelRunner
from .telemetry import log_event

MAX_CHAT_SUGGESTIONS = 5


class ChatScreen(VisualContextMixin, Screen):
    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("escape", "quit", "Quit"),
        Binding("alt+i", "toggle_visual_context", "VCS"),
        Binding("ctrl+r", "toggle_chat_speech", "Record Audio"),
        Binding("down", "chat_focus_suggestions", show=False, priority=True),
    ]

    vcs_route = "/chat"
    vcs_targets = (
        VisualContextTarget("chat-shell", "Chat Shell", "pattern anchor: SLM Chat Console layout", "scripts/learning_tui/chat_screen.py"),
        VisualContextTarget("chat-log", "Chat Transcript", "pattern anchor: model chat transcript", "scripts/learning_tui/chat_screen.py"),
        VisualContextTarget("chat-speech-status", "Chat Speech Status", "pattern anchor: live chat microphone status", "scripts/learning_tui/chat_screen.py"),
        VisualContextTarget("chat-command-preview", "Command Preview", "pattern anchor: slash command preview line", "scripts/learning_tui/chat_screen.py"),
        VisualContextTarget("chat-composer", "Chat Composer", "pattern anchor: model chat input", "scripts/learning_tui/chat_screen.py"),
    )

    def __init__(self) -> None:
        super().__init__()
        self.runner = ModelRunner()
        self.parser = SlashCommandParser(self.runner._model_labels, self.runner._model_aliases)
        
        self.active_model_key = "kael"
        self._chat_recording = False
        self._chat_recording_timer = None
        self._chat_messages: list[tuple[str, str, str]] = []
        self._response_task: asyncio.Task[None] | None = None
        self._waiting_timer = None
        self._waiting_ticks = 0
        self._waiting_message_index = 0
        self._system_status = f"model ready: {self.runner._model_labels[self.active_model_key]}"
        self._chat_suggestion_commands: list[str] = []
        self._setup_visual_context()

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Button(f"{icons.DELETE}", id="app-exit", classes="header-exit")
        yield AppBanner(self.vcs_route, "SLM Chat Console")
        
        yield VcsTag("chat-shell", self.vcs_route)
        with Vertical(id="chat-layout", classes="chat-main"):
            yield VcsTag("chat-log", self.vcs_route)
            yield RichLog(id="chat-log", highlight=True, markup=True, wrap=True)
            yield VcsTag("chat-speech-status", self.vcs_route)
            yield Static(f"{icons.AUDIO} Ctrl+R records into the composer.", id="chat-speech-status", classes="chat-live-line")
            yield VcsTag("chat-command-preview", self.vcs_route)
            yield Static("", id="chat-command-preview", classes="chat-live-line")
            yield VcsTag("chat-suggestions", self.vcs_route)
            yield ListView(
                ListItem(
                    Label("Type / for commands; ↓ to pick a suggestion, Enter to run."),
                    id="chat-suggestion-placeholder",
                    classes="suggestion-placeholder",
                ),
                *[
                    ListItem(Label(""), id=f"chat-suggestion-{index}")
                    for index in range(MAX_CHAT_SUGGESTIONS)
                ],
                id="chat-suggestions",
            )
            yield VcsTag("chat-composer", self.vcs_route)
            yield Input(placeholder="Chat... /model stein, /lesson tokenizer, /models (Ctrl+R)", id="chat-composer")

        yield Footer(id="textual-footer")

    def on_mount(self) -> None:
        self._sync_visual_context()
        self._sync_chat_status()
        self._sync_slash_suggestions("")

    def action_toggle_chat_speech(self) -> None:
        self._toggle_chat_speech()

    def _toggle_chat_speech(self) -> None:
        composer = self.query_one("#chat-composer", Input)
        status = self.query_one("#chat-speech-status", Static)
        if not self._chat_recording:
            self._chat_recording = True
            self.vcs_speech_recognizer.start()
            if self._chat_recording_timer is None:
                self._chat_recording_timer = self.set_interval(0.5, self._tick_chat_speech)
            else:
                self._chat_recording_timer.resume()
            status.update(f"{icons.RECORD} Recording... Ctrl+R stops and inserts transcript.")
            composer.placeholder = "Listening... Ctrl+R to stop"
            self.notify("Mic started for chat.")
        else:
            self._chat_recording = False
            self.vcs_speech_recognizer.stop()
            if self._chat_recording_timer is not None:
                self._chat_recording_timer.pause()
            
            # Finalize transcript
            snap = self.vcs_speech_recognizer.snapshot()
            if snap.transcript:
                composer.value = composer.value + (" " if composer.value else "") + snap.transcript
                composer.focus()
                status.update(f"{icons.AUDIO} Captured speech into composer.")
            else:
                status.update(f"{icons.AUDIO} No speech captured. Ctrl+R records into the composer.")
            composer.placeholder = "Chat... /model stein, /lesson tokenizer, /models (Ctrl+R)"
            self.notify("Mic stopped.")

    def _tick_chat_speech(self) -> None:
        if not self._chat_recording:
            return
        snap = self.vcs_speech_recognizer.snapshot()
        status = self.query_one("#chat-speech-status", Static)
        live = snap.transcript or snap.status
        status.update(f"{icons.RECORD} live: {live}")

    def _sync_chat_status(self) -> None:
        status = self.query_one("#chat-speech-status", Static)
        status.update(f"{icons.APP} {self._system_status}")

    def _append_chat(self, role: str, name: str, content: str) -> int:
        self._chat_messages.append((role, name, content))
        self._render_chat()
        return len(self._chat_messages) - 1

    def _replace_chat(self, index: int, role: str, name: str, content: str) -> None:
        if 0 <= index < len(self._chat_messages):
            self._chat_messages[index] = (role, name, content)
            self._render_chat()

    def _render_chat(self) -> None:
        log = self.query_one("#chat-log", RichLog)
        log.clear()
        for role, name, content in self._chat_messages:
            if role == "user":
                log.write(Text(f"You: {content}", style="bright_magenta"))
            elif role == "assistant":
                log.write(Text(f"{name}: {content}", style="bright_green"))
            else:
                log.write(Text(content, style="bright_cyan"))

    def _start_waiting_animation(self, message_index: int) -> None:
        self._waiting_ticks = 0
        self._waiting_message_index = message_index
        if self._waiting_timer is None:
            self._waiting_timer = self.set_interval(0.2, self._tick_waiting_animation)
        else:
            self._waiting_timer.resume()

    def _stop_waiting_animation(self) -> None:
        if self._waiting_timer is not None:
            self._waiting_timer.pause()

    def _tick_waiting_animation(self) -> None:
        if self._response_task is None or self._response_task.done():
            self._stop_waiting_animation()
            return
        dots = "." * ((self._waiting_ticks % 3) + 1)
        self._waiting_ticks += 1
        model_name = self.runner.get_model_name(self.active_model_key)
        self._replace_chat(
            self._waiting_message_index,
            "assistant",
            model_name,
            f"thinking{dots}",
        )

    async def _generate_and_stream_response(self, prompt: str, message_index: int, model_key: str, model_name: str) -> None:
        try:
            history = []
            for r, n, c in self._chat_messages[:message_index]:
                if r in ("user", "assistant"):
                    history.append({"role": r, "content": c})
                    
            queue = asyncio.Queue()
            loop = asyncio.get_running_loop()
            
            # Start generator thread
            asyncio.create_task(self.runner.stream_response(model_key, history, loop, queue))
            
            visible = ""
            first_token_received = False
            
            while True:
                token = await queue.get()
                
                if token is None:
                    break
                    
                if isinstance(token, Exception):
                    raise token
                    
                if not first_token_received:
                    self._stop_waiting_animation()
                    first_token_received = True
                    log_event("generation_start", model_name, {"model": model_key, "prompt": prompt[:50]})
                    
                visible += token
                
                # Autonomous Handoff Check
                if "<|tool_call|>switch_dr_stein" in visible:
                    self._set_active_model("dr_stein")
                    self._replace_chat(message_index, "system", "System", "Autonomous Transfer: Dr. Stein swapped in.")
                    log_event("agent_handoff", model_name, {"to": "dr_stein", "reason": "autonomous_tool_call"})
                    return
                
                self._replace_chat(message_index, "assistant", model_name, visible)

        except Exception as error:
            self._stop_waiting_animation()
            self._replace_chat(message_index, "assistant", model_name, f"error: {error}")
            log_event("generation_error", model_name, {"error": str(error)})
            return

    def action_toggle_visual_context(self) -> None:
        self._toggle_visual_context()

    def _set_active_model(self, model_key: str) -> None:
        self.active_model_key = model_key
        self._system_status = f"model set: {self.runner._model_labels.get(model_key, model_key)}"
        self._sync_chat_status()
        self.notify(f"{icons.APP} Switched model to {self.runner._model_labels.get(model_key, model_key)}")
        log_event("model_switch", "user", {"new_model": model_key})

    def _model_preview(self, query: str) -> str:
        keys = self.parser.ranked_model_keys(query)[:4]
        return " | ".join(f"/model {key.replace('_', '-')}" for key in keys)

    def _lesson_preview(self, query: str) -> str:
        matches = matching_lessons(query)
        if not matches:
            return "No lesson matches. Try /lesson tokenizer or /lesson train-smoke."
        return " | ".join(f"/lesson {lesson.id}" for _index, lesson in matches[:4])

    def _build_slash_suggestion_rows(
        self, first: str, rest: str, fams: list[str]
    ) -> list[tuple[str, str]]:
        max_slots = MAX_CHAT_SUGGESTIONS
        if first == "":
            rows: list[tuple[str, str]] = []
            for key in self.parser.ranked_model_keys(""):
                cmd = f"/model {key.replace('_', '-')}"
                rows.append((cmd, cmd))
                if len(rows) >= 2:
                    break
            for lesson_index, lesson in matching_lessons(""):
                if len(rows) >= max_slots:
                    break
                rows.append(
                    (format_lesson_suggestion(lesson_index, lesson, ""), f"/lesson {lesson.id}")
                )
            return rows

        if not fams:
            return []

        rows = []
        if "model" in fams and "lesson" in fams:
            for key in self.parser.ranked_model_keys(rest):
                if len(rows) >= 3:
                    break
                cmd = f"/model {key.replace('_', '-')}"
                rows.append((cmd, cmd))
            for lesson_index, lesson in matching_lessons(rest):
                if len(rows) >= max_slots:
                    break
                rows.append(
                    (format_lesson_suggestion(lesson_index, lesson, rest), f"/lesson {lesson.id}")
                )
            return rows

        if "model" in fams:
            for key in self.parser.ranked_model_keys(rest):
                if len(rows) >= max_slots:
                    break
                cmd = f"/model {key.replace('_', '-')}"
                rows.append((cmd, cmd))
            return rows

        if "lesson" in fams:
            for lesson_index, lesson in matching_lessons(rest):
                if len(rows) >= max_slots:
                    break
                rows.append(
                    (format_lesson_suggestion(lesson_index, lesson, rest), f"/lesson {lesson.id}")
                )
            return rows

        if "help" in fams:
            rows.append(("/help", "/help"))
        return rows

    def _sync_slash_suggestions(self, value: str) -> None:
        preview = self.query_one("#chat-command-preview", Static)
        suggestions = self.query_one("#chat-suggestions", ListView)
        placeholder = self.query_one("#chat-suggestion-placeholder", ListItem)

        if not value.strip().startswith("/"):
            preview.display = False
            preview.update("")
            suggestions.display = False
            self._chat_suggestion_commands = []
            placeholder.display = True
            for item in suggestions.children:
                if item.id != "chat-suggestion-placeholder":
                    item.display = False
            return

        first, rest = self.parser.parse_slash_line(value)
        fams = self.parser.families_for_stem(first) if first else ["model", "lesson"]

        if first and not fams:
            preview.display = True
            preview.update(f"{icons.CHAT} no slash match for `{first}` — try /m /l /help")
            rows = []
        else:
            preview.display = True
            if first == "":
                preview.update(self._root_command_preview())
            else:
                chunks: list[str] = []
                if "model" in fams:
                    chunks.append(f"{icons.CODE} models: {self._model_preview(rest)}")
                if "lesson" in fams:
                    chunks.append(f"{icons.CHAT} lessons: {self._lesson_preview(rest)}")
                if "help" in fams:
                    chunks.append(f"{icons.CHAT} /help — /m models · /l lessons")
                preview.update("  ·  ".join(chunks) if chunks else self._root_command_preview())
            rows = self._build_slash_suggestion_rows(first, rest, fams)

        self._chat_suggestion_commands = [cmd for _label, cmd in rows]
        suggestions.display = True
        placeholder.display = len(rows) == 0

        for item in suggestions.children:
            if item.id == "chat-suggestion-placeholder":
                continue
            try:
                slot = int(item.id.rsplit("-", 1)[1]) if item.id is not None else -1
            except (IndexError, ValueError):
                slot = -1
            if 0 <= slot < len(rows):
                label = item.query_one(Label)
                label.update(rows[slot][0])
                item.display = True
            else:
                item.display = False

    def _root_command_preview(self) -> str:
        return (
            f"{icons.CODE} /model … | /models | {icons.CHAT} /lesson … | "
            f"{icons.CHAT} /help — e.g. /m kael, /l tokenizer"
        )

    def _handle_chat_command(self, command: str) -> bool:
        parts = command.strip().split()
        if not parts or not parts[0].startswith("/"):
            return False
        head = parts[0].lower().removeprefix("/")
        rest_line = " ".join(parts[1:]).strip().lower()

        canonical = self.parser.canonical_action_from_stem(head)
        if canonical is None:
            self._system_status = f"unknown: `{head}` — try /m /l /help"
            self._sync_chat_status()
            self.notify("Unknown slash command.", severity="warning")
            return True

        if canonical == "help":
            self._system_status = "slash: /m /model /models · /l /lesson · /help"
            self._sync_chat_status()
            return True

        if canonical == "model":
            if not rest_line:
                models = ", ".join(f"/model {key.replace('_', '-')}" for key in self.runner._model_labels)
                self._system_status = f"models: {models}"
                self._sync_chat_status()
                return True
            requested = rest_line.replace(".", "").replace(" ", "_")
            model_key = self.runner._model_aliases.get(requested)
            if model_key is None:
                ranked = self.parser.ranked_model_keys(rest_line)
                model_key = ranked[0] if ranked else None
            if model_key is None:
                self._system_status = f"no model match: {rest_line} — try /m"
                self._sync_chat_status()
                self.notify("Unknown model.", severity="warning")
                return True
            self._set_active_model(model_key)
            return True

        if canonical == "lesson":
            matches = matching_lessons(rest_line)
            if not matches:
                self._system_status = f"no lesson match: {rest_line or '[empty]'}"
                self._sync_chat_status()
                self.notify("No matching lesson.", severity="warning")
                return True
            _index, lesson = matches[0]
            self._system_status = f"opening lesson: {lesson.id}"
            self._sync_chat_status()
            self.app.push_screen(LessonScreen(lesson))
            return True

        return False

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id != "chat-composer":
            return
        event.stop()
        self._sync_slash_suggestions(event.value)

    def on_key(self, event: events.Key) -> None:
        if event.key != "up":
            return
        suggestions = self.query_one("#chat-suggestions", ListView)
        if not suggestions.display or self.focused != suggestions:
            return
        if suggestions.index == 0:
            event.prevent_default()
            event.stop()
            self.query_one("#chat-composer", Input).focus()

    def action_chat_focus_suggestions(self) -> None:
        suggestions = self.query_one("#chat-suggestions", ListView)
        composer = self.query_one("#chat-composer", Input)
        if self.focused == suggestions:
            return
        if not suggestions.display or not self._chat_suggestion_commands:
            return
        if self.focused != composer:
            return
        suggestions.focus()
        suggestions.index = 0

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        event.stop()
        if event.list_view.id != "chat-suggestions":
            return
        self._apply_chat_suggestion_item(event.item)

    def _apply_chat_suggestion_item(self, item: ListItem | None) -> None:
        if item is None or item.id is None:
            return
        if item.id == "chat-suggestion-placeholder":
            return
        try:
            slot = int(item.id.rsplit("-", 1)[1])
        except (IndexError, ValueError):
            return
        if slot < 0 or slot >= len(self._chat_suggestion_commands):
            return
        cmd = self._chat_suggestion_commands[slot]
        composer = self.query_one("#chat-composer", Input)
        composer.focus()
        handled = self._handle_chat_command(cmd)
        composer.value = ""
        self._sync_slash_suggestions(composer.value)
        if not handled:
            composer.value = cmd
            self._sync_slash_suggestions(cmd)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id != "chat-composer":
            return
        event.stop()
        prompt = event.value.strip()
        event.input.value = ""
        self._sync_slash_suggestions("")
        
        if not prompt:
            return

        if prompt.startswith("/") and self._handle_chat_command(prompt):
            return

        if self._response_task is not None and not self._response_task.done():
            self._append_chat("system", "system", "Model is still responding. Wait for it to finish.")
            return

        self._append_chat("user", "You", prompt)
        model_key = self.active_model_key
        model_name = self.runner.get_model_name(self.active_model_key)
        message_index = self._append_chat("assistant", model_name, "thinking.")
        
        log_event("user_prompt", "user", {"prompt": prompt})
        
        self._start_waiting_animation(message_index)
        self._response_task = asyncio.create_task(self._generate_and_stream_response(prompt, message_index, model_key, model_name))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        if self._handle_vcs_button(event.button.id):
            return
        if event.button.id == "app-exit":
            self.app.exit()
