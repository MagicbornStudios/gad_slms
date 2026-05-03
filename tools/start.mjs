import { run, setupNeeded, spawnInteractive, textualCommand } from "./lib.mjs";

if (setupNeeded()) {
  run("node", ["tools/setup.mjs"]);
}

spawnInteractive(textualCommand, ["run", "scripts/06_learning_tui.py"]);
