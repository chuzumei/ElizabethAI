from pathlib import Path
import re
import threading

import numpy as np
import openvino as ov
import sounddevice as sd
from kitsune.api import KitsuneSynthesizer


_ROOT = Path(__file__).parent.parent
_KITSUNE_DIR = _ROOT / "Kitsune-TTS" / "Kitsune-TTS-main"
_MODEL = _KITSUNE_DIR / "model" / "kitsune39M.onnx"
_CONFIG = _KITSUNE_DIR / "model" / "model_config.json"

_speaking = threading.Event()
_interrupt = threading.Event()
_lock = threading.Lock()

_tts = None
_core = None
_model = None


def _get_tts():
    global _tts
    if _tts is None:
        print("[TTS] Carregando Kitsune...")
        _tts = KitsuneSynthesizer(
            onnx_path=str(_MODEL),
            config=str(_CONFIG),
            ort_threads=2,
        )
        print("[TTS] Voz: emilia")
    return _tts


def _get_model(sequence_length: int = 0):
    global _core, _model

    if _model is None:
        if _core is None:
            _core = ov.Core()

        print("[TTS] Compilando OpenVINO CPU (modelo dinâmico)...")
        model = _core.read_model(str(_MODEL))
        _model = _core.compile_model(model, "CPU")
        print("[TTS] OpenVINO pronto.")

    return _model
def _synthesize(text: str) -> np.ndarray:
    if not text or not text.strip():
        return np.empty(0, dtype=np.float32)

    tts = _get_tts()
    sequence = tts._text_to_sequence(text, "pt-br")
    speaker_id = tts._resolve_speaker("emilia")
    model = _get_model(len(sequence))

    inputs = {
        "x": np.asarray(sequence, dtype=np.int64)[None, :],
        "x_lengths": np.asarray([len(sequence)], dtype=np.int64),
        "sid": np.asarray([speaker_id], dtype=np.int64),
        "noise_scale": np.asarray([0.667], dtype=np.float32),
        "length_scale": np.asarray([1.0], dtype=np.float32),
    }

    audio = model(inputs)[model.output(0)][0, 0]
    return np.asarray(audio, dtype=np.float32)


def _split_sentences(text: str) -> list[str]:
    parts = re.split(r'(?<=[.!?])\s+', text)
    return [p.strip() for p in parts if p.strip()]


def speak_to_bytes(text: str) -> bytes:
    audio = _synthesize(text)
    if audio.size == 0:
        return b""

    pcm = (np.clip(audio, -1, 1) * 32767).astype(np.int16)
    return pcm.tobytes()


def is_speaking() -> bool:
    return _speaking.is_set()


def stop_speaking() -> None:
    _interrupt.set()
    sd.stop()
    _speaking.clear()


def _play(audio: np.ndarray) -> bool:
    if audio.size == 0 or _interrupt.is_set():
        return False

    tts = _get_tts()

    _speaking.set()
    sd.play(audio, samplerate=tts.sample_rate)

    while sd.get_stream() and sd.get_stream().active:
        if _interrupt.wait(0.05):
            sd.stop()
            return False

    return not _interrupt.is_set()


def speak(text: str) -> None:
    with _lock:
        _interrupt.clear()
        try:
            audio = _synthesize(text)
            _play(audio)
        finally:
            sd.stop()
            _speaking.clear()
            _interrupt.clear()


def speak_streamed(text: str) -> None:
    with _lock:
        _interrupt.clear()

        try:
            sentences = _split_sentences(text)

            if not sentences:
                return

            for sentence in sentences:
                if _interrupt.is_set():
                    break

                audio = _synthesize(sentence)

                if _interrupt.is_set():
                    break

                if not _play(audio):
                    break
        finally:
            sd.stop()
            _speaking.clear()
            _interrupt.clear()

