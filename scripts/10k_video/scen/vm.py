import sys; sys.path.insert(0, __file__.rsplit('/',1)[0])
from common import *
from PySide6.QtWidgets import QDialog, QWidget
SKIP_NAV = {"下载任务", "新建任务", "设置", "资源下载"}

def nav_items(h, main):
    return [w for w in main.findChildren(QWidget) if "NavigationBarPushButton" in type(w).__name__ and w.isVisible()]

def nav(h, main, text):
    for w in nav_items(h, main):
        if w.text() == text:
            return w

def find_dialog(h, main):
    d = getattr(main, "_draftDialog", None) if "_draftDialog" in type(main).__dict__ else None
    if d is not None:
        return d
    for top in [main] + h.tops():
        for w in [top] + top.findChildren(QWidget):
            n = type(w).__name__
            if ("AddTask" in n or "TaskDraftDialog" in n) and w.isVisible():
                return w

def scenario(h, log):
    oobe = None; t = 0
    while t < 25000:
        oobe = h.top("OobeWindow")
        if oobe or h.top("MainWindow"): break
        yield 250; t += 250
    if oobe:
        yield 1500
        h.capture("oobe_welcome", oobe)
        b = h.by_text(oobe, "开始配置")
        if b:
            h.click(b[0]); yield 1200
            h.capture("oobe_basic", oobe)
            h.click(h.by_text(oobe, "上一步")[0]); yield 1200
        h.click(h.by_text(oobe, "跳过全部")[0])
    main = None
    while main is None:
        yield 300
        main = h.top("MainWindow")
    h.main = main
    yield 2500
    main.resize(1120, 740)
    yield 1500
    if hasattr(main, "addUrls"):
        h.later(lambda: main.addUrls(URLS))
    else:
        h.later(lambda: main.showAddTaskDialog(urls=URLS))
    yield 6000
    dlg = find_dialog(h, main)
    log("dialog", type(dlg).__name__)
    h.capture("addtask", dlg.window() if dlg.window() is not main else main)
    if hasattr(dlg, "validate") and hasattr(dlg, "done") and getattr(dlg, "yesButton", None) is None:
        dlg.validate(); yield 300
        h.later(lambda: dlg.done(QDialog.DialogCode.Accepted))
    else:
        h.click(dlg.yesButton)
    yield 4500
    yield from flip(h, "tasks")
    for it in nav_items(h, main):
        log("NAV", it.text())
    b = nav(h, main, "设置")
    if b:
        h.click(b); yield 1800
        h.capture("settings")
    for it in nav_items(h, main):
        if it.text() not in SKIP_NAV:
            h.click(it); yield 1800
            h.capture("page_" + it.text())
