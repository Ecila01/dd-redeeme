"""素材预处理（任务书 M2/M5）：白底抠图 + 生成多尺寸 ico 图标。

- assets/fish.png（白底）→ assets/fish_alpha.png（背景透明）。
  仅从图像四边出发 flood-fill 与边缘连通的白底；气泡框内部白色与外部
  不连通，会自动保留（正好用来渲染最新兑换码文字）。
- assets/icon.ico：截取人物区域，居中成方形，输出 16~256 多尺寸图标。

用法（需 Pillow，构建脚本会自动安装）：python tools/prep_assets.py
"""
from __future__ import annotations

from collections import deque
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"

FLOOD_THRESHOLD = 240   # RGB 最小分量 >= 该值视为白底（flood-fill 起始/扩散条件）
HALO_THRESHOLD = 225    # 抠图后对残白边缘的追加清理阈值
HALO_PASSES = 3
ICON_SIZES = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]


def remove_white_bg(img: Image.Image) -> Image.Image:
    """从四边 flood-fill 去掉与边缘连通的白底（气泡内部白不被波及）。"""
    img = img.convert("RGBA")
    w, h = img.size
    px = img.load()

    def is_bg(x: int, y: int) -> bool:
        r, g, b, a = px[x, y]
        return a != 0 and min(r, g, b) >= FLOOD_THRESHOLD

    visited = bytearray(w * h)
    q: deque = deque()
    for x in range(w):
        for y in (0, h - 1):
            if is_bg(x, y) and not visited[y * w + x]:
                visited[y * w + x] = 1
                q.append((x, y))
    for y in range(h):
        for x in (0, w - 1):
            if is_bg(x, y) and not visited[y * w + x]:
                visited[y * w + x] = 1
                q.append((x, y))
    while q:
        x, y = q.popleft()
        px[x, y] = (255, 255, 255, 0)
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if 0 <= nx < w and 0 <= ny < h and not visited[ny * w + nx] and is_bg(nx, ny):
                visited[ny * w + nx] = 1
                q.append((nx, ny))
    return img


def clean_halo(img: Image.Image, passes: int = HALO_PASSES) -> Image.Image:
    """迭代清理与透明区相邻的近白像素（抗锯齿残边）。"""
    w, h = img.size
    px = img.load()
    for _ in range(passes):
        todo = []
        for y in range(h):
            for x in range(w):
                r, g, b, a = px[x, y]
                if a == 0 or min(r, g, b) < HALO_THRESHOLD:
                    continue
                for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                    if 0 <= nx < w and 0 <= ny < h and px[nx, ny][3] == 0:
                        todo.append((x, y))
                        break
        if not todo:
            break
        for x, y in todo:
            px[x, y] = (255, 255, 255, 0)
    return img


def make_icon(img: Image.Image) -> None:
    """取人物区域（图右下主体），居中方形化，输出多尺寸 ico。"""
    w, h = img.size
    crop = img.crop((int(w * 0.38), int(h * 0.26), w, h))  # 人物主体区域
    bbox = crop.getchannel("A").getbbox()
    if bbox:
        crop = crop.crop(bbox)
    side = max(crop.size)
    canvas = Image.new("RGBA", (side, side), (255, 255, 255, 0))
    canvas.alpha_composite(crop, ((side - crop.width) // 2, (side - crop.height) // 2))
    base = canvas.resize((256, 256), Image.LANCZOS)
    base.save(ASSETS / "icon.ico", sizes=ICON_SIZES)


def keep_largest_component(img: Image.Image) -> Image.Image:
    """仅保留最大不透明连通域（像素级剔除气泡描边/引导点等孤立残留）。"""
    w, h = img.size
    px = img.load()
    visited = bytearray(w * h)
    best_mask = bytearray(w * h)
    best_size = 0
    for start in range(w * h):
        if visited[start] or px[start % w, start // w][3] == 0:
            continue
        mask = bytearray(w * h)
        size = 0
        stack = [start]
        visited[start] = 1
        while stack:
            idx = stack.pop()
            mask[idx] = 1
            size += 1
            x, y = idx % w, idx // w
            for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                n = ny * w + nx
                if 0 <= nx < w and 0 <= ny < h and not visited[n] and px[nx, ny][3] != 0:
                    visited[n] = 1
                    stack.append(n)
        if size > best_size:
            best_mask, best_size = mask, size
    for idx in range(w * h):
        if not best_mask[idx]:
            x, y = idx % w, idx // w
            r, g, b, a = px[x, y]
            if a != 0:
                px[x, y] = (r, g, b, 0)
    return img


def make_body(img: Image.Image) -> None:
    """裁出不含气泡的"纯本体"贴图（鱼与气泡素材分离，仿 Dsh 大肥鱼挂件 v0.2.5）。

    在整图上保留最大不透明连通域（人物本体），像素级剔除气泡描边与引导点；
    注意必须先过滤再裁剪——若先矩形裁剪会把超出裁剪线的左侧耳朵尖切掉。
    最后按 alpha 包围盒收紧。挂件收起态使用本图（右下角锚定）。
    """
    full = keep_largest_component(img.copy())
    bbox = full.getchannel("A").getbbox()
    if bbox:
        full = full.crop(bbox)
    full.save(ASSETS / "fish_body.png")


def main() -> None:
    src = ASSETS / "fish.png"
    print(f"处理 {src}（纯 Python flood-fill，约需数十秒）...")
    img = clean_halo(remove_white_bg(Image.open(src)))
    out_alpha = ASSETS / "fish_alpha.png"
    img.save(out_alpha)
    print(f"已生成 {out_alpha}")
    make_icon(img)
    print(f"已生成 {ASSETS / 'icon.ico'}")
    make_body(img)
    print(f"已生成 {ASSETS / 'fish_body.png'}")


if __name__ == "__main__":
    main()
