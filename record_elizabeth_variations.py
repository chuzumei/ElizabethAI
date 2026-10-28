from pathlib import Path
import sounddevice as sd
import soundfile as sf

OUT = Path("wakeword_data/positive_variations")
OUT.mkdir(parents=True, exist_ok=True)

SAMPLE_RATE = 48000
DURATION = 2.5
TOTAL = 20

print("Vamos gravar 20 variações.")
print("Fale Elizabeth de formas naturais: rápido, devagar, baixo, alto, emendado com frase, etc.")
print()

existing = len(list(OUT.glob("elizabeth_var_*.wav")))

for i in range(1, TOTAL + 1):
    idx = existing + i
    input(f"[{i}/{TOTAL}] Pressione ENTER e fale...")
    print("Gravando...")
    audio = sd.rec(
        int(DURATION * SAMPLE_RATE),
        samplerate=SAMPLE_RATE,
        channels=1,
        dtype="float32",
    )
    sd.wait()

    path = OUT / f"elizabeth_var_{idx:03d}.wav"
    sf.write(path, audio, SAMPLE_RATE)

    print(f"Salvo: {path}")
    print()

print("=== Gravações concluídas ===")
