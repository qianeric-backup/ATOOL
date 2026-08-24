# -*- coding: utf-8 -*-
"""临时: 高波动网络模拟 mock (用于测试智能重试/连接池在真实波动网络下的表现)。

模拟维度(均可配置):
  --base-delay    基础延迟 ms (默认 100)
  --jitter-max    额外抖动上限 ms (默认 700, 实际延迟 = base + uniform(0, jitter))
  --fail-rate     随机返回 HTTP 500 的概率 (默认 0.15)
  --timeout-rate  随机"卡死超时"的概率 (默认 0.1, sleep 5s 触发客户端 timeout)
  --captcha-err   随机让 set_dorm 返回 505 验证码错误的概率 (默认 0.3)

用法: python _volatile_mock.py --port 8765 [选项]
"""
import argparse
import random
import time
from http.server import ThreadingHTTPServer

import mock_server

CFG = {"base": 0.1, "jitter": 0.7, "fail": 0.15, "timeout": 0.1, "cerr": 0.3}


class V(mock_server.Handler):
    def _wave(self):
        """施加波动: 随机延迟 + 随机失败/超时。返回 False 表示请求已处理(不应继续)。"""
        delay = CFG["base"] + random.uniform(0, CFG["jitter"])
        if random.random() < CFG["timeout"]:
            time.sleep(12.0)  # 超过客户端默认 timeout(10s) -> 触发超时重试
        else:
            time.sleep(delay)
        if random.random() < CFG["fail"]:
            try:
                self.send_response(500)
                self.send_header("Content-Length", "0")
                self.end_headers()
            except Exception:
                pass
            return False
        return True

    def do_GET(self):
        if not self._wave():
            return
        super().do_GET()

    def do_POST(self):
        if not self._wave():
            return
        # 验证码错误模拟: 在 set_dorm 之前拦截
        import urllib.parse
        if "/api/stu/set_dorm" in self.path and random.random() < CFG["cerr"]:
            body = self._read_body()
            self._send(200, {"suc": False, "msg": None, "emsg": "验证码错误",
                             "code": 505, "data": "", "ct": int(time.time())})
            return
        super().do_POST()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--base-delay", type=int, default=100)
    ap.add_argument("--jitter-max", type=int, default=700)
    ap.add_argument("--fail-rate", type=float, default=0.15)
    ap.add_argument("--timeout-rate", type=float, default=0.1)
    ap.add_argument("--captcha-err", type=float, default=0.3)
    args = ap.parse_args()
    CFG.update(base=args.base_delay / 1000.0, jitter=args.jitter_max / 1000.0,
               fail=args.fail_rate, timeout=args.timeout_rate, cerr=args.captcha_err)
    srv = ThreadingHTTPServer(("127.0.0.1", args.port), V)
    print(f"[volatile-mock] base={args.base_delay}ms jitter={args.jitter_max}ms "
          f"fail={args.fail_rate} timeout={args.timeout_rate} cerr={args.captcha_err}", flush=True)
    srv.serve_forever()


if __name__ == "__main__":
    main()
