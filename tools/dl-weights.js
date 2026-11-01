// Robust sequential downloader for the commander weight shards.
const https = require("https");
const fs = require("fs");
const path = require("path");

const OUT = process.argv[2];
if (!OUT || process.argv.length < 4) {
  console.log("用法: node tools/dl-weights.js <权重目录> <分片名…>");
  console.log("例:   node tools/dl-weights.js state/weights gbt-v8-v82-q5_0.gguf.part1 gbt-v8-v82-q5_0.gguf.part2");
  console.log("      （分片清单见 WEIGHTS.md；下完用 tools/merge-weights.py 合并）");
  process.exit(2);
}
const PARTS = process.argv.slice(3);

function fetchTo(url, dest, hops = 0) {
  return new Promise((resolve, reject) => {
    if (hops > 6) return reject(new Error("too many redirects"));
    const req = https.get(url, { headers: { "User-Agent": "dsh-agent" }, timeout: 60000 }, (res) => {
      if ([301, 302, 303, 307, 308].includes(res.statusCode) && res.headers.location) {
        res.resume();
        const next = new URL(res.headers.location, url).toString();
        return fetchTo(next, dest, hops + 1).then(resolve, reject);
      }
      if (res.statusCode !== 200) { res.resume(); return reject(new Error("HTTP " + res.statusCode)); }
      const total = parseInt(res.headers["content-length"] || "0", 10);
      const tmp = dest + ".tmp";
      const ws = fs.createWriteStream(tmp);
      let got = 0;
      let lastLog = 0;
      res.on("data", (c) => {
        got += c.length;
        if (got - lastLog > 200 * 1024 * 1024) {
          lastLog = got;
          console.log("   ...", (got / 1e9).toFixed(2), "GB of", (total / 1e9).toFixed(2), "GB");
        }
      });
      res.on("aborted", () => reject(new Error("aborted at " + got)));
      res.pipe(ws);
      ws.on("finish", () => fs.rename(tmp, dest, (e) => (e ? reject(e) : resolve({ got, total }))));
      ws.on("error", reject);
      res.on("error", reject);
    });
    req.on("timeout", () => { req.destroy(new Error("timeout")); });
    req.on("error", reject);
  });
}

(async () => {
  fs.mkdirSync(OUT, { recursive: true });
  let totalBytes = 0;
  for (const name of PARTS) {
    const dest = path.join(OUT, name);
    if (fs.existsSync(dest) && fs.statSync(dest).size > 0) {
      console.log("skip existing", name, (fs.statSync(dest).size / 1e9).toFixed(2), "GB");
      totalBytes += fs.statSync(dest).size;
      continue;
    }
    const url = "https://github.com/gbtweilai-star/GBTxiaotudouV8-Commander/releases/download/v1.0.0/" + name;
    const t0 = Date.now();
    console.log("downloading", name);
    const { got } = await fetchTo(url, dest);
    const secs = (Date.now() - t0) / 1000;
    console.log("  done", (got / 1e9).toFixed(2), "GB in", secs.toFixed(0), "s =", (got / 1048576 / secs).toFixed(1), "MB/s");
    totalBytes += got;
  }
  console.log("ALL DONE", (totalBytes / 1e9).toFixed(2), "GB");
})().catch((e) => { console.log("FAILED", e.message); process.exit(1); });
