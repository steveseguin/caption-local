"""Summarize saved browser load and resource evidence without running inference.

The existing 2 GiB RSS and 128 MiB warm-median-growth criteria remain explicit.
Initial caption delay is not a continuous word-aligned latency measurement.
"""
import argparse
import json
from pathlib import Path
import statistics
import math


def distribution(values):
    values=sorted(value for value in values if value is not None and math.isfinite(value))
    if not values:
        return None
    def quantile(fraction):
        position=(len(values)-1)*fraction
        lower=int(position); upper=min(lower+1,len(values)-1)
        return round(values[lower]+(values[upper]-values[lower])*(position-lower),4)
    return {'count':len(values),'min':round(values[0],4),'p50':quantile(.5),
            'p95':quantile(.95),'max':round(values[-1],4)}


def summarize(run, samples):
    responses=run.get('responses',[])
    final=run.get('final',[])
    observations=run.get('observations',[])
    memory=[sample['rss_mib'] for sample in samples]
    warm=memory[5:] or memory
    middle=max(1,len(warm)//2)
    growth=statistics.median(warm[middle:] or warm)-statistics.median(warm[:middle]) if warm else None
    duration=samples[-1]['seconds']-samples[0]['seconds'] if len(samples)>1 else 0
    checks={
        'browser_capture_and_drain':run.get('passed',False),
        'requested_capture_duration':bool(observations) and observations[-1]['seconds']>=run['capture_seconds'],
        'all_responses_successful':bool(responses) and all(response['status']==200 for response in responses),
        'continuous_health':bool(samples) and all(s['ready'] and not s['failed'] and not s['queue_timeouts'] for s in samples),
        'rss_below_2048_mib':bool(memory) and max(memory)<2048,
        'warm_median_growth_below_128_mib':growth is not None and growth<128,
    }
    streams=[]
    for index,state in enumerate(final):
        stream_responses=[response for response in responses if response['stream']==index]
        streams.append({'index':index,'first_caption_seconds':state['first_caption_seconds'],
            'caption_count':len(state['transcript']),'final_buffer_seconds':state['buffered'],
            'max_buffer_seconds':max((o['states'][index]['buffered'] for o in observations),default=None),
            'inference_seconds':distribution([r['result']['inference_seconds'] for r in stream_responses if r['status']==200]),
            'queue_seconds':distribution([r['result']['queue_seconds'] for r in stream_responses if r['status']==200])})
    return {'streams':run['streams'],'capture_seconds':run['capture_seconds'],
        'wall_seconds':run.get('wall_seconds'),'varied_conditions':run.get('varied_conditions'),
        'mixed':run.get('mixed'),'rotate_modes':run.get('rotate_modes',False),'interval':run.get('interval'),
        'requests':len(responses),'http_errors':sum(r['status']!=200 for r in responses),
        'checks':checks,'passed':all(checks.values()),
        'first_caption_seconds':distribution([s['first_caption_seconds'] for s in final]),
        'max_buffer_seconds':max((s['buffered'] for o in observations for s in o['states']),default=None),
        'queue_seconds':distribution([r['result']['queue_seconds'] for r in responses if r['status']==200]),
        'inference_seconds':distribution([r['result']['inference_seconds'] for r in responses if r['status']==200]),
        'resource_samples':len(samples),'peak_rss_mib':max(memory) if memory else None,
        'warm_median_growth_mib':round(growth,2) if growth is not None else None,
        'warm_sample_policy':'Exclude first five resource samples, compare remaining halves by median',
        'mean_cpu_cores':round((samples[-1]['cpu_seconds']-samples[0]['cpu_seconds'])/duration,3) if duration else None,
        'per_stream':streams,
        'limits':'Repeated synthetic fixtures; no population-wide accuracy or continuous word-aligned caption latency claim'}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--browser',type=Path,required=True)
    parser.add_argument('--monitor',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    report=summarize(json.loads(args.browser.read_text(encoding='utf-8')),
                     json.loads(args.monitor.read_text(encoding='utf-8')))
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({key:value for key,value in report.items() if key!='per_stream'},indent=2))
    if not report['passed']:
        raise SystemExit('Load acceptance failed; see saved checks and raw evidence')
