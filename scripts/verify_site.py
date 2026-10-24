"""Check HTTP status, required anchors, and deployment identity."""
from __future__ import annotations
import argparse
from html.parser import HTMLParser
import json
from pathlib import Path
import urllib.request


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.urls = set()

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self.urls.add(dict(attrs).get("href"))


def verify(url: str, expected: Path | None = None) -> dict:
    with urllib.request.urlopen(url, timeout=25) as response:
        status = response.status
        body = response.read()
    if status != 200:
        raise RuntimeError(f"unexpected HTTP {status}")
    page = body.decode("utf-8")
    links = Links()
    links.feed(page)
    required = {"https://github.com/eust-w", "https://claworkers.com/"}
    missing = required - links.urls
    if missing:
        raise RuntimeError(f"missing required links: {sorted(missing)}")
    if expected is not None and body != expected.read_bytes():
        raise RuntimeError("live page does not match rendered artifact")
    return {"http_status": status, "bytes": len(body), "required_links": sorted(required),
            "artifact_match": expected is not None}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url")
    parser.add_argument("--expected", type=Path)
    args = parser.parse_args()
    print(json.dumps(verify(args.url, args.expected), ensure_ascii=False))
