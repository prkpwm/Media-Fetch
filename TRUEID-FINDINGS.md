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
