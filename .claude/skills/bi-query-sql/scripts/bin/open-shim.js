/**
 * open-shim.js — 跨平台 open/xdg-open/powershell 劫持脚本
 *
 * 将 mcp-proxy 触发的浏览器打开请求转发给 catdesk browser-action。
 *
 * 支持三种调用模式：
 *   macOS:   open <url> [flags]
 *   Linux:   xdg-open <url>
 *   Windows: powershell -EncodedCommand <base64>   ← mcp-proxy 在 win32 上的调用方式
 */

const { execFileSync } = require('child_process');
const path = require('path');
const os = require('os');

// ── catdesk 可执行文件路径 ──────────────────────────────────────────────────
const CATDESK = process.env.CATDESK_BIN
  || (process.platform === 'win32'
    ? path.join(os.homedir(), '.catpaw', 'bin', 'catdesk.exe')
    : path.join(os.homedir(), '.catpaw', 'bin', 'catdesk'));

// ── 参数解析 ───────────────────────────────────────────────────────────────
const args = process.argv.slice(2);
const invokedAs = path.basename(process.argv[1]).replace(/\.(js|cmd|exe)$/i, '');

let url = null;

if (invokedAs === 'powershell' || invokedAs === 'powershell.exe') {
  // Windows 模式：mcp-proxy 传入 -EncodedCommand <base64>
  const encIdx = args.findIndex(a => /^-EncodedCommand$/i.test(a));
  if (encIdx !== -1 && args[encIdx + 1]) {
    try {
      const decoded = Buffer.from(args[encIdx + 1], 'base64').toString('utf16le');
      const match = decoded.match(/https?:\/\/[^\s'"]+/);
      if (match) url = match[0];
    } catch (e) {
      // ignore decode error
    }
  }
  // 兜底：直接在所有参数里找 URL
  if (!url) {
    const raw = args.join(' ');
    const match = raw.match(/https?:\/\/[^\s'"]+/);
    if (match) url = match[0];
  }
} else {
  // macOS / Linux 模式：open <url> [flags] 或 xdg-open <url>
  const skipNextFlags = new Set(['-a', '-e', '-f']);
  let skipNext = false;
  for (const arg of args) {
    if (skipNext) { skipNext = false; continue; }
    if (skipNextFlags.has(arg)) { skipNext = true; continue; }
    if (arg.startsWith('-')) continue;
    url = arg;
    break;
  }
}

// ── 执行 ───────────────────────────────────────────────────────────────────
if (!url) {
  process.stderr.write(`[open-shim] Could not extract URL from args: ${args.join(' ')}\n`);
  process.exit(1);
}

process.stderr.write(`[open-shim] Forwarding to catdesk browser-action: ${url}\n`);

try {
  execFileSync(CATDESK, ['browser-action', JSON.stringify({ action: 'navigate', url })], {
    stdio: ['ignore', 'inherit', 'inherit'],
  });
} catch (e) {
  process.stderr.write(`[open-shim] catdesk browser-action failed: ${e.message}\n`);
  process.exit(1);
}
