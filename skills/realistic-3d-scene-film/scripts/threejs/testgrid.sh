#!/usr/bin/env bash
# 渲染 jobs_test.json 里的 9 个镜头 → 调色 → 拼 3x3 预览
cd "$(dirname "$0")"
node render.mjs "${1:-jobs_test.json}" 2>&1 | grep -E "f[0-9]+ spp|rror" | head -30
cd ..
rm -rf renders/three/test/all_g
python grade.py --dir renders/three/test/all renders/three/test/all_g
python - <<'EOF'
from PIL import Image
d = 'renders/three/test/all_g'
order = ['f_0109', 'f_0048', 'f_0300', 'f_0416', 'f_0493', 'f_0596', 'f_0671', 'f_0768', 'f_0888']
g = Image.new('RGB', (1920, 1080))
for i, n in enumerate(order):
    im = Image.open(f'{d}/{n}.png').resize((640, 360), Image.LANCZOS)
    g.paste(im, ((i % 3) * 640, (i // 3) * 360))
g.save('renders/three/test/grid.jpg', quality=90)
print('grid ok')
EOF
