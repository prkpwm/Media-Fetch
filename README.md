# Media Fetch

The Python desktop version is in [desktop/README.md](desktop/README.md). It adds FFmpeg-based MP4 merging, separate audio tracks, and standard AES-128 HLS support with accessible playback keys. Start it with `desktop/start.cmd`.

Version 0.2 links the extension to the desktop app through native messaging. Reload the extension, run the setup command displayed under **Desktop connection** once, then choose **Open selected in desktop**. See the desktop README for registration and connection details.

A small, dependency-free Chrome / Edge Manifest V3 extension inspired by IDM's media detection and download controls.

## Install and use

1. Open `chrome://extensions` (or `edge://extensions`).
2. Turn on **Developer mode**, choose **Load unpacked**, and select `D:\dim`.
3. Open the target page, reload it after installing, sign in if required, and play the video.
4. Click the **Media Fetch** extension icon. Detected files and playlists appear in its manager tab.
5. Choose **Download**. Keep the manager tab open while HLS is assembling or saving.

Test page: https://www.trueid.net/watch/th-th/embed/A68glPP9vPAZ

## Supported behavior

- Detects media responses for each tab, including requests from embedded frames and CDNs.
- Direct files use the browser download engine, with progress, pause, resume when the server permits, cancel, and show in folder.
- Unencrypted MPEG-TS HLS VOD: selects the highest-bandwidth variant, fetches segments in order, and saves a `.ts` file. HLS fetching has progress and cancel, but no pause/resume.
- Paste a direct file or `.m3u8` URL manually.
- Detected HLS master playlists expand into a quality selector showing resolution, bitrate, and audio language. Download or copy the selected quality URL. Encrypted or separate-track options remain visible with an explanation and disabled video-download button.
- Captured URLs are session-only, limited to 100 per tab and cleared on navigation or closing the source tab. No telemetry or external service.

## Limits

This is a starter extension, not IDM's native multi-connection accelerator. It does not bypass authentication or DRM. DASH, encrypted HLS, live streams, separate audio/video tracks, fragmented MP4, byte-range playlists, and discontinuities are detected/rejected rather than silently producing incomplete files. HLS assembly uses memory and is capped at 512 MiB. TS output is not converted to MP4. Links may expire; replay the video to capture new ones. Cross-origin cookie restrictions, required request headers, or site policies can prevent downloads even if playback works. Cookies/authorization headers are not extracted or rewritten. Closing the manager cancels an HLS job; browser-managed direct downloads continue.

The extension requests HTTP/HTTPS host access to detect and fetch CDN media, `webRequest` to observe response metadata, `storage` for session state, `downloads` for file management, and `activeTab` for the clicked source tab. These are broad site permissions; install only if comfortable with this local source code.

## Validation

Run `npm test` (Node 22 or newer). Tests cover classification, signed URL resolution, variant selection, segment ordering, unsupported playlist rejection, and per-tab detection/deduplication/reset with mocked Chrome APIs.

On 2026-09-21 the TrueID test page loaded the episode poster and required TrueID sign-in before playback. An authenticated episode download has **not** been verified. Tests do not substitute for loading the extension in Chrome/Edge; browser installation and real downloads remain manual validation steps.

The subsequently supplied HAR confirms AES-128 encrypted video with separate Thai audio. This episode is unsupported by the current downloader. See [TRUEID-FINDINGS.md](TRUEID-FINDINGS.md) for the captured format details and sanitized regression fixtures.

API references: [webRequest](https://developer.chrome.com/docs/extensions/reference/api/webRequest), [downloads](https://developer.chrome.com/docs/extensions/reference/api/downloads).
