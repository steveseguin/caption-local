"""Deterministic CPU regression gate: real speech, rolling boundaries, silence.
Downloads a small public LibriSpeech test parquet on first run; samples stay local.
"""
import argparse
import json
from pathlib import Path
import re
import sys
import time
import urllib.request

import numpy as np
import pyarrow.parquet as pq
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from server import Engine
from faster_whisper.audio import decode_audio

root = Path(__file__).resolve().parents[1]
samples = root/'samples'
parquet = samples/'librispeech.parquet'
if not parquet.exists():
    urllib.request.urlretrieve('https://huggingface.co/datasets/hf-internal-testing/librispeech_asr_dummy/resolve/main/clean/validation-00000-of-00001.parquet', parquet)
rows = pq.read_table(parquet).to_pylist()

def words(text):
    return re.findall(r"[a-z]+(?:'[a-z]+)?", text.lower())

def wer(reference, hypothesis):
    a, b = words(reference), words(hypothesis)
    row = list(range(len(b)+1))
    for i, word in enumerate(a, 1):
        nxt = [i]
        for j, other in enumerate(b, 1):
            nxt.append(min(row[j]+1, nxt[j-1]+1, row[j-1]+(word != other)))
        row = nxt
    return row[-1]/max(1,len(a))

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('model',nargs='?',default='small')
parser.add_argument('--beam-size',type=int,default=5)
parser.add_argument('--output',default='evidence/quality-gate.json')
args=parser.parse_args()
engine = Engine(args.model, offline=True, beam_size=args.beam_size)
engine.warmup()
results = []
# Fixed first eight recordings over eight seconds; avoid selecting by accuracy.
fixtures = []
for row in rows:
    import io
    audio = decode_audio(io.BytesIO(row['audio']['bytes']))
    if len(audio) >= 8*16000:
        fixtures.append((row['id'], audio, row['text']))
    if len(fixtures)==8: break
fixtures.insert(0, ('jfk', decode_audio(str(samples/'jfk.wav')), 'And so my fellow Americans ask not what your country can do for you ask what you can do for your country'))
for name, audio, reference in fixtures:
    # Match a live client with six seconds of fresh speech, 500 ms context,
    # and the last second withheld until decoded with future audio.
    offset = 0; context = 0; text = []; times = []
    while offset < len(audio):
        end = min(len(audio), offset+96000+round(context*16000))
        final = end == len(audio)
        start = time.perf_counter()
        caption, _, committed = engine.window(audio[offset:end], 'en', context, final)
        times.append(time.perf_counter()-start)
        text.append(caption)
        consumed = round(committed*16000) if final else max(1, round(committed*16000)-8000)
        assert consumed > 0
        offset += consumed
        context = 0 if final else (round(committed*16000)-consumed)/16000
    hypothesis = ' '.join(text)
    result = {'fixture':name, 'reference':reference, 'transcript':hypothesis,
              'wer':round(wer(reference,hypothesis),4), 'audio_seconds':len(audio)/16000,
              'inference_seconds':round(sum(times),3), 'max_window_seconds':round(max(times),3)}
    results.append(result)
    print(json.dumps(result), flush=True)
checks={}
for kind, audio in [('silence',np.zeros(96000,np.float32)),
                    ('noise',np.random.default_rng(42).normal(0,0.003,96000).astype(np.float32))]:
    text, _, _ = engine.window(audio,'en',0,True)
    checks[kind+'_empty']=not text
    results.append({'fixture':kind,'transcript':text})
spanish = decode_audio(str(samples/'spanish.wav'))
text, _ = engine.transcribe(spanish,'es')
translated, _ = engine.transcribe(spanish,'es',task='translate')
checks['spanish_theatre_preserved']='teatro' in text.lower()
checks['english_theatre_preserved']='theater' in translated.lower() or 'theatre' in translated.lower()
results.append({'fixture':'synthetic_spanish','transcript':text,'translation':translated})
mean = sum(r['wer'] for r in results if 'wer' in r)/len(fixtures)
checks['mean_wer_at_most_15_percent']=mean<=.15
checks['jfk_exact']=results[0]['wer']==0
checks['faster_than_audio']=all(r['inference_seconds'] < r['audio_seconds'] for r in results if 'inference_seconds' in r)
report = {'beam_size':args.beam_size,'checks':checks, 'passed':all(checks.values()), 'model':args.model,'results':results,'mean_wer':round(mean,4),
          'gate':'mean WER <= 0.15; JFK exact after punctuation/case normalization; each fixture inference faster than audio; silence/noise empty; Spanish theatre preserved'}
(root/args.output).write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n')
assert all(checks.values()), checks
print('QUALITY GATE PASSED',flush=True)
