"""render a strip of frames around time T (debug)."""
import sys, os
sys.argv = sys.argv
T0, T1, N, OUT = float(sys.argv[1]), float(sys.argv[2]), int(sys.argv[3]), sys.argv[4]
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import render
from PySide6.QtGui import QGuiApplication, QImage, QPainter
from PySide6.QtCore import QRectF, Qt
app = QGuiApplication.instance() or QGuiApplication([])
cols = 3
w, h = 640, 360
rows = (N + cols - 1) // cols
sheet = QImage(w * cols, h * rows, QImage.Format.Format_RGB32)
sheet.fill(0)
p = QPainter(sheet)
p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
for i in range(N):
    t = T0 + (T1 - T0) * i / max(1, N - 1)
    img = render.render_frame(t)
    p.drawImage(QRectF((i % cols) * w, (i // cols) * h, w, h), img)
    p.setPen(Qt.GlobalColor.yellow)
    p.drawText((i % cols) * w + 8, (i // cols) * h + 18, f"t={t:.2f}")
p.end()
sheet.save(OUT)
