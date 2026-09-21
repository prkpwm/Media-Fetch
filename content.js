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

    function populateDropdown() {
      dropdown.innerHTML = '';

      const titleText = ytData?.title || document.title || 'Detected Video';
      const header = document.createElement('div');
      header.className = 'mf-idm-header';
      header.innerHTML = `
        <div class="mf-idm-title" title="${titleText}">${titleText}</div>
        <div class="mf-idm-subtitle">Select format for Media Fetch Desktop</div>
      `;
      dropdown.appendChild(header);

      const items = [];

      // If YouTube formats available
      if (ytData && ytData.formats && ytData.formats.length > 0) {
        const bestAudio = ytData.audioFormats?.[0] || null;

        for (const f of ytData.formats) {
          if (!f.url) continue; // skip unplayable / ciphered items if any
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
        if (src && !src.startsWith('blob:') && !src.startsWith('mediasource:')) {
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
        const empty = document.createElement('div');
        empty.style.padding = '8px';
        empty.style.color = '#94a3b8';
        empty.style.fontSize = '11px';
        empty.textContent = 'Media stream detected. Open Media Fetch Manager to download or capture.';
        dropdown.appendChild(empty);
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
    }

    badge.onclick = (e) => {
      e.stopPropagation();
      populateDropdown();
      dropdown.classList.toggle('mf-idm-show');
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
