import {test} from 'node:test';
import assert from 'node:assert/strict';
test('captures, deduplicates and clears media per tab',async()=>{
  const data={}, listeners={}; let badge;
  const event=name=>({addListener:fn=>{listeners[name]=fn;}});
  globalThis.chrome={webRequest:{onHeadersReceived:event('headers')},storage:{session:{get:async key=>({[key]:data[key]}),set:async value=>Object.assign(data,value),remove:async key=>{delete data[key];}}},tabs:{onUpdated:event('updated'),onRemoved:event('removed'),create:()=>{}},action:{onClicked:event('click'),setBadgeText:async value=>{badge=value;}},runtime:{getURL:x=>x}};
  chrome.runtime.onMessage=event('message');
  await import('../background.js');
  const details={tabId:7,statusCode:200,url:'https://cdn.example/video.mp4',responseHeaders:[]};
  listeners.headers(details);listeners.headers(details);
  listeners.headers({...details,tabId:8,url:'https://cdn.example/master.m3u8'});
  listeners.headers({...details,tabId:9,statusCode:403});
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal(data['media:7'].length,1);assert.equal(data['media:8'][0].kind,'hls');assert.equal(data['media:9'],undefined);
  listeners.updated(7,{status:'loading'});
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal(data['media:7'],undefined);assert.equal(data['media:8'].length,1);assert.deepEqual(badge,{tabId:7,text:''});
  data['source:7'] = {url:'https://example.com',title:'Original Title'};
  listeners.updated(7,{title:'Episode Title from HTML Head'});
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal(data['source:7'].title,'Episode Title from HTML Head');

  // Test media_detected_from_page from in-page content script
  listeners.message({
    type: 'media_detected_from_page',
    payload: {
      title: 'YouTube Stream Title',
      url: 'https://youtube.com/watch?v=xyz',
      formats: [{url: 'https://googlevideo.com/videoplayback?itag=18', mime: 'video/mp4'}]
    }
  }, {tab: {id: 10}}, () => {});
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(data['source:10'].title, 'YouTube Stream Title');
  assert.equal(data['media:10'].length, 1);
  assert.equal(data['media:10'][0].url, 'https://googlevideo.com/videoplayback?itag=18');

  delete globalThis.chrome;
});
