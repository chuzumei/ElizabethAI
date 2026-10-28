from pathlib import Path
import yaml
import numpy as np

_CONFIG_PATH = Path(__file__).parent.parent / "config.yaml"

def _load_config():
    with open(_CONFIG_PATH) as f:
        return yaml.safe_load(f)

_model = None
_model_device = None  # track what device the model is on

try:
    from faster_whisper import WhisperModel
except ImportError:
    WhisperModel = None  # type: ignore

def _get_model(force_cpu=False):
    global _model, _model_device
    if _model is not None and not force_cpu:
        return _model
    cfg = _load_config()
    stt = cfg["stt"]
    device = "cpu" if force_cpu else stt["device"]
    compute_type = "int8" if force_cpu else stt["compute_type"]
    try:
        _model = WhisperModel(stt["model"], device=device, compute_type=compute_type)
        _model_device = device
        print(f"[STT] Loaded {stt['model']} on {device}")
    except Exception as e:
        if device != "cpu":
            print(f"[STT] {device} failed to load ({e}), falling back to CPU")
            _model = WhisperModel(stt["model"], device="cpu", compute_type="int8")
            _model_device = "cpu"
            print(f"[STT] Loaded {stt['model']} on cpu")
        else:
            raise
    return _model

def transcribe_audio(audio: np.ndarray) -> str:
    """Transcribe a float32 numpy audio array (16kHz mono) to text."""
    try:
        model = _get_model()
        segments, _ = model.transcribe(
            audio,
            language="pt",
            beam_size=1,
            vad_filter=False,

        )
        text = " ".join(seg.text.strip() for seg in segments).strip()


        return text
    except Exception as e:
        # If CUDA worked for loading but fails during inference, retry on CPU
        if _model_device != "cpu":
            print(f"[STT] {_model_device} transcription failed ({e}), reloading on CPU")
            try:
                model = _get_model(force_cpu=True)
                segments, _ = model.transcribe(
                    audio,
                    language="pt",
                    beam_size=1,
                    vad_filter=False,

                )
                return " ".join(seg.text.strip() for seg in segments).strip()
            except Exception as e2:
                print(f"[STT] CPU transcription also failed: {e2}")
                return ""
        print(f"[STT] Transcription failed: {e}")
        return ""

# Global abort event â€” set by main.py so recording can be interrupted
_abort_event = None

def set_abort_event(event) -> None:
    """Register the global abort event so recording checks it."""
    global _abort_event
    _abort_event = event

def record_until_silence(
    sample_rate: int = 16000,
    silence_threshold: float = 0.012,
    max_seconds: int = 30,
) -> np.ndarray:
    """Consume o Ã¡udio contÃ­nuo capturado pelo wake word atÃ© detectar silÃªncio."""
    from elizabeth.wake import get_stt_audio_chunk, stop_stt_capture

    recording = []
    silent_chunks = 0
    silent_chunks_needed = 13  # ~1.0s de silÃªncio
    heard_speech = False
    speech_threshold = 0.015
    live_audio = False  # False enquanto consumimos o prebuffer

    try:
        while True:
            if _abort_event and _abort_event.is_set():
                print("[STT] Recording aborted.")
                break

            pcm = get_stt_audio_chunk(timeout=1.0)
            if pcm is None:
                continue

            if isinstance(pcm, str) and pcm == "__STT_LIVE__":
                live_audio = True
                silent_chunks = 0
                print("[STT] Prebuffer concluido; capturando audio ao vivo.")
                continue

            flat = pcm.astype(np.float32) / 32768.0
            recording.append(flat)

            rms = float(np.sqrt(np.mean(flat ** 2)))

            if rms >= speech_threshold:
                if not heard_speech:
                    print(f"[STT] Speech detected (rms={rms:.4f})")
                heard_speech = True
                silent_chunks = 0
            elif heard_speech and live_audio:
                silent_chunks += 1

            if heard_speech and silent_chunks >= silent_chunks_needed:
                print("[STT] Silence detected, stopping recording.")
                break

            total_samples = sum(len(x) for x in recording)
            if total_samples >= max_seconds * sample_rate:
                print(f"[STT] Max recording time reached ({max_seconds}s)")
                break

    finally:
        stop_stt_capture()

    if not recording:
        return np.zeros(int(sample_rate * 0.2), dtype=np.float32)

    audio = np.concatenate(recording)

    try:
        from scipy.io import wavfile
        wavfile.write(
            "/tmp/debug_stt.wav",
            sample_rate,
            (np.clip(audio, -1.0, 1.0) * 32767).astype(np.int16),
        )
        print("[STT DEBUG] Ãudio salvo em /tmp/debug_stt.wav")
    except Exception as e:
        print(f"[STT DEBUG] Falha ao salvar Ã¡udio: {e}")

    return audio



