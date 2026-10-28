import sounddevice as sd
from openwakeword.model import Model

model = Model(
    wakeword_models=["openwakeword-training~/elizabeth_model/elizabeth.onnx"],
    inference_framework="onnx"
)

print("Ouvindo pelo Fifine Microphone (dispositivo 2)...")
print("Diga Elizabeth algumas vezes. Ctrl+C para encerrar.")

try:
    with sd.InputStream(
        device=2,
        samplerate=16000,
        channels=1,
        dtype="int16",
        blocksize=1280
    ) as stream:
        while True:
            audio, _ = stream.read(1280)
            score = model.predict(audio[:, 0].copy()).get("elizabeth", 0)
            if score >= 0.1:
                print(f"Elizabeth: {score:.3f}", flush=True)
except KeyboardInterrupt:
    print("\nTeste encerrado.")
