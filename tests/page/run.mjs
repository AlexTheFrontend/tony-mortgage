// Runs the page checks in headless Edge or Chrome, with no network.
//
// Usage: node tests/page/run.mjs [site-dir] [time-zone]
//   site-dir   default "site"; use "public" to check the deploy folder.
//   time-zone  an IANA name such as America/Los_Angeles; default: the time zone of this computer.
// Set BROWSER to the browser program if it is not in a usual place.
// Exit code: 0 when all checks pass, 1 when a check fails, 2 when the checks cannot run.
import { spawn } from "node:child_process";
import { cpSync, existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { pathToFileURL } from "node:url";
import { XSS_HEADLINE, checkPage } from "./page_check.mjs";

const BROWSERS = [
  process.env.BROWSER,
  "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
  "/Applications/Chromium.app/Contents/MacOS/Chromium",
  "/usr/bin/microsoft-edge",
  "/usr/bin/google-chrome",
  "/usr/bin/chromium",
].filter(Boolean);
const PREFIX = "window.TONY_DATA = ";
const TIME_LIMIT_MS = 180000;

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// A copy of the site whose first headline holds markup, for check 10.
function escapingCopy(siteDir, dir) {
  cpSync(siteDir, dir, { recursive: true });
  const js = readFileSync(join(siteDir, "data.js"), "utf8");
  const data = JSON.parse(js.slice(PREFIX.length, js.lastIndexOf(";")));
  data.issues[0].headline = XSS_HEADLINE;
  writeFileSync(join(dir, "data.js"), PREFIX + JSON.stringify(data) + ";\n");
}

// The browser writes its DevTools port to this file when it starts with --remote-debugging-port=0.
async function devToolsPort(profile) {
  const file = join(profile, "DevToolsActivePort");
  for (let i = 0; i < 80; i++) {
    if (existsSync(file)) {
      const port = readFileSync(file, "utf8").split("\n")[0].trim();
      if (port) return port;
    }
    await sleep(250);
  }
  throw new Error("the browser did not open a DevTools port");
}

async function main() {
  const siteDir = resolve(process.argv[2] || "site");
  const tz = process.argv[3];
  if (!existsSync(join(siteDir, "index.html")) || !existsSync(join(siteDir, "data.js"))) {
    console.error(`${siteDir} must hold index.html and data.js. Build it first.`);
    return 2;
  }
  const browserPath = BROWSERS.find((p) => existsSync(p));
  if (!browserPath) {
    console.error("No Edge or Chrome found. Set BROWSER to the browser program.");
    return 2;
  }

  const work = mkdtempSync(join(tmpdir(), "tony-page-check-"));
  const profile = join(work, "profile"), xssDir = join(work, "site-xss"), shots = join(work, "screenshots");
  mkdirSync(shots);
  escapingCopy(siteDir, xssDir);

  // The proxy address has no server, so any request to the network fails: the page must work offline.
  const browser = spawn(browserPath, [
    "--headless=new", "--disable-gpu", "--no-first-run", "--no-default-browser-check",
    "--remote-debugging-port=0", `--user-data-dir=${profile}`, "--proxy-server=http://127.0.0.1:9", "about:blank",
  ], { stdio: "ignore" });
  const exited = new Promise((r) => browser.once("exit", r));
  const timer = setTimeout(() => { console.error("FAIL the checks took too long"); browser.kill(); process.exit(2); }, TIME_LIMIT_MS);
  try {
    const results = await checkPage({
      port: await devToolsPort(profile),
      pageUrl: pathToFileURL(join(siteDir, "index.html")).href,
      xssUrl: pathToFileURL(join(xssDir, "index.html")).href,
      outDir: shots,
      tz,
    });
    console.log(`Page checks for ${siteDir}${tz ? ` in ${tz}` : ""}:`);
    console.log(results.join("\n"));
    const failed = results.filter((r) => r.startsWith("FAIL")).length;
    console.log(failed ? `${failed} of ${results.length} checks FAILED.` : `All ${results.length} checks passed.`);
    console.log(`Screenshots: ${shots}`);
    return failed ? 1 : 0;
  } finally {
    clearTimeout(timer);
    browser.kill();
    await exited;
    rmSync(profile, { recursive: true, force: true, maxRetries: 5 });
    rmSync(xssDir, { recursive: true, force: true });
  }
}

main().then((code) => process.exit(code), (err) => { console.error("The checks could not run:", err.message); process.exit(2); });
