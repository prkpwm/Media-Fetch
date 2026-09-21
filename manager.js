import {classify, httpURL, parseHLS, inspectHLS, qualityLabel} from './media.js';
const $ = id => document.getElementById(id);
const tabId = Number(new URL(location.href).searchParams.get('tab'));
const key = `media:${tabId}`;
const ownKey = `downloads:${tabId}`;
let hlsSequence = 0;
const controllers = new Map();
let owned = new Set(), blobs = new Map();
const inspections = new Map();
let mediaRevision = 0;
const say = text => { $('status').textContent = text; };
async function desktopRequest(payload) {
  const result=await chrome.runtime.sendMessage({type:'desktop',payload});
  if(!result?.ok) throw new Error(result?.error || 'Desktop app did not respond.');
  return result;
}
async function openDesktop(row, selected) {
  const source=(await chrome.storage.session.get(`source:${tabId}`))[`source:${tabId}`] || {};
  await desktopRequest({action:'open',url:row.url,pageUrl:source.url || '',title:source.title || '',userAgent:navigator.userAgent,
    selection:selected ? {url:selected.url,audioUrl:selected.audioUrl || '',audioName:selected.audio || '',height:selected.height,bandwidth:selected.bandwidth} : null});
  $('desktop-status').textContent='Connected to Media Fetch Desktop';
  say('Opened in Media Fetch Desktop. Choose the output file there and click Download selected → MP4.');
  try {
    const list = (await chrome.storage.local.get('desktopTransfers'))?.desktopTransfers || [];
    list.push({
      url: row.url,
      pageUrl: source.url || '',
      title: source.title || '',
      selectedQuality: selected ? (selected.height ? `${selected.height}p` : 'selected') : 'original',
      timestamp: Date.now()
    });
    await chrome.storage.local.set({desktopTransfers: list.slice(-50)});
  } catch(e) {}
}
async function restoreDesktopStatus() {
  try {
    const data = await chrome.storage.local.get('desktopConnection');
    const conn = data?.desktopConnection;
    if (conn?.connected) $('desktop-status').textContent = conn.status || 'Connected to Media Fetch Desktop';
    else if (conn?.status) $('desktop-status').textContent = conn.status;
  } catch(e) {}
}
function element(tag, text, cls) { const el = document.createElement(tag); el.textContent = text; if(cls) el.className = cls; return el; }
function button(label, action) { const el = element('button',label); el.onclick = async () => { try { await action(); } catch(e) { say(e.message); } }; return el; }
async function track(id) { owned.add(id); await chrome.storage.session.set({[ownKey]:[...owned]}); await renderDownloads(); }
async function get(url, signal) {
  const response = await fetch(url,{signal,credentials:'include'});
  if (!response.ok) throw new Error(`Server returned HTTP ${response.status}. Replay the video to refresh expired links.`);
  return response;
}
function inspect(url) {
  if(!inspections.has(url)) {
    const pending=get(url,AbortSignal.timeout(15000)).then(async response=>inspectHLS(await response.text(),response.url));
    inspections.set(url,pending);
    pending.catch(()=>inspections.delete(url));
  }
  return inspections.get(url);
}
async function showQualities(row, item, actions) {
  const detail=element('div','Reading available qualities…','meta'); item.append(detail);
  try {
    const info=await inspect(row.url);
    if(!item.isConnected) return;
    if(!info.variants.length) {
      detail.textContent=info.encryption ? `${info.encryption} encrypted HLS — use the desktop app for supported AES-128 playback.` : 'HLS media playlist';
      if(info.encryption) {actions.firstChild.disabled=true;actions.firstChild.textContent='Browser download unsupported';}
      return;
    }
    const select=document.createElement('select'); select.setAttribute('aria-label','Download quality');
    for(const [index,variant] of info.variants.entries()) {
      const option=element('option',qualityLabel(variant));option.value=String(index);select.append(option);
    }
    select.value=String(info.variants.length-1);
    const note=element('p','','meta');
    const download=button('Download selected quality',async()=>{
      const selected=info.variants[Number(select.value)];
      await start(selected.url,'hls');
    });
    const copy=button('Copy selected URL',async()=>{
      await navigator.clipboard.writeText(info.variants[Number(select.value)].url);say('Selected quality URL copied.');
    });
    let selectionRevision=0;
    const update=async()=>{
      const revision=++selectionRevision, selected=info.variants[Number(select.value)];
      download.disabled=true;download.textContent='Checking selected quality…';
      note.textContent='Checking download compatibility…';
      try {
        const child=await inspect(selected.url);
        if(revision!==selectionRevision || !item.isConnected) return;
        const reasons=[];
        if(child.encryption || selected.encryption) reasons.push(`${child.encryption || selected.encryption} encryption`);
        if(selected.separateAudio) reasons.push('separate audio requires merging');
        if(selected.separateVideo) reasons.push('separate video requires merging');
        download.disabled=reasons.length>0;
        download.textContent=reasons.length?'Browser download unsupported':`Download ${selected.height?selected.height+'p':'selected quality'}`;
        note.textContent=reasons.length?`Detected · ${reasons.join(' · ')}. Use Open selected in desktop for AES-128 support and MP4 audio/video merging.`:'Browser download saves TS; the desktop app combines tracks into MP4.';
      } catch(e) {
        if(revision!==selectionRevision) return;
        download.textContent='Check again';download.disabled=false;
        note.textContent=`Could not inspect this quality: ${e.message}`;
        // A failed check must never bypass separate-track compatibility checks.
        download.onclick=()=>update();
        return;
      }
      download.onclick=async()=>{try{await start(selected.url,'hls');}catch(e){say(e.message);}};
    };
    select.onchange=update;
    const desktop=button('Open selected in desktop',()=>openDesktop(row,info.variants[Number(select.value)]));
    actions.replaceChildren(select,desktop,download,copy);
    detail.textContent=`${info.variants.length} quality options detected`;item.append(note);
    await update();
  } catch(e) { detail.textContent=`Could not load qualities: ${e.message}`; actions.append(button('Retry qualities',()=>{detail.remove();return showQualities(row,item,actions);})); }
}
function sanitizeFilename(name, fallback='video') {
  if (!name || typeof name !== 'string') return fallback;
  const cleaned = name.replace(/[\x00-\x1f\\/:*?"<>|]+/g, ' ').replace(/\s+/g, ' ').trim().replace(/^\.+|\.+$/g, '');
  return cleaned.slice(0, 200).trim().replace(/^\.+|\.+$/g, '') || fallback;
}
async function start(url, kind) {
  url = httpURL(url);
  if (kind === 'dash') throw new Error('DASH requires a muxer and is unsupported.');
  if (kind !== 'hls') {
    const source=(await chrome.storage.session.get(`source:${tabId}`))[`source:${tabId}`] || {};
    const baseName=sanitizeFilename(source.title, '');
    let filename;
    if (baseName) {
      const ext = url.split('?')[0].split('.').pop();
      filename = /^[a-z0-9]{2,4}$/i.test(ext) ? `${baseName}.${ext}` : `${baseName}.mp4`;
    }
    await track(await chrome.downloads.download({url, filename, saveAs:true}));
    say('Download sent to your browser.');
    return;
  }
  const hlsId = ++hlsSequence;
  const currentController = new AbortController();
  const {signal} = currentController;
  controllers.set(hlsId, currentController);
  $('cancel').hidden = false;
  $('cancel').textContent = controllers.size > 1 ? `Cancel HLS (${controllers.size})` : 'Cancel HLS';
  try {
    let playlist;
    for (let depth=0; depth<5; depth++) {
      say('Reading playlist…');
      const response = await get(url,signal);
      playlist = parseHLS(await response.text(),response.url);
      if (!playlist.variants) break;
      url = playlist.variants[0].url;
    }
    if (!playlist.segments) throw new Error('Too many nested playlists.');
    const parts=[]; let size=0;
    for (const [i,segment] of playlist.segments.entries()) {
      say(`Downloading segment ${i+1} / ${playlist.segments.length} · ${(size/1048576).toFixed(1)} MiB`);
      const response = await get(segment,signal);
      const reader = response.body.getReader(); const chunks=[];
      while(true) {
        const {done,value} = await reader.read(); if(done) break;
        size += value.byteLength;
        if(size > 512*1048576) { await reader.cancel(); throw new Error('HLS exceeds the 512 MiB memory limit.'); }
        chunks.push(value);
      }
      const part = new Blob(chunks); const first = new Uint8Array(await part.slice(0,1).arrayBuffer());
      if(first[0] !== 0x47) throw new Error('This playlist does not contain supported MPEG-TS segments.');
      parts.push(part);
    }
    const source=(await chrome.storage.session.get(`source:${tabId}`))[`source:${tabId}`] || {};
    const baseName=sanitizeFilename(source.title, `media-${Date.now()}`);
    const blobURL = URL.createObjectURL(new Blob(parts,{type:'video/mp2t'}));
    try { const id=await chrome.downloads.download({url:blobURL,filename:`${baseName}.ts`,saveAs:true}); blobs.set(id,blobURL); await track(id); }
    catch(e) { URL.revokeObjectURL(blobURL); throw e; }
    say('Video assembled. Keep this tab open until the file finishes saving.');
  } catch(e) { say(e.name === 'AbortError' ? 'HLS download cancelled.' : e.message); }
  finally {
    controllers.delete(hlsId);
    if (controllers.size === 0) {
      $('cancel').hidden = true;
      $('cancel').textContent = 'Cancel HLS';
    } else {
      $('cancel').textContent = `Cancel HLS (${controllers.size})`;
    }
  }
}
async function renderMedia() {
  const revision=++mediaRevision;
  const rows=(await chrome.storage.session.get(key))[key] || [];
  if(revision!==mediaRevision) return;
  $('count').textContent=rows.length; $('media').replaceChildren();
  if(!rows.length) $('media').append(element('p','No media detected yet. Reload the original page and press Play.','meta'));
  for(const row of rows) {
    const url=new URL(row.url), item=element('div','','row');
    item.append(element('div',`${row.kind.toUpperCase()} · ${url.pathname.split('/').pop() || 'Media'}`,'name'),element('div',url.hostname,'meta'));
    const actions=element('div','','actions');
    const download=button(row.kind==='dash'?'DASH unsupported':'Download',()=>start(row.url,row.kind)); download.disabled=row.kind==='dash';
    actions.append(download,button('Copy URL',async()=>{await navigator.clipboard.writeText(row.url);say('URL copied. It may contain an expiring access token.');})); item.append(actions); $('media').append(item);
    if(row.kind==='hls') actions.append(button('Open in desktop',()=>openDesktop(row)));
    if(row.kind==='hls') { download.disabled=true; download.textContent='Reading playlist…';
      showQualities(row,item,actions).then(()=>{if(actions.firstChild===download && download.textContent==='Reading playlist…'){download.disabled=false;download.textContent='Download';}}).catch(e=>say(e.message)); }
  }
}
async function renderDownloads() {
  const items=(await Promise.all([...owned].map(id=>chrome.downloads.search({id})))).flat();
  $('downloads').replaceChildren();
  if(!items.length) $('downloads').append(element('p','Downloads started here will appear below.','meta'));
  for(const item of items.reverse()) {
    const row=element('div','','row'); row.append(element('div',item.filename.split(/[\\/]/).pop() || 'Preparing…','name'));
    row.append(element('div',`${item.paused?'Paused':item.state} · ${(item.bytesReceived/1048576).toFixed(1)} MiB${item.error?' · '+item.error:''}`,'meta'));
    const progress=document.createElement('progress');progress.max=item.totalBytes>0?item.totalBytes:1;if(item.totalBytes>0)progress.value=item.bytesReceived;row.append(progress);
    if(item.state==='in_progress') row.append(button(item.paused?'Resume':'Pause',async()=>{await chrome.downloads[item.paused?'resume':'pause'](item.id);await renderDownloads();}),button('Cancel',()=>chrome.downloads.cancel(item.id)));
    if(item.state==='interrupted' && item.canResume) row.append(button('Resume',()=>chrome.downloads.resume(item.id)));
    if(item.state==='complete')row.append(button('Show in folder',()=>chrome.downloads.show(item.id)));
    if(item.state!=='in_progress' && blobs.has(item.id)){URL.revokeObjectURL(blobs.get(item.id));blobs.delete(item.id);}
    $('downloads').append(row);
  }
}
$('manual').onsubmit=async event=>{event.preventDefault();try{const url=$('url').value;await start(url,classify(url));}catch(e){say(e.message);}};
$('cancel').onclick=()=>{for(const c of controllers.values()) c.abort();controllers.clear();};
const setupCommand=`python desktop/register_host.py ${chrome.runtime.id}`;
$('setup-command').textContent=setupCommand;
$('copy-setup').onclick=()=>navigator.clipboard.writeText(setupCommand).then(()=>say('Setup command copied.'),error=>say(error.message));
$('check-desktop').onclick=async()=>{
  $('desktop-status').textContent='Connecting…';
  try {
    const res = await desktopRequest({action:'ping'});
    const statusText = 'Connected to Media Fetch Desktop';
    $('desktop-status').textContent = statusText;
    await chrome.storage.local.set({
      desktopConnection: {
        connected: true,
        version: res?.version || '0.2.0',
        lastConnected: Date.now(),
        status: statusText
      }
    });
  } catch(error) {
    $('desktop-status').textContent = error.message;
    await chrome.storage.local.set({
      desktopConnection: {
        connected: false,
        lastError: error.message,
        lastDisconnected: Date.now(),
        status: error.message
      }
    }).catch(()=>{});
  }
};
chrome.storage.onChanged.addListener((changes,area)=>{
  if(area==='session'&&changes[key]) renderMedia().catch(e=>say(e.message));
  if(area==='local'&&changes.desktopConnection){
    const conn=changes.desktopConnection.newValue;
    if(conn?.connected) $('desktop-status').textContent=conn.status || 'Connected to Media Fetch Desktop';
    else if(conn?.status) $('desktop-status').textContent=conn.status;
  }
});
chrome.downloads.onChanged.addListener(()=>renderDownloads().catch(e=>say(e.message)));
window.addEventListener('beforeunload',event=>{if(controllers.size || blobs.size){event.preventDefault();event.returnValue='';}});
owned=new Set((await chrome.storage.session.get(ownKey))[ownKey] || []);
await renderMedia();await renderDownloads();await restoreDesktopStatus();
setInterval(()=>renderDownloads().catch(e=>say(e.message)),1500);
