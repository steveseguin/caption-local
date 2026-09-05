"""Container readiness without exposing the optional access token in arguments."""
import json
import os
import urllib.request

if __name__ == '__main__':
    headers = {}
    if os.environ.get('CAPTION_API_KEY'):
        headers['Authorization'] = 'Bearer '+os.environ['CAPTION_API_KEY']
    request = urllib.request.Request('http://127.0.0.1:8765/health', headers=headers)
    with urllib.request.urlopen(request, timeout=3) as response:
        if not json.load(response)['ready']:
            raise SystemExit(1)
