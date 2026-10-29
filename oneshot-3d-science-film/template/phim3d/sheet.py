"""python sheet.py out.jpg img... — tile stills 2 per row at 960 px wide each."""
import sys
from PIL import Image
out, files = sys.argv[1], sys.argv[2:]
W = 960
ims = [Image.open(f).convert("RGB") for f in files]
ims = [i.resize((W, round(i.height * W / i.width))) for i in ims]
h = ims[0].height
cols = 2 if len(ims) > 1 else 1
rows = (len(ims) + cols - 1) // cols
S = Image.new("RGB", (W * cols, h * rows), (40, 40, 40))
for k, im in enumerate(ims):
    S.paste(im, ((k % cols) * W, (k // cols) * h))
S.save(out, quality=88)
