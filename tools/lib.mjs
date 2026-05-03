import { existsSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { spawnSync, spawn } from "node:child_process";

export const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..");
export const isWindows = process.platform === "win32";
export const venvDir = resolve(ROOT, ".venv");
export const venvPython = isWindows
  ? resolve(venvDir, "Scripts", "python.exe")
  : resolve(venvDir, "bin", "python");
export const textualCommand = isWindows
  ? resolve(venvDir, "Scripts", "textual.exe")
  : resolve(venvDir, "bin", "textual");
export const markerFile = resolve(venvDir, ".slm-learning-setup-ok");

export function run(command, args, options = {}) {
  const result = spawnSync(command, args, {
    cwd: ROOT,
    stdio: "inherit",
    shell: false,
    ...options,
  });
  if (result.error) {
    throw result.error;
  }
  if (result.status !== 0) {
    const printable = [command, ...args].join(" ");
    throw new Error(`Command failed with exit code ${result.status}: ${printable}`);
  }
}

export function runAllowFailure(command, args, options = {}) {
  const result = spawnSync(command, args, {
    cwd: ROOT,
    stdio: "inherit",
    shell: false,
    ...options,
  });
  return result.status === 0;
}

export function spawnInteractive(command, args, options = {}) {
  const child = spawn(command, args, {
    cwd: ROOT,
    stdio: "inherit",
    shell: false,
    ...options,
  });

  child.on("exit", (code, signal) => {
    if (signal) {
      process.kill(process.pid, signal);
      return;
    }
    process.exit(code ?? 0);
  });
}

export function findSystemPython() {
  const candidates = [];
  if (process.env.PYTHON) candidates.push(process.env.PYTHON);
  if (isWindows) {
    candidates.push("py", "python");
  } else {
    candidates.push("python3", "python");
  }

  for (const candidate of candidates) {
    const args = candidate === "py" ? ["-3", "--version"] : ["--version"];
    const result = spawnSync(candidate, args, {
      cwd: ROOT,
      stdio: "ignore",
      shell: false,
    });
    if (result.status === 0) return candidate;
  }

  throw new Error("Could not find Python. Install Python 3.11 or 3.12, or set the PYTHON environment variable.");
}

export function createVenvArgs(pythonCommand) {
  if (pythonCommand === "py") {
    return ["-3", "-m", "venv", ".venv"];
  }
  return ["-m", "venv", ".venv"];
}

export function setupNeeded() {
  return !existsSync(venvPython) || !existsSync(markerFile) || !existsSync(textualCommand);
}
