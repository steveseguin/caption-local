"""Reproducible CPU probe, using a public speech fixture; no relay connection."""
import json
from pathlib import Path
import sys
import time
import urllib.request
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from faster_whisper.audio import decode_audio
from server import Engine

sample = Path('samples/jfk.wav')
sample.parent.mkdir(exist_ok=True)
if not sample.exists():
    urllib.request.urlretrieve('https://raw.githubusercontent.com/ggml-org/whisper.cpp/master/samples/jfk.wav', sample)
audio = decode_audio(str(sample), sampling_rate=16000)
results = []
for name in sys.argv[1:] or ['tiny.en', 'base.en']:
    start = time.perf_counter()
    engine = Engine(name)
    load = time.perf_counter() - start
    for label, data in [('full', audio), ('first_6s', audio[:96000]), ('second_6s', audio[96000:192000]), ('silence', np.zeros(96000, dtype=np.float32))]:
        start = time.perf_counter()
        text, language = engine.transcribe(data, 'en')
        elapsed = time.perf_counter() - start
        result = dict(model=name, fixture=label, audio_seconds=len(data)/16000,
                      inference_seconds=round(elapsed,3), realtime_factor=round(elapsed/(len(data)/16000),3),
                      load_seconds=round(load,3), text=text)
        results.append(result)
        print(json.dumps(result), flush=True)
Path('evidence/benchmark.json').write_text(json.dumps(results, indent=2)+'\n')
