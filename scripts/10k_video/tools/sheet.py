import sys, os
from PIL import Image
d = sys.argv[1]; names = sys.argv[2:] or sorted(f[:-4] for f in os.listdir(d) if f.endswith('.png') and f != 'sheet.png')
ims = [Image.open(os.path.join(d, n + '.png')).convert('RGB') for n in names]
W = 1120; cols = 2
th = [int(im.height * W / im.width) for im in ims]
rows = (len(ims) + 1) // 2
rh = [max(th[i*2:(i+1)*2]) for i in range(rows)]
sheet = Image.new('RGB', (W * cols, sum(rh)), 'white')
y = 0
for r in range(rows):
    for c in range(cols):
        i = r * 2 + c
        if i < len(ims):
            sheet.paste(ims[i].resize((W, th[i])), (c * W, y))
    y += rh[r]
sheet.save(os.path.join(d, 'sheet.png'))
print(names)
