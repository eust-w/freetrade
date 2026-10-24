"""Export allowlisted operational facts; never copy raw logs or provider responses."""
import argparse
from collections import Counter
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re


def summarize(path: Path) -> dict:
    text = path.read_text(encoding="utf-8", errors="replace")
    events = []
    for line in text.splitlines():
        if line.startswith("{"):
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    success = [e for e in events if e.get("status") == "ok"]
    fallback = [e for e in events if e.get("status") == "fallback"]
    http = re.findall(r"https_status=(\d{3}) bytes=(\d+)", text)
    stamp = path.stem.removeprefix("refresh-")
    datetime.strptime(stamp, "%Y%m%d-%H%M%S")
    mode = success[-1].get("mode") if success else "unknown"
    if mode not in {"live", "fallback"}:
        mode = "unknown"
    return {
        "run_id": stamp,
        "timezone": "Asia/Shanghai",
        "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "render_status": "ok" if success else "not_observed",
        "mode": mode,
        "fallback_event_observed": bool(fallback),
        "upstream_failure": "remote_disconnect" if "RemoteDisconnected" in text else (
            "other" if fallback else None),
        "candidate_count": len(success[-1].get("stocks", [])) if success else None,
        "http_status": int(http[-1][0]) if http else None,
        "response_bytes": int(http[-1][1]) if http else None,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("logs", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    rows = [summarize(p) for p in sorted(args.logs.glob("refresh-*.log"))]
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "runs.jsonl").write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    summary = {
        "records": len(rows), "first_run": rows[0]["run_id"] if rows else None,
        "last_run": rows[-1]["run_id"] if rows else None,
        "modes": dict(Counter(r["mode"] for r in rows)),
        "render_statuses": dict(Counter(r["render_status"] for r in rows)),
        "http_statuses": dict(Counter(str(r["http_status"]) for r in rows)),
        "interpretation": "Retained logs only; not a complete scheduler ledger. HTTP 200 is not fresh-data success.",
    }
    (args.output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
