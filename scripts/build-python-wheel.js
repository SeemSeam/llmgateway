"use strict";

const fs = require("node:fs");
const path = require("node:path");
const { spawnSync } = require("node:child_process");

const root = path.resolve(__dirname, "..");
const wheelsDir = path.join(root, "python", "wheels");

function pythonCandidates() {
  const candidates = [];
  for (const name of ["LLMGATEWAY_BUILD_PYTHON", "PYTHON"]) {
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
    const result = spawnSync(candidate[0], [...candidate.slice(1), "-c", "import sys; print(sys.version_info[0])"], {
      cwd: root,
      encoding: "utf-8",
    });
    if (result.status === 0 && String(result.stdout || "").trim() === "3") {
      return candidate;
    }
  }
  throw new Error("Python 3 was not found. Set LLMGATEWAY_BUILD_PYTHON to a Python 3 executable.");
}

function runPython(python, args) {
  const result = spawnSync(python[0], [...python.slice(1), ...args], {
    cwd: root,
    stdio: "inherit",
  });
  if (result.status !== 0) {
    process.exit(result.status || 1);
  }
}

fs.rmSync(wheelsDir, {recursive: true, force: true});
fs.mkdirSync(wheelsDir, {recursive: true});

const python = findPython();
runPython(python, ["-m", "build", "--wheel", "--outdir", wheelsDir]);
