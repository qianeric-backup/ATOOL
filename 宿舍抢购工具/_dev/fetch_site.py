# -*- coding: utf-8 -*-
"""
拉取上海建桥学院迎新系统前端静态资源到本地 mock_site/ 目录,
用于本地冒烟测试 (不依赖学校服务器, 也不会产生真实请求)。
用法: python fetch_site.py
"""
import os
import re
import requests

BASE = "https://enroll.gench.edu.cn/yu"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mock_site")
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

# 页面入口 (SPA 壳)
PAGES = [
    ("", "index.html"),                       # /yu/  -> 实际是 404 壳? 用 login 页更稳
    ("/mp/login", "login.html"),              # 登录页 (同一个壳, 仅路径不同)
    ("/mp/dorm_buy_two", "dorm_buy_two.html"),
]
# 顶层引用的资源 (来自 index.html)
TOP_FILES = [
    "css/app.88227d71.css",
    "js/vendor.d272f64d.js",
    "js/app.aa708231.js",
    "js/runtime.fbbd3ec3.js",
    "statics/LOGO_jq02_42.png",
    "statics/login_banner.png",
    "statics/icons/login_name.png",
    "statics/icons/login_idcard.png",
]
# 宿舍轮播图 (来自 get_gbdorm 返回的 img 字段)
DORM_IMGS = [
    "statics/dorm/7-1.jpg",
    "statics/dorm/7-2.jpg",
    "statics/dorm/7-31.jpg",
]


def fetch(url, out_path):
    r = requests.get(url, headers=UA, timeout=30)
    r.raise_for_status()
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "wb") as f:
        f.write(r.content)
    print(f"  {url} -> {os.path.relpath(out_path, OUT)} ({len(r.content)}B)")
    return r


def parse_chunk_map(runtime_js):
    """从 runtime.js 提取 {chunk_id: (js_hash, css_hash)} 映射。"""
    js_map, css_map = {}, {}
    # js 映射形如: +"js/"+({1:"chunk-common"}[e]||e)+"."+{1:"84972a75",...}[e]+".js"
    if 'o.p+"js/"+' in runtime_js:
        seg = runtime_js.split('o.p+"js/"+')[1].split('+".js"}')[0]
        js_map = dict(re.findall(r'(\d+):"([0-9a-f]+)"', seg))
    # css 映射形如: var r="css/"+({1:"chunk-common"}[e]||e)+"."+{1:"504e55eb",...}[e]+".css"
    if 'var r="css/"+' in runtime_js:
        seg = runtime_js.split('var r="css/"+')[1].split('+".css"}')[0]
        css_map = dict(re.findall(r'(\d+):"([0-9a-f]+)"', seg))
    chunks = []
    for cid in sorted(js_map, key=int):
        name = "chunk-common" if cid == "1" else cid
        chunks.append((cid, name, js_map[cid], css_map.get(cid)))
    return chunks


def main():
    print(f"[1/3] 拉取页面壳与顶层资源 -> {OUT}")
    for path, fn in PAGES:
        url = BASE + path
        try:
            r = fetch(url, os.path.join(OUT, fn))
            # 修正 HTML 里的 base href (/yu/) 为相对路径, 便于本地打开
            html = r.text.replace('<base href=/yu/ >', '<base href=./>')
            with open(os.path.join(OUT, fn), "w", encoding="utf-8") as f:
                f.write(html)
        except Exception as e:  # noqa: BLE001
            print(f"  ! {url} 拉取失败: {e}")
    for rel in TOP_FILES:
        try:
            fetch(BASE + "/" + rel, os.path.join(OUT, rel))
        except Exception as e:  # noqa: BLE001
            print(f"  ! {rel} 拉取失败: {e}")

    print("[2/3] 解析 runtime.js chunk 映射, 拉取全部 js/css chunk")
    rt = open(os.path.join(OUT, "js/runtime.fbbd3ec3.js"), encoding="utf-8", errors="replace").read()
    chunks = parse_chunk_map(rt)
    print(f"      共 {len(chunks)} 个 chunk")
    for cid, name, jsh, cssh in chunks:
        try:
            fetch(BASE + f"/js/{name}.{jsh}.js", os.path.join(OUT, f"js/{name}.{jsh}.js"))
        except Exception as e:  # noqa: BLE001
            print(f"  ! js/{name} 失败: {e}")
        if cssh:
            try:
                fetch(BASE + f"/css/{name}.{cssh}.css", os.path.join(OUT, f"css/{name}.{cssh}.css"))
            except Exception as e:  # noqa: BLE001
                print(f"  ! css/{name} 失败: {e}")

    print("[3/3] 拉取宿舍轮播图等静态资源")
    for rel in DORM_IMGS:
        try:
            fetch(BASE + "/" + rel, os.path.join(OUT, rel))
        except Exception as e:  # noqa: BLE001
            print(f"  ! {rel} 失败: {e}")

    print("\n完成! 本地站点目录:", OUT)


if __name__ == "__main__":
    main()
