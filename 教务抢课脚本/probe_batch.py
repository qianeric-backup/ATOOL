#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""选课 API 只读探测：students / multiple-students / open-turns / 批次线索。
仅使用本人 token 发少量顺序 GET，等价于前端打开选课页的正常流量。
token 从环境变量 GENCH_CS_TOKEN 读取（不入库，见 README 敏感信息约定）。"""
import base64
import json
import os
import sys
import time

import requests

BASE = "https://eams.gench.edu.cn"
CS_API = BASE + "/course-selection-api/api/v1/student/course-select"
# 凭据一律环境变量注入（原硬编码已按仓库敏感信息约定移除）
TOKEN = os.environ.get("GENCH_CS_TOKEN", "").strip()

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")


def headers(extra=None):
    h = {"Authorization": TOKEN, "User-Agent": UA,
         "Accept": "application/json, text/plain, */*",
         "Referer": BASE + "/course-selection/",
         "Origin": BASE}
    if extra:
        h.update(extra)
    return h


def decode_jwt(tok):
    try:
        p = tok.split(".")[1]
        p += "=" * (-len(p) % 4)
        payload = json.loads(base64.urlsafe_b64decode(p))
        import datetime
        exp = payload.get("exp")
        exp_str = datetime.datetime.fromtimestamp(exp).strftime("%Y-%m-%d %H:%M:%S") if exp else "?"
        return f"iss={payload.get('iss')} user={payload.get('username')} exp={exp_str}"
    except Exception as e:
        return f"decode-fail: {e}"


def show(tag, r, keys_only=True):
    print(f"\n=== {tag} -> HTTP {r.status_code} ({len(r.content)}B, {r.elapsed.total_seconds()*1000:.0f}ms)")
    ct = r.headers.get("Content-Type", "")
    print(f"    Content-Type: {ct}")
    body = r.text
    if "json" in ct:
        try:
            d = r.json()
            if keys_only:
                print("    " + json.dumps(d, ensure_ascii=False)[:1500])
            else:
                print("    " + json.dumps(d, ensure_ascii=False, indent=2)[:4000])
            return d
        except Exception:
            print("    JSON 解析失败: " + body[:300])
    else:
        print("    非JSON响应: " + body[:200].replace("\n", " "))
    return None


def main():
    if not TOKEN:
        print("!! 未设置 GENCH_CS_TOKEN 环境变量（选课 JWT，浏览器登录后从"
              " course-selection/?token= 或 app.py 导出的 Cookie 中获取）")
        sys.exit(1)
    print("== JWT ==")
    print("  " + decode_jwt(TOKEN))

    s = requests.Session()
    s.headers.update(headers())
    s.cookies.set("cs-course-select-student-token", TOKEN, domain="eams.gench.edu.cn", path="/")

    # 0) 服务器时间（顺带测连接）
    try:
        r = s.get(CS_API + "/getCurrentDateTime", timeout=(5, 10))
        show("GET /getCurrentDateTime", r)
    except Exception as e:
        print("网络异常: %r" % e)
        sys.exit(1)
    time.sleep(0.5)

    # 1) 用户给的端点：/students
    try:
        r = s.get(CS_API + "/students", timeout=(5, 10))
        d = show("GET /students", r)
    except Exception as e:
        d = None
        print("/students 异常: %r" % e)
    time.sleep(0.5)

    # 2) /multiple-students —— 内部学生 ID
    sid = None
    try:
        r = s.get(CS_API + "/multiple-students", timeout=(5, 10))
        d2 = show("GET /multiple-students", r)
        if d2 and d2.get("result") == 0 and d2.get("data"):
            sid = str(d2["data"][0]["id"])
            print(f"    >>> 内部学生 ID = {sid}")
            print("    学生对象字段: " + ", ".join(d2["data"][0].keys()))
    except Exception as e:
        print("/multiple-students 异常: %r" % e)
    time.sleep(0.5)

    if not sid:
        print("!! 未取到内部学生 ID，无法继续 open-turns")
        return

    # 3) /open-turns/{sid} —— 开放轮次（批次）
    try:
        r = s.get(CS_API + f"/open-turns/{sid}", timeout=(5, 10))
        d3 = show("GET /open-turns/{sid}", r, keys_only=False)
        if d3 and d3.get("result") == 0:
            turns = d3.get("data") or []
            print(f"\n    >>> 开放轮次数: {len(turns)}")
            for t in turns:
                print("    ---- 轮次对象全部字段 ----")
                print("    " + json.dumps(t, ensure_ascii=False, indent=2)[:2500])
    except Exception as e:
        print("/open-turns 异常: %r" % e)


if __name__ == "__main__":
    main()
