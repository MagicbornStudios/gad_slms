import { existsSync, writeFileSync } from "node:fs";
import {
  createVenvArgs,
  findSystemPython,
  markerFile,
  run,
  runAllowFailure,
  venvDir,
  venvPython,
} from "./lib.mjs";

function main() {
  const python = findSystemPython();

  if (!existsSync(venvPython)) {
    console.log(`Creating virtual environment with ${python}...`);
    run(python, createVenvArgs(python));
  } else {
    console.log(`Using existing virtual environment: ${venvDir}`);
  }

  console.log("Upgrading pip...");
  run(venvPython, ["-m", "pip", "install", "--upgrade", "pip"]);

  console.log("Installing TUI dependencies...");
  run(venvPython, ["-m", "pip", "install", "-r", "requirements-tui.txt"]);

  console.log("Installing model dependencies...");
  const modelDepsOk = runAllowFailure(venvPython, ["-m", "pip", "install", "-r", "requirements.txt"]);

  if (!modelDepsOk) {
    console.log("");
    console.log("WARNING: Model dependencies did not fully install.");
    console.log("The TUI can still run, but training may fail until PyTorch installs successfully.");
    console.log("If you are on Python 3.14, recreate the venv with Python 3.11 or 3.12.");
    console.log("");
  }

  writeFileSync(markerFile, new Date().toISOString(), "utf8");
  console.log("Setup complete.");
}

main();
