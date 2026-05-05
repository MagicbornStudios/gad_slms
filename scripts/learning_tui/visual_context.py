from __future__ import annotations

from rich.text import Text
from textual.widgets import Button, Static

from . import icons
from .local_speech import LocalSpeechRecognizer
from .models import VisualContextTarget
from .settings import VCS_ENABLED


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
        self.vcs_speech_transcript = ""
        self.vcs_transcript = ""
        self.vcs_locked_target_id: str | None = None
        self.vcs_selected_target_id = self.vcs_targets[0].id if self.vcs_targets else None

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
        strip = self.query_one("#app-banner-vcs-strip")
        strip.display = self.vcs_visible
        for tag in self.query(".vcs-id-tag"):
            tag.display = self.vcs_visible
        target = self._active_vcs_target()
        for candidate in self.vcs_targets:
            tag = self.query_one(f"#vcs-tag-{candidate.id}", Button)
            tag.set_class(candidate.id == target.id, "vcs-selected")
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
        lock_status = "locked" if self.vcs_locked_target_id is not None else "unlocked"
        button = self.query_one("#vcs-quick-prompt", Button)
        status = self.query_one("#app-banner-vcs-status", Static)
        snapshot = self.vcs_speech_recognizer.snapshot()
        if self.vcs_recording:
            button.label = f"{icons.STOP} stop"
            button.set_class(True, "vcs-recording-button")
            line = Text()
            line.append(f"{icons.VCS} ", style="bold #ebcb8b")
            line.append("target ", style="dim #8b6914")
            line.append(target.id, style="bold #ffd77a")
            line.append("   ", style="")
            line.append("mic ", style="dim #8b6914")
            line.append(snapshot.status, style="#e6d8bd")
            line.append("   ", style="")
            line.append("live ", style="dim #8b6914")
            line.append(self.vcs_transcript or "listening…", style="#f5ecd8")
            line.append("   ", style="")
            line.append(lock_status, style="italic #c4a574")
            status.update(line)
            return
        button.label = f"{icons.RECORD} click to record"
        button.set_class(False, "vcs-recording-button")
        line = Text()
        line.append(f"{icons.VCS} ", style="bold #ebcb8b")
        line.append("target ", style="dim #8b6914")
        line.append(target.id, style="bold #ffd77a")
        line.append("   ", style="")
        line.append("file ", style="dim #8b6914")
        line.append(target.source_file, style="#e6d8bd")
        line.append("   ", style="")
        line.append(lock_status, style="italic #c4a574")
        status.update(line)

    def _tick_vcs_recorder(self) -> None:
        if not self.vcs_recording:
            return
        self.vcs_recording_ticks += 1
        self._refresh_vcs_speech_transcript()
        self._sync_vcs_recorder_view()

    def _start_vcs_recording(self) -> None:
        self.vcs_recording = True
        self.vcs_recording_ticks = 0
        self.vcs_speech_transcript = ""
        self.vcs_transcript = ""
        self.vcs_last_output = "recording started; listening to local microphone"
        self.vcs_speech_recognizer.start()
        if self.vcs_recording_timer is None:
            self.vcs_recording_timer = self.set_interval(0.5, self._tick_vcs_recorder)
        else:
            self.vcs_recording_timer.resume()
        self._sync_visual_context()
        self.notify(f"{icons.RECORD} VCS recording started")

    def _stop_vcs_recording(self, copy_prompt: bool = True) -> None:
        self.vcs_recording = False
        if self.vcs_recording_timer is not None:
            self.vcs_recording_timer.pause()
        target = self._active_vcs_target()
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
            )
            if part
        ).strip()

    def _handle_vcs_button(self, button_id: str | None) -> bool:
        if button_id is not None and button_id.startswith("vcs-tag-"):
            self._set_vcs_selected_target(button_id.removeprefix("vcs-tag-"))
            self.notify(f"{icons.CODE} Selected {self.vcs_selected_target_id}")
            return True
        if button_id == "vcs-quick-prompt":
            if not self.vcs_visible:
                return False
            if self.vcs_recording:
                self._stop_vcs_recording()
            else:
                self._start_vcs_recording()
            return True
        return False
