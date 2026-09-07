const {test} = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
function setup(privateRelay) {
  const sockets = [];
  class Socket {
    static OPEN = 1; static CLOSED = 3;
    constructor(url) { this.url = url; this.readyState = 0; this.sent = []; sockets.push(this); }
    send(value) { this.sent.push(JSON.parse(value)); }
    close() { this.readyState = 3; }
    open() { this.readyState = 1; this.onopen(); }
  }
  const states = [];
  const window = {CaptionRelay: {custom: () => privateRelay, url: () => 'ws://localhost:8787/',
    join: room => ({join: room, role: 'write', token: 'synthetic'})}};
  vm.runInNewContext(fs.readFileSync('static/ws-publisher.js', 'utf8'),
    {window, WebSocket: Socket, setTimeout, clearTimeout, setInterval, clearInterval, Date});
  const publisher = window.createWSPublisher({room: 'source', maxQueue: 2, onStateChange: state => states.push(state)});
  return {sockets, publisher, states};
}
test('private publisher waits for authorization, bounds its queue and preserves order', () => {
  const {sockets, publisher, states} = setup(true);
  try {
    publisher.connect(); const socket = sockets[0]; socket.open();
    publisher.publish({id: 1}); publisher.publish({id: 2}); publisher.publish({id: 3});
    assert.equal(socket.sent.length, 1); assert.equal(socket.sent[0].join, 'source');
    assert.equal(publisher.getSnapshot().droppedCount, 1); assert.equal(publisher.isOpen(), false);
    socket.onmessage({data: JSON.stringify({joined: 'other', role: 'write'})});
    assert.equal(socket.sent.length, 1);
    socket.onmessage({data: JSON.stringify({joined: 'source', role: 'write'})});
    assert.deepEqual(socket.sent.slice(1).map(x => x.id), [2, 3]);
    assert.equal(publisher.isOpen(), true); assert.equal(states.at(-1), 'connected');
  } finally { publisher.disconnect(); }
});
test('private denial stops retries with queued captions retained', () => {
  const {sockets, publisher, states} = setup(true);
  try {
    publisher.connect(); sockets[0].open(); publisher.publish({id: 1});
    sockets[0].readyState = 3; sockets[0].onclose({code: 1008});
    assert.equal(states.at(-1), 'denied'); assert.equal(publisher.getSnapshot().reconnectAt, 0);
    assert.equal(publisher.getSnapshot().queueLength, 1); assert.equal(sockets.length, 1);
  } finally { publisher.disconnect(); }
});
test('public publisher still sends legacy join and captions without requiring an acknowledgement', () => {
  const {sockets, publisher} = setup(false);
  try {
    publisher.connect(); sockets[0].open(); publisher.publish({msg: true, final: 'hello', id: 1});
    assert.deepEqual(sockets[0].sent, [{join: 'source'}, {msg: true, final: 'hello', id: 1}]);
    assert.equal(publisher.isOpen(), true);
  } finally { publisher.disconnect(); }
});
test('private publisher bounds writes to a congested socket and resumes in order', () => {
  const {sockets, publisher} = setup(true);
  try {
    publisher.connect(); const socket = sockets[0]; socket.open();
    socket.onmessage({data: JSON.stringify({joined: 'source', role: 'write'})});
    socket.bufferedAmount = 65536;
    publisher.publish({id: 1}); publisher.publish({id: 2}); publisher.flush();
    assert.equal(socket.sent.length, 1); assert.equal(publisher.getSnapshot().queueLength, 2);
    socket.bufferedAmount = 0; publisher.flush();
    assert.deepEqual(socket.sent.slice(1).map(item => item.id), [1, 2]);
  } finally { publisher.disconnect(); }
});
