# 🔴 GBT 加固 2026-10-25：原来写死 Windows 绝对路径
#    `C:\Users\ADMIN\Desktop\GBT小土豆V8`，Linux/手机上会**造出一个同名垃圾目录**。
#    改成按本文件位置推仓根，换机器零改动。
from pathlib import Path as _GBTPath
_GBT_ROOT = str(_GBTPath(__file__).resolve().parents[2])
from PIL import Image, ImageDraw
import pathlib
R = pathlib.Path(_GBT_ROOT + "/render")
a = Image.open(R/"宝箱-渲染-v1平光.png").convert("RGB")
b = Image.open(R/"宝箱-渲染.png").convert("RGB")
H = 700
a = a.resize((int(a.width*H/a.height), H), Image.LANCZOS)
b = b.resize((int(b.width*H/b.height), H), Image.LANCZOS)
sheet = Image.new("RGB", (a.width+b.width, H+44), (18, 22, 34))
d = ImageDraw.Draw(sheet)
sheet.paste(a, (0, 44))
sheet.paste(b, (a.width, 44))
d.text((8, 14), "v1 平光（无 IBL / ACES / 无阴影）", fill=(232, 236, 248))
d.text((a.width+8, 14), "v2 棚拍（IBL + PBR Neutral + PCFSoft 接触阴影）", fill=(0, 229, 255))
sheet.save(R/"宝箱-渲染-对照.png")
print("saved:", R/"宝箱-渲染-对照.png", sheet.size)
