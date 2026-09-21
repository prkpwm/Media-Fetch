import {test} from 'node:test';
import assert from 'node:assert/strict';
import {installDesktopBridge, nativeRequest} from '../desktop-bridge.js';
test('native bridge checks sender, receives replies, and reports disconnection', async()=>{
  let listener, nativeMessage, disconnected, sent;
  const storageData = {};
  const port={onMessage:{addListener:fn=>{nativeMessage=fn;}},onDisconnect:{addListener:fn=>{disconnected=fn;}},postMessage:value=>{sent=value;}};
  globalThis.chrome={
    runtime:{id:'test-id',getURL:path=>`chrome-extension://test-id/${path}`,onMessage:{addListener:fn=>{listener=fn;}},connectNative:name=>{assert.equal(name,'com.mediafetch.desktop');return port;}},
    storage:{local:{get:async k=>({[k]:storageData[k]}),set:async v=>{Object.assign(storageData,v);}}}
  };
  installDesktopBridge();
  let denied;
  listener({type:'desktop',payload:{action:'open'}},{id:'test-id',url:'https://untrusted.invalid'},response=>{denied=response;});
  assert.equal(denied.ok,false);
  const responsePromise=new Promise(resolve=>listener({type:'desktop',payload:{action:'ping'}},{id:'test-id',url:'chrome-extension://test-id/manager.html?tab=2'},resolve));
  assert.equal(sent.action,'ping');nativeMessage({id:sent.id,ok:true,version:'0.2.0'});
  assert.equal((await responsePromise).ok,true);
  assert.equal(storageData.desktopConnection?.connected,true);
  assert.equal(storageData.desktopConnection?.version,'0.2.0');
  const failed=nativeRequest({action:'ping'});
  disconnected();
  await assert.rejects(failed,/disconnected/);
  assert.equal(storageData.desktopConnection?.connected,false);
  const reopened=nativeRequest({action:'ping'});
  nativeMessage({id:sent.id,ok:true});
  assert.equal((await reopened).ok,true);
  assert.equal(storageData.desktopConnection?.connected,true);
  delete globalThis.chrome;
});
