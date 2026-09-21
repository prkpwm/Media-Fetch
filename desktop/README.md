# Media Fetch Desktop (Python)

Double-click `start.cmd`. Requires Python 3.10+ with Tkinter. Run `setup.cmd` once if FFmpeg is missing; it installs the `imageio-ffmpeg` wheel and its FFmpeg binary under `.vendor`, without changing global Python packages. You can also choose an existing FFmpeg executable in the app.

From Git Bash in `/d/dim`, launch with `python desktop/app.py`. For manual setup, use `python -m pip install --target "D:/dim/desktop/.vendor" imageio-ffmpeg==0.6.0`; use quoted paths with forward slashes so Bash does not strip Windows backslashes.

1. Click **Import HAR** and choose a browser network capture with playlist response bodies, or paste an HLS `.m3u8` URL and click **Inspect URL**.
2. Select a detected quality, such as 720p or 1080p. The default audio rendition from the master playlist is selected automatically.
3. Choose a new output `.mp4` filename and click **Download selected → MP4**.

FFmpeg downloads the selected video and audio tracks and muxes them with stream copy (no re-encoding). Standard AES-128 HLS is supported when its key URI is accessible to the current request. This does not support Widevine, PlayReady, SAMPLE-AES, or obtaining unavailable keys. A HAR only records captured requests; it does not guarantee the URLs are still valid. Recapture expired links while playing the video.

The app reads HAR locally, keeps signed URLs in memory, and retains only User-Agent, Referer, and Origin context headers. It never imports Cookie or Authorization headers. Servers requiring those credentials can fail. Selecting Download sends the selected URLs and playback context to their media servers. Logs displayed in errors redact URLs. No telemetry or public server is used.

Only completed HLS VOD is supported. Audio language switching, pause/resume, and a standalone packaged EXE are not included. Network reads time out after 20 seconds; cancellation during playlist inspection may take that long. Cancellation deletes this job's partial file. The destination is published only after FFmpeg completes, and existing files are never overwritten. MP4 requires compatible source codecs; incompatible sources fail instead of silently being re-encoded. Temporary and output files live on the same volume; atomic publication requires hard-link support (normal Windows NTFS works).

Tests: `python -m unittest discover -s desktop/tests -v` from the repository root.

## Link the browser extension

1. Reload Media Fetch in `chrome://extensions` or `edge://extensions`. Version 0.2 adds the native messaging permission.
2. Run `python desktop/register_host.py YOUR_EXTENSION_ID` from the repository root. The extension manager also displays this command with its actual ID filled in. This registers the host for the current Windows user in Chrome and Edge; no administrator account is needed.
3. In the extension manager, click **Check connection**, then **Open selected in desktop** on a detected HLS stream.
4. The browser opens a connected desktop window with that video quality and its matching audio track. Choose the output filename and click **Download selected → MP4**.

The browser-connected window is separate from any manually opened app. Later requests reuse that connected window; if it is busy they are rejected without replacing the current job. The browser must remain open during a connected download. Closing the manager tab is fine; closing the desktop window reconnects on the next request. Reloading the extension or closing the browser disconnects its app and can interrupt downloads. Abrupt browser termination can leave a `.partial.mp4` temporary file.

Native messaging uses browser-managed stdin/stdout pipes, with no local HTTP listener. Only the registered extension ID can invoke the host; only the extension's own manager page can request it. URLs are kept in memory and are not written to a transfer file. Cookies and Authorization are not passed. To unregister: `python desktop/register_host.py --uninstall`.

FFmpeg references: https://ffmpeg.org/ffmpeg.html and https://ffmpeg.org/ffmpeg-protocols.html. The downloaded wheel contains FFmpeg licensing information; review it before redistribution. The local binary is not committed to source control.
