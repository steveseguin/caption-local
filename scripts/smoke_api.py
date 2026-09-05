"""Probe a running deployment with real inference; never sends to a caption relay.
Requires dev environment dependencies. --spanish accepts a supplied test WAV.
"""
import argparse
import json
from pathlib import Path
import urllib.request
from faster_whisper.audio import decode_audio
import numpy as np

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--url', default='http://127.0.0.1:8765')
parser.add_argument('--spanish', type=Path)
parser.add_argument('--output', type=Path)
args = parser.parse_args()
base = args.url.rstrip('/')

def request(path, audio=None):
    req = urllib.request.Request(base+path, data=audio, headers={
        'Content-Type':'application/octet-stream', 'X-Caption-Local':'1'})
    with urllib.request.urlopen(req, timeout=120) as response:
        return json.load(response)

health = request('/health')
assert health['ready']
root = Path(__file__).resolve().parents[1]
fixture = root / 'samples/jfk.wav'
fixture.parent.mkdir(exist_ok=True)
if not fixture.exists():
    urllib.request.urlretrieve('https://raw.githubusercontent.com/ggml-org/whisper.cpp/master/samples/jfk.wav', fixture)
audio = decode_audio(str(fixture), sampling_rate=16000).astype('<f4').tobytes()
english = request('/transcribe?language=en', audio)
assert 'country' in english['text'].lower(), english
silence = request('/transcribe?language=en', np.zeros(32000, dtype='<f4').tobytes())
assert silence['text'] == ''
results = {'health':health, 'english':english, 'silence':silence}
if args.spanish:
    audio = decode_audio(str(args.spanish), sampling_rate=16000).astype('<f4').tobytes()
    spanish = request('/transcribe?language=es&mode=both', audio)
    assert 'gracias' in spanish['transcript'].lower() and 'teatro' in spanish['transcript'].lower(), spanish
    assert 'thank' in spanish['translation'].lower() and any(w in spanish['translation'].lower() for w in ('theater','theatre')), spanish
    assert spanish['language'] == 'es' and spanish['translation_language'] == 'en'
    translation = request('/transcribe?language=es&mode=translate', audio)
    assert translation['text'] and translation['text'] == translation['translation']
    assert translation['output_language'] == 'en' and not translation['transcript']
    results.update(spanish=spanish, translation_only=translation)
text = json.dumps(results, indent=2, ensure_ascii=False)+'\n'
if args.output:
    args.output.parent.mkdir(exist_ok=True, parents=True)
    args.output.write_text(text)
print(text)
