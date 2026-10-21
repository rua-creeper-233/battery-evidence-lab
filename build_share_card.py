"""Render the repository-native share card. Requires Pillow; not a site build dependency."""
from pathlib import Path
import os
from PIL import Image, ImageDraw, ImageFont


def main():
    root = Path(__file__).resolve().parent
    canvas = Image.new('RGB', (1200, 630), '#fafbf8')
    draw = ImageDraw.Draw(canvas)
    fonts = Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Fonts'
    def font(size, bold=False):
        choices = [fonts / ('msyhbd.ttc' if bold else 'msyh.ttc'), Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')]
        return ImageFont.truetype(str(next(path for path in choices if path.is_file())), size)
    draw.rounded_rectangle((48, 48, 1152, 582), radius=24, outline='#dbe3dc', width=2)
    draw.text((88, 143), 'Battery Evidence Lab', fill='#203029', font=font(54, True))
    draw.text((92, 239), '电池材料计算文献与方法', fill='#5d6a63', font=font(32))
    draw.text((92, 332), 'DFT   /   Molecular dynamics   /   AI for Science', fill='#2e6b50', font=font(23))
    draw.line((92, 402, 710, 402), fill='#dbe3dc', width=2)
    draw.text((92, 432), '论文检索   计算流程   学习路线', fill='#5d6a63', font=font(23))
    draw.rounded_rectangle((922, 104, 990, 145), radius=9, fill='#68766f')
    draw.rounded_rectangle((844, 137, 1070, 506), radius=42, fill='#2e6b50')
    draw.ellipse((844, 129, 1070, 211), fill='#edf5ef', outline='#2e6b50', width=5)
    draw.rounded_rectangle((935, 210, 1042, 468), radius=12, fill='#edf5ef')
    for x, color in [(950, '#b26a31'), (968, '#203029'), (986, '#b26a31'), (1004, '#203029')]:
        draw.rounded_rectangle((x, 224, x + 9, 452), radius=4, fill=color)
    draw.text((869, 260), '+', fill='white', font=font(42, True))
    draw.line((885, 433, 909, 433), fill='white', width=4)
    canvas.save(root / 'static/share-card.png', optimize=True)


if __name__ == '__main__':
    main()
