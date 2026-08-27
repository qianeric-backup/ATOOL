#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
上海建桥学院统一门户登录脚本（逆向自 my.gench.edu.cn 登录页源码）
=================================================================
登录机制（已由前端源码还原确认）：
  - 账号/密码用 js-base64 的 Base64.encode（UTF-8 标准 Base64）编码，字段名 name/password
  - Content-Type: application/x-www-form-urlencoded; charset=UTF-8
  - 验证码模式 signInCaptchaMode：
      1 = 直接登录 ValidateSignInDirect
      2 = 图形验证码 ValidateSignInByCaptcha   (captchaId+captcha)
      3 = 腾讯验证码 ValidateSignInByTencentCaptcha (ticket+randstr, 需先 GetAIDEncrypted)
      4 = 滑块验证码 ValidateSignInBySlideCaptcha   (verificationToken)
  - 登录成功: result.result===true, 跳回 returnUrl
用法：
  python gench_login.py 学号 密码 [returnUrl]            # 自动按当前验证码模式尝试
  python gench_login.py 学号 密码 --mode 1               # 强制模式1
  python gench_login.py 学号 密码 --cookies-only         # 只探测配置，不做登录
说明：
  - 未提供账号时仅输出链路探测；模式3/4 需要人工验证码，脚本会明确提示。
  - 登录后门户会话 Cookie（.AspNetCore.Cookies 等）由 requests.Session 自动保存，
    可用于后续访问 FAP5.Portal / FAP5.Course 定位抢课接口。
"""
import argparse
import base64
import json
import sys
import urllib.parse

import requests

BASE = "https://my.gench.edu.cn/FAP5.IdentityServer"
PORTAL = "https://my.gench.edu.cn/FAP5.Portal"


def b64(s: str) -> str:
    """与前端 js-base64 Base64.encode 一致：UTF-8 标准 Base64。"""
    return base64.b64encode(s.encode("utf-8")).decode("ascii")


def form(body: dict) -> dict:
    # 前端用 qs.stringify，这里手动保证顺序无关
    return urllib.parse.urlencode(body)


def get_sign_in_config(session: requests.Session) -> dict:
    r = session.get(f"{BASE}/api/Config/GetSignInConfig", timeout=15)
    r.raise_for_status()
    data = r.json()
    if data.get("error"):
        raise RuntimeError(f"GetSignInConfig 返回错误: {data['error']}")
    return data["result"]


def login_candidates(username: str, password: str, return_url: str, cfg: dict):
    """按配置的验证码模式生成可执行的登录候选（返回请求信息）。"""
    name, pwd = b64(username), b64(password)
    mode = cfg.get("signInCaptchaMode", "1")
    print(f"[*] 当前验证码模式 signInCaptchaMode={mode}")

    if mode == "1":
        return [(
            mode,
            f"{BASE}/api/Authentication/ValidateSignInDirect",
            {"name": name, "password": pwd, "returnUrl": return_url},
            "无验证码，可直接提交",
        )]
    if mode == "2":
        return [(
            mode,
            f"{BASE}/api/Authentication/ValidateSignInByCaptcha",
            {"name": name, "password": pwd, "returnUrl": return_url,
             "captchaId": "10000001", "captcha": "<人工输入>", },
            "需要图形验证码：GET {BASE}/captcha?id=... 识图后填 captcha",
        )]
    if mode == "3":
        return [(
            mode,
            f"{BASE}/api/Authentication/ValidateSignInByTencentCaptcha",
            {"name": name, "password": pwd, "returnUrl": return_url,
             "ticket": "<腾讯验证码ticket>", "randstr": "<腾讯验证码randstr>"},
            "需要腾讯验证码(AppId 192499621)：GET {BASE}/api/Authentication/GetAIDEncrypted 初始化，"
            "前端 TencentCaptcha.show() 通过后取 ticket/randstr",
        )]
    if mode == "4":
        return [(
            mode,
            f"{BASE}/api/Authentication/ValidateSignInBySlideCaptcha",
            {"name": name, "password": pwd, "returnUrl": return_url,
             "verificationToken": "<滑块验证token>"},
            "需要滑块验证：POST {BASE}/api/Authentication/CreateSlideCaptcha 取 challenge，"
            "拖动后 POST VerifySlideCaptcha 得 verificationToken",
        )]
    return []


def main():
    ap = argparse.ArgumentParser(description="建桥学院统一门户登录脚本(逆向自前端源码)")
    ap.add_argument("username", nargs="?", help="学号/工号")
    ap.add_argument("password", nargs="?", help="密码")
    ap.add_argument("return_url", nargs="?", default=f"{PORTAL}/signin-oidc",
                    help="登录成功跳转地址(默认门户OIDC回调)")
    ap.add_argument("--mode", default=None, help="强制验证码模式1/2/3/4")
    ap.add_argument("--cookies-only", action="store_true", help="只探测配置，不登录")
    args = ap.parse_args()

    s = requests.Session()
    s.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36"})

    print("== 1) 读取登录配置 ==")
    cfg = get_sign_in_config(s)
    print(json.dumps({k: v for k, v in cfg.items()
                      if k in ("name", "signInCaptchaMode", "enableAccountLogin",
                               "wxAppId", "enableWXQRLogin", "enableWXNativeAppLogin")},
                     ensure_ascii=False, indent=2))

    if args.cookies_only or not (args.username and args.password):
        print("\n[!] 未提供账号或仅探测模式：跳过登录。")
        if not (args.username and args.password):
            print("    请提供 学号/工号+密码 后运行（python gench_login.py 学号 密码）。")
        return

    print("\n== 2) 构造登录请求 ==")
    candidates = login_candidates(args.username, args.password, args.return_url, cfg)
    for mode, url, body, note in candidates:
        print(f"[*] 模式{mode}: POST {url}\n    body={json.dumps(body, ensure_ascii=False)}\n    注: {note}")

    if args.mode and args.mode != cfg.get("signInCaptchaMode"):
        print(f"\n[!] 强制模式 {args.mode}（与配置 {cfg.get('signInCaptchaMode')} 不同），按模式1尝试直登：")
        url = f"{BASE}/api/Authentication/ValidateSignInDirect"
        body = {"name": b64(args.username), "password": b64(args.password), "returnUrl": args.return_url}
        candidates = [(args.mode, url, body, "强制直登")]

    # 仅当模式1或强制直登时实际提交（其余模式需人工验证码）
    for mode, url, body, note in candidates:
        if mode == "1":
            print(f"\n== 3) POST {url}（直登）==")
            r = s.post(url, data=form(body),
                       headers={"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"},
                       timeout=20)
            print(f"[*] HTTP {r.status_code}")
            try:
                print("[*] 响应:", json.dumps(r.json(), ensure_ascii=False, indent=2))
            except Exception:
                print("[*] 响应:", r.text[:500])
            data = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
            if isinstance(data, dict) and data.get("result") is True:
                print("\n[√] 登录成功！会话 Cookie 已保存在 requests.Session，可继续访问门户。")
                print("    下一步：GET", PORTAL, "→ 定位选课应用 (FAP5.Course) 抓取抢课接口。")
            else:
                print(f"\n[x] 登录未成功: {data.get('failureInfo') if isinstance(data, dict) else ''} "
                      f"(needChangePassword={data.get('needChangePassword') if isinstance(data, dict) else ''})")
        else:
            print(f"\n[!] 模式{mode}需要人工验证码，脚本未自动提交。请按上面提示完成验证码后重试，"
                  f"或提供已登录 Cookie 直接进入门户。")


if __name__ == "__main__":
    main()