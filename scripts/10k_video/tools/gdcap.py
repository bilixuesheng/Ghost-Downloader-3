"""Capture harness: runs a Ghost Downloader entry script, then drives a scenario
(generator) on the Qt main thread to take screenshots + component dumps."""
import sys, os, runpy, json, faulthandler, traceback, importlib.util, time

ENTRY, OUT, SCEN = sys.argv[1], sys.argv[2], sys.argv[3]
os.makedirs(OUT, exist_ok=True)
faulthandler.dump_traceback_later(int(os.environ.get("CAP_TIMEOUT", "240")), exit=True)
sys.argv = [ENTRY] + sys.argv[4:]
sys.path.insert(0, os.path.dirname(os.path.abspath(ENTRY)))
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from PySide6 import QtWidgets, QtCore, QtGui
except ImportError:
    from PySide2 import QtWidgets, QtCore, QtGui

LOG = open(os.path.join(OUT, "cap.log"), "a", encoding="utf-8")
def log(*a):
    s = " ".join(str(x) for x in a)
    print("[cap]", s, flush=True); LOG.write(s + "\n"); LOG.flush()


def clsnames(w):
    return [c.__name__ for c in type(w).__mro__]


def text_of(w):
    for attr in ("text", "title", "windowTitle"):
        f = getattr(w, attr, None)
        if callable(f):
            try:
                t = f()
                if isinstance(t, str) and t.strip():
                    return t.strip()
            except Exception:
                pass
    return ""


def visible_rect(w, top):
    """visible rect of w in top coordinates, clipped by ancestors."""
    r = QtCore.QRect(w.mapTo(top, QtCore.QPoint(0, 0)), QtWidgets.QWidget.size(w))
    p = w.parentWidget()
    while p is not None and p is not top:
        pr = QtCore.QRect(p.mapTo(top, QtCore.QPoint(0, 0)), QtWidgets.QWidget.size(p))
        r = r.intersected(pr)
        p = p.parentWidget()
    return r.intersected(QtCore.QRect(QtCore.QPoint(0, 0), QtWidgets.QWidget.size(top)))


def really_visible(w, top):
    x = w
    while x is not None:
        if not x.isVisible():
            return False
        if x is top:
            return True
        eff = x.graphicsEffect()
        if isinstance(eff, QtWidgets.QGraphicsOpacityEffect) and eff.opacity() < 0.05:
            return False
        x = x.parentWidget()
    return True


def tree(w, top, depth=0, out=None):
    out = [] if out is None else out
    for c in w.children():
        if isinstance(c, QtWidgets.QWidget) and c.isVisible():
            r = visible_rect(c, top)
            out.append({"d": depth, "cls": clsnames(c)[:6], "name": c.objectName(), "text": text_of(c)[:60],
                        "rect": [r.x(), r.y(), r.width(), r.height()]})
            tree(c, top, depth + 1, out)
    return out


class H:
    def __init__(self):
        self.app = QtWidgets.QApplication.instance()
        self.n = 0

    # ---- finding
    def tops(self):
        return [w for w in self.app.topLevelWidgets() if w.isVisible()]

    def top(self, *names):
        for w in self.tops():
            cn = clsnames(w)
            if not names or any(n in cn for n in names):
                return w
        return None

    def find(self, root, pred):
        res = []
        for c in root.findChildren(QtWidgets.QWidget):
            try:
                if pred(c):
                    res.append(c)
            except Exception:
                pass
        return res

    def by_cls(self, root, name, visible=True):
        return [c for c in root.findChildren(QtWidgets.QWidget)
                if name in clsnames(c) and (not visible or c.isVisible())]

    def by_text(self, root, text, cls=None, visible=True):
        return [c for c in root.findChildren(QtWidgets.QWidget)
                if text_of(c) == text and (cls is None or cls in clsnames(c)) and (not visible or c.isVisible())]

    def later(self, fn, ms=0):
        """run fn from a timer (for calls that open modal loops)."""
        def run():
            try:
                fn()
            except Exception:
                log("later error\n" + traceback.format_exc())
        QtCore.QTimer.singleShot(ms, run)

    def click(self, w, later=True):
        if later:
            self.later(lambda: self.click(w, later=False)); return
        log("click", type(w).__name__, text_of(w))
        if hasattr(w, "click"):
            w.click()
        else:
            c = QtCore.QPoint(w.width() // 2, w.height() // 2)
            for t in (QtCore.QEvent.MouseButtonPress, QtCore.QEvent.MouseButtonRelease):
                ev = QtGui.QMouseEvent(t, QtCore.QPointF(c), QtCore.QPointF(w.mapToGlobal(c)),
                                       QtCore.Qt.LeftButton, QtCore.Qt.LeftButton, QtCore.Qt.NoModifier)
                self.app.sendEvent(w, ev)

    # ---- capture
    def capture(self, name, top=None, meta=None, comps=True):
        top = top or self.main
        self.app.processEvents()
        pm = top.grab()
        path = os.path.join(OUT, f"{name}.png")
        pm.save(path)
        info = {"name": name, "cls": clsnames(top)[:6], "size": [QtWidgets.QWidget.width(top), QtWidgets.QWidget.height(top)],
                "dpr": pm.devicePixelRatio(), "meta": meta or {}, "tree": tree(top, top)}
        with open(os.path.join(OUT, f"{name}.json"), "w", encoding="utf-8") as f:
            json.dump(info, f, ensure_ascii=False, indent=0)
        if comps and not os.environ.get("CAP_NOCOMP"):
            try:
                import gdcomp
                n = gdcomp.export(top, OUT, name)
                log("components", name, n)
            except Exception:
                log("component export failed\n" + traceback.format_exc())
        log("captured", name, QtWidgets.QWidget.size(top))
        return path

    def resize(self, w, h, top=None):
        top = top or self.main
        top.resize(w, h)


h = None
_gen = None
def _step():
    global _gen
    try:
        ms = next(_gen)
        QtCore.QTimer.singleShot(int(ms or 0), _step)
    except StopIteration:
        log("scenario done"); LOG.flush()
        os.system("pkill -9 -P %d >/dev/null 2>&1" % os.getpid())
        os._exit(0)
    except Exception:
        log("scenario error\n" + traceback.format_exc()); os._exit(3)


def _start():
    global h, _gen
    h = H()
    spec = importlib.util.spec_from_file_location("scenario", SCEN)
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    _gen = mod.scenario(h, log)
    _step()

_armed = [False]
def _arm():
    if not _armed[0]:
        _armed[0] = True
        QtCore.QTimer.singleShot(300, _start)

for cls in (QtWidgets.QApplication, QtCore.QEventLoop, QtWidgets.QDialog):
  for meth in ("exec", "exec_"):
    orig = getattr(cls, meth, None)
    if orig is None:
        continue
    def make(orig, static):
        def _exec(*a, **k):
            _arm()
            if static:
                return orig()
            return orig(*a, **k)
        return _exec
    setattr(cls, meth, make(orig, cls is QtWidgets.QApplication))

if os.environ.get("CAP_PRELUDE"):
    exec(compile(open(os.environ["CAP_PRELUDE"], encoding="utf-8").read(), os.environ["CAP_PRELUDE"], "exec"), {"__name__": "prelude"})
runpy.run_path(ENTRY, run_name="__main__")
