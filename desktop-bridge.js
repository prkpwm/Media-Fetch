const HOST = 'com.mediafetch.desktop';
let port;
let sequence = 0;
const pending = new Map();

export function nativeRequest(payload) {
  return new Promise((resolve, reject) => {
    try {
      if (!port) {
        port = chrome.runtime.connectNative(HOST);
        port.onMessage.addListener(message => {
          const request = pending.get(message.id);
          if (!request) return;
          pending.delete(message.id); clearTimeout(request.timer);
          if (message.ok) {
            chrome.storage?.local?.set({
              desktopConnection: {
                connected: true,
                version: message.version || '0.2.0',
                lastConnected: Date.now(),
                status: 'Connected to Media Fetch Desktop'
              }
            }).catch?.(() => {});
            request.resolve(message);
          } else {
            request.reject(new Error(message.error || 'The desktop app rejected this request.'));
          }
        });
        port.onDisconnect.addListener(() => {
          const reason = chrome.runtime.lastError?.message || 'Desktop app disconnected.';
          port = undefined;
          chrome.storage?.local?.set({
            desktopConnection: {
              connected: false,
              lastError: reason,
              lastDisconnected: Date.now(),
              status: reason
            }
          }).catch?.(() => {});
          for (const request of pending.values()) {
            clearTimeout(request.timer);
            request.reject(new Error(`${reason} Use the Desktop connection setup shown above, then retry.`));
          }
          pending.clear();
        });
      }
      const id = ++sequence;
      const timer = setTimeout(() => {
        pending.delete(id);
        reject(new Error('The desktop app did not respond within 20 seconds.'));
      }, 20000);
      pending.set(id, {resolve, reject, timer});
      try { port.postMessage({...payload, id}); }
      catch (error) { clearTimeout(timer); pending.delete(id); throw error; }
    } catch (error) { reject(error); }
  });
}

export function installDesktopBridge() {
  chrome.runtime.onMessage.addListener((message, sender, reply) => {
    if (message?.type !== 'desktop') return;
    // Only our manager page may invoke the host; webpage/content-script messages are rejected.
    if (sender.id !== chrome.runtime.id || sender.url?.split('?')[0] !== chrome.runtime.getURL('manager.html')) {
      reply({ok:false, error:'Untrusted desktop request.'}); return;
    }
    if (!['ping', 'open'].includes(message.payload?.action)) {
      reply({ok:false, error:'Unknown desktop action.'}); return;
    }
    nativeRequest(message.payload).then(reply, error => reply({ok:false, error:error.message}));
    return true;
  });
}
