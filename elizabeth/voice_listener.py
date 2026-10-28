import re
import time
from collections import deque

import numpy as np
import pyaudio

from elizabeth.stt import transcribe_audio

SAMPLE_RATE = 16000
CHUNK = 1024
MIC_INDEX = 1

def listen_for_commands(callback):
    pa = pyaudio.PyAudio()
    mic = pa.open(
        format=pyaudio.paInt16,
        channels=1,
        rate=SAMPLE_RATE,
        input=True,
        input_device_index=MIC_INDEX,
        frames_per_buffer=CHUNK,
    )

    print("[Emilia] Escutando pelo Whisper...")
    prebuffer = deque(maxlen=8)
    recording = []
    speaking = False
    silence = 0

    try:
        while True:
            pcm = mic.read(CHUNK, exception_on_overflow=False)
            chunk = np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768.0
            rms = float(np.sqrt(np.mean(chunk ** 2)))

            if not speaking:
                prebuffer.append(chunk)
                if rms > 0.015:
                    speaking = True
                    recording = list(prebuffer)
                    silence = 0
            else:
                recording.append(chunk)

                if rms < 0.012:
                    silence += 1
                else:
                    silence = 0

                duration = len(recording) * CHUNK / SAMPLE_RATE

                if silence >= 13 or duration >= 15:
                    audio = np.concatenate(recording)
                    speaking = False
                    recording = []
                    prebuffer.clear()

                    if duration < 0.4:
                        continue

                    t_stt = time.perf_counter()
                    text = transcribe_audio(audio).strip()
                    print(
                        f"[Tempo] Whisper: {time.perf_counter() - t_stt:.2f}s "
                        f"| Audio: {duration:.2f}s"
                    )
                    if not text:
                        continue

                    print("[Whisper]", text)

                    match = re.search(
                        r"\b(?:emília|emilia|elizabeth)\b",
                        text,
                        flags=re.IGNORECASE,
                    )

                    if match:
                        command = text[match.end():].strip(" ,.!?:;-")
                        if command:
                            callback(command)
                        else:
                            print("[Emilia] Nome reconhecido, aguardando comando.")

    except KeyboardInterrupt:
        pass
    finally:
        mic.stop_stream()
        mic.close()
        pa.terminate()
