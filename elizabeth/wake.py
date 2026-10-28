from __future__ import annotations

from pathlib import Path
from collections import deque
import queue
import threading
import time

import numpy as np
import yaml

_CONFIG_PATH = Path(__file__).parent.parent / "config.yaml"

_mic_pause = threading.Event()
_shutdown = threading.Event()

# Captura contÃ­nua para o STT usar o mesmo stream do wake word.
_stt_capture = threading.Event()
_stt_audio_queue = queue.Queue()
_recent_audio = deque(maxlen=32)  # 2.56 s com chunks de 1280 @ 16 kHz


def _load_config():
    with open(_CONFIG_PATH) as f:
        return yaml.safe_load(f)


def stop_wake_listener() -> None:
    _shutdown.set()
    _mic_pause.clear()


def pause_wake_mic() -> None:
    _mic_pause.set()


def resume_wake_mic() -> None:
    # Descarta Ã¡udio antigo antes de voltar a aceitar wake words.
    # O listener exigirÃ¡ o prÃ©-buffer encher novamente antes de detectar.
    _recent_audio.clear()
    _mic_pause.clear()


def start_stt_capture() -> None:
    """ComeÃ§a a encaminhar o Ã¡udio contÃ­nuo do wake word para o STT."""
    while True:
        try:
            _stt_audio_queue.get_nowait()
        except queue.Empty:
            break

    # Inclui Ã¡udio anterior Ã  detecÃ§Ã£o para nÃ£o perder
    # frases contÃ­nuas como "Elizabeth, que horas sÃ£o?"
    recent = list(_recent_audio)

    total_samples = sum(len(chunk) for chunk in recent)
    print(
        f"[STT BUFFER] {len(recent)} chunks | "
        f"{total_samples} samples | "
        f"{total_samples / 16000:.2f}s"
    )

    for chunk in recent:
        _stt_audio_queue.put(chunk.copy())

    _stt_audio_queue.put("__STT_LIVE__")  # marca: fim do prebuffer
    _stt_capture.set()


def stop_stt_capture() -> None:
    _stt_capture.clear()


def get_stt_audio_chunk(timeout: float = 1.0):
    try:
        return _stt_audio_queue.get(timeout=timeout)
    except queue.Empty:
        return None


def listen_for_wake_word(callback) -> None:
    import pyaudio
    import openwakeword
    from openwakeword.model import Model

    cfg = _load_config()["wake_word"]

    # Modelo customizado treinado para a palavra "Elizabeth"
    wakeword_path = (
        Path(__file__).parent.parent
        / "emilia_model"
        / "emilia.onnx"
    )

    if not wakeword_path.exists():
        raise FileNotFoundError(
            f"Modelo de wake word nÃ£o encontrado: {wakeword_path}"
        )

    print(f"[Wake] Modelo: {wakeword_path}")

    # Quatro detectores independentes com alinhamentos temporais diferentes.
    # O openWakeWord processa features em passos de 80 ms. Nosso modelo Elizabeth
    # mostrou forte sensibilidade Ã  fase dentro desses 80 ms, entÃ£o avaliamos
    # o mesmo Ã¡udio nas fases 0/20/40/60 ms e usamos o maior score.
    phase_offsets_ms = (0, 20, 40, 60)

    phase_models = {
        phase_ms: Model(
            wakeword_model_paths=[str(wakeword_path)]
        )
        for phase_ms in phase_offsets_ms
    }

    # ApÃ³s cada reset, cada detector precisa reaplicar seu deslocamento inicial.
    phase_initialized = {
        phase_ms: False
        for phase_ms in phase_offsets_ms
    }

    # Guarda pedaÃ§os iniciais pequenos demais para o openWakeWord.
    # A fase de 60 ms deixa apenas 320 samples no primeiro chunk,
    # enquanto o frontend exige no mÃ­nimo 400.
    phase_pending = {
        phase_ms: np.empty(0, dtype=np.int16)
        for phase_ms in phase_offsets_ms
    }

    # Nome interno do modelo customizado
    wakeword_key = "emilia"

    def reset_phase_models() -> None:
        for phase_ms, model in phase_models.items():
            model.reset()
            phase_initialized[phase_ms] = False
            phase_pending[phase_ms] = np.empty(0, dtype=np.int16)

    audio = pyaudio.PyAudio()

    mic = audio.open(
        format=pyaudio.paInt16,
        channels=1,
        rate=16000,
        input=True,
        input_device_index=2,
        frames_per_buffer=cfg["chunk_size"],
    )

    _busy = threading.Lock()
    _ignore_until = [0.0]

    print("[Elizabeth] Estou ouvindo pela palavra-chave...")

    try:
        while not _shutdown.is_set():

            # Pausa o microfone do wake word enquanto o STT grava
            if _mic_pause.is_set():

                if mic.is_active():
                    mic.stop_stream()
                    print("[Wake] Microfone pausado para gravaÃ§Ã£o.")

                while _mic_pause.is_set() and not _shutdown.is_set():
                    time.sleep(0.05)

                if _shutdown.is_set():
                    break

                mic.start_stream()
                reset_phase_models()

                print("[Wake] Microfone retomado.")
                continue

            try:
                pcm = np.frombuffer(
                    mic.read(
                        cfg["chunk_size"],
                        exception_on_overflow=False
                    ),
                    dtype=np.int16,
                )

            except Exception:
                time.sleep(0.05)
                continue

            _recent_audio.append(pcm.copy())

            # Enquanto o STT estÃ¡ capturando, este mesmo stream continua
            # lendo o microfone e envia os chunks diretamente para ele.
            if _stt_capture.is_set():
                _stt_audio_queue.put(pcm.copy())
                continue

            phase_scores = {}

            for phase_ms, model in phase_models.items():

                # Cada detector mantÃ©m uma fila prÃ³pria de Ã¡udio.
                # Na primeira entrada descartamos apenas o deslocamento da fase.
                # Depois alimentamos SEMPRE blocos exatos de 1280 samples,
                # preservando permanentemente as fases 0/20/40/60 ms.
                if not phase_initialized[phase_ms]:
                    offset_samples = int(16000 * phase_ms / 1000)
                    phase_pcm = pcm[offset_samples:]
                    phase_initialized[phase_ms] = True
                else:
                    phase_pcm = pcm

                if phase_pending[phase_ms].size:
                    phase_pending[phase_ms] = np.concatenate(
                        (phase_pending[phase_ms], phase_pcm)
                    )
                else:
                    phase_pending[phase_ms] = phase_pcm.copy()

                best_score = 0.0

                while phase_pending[phase_ms].size >= 1280:
                    model_pcm = phase_pending[phase_ms][:1280]
                    phase_pending[phase_ms] = phase_pending[phase_ms][1280:]

                    predictions = model.predict(model_pcm)
                    current_score = predictions.get(wakeword_key, 0)

                    if current_score > best_score:
                        best_score = current_score

                phase_scores[phase_ms] = best_score

            best_phase = max(
                phase_scores,
                key=phase_scores.get
            )

            score = phase_scores[best_phase]

            # Debug temporÃ¡rio: mostra o melhor alinhamento encontrado.
            if score >= 0.02:
                scores_text = " ".join(
                    f"{phase_ms}ms={phase_scores[phase_ms]:.3f}"
                    for phase_ms in phase_offsets_ms
                )

                print(
                    f"[Wake DEBUG] Elizabeth: {scores_text} "
                    f"| melhor={best_phase}ms"
                )

            if score < cfg["threshold"]:
                continue

            # Espera o prÃ©-buffer de Ã¡udio ficar completo antes de aceitar
            # a primeira wake apÃ³s iniciar o listener.
            if len(_recent_audio) < _recent_audio.maxlen:
                print(
                    f"[Wake] Ignorado durante aquecimento do Ã¡udio: "
                    f"{len(_recent_audio)}/{_recent_audio.maxlen} chunks"
                )
                continue

            print(
                f"[Wake] Palavra detectada! "
                f"Score: {score:.3f}"
            )

            # Debug: salva o Ã¡udio imediatamente anterior a cada wake.
            try:
                import wave

                debug_dir = Path("/tmp/elizabeth_wake_debug")
                debug_dir.mkdir(parents=True, exist_ok=True)

                debug_audio = np.concatenate(list(_recent_audio))
                debug_path = debug_dir / (
                    f"wake_{time.time_ns()}_score_{score:.3f}.wav"
                )

                with wave.open(str(debug_path), "wb") as wav:
                    wav.setnchannels(1)
                    wav.setsampwidth(2)
                    wav.setframerate(16000)
                    wav.writeframes(debug_audio.astype(np.int16).tobytes())

                print(f"[Wake DEBUG AUDIO] {debug_path}")

            except Exception as e:
                print(f"[Wake DEBUG AUDIO] Falha ao salvar: {e}")

            reset_phase_models()

            now = time.time()

            if now < _ignore_until[0]:
                continue

            if _busy.locked():

                _ignore_until[0] = now + 3.0
                print("[Wake] Ignorado: Elizabeth jÃ¡ estÃ¡ ocupada.")
                continue

            else:

                _ignore_until[0] = now + 2.0
                start_stt_capture()

                def _run():
                    with _busy:
                        callback()

                threading.Thread(
                    target=_run,
                    daemon=True
                ).start()

    finally:

        mic.stop_stream()
        mic.close()
        audio.terminate()

