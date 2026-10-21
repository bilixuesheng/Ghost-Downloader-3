import sys; sys.path.insert(0, __file__.rsplit('/',1)[0])
import os
from common import flip
URLBASE = "http://dl.example.com/releases/"
NAMES = ["Ghost-Downloader-Setup-x86_64.exe", "ubuntu-24.04.3-desktop-amd64.iso", "Blender-4.5.3-windows-x64.msi",
         "Big_Buck_Bunny_4K_60fps.mp4"]

def scenario(h, log):
    main = None
    while main is None:
        yield 300
        main = h.top("Window")
    h.main = main
    yield 5000
    h.capture("list")
    h.click(main.newDownBtn); yield 1500
    nt = h.top("NewTaskWindow")
    nt.urlEdit.setPlainText("\n".join(URLBASE + n for n in NAMES)); yield 300
    h.click(nt.addTableButton); yield 4000
    h.capture("newtask", nt)
    h.click(nt.addTaskBtn); yield 1500
    for t in h.tops():
        log("TOP", type(t).__name__, t.size())
    h.click(main.downBtn); yield 4500
    yield from flip(h, "down")
    h.click(main.toolsBtn); yield 1500
    h.capture("tools")
    h.click(main.titleBar.setBtn); yield 1500
    sw = h.top("SettingsWindow")
    if sw: h.capture("settings", sw)
