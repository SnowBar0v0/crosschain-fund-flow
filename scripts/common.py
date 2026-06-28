#!/usr/bin/env python3
"""Shared helpers for crosschain-fund-flow scripts."""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo


EVM_RE = re.compile(r"0x[a-fA-F0-9]{40}")
SOL_RE = re.compile(r"(?<![A-Za-z0-9])[1-9A-HJ-NP-Za-km-z]{32,44}(?![A-Za-z0-9])")


class ToolError(RuntimeError):
    pass


def fail(message: str, code: int = 2) -> None:
    print(json.dumps({"ok": False, "error": message}, ensure_ascii=False), file=sys.stderr)
    raise SystemExit(code)


def parse_time(value: str | None, timezone: str = "Asia/Shanghai") -> int | None:
    if not value:
        return None
    value = value.strip()
    if re.fullmatch(r"\d{10}", value):
        return int(value)
    if re.fullmatch(r"\d{13}", value):
        return int(value) // 1000
    tz = ZoneInfo(timezone)
    normalized = value.replace("Z", "+00:00")
    try:
        parsed = dt.datetime.fromisoformat(normalized)
    except ValueError:
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
            try:
                parsed = dt.datetime.strptime(value, fmt)
                break
            except ValueError:
                parsed = None
        if parsed is None:
            raise ToolError(f"Invalid time: {value}")
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=tz)
    return int(parsed.timestamp())


def format_time(ts: int | float | None, timezone: str = "Asia/Shanghai") -> str | None:
    if ts is None:
        return None
    return dt.datetime.fromtimestamp(float(ts), ZoneInfo(timezone)).strftime("%Y-%m-%d %H:%M:%S %Z")


def http_json(
    url: str,
    *,
    params: dict[str, Any] | None = None,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    body: Any | None = None,
    timeout: int = 30,
) -> Any:
    if params:
        url += ("&" if "?" in url else "?") + urllib.parse.urlencode(params, doseq=True)
    data = None
    req_headers = {"accept": "application/json", "user-agent": "crosschain-fund-flow/0.1"}
    if headers:
        req_headers.update(headers)
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        req_headers["content-type"] = "application/json"
    req = urllib.request.Request(url, data=data, method=method, headers=req_headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            raw = response.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:1000]
        raise ToolError(f"HTTP {exc.code} for {url}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise ToolError(f"Network error for {url}: {exc}") from exc
    try:
        return json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise ToolError(f"Non-JSON response from {url}: {raw[:200]!r}") from exc


def solana_rpc(method: str, params: list[Any], rpc_url: str) -> Any:
    payload = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
    out = http_json(rpc_url, method="POST", body=payload)
    if "error" in out:
        raise ToolError(f"Solana RPC {method} failed: {out['error']}")
    return out.get("result")


def solscan_json(path: str, *, params: dict[str, Any] | None = None, api_key: str | None = None) -> Any:
    key = api_key or os.getenv("SOLSCAN_API_KEY")
    if not key:
        raise ToolError("Missing SOLSCAN_API_KEY for Solscan Pro endpoint.")
    headers = {"token": key}
    return http_json(f"https://pro-api.solscan.io/v2.0/{path.lstrip('/')}", params=params, headers=headers)


def unwrap_items(response: Any) -> list[dict[str, Any]]:
    data = response.get("data") if isinstance(response, dict) else response
    if isinstance(data, dict):
        for key in ("items", "data", "result"):
            value = data.get(key)
            if isinstance(value, list):
                return value
        return [data]
    if isinstance(data, list):
        return data
    if isinstance(response, list):
        return response
    return []


def unwrap_object(response: Any) -> dict[str, Any]:
    data = response.get("data") if isinstance(response, dict) else response
    if isinstance(data, dict):
        return data
    return {}


def pick(item: dict[str, Any], *names: str, default: Any = None) -> Any:
    for name in names:
        if name in item and item[name] not in (None, ""):
            return item[name]
    return default


def write_json(path: str | None, data: Any) -> None:
    if not path:
        return
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def write_text(path: str | None, text: str) -> None:
    if not path:
        return
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def print_or_write(data: dict[str, Any], markdown: str, json_path: str | None, md_path: str | None) -> None:
    write_json(json_path, data)
    write_text(md_path, markdown)
    if not json_path and not md_path:
        print(json.dumps(data, indent=2, ensure_ascii=False))


def shorten(value: str | None, left: int = 6, right: int = 4) -> str:
    if not value:
        return ""
    if len(value) <= left + right + 3:
        return value
    return f"{value[:left]}...{value[-right:]}"


def amount_from_raw(value: Any, decimals: Any = 0) -> float:
    try:
        raw = float(value)
        dec = int(decimals or 0)
    except (TypeError, ValueError):
        return 0.0
    return raw / (10 ** dec)


def extract_addresses(text: str) -> list[str]:
    found: list[str] = []
    for match in EVM_RE.findall(text):
        found.append(match.lower())
    for match in SOL_RE.findall(text):
        if not EVM_RE.fullmatch(match):
            found.append(match)
    return found


def _xlsx_shared_strings(zf: zipfile.ZipFile) -> list[str]:
    try:
        raw = zf.read("xl/sharedStrings.xml")
    except KeyError:
        return []
    root = ET.fromstring(raw)
    ns = {"a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    values: list[str] = []
    for si in root.findall("a:si", ns):
        parts = [node.text or "" for node in si.findall(".//a:t", ns)]
        values.append("".join(parts))
    return values


def _xlsx_sheet_paths(zf: zipfile.ZipFile) -> dict[str, str]:
    ns = {
        "a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
        "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    }
    rel_ns = {"rel": "http://schemas.openxmlformats.org/package/2006/relationships"}
    workbook = ET.fromstring(zf.read("xl/workbook.xml"))
    rels = ET.fromstring(zf.read("xl/_rels/workbook.xml.rels"))
    rel_map = {rel.attrib["Id"]: rel.attrib["Target"] for rel in rels.findall("rel:Relationship", rel_ns)}
    out: dict[str, str] = {}
    for sheet in workbook.findall(".//a:sheet", ns):
        name = sheet.attrib["name"]
        rid = sheet.attrib[f"{{{ns['r']}}}id"]
        target = rel_map[rid]
        if not target.startswith("xl/"):
            target = "xl/" + target.lstrip("/")
        out[name] = target
    return out


def read_xlsx_rows(path: str, sheet_names: list[str] | None = None) -> dict[str, list[list[str]]]:
    with zipfile.ZipFile(path) as zf:
        shared = _xlsx_shared_strings(zf)
        paths = _xlsx_sheet_paths(zf)
        wanted = set(sheet_names or paths.keys())
        ns = {"a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
        result: dict[str, list[list[str]]] = {}
        for name, target in paths.items():
            if name not in wanted:
                continue
            root = ET.fromstring(zf.read(target))
            rows: list[list[str]] = []
            for row in root.findall(".//a:sheetData/a:row", ns):
                values: list[str] = []
                for cell in row.findall("a:c", ns):
                    cell_type = cell.attrib.get("t")
                    value = ""
                    if cell_type == "inlineStr":
                        value = "".join(node.text or "" for node in cell.findall(".//a:t", ns))
                    else:
                        v = cell.find("a:v", ns)
                        if v is not None and v.text is not None:
                            value = v.text
                            if cell_type == "s":
                                try:
                                    value = shared[int(value)]
                                except (ValueError, IndexError):
                                    pass
                    values.append(value)
                rows.append(values)
            result[name] = rows
    return result


def load_label_map(label_path: str | None, sheets: str | None = None) -> dict[str, list[dict[str, Any]]]:
    if not label_path:
        return {}
    p = Path(label_path)
    if not p.exists():
        raise ToolError(f"Label file not found: {label_path}")
    sheet_list = [s.strip() for s in sheets.split(",") if s.strip()] if sheets else None
    rows_by_sheet: dict[str, list[list[str]]] = {}
    if p.suffix.lower() == ".xlsx":
        rows_by_sheet = read_xlsx_rows(str(p), sheet_list)
    elif p.suffix.lower() == ".csv":
        with p.open(newline="", encoding="utf-8-sig") as fh:
            rows_by_sheet[p.stem] = list(csv.reader(fh))
    elif p.suffix.lower() == ".json":
        data = json.loads(p.read_text(encoding="utf-8"))
        rows_by_sheet[p.stem] = [[str(item)] for item in data]
    else:
        rows_by_sheet[p.stem] = [[line] for line in p.read_text(encoding="utf-8", errors="ignore").splitlines()]
    labels: dict[str, list[dict[str, Any]]] = {}
    for sheet, rows in rows_by_sheet.items():
        for row_index, row in enumerate(rows, start=1):
            row_text = " ".join(str(cell) for cell in row)
            for address in extract_addresses(row_text):
                labels.setdefault(address, []).append({"sheet": sheet, "row": row_index, "text": row_text[:300]})
    return labels


def label_hits(addresses: list[str], label_map: dict[str, list[dict[str, Any]]]) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {}
    for address in addresses:
        key = address.lower() if address.startswith("0x") else address
        if key in label_map:
            out[address] = label_map[key]
    return out


def add_common_output_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--output-json", help="Write normalized JSON result to this path")
    parser.add_argument("--output-md", help="Write Markdown report to this path")


def command_error(main):
    try:
        main()
    except ToolError as exc:
        fail(str(exc))
    except Exception as exc:
        fail(str(exc))
    except KeyboardInterrupt:
        fail("Interrupted", 130)
