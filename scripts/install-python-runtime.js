"use strict";

const fs = require("node:fs");
const path = require("node:path");
const { spawnSync } = require("node:child_process");

const {
  packageMetadata,
  pythonSitePackagesDir,
  resolveBundledWheel,
} = require("../index.js");

const root = path.resolve(__dirname, "..");
const stampPath = path.join(root, "python", ".install.json");

function pythonCandidates() {
  const candidates = [];
  for (const name of ["LLMGATEWAY_PYTHON", "PYTHON"]) {
    const value = String(process.env[name] || "").trim();
    if (value) {
      candidates.push([value]);
    }
  }
  if (process.platform === "win32") {
    candidates.push(["py", "-3"], ["python"]);
  } else {
    candidates.push(["python3"], ["python"]);
  }
  return candidates;
}

function findPython() {
  for (const candidate of pythonCandidates()) {
    const result = spawnSync(candidate[0], [...candidate.slice(1), "-c", "import sys; print('.'.join(map(str, sys.version_info[:2])))"], {
      cwd: root,
      encoding: "utf-8",
    });
    if (result.status === 0) {
      return candidate;
    }
  }
  throw new Error("Python 3.10+ was not found. Set LLMGATEWAY_PYTHON to a Python executable.");
}

function ensureSupportedPython(python) {
  const result = spawnSync(
    python[0],
    [...python.slice(1), "-c", "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)"],
    {cwd: root},
  );
  if (result.status !== 0) {
    throw new Error("llmgateway requires Python 3.10 or newer.");
  }
}

function installedAlready() {
  if (!fs.existsSync(stampPath)) {
    return false;
  }
  try {
    const stamp = JSON.parse(fs.readFileSync(stampPath, "utf-8"));
    return (
      stamp.version === packageMetadata.version
      && fs.existsSync(path.join(pythonSitePackagesDir(root), "llmgateway"))
    );
  } catch {
    return false;
  }
}

function installRuntime(python, wheelPath) {
  const sitePackages = pythonSitePackagesDir(root);
  fs.rmSync(sitePackages, {recursive: true, force: true});
  fs.mkdirSync(sitePackages, {recursive: true});
  const result = spawnSync(
    python[0],
    [
      ...python.slice(1),
      "-m",
      "pip",
      "install",
      "--disable-pip-version-check",
      "--no-warn-script-location",
      "--upgrade",
      "--target",
      sitePackages,
      wheelPath,
    ],
    {cwd: root, stdio: "inherit"},
  );
  if (result.status !== 0) {
    throw new Error("Python runtime installation failed.");
  }
  fs.writeFileSync(
    stampPath,
    JSON.stringify({version: packageMetadata.version, wheel: path.basename(wheelPath)}, null, 2) + "\n",
    "utf-8",
  );
}

if (String(process.env.LLMGATEWAY_SKIP_PYTHON_INSTALL || "").trim()) {
  console.log("llmgateway: skipping Python runtime install because LLMGATEWAY_SKIP_PYTHON_INSTALL is set.");
  process.exit(0);
}

try {
  if (installedAlready()) {
    console.log(`llmgateway: Python runtime ${packageMetadata.version} is already installed.`);
    process.exit(0);
  }
  const wheelPath = resolveBundledWheel(root);
  if (!wheelPath) {
    throw new Error("Bundled llmgateway wheel was not found in python/wheels.");
  }
  const python = findPython();
  ensureSupportedPython(python);
  installRuntime(python, wheelPath);
  console.log(`llmgateway: installed Python runtime ${packageMetadata.version}.`);
} catch (error) {
  console.error(`llmgateway: ${error instanceof Error ? error.message : String(error)}`);
  console.error("llmgateway: install Python 3.10+ with pip, or set LLMGATEWAY_SKIP_PYTHON_INSTALL=1 to skip.");
  process.exit(1);
}
