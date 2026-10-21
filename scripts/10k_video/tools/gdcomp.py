"""Split a captured window into morphable components.

For a top-level window we pick "component" widgets (navigation items, cards,
buttons, labels, inputs, dialogs ...), grab each one as a sprite, then grab a
background plate with all of them made invisible.  The video renderer matches
components between two captures by key and animates them.
"""
import json
import os

try:
    from PySide6 import QtCore, QtGui, QtWidgets
except ImportError:
    from PySide2 import QtCore, QtGui, QtWidgets

LEAF_HINTS = (
    "Button", "Label", "LineEdit", "TextEdit", "ProgressBar", "ProgressRing", "ComboBox",
    "SegmentedWidget", "Pivot", "Slider", "SwitchButton", "CheckBox", "RadioButton", "SpinBox",
    "InfoBar", "IconWidget", "Badge", "TrackBar",
)
CONTAINER_NAMES = {
    "QWidget", "QFrame", "QStackedWidget", "StackedWidget", "PopUpAniStackedWidget", "QScrollArea",
    "ScrollArea", "SmoothScrollArea", "SingleDirectionScrollArea", "ExpandLayout", "QSplitter",
    "NavigationBar", "NavigationInterface", "NavigationPanel", "SettingCardGroup", "QAbstractScrollArea",
}
SKIP_HINTS = ("ScrollBar", "ToolTip", "SplashScreen", "Shadow", "Mask")
NAV_HINTS = ("NavigationBarPushButton", "NavigationPushButton", "NavigationTreeWidget",
             "NavigationToolButton", "NavigationAvatarWidget", "NavigationWidget")

BTN = ("PushButton", "ToolButton", "QPushButton", "QToolButton", "SplitPushButton", "DropDownPushButton",
       "HyperlinkButton", "PillPushButton", "TogglePushButton")


def _names(w):
    return [c.__name__ for c in type(w).__mro__]


def _text(w):
    for attr in ("text", "title", "windowTitle", "placeholderText"):
        f = getattr(w, attr, None)
        if callable(f):
            try:
                t = f()
                if isinstance(t, str) and t.strip():
                    return t.strip()
            except Exception:
                pass
    return ""


def _first_text(w):
    t = _text(w)
    if t:
        return t
    for c in w.findChildren(QtWidgets.QWidget):
        if c.isVisible() and isinstance(c, (QtWidgets.QLabel, QtWidgets.QAbstractButton)):
            t = _text(c)
            if t:
                return t
    return ""


def _kind(w):
    names = _names(w)
    n = names[0]
    if any(h in n for h in NAV_HINTS) or any(h in names for h in NAV_HINTS):
        return "nav"
    if "TitleBar" in n:
        return "titlebar"
    if "Dialog" in n or "MessageBox" in n or "Drawer" in n:
        return "dialog"
    if "Card" in n or any("CardWidget" == x for x in names):
        return "card"
    if any(x.endswith(BTN) or x in BTN for x in names[:4]):
        return "btn"
    if "Label" in n or isinstance(w, QtWidgets.QLabel):
        return "lbl"
    if "Edit" in n:
        return "edit"
    if "Progress" in n:
        return "prog"
    return n


def _is_component(w):
    names = _names(w)
    n = names[0]
    if any(h in n for h in SKIP_HINTS):
        return None
    k = _kind(w)
    if k in ("nav", "titlebar", "dialog", "card"):
        return k
    if n in CONTAINER_NAMES:
        return None
    if any(h in n for h in LEAF_HINTS) or isinstance(w, (QtWidgets.QAbstractButton, QtWidgets.QLabel,
                                                          QtWidgets.QLineEdit, QtWidgets.QTextEdit,
                                                          QtWidgets.QPlainTextEdit, QtWidgets.QProgressBar,
                                                          QtWidgets.QComboBox, QtWidgets.QAbstractSlider,
                                                          QtWidgets.QAbstractItemView)):
        return k
    return None


def _visible_rect(w, top):
    # some app widgets shadow size()/width() with attributes, so call the Qt methods directly
    r = QtCore.QRect(w.mapTo(top, QtCore.QPoint(0, 0)), QtWidgets.QWidget.size(w))
    p = w.parentWidget()
    while p is not None and p is not top:
        r = r.intersected(QtCore.QRect(p.mapTo(top, QtCore.QPoint(0, 0)), QtWidgets.QWidget.size(p)))
        p = p.parentWidget()
    return r.intersected(QtCore.QRect(QtCore.QPoint(0, 0), QtWidgets.QWidget.size(top)))


def _opacity_hidden(w):
    x = w
    while x is not None:
        eff = x.graphicsEffect()
        if isinstance(eff, QtWidgets.QGraphicsOpacityEffect) and eff.opacity() < 0.05:
            return True
        x = x.parentWidget()
    return False


def select(top):
    out = []

    def walk(parent, depth):
        for c in parent.children():
            if not isinstance(c, QtWidgets.QWidget) or not c.isVisible() or c.isWindow():
                continue
            r = _visible_rect(c, top)
            if r.width() < 4 or r.height() < 4 or _opacity_hidden(c):
                continue
            k = _is_component(c)
            if k:
                out.append((c, k, r))
                if k == "dialog":
                    # the overlay itself is one sprite, but its parts morph individually too
                    walk(c, depth + 1)
            else:
                walk(c, depth + 1)

    walk(top, 0)
    return out


def export(top, out_dir, name):
    os.makedirs(os.path.join(out_dir, name + "_c"), exist_ok=True)
    comps = select(top)
    meta = []
    dpr = None
    # dialogs are drawn above their own parts: grab the dialog without its morphing parts
    dialog_parts = {}
    for i, (w, k, r) in enumerate(comps):
        if k == "dialog":
            dialog_parts[i] = [j for j, (w2, k2, r2) in enumerate(comps) if j != i and w.isAncestorOf(w2)]
    effects = {}

    def hide(idx):
        for j in idx:
            w = comps[j][0]
            if w.graphicsEffect() is None:
                e = QtWidgets.QGraphicsOpacityEffect(w)
                e.setOpacity(0.0)
                w.setGraphicsEffect(e)
                effects[j] = e

    def unhide(idx):
        for j in idx:
            if j in effects:
                comps[j][0].setGraphicsEffect(None)
                effects.pop(j)

    for i, (w, k, r) in enumerate(comps):
        local = QtCore.QRect(w.mapFrom(top, r.topLeft()), r.size())
        if i in dialog_parts:
            hide(dialog_parts[i])
            QtWidgets.QApplication.processEvents()
        pm = w.grab(local)
        if i in dialog_parts:
            unhide(dialog_parts[i])
        dpr = pm.devicePixelRatio()
        fn = f"{i:03d}.png"
        pm.save(os.path.join(out_dir, name + "_c", fn))
        names = _names(w)
        meta.append({
            "i": i, "kind": k, "cls": names[0], "text": _first_text(w)[:80], "obj": w.objectName(),
            "rect": [r.x(), r.y(), r.width(), r.height()], "file": fn,
            "z": i, "has_effect": i not in effects and w.graphicsEffect() is not None,
            "parent_dialog": next((d for d, parts in dialog_parts.items() if i in parts), None),
        })
    # plate: everything hidden
    hide(range(len(comps)))
    QtWidgets.QApplication.processEvents()
    plate = top.grab()
    plate.save(os.path.join(out_dir, name + "_plate.png"))
    unhide(list(effects.keys()))
    QtWidgets.QApplication.processEvents()
    with open(os.path.join(out_dir, name + "_c", "comps.json"), "w", encoding="utf-8") as f:
        json.dump({"size": [QtWidgets.QWidget.width(top), QtWidgets.QWidget.height(top)], "dpr": dpr or plate.devicePixelRatio(),
                   "comps": meta}, f, ensure_ascii=False, indent=0)
    return len(meta)
