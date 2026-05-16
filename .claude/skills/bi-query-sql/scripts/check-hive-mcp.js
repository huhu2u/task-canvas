#!/usr/bin/env node
/**
 * check-hive-mcp.js — 检查 mcporter 安装状态 + hive MCP Server 可用性
 *
 * 用法：node <skill_dir>/scripts/check-hive-mcp.js
 *
 * 退出码：
 *   0  — 可用（mcporter 已安装，hive server 已注册且 tools 正常）
 *   1  — 不可用（mcporter 未安装 / hive 未注册 / token 过期 / 超时 / 其他异常）
 *   2  — mcporter 未安装，已自动安装成功，但需重新运行本脚本确认
 *
 * stdout 只输出一行简洁状态，不打印完整 tool 列表，节省 token。
 * 兼容 macOS / Linux / Windows。
 */

'use strict';

const { spawnSync } = require('child_process');
const path = require('path');
const fs = require('fs');

const SCRIPT_DIR = __dirname;
const IS_WIN = process.platform === 'win32';
const SEP = IS_WIN ? ';' : ':';
const MCPORTER_SHIM = path.join(SCRIPT_DIR, 'bin', 'mcporter.js');

// ── Step 1: 检查 mcporter 是否已安装 ─────────────────────────────────────────
//
// Windows 注意事项：
//   - .cmd 文件不具备 X_OK 权限位，需用 F_OK 检测文件存在即可
//   - 优先检查 .cmd（npm 全局安装产物），再检查 .exe，最后检查无扩展名

function findMcporter() {
  const dirs = (process.env.PATH || '').split(SEP);
  // Windows 优先 .cmd（npm 全局安装的入口），再 .exe，再无扩展名
  const exts = IS_WIN ? ['.cmd', '.exe', ''] : [''];
  // Windows 用 F_OK（只判断文件存在），Unix 用 X_OK（判断可执行）
  const accessFlag = IS_WIN ? fs.constants.F_OK : fs.constants.X_OK;

  for (const dir of dirs) {
    if (!dir) continue;
    // 跳过 bin/ shim 目录自身，避免递归
    if (path.resolve(dir) === path.resolve(SCRIPT_DIR)) continue;
    for (const ext of exts) {
      const bin = path.join(dir, `mcporter${ext}`);
      try { fs.accessSync(bin, accessFlag); return bin; } catch (_) {}
    }
  }
  return null;
}

if (!findMcporter()) {
  process.stdout.write('mcporter 未安装，正在执行 npm install -g mcporter ...\n');
  // Windows 上 npm 是 npm.cmd，必须通过 shell 调用；Unix 直接调用即可
  const install = spawnSync(
    IS_WIN ? 'npm.cmd' : 'npm',
    ['install', '-g', 'mcporter'],
    {
      encoding: 'utf8',
      timeout: 120_000,
      // Windows 下 shell:true 作为兜底，防止某些环境 npm.cmd 仍找不到
      shell: IS_WIN,
    }
  );
  if (install.status !== 0) {
    const raw = ((install.stderr || '') + (install.stdout || '')).trim();
    const err = raw.split('\n').map(l => l.trim()).find(l => l.length > 0) || '安装失败';
    const hint = err.length > 120 ? err.slice(0, 120) + '…' : err;
    process.stdout.write(`mcporter 安装失败：${hint}\n`);
    process.exit(1);
  }
  process.stdout.write('mcporter 安装成功，请重新运行本脚本以继续检查。\n');
  process.exit(2);
}

// ── Step 2: 执行 mcporter list hive，捕获全部输出 ─────────────────────────────

const result = spawnSync(process.execPath, [MCPORTER_SHIM, 'list', 'hive'], {
  encoding: 'utf8',
  timeout: 60_000,
});

const stdout = (result.stdout || '').trim();
const stderr = (result.stderr || '').trim();
const combined = stdout + '\n' + stderr;

// ── Step 3: 判断是否可用 ──────────────────────────────────────────────────────
// 可用标志：输出中包含 "N tools"（N >= 1）
const toolsMatch = combined.match(/(\d+)\s+tools/);
const toolCount = toolsMatch ? parseInt(toolsMatch[1], 10) : 0;

// 不可用关键词
const UNAVAILABLE_PATTERNS = [
  /tools\s+unavailable/i,
  /token\s+error/i,
  /timed?\s*out/i,
  /not\s+found/i,
  /unknown\s+mcp\s+server/i,
  /error:/i,
  /failed/i,
];

const hasUnavailableSignal = UNAVAILABLE_PATTERNS.some(p => p.test(combined));

if (toolCount > 0 && !hasUnavailableSignal) {
  process.stdout.write(`hive MCP 可用（${toolCount} tools）\n`);
  process.exit(0);
} else {
  // 提取关键错误信息（取第一行非空内容，最多 120 字符）
  const firstLine = combined
    .split('\n')
    .map(l => l.trim())
    .find(l => l.length > 0) || '未知错误';
  const hint = firstLine.length > 120 ? firstLine.slice(0, 120) + '…' : firstLine;
  process.stdout.write(`hive MCP 不可用：${hint}\n`);
  process.exit(1);
}
