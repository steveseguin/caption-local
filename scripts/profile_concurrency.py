"""CPU model/thread sweep with real concurrent rolling-window decodes."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import sys
import time
import resource
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from server import Engine
from faster_whisper import WhisperModel
from faster_whisper.audio import decode_audio

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--extended',action='store_true',help='Compare 4/6/8 workers using base')
args=parser.parse_args()
root=Path(__file__).resolve().parents[1]
audio=decode_audio(str(root/'samples/jfk.wav'))[:96000]
results=[]
for model,beam in ([('base',5)] if args.extended else [('small',5),('base',5),('base',1),('tiny',1)]):
 for workers,threads in ([(4,1),(6,1),(8,1)] if args.extended else [(1,4),(2,2),(4,1)]):
  e=Engine.__new__(Engine)
  e.model=WhisperModel(model,device='cpu',compute_type='int8',cpu_threads=threads,num_workers=workers)
  e.beam_size=beam
  e.warmup()
  start=time.perf_counter(); cpu=resource.getrusage(resource.RUSAGE_SELF)
  def one(_):
   before=time.perf_counter()
   segments,_=e.model.transcribe(audio,language='en',beam_size=beam,temperature=0,vad_filter=True,
    word_timestamps=True,condition_on_previous_text=False,hallucination_silence_threshold=1.0,
    vad_parameters={'min_silence_duration_ms':500})
   text=''.join(s.text for s in segments)
   return time.perf_counter()-before,text
  with ThreadPoolExecutor(max_workers=workers) as pool: out=list(pool.map(one,range(12)))
  elapsed=time.perf_counter()-start; after=resource.getrusage(resource.RUSAGE_SELF)
  r={'model':model,'beam':beam,'workers':workers,'threads_per_worker':threads,
     'wall_seconds':round(elapsed,3),'audio_seconds':72,'aggregate_speedup':round(72/elapsed,2),
     'cpu_seconds':round(after.ru_utime+after.ru_stime-cpu.ru_utime-cpu.ru_stime,2),
     'mean_inference_seconds':round(sum(t for t,_ in out)/12,3),'sample_text':out[0][1]}
  results.append(r); print(json.dumps(r),flush=True)
  (root/('evidence/multistream/cpu-extended.json' if args.extended else 'evidence/multistream/cpu-sweep.json')).write_text(json.dumps(results,indent=2)+'\n')
