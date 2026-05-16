#!/usr/bin/env python3
"""
Prepare local analysis inputs for Moshu analysis.

Supported inputs:
- single file: upload directly
- multiple files: pack as a zip, then upload
- directory: pack as a zip, then upload
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import json
import os
import re
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from json import JSONDecodeError
from pathlib import Path
from urllib.parse import urlparse
from zipfile import ZIP_DEFLATED, ZipFile

import requests

UPLOAD_URL = os.getenv(
    "MOSHU_UPLOAD_URL",
    "https://ba-ai.sankuai.com/agent/manage/api/open-analysis/uploadFile",
)
GRAY_CELL = os.getenv("MOSHU_GRAY_CELL", "gray-release-apa-mdbi")
CLIENT_ID = os.getenv("MOSHU_CLIENT_ID", "openAnalysis")
SECRET_KEY = os.getenv("MOSHU_SECRET_KEY", "RkcbNtrFXZdQJwywGf8u")
UPLOAD_PATH = urlparse(UPLOAD_URL).path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Package local inputs when needed, upload them, and return the S3 URL."
    )
    parser.add_argument("paths", nargs="+", help="One or more local files or directories")
    parser.add_argument(
        "--archive-name",
        help="Optional archive base name when packaging directories or multiple inputs",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print machine-readable JSON only",
    )
    parser.add_argument(
        "--keep-archive",
        action="store_true",
        help="Keep the generated zip archive on disk after upload",
    )
    return parser.parse_args()


def sanitize_name(raw: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", raw.strip())
    cleaned = re.sub(r"-{2,}", "-", cleaned).strip("-_.")
    return cleaned or "analysis-input"


def resolve_paths(raw_paths: list[str]) -> list[Path]:
    resolved: list[Path] = []
    for raw in raw_paths:
        path = Path(raw).expanduser().resolve()
        if not path.exists():
            raise FileNotFoundError(f"输入路径不存在: {raw}")
        resolved.append(path)
    return resolved


def ensure_no_pdf(paths: list[Path]) -> None:
    pdf_files: list[Path] = []
    for path in paths:
        if path.is_file() and path.suffix.lower() == ".pdf":
            pdf_files.append(path)
            continue
        if path.is_dir():
            pdf_files.extend(
                item for item in path.rglob("*") if item.is_file() and item.suffix.lower() == ".pdf"
            )

    if pdf_files:
        sample = ", ".join(str(path) for path in pdf_files[:3])
        if len(pdf_files) > 3:
            sample = f"{sample} 等 {len(pdf_files)} 个 PDF"
        raise ValueError(f"当前 skill 不支持 PDF 分析，请改为提供非 PDF 数据文件。检测到: {sample}")


def infer_input_mode(paths: list[Path]) -> str:
    if len(paths) == 1 and paths[0].is_file():
        return "single-file"
    if len(paths) == 1 and paths[0].is_dir():
        return "directory"
    return "multi-input"


def timestamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def default_archive_stem(paths: list[Path]) -> str:
    if len(paths) == 1 and paths[0].is_dir():
        return f"{sanitize_name(paths[0].name)}-{timestamp()}"

    parts: list[str] = []
    for path in paths[:3]:
        name = path.stem if path.is_file() else path.name
        parts.append(sanitize_name(name))

    stem = "__".join(parts) or "analysis-input"
    if len(paths) > 3:
        stem = f"{stem}__plus-{len(paths) - 3}"
    return f"{stem[:80]}-{timestamp()}"


def iter_archive_entries(path: Path) -> list[tuple[Path, Path]]:
    if path.is_file():
        return [(path, Path(path.name))]

    files = sorted(item for item in path.rglob("*") if item.is_file())
    if not files:
        raise ValueError(f"目录为空，无法上传: {path}")

    return [(item, Path(path.name) / item.relative_to(path)) for item in files]


def uniquify_arcname(arcname: str, seen: set[str]) -> str:
    if arcname not in seen:
        seen.add(arcname)
        return arcname

    stem, suffix = os.path.splitext(arcname)
    index = 2
    while True:
        candidate = f"{stem}__{index}{suffix}"
        if candidate not in seen:
            seen.add(candidate)
            return candidate
        index += 1


def build_archive(
    paths: list[Path],
    archive_name: str | None,
) -> tuple[Path, str, Path]:
    archive_stem = sanitize_name(archive_name) if archive_name else default_archive_stem(paths)
    temp_dir = Path(tempfile.mkdtemp(prefix="moshu-analysis-input-"))
    archive_path = temp_dir / f"{archive_stem}.zip"

    seen: set[str] = set()
    file_count = 0
    with ZipFile(archive_path, "w", compression=ZIP_DEFLATED) as zip_file:
        for path in paths:
            for source_path, archive_rel in iter_archive_entries(path):
                arcname = uniquify_arcname(archive_rel.as_posix(), seen)
                zip_file.write(source_path, arcname)
                file_count += 1

    if file_count == 0:
        raise ValueError("未找到可打包的文件")

    return archive_path, archive_path.name, temp_dir


def generate_ba_auth_headers(
    method: str,
    uri: str,
    secret: str,
    client_id: str,
) -> dict[str, str]:
    date_str = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT")
    string_to_sign = f"{method.upper()} {uri}\n{date_str}"
    signature = base64.b64encode(
        hmac.new(
            secret.encode("utf-8"),
            string_to_sign.encode("utf-8"),
            hashlib.sha1,
        ).digest()
    ).decode("utf-8")
    return {
        "Date": date_str,
        "Authorization": f"MWS {client_id}:{signature}",
        "Gray-Cell": GRAY_CELL,
    }


def upload_file(file_path: str) -> list[dict[str, object]]:
    headers = generate_ba_auth_headers("POST", UPLOAD_PATH, SECRET_KEY, CLIENT_ID)
    with open(file_path, "rb") as file_handle:
        response = requests.post(
            UPLOAD_URL,
            headers=headers,
            files={"file": file_handle},
            timeout=60,
            allow_redirects=False,
        )

    if response.is_redirect or response.is_permanent_redirect:
        location = response.headers.get("location", "")
        raise RuntimeError(
            "上传被重定向到登录页。当前上传服务除了 BA 签名和 Gray-Cell 外，"
            "还依赖企业登录态/Cookie/MissID。请先完成认证，再重试上传。"
            + (f" redirect={location}" if location else "")
        )

    response.raise_for_status()
    try:
        body = response.json()
    except JSONDecodeError as exc:
        content_type = response.headers.get("content-type", "")
        body_prefix = response.text[:300].strip()
        raise RuntimeError(
            "上传接口未返回 JSON，无法解析结果。"
            f" status={response.status_code}, content_type={content_type}, body_prefix={body_prefix}"
        ) from exc

    if body.get("code") != 0:
        raise RuntimeError(
            f"上传接口返回错误: code={body.get('code')}, message={body.get('message')}"
        )

    results = body.get("data") or []
    if not results:
        raise RuntimeError("上传接口未返回 data")
    return results


def build_summary(
    input_mode: str,
    upload_target: Path,
    upload_result: dict[str, object],
    packaged: bool,
    source_paths: list[Path],
) -> dict[str, object]:
    s3_url = str(upload_result.get("s3Url", ""))
    file_name = str(upload_result.get("fileName") or upload_target.name)
    return {
        "input_mode": input_mode,
        "packaged": packaged,
        "source_paths": [str(path) for path in source_paths],
        "file_name": file_name,
        "s3_url": s3_url,
        "next_step": (
            "使用该 s3_url 继续执行分析流程；先检查当前环境实际已连接可用的 MCP server 名，"
            "优先使用已连接的 sdk-mtbi_ai，若其 not connected 或 status error，"
            "则回退到已连接的 mtbi_ai；调用 data_analysis_tool 时，"
            f"将 fileList 设为 [{{\"s3Url\":\"{s3_url}\",\"fileName\":\"{file_name}\"}}]。"
        ),
    }


def print_human_summary(summary: dict[str, object]) -> None:
    print("输入整理完成")
    print(f"- 输入类型: {summary['input_mode']}")
    print(f"- 是否打包: {'是' if summary['packaged'] else '否'}")
    print(f"- 上传文件名: {summary['file_name']}")
    print(f"- S3 URL: {summary['s3_url']}")
    print(f"- 下一步: {summary['next_step']}")


def main() -> int:
    args = parse_args()
    source_paths = resolve_paths(args.paths)
    ensure_no_pdf(source_paths)
    input_mode = infer_input_mode(source_paths)

    packaged = False
    temp_dir: Path | None = None
    if input_mode == "single-file":
        upload_target = source_paths[0]
    else:
        packaged = True
        upload_target, _, temp_dir = build_archive(source_paths, args.archive_name)

    try:
        upload_results = upload_file(str(upload_target))
        upload_result = upload_results[0]
        if not upload_result.get("success"):
            raise RuntimeError(f"上传失败: {upload_result.get('errorMessage')}")
        summary = build_summary(
            input_mode=input_mode,
            upload_target=upload_target,
            upload_result=upload_result,
            packaged=packaged,
            source_paths=source_paths,
        )

        if args.json:
            print(json.dumps(summary, ensure_ascii=False, indent=2))
        else:
            print_human_summary(summary)
        return 0
    finally:
        if packaged and temp_dir and not args.keep_archive and temp_dir.exists():
            shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
