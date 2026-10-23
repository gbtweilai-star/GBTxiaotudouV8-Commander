import sys
import time
from pathlib import Path

sys.path.insert(0, ".")
sys.stdout.reconfigure(encoding="utf-8")

from gbt_allinone import record_grid as RG  # noqa: E402

src = Path("gbt_allinone/record_grid.py")
text = src.read_text(encoding="utf-8")
print("record_grid.py:", len(text.splitlines()), "lines |",
      f"{src.stat().st_size / 1024:.1f} KB")

data = Path(".scratch/oldlinks/links.txt").read_bytes()
txt, enc, _ = RG.decode_bytes(data)
plan = RG._preset("link_index")

t0 = time.perf_counter()
p = RG.parse_text(txt, plan)
t_parse = time.perf_counter() - t0

t0 = time.perf_counter()
v = RG.verify_roundtrip(txt, plan)
t_verify = time.perf_counter() - t0

t0 = time.perf_counter()
prof = RG.profile_text(txt)
t_profile = time.perf_counter() - t0

print(f"corpus: {len(data)} bytes | {len(txt.splitlines())} lines")
print(f"parse: {t_parse * 1000:.1f} ms | verify: {t_verify * 1000:.1f} ms | "
      f"profile: {t_profile * 1000:.1f} ms")
print("records:", len(p["records"]), "| invalid:", len(p["invalid"]),
      "| findings:", len(p["findings"]), "| idempotent:", v["ok"])
print("throughput: %.0f lines/s" % (len(txt.splitlines()) / max(t_parse, 1e-9)))
