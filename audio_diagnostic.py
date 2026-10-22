import numpy as np
from psychtoolbox import audio
from psychopy import core

print("Opening Realtek audio device...", flush=True)

stream = None

try:
    stream = audio.Stream(
        device_id=4,
        mode=1,
        freq=48000,
        channels=2
    )

    print("Stream opened successfully!", flush=True)

    sample_rate = 48000
    duration = 1.0

    t = np.arange(int(sample_rate * duration)) / sample_rate
    tone = 0.8 * np.sin(2 * np.pi * 800 * t)

    # Two-channel audio, with channels arranged in rows
    stereo_tone = np.column_stack([tone, tone]).astype(np.float32)

    print("Loading beep...", flush=True)

    # Use the stream directly rather than creating a slave
    stream.fill_buffer(stereo_tone)

    print("Playing beep...", flush=True)

    stream.start()
    core.wait(1.5)
    stream.stop()

    print("Beep test completed successfully!", flush=True)

except Exception as e:
    print("Audio error:", repr(e), flush=True)

finally:
    if stream is not None:
        stream.close()