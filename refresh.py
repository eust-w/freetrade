"""Render research snapshots with explicit data provenance and offline demos."""
from __future__ import annotations

import argparse
import html
import json
import math
import os
import re
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent
TZ = ZoneInfo("Asia/Shanghai")
NUMBERS = ("score", "price", "change")
TEXT = ("code", "name", "action", "shortBuy", "shortStop", "shortTake",
        "longBuy", "longStop", "longTake")


def validate_snapshot(snapshot: dict) -> dict:
    if snapshot.get("schema_version") != 1:
        raise ValueError("unsupported snapshot schema")
    if snapshot.get("source") not in {"synthetic", "eastmoney-akshare"}:
        raise ValueError("unknown data source")
    date.fromisoformat(snapshot["data_as_of"])
    stocks = snapshot["stocks"]
    if not isinstance(stocks, list) or not 1 <= len(stocks) <= 10:
        raise ValueError("snapshot must contain 1-10 candidates")
    codes = set()
    for item in stocks:
        if any(not isinstance(item.get(k), str) or not item[k] for k in TEXT):
            raise ValueError("missing candidate text")
        if item["code"] in codes:
            raise ValueError("duplicate candidate")
        codes.add(item["code"])
        for key in NUMBERS:
            value = item[key]
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                raise ValueError("non-finite candidate metric")
        if item["price"] <= 0 or not 0 <= item["score"] <= 100:
            raise ValueError("invalid price or score")
        if type(item.get("hot")) is not bool:
            raise ValueError("invalid hot flag")
        if not isinstance(item.get("rank"), int) or item["rank"] < 1:
            raise ValueError("invalid rank")
        if not isinstance(item.get("drivers"), list) or not all(isinstance(x, str) for x in item["drivers"]):
            raise ValueError("invalid drivers")
    return snapshot


def atomic_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    tmp.replace(path)


def live_snapshot() -> dict:
    # Offline/demo rendering does not import network providers.
    from a_share_quant_scan import build
    from planning import trade_plan

    for key in ("FREETRADE_REPORT_PERIOD", "FREETRADE_ANNUAL_YEAR"):
        if not os.environ.get(key):
            raise ValueError(f"{key} must be explicitly configured")
    selected, metadata = build()
    excluded = set(filter(None, os.environ.get("FREETRADE_EXCLUDED_CODES", "").split(",")))
    selected = selected[~selected["code"].astype(str).str.zfill(6).isin(excluded)]
    top = selected.sort_values("score", ascending=False).head(10)
    if len(top) < 10:
        raise ValueError("insufficient eligible candidates")
    stocks = []
    for rank, (_, row) in enumerate(top.iterrows(), 1):
        item = trade_plan(row)
        item["rank"] = rank
        stocks.append(item)
    # The oldest included bar is a conservative candidate-data freshness marker.
    return validate_snapshot({
        "schema_version": 1,
        "source": "eastmoney-akshare",
        "data_as_of": str(top["last_k_date"].min()),
        "fetched_at": datetime.now(TZ).isoformat(timespec="seconds"),
        "report_period": os.environ["FREETRADE_REPORT_PERIOD"],
        "annual_year": os.environ["FREETRADE_ANNUAL_YEAR"],
        "stocks": stocks,
        "market": {k: metadata[k] for k in (
            "market_amount", "up_count", "valid_spot_rows", "limit_upish_count"
        )},
    })


def read_snapshot(path: Path) -> dict:
    return validate_snapshot(json.loads(path.read_text(encoding="utf-8")))


def escape_values(value):
    if isinstance(value, str):
        return html.escape(value, quote=True)
    if isinstance(value, list):
        return [escape_values(item) for item in value]
    if isinstance(value, dict):
        return {key: escape_values(item) for key, item in value.items()}
    return value


def render(snapshot: dict, mode: str, generated_at: str) -> str:
    validate_snapshot(snapshot)
    template = (ROOT / "site_template.html").read_text(encoding="utf-8")
    labels = {"demo": "离线演示 · 合成数据", "live": "数据源采集 · 请核对数据日期",
              "cached": "缓存模式 · 非实时行情", "fallback": "数据源失败 · 使用历史缓存"}
    replacements = {
        "{{STATUS}}": labels[mode],
        "{{GENERATED_AT}}": html.escape(generated_at),
        "{{DATA_AS_OF}}": html.escape(snapshot["data_as_of"]),
        "{{SOURCE}}": html.escape(snapshot["source"]),
    }
    for key, value in replacements.items():
        template = template.replace(key, value)
    data = json.dumps(escape_values(snapshot["stocks"]), ensure_ascii=False, allow_nan=False)
    return template.replace("const stocks = [];", "const stocks = " + data.replace("<", "\\u003c") + ";")


def run(mode: str, output: Path, cache: Path, allow_fallback: bool = False) -> dict:
    generated = datetime.now(TZ).isoformat(timespec="seconds")
    error_type = None
    if mode == "demo":
        snapshot = read_snapshot(ROOT / "examples" / "demo_snapshot.json")
    elif mode == "cached":
        snapshot = read_snapshot(cache)
        if snapshot["source"] == "synthetic":
            raise ValueError("synthetic demo cannot masquerade as cached market data")
    else:
        try:
            snapshot = live_snapshot()
            atomic_json(cache, snapshot)
        except Exception as exc:
            if not allow_fallback:
                raise
            snapshot = read_snapshot(cache)
            if snapshot["source"] == "synthetic":
                raise ValueError("demo data cannot be used for live fallback") from exc
            mode = "fallback"
            error_type = type(exc).__name__
    page = render(snapshot, mode, generated)
    output.mkdir(parents=True, exist_ok=True)
    tmp = output / ".index.html.tmp"
    tmp.write_text(page, encoding="utf-8")
    tmp.replace(output / "index.html")
    report = {
        "schema_version": 1, "status": "ok", "mode": mode,
        "generated_at": generated, "data_as_of": snapshot["data_as_of"],
        "source": snapshot["source"], "candidate_count": len(snapshot["stocks"]),
        "upstream_error_type": error_type,
    }
    atomic_json(output / "run.json", report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("demo", "live", "cached"), default="demo")
    parser.add_argument("--output", type=Path, default=ROOT / "dist")
    parser.add_argument("--cache", type=Path, default=ROOT / "var" / "last_success.json")
    parser.add_argument("--allow-fallback", action="store_true",
                        help="Allow explicitly labelled historical cache on live failure")
    args = parser.parse_args()
    print(json.dumps(run(args.mode, args.output, args.cache, args.allow_fallback), ensure_ascii=False))


if __name__ == "__main__":
    main()
