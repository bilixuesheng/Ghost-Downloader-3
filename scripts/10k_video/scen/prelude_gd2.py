# Make Ghost Downloader 2 (Windows-only, PySide2) start on Linux for screenshots.
import os, sys, types, threading
os.startfile = lambda *a, **k: None
class _WV:
    build = 22000; major = 10; minor = 0
sys.getwindowsversion = lambda: _WV()

from PySide2 import QtWidgets, QtCore
m = types.ModuleType("PySide2.QtWinExtras")
class QtWin:
    @staticmethod
    def enableBlurBehindWindow(*a, **k): pass
m.QtWin = QtWin
sys.modules["PySide2.QtWinExtras"] = m

# windoweffect: record the acrylic tint instead of calling DWM
we = types.ModuleType("windoweffect")
class WindowEffect:
    tint = "FFFFFF99"
    def setAcrylicEffect(self, hWnd, gradientColor="FFFFFF99", *a, **k):
        WindowEffect.tint = gradientColor
    def __getattr__(self, name):
        return lambda *a, **k: None
class _S: pass
we.WindowEffect = WindowEffect; we.MINMAXINFO = _S; we.NCCALCSIZE_PARAMS = _S
sys.modules["windoweffect"] = we

import framelesswindow.frameless_window as _fw
for _cls in (_fw.FramelessWindow, _fw.FramelessDialog):
    _cls.nativeEvent = lambda self, t, m: (False, 0)
_fw.FramelessWindow._FramelessWindow__isWindowMaximized = lambda self, h: False
_fw.FramelessDialog._FramelessDialog__isWindowMaximized = lambda self, h: False
_fw.FramelessWindow._FramelessWindow__onScreenChanged = lambda self: None

# Offline: the online resource list / donation info are unreachable, serve them empty;
# remote images fall back to the app logo. Local test downloads pass through.
import requests as _rq
_RQ_GET = _rq.get
class _Resp:
    status_code = 200
    encoding = "utf-8"
    def __init__(self, data):
        self.content = data
        self.text = data.decode("utf-8", "ignore")
        self.headers = {"content-length": str(len(data))}
    def raise_for_status(self): pass
def _get(*a, **k):
    u = str(a[0] if a else k.get("url"))
    if "example.com" in u:
        return _RQ_GET(*a, **k)
    if u.endswith((".png", ".jpg")):
        return _Resp(open("skins/Default/logo.png", "rb").read())
    return _Resp(b"")
_rq.get = _get

# Forking the Qt process hangs here; run the download engine in a thread (progress is read from cache files).
import DownloadEngine as _de
_de.DownloadEngine.start = lambda self: threading.Thread(target=self.run, daemon=True).start()
