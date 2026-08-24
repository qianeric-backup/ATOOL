# -*- coding: utf-8 -*-
"""高波动环境对比: v1.2.4 vs v1.2.6 (波动 mock: 100ms+抖动700ms, 15%失败, 10%超时, 30%验证码错)。

测: 完整流程耗时 / 成功率 / 重试次数。
"""
import importlib.util
import os
import sys
import time

DEV = os.path.join(os.path.dirname(os.path.abspath(__file__)), "宿舍抢购工具")
API = "http://127.0.0.1:8765/api"
ENROLL = "2631141739"
IDCARD = "310110200605112038"

VERSIONS = {
    "v1.2.4": os.path.join(DEV, "releases", "v1.2.4", "src", "grab_dorm.py"),
    "v1.2.6": os.path.join(DEV, "_dev", "grab_dorm.py"),
}


def load_mod(path):
    spec = importlib.util.spec_from_file_location("m_" + str(int(time.time()*1000)), path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def one_run(mod):
    ocr = mod.CaptchaOcr(auto=True, save_dir=None)
    g = mod.DormGrabber(enrollid=ENROLL, idcard=IDCARD, ocr=ocr,
                        concurrency=1, ahead_ms=0, max_retries=8, interval_ms=50,
                        api_base=API)
    t0 = time.time()
    g.login()
    g.fetch_dorm()
    g.sync_time(rounds=3)
    info = g.grab(start_ts=time.time())
    dt = time.time() - t0
    if info:
        return dt, info["attempt"], True
    return dt, None, False


def bench(version, path, rounds=5):
    mod = load_mod(path)
    rows = []
    for i in range(rounds):
        try:
            rows.append(one_run(mod))
        except Exception as e:
            rows.append((None, None, False))
            print(f"  [{version}] #{i+1} 异常: {type(e).__name__}: {str(e)[:60]}")
        time.sleep(0.3)
    ok = [r for r in rows if r[2]]
    fail = rounds - len(ok)
    avg_t = sum(r[0] for r in ok) / len(ok) if ok else 0
    avg_att = sum(r[1] for r in ok) / len(ok) if ok else 0
    return {"avg_t": avg_t, "avg_att": avg_att, "success": len(ok), "fail": fail}


if __name__ == "__main__":
    print("=== 高波动环境对比 (各 5 次) ===")
    print(f"{'版本':<8}{'平均耗时s':>10}{'平均重试':>10}{'成功':>6}{'失败':>6}")
    for v, p in VERSIONS.items():
        r = bench(v, p)
        print(f"{v:<8}{r['avg_t']:>10.2f}{r['avg_att']:>10.1f}{r['success']:>6}{r['fail']:>6}")
