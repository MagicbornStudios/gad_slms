from __future__ import annotations

from textual.app import ComposeResult
from textual.widgets import Button, Input, Static

from . import icons
from .local_speech import LocalSpeechRecognizer
from .models import VisualContextTarget
from .settings import VCS_ENABLED
from .vcs_footer import VcsFooter


class VisualContextMixin:
    vcs_targets: tuple[VisualContextTarget, ...] = ()
    vcs_route = "/"

    def _setup_visual_context(self) -> None:
        self.vcs_visible = False
        self.vcs_recording = False
        self.vcs_recording_ticks = 0
        self.vcs_last_output = "idle"
        self.vcs_recording_timer = None
        self.vcs_speech_recognizer = LocalSpeechRecognizer()
        self.vcs_typed_transcript = ""
        self.vcs_speech_transcript = ""
        self.vcs_transcript = ""
        self.vcs_locked_target_id: str | None = None
        self.vcs_selected_target_id = self.vcs_targets[0].id if self.vcs_targets else None

    def _compose_visual_context_footer(self) -> ComposeResult:
        if not VCS_ENABLED:
            return
        yield VcsFooter(self.vcs_targets, self.vcs_route)

    def _target_by_id(self, target_id: str | None) -> VisualContextTarget:
        if target_id is not None:
            for target in self.vcs_targets:
                if target.id == target_id:
                    return target
        return self.vcs_targets[0]

    def _active_vcs_target(self) -> VisualContextTarget:
        locked_target = self.vcs_locked_target_id
        if locked_target is not None:
            return self._target_by_id(locked_target)
        return self._target_by_id(self.vcs_selected_target_id)

    def _sync_visual_context(self) -> None:
        if not VCS_ENABLED or not self.vcs_targets:
            return
        self.set_class(self.vcs_visible, "vcs-dev")
        self.set_class(self.vcs_recording, "vcs-recording")
        footer = self.query_one("#vcs-footer", VcsFooter)
        footer.display = self.vcs_visible
        textual_footer = self.query_one("#textual-footer")
        textual_footer.display = not self.vcs_visible
        for tag in self.query(".vcs-id-tag"):
            tag.display = self.vcs_visible
        target = self._active_vcs_target()
        for candidate in self.vcs_targets:
            tag = self.query_one(f"#vcs-tag-{candidate.id}", Button)
            tag.set_class(candidate.id == target.id, "vcs-selected")
        lock_status = "locked" if self.vcs_locked_target_id is not None else "unlocked"
        status = self.query_one("#vcs-footer-status", Static)
        status.update(
            f"{icons.VCS} VCS dev mode: click an id on screen, then use VCS Quick Prompt. "
            f"selected={target.id} route={self.vcs_route} source={target.source_file} state={lock_status}"
        )
        self._sync_vcs_recorder_view()

    def _set_vcs_selected_target(self, target_id: str | None) -> None:
        if target_id is None:
            return
        self.vcs_selected_target_id = target_id
        if self.vcs_recording:
            self.vcs_last_output = f"target switched to {target_id}; recorder prompt will use this id"
        self._sync_visual_context()

    def _toggle_visual_context(self) -> None:
        if not VCS_ENABLED:
            self.notify("Visual context is disabled. Set SLM_TUI_VCS=1 to enable it.", severity="warning")
            return
        self.vcs_visible = not self.vcs_visible
        if not self.vcs_visible and self.vcs_recording:
            self._stop_vcs_recording(copy_prompt=False)
        self._sync_visual_context()

    def _toggle_vcs_lock(self) -> None:
        if self.vcs_locked_target_id is None:
            self.vcs_locked_target_id = self.vcs_selected_target_id
            self.notify(f"{icons.LOCK} Locked visual context to {self.vcs_locked_target_id}")
        else:
            self.vcs_locked_target_id = None
            self.notify(f"{icons.UNLOCK} Unlocked visual context")
        self._sync_visual_context()

    def _copy_vcs_prompt(self) -> None:
        target = self._active_vcs_target()
        prompt = (
            "operation: VCS_QUICK_PROMPT\n"
            f"target id: {target.id}\n"
            f"route: {self.vcs_route}\n"
            f"source file: {target.source_file}\n"
            f"source hint: {target.source_hint}\n\n"
            "intent: update, delete, create-nearby, read, or explain this target\n"
            "transcript:\n"
            f"{self.vcs_transcript or '[empty transcript]'}\n"
        )
        try:
            self.app.copy_to_clipboard(prompt)
        except Exception as error:
            self.notify(f"Clipboard copy failed: {error}", severity="error")
        else:
            self.notify(f"{icons.COPY} Copied VCS quick prompt for {target.id}")

    def _sync_vcs_recorder_view(self) -> None:
        if not VCS_ENABLED or not self.vcs_targets:
            return
        target = self._active_vcs_target()
        button = self.query_one("#vcs-quick-prompt", Button)
        recorder_input = self.query_one("#vcs-recorder-input", Input)
        speech_status = self.query_one("#vcs-speech-bridge", Static)
        live_input = self.query_one("#vcs-live-input", Static)
        snapshot = self.vcs_speech_recognizer.snapshot()
        if self.vcs_recording:
            button.label = f"{icons.STOP} Stop & Copy"
            button.set_class(True, "vcs-recording-button")
            recorder_input.disabled = False
            speech_status.update(f"{icons.AUDIO} local mic: {snapshot.device} | {snapshot.status}")
            live_input.update(f"{icons.RECORD} {self.vcs_transcript or '[listening...]'}")
            return
        button.label = f"{icons.RECORD} Quick Prompt"
        button.set_class(False, "vcs-recording-button")
        recorder_input.disabled = True
        speech_status.update(f"{icons.AUDIO} local mic: {snapshot.device} | {snapshot.status}")
        live_input.update(f"{icons.COPY} selected={target.id}; click Quick Prompt to record")

    def _tick_vcs_recorder(self) -> None:
        if not self.vcs_recording:
            return
        self.vcs_recording_ticks += 1
        self._refresh_vcs_speech_transcript()
        self._sync_vcs_recorder_view()

    def _start_vcs_recording(self) -> None:
        self.vcs_recording = True
        self.vcs_recording_ticks = 0
        self.vcs_typed_transcript = ""
        self.vcs_speech_transcript = ""
        self.vcs_transcript = ""
        self.vcs_last_output = "recording started; listening to local microphone"
        recorder_input = self.query_one("#vcs-recorder-input", Input)
        recorder_input.value = ""
        recorder_input.disabled = False
        self.vcs_speech_recognizer.start()
        if self.vcs_recording_timer is None:
            self.vcs_recording_timer = self.set_interval(0.5, self._tick_vcs_recorder)
        else:
            self.vcs_recording_timer.resume()
        self._sync_visual_context()
        recorder_input.focus()
        self.notify(f"{icons.RECORD} VCS recording started")

    def _stop_vcs_recording(self, copy_prompt: bool = True) -> None:
        self.vcs_recording = False
        if self.vcs_recording_timer is not None:
            self.vcs_recording_timer.pause()
        target = self._active_vcs_target()
        recorder_input = self.query_one("#vcs-recorder-input", Input)
        self.vcs_typed_transcript = recorder_input.value.strip()
        self._refresh_vcs_speech_transcript()
        self.vcs_speech_recognizer.stop()
        self._update_combined_vcs_transcript()
        self.vcs_last_output = f"captured quick prompt for {target.id}" if copy_prompt else "recording cancelled"
        self._sync_visual_context()
        if copy_prompt:
            self._copy_vcs_prompt()

    def _refresh_vcs_speech_transcript(self) -> None:
        snapshot = self.vcs_speech_recognizer.snapshot()
        if snapshot.transcript:
            self.vcs_speech_transcript = snapshot.transcript
        self.vcs_last_output = f"speech status: {snapshot.status}; device: {snapshot.device}"
        self._update_combined_vcs_transcript()

    def _update_combined_vcs_transcript(self) -> None:
        self.vcs_transcript = "\n".join(
            part
            for part in (
                f"speech: {self.vcs_speech_transcript}" if self.vcs_speech_transcript else "",
                f"typed: {self.vcs_typed_transcript}" if self.vcs_typed_transcript else "",
            )
            if part
        ).strip()

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id != "vcs-recorder-input":
            return
        event.stop()
        self.vcs_typed_transcript = event.value
        self._update_combined_vcs_transcript()
        if self.vcs_recording:
            self._sync_vcs_recorder_view()

    def _handle_vcs_button(self, button_id: str | None) -> bool:
        if button_id is not None and button_id.startswith("vcs-tag-"):
            self._set_vcs_selected_target(button_id.removeprefix("vcs-tag-"))
            self.notify(f"{icons.CODE} Selected {self.vcs_selected_target_id}")
            return True
        if button_id == "vcs-quick-prompt":
            if self.vcs_recording:
                self._stop_vcs_recording()
            else:
                self._start_vcs_recording()
            return True
        return False
