const {test} = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
function load(search = '', hash = '') {
  const location = {search, hash, href: 'http://localhost:8080/editor.html' + search + hash, pathname: '/editor.html'};
  const history = {replaceState(_, __, value) { history.value = value; }};
  const window = {location, history, addEventListener() {}, prompt() { throw new Error('Unexpected prompt'); }};
  const context = {window, URL, URLSearchParams};
  vm.runInNewContext(fs.readFileSync('static/relay-config.js', 'utf8'), context);
  return {relay: window.CaptionRelay, history};
}
test('public join protocol is unchanged; private relay never falls back on invalid configuration', () => {
  assert.equal(JSON.stringify(load().relay.join('source', 'write')), '{"join":"source"}');
  for (const search of ['?relay=', '?relay=invalid', '?relay=ws://remote.example', '?relay=wss://user:secret@example.com']) {
    const {relay} = load(search); assert.equal(relay.custom(), true); assert.equal(relay.url(), '');
  }
});
test('fragment credentials are removed and never propagated into viewer links', () => {
  const token = 'x'.repeat(43), {relay, history} = load('?relay=ws://localhost:8787', '#relayReadToken=' + token);
  assert.ok(!history.value.includes(token));
  assert.equal(relay.join('source', 'read').token, token);
  const link = new URL(relay.link('http://localhost:8080/overlay.html?room=output#relayWriteToken=secret'));
  assert.equal(link.searchParams.get('relay'), 'ws://localhost:8787/'); assert.equal(link.hash, '');
  assert.throws(() => relay.join('source', 'write', ''), /token is required/);
});
