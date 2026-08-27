#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
建桥工作台会话探测脚本（用浏览器 Cookie 进门户，定位选课/抢课应用）
====================================================================
用法：
  python gench_session.py "Cookie字符串"
        # Cookie 字符串 = 浏览器里复制的一整串，如
        # "name1=val1; name2=val2; ..."
  可选项：--portal https://my.gench.edu.cn/FAP5.Portal  
  说明：
    - 只做只读探测：访问门户首页/菜单/接口，不提交任何选课操作。
    - 输出：门户可达性、菜单里与选课/教务相关的应用链接、各 FAP5.*
      应用接口探测结果，供下一步定位抢课接口。
"""
import argparse
import json
import re
import sys

import requests

BASE = "https://my.gench.edu.cn"
PORTAL = f"{BASE}/FAP5.Portal"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")


def make_session(cookie_str: str) -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": UA, "Accept-Language": "zh-CN,zh;q=0.9"})
    if cookie_str:
        for part in cookie_str.split(";"):
            part = part.strip()
            if "=" in part:
                k, v = part.split("=", 1)
                s.cookies.set(k, v, domain="my.gench.edu.cn")
    return s


def probe(s: requests.Session, url: str, timeout: int = 15):
    try:
        r = s.get(url, timeout=timeout, allow_redirects=False)
        return r.status_code, r.headers.get("Content-Type", ""), len(r.content)
    except Exception as e:
        return "ERR", str(e), 0


def main():
    ap = argparse.ArgumentParser(description="建桥工作台会话探测（只读）")
    ap.add_argument("cookie", help="浏览器登录后的 Cookie 字符串")
    args = ap.parse_args()

    s = make_session(args.cookie)

    print("== 1) 门户可达性 ==")
    for url in [PORTAL + "/", BASE + "/", PORTAL + "/api/"]:
        code, ctype, size = probe(s, url)
        print(f"  GET {url} -> {code} {ctype} {size}B")
        if code in (200, 302) and "html" in ctype:
            r = s.get(url, timeout=15, allow_redirects=False)
            if code == 302:
                loc = r.headers.get("Location", "")
                print(f"     302 -> {loc}")
                if loc.startswith(BASE):
                    code2, ctype2, size2 = probe(s, loc)
                    print(f"     follow {loc} -> {code2} {ctype2} {size2}B")
                    r2 = s.get(loc, timeout=15)
                    body = r2.text
            else:
                body = r.text
            # 提取页面里的应用链接/菜单线索
            links = set(re.findall(r'["\'](/FAP5\.[A-Za-z]+[^"\']*)["\']', body))
            if links:
                print("     页面内 FAP5.* 链接:")
                for l in sorted(links)[:30]:
                    print(f"       {l}")

    print("\n== 2) 各 FAP5 服务可访问性与标题 ==")
    apps = ["FAP5.Portal", "FAP5.Course", "FAP5.Jwc", "FAP5.Teaching",
            "FAP5.Edu", "FAP5.Exam", "FAP5.App"]
    for app in apps:
        url = f"{BASE}/{app}/"
        code, ctype, size = probe(s, url)
        marker = ""
        if code == 200 and "html" in ctype:
            r = s.get(url, timeout=15)
            t = re.search(r"<title>(.*?)</title>", r.text, re.S)
            marker = f" title={t.group(1).strip()[:40]!r}" if t else ""
        print(f"  {app} -> {code} {ctype} {size}B{marker}")

    print("\n== 3) 建议下一步 ==")
    print("  看上面 FAP5.Course / FAP5.Jwc 的返回：若出现真正的应用界面（非登录页跳转），")
    print("  把对应 URL 和页面源码里的 /api/ 接口线索发我，即可定位选课/抢课接口。")


if __name__ == "__main__":
    main()