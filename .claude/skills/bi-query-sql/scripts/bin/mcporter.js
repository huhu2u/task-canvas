/**
 * mcporter.js — 跨平台 shim，macOS / Linux / Windows 均适用
 *
 * 用法：node <skill_dir>/scripts/bin/mcporter.js <args...>
 *
 * 【CatDesk 环境】把 scripts/bin/ 注入到子进程的 PATH 最前面，
 *   使 mcp-proxy 调用 open / xdg-open / powershell 时命中同目录的 shim，
 *   从而将浏览器打开请求转发给 catdesk browser-action。
 *
 * 【非 CatDesk 环境】直接透传给真正的 mcporter，不做任何 PATH 注入，
 *   mcp-proxy 仍使用系统默认的 open / xdg-open。
 *
 * 当前 shell 的 PATH 在任何情况下都不受影响。
 */

'use strict';

const { spawnSync } = require('child_process');
const path = require('path');
const fs = require('fs');

const SCRIPT_DIR = __dirname;
const IS_WIN = process.platform === 'win32';
const SEP = IS_WIN ? ';' : ':';

// ── 检测是否在 CatDesk 环境 ───────────────────────────────────────────────────
// 判据：CatDesk 启动的子进程会注入 CATPAW_CLIENT_TYPE 环境变量

function isCatDesk() {
  return !!process.env.CATPAW_CLIENT_TYPE;
}

// ── 找到真正的 mcporter（跳过 bin/ 目录自身，避免递归）──────────────────────

function findReal() {
  const dirs = (process.env.PATH || '').split(SEP);
  const exts = IS_WIN ? ['.cmd', '.exe', ''] : [''];

  for (const dir of dirs) {
    if (path.resolve(dir) === path.resolve(SCRIPT_DIR)) continue;
    for (const ext of exts) {
      const bin = path.join(dir, `mcporter${ext}`);
      try { fs.accessSync(bin, fs.constants.X_OK); return bin; } catch (_) {}
    }
  }
  return null;
}

const real = findReal();
if (!real) {
  process.stderr.write('[mcporter-shim] ERROR: real mcporter not found in PATH\n');
  process.exit(1);
}

// ── 构造子进程环境：CatDesk 下注入 bin/，否则原样透传 ────────────────────────

const childEnv = isCatDesk()
  ? {
      ...process.env,
      PATH: [
        SCRIPT_DIR,
        ...(process.env.PATH || '').split(SEP).filter(d => path.resolve(d) !== path.resolve(SCRIPT_DIR)),
      ].join(SEP),
    }
  : process.env;

// ── 启动 ──────────────────────────────────────────────────────────────────────

const result = spawnSync(real, process.argv.slice(2), {
  env: childEnv,
  stdio: 'inherit',
  shell: false,
});

process.exit(result.status ?? 1);
