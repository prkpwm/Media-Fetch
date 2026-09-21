import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {parseHLS,inspectHLS,qualityLabel} from '../media.js';
const fixture=name=>readFileSync(new URL(`./fixtures/trueid-${name}.m3u8`,import.meta.url),'utf8');
test('discovery exposes all six screenshot quality choices without rejecting separate audio',()=>{
  const {variants}=inspectHLS(fixture('master'),'https://fixture.invalid/master.m3u8');
  assert.deepEqual(variants.map(x=>x.height),[180,240,360,480,720,1080]);
  assert.deepEqual(variants.map(x=>x.bandwidth),[230000,501000,942000,1366000,2426000,4334000]);
  assert.ok(variants.every(x=>x.audio==='Thai' && x.separateAudio));
  assert.ok(variants.every(x=>x.audioUrl==='https://fixture.invalid/redacted'));
  assert.equal(qualityLabel(variants[5]),'1080p HD · 4334 kbps · Thai audio');
});
test('discovery labels encrypted video without treating it as downloadable',()=>{
  assert.equal(inspectHLS(fixture('video'),'https://fixture.invalid/video.m3u8').encryption,'AES-128');
});
test('captured TrueID master explicitly rejects separate audio',()=>{
  assert.throws(()=>parseHLS(fixture('master'),'https://fixture.invalid/master.m3u8'),/Separate audio/);
});
test('captured TrueID video explicitly rejects AES-128',()=>{
  assert.throws(()=>parseHLS(fixture('video'),'https://fixture.invalid/video.m3u8'),/Encrypted HLS/);
});
test('captured TrueID unencrypted audio contains 354 ordered segments',()=>{
  const {segments}=parseHLS(fixture('audio'),'https://fixture.invalid/audio.m3u8');
  assert.equal(segments.length,354);
  assert.equal(segments[0],'https://fixture.invalid/1.ts');
  assert.equal(segments[353],'https://fixture.invalid/354.ts');
});
