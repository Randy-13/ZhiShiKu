import { readdir, rm, writeFile } from "node:fs/promises";
import { existsSync } from "node:fs";
import { spawn } from "node:child_process";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";

const scriptDir = dirname(fileURLToPath(import.meta.url));
const root = resolve(scriptDir, "..");
const viteBin = resolve(root, "../node_modules/vite/bin/vite.js");
const buildName = `dist-served-${Date.now()}`;
const buildDir = resolve(root, buildName);
const pointerFile = resolve(root, ".served-dist");

await run(process.execPath, [viteBin, "build", "--outDir", buildDir, "--emptyOutDir=true"], root);
await writeFile(pointerFile, `${buildName}\n`, "utf-8");
await removeOldServedBuilds(buildName);

function run(command, args, cwd) {
  return new Promise((resolveRun, rejectRun) => {
    const child = spawn(command, args, {
      cwd,
      stdio: "inherit",
      shell: false,
    });
    child.on("error", rejectRun);
    child.on("exit", (code) => {
      if (code === 0) {
        resolveRun();
      } else {
        rejectRun(new Error(`Command failed with exit code ${code}: ${command} ${args.join(" ")}`));
      }
    });
  });
}

async function removeOldServedBuilds(currentName) {
  let entries = [];
  try {
    entries = await readdir(root, { withFileTypes: true });
  } catch {
    return;
  }
  const oldBuilds = entries
    .filter((entry) => entry.isDirectory() && entry.name.startsWith("dist-served-") && entry.name !== currentName)
    .map((entry) => entry.name)
    .sort()
    .slice(0, -2);
  for (const name of oldBuilds) {
    const path = resolve(root, name);
    if (!existsSync(path)) continue;
    try {
      await rm(path, { recursive: true, force: true, maxRetries: 3, retryDelay: 200 });
    } catch (error) {
      console.warn(`Keeping old build ${name}: ${error.message}`);
    }
  }
}
