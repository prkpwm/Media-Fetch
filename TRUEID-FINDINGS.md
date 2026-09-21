# TrueID HAR findings

Source: local `www.trueid.net.har`, 106 requests, inspected 2026-09-21. No captured credentials, signed URLs, or keys were replayed.

- The stream uses HLS (`application/vnd.apple.mpegurl`) and MPEG-TS segments.
- Master playlist: HAR entry 35 (zero-based). Six variants: 320×180, 426×240, 640×360, 854×480, 1280×720, 1920×1080.
- Video playlists: entries 43 and 78, representing the observed 720p and 1080p variants. They declare `METHOD=AES-128`, a key URI, and an IV. This establishes HLS encryption; it does not by itself establish Widevine or PlayReady DRM.
- Audio is separate. The master labels it Thai (`LANGUAGE="th"`, `NAME="Thai"`), even though its URL filename contains `audio_eng`.
- Both video and audio playlists contain 354 segments and an end marker. Video duration is 1,414.84 seconds (23 minutes 34.84 seconds).
- Requests include signed query parameters and session/device identifiers. These are deliberately excluded from this report and the test fixtures.

## Extension compatibility

Detection supports this HLS response type. Complete episode downloading does **not** currently work: the extension cannot decrypt AES-128 video or combine separate audio and video tracks. A copied playlist URL is not a complete downloadable video.

At the advertised highest variant bandwidth, the episode is roughly 731 MiB, also above the current 512 MiB assembly limit. This is an estimate, not a measured final file size.

The fixtures preserve relevant playlist tags and ordering while replacing all media/key URLs and IV values. Tests prove that the current implementation reports unsupported video encryption and separate audio instead of silently producing a broken episode. They do not prove successful downloading or authenticated browser playback.

## DASH capture findings (`www.trueid.net.dash.har`)

Source: local `www.trueid.net.dash.har`, 152 requests, inspected 2026-09-22.

- **Manifest**: MPEG-DASH manifest (`index.mpd`) located at `/avod/th_gn/wv/...` with query parameter `drm=wv3`.
- **Encryption Scheme**: Common Encryption (CENC, `urn:mpeg:dash:mp4protection:2011`) with `default_KID` declarations:
  - `E51B8E14-1381-599C-BBA1-1E936A754A47`
  - `F41686FA-DF20-5D6A-B11B-28DD9B5CD5CD`
- **DRM System**: Widevine Modular DRM. The browser issues license request POSTs to `https://kdcid.stm.trueid.net/vod/widevine` to obtain encrypted Content Encryption Keys (CEKs) through the browser's Content Decryption Module (CDM).
- **Decoder / Downloader Support**:
  - **Cannot be decoded or downloaded**: Unlike HLS AES-128 (where standard keys are provided directly via HTTP in-band in the playlist), Widevine CENC streams require secure hardware/browser CDM challenge-response license exchanges. Standard tools (such as FFmpeg) cannot decrypt Widevine-protected content without CDM hardware keys.
  - `import_har` explicitly detects DASH Widevine CENC captures and informs the user that DRM-protected streams cannot be decoded.
