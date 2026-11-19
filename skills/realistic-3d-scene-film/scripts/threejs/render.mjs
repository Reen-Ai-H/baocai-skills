// 无头 Chrome（独显 WebGL2）驱动 three.js 离线渲染
// 用法: node render.mjs <jobs.json>      jobs: [{shot, frames:[...], spp, w, h, shutter, out}]
//       node render.mjs --still S2 109 [spp] [w] [h]
import puppeteer from "puppeteer-core";
import fs from "node:fs";
import { startServer } from "./server.mjs";

const CHROME = process.env.CHROME_PATH || [
  "C:/Program Files/Google/Chrome/Application/chrome.exe",
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
  "/usr/bin/google-chrome", "/usr/bin/chromium",
].find((p) => fs.existsSync(p));
if (!CHROME) throw new Error("Chrome not found: set CHROME_PATH");
let jobs;
if (process.argv[2] === "--still") {
  const [, , , shot, fr, spp = 64, w = 1920, h = 1080] = process.argv;
  jobs = [{ shot, frames: [+fr], spp: +spp, w: +w, h: +h, shutter: 0, out: `../renders/three/test/${shot}_${fr}` }];
} else {
  jobs = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
}

const srv = await startServer(5178);
const browser = await puppeteer.launch({
  executablePath: CHROME, headless: "new", protocolTimeout: 0,
  args: ["--use-angle=d3d11", "--enable-gpu", "--ignore-gpu-blocklist", "--force_high_performance_gpu",
    "--enable-unsafe-swiftshader=false", "--disable-gpu-watchdog", "--disable-renderer-backgrounding",
    "--js-flags=--max-old-space-size=8192", "--window-size=800,450"],
});
const page = await browser.newPage();
page.on("console", (m) => console.log("[page]", m.text()));
page.on("pageerror", (e) => console.log("[pageerror]", e.message));
await page.goto("http://127.0.0.1:5178/index.html", { waitUntil: "load", timeout: 0 });
await page.waitForFunction("window.READY === true || window.FAILED", { timeout: 0, polling: 500 });
if (await page.evaluate("window.FAILED")) { console.log("init failed"); process.exit(1); }
const t0 = Date.now();
for (const job of jobs) {
  await page.evaluate((j) => window.renderJob(j), job);
}
console.log(`all jobs done in ${((Date.now() - t0) / 1000).toFixed(1)} s`);
await browser.close();
srv.close();
