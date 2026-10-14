"""Create public synthetic microphone inputs in a disposable Mint worker."""
from pathlib import Path
import subprocess
import wave
import numpy as np
from faster_whisper.audio import decode_audio

assert subprocess.run(['systemd-detect-virt', '--vm'], capture_output=True).returncode == 0
root = Path.home()/'feedback-fixtures'
root.mkdir(exist_ok=True)
phrases = [
    'Transcript number one. Apples are red.',
    'Transcript number two. Bananas are yellow.',
    'Transcript number three. The ocean is blue.',
    'Transcript number four. The forest is green.',
    'Transcript number five. Snow is white.',
    'Transcript number six. Oranges are orange.',
]
for number, text in enumerate(phrases, 1):
    raw = root/f'raw-{number}.wav'
    subprocess.run(['espeak-ng', '-s', '145', '-w', str(raw), text], check=True)
    samples = decode_audio(str(raw), sampling_rate=16000)
    samples = np.concatenate([np.zeros(6400), samples, np.zeros(9600)])
    for name, gain in [(str(number), 1), (f'soft-{number}', .15)]:
        with wave.open(str(root/f'{name}.wav'), 'wb') as out:
            out.setparams((1, 2, 16000, len(samples), 'NONE', 'not compressed'))
            out.writeframes((samples * gain * 32767).astype(np.int16).tobytes())
    print(number, text, round(len(samples)/16000, 2))
