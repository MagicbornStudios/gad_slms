from __future__ import annotations
import asyncio
import os
import sys

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Input, RichLog, Select, Static

from . import icons
from .app_banner import AppBanner
from .models import VisualContextTarget
from .vcs_tag import VcsTag
from .visual_context import VisualContextMixin

# Ensure we can import the models
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "src")))
try:
    from slm_from_scratch.models.kael import KaelModel
    from slm_from_scratch.models.dr_stein import DrSteinModel
except ImportError:
    # Fallbacks if models aren't ready
    class KaelModel:
        def __init__(self, *args, **kwargs): self.name = "Kael"
        def generate(self, p, **kwargs): return f"[Kael] Fallback mock for: {p}"
    class DrSteinModel:
        def __init__(self, *args, **kwargs): self.name = "Dr. Stein"
        def generate(self, p, **kwargs): return f"[Dr. Stein] Fallback mock for: {p}"

class ChatScreen(VisualContextMixin, Screen):
    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("escape", "quit", "Quit"),
        Binding("alt+i", "toggle_visual_context", "VCS"),
        Binding("ctrl+r", "toggle_chat_speech", "Record Audio"),
    ]

    vcs_route = "/chat"
    vcs_targets = (
        VisualContextTarget("chat-shell", "Chat Shell", "pattern anchor: SLM Chat Console layout", "scripts/learning_tui/chat_screen.py"),
        VisualContextTarget("chat-controls", "Model Controls", "pattern anchor: chat model selector", "scripts/learning_tui/chat_screen.py"),
        VisualContextTarget("model-selector", "Model Selector", "pattern anchor: active model selector", "scripts/learning_tui/chat_screen.py"),
        VisualContextTarget("chat-log", "Chat Transcript", "pattern anchor: model chat transcript", "scripts/learning_tui/chat_screen.py"),
        VisualContextTarget("chat-speech-status", "Chat Speech Status", "pattern anchor: live chat microphone status", "scripts/learning_tui/chat_screen.py"),
        VisualContextTarget("chat-composer", "Chat Composer", "pattern anchor: model chat input", "scripts/learning_tui/chat_screen.py"),
    )

    def __init__(self) -> None:
        super().__init__()
        self._model_classes = {
            "kael": KaelModel,
            "dr_stein": DrSteinModel,
        }
        self._model_labels = {
            "kael": "Kael",
            "dr_stein": "Dr. Stein",
        }
        self._model_cache = {}
        self.active_model_key = "kael"
        self._chat_recording = False
        self._chat_recording_timer = None
        self._chat_messages: list[tuple[str, str, str]] = []
        self._response_task: asyncio.Task[None] | None = None
        self._waiting_timer = None
        self._waiting_ticks = 0
        self._waiting_message_index = 0
        self._ambient_timer = None
        self._ambient_ticks = 0
        self._system_status = f"model ready: {self._model_labels[self.active_model_key]}"
        self._setup_visual_context()

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Button(f"{icons.DELETE}", id="app-exit", classes="header-exit")
        yield AppBanner(self.vcs_route, "SLM Chat Console")
        
        yield VcsTag("chat-shell", self.vcs_route)
        with Vertical(id="chat-layout", classes="chat-main"):
            yield VcsTag("chat-controls", self.vcs_route)
            with Horizontal(id="chat-controls"):
                yield VcsTag("model-selector", self.vcs_route)
                yield Select(
                    [(self._model_labels["kael"], "kael"), (self._model_labels["dr_stein"], "dr_stein")],
                    value="kael", 
                    id="model-selector"
                )
            yield VcsTag("chat-log", self.vcs_route)
            yield RichLog(id="chat-log", highlight=True, markup=True, wrap=True)
            yield VcsTag("chat-speech-status", self.vcs_route)
            yield Static(f"{icons.AUDIO} Ctrl+R records into the composer.", id="chat-speech-status", classes="chat-live-line")
            yield VcsTag("chat-composer", self.vcs_route)
            yield Input(placeholder="Chat with the model... (Ctrl+R to record)", id="chat-composer")

        yield Footer(id="textual-footer")

    def on_mount(self) -> None:
        self._sync_visual_context()
        self._sync_chat_status()
        self._ambient_timer = self.set_interval(0.8, self._tick_ambient_status)

    @property
    def _active_model_name(self) -> str:
        model = self._model_cache.get(self.active_model_key)
        if model is not None:
            return model.name
        return self._model_labels[self.active_model_key]

    def _get_active_model(self):
        if self.active_model_key not in self._model_cache:
            model_class = self._model_classes[self.active_model_key]
            self._model_cache[self.active_model_key] = model_class()
        return self._model_cache[self.active_model_key]

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
            composer.placeholder = "Chat with the model... (Ctrl+R to record)"
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

    def _tick_ambient_status(self) -> None:
        if self._chat_recording or (self._response_task is not None and not self._response_task.done()):
            return
        phases = ("calibrating corpus", "pruning stale lines", "warming decoder", "summarizing context")
        pulse = ("*", "**", "***", "**")[self._ambient_ticks % 4]
        phase = phases[self._ambient_ticks % len(phases)]
        self._ambient_ticks += 1
        status = self.query_one("#chat-speech-status", Static)
        status.update(f"{icons.APP} {self._system_status} | {phase} {pulse}")

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
        self._replace_chat(
            self._waiting_message_index,
            "assistant",
            self._active_model_name,
            f"thinking{dots}",
        )

    async def _generate_and_stream_response(self, prompt: str, message_index: int, model_key: str, model_name: str) -> None:
        try:
            model = self._model_cache.get(model_key)
            if model is None:
                model_class = self._model_classes[model_key]
                model = await asyncio.to_thread(model_class)
                self._model_cache[model_key] = model
                model_name = model.name
            response = await asyncio.to_thread(model.generate, prompt)
        except Exception as error:
            self._stop_waiting_animation()
            self._replace_chat(message_index, "assistant", model_name, f"error: {error}")
            return

        self._stop_waiting_animation()
        visible = ""
        for char in response:
            visible += char
            self._replace_chat(message_index, "assistant", model_name, visible)
            await asyncio.sleep(0.01)

    def action_toggle_visual_context(self) -> None:
        self._toggle_visual_context()

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id == "model-selector":
            if event.value == "kael":
                self.active_model_key = "kael"
            elif event.value == "dr_stein":
                self.active_model_key = "dr_stein"
            self._system_status = f"model set: {self._active_model_name}"
            self._sync_chat_status()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id != "chat-composer":
            return
        event.stop()
        prompt = event.value.strip()
        event.input.value = ""
        
        if not prompt:
            return

        if self._response_task is not None and not self._response_task.done():
            self._append_chat("system", "system", "Model is still responding. Wait for it to finish.")
            return

        self._append_chat("user", "You", prompt)
        model_key = self.active_model_key
        model_name = self._active_model_name
        message_index = self._append_chat("assistant", model_name, "thinking.")
        self._start_waiting_animation(message_index)
        self._response_task = asyncio.create_task(self._generate_and_stream_response(prompt, message_index, model_key, model_name))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        if self._handle_vcs_button(event.button.id):
            return
        if event.button.id == "app-exit":
            self.app.exit()
