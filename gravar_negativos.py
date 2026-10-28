import sounddevice as sd
import soundfile as sf
from pathlib import Path
import time

RATE = 44100
CHANNELS = 1
DEVICE = 0
SECONDS = 2

OUT = Path(__file__).resolve().parent / "wakeword_data" / "negative"
OUT.mkdir(parents=True, exist_ok=True)

frases = [
    "olÃ¡",
    "bom dia",
    "boa tarde",
    "boa noite",
    "como vocÃª estÃ¡",
    "tudo bem",
    "pode me ajudar",
    "abra o navegador",
    "abra o computador",
    "que horas sÃ£o",
    "vamos jogar",
    "estÃ¡ funcionando",
    "ligue a mÃºsica",
    "pare a mÃºsica",
    "aumente o volume",
    "diminua o volume",
    "qual Ã© a previsÃ£o do tempo",
    "pesquise isso",
    "abra o YouTube",
    "feche a janela",
    "vamos comeÃ§ar",
    "pode executar",
    "faÃ§a isso",
    "me ajude",
    "computador",
    "assistente",
    "ei",
    "escute",
    "preste atenÃ§Ã£o",
    "vamos lÃ¡",
]

print(f"Gravando {len(frases)} exemplos negativos.")
print("Microfone: Fifine Microphone (device 0)")
print()

for i, frase in enumerate(frases, 1):
    input(f"[{i:02d}/{len(frases)}] Pressione ENTER e diga: \"{frase}\"")

    print("Gravando...")
    audio = sd.rec(
        int(SECONDS * RATE),
        samplerate=RATE,
        channels=CHANNELS,
        dtype="float32",
        device=DEVICE,
    )
    sd.wait()

    path = OUT / f"negative_{i:03d}.wav"
    sf.write(path, audio, RATE)

    print(f"Salvo: {path}")
    time.sleep(0.3)

print()
print("=== GRAVAÃ‡ÃƒO CONCLUÃDA ===")
