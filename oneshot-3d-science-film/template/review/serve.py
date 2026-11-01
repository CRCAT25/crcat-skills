# Review page server with HTTP Range support, so the browser can seek in the draft video.
# python3 serve.py [port]   (serves this folder on 127.0.0.1)
import os, re, sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

class H(SimpleHTTPRequestHandler):
    def send_head(self):
        path = self.translate_path(self.path)
        m = re.match(r'bytes=(\d*)-(\d*)$', self.headers.get('Range', ''))
        if not m or not os.path.isfile(path):
            return super().send_head()
        size = os.path.getsize(path)
        a = int(m[1]) if m[1] else max(0, size - int(m[2] or 0))
        b = min(int(m[2]), size - 1) if m[1] and m[2] else size - 1
        if a >= size:
            self.send_error(416); return None
        f = open(path, 'rb'); f.seek(a)
        self.send_response(206)
        self.send_header('Content-Type', self.guess_type(path))
        self.send_header('Content-Range', f'bytes {a}-{b}/{size}')
        self.send_header('Content-Length', str(b - a + 1))
        self.send_header('Accept-Ranges', 'bytes')
        self.end_headers()
        self.left = b - a + 1
        return f

    def copyfile(self, src, dst):
        n = getattr(self, 'left', None)
        if n is None: return super().copyfile(src, dst)
        while n > 0:
            buf = src.read(min(1 << 20, n))
            if not buf: break
            try: dst.write(buf)
            except (BrokenPipeError, ConnectionResetError): break
            n -= len(buf)

    def end_headers(self):
        self.send_header('Accept-Ranges', 'bytes')
        self.send_header('Cache-Control', 'no-store')
        super().end_headers()

os.chdir(os.path.dirname(os.path.abspath(__file__)))
ThreadingHTTPServer(('127.0.0.1', int(sys.argv[1]) if len(sys.argv) > 1 else 8797), H).serve_forever()
