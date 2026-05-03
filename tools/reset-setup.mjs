import { existsSync, rmSync } from "node:fs";
import { venvDir } from "./lib.mjs";

if (existsSync(venvDir)) {
  rmSync(venvDir, { recursive: true, force: true });
  console.log("Removed .venv. Run npm run dev to rebuild it.");
} else {
  console.log("No .venv found.");
}
