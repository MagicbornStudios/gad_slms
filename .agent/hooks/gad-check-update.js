#!/usr/bin/env node
// gad-hook-version: 1.35.0
// Check for GAD updates in background, write result to cache
// Called by SessionStart hook - runs once per session

const fs = require('fs');
const path = require('path');
const os = require('os');
const { spawn, execFileSync } = require('child_process');

const homeDir = os.homedir();
const cwd = process.cwd();
const cacheDir = path.join(homeDir, '.cache', 'gad');
const cacheFile = path.join(cacheDir, 'gad-update-check.json');
const legacyHookPrefix = ['g', 's', 'd', '-'].join('');
const legacyVersionMarker = ['g', 's', 'd', '-hook-version'].join('');
const DEFAULT_RELEASE_REPO = 'MagicbornStudios/get-anything-done';

function detectConfigDir(baseDir) {
  const envDir = process.env.CLAUDE_CONFIG_DIR;
  if (envDir && fs.existsSync(path.join(envDir, 'get-anything-done', 'VERSION'))) {
    return envDir;
  }
  for (const dir of ['.config/opencode', '.opencode', '.gemini', '.agent']) {
    if (fs.existsSync(path.join(baseDir, dir, 'get-anything-done', 'VERSION'))) {
      return path.join(baseDir, dir);
    }
  }
  return envDir || path.join(baseDir, '.agent');
}

function ensureDir(dirPath) {
  if (!fs.existsSync(dirPath)) {
    fs.mkdirSync(dirPath, { recursive: true });
  }
}

function normalizeRepoSlug(value) {
  let repo = String(value || '').trim();
  if (!repo) return '';
  repo = repo
    .replace(/^git\+/, '')
    .replace(/^ssh:\/\/git@github\.com\//i, '')
    .replace(/^git@github\.com:/i, '')
    .replace(/^https?:\/\/github\.com\//i, '')
    .replace(/^github\.com\//i, '')
    .replace(/^repos\//i, '')
    .replace(/\.git$/i, '')
    .replace(/^\/+|\/+$/g, '');
  return /^[^/]+\/[^/]+$/.test(repo) ? repo : '';
}

function normalizeVersion(value) {
  return String(value || '').trim().replace(/^refs\/tags\//, '').replace(/^v/, '');
}

function parseSemver(value) {
  const match = normalizeVersion(value).match(/^(\d+)\.(\d+)\.(\d+)(?:-([0-9A-Za-z.-]+))?$/);
  if (!match) return null;
  return {
    major: Number(match[1]),
    minor: Number(match[2]),
    patch: Number(match[3]),
    prerelease: match[4] ? match[4].split('.') : [],
  };
}

function comparePrereleaseParts(left, right) {
  const leftNumeric = /^\d+$/.test(left);
  const rightNumeric = /^\d+$/.test(right);
  if (leftNumeric && rightNumeric) return Number(left) - Number(right);
  if (leftNumeric) return -1;
  if (rightNumeric) return 1;
  return left.localeCompare(right);
}

function compareVersions(left, right) {
  const a = parseSemver(left);
  const b = parseSemver(right);
  if (!a || !b) {
    return normalizeVersion(left).localeCompare(normalizeVersion(right), undefined, { numeric: true });
  }
  if (a.major !== b.major) return a.major - b.major;
  if (a.minor !== b.minor) return a.minor - b.minor;
  if (a.patch !== b.patch) return a.patch - b.patch;
  if (a.prerelease.length === 0 && b.prerelease.length === 0) return 0;
  if (a.prerelease.length === 0) return 1;
  if (b.prerelease.length === 0) return -1;
  const length = Math.max(a.prerelease.length, b.prerelease.length);
  for (let i = 0; i < length; i++) {
    const leftPart = a.prerelease[i];
    const rightPart = b.prerelease[i];
    if (leftPart == null) return -1;
    if (rightPart == null) return 1;
    const cmp = comparePrereleaseParts(leftPart, rightPart);
    if (cmp !== 0) return cmp;
  }
  return 0;
}

function listReleaseTagsFromLsRemote(output) {
  return String(output || '')
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => {
      const ref = line.split(/\s+/)[1] || '';
      return ref.replace(/^refs\/tags\//, '');
    })
    .filter((tag) => parseSemver(tag))
    .sort(compareVersions);
}

function readInstalledContext(projectVersionFile, globalVersionFile) {
  let installed = '0.0.0';
  let configDir = '';
  let runtimeRoot = '';

  try {
    if (projectVersionFile && fs.existsSync(projectVersionFile)) {
      installed = fs.readFileSync(projectVersionFile, 'utf8').trim();
      runtimeRoot = path.dirname(projectVersionFile);
      configDir = path.dirname(runtimeRoot);
    } else if (globalVersionFile && fs.existsSync(globalVersionFile)) {
      installed = fs.readFileSync(globalVersionFile, 'utf8').trim();
      runtimeRoot = path.dirname(globalVersionFile);
      configDir = path.dirname(runtimeRoot);
    }
  } catch {}

  return { installed, configDir, runtimeRoot };
}

function collectStaleHooks(configDir, installed) {
  if (!configDir) return [];
  const staleHooks = [];
  const hooksDir = path.join(configDir, 'hooks');
  try {
    if (!fs.existsSync(hooksDir)) return staleHooks;
    const hookFiles = fs.readdirSync(hooksDir).filter((file) => (file.startsWith('gad-') || file.startsWith(legacyHookPrefix)) && file.endsWith('.js'));
    for (const hookFile of hookFiles) {
      try {
        const content = fs.readFileSync(path.join(hooksDir, hookFile), 'utf8');
        const versionMatch = content.match(new RegExp(`\\/\\/ (?:gad-hook-version|${legacyVersionMarker}):\\s*(.+)`));
        if (versionMatch) {
          const hookVersion = versionMatch[1].trim();
          if (hookVersion !== installed && !hookVersion.includes('{{')) {
            staleHooks.push({ file: hookFile, hookVersion, installedVersion: installed });
          }
        } else {
          staleHooks.push({ file: hookFile, hookVersion: 'unknown', installedVersion: installed });
        }
      } catch {}
    }
  } catch {}
  return staleHooks;
}

function readReleaseRepo(runtimeRoot) {
  const envRepo = normalizeRepoSlug(process.env.GAD_RELEASE_REPO);
  if (envRepo) return envRepo;
  if (!runtimeRoot) return DEFAULT_RELEASE_REPO;
  try {
    const packageJsonPath = path.join(runtimeRoot, 'package.json');
    if (!fs.existsSync(packageJsonPath)) return DEFAULT_RELEASE_REPO;
    const pkg = JSON.parse(fs.readFileSync(packageJsonPath, 'utf8'));
    const repo = normalizeRepoSlug(
      typeof pkg.repository === 'string'
        ? pkg.repository
        : (pkg.repository && pkg.repository.url) || pkg.homepage || '',
    );
    return repo || DEFAULT_RELEASE_REPO;
  } catch {
    return DEFAULT_RELEASE_REPO;
  }
}

function getLatestReleaseTag(releaseRepo) {
  try {
    const tag = execFileSync(
      'gh',
      ['api', `repos/${releaseRepo}/releases/latest`, '--jq', '.tag_name'],
      { encoding: 'utf8', timeout: 10000, windowsHide: true },
    ).trim();
    if (tag) return tag;
  } catch {}

  try {
    const output = execFileSync(
      'git',
      ['ls-remote', '--tags', '--refs', `https://github.com/${releaseRepo}.git`],
      { encoding: 'utf8', timeout: 10000, windowsHide: true },
    ).trim();
    const tags = listReleaseTagsFromLsRemote(output);
    return tags[tags.length - 1] || '';
  } catch {}

  return '';
}

function runBackgroundCheck({ targetCacheFile, projectVersionFile, globalVersionFile }) {
  const { installed, configDir, runtimeRoot } = readInstalledContext(projectVersionFile, globalVersionFile);
  const staleHooks = collectStaleHooks(configDir, installed);
  const releaseRepo = readReleaseRepo(runtimeRoot);
  const latestTag = getLatestReleaseTag(releaseRepo);
  const latest = normalizeVersion(latestTag);

  const result = {
    update_available: Boolean(latest && compareVersions(installed, latest) < 0),
    installed,
    latest: latest || 'unknown',
    latest_tag: latestTag || undefined,
    release_repo: releaseRepo,
    checked: Math.floor(Date.now() / 1000),
    stale_hooks: staleHooks.length > 0 ? staleHooks : undefined,
  };

  fs.writeFileSync(targetCacheFile, JSON.stringify(result));
}

function spawnBackgroundCheck({ targetCacheFile, projectVersionFile, globalVersionFile }) {
  const child = spawn(
    process.execPath,
    [__filename, '--background-check'],
    {
      stdio: 'ignore',
      windowsHide: true,
      detached: true,
      env: {
        ...process.env,
        GAD_UPDATE_CACHE_FILE: targetCacheFile,
        GAD_UPDATE_PROJECT_VERSION_FILE: projectVersionFile,
        GAD_UPDATE_GLOBAL_VERSION_FILE: globalVersionFile,
      },
    },
  );
  child.unref();
}

function main() {
  const globalConfigDir = detectConfigDir(homeDir);
  const projectConfigDir = detectConfigDir(cwd);
  const projectVersionFile = path.join(projectConfigDir, 'get-anything-done', 'VERSION');
  const globalVersionFile = path.join(globalConfigDir, 'get-anything-done', 'VERSION');

  ensureDir(cacheDir);

  if (process.argv.includes('--background-check')) {
    runBackgroundCheck({
      targetCacheFile: process.env.GAD_UPDATE_CACHE_FILE || cacheFile,
      projectVersionFile: process.env.GAD_UPDATE_PROJECT_VERSION_FILE || projectVersionFile,
      globalVersionFile: process.env.GAD_UPDATE_GLOBAL_VERSION_FILE || globalVersionFile,
    });
    return;
  }

  spawnBackgroundCheck({
    targetCacheFile: cacheFile,
    projectVersionFile,
    globalVersionFile,
  });
}

if (require.main === module) {
  main();
}

module.exports = {
  compareVersions,
  listReleaseTagsFromLsRemote,
  normalizeRepoSlug,
  normalizeVersion,
};
