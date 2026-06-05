"use strict";

const fs = require("node:fs");
const path = require("node:path");

const root = path.resolve(__dirname, "..");

for (const relative of ["build", "python/wheels", "src/llmgateway.egg-info"]) {
  fs.rmSync(path.join(root, relative), {recursive: true, force: true});
}
