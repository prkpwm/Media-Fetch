export function classify(url, mime = '') {
  let path;
  try { const u = new URL(url); if (!['http:', 'https:'].includes(u.protocol)) return null; path = u.pathname; } catch { return null; }
  if (/\.m3u8$/i.test(path) || /mpegurl/i.test(mime)) return 'hls';
  if (/\.mpd$/i.test(path) || /dash\+xml/i.test(mime)) return 'dash';
  if (/\.(ts|m4s)$/i.test(path) || /mp2t/i.test(mime)) return null;
  if (/\.(mp4|webm|mkv|mov|mp3|m4a|ogg|wav)$/i.test(path) || /^(video|audio)\//i.test(mime)) return 'file';
  return null;
}
export function httpURL(value, base) {
  const u = new URL(value, base);
  if (!['https:', 'http:'].includes(u.protocol)) throw new Error('Unsupported media URL.');
  return u.href;
}
function attributes(line) {
  return Object.fromEntries([...line.slice(line.indexOf(':') + 1).matchAll(/([A-Z0-9-]+)=("[^"]*"|[^,]*)/g)]
    .map(([,key,value]) => [key,value.replace(/^"|"$/g,'')]));
}
// Discovery must retain choices even when downloading their tracks is unsupported.
export function inspectHLS(text, base) {
  const lines=text.trim().split(/\r?\n/).map(x=>x.trim()).filter(Boolean);
  if(lines[0]!=='#EXTM3U') throw new Error('Server did not return an HLS playlist.');
  const audio=lines.filter(x=>x.startsWith('#EXT-X-MEDIA:')).map(attributes).filter(x=>x.TYPE==='AUDIO');
  const encryption=lines.filter(x=>/^#EXT-X-(SESSION-)?KEY:/.test(x)).map(attributes).find(x=>x.METHOD!=='NONE')?.METHOD;
  const variants=[];
  for(let i=0;i<lines.length;i++) {
    if(!lines[i].startsWith('#EXT-X-STREAM-INF:')) continue;
    const attrs=attributes(lines[i]);
    if(!lines[i+1] || lines[i+1].startsWith('#')) throw new Error('Malformed variant playlist.');
    const track=audio.find(x=>x['GROUP-ID']===attrs.AUDIO && x.DEFAULT==='YES') || audio.find(x=>x['GROUP-ID']===attrs.AUDIO);
    const height=Number(attrs.RESOLUTION?.split('x')[1]) || 0;
    variants.push({url:httpURL(lines[i+1],base),height,resolution:attrs.RESOLUTION || '',bandwidth:Number(attrs.BANDWIDTH)||0,
      audio:track?.NAME || track?.LANGUAGE || '',audioUrl:track?.URI ? httpURL(track.URI,base) : '',separateAudio:Boolean(track?.URI),separateVideo:Boolean(attrs.VIDEO),encryption});
  }
  return {variants:variants.sort((a,b)=>a.height-b.height || a.bandwidth-b.bandwidth),encryption};
}
export function qualityLabel(variant) {
  return [variant.height ? `${variant.height}p${variant.height>=720?' HD':''}` : 'Original quality',
    variant.bandwidth ? `${Math.round(variant.bandwidth/1000)} kbps` : '',variant.audio ? `${variant.audio} audio` : ''].filter(Boolean).join(' · ');
}
export function parseHLS(text, base) {
  const lines = text.trim().split(/\r?\n/).map(x => x.trim()).filter(Boolean);
  if (lines[0] !== '#EXTM3U') throw new Error('Server did not return an HLS playlist.');
  if (lines.some(x => /^#EXT-X-(SESSION-)?KEY:/.test(x) && !/^#EXT-X-KEY:METHOD=NONE$/.test(x))) throw new Error('Encrypted HLS is unsupported.');
  const variants = [];
  for (let i = 0; i < lines.length; i++) {
    if (!lines[i].startsWith('#EXT-X-STREAM-INF:')) continue;
    if (/AUDIO=|VIDEO=/.test(lines[i])) throw new Error('Separate audio/video tracks require a muxer and are unsupported.');
    if (!lines[i + 1] || lines[i + 1].startsWith('#')) throw new Error('Malformed variant playlist.');
    variants.push({url:httpURL(lines[i + 1], base), bandwidth:Number(lines[i].match(/(?:[:,])BANDWIDTH=(\d+)/)?.[1] || 0)});
  }
  if (variants.length) return {variants:variants.sort((a,b) => b.bandwidth-a.bandwidth)};
  if (!lines.includes('#EXT-X-ENDLIST')) throw new Error('Live playlists are unsupported. Wait for a complete VOD playlist.');
  if (lines.some(x => /^#EXT-X-(MAP|BYTERANGE|DISCONTINUITY)(:|$)/.test(x))) throw new Error('Fragmented MP4, byte ranges, and discontinuities require a muxer and are unsupported.');
  const segments = lines.filter(x => !x.startsWith('#')).map(x => httpURL(x, base));
  if (!segments.length) throw new Error('No video segments found.');
  return {segments};
}
