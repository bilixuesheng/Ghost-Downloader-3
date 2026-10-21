import sys; sys.path.insert(0, __file__.rsplit('/',1)[0])
from common import *
from PySide6 import QtWidgets

NTASK = int(os.environ.get("NTASK", "6"))
PAGES = os.environ.get("PAGES", "设置").split(",")

def nav(h, main, text):
    ws = [w for w in h.by_text(main, text) if "Navigation" in type(w).__name__]
    return ws[0] if ws else None

def find_dialog(h, main):
    for top in [main] + h.tops():
        for w in [top] + top.findChildren(QtWidgets.QWidget):
            n = type(w).__name__
            if ("AddTask" in n or "TaskDialog" in n) and w.isVisible():
                return w
    return None

def text_edit(dlg):
    te = getattr(dlg, "linkTextEdit", None)
    if te is None:
        for w in dlg.findChildren(QtWidgets.QWidget):
            if isinstance(w, (QtWidgets.QTextEdit, QtWidgets.QPlainTextEdit)) and w.isVisible():
                return w
    return te

def scenario(h, log):
    main = None
    while main is None:
        yield 300
        main = h.top("MainWindow")
    h.main = main
    yield 3000
    main.resize(1120, 740)
    yield 1000
    h.capture("home")
    multi = os.environ.get("MULTI", "1") == "1"
    groups = [URLS[:NTASK]] if multi else [[u] for u in URLS[:NTASK]]
    for i, g in enumerate(groups):
        b = nav(h, main, "新建任务")
        if b is not None:
            h.click(b)
        else:
            h.later(main.showAddTaskBox)
        yield 1200
        dlg = find_dialog(h, main)
        log("dialog", type(dlg).__name__ if dlg else None)
        te = text_edit(dlg)
        te.setPlainText("\n".join(g)); yield 5000
        if i == 0:
            h.capture("addtask", dlg.window() if dlg.window() is not main else main)
        yes = dlg.yesButton
        # 3.5+ uses a PrimarySplitPushButton: the real button is its .button
        h.click(getattr(yes, "button", yes)); yield 800
    b = nav(h, main, "任务列表")
    if b: h.click(b)
    yield 4500
    yield from flip(h, "tasks")
    for p in PAGES:
        b = nav(h, main, p)
        if b:
            h.click(b); yield 1500
            h.capture("page_" + p)
    if hasattr(main, "showInfoMessageBox"):
        h.later(main.showInfoMessageBox); yield 1500
        h.capture("about")
