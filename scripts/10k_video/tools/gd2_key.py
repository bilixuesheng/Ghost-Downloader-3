"""GD2 relied on DWM acrylic: large pure-black areas in the Qt backing store showed the blur.
Key such areas (big connected regions of opaque pure black) to transparent; keep thin text."""
import sys, numpy as np
from PIL import Image
from scipy import ndimage
for p in sys.argv[1:]:
    im = np.array(Image.open(p).convert("RGBA"))
    black = (im[..., 0] < 3) & (im[..., 1] < 3) & (im[..., 2] < 3) & (im[..., 3] > 250)
    core = ndimage.binary_erosion(black, iterations=3)
    lab, n = ndimage.label(core)
    if n:
        sizes = ndimage.sum(core, lab, range(1, n + 1))
        keep = np.isin(lab, np.nonzero(sizes > 400)[0] + 1)
        region = ndimage.binary_dilation(keep, iterations=4) & black
        im[region, 3] = 0
    Image.fromarray(im).save(p)
    print(p, "keyed", int(region.sum()) if n else 0)
