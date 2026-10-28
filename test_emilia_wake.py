import pyaudio
import numpy as np
from openwakeword.model import Model

MODEL = r".\emilia_model\emilia.onnx"
DEVICE = 2
CHUNK = 1280
RATE = 16000
PHASES = (0, 20, 40, 60)

models = {p: Model(wakeword_model_paths=[MODEL]) for p in PHASES}
initialized = {p: False for p in PHASES}
pending = {p: np.empty(0, dtype=np.int16) for p in PHASES}

audio = pyaudio.PyAudio()
mic = audio.open(format=pyaudio.paInt16, channels=1, rate=RATE, input=True, input_device_index=DEVICE, frames_per_buffer=CHUNK)

print("=== TESTE WAKE WORD EMILIA ===")
print("Fale 'Emilia' normalmente. Ctrl+C para sair.")

try:
    while True:
        pcm = np.frombuffer(mic.read(CHUNK, exception_on_overflow=False), dtype=np.int16)
        scores = {}

        for phase, model in models.items():
            if not initialized[phase]:
                offset = int(RATE * phase / 1000)
                part = pcm[offset:]
                initialized[phase] = True
            else:
                part = pcm

            pending[phase] = np.concatenate((pending[phase], part))
            best = 0.0

            while pending[phase].size >= CHUNK:
                block = pending[phase][:CHUNK]
                pending[phase] = pending[phase][CHUNK:]
                pred = model.predict(block)
                score = float(pred.get("emilia", 0))
                best = max(best, score)

            scores[phase] = best

        best_phase = max(scores, key=scores.get)
        score = scores[best_phase]

        if score >= 0.20:
            values = " ".join(f"{p}ms={scores[p]:.3f}" for p in PHASES)
            print(f"{values} | MELHOR={score:.3f} ({best_phase}ms)")

except KeyboardInterrupt:
    print("\nTeste encerrado.")

finally:
    mic.stop_stream()
    mic.close()
    audio.terminate()
