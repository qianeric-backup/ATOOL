# -*- coding: utf-8 -*-
"""
上海建桥学院迎新系统 —— 智能化宿舍自动竞选脚本
=================================================
版本: 1.2.4
目标页面: https://enroll.gench.edu.cn/yu/mp/dorm_buy_two
API 基址: https://enroll.gench.edu.cn/api

流程:
  1. 登录      POST /stu/login           (enrollid + idcard)
  2. 查询      POST /stu/get_gbdorm      (dtype=2 -> 新宿舍信息, 含开放时间/宿舍id/余量)
  3. 抢购      GET  /pc/common/kaptcha   (图形验证码 5 位)
              POST /stu/set_dorm         (did + yzmstr)  -> {"suc": true/false, "emsg": ...}
  4. 确认      POST /stu/gbinfo_status   (下单/支付状态)

用法:
  python grab_dorm.py --enrollid 2631141739 --idcard 310110200605112038
  python grab_dorm.py --config config.json --dry-run        # 演练: 只登录+查询+校时
  python grab_dorm.py --config config.json --did 83 --concurrency 4   # 多线程并发抢

依赖:
  requests, beautifulsoup4 (必须)
  ddddocr                  (可选, 自动识别验证码; 未安装则手动输入)
"""
import argparse
import json
import os
import sys
import threading
import time
import io

import requests

__version__ = "1.2.4"

API_BASE = "https://enroll.gench.edu.cn/api"
USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")
# 竞选页中硬编码的白名单学号, 不受开放时间限制 (来自前端 js)
WHITELIST_ENROLLIDS = {"18925", "22939", "20911", "19918", "22904", "18934", "22933"}


class CaptchaOcr:
    """验证码识别: 优先 ddddocr, 失败/未安装时回退手动输入。"""

    def __init__(self, auto=True, save_dir=None):
        self.auto = auto
        self.save_dir = save_dir
        self._tl = threading.local()  # 每线程独立 OCR 实例
        if auto:
            try:
                import ddddocr
                self._ocr_cls = ddddocr.DdddOcr
                self._get_ocr()  # 预加载并提示
                print("[OCR] ddddocr 已加载, 使用自动识别")
            except Exception as e:  # noqa: BLE001
                print(f"[OCR] ddddocr 不可用 ({e}), 将改为手动输入验证码")
                self.auto = False
        else:
            print("[OCR] 已禁用自动识别, 将手动输入验证码")

    def _get_ocr(self):
        if not self.auto:
            return None
        ocr = getattr(self._tl, "ocr", None)
        if ocr is None:
            ocr = self._ocr_cls(show_ad=False)
            self._tl.ocr = ocr
        return ocr

    def recognize(self, img_bytes: bytes):
        """返回 5 位验证码字符串; 自动模式下识别失败返回 None (由调用方换图重试)。"""
        ocr = self._get_ocr()
        if ocr is not None:
            try:
                text = ocr.classification(img_bytes)
                text = "".join(ch for ch in text if ch.isalnum())
                if len(text) == 5:
                    return text
                print(f"[OCR] 识别结果 '{text}' 长度不为5, 换图重试")
            except Exception as e:  # noqa: BLE001
                print(f"[OCR] 识别异常: {e}")
            if self.auto:
                return None  # 自动模式: 不阻塞, 让主循环换图重试
        # 手动输入 (--no-ocr 或 ddddocr 不可用)
        path = None
        if self.save_dir:
            os.makedirs(self.save_dir, exist_ok=True)
            path = os.path.join(self.save_dir, f"captcha_{int(time.time() * 1000)}.png")
            with open(path, "wb") as f:
                f.write(img_bytes)
            print(f"[CAPTCHA] 验证码图片已保存: {path}")
        else:
            print("[CAPTCHA] 无法显示图片, 已打印字节长度:", len(img_bytes))
        while True:
            try:
                raw = input("请输入验证码(5位): ").strip()
            except EOFError:
                print("[CAPTCHA] 无法读取输入, 重试...")
                continue
            if len(raw) == 5:
                return raw
            print("输入无效, 需要恰好 5 位")


class AiCaptchaOcr:
    """可选 AI 验证码识别（OpenAI 兼容 Chat Completions 接口）。

    用于开放前预取阶段的双识别投票: 与 ddddocr 结果一致才高可信, 提升真实环境码有效率。
    默认使用智谱 glm-4v-plus-0111(真实环境实测码有效率最高 60%), 可通过参数/环境变量
    切换其他 OpenAI 兼容视觉模型(如 qwen3-vl-flash / glm-4v-plus)。
    未配置 API key / 调用失败时由调用方降级到 CaptchaOcr(ddddocr), 不阻塞主流程。
    配置来源(优先级: 构造参数 > 环境变量 > 默认):
      GRAB_DORM_AI_KEY    API key (必填, 无 key 则禁用 AI)
      GRAB_DORM_AI_BASE   API base URL, 默认 https://open.bigmodel.cn/api/paas/v4 (智谱)
      GRAB_DORM_AI_MODEL  模型名, 默认 glm-4v-plus-0111
    """

    def __init__(self, api_key=None, base_url=None, model=None, timeout=15):
        self.api_key = api_key or os.environ.get("GRAB_DORM_AI_KEY")
        self.base_url = (base_url or os.environ.get("GRAB_DORM_AI_BASE")
                         or "https://open.bigmodel.cn/api/paas/v4").rstrip("/")
        self.model = model or os.environ.get("GRAB_DORM_AI_MODEL") or "glm-4v-plus-0111"
        self.timeout = timeout
        self._session = requests.Session()
        self.available = bool(self.api_key)
        if self.available:
            print(f"[AI-OCR] AI 识别可用: model={self.model} base={self.base_url}")
        else:
            print("[AI-OCR] 未配置 GRAB_DORM_AI_KEY, 预取将降级为 ddddocr")

    def recognize(self, img_bytes: bytes):
        """识别 5 位验证码; 成功返回 5 位字符串, 失败/不可用返回 None。"""
        if not self.available:
            return None
        import base64
        b64 = base64.b64encode(img_bytes).decode()
        try:
            r = self._session.post(
                self.base_url + "/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "model": self.model,
                    "messages": [{
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "识别图片中的 5 位验证码(字母数字, 可能含干扰线)。只输出这 5 个字符, 不要任何解释或标点。"},
                            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
                        ],
                    }],
                    "max_tokens": 10,
                    "temperature": 0,
                },
                timeout=self.timeout,
            )
            r.raise_for_status()
            text = r.json()["choices"][0]["message"]["content"].strip()
            text = "".join(ch for ch in text if ch.isalnum())
            if len(text) == 5:
                return text
            print(f"[AI-OCR] 识别结果 '{text}' 长度不为5, 视为失败")
        except Exception as e:  # noqa: BLE001
            print(f"[AI-OCR] 识别异常: {e}")
        return None


class DormGrabber:
    def __init__(self, enrollid, idcard, dtype=2, did=None, ocr=None,
                 concurrency=1, ahead_ms=300, max_retries=200, interval_ms=200,
                 api_base=None, ai_ocr=None, enable_prefetch=True):
        self.enrollid = str(enrollid)
        self.idcard = str(idcard)
        self.dtype = dtype
        self.did = did          # 可指定宿舍id, 否则用 get_gbdorm 返回的 value
        self.ocr = ocr
        self.ai_ocr = ai_ocr    # 可选 AI 识别器(预取阶段优先使用, 可 None)
        self.concurrency = max(1, concurrency)
        self.ahead_ms = ahead_ms
        self.max_retries = max_retries   # None 表示无限重试直到成功
        self.interval_ms = interval_ms
        self.api_base = (api_base or API_BASE).rstrip("/")
        self.enable_prefetch = enable_prefetch  # False 时跳过预取, worker 直接现场取码

        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT})
        self.dorm = None        # 宿舍信息 dict
        self.server_offset = 0.0  # 服务器时间 - 本地时间 (秒)
        self.cached_yzm = None  # 预取缓存验证码 (开抢瞬间直接提交, 一次性)
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self.success_info = None

    # ---------- 基础请求 ----------
    def _post(self, path, data, timeout=10, retry=3):
        last = None
        for i in range(retry):
            try:
                r = self.session.post(self.api_base + path, data=data, timeout=timeout)
                r.raise_for_status()
                return r
            except Exception as e:  # noqa: BLE001
                last = e
                time.sleep(0.3 * (i + 1))
        raise last

    def _get(self, path, timeout=10, retry=3):
        last = None
        for i in range(retry):
            try:
                r = self.session.get(self.api_base + path, timeout=timeout)
                r.raise_for_status()
                return r
            except Exception as e:  # noqa: BLE001
                last = e
                time.sleep(0.3 * (i + 1))
        raise last

    def server_now(self) -> float:
        """返回服务器当前时间(Unix 秒, 浮点)。"""
        r = self._get("/stu/timestamp")
        ts_ms = int(r.text.strip())
        return ts_ms / 1000.0

    def sync_time(self, rounds=3):
        """往返校准本地时钟与服务器时钟, offset = server - local。
        rounds 默认 3 次取中位数, 兼顾准确性与速度(每次往返约 0.4~0.5s)。"""
        samples = []
        for _ in range(rounds):
            t0 = time.time()
            try:
                srv = self.server_now()
                t1 = time.time()
                samples.append(srv - (t0 + t1) / 2)
            except Exception as e:  # noqa: BLE001
                print(f"[TIME] 校时失败: {e}")
            time.sleep(0.05)
        if samples:
            self.server_offset = sorted(samples)[len(samples) // 2]  # 中位数
        print(f"[TIME] 服务器时间偏移: {self.server_offset:+.3f}s "
              f"(本地现在约 {time.strftime('%H:%M:%S', time.localtime(self.local_now()))})")

    def local_now(self) -> float:
        return time.time() + self.server_offset

    # ---------- 业务接口 ----------
    def login(self):
        print(f"[LOGIN] 登录: enrollid={self.enrollid}")
        r = self._post("/stu/login", {"enrollid": self.enrollid, "idcard": self.idcard})
        body = r.text.strip()
        if body == "fail":
            raise RuntimeError("登录失败: 录取通知书编号或身份证号错误")
        print(f"[LOGIN] 成功, 响应={body!r}, 会话已建立")

    def fetch_dorm(self):
        data = self._post("/stu/get_gbdorm", {"dtype": self.dtype,
                                              "timestamp": int(time.time() * 1000)})
        arr = data.json()
        if not arr:
            raise RuntimeError("get_gbdorm 返回空列表, 可能尚未开放或专业不适用")
        self.dorm = arr[0]
        d = self.dorm
        print(f"[DORM] 宿舍: {d.get('label')} | 学院: {d.get('college')} | "
              f"性别: {d.get('sex')} | 价格: {d.get('price')} | "
              f"剩余: {d.get('sum')} | did(value): {d.get('value')} | "
              f"开放: {d.get('buysdt')} ~ {d.get('buyedt')}")
        if self.did is None:
            self.did = d.get("value")
        if not self.did:
            raise RuntimeError("未从服务器获取到宿舍 id")

    def fetch_captcha(self) -> bytes:
        r = self._get("/pc/common/kaptcha")
        return r.content

    def prefetch_captcha(self, deadline, prefer_ai=True):
        """开放前预取验证码: 取码 + 识别(优先 AI, 失败降级 ddddocr)。

        成功则写入 self.cached_yzm 并返回; 到 deadline 仍未成功返回 None(兜底现场取码)。
        注意: 会话验证码单槽, 成功后绝不能再取码(会覆盖), 只等开抢直接提交。
        """
        attempt = 0
        while not self._stop.is_set() and time.time() < deadline:
            attempt += 1
            try:
                img = self.fetch_captcha()
                # 双识别投票: AI + ddddocr 都识别同一张图
                ai_yzm = self.ai_ocr.recognize(img) if (prefer_ai and self.ai_ocr) else None
                dd_yzm = self.ocr.recognize(img) if self.ocr else None
                # 投票规则: 一致->高可信; 不一致->用 ddddocr(0错误提交); ddddocr失败->用 AI
                if ai_yzm and dd_yzm and ai_yzm.upper() == dd_yzm.upper():
                    yzm, source = dd_yzm, "AI+ddddocr一致"
                elif dd_yzm:
                    yzm, source = dd_yzm, "ddddocr"
                elif ai_yzm:
                    yzm, source = ai_yzm, "AI"
                else:
                    yzm, source = None, ""
                if yzm:
                    self.cached_yzm = yzm
                    print(f"[PREFETCH] 第{attempt}次预取成功, 缓存验证码 '{yzm}' ({source})")
                    return yzm
                print(f"[PREFETCH] 第{attempt}次识别失败, 换图重试...")
            except Exception as e:  # noqa: BLE001
                print(f"[PREFETCH] 第{attempt}次异常: {e}")
        print("[PREFETCH] 达到截止时间未预取成功, 开抢时现场取码兜底")
        return None

    def set_dorm(self, did, yzmstr):
        r = self._post("/stu/set_dorm", {"did": did, "yzmstr": yzmstr}, timeout=10)
        try:
            return r.json()
        except ValueError:
            return {"suc": False, "emsg": f"非JSON响应: {r.text[:100]}"}

    def gb_status(self):
        r = self._post("/stu/gbinfo_status", {"timestamp": int(time.time() * 1000)})
        return r.json()

    # ---------- 抢购核心 ----------
    def one_attempt(self, did):
        """单次尝试: 现场取验证码 -> 识别 -> 提交。失败由 worker 下一轮立即重新取码重试。"""
        img = self.fetch_captcha()
        yzm = self.ocr.recognize(img)
        if not yzm:
            return False, {"emsg": "验证码识别失败, 换图重试"}
        res = self.set_dorm(did, yzm)
        if res.get("suc") is True:
            return True, res
        return False, res

    def worker(self, did, results):
        n = 0
        while not self._stop.is_set():
            if self.max_retries is not None and n >= self.max_retries:
                break
            n += 1
            try:
                # 方案A: 首轮优先用预取缓存码 (0ms 取码), 用后即失效; 失败则现场取码
                if self.cached_yzm is not None:
                    yzm = self.cached_yzm
                    self.cached_yzm = None   # 一次性: 无论成败都作废, 防止重放
                    print(f"[PREFETCH-USE] 第{n}次尝试使用预取验证码 '{yzm}' 直接提交")
                    res = self.set_dorm(did, yzm)
                    ok = res.get("suc") is True
                    detail = res
                else:
                    ok, detail = self.one_attempt(did)
                if ok:
                    with self._lock:
                        self.success_info = {"worker": threading.current_thread().name,
                                             "attempt": n, "detail": detail}
                    self._stop.set()
                    print(f"[OK] 第{n}次尝试成功! 宿舍 did={did} {detail}")
                    return
                emsg = str(detail.get("emsg", ""))
                if emsg:
                    print(f"[RETRY-{n}] {emsg}")
                else:
                    print(f"[RETRY-{n}] 未知结果: {detail}")
                # 登录过期/失效 -> 自动重新登录后继续
                if ("登录" in emsg or "过期" in emsg) and emsg != "登录失败: 录取通知书编号或身份证号错误":
                    print("[LOGIN] 检测到会话失效, 自动重新登录...")
                    try:
                        self.login()
                    except Exception as le:  # noqa: BLE001
                        print(f"[LOGIN] 重新登录失败: {le}")
            except Exception as e:  # noqa: BLE001
                print(f"[RETRY-{n}] 请求异常: {e}")
            # 距开放时间还很远时, 加大间隔; 临近时快速重试
            wait = self.interval_ms / 1000.0
            try:
                if self.open_time is not None:
                    remain = self.open_time - self.local_now()
                    if remain > 60:
                        wait = min(wait, 5.0)
                    elif remain > 5:
                        wait = min(wait, 1.0)
            except Exception:  # noqa: BLE001
                pass
            self._stop.wait(wait)
        results.append(n)

    def grab(self, start_ts=None, dry_run=False):
        if dry_run:
            print("[DRY-RUN] 演练模式: 仅登录/查询/校时, 不提交抢购")
            self.sync_time()
            return None
        self.sync_time()
        if start_ts is None:
            if self.open_time is None:
                # 服务器未返回开放时间(buysdt): 提示并稍后自动重新查询, 不视为账号失败
                keys = sorted(self.dorm.keys()) if (self.dorm and isinstance(self.dorm, dict)) else []
                print(f"[WAIT] 服务器未返回开放时间(buysdt); 当前宿舍字段={keys}, 5s 后重新查询...")
                self._stop.wait(5)
                return None
            start_ts = self.open_time
        remain = start_ts - self.local_now()
        if remain > 0:
            print(f"[WAIT] 距离开放还有 {remain:.1f}s, "
                  f"提前 {self.ahead_ms}ms 于 {time.strftime('%H:%M:%S', time.localtime(start_ts))} "
                  f"(服务器时间) 开始抢购")
            # 方案A: 开放前预取验证码 (deadline = 开放前 2s), 成功后开抢瞬间直接提交
            if self.enable_prefetch:
                prefetch_deadline = start_ts - 2.0
                if remain > 12:
                    # 距开放较远: 先睡到开放前 ~10s 再开始预取, 避免缓存码过早
                    self._sleep_until(prefetch_deadline - 10.0)
                elif remain > 2:
                    pass  # 已在预取窗口内, 直接开始
                self.prefetch_captcha(deadline=prefetch_deadline,
                                      prefer_ai=self.ai_ocr is not None)
            else:
                print("[PREFETCH] 预取已关闭, 开抢后直接现场取码提交")
            # 等待到开放点(按服务器时间), 不提前试探: 提前提交会触发 507 并消耗一次性验证码
            self._sleep_until(start_ts)
        elif remain < -600:
            print(f"[WARN] 开放时间已过 {abs(remain):.0f}s, 继续尝试 (可能已售罄)")

        results = []
        threads = []
        for i in range(self.concurrency):
            t = threading.Thread(target=self.worker, args=(self.did, results),
                                 name=f"grab-{i + 1}", daemon=True)
            threads.append(t)
            t.start()
        for t in threads:
            t.join()
        return self.success_info

    def monitor_order(self, interval=30):
        """抢购成功后持续监控订单状态; 订单丢失(被取消/异常)时返回 False, 供上层重新抢购。"""
        print(f"[MONITOR] 抢购成功! 开始监控订单状态 (每 {interval}s 检查一次, 可点停止退出)")
        while not self._stop.is_set():
            try:
                st = self.gb_status()
                if st:
                    info = st[0]
                    action = info.get("action")
                    print(f"[MONITOR] {time.strftime('%H:%M:%S')} 订单状态: {action} | "
                          f"dormid={info.get('dormid')}")
                    if action in ("支付完成", "下单"):
                        pass  # 正常
                    else:
                        print(f"[MONITOR] 订单状态异常: {info}")
                else:
                    print(f"[MONITOR] {time.strftime('%H:%M:%S')} 未查询到订单! "
                          f"可能已被取消, 准备自动重新抢购...")
                    return False
            except Exception as e:  # noqa: BLE001
                print(f"[MONITOR] 查询异常: {e}")
            self._stop.wait(interval)
        return True

    def run(self, start_ts=None, start_dt=None, dry_run=False, monitor=True,
            monitor_interval=30):
        """完整抢购生命周期: 登录 -> 查询宿舍 -> 等待开放 -> 无限抢购直到成功
        -> 订单监控 (订单丢失自动重新抢购), 保证最终抢到宿舍。
        start_dt: 字符串形式覆盖开放时间(如测试用), 每次循环查询宿舍后生效。"""
        self.login()
        while not self._stop.is_set():
            try:
                self.fetch_dorm()
            except Exception as e:  # noqa: BLE001
                print(f"[DORM] 查询宿舍失败: {e}, 5s 后重试")
                self._stop.wait(5)
                continue
            if start_dt:
                self.dorm["buysdt"] = start_dt
            self.success_info = None
            self._stop.clear()
            info = self.grab(start_ts=start_ts, dry_run=dry_run)
            if dry_run:
                return info
            if self._stop.is_set() and info is None:
                print("[STOP] 已手动停止")
                return None
            # 服务器未返回开放时间: 不判定失败, 稍后自动重新查询
            if info is None and start_ts is None and self.open_time is None:
                print("[RETRY] 服务器未返回开放时间, 继续等待并重新查询...")
                continue
            if info:
                print("\n================= 抢购成功 =================")
                print(f"  线程: {info['worker']}, 第 {info['attempt']} 次尝试")
                print(f"  宿舍: {self.dorm.get('label')}, did={self.did}")
                print("  请尽快前往页面完成支付 (1小时内): /yu/mp/dorm_pay")
                if monitor:
                    self._stop.clear()  # 抢购 worker 已结束, 清除标记供订单监控使用
                    ok = self.monitor_order(interval=monitor_interval)
                    if ok:
                        print("\n[DONE] 订单状态正常, 任务结束")
                        return info
                    print("\n[RESTART] 订单丢失, 自动重新抢购...")
                    self._stop.clear()
                    continue
                return info
            # 有限重试耗尽
            print("[GIVE-UP] 重试已达上限仍未成功, 退出")
            return None

    def _sleep_until(self, target):
        """高精度等待到目标本地时间(秒)。"""
        while True:
            now = time.perf_counter()
            local = time.time()
            remaining = target - local
            if remaining <= 0:
                return
            if remaining > 0.05:
                time.sleep(remaining / 2)
            else:
                # 忙等最后 50ms, 避开 Windows 定时器 ~15ms 误差
                while time.time() < target:
                    pass

    @property
    def open_time(self):
        if self.dorm and self.dorm.get("buysdt"):
            return self._parse_dt(self.dorm["buysdt"])
        return None

    @staticmethod
    def _parse_dt(s):
        return time.mktime(time.strptime(s.replace("-", "/"), "%Y/%m/%d %H:%M:%S"))


def load_config(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def auto_config_path():
    """自动发现配置: 优先 --config; 否则依次查找 exe 同目录、当前工作目录下的 config.json。"""
    for d in (os.path.dirname(os.path.abspath(sys.argv[0])), os.getcwd()):
        cand = os.path.join(d, "config.json")
        if os.path.isfile(cand):
            return cand
    return None


def main():
    ap = argparse.ArgumentParser(description="上海建桥学院 智能化宿舍自动竞选脚本")
    ap.add_argument("--version", action="version", version=f"%(prog)s {__version__}",
                    help="显示版本号")
    ap.add_argument("--config", help="配置文件路径 (JSON, 可含 enrollid/idcard/dtype 等); "
                                     "缺省时自动查找程序同目录下的 config.json")
    ap.add_argument("--enrollid", help="录取通知书编号 (10位)")
    ap.add_argument("--idcard", help="身份证号 (18位)")
    ap.add_argument("--dtype", type=int, default=2, help="宿舍类型, 默认2=新宿舍(智能宿舍)")
    ap.add_argument("--did", type=int, default=None, help="指定宿舍id, 默认用服务器返回的 value")
    ap.add_argument("--start", default=None, help="覆盖开放时间, 格式 2026-08-20 10:00:00 (便于测试)")
    ap.add_argument("--concurrency", type=int, default=1,
                    help="并发抢购线程数, 默认1; 注意验证码为会话级单槽, 多线程会互相覆盖导致错误率上升, 一般保持1即可")
    ap.add_argument("--ahead-ms", type=int, default=300, help="提前多少毫秒开始, 默认300")
    ap.add_argument("--max-retries", type=int, default=200, help="每个线程最大重试次数, 默认200")
    ap.add_argument("--interval-ms", type=int, default=200, help="重试间隔毫秒, 默认200")
    ap.add_argument("--no-ocr", action="store_true", help="禁用自动识别验证码, 改为手动输入")
    ap.add_argument("--ai-key", default=None, help="AI 识别 API key (默认读环境变量 GRAB_DORM_AI_KEY)")
    ap.add_argument("--ai-base", default=None, help="AI 识别 API base URL (OpenAI 兼容, 默认智谱 https://open.bigmodel.cn/api/paas/v4)")
    ap.add_argument("--ai-model", default=None, help="AI 识别模型名 (默认 GRAB_DORM_AI_MODEL 或 glm-4v-plus-0111)")
    ap.add_argument("--no-ai", action="store_true",
                    help="禁用 AI 预取识别(仅用 ddddocr 预取), 即使配置了 API key 也不用")
    ap.add_argument("--no-prefetch", action="store_true",
                    help="禁用验证码预取(方案A), 开抢后直接现场取码提交")
    ap.add_argument("--dry-run", action="store_true", help="演练模式: 只登录+查询+校时")
    ap.add_argument("--forever", action="store_true",
                    help="无限重试直到抢到宿舍; 成功后持续监控订单, 订单丢失自动重新抢购")
    ap.add_argument("--monitor-interval", type=int, default=30,
                    help="订单监控检查间隔秒数, 默认30 (仅 --forever 生效)")
    ap.add_argument("--gui", action="store_true", help="启动图形界面 (输入账号密码, 一键抢购)")
    ap.add_argument("--key", default=None,
                    help="激活KEY (若使用者在目标机器已用 generate_key 签发绑定KEY, 可直接传入; 否则GUI会弹窗索取)")
    ap.add_argument("--api-base", default=API_BASE,
                    help="API 基地址, 默认 %(default)s; 本地冒烟测试可指向 mock 服务器, 如 http://127.0.0.1:8765/api")
    args = ap.parse_args()

    # ===== 激活门卫: 未通过校验则拒绝运行 =====
    import activation
    # 图形界面模式: 显式 --gui, 或未指定任何命令行抢购参数时(即双击 exe 场景) 默认打开 GUI
    has_cli_opts = any([args.config, args.enrollid, args.idcard,
                        args.dry_run, args.forever, args.start, args.did])
    if args.gui or not has_cli_opts:
        # GUI 模式的激活校验在界面内进行(需用户在界面输入KEY)
        from gui import main as gui_main
        gui_main()
        return

    # ===== 激活门卫: CLI 模式, 未通过校验则拒绝运行 =====
    import activation
    ok_key = activation.require_activation(args.key)
    if not ok_key:
        print("错误: 激活KEY无效或未提供。")
        print("提示: 运行  activation.py get-machine 获取本机指纹, 让授权方用 generate_key.py 签发KEY;")
        print("      或使用固定KEY。")
        sys.exit(2)
    print("[ACTIVATION] 激活校验通过")

    cfg = {}
    cfg_path = args.config or auto_config_path()
    if cfg_path:
        cfg = load_config(cfg_path)
        print(f"[CONFIG] 已加载配置: {cfg_path}")
    # CLI 参数优先
    enrollid = args.enrollid or cfg.get("enrollid")
    idcard = args.idcard or cfg.get("idcard")
    if not enrollid or not idcard:
        ap.error("必须提供 --enrollid 和 --idcard (或 --config)")

    ocr = CaptchaOcr(auto=not args.no_ocr,
                     save_dir=os.path.join(os.path.dirname(os.path.abspath(__file__)), "captcha"))

    ai_ocr = None
    if not args.no_ai and not args.no_ocr:
        ai_ocr = AiCaptchaOcr(api_key=args.ai_key, base_url=args.ai_base,
                              model=args.ai_model)

    g = DormGrabber(
        enrollid=enrollid,
        idcard=idcard,
        dtype=args.dtype or cfg.get("dtype", 2),
        did=args.did or cfg.get("did"),
        ocr=ocr,
        ai_ocr=ai_ocr,
        concurrency=args.concurrency or cfg.get("concurrency", 1),
        ahead_ms=args.ahead_ms or cfg.get("ahead_ms", 300),
        max_retries=None if args.forever else (args.max_retries or cfg.get("max_retries", 200)),
        interval_ms=args.interval_ms or cfg.get("interval_ms", 200),
        api_base=args.api_base or cfg.get("api_base"),
        enable_prefetch=not args.no_prefetch,
    )

    try:
        if args.forever:
            # 无限重试 + 订单监控, 保证最终抢到
            info = g.run(dry_run=args.dry_run, monitor=not args.dry_run,
                         monitor_interval=args.monitor_interval, start_dt=args.start)
            if args.dry_run:
                print("\n[DRY-RUN] 演练结束: 登录/查询/校时均正常, 可正式运行 (不加 --dry-run)")
            elif info:
                print(f"\n[INFO] 订单状态: {json.dumps(g.gb_status(), ensure_ascii=False)}")
            return
        g.login()
        g.fetch_dorm()
        if args.start:
            g.dorm = g.dorm or {}
            g.dorm["buysdt"] = args.start
        if g.enrollid in WHITELIST_ENROLLIDS:
            print("[INFO] 学号在内部白名单中, 不受开放时间限制")
        info = g.grab(dry_run=args.dry_run)
        if args.dry_run:
            print("\n[DRY-RUN] 演练结束: 登录/查询/校时均正常, 可正式运行 (不加 --dry-run)")
        elif info:
            print("\n================= 抢购成功 =================")
            print(f"  线程: {info['worker']}, 第 {info['attempt']} 次尝试")
            print(f"  宿舍: {g.dorm.get('label')}, did={g.did}")
            print("  请尽快前往页面完成支付 (1小时内): /yu/mp/dorm_pay")
            try:
                st = g.gb_status()
                print("  订单状态:", json.dumps(st, ensure_ascii=False))
            except Exception as e:  # noqa: BLE001
                print("  (查询订单状态失败)", e)
        else:
            print("\n[结果] 达到最大重试次数仍未成功, 请检查验证码识别率/网络后重试")
    except KeyboardInterrupt:
        g._stop.set()
        print("\n[EXIT] 已手动中断")
        sys.exit(130)
    except Exception as e:  # noqa: BLE001
        print(f"\n[ERROR] {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
