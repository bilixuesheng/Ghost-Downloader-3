import sys; sys.path.insert(0, __file__.rsplit('/',1)[0])
from common import *
from PySide6.QtGui import QPixmap

def scenario(h, log):
    main = None
    while main is None:
        yield 300
        main = h.top("MainWindow")
    h.main = main
    main.resize(1120, 740)
    yield 2500
    h.capture("home")
    from app.common.signal_bus import signalBus
    for name, size, rate in TASKS:
        signalBus.addTaskSignal.emit(url(name), os.path.expanduser("~/Downloads"), 8, name, QPixmap())
    yield 300
    h.click(h.by_text(main, "任务列表")[0]); yield 4500
    yield from flip(h, "tasks")
    h.later(main.showInfoMessageBox); yield 1500
    h.capture("about")
