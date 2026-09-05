"""Provision public/synthetic fixtures; never uploads audio."""
import argparse
from pathlib import Path
import shutil
import subprocess
import urllib.request

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--espeak', default=shutil.which('espeak-ng'),
                    help='Path to espeak-ng executable; needed only if Spanish WAV is missing')
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
samples = root / 'samples'
samples.mkdir(exist_ok=True)
for name, url in {
    'jfk.wav': 'https://raw.githubusercontent.com/ggml-org/whisper.cpp/master/samples/jfk.wav',
    'librispeech.parquet': 'https://huggingface.co/datasets/hf-internal-testing/librispeech_asr_dummy/resolve/main/clean/validation-00000-of-00001.parquet',
}.items():
    target = samples / name
    if not target.exists():
        temporary = target.with_suffix(target.suffix + '.download')
        urllib.request.urlretrieve(url, temporary)
        temporary.replace(target)
if not (samples / 'spanish.wav').exists():
    if not args.espeak:
        raise SystemExit('Supply --espeak PATH or prepare samples/spanish.wav using the exact sentence in DEPLOYMENT.md, then rerun.')
    subprocess.run([args.espeak, '-v', 'es', '-s', '140', '-w', str(samples/'spanish.wav'),
                    'Hola. Bienvenidos al teatro. Muchas gracias por venir esta noche.'], check=True)
# The continuous browser test loops speech plus a pause.
import wave
import numpy as np
from faster_whisper.audio import decode_audio
loop = np.concatenate([decode_audio(str(samples/'jfk.wav')), np.zeros(16000, np.float32)])
with wave.open(str(samples/'soak.wav'), 'wb') as output:
    output.setnchannels(1); output.setsampwidth(2); output.setframerate(16000)
    output.writeframes((loop*32767).astype('<i2').tobytes())
print('Public English, synthetic Spanish and browser-loop fixtures ready in samples/.')
