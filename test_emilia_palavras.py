import pyaudio
import numpy as np
from openwakeword.model import Model

MODEL = r'.\emilia_model\emilia.onnx'
DEVICE = 2
CHUNK = 1280
RATE = 16000
PHASES = (0, 20, 40, 60)

models = {p: Model(wakeword_model_paths=[MODEL]) for p in PHASES}
audio = pyaudio.PyAudio()
mic = audio.open(format=pyaudio.paInt16, channels=1, rate=RATE, input=True, input_device_index=DEVICE, frames_per_buffer=CHUNK)

def reset_models():
    for model in models.values():
        model.reset()

WORDS = ['Emilia','Familia','Emiliano','E minha','Emilio','Amelia','Maravilha']

def medir_pico():
    reset_models()
    peak = 0.0
    for _ in range(32):
        pcm = np.frombuffer(mic.read(CHUNK, exception_on_overflow=False), dtype=np.int16)
        for phase, model in models.items():
            pred = model.predict(pcm)
            score = float(pred.get('emilia', 0.0))
            peak = max(peak, score)
    return peak

try:
    print('=== TESTE INDIVIDUAL EMILIA ===')
    for word in WORDS:
        input(f'\nENTER e fale: {word} ')
        peak = medir_pico()
        print(f'{word:12s} -> PICO: {peak:.3f}')
finally:
    mic.stop_stream()
    mic.close()
    audio.terminate()
