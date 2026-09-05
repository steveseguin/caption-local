from types import SimpleNamespace
import pytest
import ctranslate2
import faster_whisper
from server import Engine


def test_cpu_default_and_explicit_cuda(monkeypatch):
    seen = []
    def model(name, **kwargs):
        seen.append(kwargs)
        return SimpleNamespace(model=SimpleNamespace(is_multilingual=True))
    monkeypatch.setattr(faster_whisper, 'WhisperModel', model)
    assert Engine('base').device == 'cpu'
    assert Engine('base', device='cuda').device == 'cuda'
    assert [(c['device'], c['compute_type']) for c in seen] == [('cpu', 'int8'), ('cuda', 'float16')]


def test_auto_fallback_and_explicit_cuda_failure(monkeypatch):
    monkeypatch.setattr(ctranslate2, 'get_cuda_device_count', lambda: 1)
    def model(name, **kwargs):
        if kwargs['device'] == 'cuda':
            raise RuntimeError('CUDA missing')
        return SimpleNamespace(model=SimpleNamespace(is_multilingual=True))
    monkeypatch.setattr(faster_whisper, 'WhisperModel', model)
    engine = Engine('base', device='auto')
    assert (engine.device, engine.compute_type) == ('cpu', 'int8')
    with pytest.raises(RuntimeError, match='CUDA missing'):
        Engine('base', device='cuda')
    with pytest.raises(RuntimeError, match='CUDA missing'):
        Engine('base', device='auto', compute_type='float16')


def test_auto_without_gpu(monkeypatch):
    monkeypatch.setattr(ctranslate2, 'get_cuda_device_count', lambda: 0)
    monkeypatch.setattr(faster_whisper, 'WhisperModel', lambda *a, **k: SimpleNamespace(model=SimpleNamespace(is_multilingual=False)))
    engine = Engine('base.en', device='auto')
    assert not engine.multilingual and engine.device == 'cpu'

def test_window_excludes_zero_duration_context_duplicate_but_keeps_repetition():
    word = lambda text,start,end: SimpleNamespace(word=text,start=start,end=end)
    class Model:
        def transcribe(self,*args,**kwargs):
            words=[word(' ask',0,.45),word(' not',.52,.52),word(' what',.8,1.2),
                   word(' very',1.2,1.5),word(' very',1.5,1.8),word(' good',1.8,2.3)]
            return [SimpleNamespace(words=words)],SimpleNamespace(language='en')
    engine=Engine.__new__(Engine); engine.model=Model()
    import numpy as np
    text,_,_=engine.window(np.zeros(48000,np.float32),'en',.5,True)
    assert text=='what very very good'
