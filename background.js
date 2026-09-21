import {classify} from './media.js';
import {installDesktopBridge, nativeRequest} from './desktop-bridge.js';
installDesktopBridge();

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message?.type === 'media_detected_from_page') {
    if (!sender.tab?.id) return;
    const tabId = sender.tab.id;
    enqueue(async () => {
      if (message.payload?.title) {
        const key = `source:${tabId}`;
        const source = (await chrome.storage.session.get(key))[key] || {};
        await chrome.storage.session.set({[key]: {...source, title: message.payload.title, url: message.payload.url || source.url || ''}});
      }
      if (Array.isArray(message.payload?.formats)) {
        const key = `media:${tabId}`;
        const rows = (await chrome.storage.session.get(key))[key] || [];
        for (const f of message.payload.formats) {
          if (f.url && !rows.some(r => r.url === f.url)) {
            rows.push({url: f.url, kind: 'file', mime: f.mime || 'video/mp4'});
          }
        }
        await chrome.storage.session.set({[key]: rows.slice(-100)});
        await chrome.action.setBadgeText({tabId, text: String(Math.min(rows.length, 100))});
      }
    });
    sendResponse?.({ok: true});
    return true;
  }

  if (message?.type === 'download_from_content') {
    const payload = message.payload;
    if (!payload?.url) {
      sendResponse({ok: false, error: 'No media URL provided.'});
      return;
    }
    const pageUrl = payload.pageUrl || sender.tab?.url || '';
    const title = payload.title || sender.tab?.title || 'Video';
    nativeRequest({
      action: 'open',
      url: payload.url,
      pageUrl,
      title,
      userAgent: navigator.userAgent,
      selection: {
        url: payload.url,
        audioUrl: payload.audioUrl || '',
        height: payload.height || 0,
        bandwidth: payload.bandwidth || 0
      }
    }).then(res => {
      sendResponse({ok: true, ...res});
      chrome.storage.local.get('desktopTransfers').then(data => {
        const list = data?.desktopTransfers || [];
        list.push({
          url: payload.url,
          pageUrl,
          title,
          selectedQuality: payload.quality || 'selected',
          timestamp: Date.now()
        });
        chrome.storage.local.set({desktopTransfers: list.slice(-50)}).catch(() => {});
      }).catch(() => {});
    }).catch(err => {
      sendResponse({ok: false, error: err.message});
    });
    return true;
  }
});
let queue = Promise.resolve();
function enqueue(work) { queue = queue.then(work).catch(console.error); }
chrome.webRequest.onHeadersReceived.addListener(details => {
  if (details.tabId < 0 || details.statusCode >= 400) return;
  const mime = details.responseHeaders?.find(h => h.name.toLowerCase() === 'content-type')?.value || '';
  const kind = classify(details.url, mime);
  if (!kind) return;
  enqueue(async () => {
    const key = `media:${details.tabId}`;
    const rows = (await chrome.storage.session.get(key))[key] || [];
    if (rows.some(row => row.url === details.url)) return;
    rows.push({url:details.url, kind, mime});
    await chrome.storage.session.set({[key]:rows.slice(-100)});
    await chrome.action.setBadgeText({tabId:details.tabId, text:String(Math.min(rows.length,100))});
  });
}, {urls:['http://*/*','https://*/*']}, ['responseHeaders']);
chrome.tabs.onUpdated.addListener((id, change, tab) => {
  if (change.status === 'loading') enqueue(async () => {
    await chrome.storage.session.remove(`media:${id}`);
    await chrome.action.setBadgeText({tabId:id,text:''});
  });
  if (change.title || tab?.title) enqueue(async () => {
    const key = `source:${id}`;
    const source = (await chrome.storage.session.get(key))[key];
    if (source) {
      const newTitle = change.title || tab?.title;
      if (newTitle && newTitle !== source.title) {
        await chrome.storage.session.set({[key]: {...source, title: newTitle}});
      }
    }
  });
});
chrome.tabs.onRemoved.addListener(id => enqueue(() => chrome.storage.session.remove(`media:${id}`)));
chrome.action.onClicked.addListener(async tab => {
  await chrome.storage.session.set({[`source:${tab.id}`]:{url:tab.url || '',title:tab.title || ''}});
  await chrome.tabs.create({url:chrome.runtime.getURL(`manager.html?tab=${tab.id}`)});
});
