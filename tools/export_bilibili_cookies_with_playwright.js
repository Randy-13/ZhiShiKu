const fs = require("fs");
const path = require("path");
const { chromium } = require("playwright");

const root = path.resolve(__dirname, "..");
const authDir = path.join(root, "auth");
const userDataDir = path.join(authDir, "playwright-bilibili-profile");
const outputPath = path.join(authDir, "bilibili.cookies.txt");
const targetUrl = process.argv[2] || "https://space.bilibili.com/520819684";
const timeoutMs = Number(process.env.BILIBILI_COOKIE_EXPORT_TIMEOUT_MS || 300000);

function boolFlag(value) {
  return value ? "TRUE" : "FALSE";
}

function domainFlag(domain) {
  return domain.startsWith(".") ? "TRUE" : "FALSE";
}

function expiryValue(cookie) {
  if (!cookie.expires || cookie.expires < 0) return "0";
  return String(Math.floor(cookie.expires));
}

function toNetscape(cookies) {
  const lines = [
    "# Netscape HTTP Cookie File",
    "# Generated locally from Playwright Edge profile for yt-dlp. Keep this file private.",
  ];
  for (const cookie of cookies) {
    if (!cookie.domain || !cookie.name) continue;
    lines.push(
      [
        cookie.domain,
        domainFlag(cookie.domain),
        cookie.path || "/",
        boolFlag(cookie.secure),
        expiryValue(cookie),
        cookie.name,
        cookie.value || "",
      ].join("\t")
    );
  }
  return `${lines.join("\n")}\n`;
}

async function bilibiliCookies(context) {
  const cookies = await context.cookies([
    "https://www.bilibili.com",
    "https://space.bilibili.com",
  ]);
  return cookies.filter((cookie) => cookie.domain.includes("bilibili.com"));
}

async function main() {
  fs.mkdirSync(authDir, { recursive: true });
  console.log(`Opening Edge with isolated profile: ${userDataDir}`);
  console.log("Log in to Bilibili in the opened window if needed. The script will continue after login cookies appear.");

  const context = await chromium.launchPersistentContext(userDataDir, {
    channel: "msedge",
    headless: false,
    viewport: { width: 1280, height: 900 },
    locale: "zh-CN",
  });
  const page = context.pages()[0] || await context.newPage();
  await page.goto(targetUrl, { waitUntil: "domcontentloaded", timeout: 45000 });

  const startedAt = Date.now();
  let cookies = await bilibiliCookies(context);
  while (!cookies.some((cookie) => cookie.name === "SESSDATA")) {
    if (Date.now() - startedAt > timeoutMs) {
      await context.close();
      throw new Error("Timed out waiting for Bilibili login cookie SESSDATA. Please log in and run again.");
    }
    await page.waitForTimeout(2000);
    cookies = await bilibiliCookies(context);
  }

  fs.writeFileSync(outputPath, toNetscape(cookies), "utf8");
  const names = new Set(cookies.map((cookie) => cookie.name));
  const required = ["SESSDATA", "DedeUserID", "bili_jct"];
  const missing = required.filter((name) => !names.has(name));
  if (missing.length) {
    console.log(`Exported cookies to ${outputPath}, but missing: ${missing.join(", ")}`);
    await context.close();
    process.exit(1);
  }

  console.log(`Exported Bilibili cookies to ${outputPath}`);
  console.log(`Cookie count: ${cookies.length}; required login keys are present.`);
  await context.close();
}

main().catch((error) => {
  console.error(error.message || error);
  process.exit(1);
});
