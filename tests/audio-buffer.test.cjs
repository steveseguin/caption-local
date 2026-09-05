const {test} = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const CaptureBuffer = require('../static/audio-buffer.js');
const voice = n => new Float32Array(n).fill(.1);

test('caption intervals change collection without losing retained audio', () => {
  for (const seconds of [3,6,9]) {
    const b=new CaptureBuffer(.002,seconds);
    b.append(voice(seconds*16000-160)); assert.equal(b.snapshot(),null);
    b.append(voice(160)); const first=b.snapshot();
    assert.equal(first.audio.length,seconds*16000); assert.equal(first.final,false);
    b.append(voice(16000)); b.commit(first,seconds-1);
    assert.equal(b.length,40000); assert.equal(b.context,8000);
    const final=b.snapshot(true); b.commit(final,2.5); assert.equal(b.length,0);
  }
  assert.throws(()=>new CaptureBuffer(.002,1));
});
test('idle silence retains only half a second regardless of duration', () => {
  const b = new CaptureBuffer();
  for(let i=0;i<100000;i++) b.append(new Float32Array(160));
  assert.equal(b.length, 8000); assert.equal(b.snapshot(true), null);
});
test('overlap commits preserve future audio and precisely retain context', () => {
  const b = new CaptureBuffer(); b.append(voice(96000));
  const first=b.snapshot(); assert.equal(first.final,false);
  b.append(voice(16000)); // Audio captured during inference is not discarded.
  b.commit(first,4.5);
  assert.equal(b.length,48000); assert.equal(b.context,8000);
  const last=b.snapshot(true); assert.equal(last.audio.length,48000);
  b.commit(last,3); assert.equal(b.length,0);
});
test('failed snapshot remains byte-identical while new audio arrives', () => {
  const b = new CaptureBuffer(); b.append(voice(96000)); const s=b.snapshot();
  b.append(voice(1000)); assert.equal(s.audio.length,96000);
  assert.equal(b.length,97000); assert.throws(()=>b.commit(s,NaN));
  assert.equal(b.length,97000);
});
test('long buffers are processed with the API size cap before final flush', () => {
  const b = new CaptureBuffer(); b.append(voice(25*16000));
  const s=b.snapshot(true); assert.equal(s.audio.length,12*16000); assert.equal(s.final,false);
});
test('worklet stop flushes the partial frame exactly once and stops processing', () => {
  let Processor;
  const sent=[];
  const sandbox={Float32Array, AudioWorkletProcessor: class { constructor(){this.port={postMessage:x=>sent.push(x)};} },
    registerProcessor:(_,type)=>{Processor=type;}};
  vm.runInNewContext(fs.readFileSync('static/pcm-worklet.js','utf8'),sandbox);
  const p=new Processor(); p.process([[voice(128)]]); p.port.onmessage({data:'stop'});
  assert.equal(sent[0].length,128); assert.equal(sent[1],'stopped'); assert.equal(p.process([[voice(128)]]),false);
});
