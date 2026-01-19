from PIL import Image, ImageDraw
import math

def create_icon():
    # 创建 512x512 图标
    size = 512
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # 1. 绘制渐变圆形背景（蓝色到青色）
    center = size // 2
    for r in range(240, 0, -1):
        ratio = (240 - r) / 240
        color_r = int(26 + (79 - 26) * ratio)
        color_g = int(26 + (195 - 26) * ratio)
        color_b = int(46 + (247 - 46) * ratio)
        alpha = 255
        draw.ellipse([center-r, center-r, center+r, center+r], 
                     fill=(color_r, color_g, color_b, alpha))

    # 2. 绘制齿轮（代表自动化工具）
    def draw_gear(draw, cx, cy, outer_r, inner_r, teeth=8, color=(255, 255, 255, 255)):
        points = []
        for i in range(teeth * 4):
            angle = (i * math.pi * 2) / (teeth * 4)
            if i % 4 == 0 or i % 4 == 3:
                r = outer_r
            else:
                r = outer_r * 0.85
            x = cx + r * math.cos(angle)
            y = cy + r * math.sin(angle)
            points.append((x, y))
        
        draw.polygon(points, fill=color)
        draw.ellipse([cx-inner_r, cy-inner_r, cx+inner_r, cy+inner_r], 
                     fill=(79, 195, 247, 255))

    # 绘制齿轮（右下角，稍小）
    gear_cx = center + 70
    gear_cy = center + 70
    draw_gear(draw, gear_cx, gear_cy, 80, 30, teeth=8, color=(255, 255, 255, 230))

    # 3. 绘制 Python 蛇形状（简化的 P 字母 + 曲线）
    # 绘制大圆（P 的上半部分）
    p_x = center - 40
    p_y = center - 60
    draw.ellipse([p_x-70, p_y-70, p_x+70, p_y+70], fill=(255, 255, 255, 255))
    draw.ellipse([p_x-50, p_y-50, p_x+50, p_y+50], fill=(79, 195, 247, 255))

    # 绘制竖线（P 的竖）
    draw.rectangle([p_x-70, p_y-70, p_x-40, p_y+120], fill=(255, 255, 255, 255))

    # 4. 绘制魔法棒/闪电（代表"一键"）
    wand_points = [
        (center + 80, center - 120),
        (center + 90, center - 90),
        (center + 70, center - 85),
        (center + 100, center - 50),
        (center + 75, center - 55),
        (center + 85, center - 30),
        (center + 65, center - 50),
        (center + 70, center - 75),
    ]
    draw.polygon(wand_points, fill=(255, 220, 100, 255))

    # 5. 添加勾选符号（表示完成/解决）
    check_scale = 50
    check_x = center - 50
    check_y = center + 80
    check_points = [
        (check_x, check_y),
        (check_x + check_scale * 0.3, check_y + check_scale * 0.4),
        (check_x + check_scale, check_y - check_scale * 0.4),
        (check_x + check_scale * 0.3, check_y + check_scale * 0.6),
    ]
    draw.polygon(check_points, fill=(100, 255, 100, 255))
    draw.line([(check_x, check_y), (check_x + check_scale * 0.3, check_y + check_scale * 0.4)], 
              fill=(255, 255, 255, 255), width=15)
    draw.line([(check_x + check_scale * 0.3, check_y + check_scale * 0.4), 
               (check_x + check_scale, check_y - check_scale * 0.4)], 
              fill=(255, 255, 255, 255), width=15)

    # 保存为 PNG
    png_path = 'icon.png'
    img.save(png_path, 'PNG')
    print(f"✅ PNG icon created: {png_path}")

    # 转换为 ICO（多尺寸）
    ico_path = 'icon.ico'
    sizes = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    icon_images = [img.resize(s, Image.Resampling.LANCZOS) for s in sizes]
    icon_images[0].save(ico_path, format='ICO', sizes=sizes)
    print(f"✅ ICO icon created: {ico_path}")

if __name__ == "__main__":
    create_icon()
