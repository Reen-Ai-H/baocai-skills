// 静态文件服务 + 接收渲染帧（16-bit 原始数据）写盘
import http from "node:http";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = path.dirname(fileURLToPath(import.meta.url));
const TYPES = { ".html": "text/html", ".js": "text/javascript", ".mjs": "text/javascript", ".json": "application/json",
  ".glb": "model/gltf-binary", ".bin": "application/octet-stream" };

export function startServer(port = 5178) {
  const srv = http.createServer((req, res) => {
    const url = new URL(req.url, "http://x");
    if (req.method === "POST" && url.pathname === "/save") {
      const out = path.resolve(ROOT, url.searchParams.get("path"));
      if (!out.startsWith(path.resolve(ROOT, "..", "renders"))) { res.writeHead(403); return res.end(); }
      fs.mkdirSync(path.dirname(out), { recursive: true });
      const chunks = [];
      req.on("data", (c) => chunks.push(c));
      req.on("end", () => { fs.writeFileSync(out, Buffer.concat(chunks)); res.writeHead(200); res.end("ok"); });
      return;
    }
    const file = path.join(ROOT, decodeURIComponent(url.pathname === "/" ? "/index.html" : url.pathname));
    if (!file.startsWith(ROOT) || !fs.existsSync(file) || fs.statSync(file).isDirectory()) { res.writeHead(404); return res.end(); }
    res.writeHead(200, { "Content-Type": TYPES[path.extname(file)] || "application/octet-stream", "Cache-Control": "no-store" });
    fs.createReadStream(file).pipe(res);
  });
  return new Promise((r) => srv.listen(port, "127.0.0.1", () => r(srv)));
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  await startServer(+process.argv[2] || 5178);
  console.log("serving on http://127.0.0.1:" + (+process.argv[2] || 5178));
}
