// node render.mjs <out.mp4|dir/> [--w 1920 --h 1080 --fps 30 --from s --to s --stills 1,2,3 --crf 18 --ref 1080 --hevc 1 --ofps 60]
// --ofps: play the frames sampled at --fps back at this rate (--fps 69 --ofps 60 = the film at 1.15x speed)
// Renders film.js in headless Chrome (Metal GPU) and pipes JPEG frames into ffmpeg.
import { chromium } from 'playwright-core';
import { spawn } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = path.dirname(fileURLToPath(import.meta.url));
const argv = process.argv.slice(2), opt = {}, pos = [];
for (let i = 0; i < argv.length; i++) argv[i].startsWith('--') ? (opt[argv[i].slice(2)] = argv[++i]) : pos.push(argv[i]);
const [out] = pos;
const W = +(opt.w || 1920), H = +(opt.h || 1080), FPS = +(opt.fps || 30), OFPS = +(opt.ofps || FPS);
const MIME = { '.js': 'text/javascript', '.mjs': 'text/javascript', '.html': 'text/html', '.json': 'application/json',
  '.png': 'image/png', '.jpg': 'image/jpeg', '.bin': 'application/octet-stream' };
const browser = await chromium.launch({ channel: 'chrome', headless: true,
  args: ['--use-angle=metal', '--enable-gpu', '--ignore-gpu-blocklist', '--enable-unsafe-swiftshader=false'] });
const page = await browser.newPage({ viewport: { width: W, height: H } });
page.on('console', (m) => { if (m.type() === 'error' || m.type() === 'warning') console.error('[page]', m.text().slice(0, 2000)); });
page.on('pageerror', (e) => console.error('[pageerror]', e.message));
await page.route('http://film.local/**', async (route) => {
  const u = new URL(route.request().url());
  const f = path.join(ROOT, decodeURIComponent(u.pathname === '/' ? '/page.html' : u.pathname));
  if (!f.startsWith(ROOT) || !fs.existsSync(f)) return route.fulfill({ status: 404, body: 'nf' });
  route.fulfill({ contentType: MIME[path.extname(f)] || 'application/octet-stream', body: fs.readFileSync(f) });
});
await page.goto(`http://film.local/page.html?w=${W}&h=${H}&ref=${opt.ref || 1080}&strips=${opt.strips || (W * H > 1920 * 1080 ? 32 : 1)}`);
await page.waitForFunction(() => window.READY || window.ERR, null, { timeout: 120000 });
const err = await page.evaluate(() => window.ERR);
if (err) { console.error(err); await browser.close(); process.exit(1); }
const DUR = await page.evaluate(() => window.DUR);

if (opt.stills) {
  fs.mkdirSync(out, { recursive: true });
  for (const ts of opt.stills.split(',').map(Number)) {
    const tA = Date.now();
    const b64 = await page.evaluate((t) => window.frame(t), ts);
    fs.writeFileSync(path.join(out, `f_${ts.toFixed(2)}.jpg`), Buffer.from(b64, 'base64'));
    console.log(`still ${ts} ${Date.now() - tA} ms`);
  }
} else {
  const fa = Math.round(+(opt.from || 0) * FPS), fb = Math.round(+(opt.to || DUR) * FPS);
  const ff = spawn('ffmpeg', ['-y', '-loglevel', 'error', '-f', 'image2pipe', '-c:v', 'mjpeg', '-framerate', String(OFPS), '-i', '-',
    // --hevc: x265 chunks are about half the size of x264 at the same quality (4K60 chunks would not fit on disk otherwise)
    ...(opt.hevc ? ['-c:v', 'libx265', '-preset', opt.preset || 'fast', '-tag:v', 'hvc1', '-x265-params', 'log-level=error'] : ['-c:v', 'libx264', '-preset', opt.preset || 'medium']),
    '-crf', opt.crf || '18', ...(opt.maxrate ? ['-maxrate', opt.maxrate, '-bufsize', opt.maxrate] : []),
    '-pix_fmt', 'yuv420p', '-r', String(OFPS), out], { stdio: ['pipe', 'inherit', 'inherit'] });
  const tA = Date.now();
  for (let i = fa; i < fb; i++) {
    const b64 = await page.evaluate((t) => window.frame(t), i / FPS);
    if (!ff.stdin.write(Buffer.from(b64, 'base64'))) await new Promise((r) => ff.stdin.once('drain', r));
    if (i % 30 === 0) process.stdout.write(`\r${i - fa}/${fb - fa}`);
  }
  ff.stdin.end();
  await new Promise((r) => ff.on('close', r));
  const s = (Date.now() - tA) / 1000;
  console.log(`\n${fb - fa} frames in ${s.toFixed(1)}s (${(1000 * s / (fb - fa)).toFixed(0)} ms/frame) -> ${out}`);
}
await browser.close();
