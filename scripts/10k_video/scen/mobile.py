import sys; sys.path.insert(0, __file__.rsplit('/',1)[0])
from common import *
from PySide6.QtWidgets import QDialog

def scenario(h, log):
    w = None
    while w is None:
        yield 300
        w = h.top("MobileMainWindow")
    h.main = w
    w.resize(400, 800)
    yield 2500
    h.capture("empty")
    h.later(w._showAddTaskDialog); yield 800
    w._draftDialog.addUrls(URLS[:5]); yield 5000
    h.capture("addtask")
    dlg = w._draftDialog
    if hasattr(dlg, "validate"):
        dlg.validate(); yield 300
    h.later(lambda: dlg.done(QDialog.DialogCode.Accepted))
    yield 4500
    yield from flip(h, "tasks")
    w.navigationBar.setCurrentIndex(1) if hasattr(w.navigationBar, "setCurrentIndex") else None
    yield 1500
    h.capture("settings")
