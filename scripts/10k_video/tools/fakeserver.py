"""Throttled fake download server. URL: /<rate_kbps>/<size_bytes>/<filename>
Supports HEAD, Range, per-file shared bandwidth budget."""
import sys, time, threading, re, os
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import unquote, quote

BUCKETS = {}
LOCK = threading.Lock()
CHUNK = 16384
BLOCK = (bytes(range(256)) * (CHUNK // 256))

import json
FILES = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "files.json"), encoding="utf-8"))

class Bucket:
    def __init__(self, rate):
        self.rate = rate; self.t = time.monotonic(); self.tokens = 0.0; self.lock = threading.Lock()
    def take(self, n):
        while True:
            with self.lock:
                now = time.monotonic()
                self.tokens = min(self.tokens + (now - self.t) * self.rate, self.rate * 0.25)
                self.t = now
                if self.tokens >= n:
                    self.tokens -= n; return
                wait = (n - self.tokens) / self.rate
            time.sleep(min(wait, 0.05))

class H(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    def log_message(self, *a): pass
    def parse(self):
        path = self.path.split("?")[0]
        m = re.match(r"^/(\d+)/(\d+)/(.+)$", path)
        if m:
            return int(m.group(1)) * 1024, int(m.group(2)), unquote(m.group(3))
        name = unquote(path.rsplit("/", 1)[-1])
        if name in FILES:
            size_mb, rate_mbps = FILES[name]
            return int(rate_mbps * 1048576), int(size_mb * 1048576), name
        return None
    def headers_for(self, size, name, start, end, partial):
        self.send_response(206 if partial else 200)
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Accept-Ranges", "bytes")
        if os.environ.get("FS_CD"): self.send_header("Content-Disposition", "attachment; filename*=UTF-8''" + quote(name))
        self.send_header("Content-Length", str(end - start + 1))
        self.send_header("Last-Modified", "Mon, 20 Oct 2026 08:00:00 GMT")
        self.send_header("ETag", '"%x"' % size)
        if partial: self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.end_headers()
    def rng(self, size):
        r = self.headers.get("Range")
        if r:
            m = re.match(r"bytes=(\d*)-(\d*)", r)
            if m:
                s = int(m.group(1)) if m.group(1) else 0
                e = int(m.group(2)) if m.group(2) else size - 1
                return s, min(e, size - 1), True
        return 0, size - 1, False
    def do_HEAD(self):
        p = self.parse()
        if not p: self.send_error(404); return
        rate, size, name = p
        s, e, partial = self.rng(size)
        self.headers_for(size, name, s, e, partial)
    def do_GET(self):
        p = self.parse()
        if not p: self.send_error(404); return
        rate, size, name = p
        s, e, partial = self.rng(size)
        self.headers_for(size, name, s, e, partial)
        with LOCK:
            b = BUCKETS.setdefault((name, rate), Bucket(rate))
        left = e - s + 1
        try:
            while left > 0:
                n = min(CHUNK, left)
                if rate > 0: b.take(n)
                self.wfile.write(BLOCK[:n]); left -= n
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass

if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 18080
    ThreadingHTTPServer.daemon_threads = True
    ThreadingHTTPServer(("127.0.0.1", port), H).serve_forever()
