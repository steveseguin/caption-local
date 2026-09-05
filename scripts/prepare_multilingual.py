"""Generate six explicitly synthetic test fixtures with an existing eSpeak NG.

Use --espeak PATH on Linux/Windows, or --wsl-espeak PREFIX for locally extracted
Ubuntu packages. No cloud TTS calls or system package installation.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import wave

import numpy as np
from faster_whisper.audio import decode_audio

FIXTURES = [
    ('en','en-us','Welcome to the theatre. The show begins at seven tonight.'),
    ('es','es','Hola. Bienvenidos al teatro. Muchas gracias por venir esta noche.'),
    ('fr','fr-fr','Bienvenue au théâtre. Merci de venir ce soir.'),
    ('de','de','Willkommen im Theater. Vielen Dank für Ihren Besuch heute Abend.'),
    ('it','it','Benvenuti al teatro. Grazie per essere qui questa sera.'),
    ('pt','pt-br','Bem-vindos ao teatro. Obrigado por vir esta noite.'),
]

if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--espeak',default=shutil.which('espeak-ng'))
    parser.add_argument('--wsl-espeak',help='Linux absolute prefix containing usr/bin/espeak-ng and usr/lib')
    args=parser.parse_args()
    root=Path(__file__).resolve().parents[1]
    folder=root/'samples/multilingual'; folder.mkdir(parents=True,exist_ok=True)
    manifest=[]
    for language,voice,text in FIXTURES:
        target=folder/f'{language}.wav'
        if not target.exists():
            source=folder/f'{language}.txt'; source.write_text(text,encoding='utf-8')
            if args.wsl_espeak and os.name=='nt':
                prefix=args.wsl_espeak.rstrip('/')
                def linux_path(path):
                    return subprocess.check_output(['wsl','-e','wslpath','-a',str(path)],text=True).strip()
                command=['wsl','-e','env',f'LD_LIBRARY_PATH={prefix}/usr/lib/x86_64-linux-gnu',
                    f'ESPEAK_DATA_PATH={prefix}/usr/lib/x86_64-linux-gnu/espeak-ng-data',
                    prefix+'/usr/bin/espeak-ng','-v',voice,'-s','145','-w',linux_path(target),'-f',linux_path(source)]
            elif args.espeak:
                command=[args.espeak,'-v',voice,'-s','145','-w',str(target),'-f',str(source)]
            else:
                parser.error('Supply --espeak or --wsl-espeak to generate missing fixtures')
            subprocess.run(command,check=True)
        audio=decode_audio(str(target))
        loop=np.concatenate([audio,np.zeros(max(16000,96000-len(audio)),dtype=np.float32)])
        loop_path=folder/f'{language}-loop.wav'
        with wave.open(str(loop_path),'wb') as output:
            output.setnchannels(1); output.setsampwidth(2); output.setframerate(16000)
            output.writeframes((loop*32767).astype('<i2').tobytes())
        noise=np.random.default_rng(42).normal(0,float(np.sqrt(np.mean(audio**2)))/3.1623,len(audio))
        varied=np.concatenate([loop,loop*.05,np.clip(audio+noise,-1,1),np.zeros(16000,dtype=np.float32)])
        varied_path=folder/f'{language}-varied.wav'
        with wave.open(str(varied_path),'wb') as output:
            output.setnchannels(1); output.setsampwidth(2); output.setframerate(16000)
            output.writeframes((varied*32767).astype('<i2').tobytes())
        manifest.append({'language':language,'voice':voice,'text':text,'speed':145,
            'path':target.relative_to(root).as_posix(),'loop_path':loop_path.relative_to(root).as_posix(),
            'varied_loop_path':varied_path.relative_to(root).as_posix(),
            'varied_conditions':'clean, -26 dB speech, 10 dB SNR seeded Gaussian noise, pauses; repeats',
            'sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'seconds':len(audio)/16000})
    (folder/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('Prepared six synthetic languages and browser loops; existing WAV files preserved.')
