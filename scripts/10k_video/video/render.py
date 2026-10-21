"""Ghost Downloader 10k-star memorial video renderer.

Composites real captured UI (see tools/gdcap.py) into a 1920x1080 video synced to the song's bar grid:
versions regress from newest to oldest, components morph between versions, captions sit lower-left,
version + stars top-right, and the ending condenses feature keywords into the app icon.

Usage:  python render.py --frames A B --out part.mp4      (render a frame range, video only)
        python render.py --still T --out frame.png        (debug: one frame at time T)
"""
import argparse
import csv
import json
import math
import os
import random
import subprocess
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (QBrush, QColor, QFont, QFontMetricsF, QGuiApplication, QImage, QLinearGradient,
                           QPainter, QPainterPath, QPen, QRadialGradient, QTransform)

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SHOTS = os.path.join(ROOT, "shots")
sys.path.insert(0, HERE)
from scenes import SEGMENTS  # noqa: E402

W, H, FPS = 1920, 1080, 60
TL = json.load(open(os.path.join(ROOT, "data", "timeline.json")))
BEAT, BAR, BAR0 = TL["beat"], TL["bar"], TL["bar0"]
SONG_END = 151.42
GD2_START = TL["segments"][-1]["start"]
ENDING = GD2_START + 2 * BAR          # word-cloud ending starts here
SINK = TL["segments"][15]["start"]     # 124.4s: the music starts sinking
DURATION = 156.0

STARS = {}
for row in csv.DictReader(open(os.path.join(ROOT, "data", "gd3_stars.csv"))):
    STARS[row["Date"]] = int(row["Stars"])
STAR_DATES = sorted(STARS)

CJK = "Noto Sans CJK SC"
LATIN = "Inter Display"


# ---------------------------------------------------------------- helpers
def clamp(x, a=0.0, b=1.0):
    return a if x < a else b if x > b else x


def smooth(a, b, x):
    t = clamp((x - a) / (b - a)) if b != a else (1.0 if x >= b else 0.0)
    return t * t * (3 - 2 * t)


def ease_io(t):
    t = clamp(t)
    return 4 * t * t * t if t < 0.5 else 1 - (-2 * t + 2) ** 3 / 2


def ease_out(t):
    t = clamp(t)
    return 1 - (1 - t) ** 3


def lerp(a, b, t):
    return a + (b - a) * t


def lerp_rect(a, b, t):
    return QRectF(lerp(a.x(), b.x(), t), lerp(a.y(), b.y(), t), lerp(a.width(), b.width(), t),
                  lerp(a.height(), b.height(), t))


def font(family, px, bold=False, italic=False, weight=None):
    f = QFont(family)
    f.setPixelSize(int(px))
    if weight is not None:
        f.setWeight(weight)
    elif bold:
        f.setBold(True)
    f.setItalic(italic)
    f.setHintingPreference(QFont.HintingPreference.PreferNoHinting)
    return f


def fmt_int(n):
    return f"{int(round(n)):,}"


def bar_time(n):
    return BAR0 + n * BAR


# ---------------------------------------------------------------- captured states
class Comp:
    __slots__ = ("key", "kind", "rect", "img", "z", "text")


class State:
    """One captured screen: full image, plate, components (all in 2x pixels; rects in logical px)."""

    def __init__(self, d, name):
        self.dir, self.name = d, name
        base = os.path.join(SHOTS, d)
        self.full_path = os.path.join(base, name + ".png")
        self.size = None
        self._full = None
        self._plate = None
        self._comps = None
        meta = os.path.join(base, name + ".json")
        if os.path.exists(meta):
            m = json.load(open(meta, encoding="utf-8"))
            self.size = m["size"]
        cj = os.path.join(base, name + "_c", "comps.json")
        self.has_comps = os.path.exists(cj)

    def full(self):
        if self._full is None:
            self._full = QImage(self.full_path).convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
            if self.size is None:
                self.size = [self._full.width() // 2, self._full.height() // 2]
        return self._full

    def plate(self):
        if self._plate is None:
            p = os.path.join(SHOTS, self.dir, self.name + "_plate.png")
            self._plate = QImage(p).convertToFormat(QImage.Format.Format_ARGB32_Premultiplied) \
                if os.path.exists(p) else self.full()
        return self._plate

    def comps(self):
        if self._comps is None:
            self._comps = []
            if self.has_comps:
                base = os.path.join(SHOTS, self.dir, self.name + "_c")
                meta = json.load(open(os.path.join(base, "comps.json"), encoding="utf-8"))
                n = max(1, len(meta["comps"]))
                seen = {}
                for c in sorted(meta["comps"], key=lambda c: c["i"]):
                    k = make_key(c)
                    seen[k] = seen.get(k, 0) + 1
                    o = Comp()
                    o.key = f"{k}#{seen[k]}"
                    o.kind = c["kind"]
                    o.text = c["text"]
                    o.rect = QRectF(*c["rect"])
                    o.img = QImage(os.path.join(base, c["file"])).convertToFormat(
                        QImage.Format.Format_ARGB32_Premultiplied)
                    o.z = c["i"] / n
                    self._comps.append(o)
        return self._comps

    def drop(self):
        self._full = self._plate = self._comps = None


BTN_ALIASES = ("PushButton", "ToolButton")


def make_key(c):
    k, t, cls = c["kind"], c["text"].strip(), c["cls"]
    if k == "titlebar":
        return "titlebar"
    if k == "dialog":
        return "dialog"
    if k in ("nav", "card", "lbl", "edit", "btn") and t:
        return f"{k}:{t[:24]}"
    return f"{k}:{cls}:{c.get('obj', '')}"


_STATES = {}


def state(d, name):
    key = (d, name)
    if key not in _STATES:
        _STATES[key] = State(d, name)
    return _STATES[key]


def flip_frames(d, base):
    out = []
    i = 0
    while os.path.exists(os.path.join(SHOTS, d, f"{base}_f{i:02d}.png")):
        out.append(f"{base}_f{i:02d}")
        i += 1
    return out


# ---------------------------------------------------------------- shot plan
class Shot:
    def __init__(self, seg, sdef, t0, t1):
        self.seg, self.t0, self.t1 = seg, t0, t1
        self.dir = sdef["dir"]
        name = sdef["name"]
        self.flip = name.endswith("*")
        if self.flip:
            self.frames = flip_frames(self.dir, name[:-1]) or [name[:-1]]
        else:
            self.frames = [name]
        self.place = sdef.get("place")

    def frame_at(self, t):
        """flipbook frame shown at time t: the app refreshes about every two beats."""
        if len(self.frames) == 1:
            return state(self.dir, self.frames[0])
        steps = max(1, int(round((self.t1 - self.t0) / (2 * BEAT))))
        k = clamp(int((t - self.t0) / (2 * BEAT)), 0, steps - 1)
        idx = round(k * (len(self.frames) - 1) / max(1, steps - 1))
        return state(self.dir, self.frames[int(idx)])

    def first(self):
        return state(self.dir, self.frames[0])

    def last(self):
        return state(self.dir, self.frames[-1])


def build_shots():
    shots = []
    segs = TL["segments"]
    for i, seg in enumerate(SEGMENTS):
        t0 = segs[i]["start"]
        t1 = segs[i + 1]["start"] if i + 1 < len(segs) else ENDING
        seg_bars = round((t1 - t0) / BAR)
        defs = seg["shots"]
        for j, sd in enumerate(defs):
            a = t0 + sd.get("at", 0) * BAR
            b = t0 + defs[j + 1].get("at", 0) * BAR if j + 1 < len(defs) else t1
            if j + 1 == len(defs) and seg_bars <= 0:
                b = t1
            shots.append(Shot(i, sd, a, b))
    return shots


SHOT_LIST = build_shots()


# ---------------------------------------------------------------- layout
WIN_SCALE = 1.03          # video px per logical px for the desktop window
WIN_RIGHT = 1858
WIN_CENTER_Y = 584


def window_rect(st, place=None, t=0.0):
    w, h = st.size if st.size else (1120, 740)
    s = WIN_SCALE
    if place == "with_phone":
        s *= 0.8
    if w <= 620:          # GD2 is a 600x600 window
        s *= 1.12
    ww, hh = w * s, h * s
    cx = WIN_RIGHT - 1120 * WIN_SCALE / 2
    if place == "with_phone":
        cx += 108
    x = cx - ww / 2
    y = WIN_CENTER_Y - hh / 2
    # sinking: after 124.4s windows slowly drift down and shrink as the song fades
    if t > SINK:
        k = smooth(SINK, ENDING, t)
        y += 46 * k
    return QRectF(x, y, ww, hh)


PHONE_RECT = QRectF(712, 330, 320, 640)


# ---------------------------------------------------------------- background
ERA_COLORS = {          # (top, bottom, glow)
    2026: ("#0b1430", "#1d2f73", "#4a7dff"),
    2025: ("#081a2a", "#13456b", "#2fb8d6"),
    2024: ("#120d2a", "#33246b", "#9b6bff"),
    2023: ("#1a120a", "#4a3313", "#ffb347"),
    2022: ("#1f0a1c", "#5a1d4f", "#ff4fa8"),
}


def mix_color(a, b, t):
    a, b = QColor(a), QColor(b)
    return QColor(int(lerp(a.red(), b.red(), t)), int(lerp(a.green(), b.green(), t)),
                  int(lerp(a.blue(), b.blue(), t)), int(lerp(a.alpha(), b.alpha(), t)))


def era_of_segment(i):
    d = TL["segments"][i]["date"]
    return int(d[:4])


def era_colors(t):
    segs = TL["segments"]
    i = seg_index(t)
    cur = ERA_COLORS[era_of_segment(i)]
    if i + 1 < len(segs):
        nxt = ERA_COLORS[era_of_segment(i + 1)]
        k = smooth(segs[i + 1]["start"] - 0.6, segs[i + 1]["start"] + 0.4, t)
        return [mix_color(a, b, k) for a, b in zip(cur, nxt)]
    return [QColor(c) for c in cur]


def seg_index(t):
    segs = TL["segments"]
    i = 0
    for j, s in enumerate(segs):
        if t >= s["start"] - 1e-6:
            i = j
    return i


random.seed(7)
PARTICLES = [(random.random(), random.random(), random.uniform(0.6, 2.4), random.uniform(0.15, 0.6),
              random.uniform(0, 6.28)) for _ in range(90)]


def draw_background(p, t, cols=None, darken=0.0):
    top, bot, glow = cols or era_colors(t)
    g = QLinearGradient(0, 0, 0, H)
    g.setColorAt(0, top)
    g.setColorAt(1, bot)
    p.fillRect(0, 0, W, H, g)
    # two slow glow blobs
    for k, (bx, by, r, ph) in enumerate(((0.78, 0.35, 900, 0.0), (0.18, 0.8, 760, 2.1))):
        cx = W * bx + 120 * math.sin(t * 0.21 + ph)
        cy = H * by + 80 * math.cos(t * 0.17 + ph)
        rg = QRadialGradient(cx, cy, r)
        c = QColor(glow)
        c.setAlpha(70 if k == 0 else 45)
        rg.setColorAt(0, c)
        c2 = QColor(glow)
        c2.setAlpha(0)
        rg.setColorAt(1, c2)
        p.fillRect(0, 0, W, H, rg)
    # drifting dust (falls slowly once the song starts sinking)
    sink = smooth(SINK - 2, ENDING, t)
    p.setPen(Qt.PenStyle.NoPen)
    for (x0, y0, sz, a, ph) in PARTICLES:
        x = (x0 * W + 18 * math.sin(t * 0.3 + ph)) % W
        y = (y0 * H - t * 9 * (1 - sink) + t * 14 * sink) % H
        c = QColor(255, 255, 255, int(255 * a * 0.35))
        p.setBrush(c)
        p.drawEllipse(QPointF(x, y), sz, sz)
    # vignette + sinking darkness
    vg = QRadialGradient(W * 0.55, H * 0.5, W * 0.75)
    vg.setColorAt(0.55, QColor(0, 0, 0, 0))
    vg.setColorAt(1.0, QColor(0, 0, 0, 150))
    p.fillRect(0, 0, W, H, vg)
    dk = darken + 0.35 * sink
    if dk > 0:
        p.fillRect(0, 0, W, H, QColor(0, 0, 0, int(255 * clamp(dk))))


# ---------------------------------------------------------------- window drawing
def rounded(rect, r=9.0):
    path = QPainterPath()
    path.addRoundedRect(rect, r, r)
    return path


def draw_shadow(p, rect, alpha=1.0, radius=10):
    for i in range(14, 0, -1):
        k = i / 14
        grow = 34 * k
        c = QColor(0, 0, 0, int(26 * (1 - k) * alpha))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(c)
        p.drawRoundedRect(rect.adjusted(-grow, -grow * 0.6, grow, grow * 1.3), radius + grow, radius + grow)


def acrylic_under(p, rect, t, alpha=1.0):
    """GD2 relied on the Windows acrylic blur: approximate with a bright frosted panel."""
    p.save()
    p.setClipPath(rounded(rect, 4))
    top, bot, glow = era_colors(t)
    g = QLinearGradient(rect.topLeft(), rect.bottomRight())
    g.setColorAt(0, mix_color(top, "#ffffff", 0.78))
    g.setColorAt(1, mix_color(glow, "#ffffff", 0.72))
    p.setOpacity(alpha)
    p.fillRect(rect, g)
    p.restore()


def draw_window_image(p, img, rect, opacity=1.0, gd2=False, t=0.0, frame=True):
    if opacity <= 0.003:
        return
    p.save()
    if frame:
        draw_shadow(p, rect, opacity)
    if gd2:
        acrylic_under(p, rect, t, opacity)
    p.setClipPath(rounded(rect, 4 if gd2 else 9))
    p.setOpacity(opacity)
    p.drawImage(rect, img)
    p.restore()
    if frame and not gd2:
        p.save()
        p.setOpacity(opacity * 0.5)
        p.setPen(QPen(QColor(255, 255, 255, 60), 1.0))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(rect.adjusted(0.5, 0.5, -0.5, -0.5), 9, 9)
        p.restore()


def map_rect(r, st, wrect):
    sx = wrect.width() / st.size[0]
    sy = wrect.height() / st.size[1]
    return QRectF(wrect.x() + r.x() * sx, wrect.y() + r.y() * sy, r.width() * sx, r.height() * sy)


def match_comps(A, B):
    """pair components of two states: same key first, then cards by common filename prefix."""
    bmap = {}
    for c in B:
        bmap.setdefault(c.key, c)
    pairs, used_b, a_only = [], set(), []
    for c in A:
        m = bmap.get(c.key)
        if m is not None and id(m) not in used_b:
            pairs.append((c, m))
            used_b.add(id(m))
        else:
            a_only.append(c)
    rest_a = []
    for c in a_only:
        best = None
        if c.kind in ("card", "lbl") and len(c.text) >= 6:
            for m in B:
                if id(m) in used_b or m.kind != c.kind or len(m.text) < 6:
                    continue
                n = 0
                for x, y in zip(c.text, m.text):
                    if x != y:
                        break
                    n += 1
                if n >= 8 and (best is None or n > best[0]):
                    best = (n, m)
        if best:
            pairs.append((c, best[1]))
            used_b.add(id(best[1]))
        else:
            rest_a.append(c)
    b_only = [c for c in B if id(c) not in used_b]
    return pairs, rest_a, b_only


def draw_morph(p, A, B, ra, rb, k, t, gd2a=False, gd2b=False):
    """component morph from state A (in window rect ra) to state B (in rb) at progress k."""
    wr = lerp_rect(ra, rb, k)
    draw_shadow(p, wr, 1.0)
    if gd2a or gd2b:
        acrylic_under(p, wr, t, (1 - k) if gd2a and not gd2b else k if gd2b and not gd2a else 1)
    p.save()
    p.setClipPath(rounded(wr, 9))
    pa, pb = A.plate(), B.plate()
    # outgoing plate stays opaque underneath so the dark background never bleeds through,
    # unless the incoming window is see-through (GD2's acrylic)
    p.setOpacity(1.0 - smooth(0.15, 0.85, k) if gd2b and not gd2a else 1.0)
    p.drawImage(wr, pa)
    p.setOpacity(smooth(0.15, 0.85, k))
    p.drawImage(wr, pb)
    pairs, a_only, b_only = match_comps(A.comps(), B.comps())
    items = []
    for c in a_only:
        items.append((c.z, 0, c, None))
    for a, b in pairs:
        items.append((lerp(a.z, b.z, k), 1, a, b))
    for c in b_only:
        items.append((c.z, 2, c, None))
    items.sort(key=lambda x: x[0])
    for _, typ, c, d in items:
        if typ == 0:
            o = 1 - smooth(0.0, 0.62, k)
            if o <= 0:
                continue
            r = map_rect(c.rect, A, ra)
            s = lerp(1.0, 0.94, ease_out(k))
            r = QRectF(r.center().x() - r.width() * s / 2, r.center().y() - r.height() * s / 2 - 10 * k,
                       r.width() * s, r.height() * s)
            p.setOpacity(o)
            p.drawImage(r, c.img)
        elif typ == 2:
            o = smooth(0.3, 0.95, k)
            if o <= 0:
                continue
            r = map_rect(c.rect, B, rb)
            e = ease_out(smooth(0.3, 1.0, k))
            s = lerp(0.94, 1.0, e)
            r = QRectF(r.center().x() - r.width() * s / 2, r.center().y() - r.height() * s / 2 + 12 * (1 - e),
                       r.width() * s, r.height() * s)
            p.setOpacity(o)
            p.drawImage(r, c.img)
        else:
            r = lerp_rect(map_rect(c.rect, A, ra), map_rect(d.rect, B, rb), k)
            q = smooth(0.3, 0.7, k)
            a_op = 1 - smooth(0.6, 1.0, q)
            if a_op > 0:
                p.setOpacity(a_op)
                p.drawImage(r, c.img)
            if q > 0:
                p.setOpacity(q)
                p.drawImage(r, d.img)
    p.restore()


# ---------------------------------------------------------------- overlays
def seg_info(i):
    seg = SEGMENTS[i]
    meta = TL["segments"][i]
    return seg, meta


def stars_at(i):
    v = TL["segments"][i]["stars"]
    return v if v is not None else 0


def star_value(t):
    """star counter rolls toward each version's count around its boundary."""
    segs = TL["segments"]
    i = seg_index(t)
    cur = stars_at(i)
    prev = stars_at(i - 1) if i > 0 else 10139
    k = ease_out(clamp((t - (segs[i]["start"] - 0.25)) / 0.75))
    return lerp(prev, cur, k)


def draw_text(p, x, y, text, f, color, align_right=False, shadow=True, opacity=1.0):
    fm = QFontMetricsF(f)
    w = fm.horizontalAdvance(text)
    if align_right:
        x -= w
    p.save()
    p.setFont(f)
    p.setOpacity(opacity)
    if shadow:
        p.setPen(QColor(0, 0, 0, 110))
        p.drawText(QPointF(x + 1.5, y + 2.5), text)
    p.setPen(color)
    p.drawText(QPointF(x, y), text)
    p.restore()
    return w


def draw_version_label(p, t):
    segs = TL["segments"]
    i = seg_index(t)
    tb = segs[i]["start"]
    k_in = ease_out(clamp((t - (tb - 0.18)) / 0.45))
    fade_out = 1 - smooth(ENDING - 0.2, ENDING + 0.5, t)
    for idx, k, direction in ((i - 1, 1 - k_in, -1), (i, k_in, 1)):
        if idx < 0 or k <= 0.01:
            continue
        seg, meta = seg_info(idx)
        dy = (1 - k) * 26 * direction
        op = k * fade_out
        is_gd2 = seg.get("gd2")
        name = "Ghost Downloader 2" if is_gd2 else "Ghost Downloader 3"
        draw_text(p, 1860, 58 + dy, name, font(LATIN, 22, weight=QFont.Weight.Medium),
                  QColor(220, 228, 255, 200), True, opacity=op)
        draw_text(p, 1860, 124 + dy, seg["label"], font(LATIN, 66, weight=QFont.Weight.Bold),
                  QColor(255, 255, 255), True, opacity=op)
    # star line (rolling counter) + date
    seg, meta = seg_info(i)
    date = meta["date"].replace("-", ".")
    op = fade_out * smooth(5.6, 6.2, t)
    if seg.get("gd2"):
        line = f"GD3 尚未诞生 · {date}"
        draw_text(p, 1860, 168, line, font(CJK, 26), QColor(230, 236, 255, 220), True, opacity=op)
        return
    sv = star_value(t)
    f_star = font(LATIN, 34, weight=QFont.Weight.DemiBold)
    f_date = font(LATIN, 24)
    wdate = QFontMetricsF(f_date).horizontalAdvance("  ·  " + date)
    draw_text(p, 1860, 168, "  ·  " + date, f_date, QColor(210, 220, 250, 210), True, opacity=op)
    num = fmt_int(sv)
    wnum = draw_text(p, 1860 - wdate, 168, num, f_star, QColor(255, 255, 255), True, opacity=op)
    draw_star(p, QPointF(1860 - wdate - wnum - 24, 156), 15, QColor(255, 205, 64), op)


def star_path(c, r):
    path = QPainterPath()
    for k in range(10):
        a = -math.pi / 2 + k * math.pi / 5
        rr = r if k % 2 == 0 else r * 0.45
        pt = QPointF(c.x() + rr * math.cos(a), c.y() + rr * math.sin(a))
        if k == 0:
            path.moveTo(pt)
        else:
            path.lineTo(pt)
    path.closeSubpath()
    return path


def draw_star(p, c, r, color, op=1.0):
    p.save()
    p.setOpacity(op)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(color)
    p.drawPath(star_path(c, r))
    p.restore()


def wrap(text, f, maxw):
    fm = QFontMetricsF(f)
    lines, cur = [], ""
    for ch in text:
        if fm.horizontalAdvance(cur + ch) > maxw and cur:
            lines.append(cur)
            cur = ch.lstrip()
        else:
            cur += ch
    if cur:
        lines.append(cur)
    return lines


def draw_caption(p, t):
    segs = TL["segments"]
    i = seg_index(t)
    if t < segs[0]["start"] - 0.1 or t > ENDING + 0.6:
        return
    seg, meta = seg_info(i)
    t0 = segs[i]["start"]
    t1 = segs[i + 1]["start"] if i + 1 < len(segs) else ENDING
    x0, ybot, maxw = 74, 936, 600
    f_title = font(CJK, 46, bold=True, italic=True)
    f_line = font(CJK, 25, italic=True)
    rows = []
    for ln in seg["lines"]:
        rows.extend(wrap(ln, f_line, maxw))
    title_rows = wrap(seg["title"], f_title, maxw)
    total_h = len(title_rows) * 60 + 18 + len(rows) * 38
    y = ybot - total_h
    out = smooth(t1 - 0.32, t1 - 0.02, t)
    # accent bar
    top, bot, glow = era_colors(t)
    a_in = ease_out(clamp((t - t0 - 0.05) / 0.45))
    p.save()
    p.setOpacity(a_in * (1 - out))
    p.fillRect(QRectF(x0 - 22, y + 6, 4, total_h - 6), glow)
    p.restore()
    for j, row in enumerate(title_rows):
        k = ease_out(clamp((t - t0 - 0.05 - 0.06 * j) / 0.5))
        dx = (1 - k) * -36 - out * 30
        draw_text(p, x0 + dx, y + 48 + j * 60, row, f_title, QColor(255, 255, 255), opacity=k * (1 - out))
    y += len(title_rows) * 60 + 18
    for j, row in enumerate(rows):
        k = ease_out(clamp((t - t0 - 0.22 - 0.09 * j) / 0.5))
        dx = (1 - k) * -28 - out * 24
        draw_text(p, x0 + dx, y + 28 + j * 38, row, f_line, QColor(222, 230, 252), opacity=k * (1 - out))


# star-history mini chart (upper left), the dot follows the version being shown
CHART = QRectF(74, 250, 520, 250)
CHART_T0, CHART_T1 = "2024-08-03", "2026-10-21"


def date_x(d):
    from datetime import date
    a = date.fromisoformat(CHART_T0)
    b = date.fromisoformat(CHART_T1)
    x = date.fromisoformat(d)
    return CHART.x() + CHART.width() * clamp((x - a).days / (b - a).days)


def star_y(v):
    return CHART.bottom() - CHART.height() * v / 10500


_CHART_PATH = None


def chart_path():
    global _CHART_PATH
    if _CHART_PATH is None:
        path = QPainterPath()
        for j, d in enumerate(STAR_DATES):
            pt = QPointF(date_x(d), star_y(STARS[d]))
            path.moveTo(pt) if j == 0 else path.lineTo(pt)
        _CHART_PATH = path
    return _CHART_PATH


def current_date_float(t):
    """chart cursor date as fraction along the chart, rolling back with the versions."""
    from datetime import date
    segs = TL["segments"]
    i = seg_index(t)
    a = date.fromisoformat(CHART_T0)
    b = date.fromisoformat(CHART_T1)

    def frac(d):
        return clamp((date.fromisoformat(d) - a).days / (b - a).days, -0.08, 1)

    cur = frac(segs[i]["date"])
    prev = frac(segs[i - 1]["date"]) if i > 0 else 1.0
    k = ease_out(clamp((t - (segs[i]["start"] - 0.25)) / 0.75))
    return lerp(prev, cur, k)


def draw_chart(p, t):
    op = smooth(5.7, 6.6, t) * (1 - smooth(GD2_START - 6.5, GD2_START - 3, t))
    if op <= 0:
        return
    p.save()
    p.setOpacity(op)
    f = font(CJK, 20)
    draw_text(p, CHART.x(), CHART.y() - 18, "Star History", font(LATIN, 22, weight=QFont.Weight.DemiBold),
              QColor(225, 232, 255), shadow=False, opacity=op * 0.9)
    pen = QPen(QColor(255, 255, 255, 34), 1)
    p.setPen(pen)
    for v in (2500, 5000, 7500, 10000):
        y = star_y(v)
        p.drawLine(QPointF(CHART.x(), y), QPointF(CHART.right(), y))
        draw_text(p, CHART.right() + 8, y + 6, f"{v // 1000 if v % 1000 == 0 else v / 1000}k", f,
                  QColor(255, 255, 255, 110), shadow=False, opacity=op)
    fr = current_date_float(t)
    cut = CHART.x() + CHART.width() * clamp(fr)
    # faint full curve, bright up to the cursor
    p.setPen(QPen(QColor(255, 255, 255, 50), 2))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawPath(chart_path())
    p.save()
    p.setClipRect(QRectF(CHART.x() - 4, CHART.y() - 20, cut - CHART.x() + 4, CHART.height() + 40))
    top, bot, glow = era_colors(t)
    p.setPen(QPen(QColor(255, 214, 92), 3))
    p.drawPath(chart_path())
    p.restore()
    if fr >= 0:
        sv = star_value(t)
        c = QPointF(cut, star_y(sv))
        p.setPen(Qt.PenStyle.NoPen)
        for rr, a in ((16, 40), (10, 80)):
            p.setBrush(QColor(255, 214, 92, a))
            p.drawEllipse(c, rr, rr)
        p.setBrush(QColor(255, 240, 200))
        p.drawEllipse(c, 5, 5)
    for d, lab in (("2024-08-03", "2024.08"), ("2025-05-20", "2025.05"), ("2026-07-16", "2026.07")):
        x = date_x(d)
        draw_text(p, x - 24, CHART.bottom() + 26, lab, font(LATIN, 17), QColor(255, 255, 255, 110),
                  shadow=False, opacity=op)
    p.restore()


# ---------------------------------------------------------------- phone
def draw_phone(p, img, rect, op=1.0):
    if op <= 0:
        return
    p.save()
    p.setOpacity(op)
    draw_shadow(p, rect, op, 40)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(18, 18, 22))
    p.drawRoundedRect(rect, 44, 44)
    inner = rect.adjusted(11, 11, -11, -11)
    p.setClipPath(rounded(inner, 34))
    p.drawImage(inner, img)
    p.setClipping(False)
    p.setBrush(QColor(18, 18, 22))
    p.drawRoundedRect(QRectF(rect.center().x() - 46, inner.y() + 6, 92, 22), 11, 11)
    p.restore()


# ---------------------------------------------------------------- intro & ending
LOGO = QImage(os.environ.get("GDV_LOGO") or os.path.join(ROOT, "..", "..", "app", "assets", "logo.png")).convertToFormat(
    QImage.Format.Format_ARGB32_Premultiplied)
INTRO_KICKS = [0.029, 0.36, 0.694, 1.019, 1.35, 1.679, 2.01, 2.341, 2.634, 2.943, 3.287, 4.124, 4.455,
               4.785, 5.066, 5.39, 5.786]


def kick_pulse(t, kicks, width=0.18):
    v = 0.0
    for k in kicks:
        if k <= t < k + width * 3:
            v = max(v, math.exp(-(t - k) / width))
    return v


def draw_intro(p, t):
    t_imp = BAR0
    if t > t_imp + 0.8:
        return
    out = smooth(t_imp - 0.05, t_imp + 0.5, t)
    fade_in = smooth(0.0, 0.8, t)
    op = fade_in * (1 - out)
    if op <= 0:
        return
    pulse = kick_pulse(t, INTRO_KICKS)
    cx, cy = W / 2, H / 2 - 70
    s = (180 + 10 * pulse) * (1 + 0.6 * ease_io(out))
    p.save()
    p.setOpacity(op)
    rg = QRadialGradient(cx, cy, 420)
    rg.setColorAt(0, QColor(110, 150, 255, int(90 + 60 * pulse)))
    rg.setColorAt(1, QColor(110, 150, 255, 0))
    p.fillRect(0, 0, W, H, rg)
    p.drawImage(QRectF(cx - s / 2, cy - s / 2, s, s), LOGO)
    p.restore()
    f = font(LATIN, 62, weight=QFont.Weight.Bold)
    draw_text(p, cx - QFontMetricsF(f).horizontalAdvance("Ghost Downloader") / 2, cy + 175, "Ghost Downloader",
              f, QColor(255, 255, 255), opacity=op * smooth(0.6, 1.6, t))
    # star counter racing toward 10,000 with the riser
    k = ease_io(clamp((t - 1.2) / (t_imp - 0.35 - 1.2)))
    n = 10000 * (k ** 1.6)
    txt = fmt_int(n)
    f2 = font(LATIN, 88, weight=QFont.Weight.Black)
    tw = QFontMetricsF(f2).horizontalAdvance(txt)
    x = cx - (tw + 70) / 2 + 70
    o2 = op * smooth(1.0, 1.8, t)
    draw_star(p, QPointF(x - 46, cy + 262), 30, QColor(255, 205, 64), o2)
    draw_text(p, x, cy + 295, txt, f2, QColor(255, 255, 255), opacity=o2)
    f3 = font(CJK, 30)
    sub = "感谢每一颗 Star · 回到最初"
    draw_text(p, cx - QFontMetricsF(f3).horizontalAdvance(sub) / 2, cy + 352, sub, f3, QColor(220, 228, 255),
              opacity=op * smooth(3.3, 4.2, t))


KEYWORDS = ["多线程", "断点续传", "跨平台", "开源", "免费", "无广告", "256 线程", "AI 加速", "浏览器扩展", "BitTorrent",
            "磁力链接", "M3U8", "eD2k", "FTP", "YouTube", "Bilibili", "GitHub 加速", "HuggingFace", "Aria2 RPC",
            "自动分类", "计划任务", "下载限速", "增量更新", "功能包", "Fluent Design", "Android", "macOS", "Linux",
            "ghd 命令行", "多语言", "文件校验", "拖拽下载", "剪贴板监听", "Mica", "分段进度条", "首次启动引导", "统一搜索",
            "直播录制", "TLS 指纹", "任务队列", "托盘", "满速", "持续更新", "Windows"]
random.seed(42)
KW = []
N = len(KEYWORDS)
for j, word in enumerate(KEYWORDS):
    y = 1 - (j + 0.5) / N * 2
    r = math.sqrt(1 - y * y)
    th = j * math.pi * (3 - math.sqrt(5))
    sphere = (r * math.cos(th), y, r * math.sin(th))
    start = (random.uniform(-1.6, 1.6), random.uniform(-0.95, 0.95), random.uniform(-1.2, 1.4))
    big = random.random() < 0.3
    KW.append((word, sphere, start, big))


def draw_ending(p, t):
    T0 = ENDING
    if t < T0 - 0.6:
        return
    cx, cy = W / 2, H / 2 - 40
    # keywords: scattered -> sphere -> shrink into the icon tile
    gather = ease_io(clamp((t - T0) / 1.7))
    rot = (t - T0) * 1.15
    shrink = ease_io(clamp((t - (T0 + 1.9)) / 1.2))
    radius = lerp(330, 70, shrink)
    kw_op = smooth(T0 - 0.4, T0 + 0.4, t) * (1 - smooth(T0 + 2.6, T0 + 3.15, t))
    tile_k = ease_out(clamp((t - (T0 + 2.4)) / 0.6))
    logo_k = ease_out(clamp((t - (T0 + 2.75)) / 0.6))
    if kw_op > 0:
        items = []
        for word, (sx, sy, sz), (ax, ay, az), big in KW:
            ca, sa = math.cos(rot), math.sin(rot)
            rx, rz = sx * ca + sz * sa, -sx * sa + sz * ca
            px = lerp(ax * 700, rx * radius, gather)
            py = lerp(ay * 430, sy * radius, gather)
            pz = lerp(az * 600, rz * radius, gather)
            persp = 900 / (900 + pz)
            items.append((pz, word, px * persp, py * persp, persp, big))
        items.sort(key=lambda x: -x[0])
        for pz, word, x, y, persp, big in items:
            size = (34 if big else 22) * persp * lerp(1.0, 0.55, shrink)
            depth_a = clamp(lerp(1.0, 0.25, (pz + 400) / 1000))
            f = font(CJK, max(8, size), bold=big)
            w = QFontMetricsF(f).horizontalAdvance(word)
            draw_text(p, cx + x - w / 2, cy + y + size * 0.35, word, f, QColor(235, 240, 255),
                      shadow=False, opacity=kw_op * depth_a)
    # frosted tile becoming the app icon
    if tile_k > 0:
        s = lerp(260, 200, logo_k)
        rect = QRectF(cx - s / 2, cy - s / 2, s, s)
        p.save()
        p.setOpacity(tile_k * (1 - logo_k * 0.85))
        p.setPen(QPen(QColor(255, 255, 255, 120), 2))
        p.setBrush(QColor(200, 215, 255, 60))
        p.drawRoundedRect(rect, s * 0.24, s * 0.24)
        p.restore()
    if logo_k > 0:
        s = 200
        glow = QRadialGradient(cx, cy, 380)
        glow.setColorAt(0, QColor(140, 170, 255, int(110 * logo_k)))
        glow.setColorAt(1, QColor(140, 170, 255, 0))
        p.fillRect(0, 0, W, H, glow)
        p.save()
        p.setOpacity(logo_k)
        p.drawImage(QRectF(cx - s / 2, cy - s / 2, s, s), LOGO)
        p.restore()
    # title and lines
    f1 = font(LATIN, 54, weight=QFont.Weight.Bold)
    k1 = ease_out(clamp((t - (T0 + 3.5)) / 0.7))
    title = "Ghost Downloader"
    draw_text(p, cx - QFontMetricsF(f1).horizontalAdvance(title) / 2, cy + 170 + (1 - k1) * 14, title, f1,
              QColor(255, 255, 255), opacity=k1)
    k2 = ease_out(clamp((t - (T0 + 4.3)) / 0.7))
    f2 = font(LATIN, 24)
    line = "Available at   GitCode   ·   GitHub   ·   https://gd.xychr.com"
    draw_text(p, cx - QFontMetricsF(f2).horizontalAdvance(line) / 2, cy + 222, line, f2, QColor(215, 224, 250),
              opacity=k2)
    k3 = ease_out(clamp((t - (T0 + 5.0)) / 0.7))
    f3 = font(LATIN, 26, weight=QFont.Weight.DemiBold)
    s3 = "10K Stars on GitHub"
    w3 = QFontMetricsF(f3).horizontalAdvance(s3)
    draw_star(p, QPointF(cx - w3 / 2 - 22, cy + 262), 12, QColor(255, 205, 64), k3)
    draw_text(p, cx - w3 / 2 + 4, cy + 271, s3, f3, QColor(255, 236, 190), opacity=k3)
    f4 = font(CJK, 24)
    s4 = "谢谢你，陪 Ghost Downloader 走到一万颗星"
    draw_text(p, cx - QFontMetricsF(f4).horizontalAdvance(s4) / 2, cy + 328, s4, f4, QColor(200, 210, 240),
              opacity=ease_out(clamp((t - (T0 + 5.7)) / 0.8)))


# ---------------------------------------------------------------- main frame
def current_shot(t):
    cur = SHOT_LIST[0]
    for s in SHOT_LIST:
        if t >= s.t0 - 1e-6:
            cur = s
    return cur


TRANS = 0.58   # transition length (s), centred slightly before the bar line


def draw_app(p, t):
    if t < BAR0 - 0.3:
        return
    idx = SHOT_LIST.index(current_shot(t))
    shot = SHOT_LIST[idx]
    nxt = SHOT_LIST[idx + 1] if idx + 1 < len(SHOT_LIST) else None
    prev = SHOT_LIST[idx - 1] if idx > 0 else None
    seg = SEGMENTS[shot.seg]
    gd2 = bool(seg.get("gd2"))
    # entering from the previous shot?
    tr_a, tr_b = -0.36, TRANS - 0.36
    morph = None
    if nxt and t >= nxt.t0 + tr_a:
        morph = (shot, nxt, (t - (nxt.t0 + tr_a)) / TRANS)
    elif prev and t < shot.t0 + tr_b:
        morph = (prev, shot, (t - (shot.t0 + tr_a)) / TRANS)
    # very first appearance: slam in on the intro impact
    if idx == 0 and t < BAR0 + 0.6:
        k = ease_out(clamp((t - (BAR0 - 0.12)) / 0.55))
        st = shot.first()
        r = window_rect(st, shot.place, t)
        sc = lerp(1.12, 1.0, k)
        r = QRectF(r.center().x() - r.width() * sc / 2, r.center().y() - r.height() * sc / 2,
                   r.width() * sc, r.height() * sc)
        draw_window_image(p, st.full(), r, k)
        return
    # ending: GD2 window recedes into the past
    if t >= ENDING - 0.2:
        k = ease_io(clamp((t - (ENDING - 0.2)) / 1.4))
        st = shot.frame_at(t)
        r = window_rect(st, shot.place, t)
        sc = lerp(1.0, 0.25, k)
        r = QRectF(r.center().x() * (1 - k) + W / 2 * k - r.width() * sc / 2,
                   r.center().y() * (1 - k) + (H / 2 - 40) * k - r.height() * sc / 2, r.width() * sc,
                   r.height() * sc)
        draw_window_image(p, st.full(), r, 1 - k, gd2=True, t=t)
        return
    if morph:
        a_shot, b_shot, k = morph
        k = ease_io(k)
        A, B = a_shot.last(), b_shot.first()
        ra = window_rect(A, a_shot.place, t)
        rb = window_rect(B, b_shot.place, t)
        ga = bool(SEGMENTS[a_shot.seg].get("gd2"))
        gb = bool(SEGMENTS[b_shot.seg].get("gd2"))
        if A.has_comps and B.has_comps:
            draw_morph(p, A, B, ra, rb, k, t, ga, gb)
        else:
            draw_window_image(p, A.full(), lerp_rect(ra, rb, k), 1 - smooth(0.2, 0.8, k), ga, t)
            draw_window_image(p, B.full(), lerp_rect(ra, rb, k), smooth(0.2, 0.8, k), gb, t)
    else:
        st = shot.frame_at(t)
        r = window_rect(st, shot.place, t)
        # slow push-in + beat pulse keep held shots alive
        u = clamp((t - shot.t0) / max(0.1, shot.t1 - shot.t0))
        beat_phase = ((t - BAR0) / BEAT) % 1.0
        pulse = 0.004 * math.exp(-beat_phase * 6) if t > BAR0 else 0
        sc = 1.0 + 0.018 * ease_io(u) + pulse
        r = QRectF(r.center().x() - r.width() * sc / 2 - 6 * u, r.center().y() - r.height() * sc / 2,
                   r.width() * sc, r.height() * sc)
        draw_window_image(p, st.full(), r, 1.0, gd2, t)
    # phone (v4.0.0)
    for s in (shot,):
        pdef = SEGMENTS[s.seg].get("phone")
        if not pdef:
            continue
        segs = TL["segments"]
        t0 = segs[s.seg]["start"]
        t1 = segs[s.seg + 1]["start"]
        k_in = ease_out(clamp((t - (t0 + BAR * 0.5)) / 0.7))
        k_out = smooth(t1 - 0.45, t1 - 0.05, t)
        frames = flip_frames(pdef["dir"], "tasks")
        n = int(clamp((t - t0) / (2 * BEAT), 0, len(frames) - 1))
        img = state(pdef["dir"], frames[min(n, len(frames) - 1)]).full()
        r = QRectF(PHONE_RECT)
        r.translate(0, (1 - k_in) * 160 + k_out * 60)
        draw_phone(p, img, r, k_in * (1 - k_out))


def draw_flash(p, t):
    # white flash on big drops
    for tb, strength in ((BAR0, 0.55), (TL["segments"][12]["start"], 0.35), (SINK, 0.22)):
        if tb - 0.05 <= t < tb + 0.6:
            a = strength * math.exp(-(t - tb) / 0.14) if t >= tb else strength * smooth(tb - 0.05, tb, t)
            p.fillRect(0, 0, W, H, QColor(255, 255, 255, int(255 * clamp(a))))


def render_frame(t, img=None):
    if img is None:
        img = QImage(W, H, QImage.Format.Format_RGB32)
    p = QPainter(img)
    p.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.SmoothPixmapTransform |
                     QPainter.RenderHint.TextAntialiasing)
    end_dark = smooth(DURATION - 0.9, DURATION - 0.05, t)
    if t >= ENDING - 0.5:
        k = smooth(ENDING - 0.5, ENDING + 1.0, t)
        cols = [mix_color(c, n, k) for c, n in zip(era_colors(t), ("#070b1c", "#1c2a63", "#6f8cff"))]
        draw_background(p, t, cols)
    else:
        draw_background(p, t)
    intro_bg = 1 - smooth(0.0, 0.9, t)
    if intro_bg > 0:
        p.fillRect(0, 0, W, H, QColor(0, 0, 0, int(255 * intro_bg)))
    draw_chart(p, t)
    draw_intro(p, t)
    draw_app(p, t)
    draw_caption(p, t)
    draw_version_label(p, t)
    draw_ending(p, t)
    draw_flash(p, t)
    if end_dark > 0:
        p.fillRect(0, 0, W, H, QColor(0, 0, 0, int(255 * end_dark)))
    p.end()
    return img


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--still", type=float)
    ap.add_argument("--frames", type=int, nargs=2)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    app = QGuiApplication.instance() or QGuiApplication(sys.argv)  # noqa: F841
    if a.still is not None:
        render_frame(a.still).save(a.out)
        return
    f0, f1 = a.frames
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgra",
           "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "medium", "-crf", "17",
           "-pix_fmt", "yuv420p", "-x264-params", "keyint=120", a.out]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    img = QImage(W, H, QImage.Format.Format_RGB32)
    last_shot = None
    for fi in range(f0, f1):
        t = fi / FPS
        img.fill(0)
        render_frame(t, img)
        proc.stdin.write(bytes(img.constBits()))
        cs = current_shot(t)
        if cs is not last_shot:
            # free images of shots we have left behind
            for s in SHOT_LIST:
                if s.t1 < t - 3:
                    for f in s.frames:
                        state(s.dir, f).drop()
            last_shot = cs
        if fi % 300 == 0:
            print(f"frame {fi} t={t:.2f}", flush=True)
    proc.stdin.close()
    proc.wait()


if __name__ == "__main__":
    main()
