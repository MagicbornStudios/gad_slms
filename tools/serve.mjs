import { run, setupNeeded, spawnInteractive, textualCommand, venvPython } from "./lib.mjs";

if (setupNeeded()) {
  run("node", ["tools/setup.mjs"]);
}

spawnInteractive(textualCommand, ["serve", `${venvPython} scripts/06_learning_tui.py`]);
