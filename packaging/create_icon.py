"""
生成应用图标占位文件 (assets/app_icon.ico)。
在构建前由 build_windows.bat 自动调用。

社区贡献者可替换 assets/app_icon.ico 为正式图标，
推荐尺寸：256×256 像素，ICO 格式（包含 16/32/48/256 多尺寸）。
"""
import os
import sys

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'assets')
OUTPUT_ICO = os.path.join(OUTPUT_DIR, 'app_icon.ico')


def create_placeholder_icon():
    """使用 Pillow 生成一个简单的星形占位图标。"""
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # 若已有图标，不覆盖（允许社区替换）
    if os.path.isfile(OUTPUT_ICO):
        print(f'[icon] 已有图标，跳过生成: {OUTPUT_ICO}')
        return

    try:
        from PIL import Image, ImageDraw
    except ImportError:
        print('[icon] Pillow 未安装，跳过图标生成。请手动提供 assets/app_icon.ico')
        return

    sizes = [256, 48, 32, 16]
    images = []

    for size in sizes:
        img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        # 深色背景圆
        bg_r = size // 2 - 1
        cx = cy = size // 2
        draw.ellipse(
            [cx - bg_r, cy - bg_r, cx + bg_r, cy + bg_r],
            fill=(30, 30, 40, 230)
        )

        # 简单五角星（用多边形近似）
        import math
        star_r = size * 0.38
        inner_r = size * 0.16
        points = []
        for i in range(10):
            angle = math.radians(-90 + i * 36)
            r = star_r if i % 2 == 0 else inner_r
            points.append((
                cx + r * math.cos(angle),
                cy + r * math.sin(angle),
            ))
        draw.polygon(points, fill=(74, 159, 212, 255))

        images.append(img)

    images[0].save(
        OUTPUT_ICO,
        format='ICO',
        sizes=[(s, s) for s in sizes],
        append_images=images[1:],
    )
    print(f'[icon] 已生成占位图标: {OUTPUT_ICO}')
    print('[icon] 提示: 请用正式图标替换 assets/app_icon.ico 以获得更好的视觉效果')


if __name__ == '__main__':
    create_placeholder_icon()
