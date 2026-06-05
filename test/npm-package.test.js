"use strict";

const assert = require("node:assert/strict");
const path = require("node:path");
const test = require("node:test");

const {
  packageMetadata,
  resolveProviderStateFile,
  resolveUserConfigFile,
  userConfigDir,
} = require("../index.js");

test("exports package metadata", () => {
  assert.equal(packageMetadata.name, "@seemseam/llmgateway");
  assert.equal(packageMetadata.version, "0.1.1");
  assert.equal(packageMetadata.primaryRuntime, "python");
});

test("resolves default config paths", () => {
  const home = path.resolve("/tmp/llmgateway-home");
  assert.equal(userConfigDir({}, home), path.join(home, ".llmgateway"));
  assert.equal(resolveUserConfigFile({}, home), path.join(home, ".llmgateway", "config.yaml"));
  assert.equal(
    resolveProviderStateFile({}, home),
    path.join(home, ".llmgateway", "provider-state.json"),
  );
});

test("honors explicit environment overrides", () => {
  const env = {
    LLMGATEWAY_CONFIG: "/tmp/custom-config.yaml",
    LLMGATEWAY_PROVIDER_STATE: "/tmp/custom-provider-state.json",
    LLMGATEWAY_USER_CONFIG_DIR: "/tmp/custom-dir",
  };
  assert.equal(userConfigDir(env), path.resolve("/tmp/custom-dir"));
  assert.equal(resolveUserConfigFile(env), path.resolve("/tmp/custom-config.yaml"));
  assert.equal(resolveProviderStateFile(env), path.resolve("/tmp/custom-provider-state.json"));
});
