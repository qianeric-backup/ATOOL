#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Gench 公选课 新批次探测脚本
用法: python3 probe_batch.py            # 单次探测
      python3 probe_batch.py --loop 60  # 每60s循环探测, 发现新批次/资格翻转即高亮告警
Cookie 读取顺序: --cookie= > 环境变量 GENCH_COOKIE > 同目录 cookies.txt
"""
import json
import os
import ssl
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime

BASE = "https://my.gench.edu.cn/Gench.PublicElectivePlatform/api/PublicElective"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")

# 上次探测快照(2026-09-13 19:42): 仅这两个批次
KNOWN_BATCH_IDS = {
    "6efe2ec6-f0f7-404d-b11b-483e732a5904",  # 第二轮
    "9e1bc9d2-d876-49b7-a233-a12efcc0040e",  # 第一轮
}


def load_cookie():
    for arg in sys.argv[1:]:
        if arg.startswith("--cookie="):
            return arg.split("=", 1)[1].strip()
    env = os.environ.get("GENCH_COOKIE")
    if env:
        return env.strip()
    here = os.path.dirname(os.path.abspath(__file__))
    f = os.path.join(here, "cookies.txt")
    if os.path.exists(f):
        with open(f, "r", encoding="utf-8") as fh:
            return fh.read().strip()
    sys.exit("未找到 Cookie: 请写入同目录 cookies.txt")


COOKIE = load_cookie()
CTX = ssl.create_default_context()


def req(path, params=None):
    url = BASE + "/" + path
    if params:
        url += "?" + "&".join(f"{k}={v}" for k, v in params.items())
    r = urllib.request.Request(url, headers={
        "User-Agent": UA, "Cookie": COOKIE,
        "Referer": "https://my.gench.edu.cn/Gench.PublicElectivePlatform/pc.html",
        "X-Requested-With": "XMLHttpRequest", "Accept": "application/json",
    })
    try:
        with urllib.request.urlopen(r, timeout=20, context=CTX) as resp:
            return resp.status, resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")
    except Exception as e:  # 网络抖动
        return -1, json.dumps({"error": str(e)}, ensure_ascii=False)


def unwrap(body):
    try:
        d = json.loads(body)
    except Exception:
        return body[:400]
    if isinstance(d, dict) and "data" in d and "success" in d:
        return d.get("data")
    return d


def probe_once(n=1):
    ts = datetime.now().strftime("%F %T")
    print(f"==== 第{n}次探测 {ts} ====")

    st, body = req("student/enrollment-eligibility")
    eli = unwrap(body)
    print(f"[1] eligibility HTTP {st}: {json.dumps(eli, ensure_ascii=False)}")

    st, body = req("student/enrollment-batches/active")
    act = unwrap(body)
    print(f"[2] active批次 HTTP {st}: {json.dumps(act, ensure_ascii=False)}")

    st, body = req("enrollment-batches", {"pageIndex": 1, "pageSize": 50})
    allb = unwrap(body)
    items = allb.get("items") if isinstance(allb, dict) else allb
    print(f"[3] 全量批次 HTTP {st}: 共 {len(items) if isinstance(items, list) else '?'} 个")
    new_batches = []
    future_batches = []
    if isinstance(items, list):
        for b in items:
            bid = b.get("id")
            mark = ""
            if bid not in KNOWN_BATCH_IDS:
                mark = "  ★★★ 新批次出现!"
                new_batches.append(b)
            start = b.get("enrollDropStartAt") or ""
            try:
                st_t = datetime.fromisoformat(start).timestamp()
            except Exception:
                st_t = 0
            if st_t > time.time():
                future_batches.append(b)
                mark += "  ⏰ 未开始, 开抢 " + start
            print(f"  - id={bid}  {b.get('name')!r}  term={b.get('academicYearTermId')}"
                  f"  选退课 {start} ~ {b.get('enrollDropEndAt')}"
                  f"  仅退 {b.get('dropOnlyStartAt')} ~ {b.get('dropOnlyEndAt')}{mark}")
    hit = bool(new_batches) or bool(future_batches) or \
        (isinstance(eli, dict) and eli.get("canEnroll"))
    if hit:
        print(">>> 触发条件命中: 新批次 / 未开始批次 / 资格放开 <<<")
    return hit, new_batches, future_batches, eli


def main():
    loop = None
    for arg in sys.argv[1:]:
        if arg.startswith("--loop"):
            parts = arg.split("=", 1)
            loop = float(parts[1]) if len(parts) > 1 else 60.0
    if not loop:
        probe_once()
        return
    print(f"循环探测模式: 每 {loop}s 一次, Ctrl+C 退出")
    n = 0
    while True:
        n += 1
        try:
            hit, new_b, fut_b, eli = probe_once(n)
            if hit:
                with open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                       "probe_alert.log"), "a", encoding="utf-8") as f:
                    f.write(json.dumps({
                        "t": datetime.now().isoformat(timespec="seconds"),
                        "new": [b.get("name") for b in new_b],
                        "future": [b.get("name") for b in fut_b],
                        "canEnroll": eli.get("canEnroll") if isinstance(eli, dict) else None,
                    }, ensure_ascii=False) + "\n")
                print(">>> 已写入 probe_alert.log, 可执行抢课流程 <<<")
        except Exception as e:
            print("探测异常:", e)
        time.sleep(loop)


if __name__ == "__main__":
    main()
