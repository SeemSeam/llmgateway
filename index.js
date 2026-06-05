"use strict";

const os = require("node:os");
const fs = require("node:fs");
const path = require("node:path");

const packageMetadata = Object.freeze({
  name: "@seemseam/llmgateway",
  version: "0.1.2",
  pythonPackage: "llmgateway",
  primaryRuntime: "python",
});

const packageRoot = __dirname;

function resolvePath(value) {
  return path.resolve(String(value || ""));
}

function userConfigDir(env = process.env, homeDir = os.homedir()) {
  const override = String(env.LLMGATEWAY_USER_CONFIG_DIR || "").trim();
  if (override) {
    return resolvePath(override);
  }
  return path.join(homeDir, ".llmgateway");
}

function resolveUserConfigFile(env = process.env, homeDir = os.homedir()) {
  const explicit = String(env.LLMGATEWAY_CONFIG || "").trim();
  if (explicit) {
    return resolvePath(explicit);
  }
  return path.join(userConfigDir(env, homeDir), "config.yaml");
}

function resolveProviderStateFile(env = process.env, homeDir = os.homedir()) {
  const explicit = String(env.LLMGATEWAY_PROVIDER_STATE || "").trim();
  if (explicit) {
    return resolvePath(explicit);
  }
  return path.join(userConfigDir(env, homeDir), "provider-state.json");
}

function pythonSitePackagesDir(root = packageRoot) {
  return path.join(root, "python", "site-packages");
}

function pythonWheelsDir(root = packageRoot) {
  return path.join(root, "python", "wheels");
}

function resolveBundledWheel(root = packageRoot) {
  const wheelsDir = pythonWheelsDir(root);
  if (!fs.existsSync(wheelsDir)) {
    return "";
  }
  const expected = `llmgateway-${packageMetadata.version}-py3-none-any.whl`;
  const exactPath = path.join(wheelsDir, expected);
  if (fs.existsSync(exactPath)) {
    return exactPath;
  }
  const candidates = fs
    .readdirSync(wheelsDir)
    .filter((name) => /^llmgateway-.+\.whl$/.test(name))
    .sort();
  return candidates.length ? path.join(wheelsDir, candidates[candidates.length - 1]) : "";
}

function pythonEnv(env = process.env, root = packageRoot) {
  const sitePackages = pythonSitePackagesDir(root);
  const current = String(env.PYTHONPATH || "").trim();
  return {
    ...env,
    PYTHONPATH: current ? `${sitePackages}${path.delimiter}${current}` : sitePackages,
  };
}

function isPythonRuntimeInstalled(root = packageRoot) {
  return fs.existsSync(path.join(pythonSitePackagesDir(root), "llmgateway"));
}

module.exports = {
  isPythonRuntimeInstalled,
  packageMetadata,
  pythonEnv,
  pythonSitePackagesDir,
  pythonWheelsDir,
  resolveBundledWheel,
  resolveProviderStateFile,
  resolveUserConfigFile,
  userConfigDir,
};
