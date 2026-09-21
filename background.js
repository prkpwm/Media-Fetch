import {classify} from './media.js';
import {installDesktopBridge} from './desktop-bridge.js';
installDesktopBridge();
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
