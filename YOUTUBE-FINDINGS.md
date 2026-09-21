# YouTube HAR & UMP Protocol Findings

Source: local `www.youtube.com.har`, 10 requests, inspected 2026-09-22.

## 1. Protocol Architecture: SABR & UMP

Unlike standard video streaming protocols (HLS with `.m3u8` or MPEG-DASH with `.mpd`), YouTube's modern desktop HTML5 player uses Google's proprietary **SABR (Server-side Adaptive BitRate)** delivery protocol over **UMP (Universal Media Protocol)**:

- **Endpoint**: `https://*.googlevideo.com/videoplayback?...`
- **MIME Content-Type**: `application/vnd.yt-ump`
- **Transport**: HTTP `POST` requests sending binary Protocol Buffer request descriptors (`rn=945` through `rn=950`) and receiving chunked UMP stream responses.
- **Multiplexing**: Both video and audio tracks are dynamically scheduled and transmitted over the same connection session rather than separate static URL manifests.

## 2. UMP Stream Structure

A UMP stream is a sequential framing protocol composed of discrete **Parts**. Each part is serialized with variable-length integer (VINT) headers:

```text
+---------------------+-----------------------+-----------------------------+
| Part Type (VINT)    | Payload Length (VINT) | Payload Data (N bytes)      |
+---------------------+-----------------------+-----------------------------+
```

### Key Part Types Identified:

| Part ID | Name | Description |
| :--- | :--- | :--- |
| `20` (`0x14`) | `MEDIA_HEADER` | Protobuf descriptor containing the upcoming media chunk's track metadata: **`itag`** (stream format), sequence ID, timestamp (`cmt`), and bitrate. |
| `21` (`0x15`) | `MEDIA` | Raw media chunk bytes. Depending on the `itag`, this is either an ISO BMFF (`moof` + `mdat`) fragment or a Matroska/WebM Cluster. |
| `22` (`0x16`) | `NEXT_REQUEST_POLICY` | Server steering instructions informing the client when and how to issue the next sequence request (`rn+1`). |
| `35`, `47`, `52`, `53`, `58` | Control / QoS / Telemetry | Stream health diagnostics, buffer fullness targets, and connection keep-alive signals. |

### Stream Interleaving in `www.youtube.com.har`:

In the captured HAR session:
- **Video Track (`itag 395`)**: AV1 video framed in fragmented MP4 (fMP4) containing movie fragment (`moof`) and media data (`mdat`) atoms.
- **Audio Track (`itag 251`)**: Opus audio framed in Matroska/WebM Clusters (`\x1f\x43\xb6\x75`) with SimpleBlocks (`\xa3`).
- **Continuous Stream**: Parts are not constrained to individual HTTP request boundaries; a large media part can span across multiple HTTP responses (`rn=945` to `rn=950`), requiring a continuous state machine to reconstruct the stream.

## 3. Why Browser HAR Sniffing Cannot Play Standalone YouTube Videos

1. **Missing Initialization Segments (`ftyp` / `moov` / `EBML`)**:
   In fragmented streaming, media chunks only contain incremental delta frames (`moof` + `mdat`). They require the initial track header segment (`ftyp` + `moov` for MP4, or `EBML` + `Segment` + `Tracks` for WebM) to configure decoders (codecs, SPS/PPS, channel mapping). These init segments are fetched once when video starts and were not captured in this middle-stream HAR.
2. **Dynamic Ciphering (`n` parameter & `sig`)**:
   YouTube protects URLs with time-limited tokens (`expire`), IP restrictions (`ip`), and dynamic JavaScript signature ciphers (`n=...`). Without executing YouTube's player script to reverse the cipher, Google Video endpoints return `403 Forbidden` or bandwidth-throttle connections.
3. **Incomplete Playback Duration**:
   The HAR only captures a 1.5 MB playback slice (~5–10 seconds) rather than the entire video.

## 4. Extension & Desktop Compatibility

- **Browser Extension (`media.js`)**:
  `application/vnd.yt-ump` is intentionally ignored by `classify()` so that isolated UMP packets do not flood the Detected Media list as broken files.
- **Desktop HAR Import (`desktop/core.py`)**:
  `import_har` specifically identifies `application/vnd.yt-ump` and `googlevideo.com/videoplayback` sessions and informs the user that YouTube SABR/UMP streams cannot be reconstructed from browser network traces.
- **Recommended Downloader Path**:
  For full YouTube downloads, use a dedicated engine (such as `yt-dlp`) that interfaces directly with the YouTube InnerTube player API and reverses the dynamic player signature.
