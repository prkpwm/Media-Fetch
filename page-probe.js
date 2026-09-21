// Page context probe for YouTube and HTML5 video streaming players
(function () {
  function getYouTubeData() {
    let pr = null;
    try {
      if (typeof window.ytInitialPlayerResponse !== 'undefined' && window.ytInitialPlayerResponse) {
        pr = window.ytInitialPlayerResponse;
      }
    } catch (e) {}

    if (!pr) {
      try {
        const app = document.querySelector('ytd-app');
        if (app?.player?.getPlayerResponse) {
          pr = app.player.getPlayerResponse();
        }
      } catch (e) {}
    }

    if (!pr) {
      try {
        const player = document.getElementById('movie_player');
        if (player?.getPlayerResponse) {
          pr = player.getPlayerResponse();
        }
      } catch (e) {}
    }

    if (!pr?.streamingData) return null;

    const sd = pr.streamingData;
    const title = pr.videoDetails?.title || document.title.replace(/ - YouTube$/, '');
    const duration = Number(pr.videoDetails?.lengthSeconds || 0);

    const formats = [];
    // Combined video + audio formats
    for (const f of sd.formats || []) {
      formats.push({
        itag: f.itag,
        quality: f.qualityLabel || `${f.height || 360}p`,
        height: f.height || 0,
        fps: f.fps || 30,
        bitrate: f.bitrate || 0,
        mime: f.mimeType || '',
        url: f.url || '',
        hasAudio: true,
        type: 'combined',
        size: f.contentLength ? Number(f.contentLength) : 0
      });
    }

    // Adaptive video formats
    const audioFormats = [];
    for (const f of sd.adaptiveFormats || []) {
      const mime = f.mimeType || '';
      if (mime.startsWith('audio/')) {
        audioFormats.push({
          itag: f.itag,
          quality: f.audioQuality || 'Audio',
          bitrate: f.bitrate || 0,
          mime: f.mimeType || '',
          url: f.url || '',
          size: f.contentLength ? Number(f.contentLength) : 0
        });
      } else if (mime.startsWith('video/')) {
        formats.push({
          itag: f.itag,
          quality: f.qualityLabel || `${f.height || 720}p`,
          height: f.height || 0,
          fps: f.fps || 30,
          bitrate: f.bitrate || 0,
          mime: f.mimeType || '',
          url: f.url || '',
          hasAudio: false,
          type: 'video_only',
          size: f.contentLength ? Number(f.contentLength) : 0
        });
      }
    }

    return {
      source: 'youtube',
      title,
      duration,
      formats,
      audioFormats
    };
  }

  function emit() {
    const data = getYouTubeData();
    if (data && data.formats.length > 0) {
      window.dispatchEvent(new CustomEvent('__mf_stream_data__', {detail: data}));
    }
  }

  // Poll or hook into YouTube navigation
  window.addEventListener('__mf_probe_request__', emit);
  window.addEventListener('yt-navigate-finish', () => setTimeout(emit, 600));
  window.addEventListener('yt-page-data-updated', () => setTimeout(emit, 600));
  
  // Initial check
  setTimeout(emit, 1000);
  setTimeout(emit, 3000);
})();
