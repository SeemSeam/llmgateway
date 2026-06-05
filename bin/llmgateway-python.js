#!/usr/bin/env node
"use strict";

const { spawnSync } = require("node:child_process");
const { pythonEnv } = require("../index.js");

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
    const result = spawnSync(candidate[0], [...candidate.slice(1), "-c", "import sys"], {
      encoding: "utf-8",
    });
    if (result.status === 0) {
      return candidate;
    }
  }
  throw new Error("Python 3 was not found. Set LLMGATEWAY_PYTHON to a Python executable.");
}

try {
  const python = findPython();
  const args = process.argv.slice(2);
  const commandArgs = args.length
    ? args
    : ["-c", "import llmgateway; print(llmgateway.__name__)"];
  const result = spawnSync(python[0], [...python.slice(1), ...commandArgs], {
    env: pythonEnv(),
    stdio: "inherit",
  });
  process.exit(result.status === null ? 1 : result.status);
} catch (error) {
  console.error(`llmgateway-python: ${error instanceof Error ? error.message : String(error)}`);
  process.exit(1);
}
