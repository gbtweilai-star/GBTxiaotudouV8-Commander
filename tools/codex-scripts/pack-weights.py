import argparse, hashlib, os, zipfile

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=os.path.join("state", "weights", "gbt-v8-v82-stream"))
    ap.add_argument("--out", default=os.path.join("outputs", "gbt-weights.zip"))
    a = ap.parse_args()
    src = os.path.abspath(a.src)
    if not os.path.isdir(src):
        raise SystemExit("权重目录不存在: " + src)
    need = ["config.json", "tokenizer.json", "tokenizer_config.json", "stream_manifest.json"]
    miss = [n for n in need if not os.path.isfile(os.path.join(src, n))]
    if miss:
        raise SystemExit("缺关键件，拒绝打包（不许半个模型出门）: " + ", ".join(miss))
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    h = hashlib.sha256()
    with zipfile.ZipFile(a.out, "w", zipfile.ZIP_DEFLATED, compresslevel=1) as z:
        for base, _d, files in os.walk(src):
            for f in sorted(files):
                p = os.path.join(base, f)
                rel = os.path.relpath(p, src)          # 解压后就是模型根目录
                z.write(p, rel)
                with open(p, "rb") as fh:
                    for chunk in iter(lambda: fh.read(1 << 20), b""):
                        h.update(chunk)
    size = os.path.getsize(a.out)
    print("打包完成:", a.out)
    print("大小: %.2f GB" % (size / 1024**3))
    print("sha256:", h.hexdigest()[:32])
    print("解压后目录要含:", ", ".join(need))

if __name__ == "__main__":
    main()
