"""One isolated real-inference configuration; launch separately for each matrix cell.

This short probe measures capacity, not sustained operation or browser latency.
Run quality_gate.py for every candidate; no quality thresholds are changed here.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import io
import json
from pathlib import Path
import subprocess
import sys
import threading
import time

import numpy as np
import psutil
import pyarrow.parquet as pq
from faster_whisper.audio import decode_audio

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from server import Engine


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', default='small')
    parser.add_argument('--device', choices=['cpu', 'cuda'], default='cuda')
    parser.add_argument('--compute-type', default='float16')
    parser.add_argument('--beam-size', type=int, choices=range(1, 6), default=5)
    parser.add_argument('--workers', type=int, choices=range(1, 9), default=1)
    parser.add_argument('--threads', type=int, default=4)
    parser.add_argument('--streams', type=int, nargs='+', default=[1, 2, 4, 8, 12])
    parser.add_argument('--rounds', type=int, default=3)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.device == 'cuda':
        active = subprocess.check_output(['nvidia-smi', '--query-compute-apps=pid,process_name', '--format=csv,noheader'], text=True).strip()
        if active:
            parser.error('GPU has existing compute processes; stop competing workloads first: ' + active)
    rows = pq.read_table(ROOT/'samples/librispeech.parquet').to_pylist()
    audios = [decode_audio(io.BytesIO(row['audio']['bytes']))[:96000] for row in rows[:max(args.streams)]]
    spanish = decode_audio(str(ROOT/'samples/spanish.wav'))
    process = psutil.Process()
    samples = []
    finished = threading.Event()
    def monitor():
        while not finished.is_set():
            sample = {'time': time.perf_counter(), 'rss_mib': process.memory_info().rss/2**20,
                      'cpu_seconds': sum(process.cpu_times()[:2])}
            if args.device == 'cuda':
                result = subprocess.run(['nvidia-smi', '--query-gpu=memory.used,utilization.gpu,power.draw', '--format=csv,noheader,nounits'], capture_output=True, text=True)
                sample['nvidia_smi'] = result.stdout.strip()
                if result.returncode:
                    sample['monitor_error'] = result.stderr
            samples.append(sample)
            finished.wait(.25)
    thread = threading.Thread(target=monitor, daemon=True)
    report = {'configuration': vars(args).copy(), 'results': [], 'samples': samples, 'passed': False}
    report['configuration']['output'] = str(args.output)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    thread.start()
    try:
        start = time.perf_counter()
        engine = Engine(args.model, threads=args.threads, offline=True, device=args.device,
                        compute_type=args.compute_type, workers=args.workers, beam_size=args.beam_size)
        report['model_load_seconds'] = time.perf_counter()-start
        start = time.perf_counter()
        engine.warmup()
        report['warmup_seconds'] = time.perf_counter()-start
        report['actual_device'] = engine.device
        report['actual_compute_type'] = str(engine.model.model.compute_type)
        for mixed in (False, True):
            for streams in args.streams:
                for cycle in range(args.rounds):
                    start = time.perf_counter()
                    def one(index):
                        began = time.perf_counter()
                        if mixed and index % 3 == 0:
                            text, _ = engine.transcribe(spanish, 'es')
                            translation, _ = engine.transcribe(spanish, 'es', task='translate')
                            quality = 'teatro' in text.lower() and any(w in translation.lower() for w in ('theater', 'theatre'))
                        else:
                            text, _, _ = engine.window(audios[index], 'en', 0, False)
                            translation = ''
                            quality = bool(text)
                        return {'stream': index, 'queue_seconds': began-start,
                                'inference_seconds': time.perf_counter()-began,
                                'text': text, 'translation': translation, 'fixture_check': quality}
                    with ThreadPoolExecutor(max_workers=args.workers) as pool:
                        results = list(pool.map(one, range(streams)))
                    cell = {'streams': streams, 'mixed': mixed, 'round': cycle,
                            'wall_seconds': time.perf_counter()-start, 'results': results}
                    report['results'].append(cell)
                    print(json.dumps({k: v for k, v in cell.items() if k != 'results'}), flush=True)
        report['passed'] = all(r['fixture_check'] for cell in report['results'] for r in cell['results'])
    except Exception as exc:
        report['error'] = repr(exc)
        raise
    finally:
        finished.set()
        thread.join(timeout=5)
        args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False)+'\n', encoding='utf-8')
    if not report['passed']:
        raise SystemExit('Fixture checks failed; results retained.')


if __name__ == '__main__':
    main()
