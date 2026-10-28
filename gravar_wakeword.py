import wave
import pyaudio
from pathlib import Path

OUTPUT_DIR = Path(__file__).parent / "wakeword_data" / "positive"

RATE = 44100
CHANNELS = 1
CHUNK = 1024
DEVICE_INDEX = 0
SECONDS = 2

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

p = pyaudio.PyAudio()

print()
print("======================================")
print("   GRAVADOR DE WAKE WORD - ELIZABETH")
print("======================================")
print()
print("Microfone: Fifine Microphone")
print()
print("Você vai gravar 30 exemplos.")
print()
print("Quando aparecer 'GRAVANDO', diga:")
print()
print("             Elizabeth")
print()
print("Varie um pouco a distância e a entonação.")
print()
print("Pressione ENTER para começar.")
input()

for i in range(1, 31):

    input(f"[{i}/30] ENTER para gravar...")

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
        data = stream.read(
            CHUNK,
            exception_on_overflow=False
        )
        frames.append(data)

    stream.stop_stream()
    stream.close()

    filename = OUTPUT_DIR / f"elizabeth_{i:03d}.wav"

    with wave.open(str(filename), "wb") as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(p.get_sample_size(pyaudio.paInt16))
        wf.setframerate(RATE)
        wf.writeframes(b"".join(frames))

    print(f"Salvo: {filename}")
    print()

p.terminate()

print("======================================")
print("30 gravações concluídas!")
print("======================================")
