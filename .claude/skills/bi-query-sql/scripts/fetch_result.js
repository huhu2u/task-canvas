#!/usr/bin/env node
/**
 * fetch_result.js — 轮询 Talos 查询状态 + 拉取结果 + 落盘 CSV（路径 B）或返回全量数据（路径 A）
 *
 * 用法：
 *   node fetch_result.js <qid> <output_path> [options]
 *
 * 参数：
 *   qid           Talos 查询 ID
 *   output_path   CSV 输出路径（路径 B 时使用；路径 A 小结果集不落盘）
 *
 * 选项：
 *   --batch-size <n>        初始分批大小，默认 500
 *   --timeout <s>           最大等待秒数，默认 300
 *   --small-threshold <n>   ≤ 此行数走路径 A（全量返回），默认 100
 *
 * stdout 输出一行 JSON（供 LLM 解析）：
 *   成功路径 A：{ "status":"ok","path":"A","total":N,"columns":[...],"rows":[[...],...],"elapsed":N }
 *   成功路径 B：{ "status":"ok","path":"B","total":N,"columns":[...],"outputPath":"...","sizeKB":N,"preview":[[...],...],"elapsed":N }
 *   失败：      { "status":"error","reason":"FAILED|KILLED|TIMEOUT|...","message":"..." }
 *
 * 实现说明：
 *   mcporter 在 pipe 模式下捕获 stdout 会截断大结果输出，
 *   因此 get_query_result 通过 spawnSync + stdio 文件重定向写临时文件后再由 Node 读取解析，
 *   get_query_info 数据量小，直接用 spawnSync 捕获 stdout 即可。
 *   两处 JSON 解析均有容错逻辑，兼容 mcporter 输出前带有 warning/ANSI 颜色码的情况。
 */

"use strict";

const { spawnSync } = require("child_process");
const fs   = require("fs");
const path = require("path");

// mcporter shim 路径
const MCPORTER_JS = path.join(__dirname, "bin", "mcporter.js");

// ─── 参数解析 ────────────────────────────────────────────────────────────────

const args = process.argv.slice(2);
const qid        = args[0];

if (!qid) {
  process.stderr.write("Usage: node fetch_result.js <qid> [--batch-size N] [--timeout N] [--small-threshold N] [--work-dir <path>]\n");
  process.exit(1);
}

function getOpt(name, def) {
  const i = args.indexOf(name);
  return i !== -1 && args[i + 1] ? Number(args[i + 1]) : def;
}

const INIT_BATCH_SIZE = getOpt("--batch-size", 500);
const TIMEOUT_SEC     = getOpt("--timeout", 300);
const SMALL_THRESHOLD = getOpt("--small-threshold", 100);
const WORK_DIR = (() => {
  const i = args.indexOf("--work-dir");
  if (i !== -1 && args[i+1]) return args[i+1];
  return process.cwd();
})();
const BI_DIR = path.join(WORK_DIR, "bi-query-sql");
const outputPath = path.join(BI_DIR, `query_result_${qid.slice(0, 8)}.csv`);
const MIN_BATCH_SIZE  = 10;

const startTime = Date.now();

// ─── mcporter 调用 ────────────────────────────────────────────────────────────

/**
 * 使用 spawnSync 调用 mcporter，避免跨平台 shell 引号差异。
 * get_query_info：数据量小，可以直接捕获 stdout。
 */
function callDirect(expr) {
  const result = spawnSync("node", [MCPORTER_JS, "call", expr], {
    encoding: "utf8",
    timeout: 30000,
    maxBuffer: 8 * 1024 * 1024,
  });
  if (result.error) throw result.error;
  const raw = result.stdout || "";
  // 先直接尝试，失败则找首尾 {}
  try { return JSON.parse(raw.trim()); } catch (_) {}
  const s = raw.indexOf("{"), e = raw.lastIndexOf("}");
  if (s === -1 || e === -1 || e <= s) throw new Error("No JSON in output: " + raw.slice(0, 200));
  return JSON.parse(raw.slice(s, e + 1));
}

/**
 * get_query_result：数据量大，mcporter 在 pipe 模式下会截断输出。
 * 通过 spawnSync 将 stdout 直接写入临时文件，再由 Node 读文件解析。
 * 使用 spawnSync + stdio 文件重定向，完全绕开 shell 引号差异。
 */
function callViaFile(expr) {
  const tmpDir = path.join(BI_DIR, ".tmp");
  fs.mkdirSync(tmpDir, { recursive: true });
  const tmpFile = path.join(tmpDir, `mcp_${Date.now()}_${Math.random().toString(36).slice(2)}.json`);
  try {
    // 打开文件描述符作为 stdout 目标，完全不经过 shell
    const fd = fs.openSync(tmpFile, "w");
    const result = spawnSync("node", [MCPORTER_JS, "call", expr], {
      timeout: 60000,
      stdio: ["ignore", fd, "ignore"],
    });
    fs.closeSync(fd);
    if (result.error) throw result.error;
    const raw = fs.readFileSync(tmpFile, "utf8");
    // 与 callDirect 保持一致：先直接尝试，失败则找首尾 {}（兼容 mcporter 输出前有 warning/ANSI 颜色码的情况）
    try { return JSON.parse(raw.trim()); } catch (_) {}
    const s = raw.indexOf("{"), e = raw.lastIndexOf("}");
    if (s === -1 || e === -1 || e <= s) throw new Error("No JSON in output: " + raw.slice(0, 200));
    return JSON.parse(raw.slice(s, e + 1));
  } finally {
    try { fs.unlinkSync(tmpFile); } catch (_) {}
  }
}

// ─── 轮询状态 ────────────────────────────────────────────────────────────────

function pollIntervalMs(elapsed) {
  if (elapsed < 10)  return 1000;
  if (elapsed < 30)  return 3000;
  if (elapsed < 60)  return 5000;
  if (elapsed < 300) return 10000;
  return 20000;
}

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

async function pollUntilDone() {
  while (true) {
    const elapsed = (Date.now() - startTime) / 1000;
    if (elapsed > TIMEOUT_SEC) {
      return { status: "error", reason: "TIMEOUT", message: `Query did not finish within ${TIMEOUT_SEC}s` };
    }

    const res = callDirect(`hive.get_query_info(qid: "${qid}")`);
    if (res.code !== 1) {
      return { status: "error", reason: "API_ERROR", message: res.message || JSON.stringify(res) };
    }

    const d     = res.data;
    const state = (d.status || "").trim();

    if (state === "FINISHED") {
      const total   = d.total ?? 0;
      const columns = (d.resultTableColumns || d.columns || []).map(c => c.name);
      return { status: "ok", total, columns };
    }
    if (state === "FAILED") {
      return { status: "error", reason: "FAILED", message: d.failReason || "Query FAILED" };
    }
    if (state === "KILLED") {
      return { status: "error", reason: "KILLED", message: "Query was KILLED" };
    }

    process.stderr.write(`[poll] status=${state} elapsed=${elapsed.toFixed(0)}s\n`);
    await sleep(pollIntervalMs(elapsed));
  }
}

// ─── 获取一批结果行 ───────────────────────────────────────────────────────────

function fetchBatch(offset, length) {
  const res = callViaFile(`hive.get_query_result(qid: "${qid}", offset: ${offset}, length: ${length})`);

  if (res.code === -1) {
    const msg = String(res.message || "");
    if (msg.includes("超过1MB限制")) {
      const e = new Error("超过1MB限制");
      e.limitHit = true;
      throw e;
    }
    throw new Error(msg || "get_query_result failed");
  }
  if (res.code !== 1) {
    throw new Error(res.message || "get_query_result unknown error");
  }

  // data.data 是序列化 JSON 字符串，需要二次 parse
  let inner = res?.data?.data ?? "{}";
  if (typeof inner === "string") inner = JSON.parse(inner);
  return inner?.data?.data ?? [];
}

// ─── CSV 工具 ─────────────────────────────────────────────────────────────────

function csvCell(val) {
  const s = val === null || val === undefined ? "" : String(val);
  if (s.includes(",") || s.includes('"') || s.includes("\n") || s.includes("\r")) {
    return '"' + s.replace(/"/g, '""') + '"';
  }
  return s;
}
function csvRow(cells) { return cells.map(csvCell).join(","); }

// ─── 路径 A：小结果集，全量返回（不落盘）────────────────────────────────────

async function fetchSmall(total, columns) {
  let rows;
  try {
    rows = fetchBatch(0, total);
  } catch (e) {
    if (e.limitHit) return null; // 降级到路径 B
    return { status: "error", reason: "FETCH_ERROR", message: e.message };
  }
  const elapsed = ((Date.now() - startTime) / 1000).toFixed(1);
  return { status: "ok", path: "A", total, columns, rows, elapsed: Number(elapsed) };
}

// ─── 路径 B：大结果集，分批落盘 ──────────────────────────────────────────────

async function fetchLarge(total, columns, initBatch) {
  const outDir = path.dirname(path.resolve(outputPath));
  fs.mkdirSync(outDir, { recursive: true });

  const out = fs.createWriteStream(outputPath, { encoding: "utf8" });
  out.write("\uFEFF" + csvRow(columns) + "\n"); // UTF-8 BOM

  let batchSize = initBatch;
  let offset    = 0;
  let written   = 0;
  const preview = [];

  while (offset < total) {
    let rows;
    const remaining = total - offset;
    const thisLength = Math.min(batchSize, remaining);

    while (true) {
      try {
        rows = fetchBatch(offset, thisLength);
        break;
      } catch (e) {
        if (e.limitHit) {
          const next = Math.max(MIN_BATCH_SIZE, Math.floor(batchSize / 2));
          if (next === batchSize) {
            return { status: "error", reason: "BATCH_TOO_LARGE", message: `Single row exceeds 1MB at offset ${offset}` };
          }
          process.stderr.write(`[batch] 1MB limit, reducing: ${batchSize} → ${next}\n`);
          batchSize = next;
          continue;
        }
        return { status: "error", reason: "FETCH_ERROR", message: e.message };
      }
    }

    if (rows.length === 0) break;

    for (const row of rows) {
      out.write(csvRow(row) + "\n");
      if (preview.length < 10) preview.push(row);
    }

    written += rows.length;
    offset  += rows.length;

    if (written % 1000 === 0 || offset >= total) {
      process.stderr.write(`[fetch] ${written}/${total} rows written\n`);
    }
  }

  await new Promise(r => out.end(r));

  const sizeKB  = (fs.statSync(outputPath).size / 1024).toFixed(1);
  const elapsed = ((Date.now() - startTime) / 1000).toFixed(1);

  return {
    status: "ok",
    path: "B",
    total: written,
    columns,
    outputPath: path.resolve(outputPath),
    sizeKB: Number(sizeKB),
    preview,
    elapsed: Number(elapsed)
  };
}

// ─── 主入口 ──────────────────────────────────────────────────────────────────

async function main() {
  const poll = await pollUntilDone();
  if (poll.status !== "ok") {
    process.stdout.write(JSON.stringify(poll) + "\n");
    process.exit(0);
  }

  const { total, columns } = poll;

  let result;
  if (total <= SMALL_THRESHOLD) {
    result = await fetchSmall(total, columns);
    if (result === null) {
      result = await fetchLarge(total, columns, Math.min(total, 50));
    }
  } else {
    const initBatch = columns.length > 30 ? 200 : INIT_BATCH_SIZE;
    result = await fetchLarge(total, columns, initBatch);
  }

  process.stdout.write(JSON.stringify(result) + "\n");
  process.exit(result.status === "ok" ? 0 : 1);
}

main().catch(e => {
  process.stdout.write(JSON.stringify({ status: "error", reason: "UNEXPECTED", message: e.message }) + "\n");
  process.exit(1);
});
