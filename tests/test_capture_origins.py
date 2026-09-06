import pytest
from fastapi.testclient import TestClient
from server import create_app


class Engine:
    workers = 1
    multilingual = True
    device = 'cpu'
    compute_type = 'int8'


TOKEN = 'test-capture-origin-token-123456'
ORIGIN = 'https://caption.ninja'


@pytest.mark.parametrize('origin', ['*', 'null', 'https://*.caption.ninja',
    'https://caption.ninja/path', 'http://example.com', 'https://user:pass@caption.ninja',
    'https://caption.ninja?key=x', 'https://caption.ninja\n', 'https://caption.ninja:bad'])
def test_reject_invalid_origins(origin):
    with pytest.raises(ValueError):
        create_app(Engine(), api_key=TOKEN, allowed_origins=[origin])


def test_cross_origin_requires_token_and_preserves_host_and_mutation_guards():
    with pytest.raises(ValueError):
        create_app(Engine(), allowed_origins=[ORIGIN])
    client = TestClient(create_app(Engine(), api_key=TOKEN, allowed_origins=[ORIGIN]), base_url='http://localhost')
    headers = {'Origin': ORIGIN, 'Access-Control-Request-Method': 'POST',
               'Access-Control-Request-Headers': 'authorization,x-caption-local,x-stream-id,x-request-id,content-type'}
    preflight = client.options('/transcribe', headers=headers)
    assert preflight.status_code == 200
    assert preflight.headers['access-control-allow-origin'] == ORIGIN
    assert client.options('/transcribe', headers={**headers, 'Host': 'evil.test'}).status_code == 400
    for token in ('', 'wrong'):
        result = client.get('/health', headers={'Origin': ORIGIN, 'Authorization': 'Bearer '+token})
        assert result.status_code == 401
        assert result.headers['access-control-allow-origin'] == ORIGIN
    auth = {'Origin': ORIGIN, 'Authorization': 'Bearer '+TOKEN}
    assert client.get('/health', headers=auth).status_code == 200
    assert client.delete('/streams/test', headers=auth).status_code == 403
    assert client.delete('/streams/test', headers={**auth, 'X-Caption-Local': '1'}).status_code == 200
    foreign = {**auth, 'Origin': 'https://evil.test', 'X-Caption-Local': '1'}
    assert client.delete('/streams/test', headers=foreign).status_code == 403
    denied = client.options('/transcribe', headers={**headers, 'Origin': 'https://evil.test'})
    assert denied.status_code == 400
    assert 'access-control-allow-origin' not in denied.headers
    assert client.get('/capture-local.html').status_code == 200


def test_default_does_not_allow_hosted_capture():
    client = TestClient(create_app(Engine()), base_url='http://localhost')
    result = client.options('/transcribe', headers={'Origin': ORIGIN, 'Access-Control-Request-Method': 'POST'})
    assert result.status_code == 400
    assert 'access-control-allow-origin' not in result.headers
