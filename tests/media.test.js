import {test} from 'node:test';
import assert from 'node:assert/strict';
import {classify,parseHLS,httpURL,inspectHLS,qualityLabel} from '../media.js';
const base='https://cdn.example/video/master.m3u8?token=secret';
test('quality discovery retains signed URL and parses quoted codec commas',()=>{
  const {variants}=inspectHLS('#EXTM3U\n#EXT-X-STREAM-INF:BANDWIDTH=800000,CODECS="avc1.4D401E,mp4a.40.2",RESOLUTION=640x360\n360.m3u8?sig=abc',base);
  assert.equal(variants[0].url,'https://cdn.example/video/360.m3u8?sig=abc');
  assert.equal(variants[0].separateAudio,false);
  assert.equal(qualityLabel(variants[0]),'360p · 800 kbps');
  assert.throws(()=>inspectHLS('#EXTM3U\n#EXT-X-STREAM-INF:BANDWIDTH=1',base),/Malformed/);
});
test('recognizes extensionless responses and ignores segments',()=>{
  assert.equal(classify('https://cdn.example/play?id=1','application/vnd.apple.mpegurl'),'hls');
  assert.equal(classify('https://cdn.example/video.MP4?token=x'),'file');
  assert.equal(classify('https://cdn.example/seg.ts','video/mp2t'),null);
  assert.equal(classify('https://cdn.example/video=800000.dash','video/mp4'),null);
  assert.equal(classify('https://cdn.example/audio_eng=93377.dash','audio/mp4'),null);
  assert.equal(classify('blob:https://example.com/id','video/mp4'),null);
  assert.equal(classify('https://cdn.example/manifest','application/dash+xml'),'dash');
});
test('resolves signed variant URLs and chooses highest bandwidth',()=>{
  const parsed=parseHLS('#EXTM3U\n#EXT-X-STREAM-INF:BANDWIDTH=100\nlow/index.m3u8?t=one\n#EXT-X-STREAM-INF:BANDWIDTH=200\n/high.m3u8?t=two',base);
  assert.equal(parsed.variants[0].url,'https://cdn.example/high.m3u8?t=two');
  assert.equal(parsed.variants[1].url,'https://cdn.example/video/low/index.m3u8?t=one');
});
test('preserves segment order and resolves relative paths',()=>{
  assert.deepEqual(parseHLS('#EXTM3U\n#EXTINF:2,\na.ts\n#EXTINF:2,\n../b.ts?sig=x\n#EXT-X-ENDLIST',base).segments,['https://cdn.example/video/a.ts','https://cdn.example/b.ts?sig=x']);
});
test('rejects encrypted, live, unmuxed and malformed media',()=>{
  for(const tag of ['#EXT-X-KEY:METHOD=AES-128,URI="key"','#EXT-X-SESSION-KEY:METHOD=SAMPLE-AES,URI="key"','#EXT-X-MAP:URI="init.mp4"','#EXT-X-BYTERANGE:123@0','#EXT-X-DISCONTINUITY']) assert.throws(()=>parseHLS(`#EXTM3U\n${tag}\na.ts\n#EXT-X-ENDLIST`,base));
  assert.throws(()=>parseHLS('#EXTM3U\na.ts',base),/Live/);
  assert.throws(()=>parseHLS('#EXTM3U\n#EXT-X-STREAM-INF:BANDWIDTH=100,AUDIO="en"\na.m3u8',base),/Separate/);
  assert.throws(()=>parseHLS('<html>Sign in</html>',base),/playlist/);
  assert.throws(()=>parseHLS('#EXTM3U\n#EXT-X-STREAM-INF:BANDWIDTH=100',base),/Malformed/);
  assert.throws(()=>httpURL('javascript:alert(1)'),/Unsupported/);
});
