// node hud.mjs <base.mp4> <out> [--audio a.wav --w 960 --h 540 --fps 30 --hevc 1 --crf 20 --stills 17,23,28.5]
// Draws hud.js (narration cues) frame by frame in headless Chrome and overlays it on an already rendered film.
// The base video is in final time, so frame i is at t = i / fps. --stills writes JPEG stills into the <out> folder.
import { chromium } from 'playwright-core';
import { spawn, spawnSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = path.dirname(fileURLToPath(import.meta.url));
const argv = process.argv.slice(2), opt = {}, pos = [];
for (let i = 0; i < argv.length; i++) argv[i].startsWith('--') ? (opt[argv[i].slice(2)] = argv[++i]) : pos.push(argv[i]);
const [base, out] = pos;
const W = +(opt.w || 960), H = +(opt.h || 540), FPS = +(opt.fps || 30);
const browser = await chromium.launch({ channel: 'chrome', headless: true });
const page = await browser.newPage({ viewport: { width: W, height: H } });
page.on('pageerror', (e) => console.error('[pageerror]', e.message));
page.on('console', (m) => { if (m.type() === 'error') console.error('[page]', m.text()); });
await page.route('http://film.local/**', (route) => {
  const f = path.join(ROOT, new URL(route.request().url()).pathname);
  if (!f.startsWith(ROOT) || !fs.existsSync(f)) return route.fulfill({ status: 404, body: 'nf' });
  route.fulfill({ contentType: f.endsWith('.js') ? 'text/javascript' : 'text/html', body: fs.readFileSync(f) });
});
await page.goto(`http://film.local/hud.html?w=${W}&h=${H}`);
await page.waitForFunction(() => window.READY, null, { timeout: 30000 });
const png = (u) => Buffer.from(u.slice(u.indexOf(',') + 1), 'base64');
const blank = png(await page.evaluate(() => { const c = document.createElement('canvas'); c.width = document.getElementById('c').width; c.height = document.getElementById('c').height; return c.toDataURL('image/png'); }));
const hud = async (t) => { const u = await page.evaluate((t) => window.hud(t), t); return u ? png(u) : blank; };

if (opt.stills) {
  fs.mkdirSync(out, { recursive: true });
  for (const t of opt.stills.split(',').map(Number)) {
    const tmp = path.join(out, `.h_${t}.png`);
    fs.writeFileSync(tmp, await hud(t));
    spawnSync('ffmpeg', ['-y', '-loglevel', 'error', '-ss', String(t), '-i', base, '-i', tmp, '-filter_complex',
      `[0:v]scale=${W}:${H}[b];[b][1:v]overlay=0:0`, '-frames:v', '1', '-q:v', '3', path.join(out, `h_${t.toFixed(2)}.jpg`)], { stdio: 'inherit' });
    fs.unlinkSync(tmp);
  }
} else {
  const dur = +spawnSync('ffprobe', ['-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', base]).stdout.toString();
  const n = Math.round(dur * FPS);
  const enc = opt.hevc ? ['-c:v', 'libx265', '-preset', 'medium', '-tag:v', 'hvc1', '-x265-params', 'log-level=error'] : ['-c:v', 'libx264', '-preset', 'fast'];
  const ff = spawn('nice', ['-n', '15', 'ffmpeg', '-y', '-loglevel', 'error', '-i', base, '-f', 'image2pipe', '-c:v', 'png', '-framerate', String(FPS), '-i', '-',
    ...(opt.audio ? ['-i', opt.audio] : []), '-filter_complex', `[0:v]scale=${W}:${H},fps=${FPS}[b];[b][1:v]overlay=0:0:format=auto,format=yuv420p[v]`,
    '-map', '[v]', ...(opt.audio ? ['-map', '2:a', '-c:a', 'aac', '-b:a', opt.ab || '192k'] : []), ...enc, '-crf', opt.crf || '20',
    '-r', String(FPS), '-frames:v', String(n), '-movflags', '+faststart', out], { stdio: ['pipe', 'inherit', 'inherit'] });
  const tA = Date.now();
  for (let i = 0; i < n; i++) {
    if (!ff.stdin.write(await hud(i / FPS))) await new Promise((r) => ff.stdin.once('drain', r));
    if (i % 300 === 0) process.stdout.write(`\r${i}/${n}`);
  }
  ff.stdin.end();
  await new Promise((r) => ff.on('close', r));
  console.log(`\n${n} frames in ${((Date.now() - tA) / 1000).toFixed(0)}s -> ${out}`);
}
await browser.close();
