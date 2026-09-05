"""Exercise the local WAV adapter through the official OpenAI Python SDK.

No OpenAI account/key or cloud request is used. Optional CAPTION_API_KEY belongs
to this local service, not to an external provider.
"""
import argparse
import json
import os
from pathlib import Path
from urllib.parse import urlsplit
import openai

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--url',default='http://127.0.0.1:8765')
parser.add_argument('--output',type=Path,required=True)
args=parser.parse_args()
if urlsplit(args.url).hostname not in ('localhost','127.0.0.1','::1'):
    parser.error('This smoke test sends fixtures only to localhost')
root=Path(__file__).resolve().parents[1]
client=openai.OpenAI(base_url=args.url.rstrip('/')+'/v1',api_key=os.environ.get('CAPTION_API_KEY') or 'local-test-unused',max_retries=0)
model=client.models.list().data[0].id
with (root/'samples/jfk.wav').open('rb') as audio:
    english=client.audio.transcriptions.create(model=model,file=audio,language='en')
assert 'country' in english.text.lower()
with (root/'samples/spanish.wav').open('rb') as audio:
    spanish=client.audio.transcriptions.create(model='whisper-1',file=audio,language='es',response_format='text')
assert 'teatro' in spanish.lower()
with (root/'samples/spanish.wav').open('rb') as audio:
    translation=client.audio.translations.create(model='whisper-1',file=audio)
assert any(word in translation.text.lower() for word in ('theater','theatre'))
args.output.parent.mkdir(parents=True,exist_ok=True)
args.output.write_text(json.dumps({'sdk':openai.__version__,'model':model,'english':english.text,
    'spanish':spanish,'translation':translation.text,'cloud_requests':False},indent=2,ensure_ascii=False),encoding='utf-8')
print('Official SDK local transcription/translation passed')
