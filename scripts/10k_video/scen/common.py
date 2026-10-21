import os, sys
from urllib.parse import quote
try:
    from PySide6 import QtWidgets, QtCore
except ImportError:
    from PySide2 import QtWidgets, QtCore
SRV = "http://dl.example.com"
def url(name, size_mb=0, rate_mbps=0):
    return f"{SRV}/releases/{quote(name)}"
TASKS = [
    ("Ghost-Downloader-Setup-x86_64.exe", 46, 30),
    ("ubuntu-24.04.3-desktop-amd64.iso", 6100, 34),
    ("Blender-4.5.3-windows-x64.msi", 362, 15),
    ("Big_Buck_Bunny_4K_60fps.mp4", 880, 11),
    ("Qwen3-8B-Q4_K_M.gguf", 5030, 26),
    ("VSCodeUserSetup-x64-1.105.1.exe", 112, 7),
]
URLS = [url(t[0]) for t in TASKS]

def wait_top(h, *names, timeout=30000):
    t = 0
    while t < timeout:
        w = h.top(*names)
        if w is not None:
            return w
        yield 250; t += 250
    raise RuntimeError(f"top {names} not found")

def flip(h, name, n=10, interval=800, top=None):
    """capture a flipbook: name_f00.. every `interval` ms; components only on first and last frame."""
    for i in range(n):
        h.capture(f"{name}_f{i:02d}", top, comps=(i in (0, n - 1)))
        if i < n - 1:
            yield interval
