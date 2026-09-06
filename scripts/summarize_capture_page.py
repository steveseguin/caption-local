"""Summarize short browser integration runs without reclassifying acceptance."""
import argparse
import json
import math
from pathlib import Path
import statistics


def distribution(values):
    values = sorted(values)
    return {'median': round(statistics.median(values), 3),
            'p95': round(values[max(0, math.ceil(.95*len(values))-1)], 3),
            'max': round(values[-1], 3)} if values else None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('reports', type=Path, nargs='+')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    results = []
    for path in args.reports:
        report = json.loads(path.read_text(encoding='utf-8'))
        responses = report.get('responses', [])
        successful = [response['result'] for response in responses if response['status'] == 200]
        results.append({'file': path.name, 'passed': report['passed'], 'streams': report['streams'],
            'capture_seconds': report['capture_seconds'], 'mixed': report['mixed'],
            'requests': len(responses), 'http_errors': sum(response['status'] != 200 for response in responses),
            'first_caption_seconds': distribution([state['first_caption_seconds'] for state in report.get('final', [])
                                                    if state.get('first_caption_seconds') is not None]),
            'inference_seconds': distribution([r['inference_seconds'] for r in successful]),
            'queue_seconds': distribution([r.get('queue_seconds', 0) for r in successful]),
            'maximum_buffer_seconds': max((state['buffered'] for sample in report['observations'] for state in sample['states']), default=None),
            'maximum_final_buffer_seconds': max((state['buffered'] for state in report.get('final', [])), default=None)})
    args.output.write_text(json.dumps(results, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(results, indent=2))


if __name__ == '__main__':
    main()
