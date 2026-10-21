"""Find the song's bar grid from its kick drums and write data/timeline.json.

usage: python beatgrid.py song.flac <repo-with-upstream-tags> [out.json]

Kicks are sharp rises in the 20-150 Hz band.  Fitting t = t0 + k*T to them gives the tempo
(145.88 BPM for this track, residual < 8 ms).  The intro impact at ~5.96 s is bar 0; version
boundaries are the bar numbers below (the user's segment list snapped to bar lines).
"""
import csv
import json
import os
import subprocess
import sys

import librosa
import numpy as np
from scipy.signal import find_peaks

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(os.path.dirname(HERE), "data")

# bar where each version starts (0 = the impact after the intro), newest version first
SEGMENT_BARS = [0, 4, 8, 16, 24, 28, 32, 36, 40, 44, 48, 52, 56, 60, 64, 72, 76, 80, 84]
VERSIONS = ["v4.4.4", "v4.4.0", "v4.3.0", "v4.2.6", "v4.1.1", "v4.1.0", "v4.0.0", "v3.10", "v3.9", "v3.8.3",
            "v3.7", "v3.6.1", "v3.5.12", "v3.5.0", "v3.4.1", "v3.3.0", "release", "v2.9.9", "gd2"]
FIXED_DATES = {"v2.9.9": "2023-08-16", "gd2": "2022-05-22"}   # first commit / last GD2 release


def kick_times(path):
    y, sr = librosa.load(path, sr=22050, mono=True)
    hop = 32
    fps = sr / hop
    S = np.abs(librosa.stft(y, n_fft=1024, hop_length=hop))
    f = librosa.fft_frequencies(sr=sr, n_fft=1024)
    low = np.log1p(S[(f > 20) & (f < 150)].sum(0))
    d = np.convolve(np.diff(low, prepend=low[0]), np.ones(5) / 5, "same")
    pk, _ = find_peaks(d, height=np.percentile(d, 97), distance=int(0.25 * fps))
    return pk / fps


def fit_grid(kt):
    k = kt[kt > 6.3]                      # the intro runs at a different (faster) pulse
    T, t0 = 0.4111, k[len(k) // 4]
    for _ in range(5):
        idx = np.round((k - t0) / T)
        good = np.abs(k - (t0 + idx * T)) < 0.06
        A = np.vstack([np.ones(good.sum()), idx[good]]).T
        (t0, T), *_ = np.linalg.lstsq(A, k[good], rcond=None)
    return t0, T


def main():
    song, repo = sys.argv[1], sys.argv[2]
    out = sys.argv[3] if len(sys.argv) > 3 else os.path.join(DATA, "timeline.json")
    t0, T = fit_grid(kick_times(song))
    # bars start on beats n = 1 (mod 4) counting from t0; the impact before 6 s is bar 0
    bar0 = t0 + (1 + 4 * round(((5.95 - t0) / T - 1) / 4)) * T
    bar = 4 * T
    stars = {r["Date"]: int(r["Stars"]) for r in csv.DictReader(open(os.path.join(DATA, "gd3_stars.csv")))}
    segs = []
    for v, b in zip(VERSIONS, SEGMENT_BARS):
        date = FIXED_DATES.get(v) or subprocess.check_output(
            ["git", "-C", repo, "log", "-1", "--format=%ad", "--date=short", v]).decode().strip()
        segs.append({"ver": v, "start": round(bar0 + b * bar, 4), "date": date,
                     "stars": stars.get(date) if date >= min(stars) else None})
    json.dump({"bpm": 60 / T, "beat": T, "bar": bar, "bar0": bar0, "segments": segs}, open(out, "w"), indent=1)
    print(f"{60 / T:.3f} BPM, bar0={bar0:.4f}s -> {out}")


if __name__ == "__main__":
    main()
