import wave
import pyaudio
from pathlib import Path

OUTPUT_DIR = Path(__file__).parent / "wakeword_data" / "emilia_positive_16k"

RATE = 16000
CHANNELS = 1
CHUNK = 1280
DEVICE_INDEX = 2
SECONDS = 2.5
TOTAL = 50

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

p = pyaudio.PyAudio()

print()
print("======================================")
print("      GRAVADOR DE WAKE WORD - EMILIA")
print("======================================")
print()
print("Microfone: Fifine Microphone (dispositivo 2)")
print("Formato: 16 kHz / mono")
print()
print("Voce vai gravar 50 exemplos.")
print("MANTENHA o microfone na posicao normal de uso.")
print()
print("Fale 'Emilia' naturalmente.")
print("Varie volume, velocidade, angulo e um pouco a distancia.")
print("Em algumas gravacoes, emende com um comando, por exemplo:")
print("Emilia, abra o bloco de notas")
print()

for i in range(1, TOTAL + 1):
    input(f"[{i}/{TOTAL}] ENTER para gravar...")

    print(">>> GRAVANDO <<<")

    stream = p.open(
        format=pyaudio.paInt16,
        channels=CHANNELS,
        rate=RATE,
        input=True,
        input_device_index=DEVICE_INDEX,
        frames_per_buffer=CHUNK,
    )

    frames = []

    for _ in range(int(RATE / CHUNK * SECONDS)):
        data = stream.read(CHUNK, exception_on_overflow=False)
        frames.append(data)

    stream.stop_stream()
    stream.close()

    filename = OUTPUT_DIR / f"emilia_{i:03d}.wav"

    with wave.open(str(filename), "wb") as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(p.get_sample_size(pyaudio.paInt16))
        wf.setframerate(RATE)
        wf.writeframes(b"".join(frames))

    print(f"Salvo: {filename}")
    print()

p.terminate()

print("======================================")
print("50 gravacoes da Emilia concluidas!")
print("======================================")
