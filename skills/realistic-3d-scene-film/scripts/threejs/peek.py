# 快速查看：u16 -> 原始 jpg（不调色）和 调色后 jpg
import sys, os, numpy as np
from PIL import Image
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import grade
src = sys.argv[1]; base = os.path.splitext(src)[0]
a = grade.load(src)
Image.fromarray((np.clip(a, 0, 1) * 255 + 0.5).astype(np.uint8)).save(base + "_raw.jpg", quality=92)
grade.grade(src, base + "_graded.jpg")
print(base + "_graded.jpg")
