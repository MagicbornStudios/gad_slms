from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
from queue import Empty, Queue
from threading import Event, Thread
from typing import Any

from .settings import ROOT


MODEL_PATH = ROOT / "models" / "vosk-model-small-en-us-0.15"


@dataclass
class SpeechSnapshot:
    final_text: str = ""
    partial_text: str = ""
    status: str = "idle"
    device: str = "default input"

    @property
    def transcript(self) -> str:
        return " ".join(part for part in (self.final_text, self.partial_text) if part).strip()


class LocalSpeechRecognizer:
    def __init__(self, model_path: Path = MODEL_PATH) -> None:
        self.model_path = model_path
        self._audio_queue: Queue[bytes] = Queue()
        self._stop_event = Event()
        self._thread: Thread | None = None
        self._stream: Any | None = None
        self._model: Any | None = None
        self._snapshot = SpeechSnapshot(status="ready", device=describe_default_input())

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        try:
            import sounddevice as sd
            from vosk import Model
        except Exception as error:
            self._snapshot.status = f"speech dependency error: {error}"
            return
        if not self.model_path.exists():
            self._snapshot.status = f"missing Vosk model: {self.model_path}"
            return

        self._stop_event.clear()
        self._audio_queue = Queue()
        device = _device_from_env()
        try:
            device_info = sd.query_devices(device, "input")
            sample_rate = int(device_info["default_samplerate"])
            device_name = str(device_info["name"])
        except Exception as error:
            self._snapshot.status = f"input device error: {error}"
            return

        if self._model is None:
            self._model = Model(str(self.model_path))

        def callback(indata: bytes, frames: int, time: object, status: object) -> None:
            if status:
                self._snapshot.status = f"audio status: {status}"
            self._audio_queue.put(bytes(indata))

        try:
            self._stream = sd.RawInputStream(
                samplerate=sample_rate,
                blocksize=8000,
                device=device,
                dtype="int16",
                channels=1,
                callback=callback,
            )
            self._stream.start()
        except Exception as error:
            self._snapshot.status = f"failed to start mic: {error}"
            self._stream = None
            return

        self._snapshot = SpeechSnapshot(status="listening", device=f"{device_name} ({sample_rate} Hz)")
        self._thread = Thread(target=self._recognize_loop, args=(sample_rate,), daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception as error:
                self._snapshot.status = f"mic close error: {error}"
            finally:
                self._stream = None
        if self._thread is not None:
            self._thread.join(timeout=1)
            self._thread = None
        self._snapshot.status = "stopped"

    def snapshot(self) -> SpeechSnapshot:
        return SpeechSnapshot(
            final_text=self._snapshot.final_text,
            partial_text=self._snapshot.partial_text,
            status=self._snapshot.status,
            device=self._snapshot.device,
        )

    def _recognize_loop(self, sample_rate: int) -> None:
        from vosk import KaldiRecognizer

        recognizer = KaldiRecognizer(self._model, sample_rate)
        final_parts: list[str] = []
        while not self._stop_event.is_set():
            try:
                data = self._audio_queue.get(timeout=0.2)
            except Empty:
                continue
            if recognizer.AcceptWaveform(data):
                text = _json_text(recognizer.Result(), "text")
                if text:
                    final_parts.append(text)
                self._snapshot.final_text = " ".join(final_parts).strip()
                self._snapshot.partial_text = ""
                self._snapshot.status = "listening"
            else:
                self._snapshot.partial_text = _json_text(recognizer.PartialResult(), "partial")
                self._snapshot.status = "listening"
        text = _json_text(recognizer.FinalResult(), "text")
        if text:
            final_parts.append(text)
        self._snapshot.final_text = " ".join(final_parts).strip()
        self._snapshot.partial_text = ""


def _device_from_env() -> int | str | None:
    value = os.getenv("SLM_TUI_AUDIO_DEVICE")
    if value is None or value.strip() == "":
        return None
    value = value.strip()
    if value.isdigit():
        return int(value)
    return value


def describe_default_input() -> str:
    try:
        import sounddevice as sd
    except Exception as error:
        return f"audio unavailable: {error}"
    try:
        device = _device_from_env()
        info = sd.query_devices(device, "input")
    except Exception as error:
        return f"input unavailable: {error}"
    return f"{info['name']} ({int(info['default_samplerate'])} Hz)"


def _json_text(payload: str, key: str) -> str:
    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        return ""
    return str(data.get(key, "")).strip()
