const {test} = require('node:test');
const assert = require('node:assert/strict');
const {LocalConnection} = require('../static/local-connection.js');
test('reject unsafe endpoints and prevent connection changes with retained audio', () => {
  const c = new LocalConnection();
  for (const endpoint of ['http://example.com', 'https://example.com/path', 'https://user:pass@example.com', 'https://example.com?key=x']) {
    assert.throws(() => c.configure(endpoint, 'test', 'https://caption.ninja'));
  }
  assert.throws(() => c.configure('http://localhost:8765', '', 'https://caption.ninja'));
  c.configure('http://localhost:8765', 'test', 'https://caption.ninja');
  c.busy = true;
  assert.throws(() => c.configure('http://localhost:8772', 'other', 'https://caption.ninja'));
  assert.equal(c.endpoint, 'http://localhost:8765');
});
test('token is confined to selected service; diagnostics bounded and exclude content', async () => {
  const c = new LocalConnection();
  c.configure('http://localhost:8765', 'private-test-token', 'https://caption.ninja');
  const original = global.fetch;
  global.fetch = async (url, options) => {
    assert.equal(url, 'http://localhost:8765/transcribe?language=en');
    assert.equal(options.headers.get('Authorization'), 'Bearer private-test-token');
    assert.equal(options.redirect, 'error'); assert.equal(options.credentials, 'omit');
    return new Response('{}');
  };
  try {
    await assert.rejects(c.fetch('//evil.test/health'));
    await assert.rejects(c.fetch('https://evil.test/health'));
    for (let i=0; i<110; i++) await c.fetch('/transcribe?language=en', {body:'private-audio', method:'POST'});
    assert.equal(c.metrics.length, 100);
    assert.ok(!JSON.stringify(c.metrics).includes('private'));
    assert.ok(!JSON.stringify(c.metrics).includes('language'));
  } finally { global.fetch = original; }
});
