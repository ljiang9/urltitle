#!/usr/bin/env python3
"""urltitle — 批量抓取网页标题的小工具。

URL 进，标题出。适合做研究笔记时快速把一堆链接变成带标题的 Markdown 列表。

设计取舍：
- 优先取 og:title（通常是作者想要展示的标题），没有再退回 <title>。README 里有说明。
- 只抓前 64KB 就停：标题都在 <head> 里，没必要下载整页。
- 纯静态 HTML 解析：JS 渲染的页面拿不到标题，这是诚实局限。
"""

import argparse
import concurrent.futures
import gzip
import html
import json
import re
import sys
import urllib.error
import urllib.request
import zlib

VERSION = "0.1.0"
MAX_BYTES = 64 * 1024  # 标题在 head 里，64KB 足够

OG_TITLE_RE = re.compile(
    r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\'](.*?)["\']', re.I | re.S)
OG_TITLE_REV = re.compile(
    r'<meta[^>]+content=["\'](.*?)["\'][^>]+property=["\']og:title["\']', re.I | re.S)
TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.I | re.S)
META_CHARSET_RE = re.compile(
    r'<meta[^>]+charset=["\']?\s*([a-zA-Z0-9_-]+)', re.I)
TAG_RE = re.compile(r"<[^>]+>")


def detect_encoding(raw: bytes, content_type: str) -> str:
    """从 HTTP 头 / meta 标签猜编码，默认 utf-8。"""
    m = re.search(r"charset=([a-zA-Z0-9_-]+)", content_type or "", re.I)
    if m:
        return m.group(1).lower()
    # 只看前 4KB 的 meta 标签
    head = raw[:4096].decode("ascii", errors="ignore")
    m = META_CHARSET_RE.search(head)
    if m:
        return m.group(1).lower()
    return "utf-8"


def clean_title(text: str) -> str:
    text = TAG_RE.sub("", text)          # 去掉标题里可能嵌套的标签
    text = html.unescape(text)           # &amp; 之类
    text = re.sub(r"\s+", " ", text).strip()
    return text


def extract_title(raw: bytes, content_type: str) -> str | None:
    enc = detect_encoding(raw, content_type)
    try:
        text = raw.decode(enc, errors="strict")
    except (LookupError, UnicodeDecodeError):
        text = raw.decode("utf-8", errors="replace")
    for rx in (OG_TITLE_RE, OG_TITLE_REV):   # og:title 优先
        m = rx.search(text)
        if m and clean_title(m.group(1)):
            return clean_title(m.group(1))
    m = TITLE_RE.search(text)
    if m and clean_title(m.group(1)):
        return clean_title(m.group(1))
    return None


def fetch_one(url: str, timeout: float) -> dict:
    """返回 {"url":..., "title":..., "status":...}。status: ok / http404 / 非HTML / 超时 / 错误…"""
    req = urllib.request.Request(
        url, headers={"User-Agent": "urltitle/0.1.0 (research notes tool)"})
    try:
        resp = urllib.request.urlopen(req, timeout=timeout)
    except urllib.error.HTTPError as e:
        return {"url": url, "title": None, "status": f"HTTP {e.code}"}
    except TimeoutError:
        return {"url": url, "title": None, "status": "超时"}
    except Exception as e:  # DNS 失败、连接拒绝等
        return {"url": url, "title": None, "status": f"错误：{type(e).__name__}"}

    with resp:
        ctype = resp.headers.get("Content-Type", "")
        if "html" not in ctype.lower():
            return {"url": url, "title": None,
                    "status": f"非 HTML（{ctype.split(';')[0] or '未知类型'}）"}
        raw = resp.read(MAX_BYTES + 1)
        enc = (resp.headers.get("Content-Encoding") or "").lower()
        if "gzip" in enc:
            try:
                raw = gzip.decompress(raw)
            except OSError:
                pass
        elif "deflate" in enc:
            try:
                raw = zlib.decompress(raw)
            except zlib.error:
                pass
    title = extract_title(raw[:MAX_BYTES], ctype)
    if title:
        return {"url": url, "title": title, "status": "ok"}
    return {"url": url, "title": None, "status": "未找到标题"}


def read_urls(args) -> list[str]:
    urls: list[str] = []
    if args.stdin or (not args.sources and not sys.stdin.isatty()):
        urls += [ln.strip() for ln in sys.stdin if ln.strip()]
    for src in args.sources:
        try:
            with open(src, encoding="utf-8") as f:
                urls += [ln.strip() for ln in f
                         if ln.strip() and not ln.strip().startswith("#")]
        except OSError:
            urls.append(src)  # 不是文件就当 URL
    # 去重保序
    seen, out = set(), []
    for u in urls:
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out


def print_table(results: list[dict]) -> None:
    w_url = max([len(r["url"]) for r in results] + [3])
    w_url = min(w_url, 60)
    print(f"{'URL':<{w_url}}  标题  状态")
    print("-" * (w_url + 20))
    for r in results:
        url = r["url"] if len(r["url"]) <= w_url else r["url"][:w_url - 1] + "…"
        title = r["title"] or "—"
        print(f"{url:<{w_url}}  {title}  [{r['status']}]")
    ok = sum(1 for r in results if r["status"] == "ok")
    print(f"\n共 {len(results)} 个链接：{ok} 个拿到标题。")


def print_md(results: list[dict]) -> None:
    for r in results:
        if r["title"]:
            safe = r["title"].replace("[", "\\[").replace("]", "\\]")
            print(f"- [{safe}]({r['url']})")
        else:
            print(f"- [{r['url']}]({r['url']})  <!-- {r['status']} -->")


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        prog="urltitle",
        description="批量抓取网页标题：URL 进，标题出。优先 og:title，其次 <title>。")
    p.add_argument("sources", nargs="*",
                   help="URL 列表文件，或直接写 URL（# 开头行忽略）")
    p.add_argument("--stdin", action="store_true", help="从 stdin 读 URL")
    p.add_argument("--jobs", type=int, default=8, help="并发数（默认 8）")
    p.add_argument("--timeout", type=float, default=10, help="单个请求超时秒数（默认 10）")
    p.add_argument("--json", action="store_true", help="JSON 输出")
    p.add_argument("--md", action="store_true",
                   help="输出 Markdown 链接列表（适合粘进研究笔记）")
    p.add_argument("--version", action="version", version=f"urltitle {VERSION}")
    args = p.parse_args(argv)

    urls = read_urls(args)
    if not urls:
        print("error: 没有输入 URL（给文件、参数或 --stdin）", file=sys.stderr)
        return 2

    results = [None] * len(urls)
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as ex:
        futs = {ex.submit(fetch_one, u, args.timeout): i
                for i, u in enumerate(urls)}
        for fut in concurrent.futures.as_completed(futs):
            results[futs[fut]] = fut.result()

    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    elif args.md:
        print_md(results)
    else:
        print_table(results)
    return 0


if __name__ == "__main__":
    sys.exit(main())
