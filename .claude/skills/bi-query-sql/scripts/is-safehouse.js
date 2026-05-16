#!/usr/bin/env node
/**
 * is-safehouse.js — 检测会话是否处于安全屋模式（跨平台版，替代 is-safehouse.sh）
 *
 * 用法:
 *   node is-safehouse.js                # UI 当前显示的会话
 *   node is-safehouse.js <session-id>   # 指定会话
 *   node is-safehouse.js --all          # 列出所有会话的安全屋状态
 *
 * 退出码:  0 = 安全屋   1 = 普通模式   2 = 检测失败
 */

"use strict";

const http = require("http");
const fs   = require("fs");
const path = require("path");
const os   = require("os");

// ─── DevToolsActivePort 路径（跨平台）────────────────────────────────────────

function getPortFilePath() {
  switch (process.platform) {
    case "win32":
      // Windows: %APPDATA%\catpaw-desk\DevToolsActivePort
      return path.join(process.env.APPDATA || path.join(os.homedir(), "AppData", "Roaming"),
                       "catpaw-desk", "DevToolsActivePort");
    case "linux":
      // Linux: ~/.config/catpaw-desk/DevToolsActivePort
      return path.join(os.homedir(), ".config", "catpaw-desk", "DevToolsActivePort");
    default:
      // macOS
      return path.join(os.homedir(), "Library", "Application Support",
                       "catpaw-desk", "DevToolsActivePort");
  }
}

// ─── 读取 DevTools 端口 ───────────────────────────────────────────────────────

function readPort() {
  const portFile = getPortFilePath();
  try {
    const content = fs.readFileSync(portFile, "utf8");
    const port = content.split("\n")[0].trim();
    if (!port || isNaN(Number(port))) throw new Error("invalid port");
    return Number(port);
  } catch (e) {
    throw new Error(`CatPaw Desk 未运行或端口文件不存在: ${getPortFilePath()}`);
  }
}

// ─── HTTP GET（替代 curl）────────────────────────────────────────────────────

function httpGet(url) {
  return new Promise((resolve, reject) => {
    const req = http.get(url, { timeout: 5000 }, (res) => {
      let data = "";
      res.on("data", chunk => data += chunk);
      res.on("end", () => resolve(data));
    });
    req.on("error", reject);
    req.on("timeout", () => { req.destroy(); reject(new Error("HTTP timeout")); });
  });
}

// ─── 获取 CatPaw Desk 的 WebSocket 调试地址 ──────────────────────────────────

async function getWsUrl(port) {
  const raw = await httpGet(`http://127.0.0.1:${port}/json/list`);
  const pages = JSON.parse(raw);
  const page = pages.find(p => p.type === "page" && (p.title || "").includes("Desk"));
  if (!page) throw new Error("找不到 CatPaw Desk 页面");
  return page.webSocketDebuggerUrl;
}

// ─── CDP WebSocket 执行器 ─────────────────────────────────────────────────────
// Node.js v22+ 内置 WebSocket；低版本回退到 net 模块手动实现 WS 握手

function cdpEval(wsUrl, expression) {
  return new Promise((resolve, reject) => {
    const timeout = setTimeout(() => reject(new Error("CDP timeout")), 8000);

    // 解析 ws:// URL
    const url = new URL(wsUrl);
    const host = url.hostname;
    const port = Number(url.port) || 80;
    const wsPath = url.pathname + (url.search || "");

    const net = require("net");
    const crypto = require("crypto");
    const key = crypto.randomBytes(16).toString("base64");

    const socket = net.createConnection(port, host, () => {
      // WebSocket 握手
      socket.write(
        `GET ${wsPath} HTTP/1.1\r\n` +
        `Host: ${host}:${port}\r\n` +
        `Upgrade: websocket\r\n` +
        `Connection: Upgrade\r\n` +
        `Sec-WebSocket-Key: ${key}\r\n` +
        `Sec-WebSocket-Version: 13\r\n\r\n`
      );
    });

    let handshakeDone = false;
    let buf = Buffer.alloc(0);
    let seq = 1;

    socket.on("data", (chunk) => {
      buf = Buffer.concat([buf, chunk]);

      if (!handshakeDone) {
        const headerEnd = buf.indexOf("\r\n\r\n");
        if (headerEnd === -1) return;
        handshakeDone = true;
        buf = buf.slice(headerEnd + 4);

        // 发送 Runtime.enable + Runtime.evaluate
        const send = (obj) => {
          const payload = Buffer.from(JSON.stringify(obj));
          const frame = Buffer.alloc(2 + 4 + payload.length);
          frame[0] = 0x81; // FIN + text frame
          frame[1] = 0x80 | payload.length; // MASK bit + length (假设 < 126 字节)
          // 对于较长的 payload 需要扩展长度字段
          if (payload.length > 125) {
            const frame2 = Buffer.alloc(2 + 2 + 4 + payload.length);
            frame2[0] = 0x81;
            frame2[1] = 0x80 | 126;
            frame2.writeUInt16BE(payload.length, 2);
            const mask = crypto.randomBytes(4);
            mask.copy(frame2, 4);
            for (let i = 0; i < payload.length; i++) {
              frame2[8 + i] = payload[i] ^ mask[i % 4];
            }
            socket.write(frame2);
            return;
          }
          const mask = crypto.randomBytes(4);
          mask.copy(frame, 2);
          for (let i = 0; i < payload.length; i++) {
            frame[6 + i] = payload[i] ^ mask[i % 4];
          }
          socket.write(frame);
        };

        send({ id: 1, method: "Runtime.enable" });
        send({ id: 2, method: "Runtime.evaluate", params: {
          returnByValue: true,
          awaitPromise: true,
          expression,
        }});
        return;
      }

      // 解析 WebSocket 帧
      while (buf.length >= 2) {
        const b1 = buf[0], b2 = buf[1];
        const masked = (b2 & 0x80) !== 0;
        let payloadLen = b2 & 0x7f;
        let offset = 2;

        if (payloadLen === 126) {
          if (buf.length < 4) return;
          payloadLen = buf.readUInt16BE(2);
          offset = 4;
        } else if (payloadLen === 127) {
          if (buf.length < 10) return;
          payloadLen = Number(buf.readBigUInt64BE(2));
          offset = 10;
        }

        if (masked) offset += 4;
        if (buf.length < offset + payloadLen) return;

        const frameData = buf.slice(offset, offset + payloadLen);
        buf = buf.slice(offset + payloadLen);

        const opcode = b1 & 0x0f;
        if (opcode === 0x1 || opcode === 0x0) { // text or continuation
          try {
            const msg = JSON.parse(frameData.toString("utf8"));
            if (msg.id === 2) {
              clearTimeout(timeout);
              socket.destroy();
              resolve(msg.result?.result?.value ?? "");
            }
          } catch (_) {}
        }
      }
    });

    socket.on("error", (e) => { clearTimeout(timeout); reject(e); });
    socket.on("close", () => { clearTimeout(timeout); });
  });
}

// ─── 主逻辑 ──────────────────────────────────────────────────────────────────

async function main() {
  const arg = process.argv[2] || "";

  let port, wsUrl;
  try {
    port  = readPort();
    wsUrl = await getWsUrl(port);
  } catch (e) {
    process.stderr.write(`⚠ ${e.message}\n`);
    process.exit(2);
  }

  // ── --all 模式 ────────────────────────────────────────────────────────────
  if (arg === "--all" || arg === "-a") {
    let result;
    try {
      result = await cdpEval(wsUrl, `
        (async function(){
          const api = window.electronAPI;
          const [sessions, currentId] = await Promise.all([
            api.getSessions(),
            api.uiGetCurrentSessionId()
          ]);
          return JSON.stringify(sessions.map(s => ({
            id: s.id,
            name: (s.title || s.name || "").slice(0, 40),
            sandbox: !!(s.enableSafeHouse ?? s.sandboxMode),
            status: s.status,
            current: s.id === currentId
          })));
        })()
      `);
    } catch (e) {
      process.stderr.write(`⚠ CDP 执行失败: ${e.message}\n`);
      process.exit(2);
    }

    let sessions;
    try { sessions = JSON.parse(result); } catch (_) {
      process.stderr.write("⚠ 解析结果失败\n");
      process.exit(2);
    }

    const safeCount = sessions.filter(s => s.sandbox).length;
    process.stdout.write(`\n  共 ${sessions.length} 个会话，${safeCount} 个安全屋\n\n`);
    for (const s of sessions) {
      const icon   = s.sandbox ? "🛡" : " ○";
      const cur    = s.current ? " ◀" : "";
      const name   = (s.name || "(未命名)").padEnd(36).slice(0, 36);
      const status = (s.status || "").padEnd(8).slice(0, 8);
      process.stdout.write(`  ${icon}  ${name}  ${status}${cur}\n`);
    }
    process.stdout.write("\n");
    process.exit(0);
  }

  // ── 单会话检测 ────────────────────────────────────────────────────────────
  const targetId = arg;
  let result;
  try {
    result = await cdpEval(wsUrl, `
      (async function(){
        const api = window.electronAPI;
        if (!api) return JSON.stringify({ error: 'no electronAPI' });
        const [sessions, uiCurrentId] = await Promise.all([
          api.getSessions(),
          api.uiGetCurrentSessionId()
        ]);
        const targetId = ${JSON.stringify(targetId)} || uiCurrentId;
        const target = sessions.find(s => s.id === targetId);
        if (!target) return JSON.stringify({ error: 'session not found: ' + targetId });
        return JSON.stringify({
          id: target.id,
          name: (target.title || target.name || '').slice(0, 50),
          sandboxMode: !!(target.enableSafeHouse ?? target.sandboxMode),
          status: target.status,
          isUiCurrent: target.id === uiCurrentId,
          total: sessions.length,
          safehouseCount: sessions.filter(s => s.enableSafeHouse ?? s.sandboxMode).length
        });
      })()
    `);
  } catch (e) {
    process.stderr.write(`⚠ CDP 执行失败: ${e.message}\n`);
    process.exit(2);
  }

  if (!result) {
    process.stderr.write("⚠ 读取失败\n");
    process.exit(2);
  }

  let data;
  try { data = JSON.parse(result); } catch (_) {
    process.stderr.write("⚠ 解析结果失败\n");
    process.exit(2);
  }

  if (data.error) {
    process.stderr.write(`⚠ ${data.error}\n`);
    process.exit(2);
  }

  const label = data.isUiCurrent ? "（UI 当前显示）" : "";

  if (data.sandboxMode) {
    process.stdout.write(`🛡  安全屋: ON  公司自部署模型 · 对话不出域\n`);
    if (data.name) process.stdout.write(`   会话: ${data.name} ${label}\n`);
    process.stdout.write(`   ${data.safehouseCount}/${data.total} 个会话为安全屋模式\n`);
    process.exit(0);
  } else {
    process.stdout.write(`○  安全屋: OFF\n`);
    if (data.name) process.stdout.write(`   会话: ${data.name} ${label}\n`);
    process.stdout.write(`   ${data.safehouseCount}/${data.total} 个会话为安全屋模式\n`);
    process.exit(1);
  }
}

main().catch(e => {
  process.stderr.write(`⚠ 未预期错误: ${e.message}\n`);
  process.exit(2);
});
