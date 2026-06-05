"use strict";

const os = require("node:os");
const path = require("node:path");

const packageMetadata = Object.freeze({
  name: "llmgateway",
  version: "0.1.1",
  pythonPackage: "llmgateway",
  primaryRuntime: "python",
});

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

module.exports = {
  packageMetadata,
  resolveProviderStateFile,
  resolveUserConfigFile,
  userConfigDir,
};
