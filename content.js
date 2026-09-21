// Content script: IDM-inspired in-page video detection & floating download widget

(function () {
  let ytData = null;
  const attachedVideos = new WeakSet();

  // 1. Inject page-probe.js into page context to read YouTube player data
  function injectProbe() {
    try {
      const script = document.createElement('script');
      script.src = chrome.runtime.getURL('page-probe.js');
      script.onload = () => script.remove();
      (document.head || document.documentElement).appendChild(script);
    } catch (e) {}
  }
  injectProbe();

  // 2. Listen for YouTube stream discovery events
  window.addEventListener('__mf_stream_data__', (event) => {
    if (!event.detail) return;
    ytData = event.detail;
    notifyBackground(ytData);
    // Refresh badges on all videos
    document.querySelectorAll('video').forEach(attachBadge);
  });

  function notifyBackground(data) {
    try {
      chrome.runtime.sendMessage({
        type: 'media_detected_from_page',
        payload: {
          title: data.title || document.title,
          url: location.href,
          formats: data.formats
        }
      });
    } catch (e) {}
  }

  function showToast(message) {
    const existing = document.querySelector('.mf-idm-toast');
    if (existing) existing.remove();

    const toast = document.createElement('div');
    toast.className = 'mf-idm-toast';
    toast.innerHTML = `<span style="color:#10b981;font-size:16px;">✓</span> <span>${message}</span>`;
    document.body.appendChild(toast);

    setTimeout(() => {
      toast.style.opacity = '0';
      toast.style.transition = 'opacity 0.3s ease';
      setTimeout(() => toast.remove(), 300);
    }, 3000);
  }

  function sendToDesktop(item, title) {
    showToast(`Sending ${item.label || item.quality || 'video'} to Desktop…`);
    chrome.runtime.sendMessage({
      type: 'download_from_content',
      payload: {
        url: item.url,
        audioUrl: item.audioUrl || '',
        title: title || document.title,
        quality: item.quality || `${item.height || 0}p`,
        height: item.height || 0,
        bandwidth: item.bitrate || 0,
        pageUrl: location.href
      }
    }, (response) => {
      if (response?.ok) {
        showToast(`Sent to Media Fetch Desktop!`);
      } else {
        showToast(response?.error || 'Failed to connect to Desktop app.');
      }
    });
  }

  // 3. Attach IDM-style floating badge to video player
  function attachBadge(video) {
    if (!video || attachedVideos.has(video)) return;
    if (video.offsetWidth < 120 || video.offsetHeight < 80) return; // ignore tiny tracking pixels

    attachedVideos.add(video);

    const parent = video.parentElement || video;
    // Ensure parent can position absolute children
    const style = window.getComputedStyle(parent);
    if (style.position === 'static') {
      parent.style.position = 'relative';
    }

    const container = document.createElement('div');
    container.className = 'mf-idm-container';

    const badge = document.createElement('div');
    badge.className = 'mf-idm-badge';
    badge.innerHTML = `<span class="mf-idm-icon">⬇</span> <span>Download Video</span>`;

    const dropdown = document.createElement('div');
    dropdown.className = 'mf-idm-dropdown';

    function openDesktopApp(targetUrl) {
      const titleText = ytData?.title || document.title || 'Detected Video';
      showToast('Opening in Media Fetch Desktop…');
      chrome.runtime.sendMessage({
        type: 'open_desktop_for_tab',
        payload: {
          url: targetUrl || '',
          title: titleText,
          pageUrl: location.href
        }
      }, (res) => {
        if (res?.ok) {
          showToast('✓ Opened in Media Fetch Desktop!');
        } else {
          showToast(res?.error || 'Could not connect to Desktop. Opening Manager…');
          openManager();
        }
      });
    }

    function openManager() {
      chrome.runtime.sendMessage({type: 'open_manager_for_tab'}, () => {});
    }

    async function populateDropdown() {
      dropdown.innerHTML = '';

      const titleText = ytData?.title || document.title || 'Detected Video';
      const header = document.createElement('div');
      header.className = 'mf-idm-header';
      header.innerHTML = `
        <div class="mf-idm-title" title="${titleText}">${titleText}</div>
        <div class="mf-idm-subtitle">Media Fetch Desktop Link</div>
      `;
      dropdown.appendChild(header);

      const items = [];

      // Query background for streams sniffed by webRequest
      try {
        const bgRes = await new Promise(resolve => {
          chrome.runtime.sendMessage({type: 'get_tab_media'}, res => resolve(res));
        });
        for (const row of bgRes?.media || []) {
          const kindLabel = row.kind === 'hls' ? 'HLS Stream (m3u8)' : (row.kind === 'dash' ? 'DASH Stream' : 'Media Stream');
          let displayHost = '';
          try { displayHost = new URL(row.url).hostname; } catch(e) {}
          items.push({
            label: kindLabel,
            meta: displayHost,
            url: row.url,
            audioUrl: '',
            height: 0,
            bitrate: 0
          });
        }
      } catch (e) {}

      // If YouTube formats available
      if (ytData && ytData.formats && ytData.formats.length > 0) {
        const bestAudio = ytData.audioFormats?.[0] || null;

        for (const f of ytData.formats) {
          if (!f.url) continue;
          items.push({
            label: f.quality || `${f.height}p`,
            meta: f.fps ? `${f.fps}fps · ${Math.round(f.bitrate / 1000)} kbps` : '',
            url: f.url,
            audioUrl: f.hasAudio ? '' : (bestAudio?.url || ''),
            height: f.height,
            bitrate: f.bitrate
          });
        }

        // Add Audio only option
        if (bestAudio?.url) {
          items.push({
            label: 'Audio Only (M4A / Opus)',
            meta: `${Math.round(bestAudio.bitrate / 1000)} kbps`,
            url: bestAudio.url,
            audioUrl: '',
            height: 0,
            bitrate: bestAudio.bitrate
          });
        }
      } else if (video.currentSrc || video.src) {
        const src = video.currentSrc || video.src;
        if (src && !src.startsWith('blob:') && !src.startsWith('mediasource:') && !items.some(i => i.url === src)) {
          const res = video.videoHeight ? `${video.videoHeight}p` : 'Original Video';
          items.push({
            label: res,
            meta: video.duration ? `${Math.round(video.duration)}s` : '',
            url: src,
            audioUrl: '',
            height: video.videoHeight || 0,
            bitrate: 0
          });
        }
      }

      if (items.length === 0) {
        const emptyCard = document.createElement('div');
        emptyCard.className = 'mf-idm-empty-card';
        emptyCard.innerHTML = `
          <div class="mf-idm-empty-msg">Media stream active. Click below to open in Desktop app or launch Manager:</div>
          <button class="mf-idm-btn-primary" type="button">
            <span>🖥 Open in Media Fetch Desktop</span>
          </button>
          <button class="mf-idm-btn-secondary" type="button">
            <span>📋 Open Media Manager</span>
          </button>
        `;
        emptyCard.querySelector('.mf-idm-btn-primary').onclick = (e) => {
          e.stopPropagation();
          dropdown.classList.remove('mf-idm-show');
          openDesktopApp();
        };
        emptyCard.querySelector('.mf-idm-btn-secondary').onclick = (e) => {
          e.stopPropagation();
          dropdown.classList.remove('mf-idm-show');
          openManager();
        };
        dropdown.appendChild(emptyCard);
        return;
      }

      items.forEach(item => {
        const row = document.createElement('div');
        row.className = 'mf-idm-item';
        row.innerHTML = `
          <span class="mf-idm-item-label">${item.label}</span>
          <span class="mf-idm-item-meta">${item.meta}</span>
        `;
        row.onclick = (e) => {
          e.stopPropagation();
          dropdown.classList.remove('mf-idm-show');
          sendToDesktop(item, titleText);
        };
        dropdown.appendChild(row);
      });

      // Also append direct desktop and manager launcher buttons
      const divider = document.createElement('div');
      divider.className = 'mf-idm-divider';
      dropdown.appendChild(divider);

      const appBtn = document.createElement('button');
      appBtn.className = 'mf-idm-btn-primary';
      appBtn.type = 'button';
      appBtn.innerHTML = `<span>🖥 Open in Media Fetch Desktop</span>`;
      appBtn.onclick = (e) => {
        e.stopPropagation();
        dropdown.classList.remove('mf-idm-show');
        openDesktopApp(items[0]?.url);
      };
      dropdown.appendChild(appBtn);

      const mgrBtn = document.createElement('button');
      mgrBtn.className = 'mf-idm-btn-secondary';
      mgrBtn.type = 'button';
      mgrBtn.innerHTML = `<span>📋 Open Media Manager</span>`;
      mgrBtn.onclick = (e) => {
        e.stopPropagation();
        dropdown.classList.remove('mf-idm-show');
        openManager();
      };
      dropdown.appendChild(mgrBtn);
    }

    badge.onclick = async (e) => {
      e.stopPropagation();
      dropdown.classList.toggle('mf-idm-show');
      if (dropdown.classList.contains('mf-idm-show')) {
        await populateDropdown();
      }
    };

    document.addEventListener('click', (e) => {
      if (!container.contains(e.target)) {
        dropdown.classList.remove('mf-idm-show');
      }
    });

    container.appendChild(badge);
    container.appendChild(dropdown);
    parent.appendChild(container);
  }

  // 4. Observe page for video elements
  function scan() {
    document.querySelectorAll('video').forEach(attachBadge);
  }

  const observer = new MutationObserver(() => scan());
  observer.observe(document.documentElement, {childList: true, subtree: true});

  window.addEventListener('play', (e) => {
    if (e.target?.tagName === 'VIDEO') attachBadge(e.target);
  }, true);

  // Initial scan
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', scan);
  } else {
    scan();
  }
})();
