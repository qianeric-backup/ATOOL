#!/usr/bin/env python3
"""
Gench 公选课平台 (Gench.PublicElectivePlatform) 选课脚本
=========================================================
逆向自前端 Vue SPA (assets/publicElective-CBEuUtdW.js / pc-*.js)。

用法:
  1. 浏览器登录 https://my.gench.edu.cn/FAP5.Portal/pc2.html 后,
     将 Cookie 整串复制到下面的 COOKIE(或环境变量 GENCH_COOKIE / 同目录 cookies.txt)。
  2. python3 gench_enroll.py            # 交互流程: 列批次 -> 列课程 -> 选课
     python3 gench_enroll.py --watch    # 开抢模式: 轮询刷课名额, 有票即抢

主要接口 (base = https://my.gench.edu.cn/Gench.PublicElectivePlatform/api/PublicElective):
  GET  student/enrollment-batches/active          当前激活选课批次
  GET  enrollment-batches?academicYearTermId=..   管理端批次列表(亦可读)
  GET  student/class-plans/open?academicYearTermId=&enrollmentBatchId=&keyword=&pageIndex=&pageSize=
                                                  开放课程(教学班)列表
  GET  student/class-plans/open/{classPlanId}?academicYearTermId=
                                                  课程详情
  GET  student/enrollments?academicYearTermId=    我的选课
  GET  student/enrollments/check?courseId=&classPlanId=
                                                  选课校验(时间冲突/人数等)
  POST student/enrollments/{classPlanId}          选课
  DEL  student/enrollments/{classPlanId}          退课
  GET  student/enrollment-eligibility             选课资格(26级新生会被拒绝: canEnroll=false)
  GET  enrollment-batches                         全部批次(可读), 含未激活批次
"""

import json
import logging
import os
import re
import sys
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

try:
    import requests
except ImportError:
    sys.exit("需要 requests:  pip3 install requests")

BASE_PAGE = "https://my.gench.edu.cn/Gench.PublicElectivePlatform"
BASE_API = BASE_PAGE + "/api/PublicElective"

COOKIE = ""  # 也可放环境变量 GENCH_COOKIE 或同目录 cookies.txt

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")


def load_cookie() -> str:
    """优先级: 命令行 --cookie > 环境变量 GENCH_COOKIE > cookies.txt > 脚本内 COOKIE"""
    global COOKIE
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
    return COOKIE.strip()


class EnrollmentForbidden(RuntimeError):
    """资格不足(如 26级新生) —— 服务端 403 特化异常"""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


class GenchClient:
    def __init__(self, cookie: str):
        self.s = requests.Session()
        self.s.headers.update({
            "User-Agent": UA,
            "Cookie": cookie,
            "Referer": BASE_PAGE + "/pc.html",
            "X-Requested-With": "XMLHttpRequest",
        })

    def req(self, method: str, path: str, **kw) -> Any:
        url = f"{BASE_API}/{path}"
        r = self.s.request(method, url, timeout=20, **kw)
        if r.status_code in (301, 302) and "IdentityServer" in r.headers.get("Location", ""):
            raise PermissionError("Cookie 失效, 请重新从浏览器复制")
        ct = r.headers.get("Content-Type", "")
        if r.status_code == 403 and "json" in ct:
            try:
                err = r.json()
                code = err.get("code") or err.get("Code") or "FORBIDDEN"
                msg = err.get("msg") or err.get("message") or "无权限"
                raise EnrollmentForbidden(str(code), str(msg))
            except ValueError:
                pass
        if "json" not in ct:
            if r.status_code == 200:
                return None
            r.raise_for_status()
            return None
        data = r.json()
        # 后端两种包裹风格: {success,code,data,msg} 或裸对象
        if isinstance(data, dict) and "success" in data and "data" in data:
            if data.get("success") is False and data.get("code") not in (None, "0", 0, 200, "200"):
                msg = data.get("msg") or data.get("message") or f"code={data['code']}"
                raise RuntimeError(msg)
            return data["data"]
        return data

    # ---- 接口封装 -------------------------------------------------
    def active_batches(self) -> List[dict]:
        d = self.req("GET", "student/enrollment-batches/active")
        return d if isinstance(d, list) else []

    def open_plans(self, term_id: str, batch_id: str = None, keyword: str = None,
                   is_full: bool = None, page: int = 1, size: int = 100) -> dict:
        params = {"academicYearTermId": term_id, "pageIndex": page, "pageSize": size}
        if batch_id:
            params["enrollmentBatchId"] = batch_id
        if keyword:
            params["keyword"] = keyword
        if is_full is not None:
            params["isFull"] = is_full
        return self.req("GET", "student/class-plans/open", params=params) or {}

    def plan_detail(self, class_plan_id: str, term_id: str = None) -> dict:
        params = {"academicYearTermId": term_id} if term_id else {}
        return self.req("GET", f"student/class-plans/open/{class_plan_id}", params=params) or {}

    def my_enrollments(self, term_id: str = None, page: int = 1, size: int = 20) -> dict:
        params = {"pageIndex": page, "pageSize": size}
        if term_id:
            params["academicYearTermId"] = term_id
        d = self.req("GET", "student/enrollments", params=params)
        # 学期有误时后端返回 401 包裹, 直接重试无学期参数
        if isinstance(d, dict):
            return d
        return {}

    def check(self, course_id: str, class_plan_id: str) -> Any:
        return self.req("GET", "student/enrollments/check",
                        params={"courseId": course_id, "classPlanId": class_plan_id})

    def enroll(self, class_plan_id: str) -> Any:
        return self.req("POST", f"student/enrollments/{class_plan_id}")

    def drop(self, class_plan_id: str) -> Any:
        return self.req("DELETE", f"student/enrollments/{class_plan_id}")

    def eligibility(self) -> Dict[str, Any]:
        """选课资格: {canEnroll, code, message}"""
        return self.req("GET", "student/enrollment-eligibility") or {}

    def all_batches(self, page: int = 1, size: int = 50) -> dict:
        """全部批次(含未激活/未开始), 供监控'下一轮何时开'"""
        return self.req("GET", "enrollment-batches",
                        params={"pageIndex": page, "pageSize": size}) or {}

    def batch_watcher(self, logger: "ChangeLogger" = None, interval: float = 30.0,
                      timeout_min: float = 720.0, on_new_batch=None) -> Optional[dict]:
        """监控新批次: 每interval秒拉 enrollment-batches 全表,
        发现(1)新增批次 或(2)已有批次的 enrollDropStartAt 被改动 且未开始
        => 记录变化+回调. 返回新批次(dict)或 None(超时)"""
        import subprocess
        from datetime import datetime as dt
        deadline = time.time() + timeout_min * 60
        seen_ids: Dict[str, dict] = {}
        n = 0
        while n == 0 or time.time() < deadline:
            n += 1
            if timeout_min <= 0:
                deadline = time.time()  # 单次快照
            try:
                page = self.all_batches(size=50)
                items = page.get("items") if isinstance(page, dict) else (page or [])
                now = time.time()
                for b in items or []:
                    bid = b.get("id")
                    start = b.get("enrollDropStartAt") or ""
                    end = b.get("enrollDropEndAt") or ""
                    cur = {k: b.get(k) for k in ("name", "academicYearTermId",
                                                  "enrollDropStartAt", "enrollDropEndAt",
                                                  "dropOnlyStartAt", "dropOnlyEndAt")}
                    old = seen_ids.get(bid)
                    if old is not None and old == cur:
                        continue
                    if logger:
                        logger.snapshot(f"batch.{bid}", cur)
                    seen_ids[bid] = cur
                    # 未开始且 未来有开始时间
                    try:
                        st_t = dt.fromisoformat(start).timestamp()
                    except Exception:
                        continue
                    if st_t > now:
                        remain_min = (st_t - now) / 60
                        print(f"[批次观察] 未开始的批次: {b.get('name')} 开抢 {start} (还有{remain_min:.0f}分钟)")
                        if on_new_batch and b:
                            on_new_batch(b, st_t)
                        return b
            except Exception as e:
                if n % 20 == 1:
                    print("批次监控异常:", e)
            if timeout_min <= 0:
                break
            time.sleep(interval)
        return None

    def batch_class_plans(self, term_id: str, batch_id: str = None,
                          keyword: str = None, is_selected: bool = None,
                          page: int = 1, size: int = 100) -> dict:
        """批次课程池(逆向自 enrollment-batches/class-plans, 含 remainingCount)"""
        params = {"academicYearTermId": term_id, "enrollmentBatchId": batch_id,
                  "pageIndex": page, "pageSize": size}
        if keyword:
            params["keyword"] = keyword
        if is_selected is not None:
            params["isSelected"] = is_selected
        return self.req("GET", "enrollment-batches/class-plans", params=params) or {}


class ChangeLogger:
    """变化记录器: 所有 eligibility/余量/选课结果变化 追加到 JSONL+TXT 日志"""

    def __init__(self, path: str = None):
        here = os.path.dirname(os.path.abspath(__file__))
        self.jsonl = path or os.path.join(here, "gench_changes.log")
        self.txt = os.path.join(here, "gench_changes_readable.txt")
        self.state: Dict[str, Any] = {}

    def snapshot(self, key: str, value: Any) -> bool:
        """值变化则记日志, 返回是否变化"""
        old = self.state.get(key)
        self.state[key] = value
        if old != value:
            ts = datetime.now().strftime("%m-%d %H:%M:%S")
            with open(self.jsonl, "a", encoding="utf-8") as f:
                f.write(json.dumps({"t": ts, "key": key, "old": old, "new": value,
                                    "value": value}, ensure_ascii=False) + "\n")
            with open(self.txt, "a", encoding="utf-8") as f:
                f.write(f"[{ts}] {key}: {old!r} → {value!r}\n")
            return True
        return False


def items_of(page: Any) -> List[dict]:
    if isinstance(page, list):
        return page
    if isinstance(page, dict):
        return page.get("items") or page.get("results") or []
    return []


def show(plans: List[dict]) -> None:
    for i, p in enumerate(plans):
        course = p.get("course") or p
        full = p.get("enrolledCount", p.get("selectedCount"))
        cap = p.get("capacity", p.get("quota"))
        print(f"[{i:>3}] id={p.get('id')}  {course.get('name', '?')}  "
              f"({p.get('teacher', p.get('teachers')) or '?'})  "
              f"人数:{full if full is not None else '?'}/{cap if cap else '?'}  "
              f"学期:{p.get('academicYearTermId') or '-'}  "
              f"批次:{p.get('enrollmentBatchId') or '-'}")


def pick_exam_fields(p: dict) -> str:
    """展示课程关键字段, 便于人工挑选"""
    j = json.dumps(p, ensure_ascii=False)
    return (j[:300] + "…") if len(j) > 300 else j


def check_eligibility(c: GenchClient, quiet: bool = False) -> bool:
    """资格检查; 返回是否可以选课"""
    try:
        d = c.eligibility()
    except Exception as e:
        if not quiet:
            print(f"资格查询失败: {e}")
        return False
    if d.get("canEnroll") is False:
        if not quiet:
            print(f"⛔ 无选课资格 [{d.get('code')}]: {d.get('message')}")
            print("  → 服务端闸门, 等待资格放开(开放时间/年级限制). 脚本将持续监控…")
        return False
    if not quiet:
        print("✅ 选课资格已通过")
    return True


def watch_batches_and_eligibility(c: GenchClient, interval: float,
                                  timeout_min: float, logger: "ChangeLogger" = None,
                                  early_sec: float = 1.0) -> bool:
    """双监控:
      A. 资格闸门翻转(canEnroll true) -> 立即 True
      B. 未开始的新批次 -> 计算开抢时刻, 到点提前 early_sec 开始逐门 enroll 直至成功
    """
    deadline = time.time() + timeout_min * 60
    print(f"开始监控: 资格闸门 + 新批次 (每{interval}s, 超时{timeout_min}分钟)")
    have_pending = False
    pending_fire = None
    n = 0
    while time.time() < deadline:
        n += 1
        try:
            # A. 资格
            d = c.eligibility()
            can = d.get("canEnroll")
            if logger:
                logger.snapshot("eligibility.canEnroll", can)
            if can:
                print(f"🎉 {datetime.now():%H:%M:%S} 资格放开!")
                return True
            if n % 12 == 1:
                print(f"· 资格未放开 [{d.get('code')}] ({datetime.now():%H:%M:%S})")
        except Exception as e:
            if n % 12 == 1:
                print("资格探测异常:", e)
        try:
            # B. 批次新建/改动 => 设定 pending_fire
            b = c.batch_watcher(logger=logger, interval=0, timeout_min=0) or \
                None
        except Exception:
            b = None
        if b and not have_pending:
            try:
                from datetime import datetime as dt
                st = dt.fromisoformat(b["enrollDropStartAt"]).timestamp()
                if st > time.time():
                    have_pending = True
                    pending_fire = st
                    print(f"⏰ 捕捉到未开始批次: {b['name']} 开抢 "
                          f"{b['enrollDropStartAt']} -> 预约提前{early_sec}s 抢")
            except Exception:
                pass
        # B2: 到点提前抢
        if have_pending and pending_fire and time.time() >= pending_fire - early_sec:
            print(f"🚀 {datetime.now():%H:%M:%S} 到达提前量, 开始火力全开!")
            # 无资格也可能炸出名额窗口: 连发全部课程
            try:
                plans = items_of(c.batch_class_plans(b["academicYearTermId"], size=500))
                for p in plans:
                    try:
                        c.enroll(p["id"])
                        print(f"✅ 抢到 {p.get('courseName')} (id={p['id']})")
                        return True
                    except EnrollmentForbidden:
                        break  # 资格仍未放开, 不空转
                    except Exception:
                        continue
            except Exception as e:
                print("提前抢异常:", e)
        time.sleep(max(1.0, interval))
    print("监控超时.")
    return False
    """轮询资格, 放开瞬间返回 True; 变化写入日志; 支持回调供 GUI/CLI 联动"""
    deadline = time.time() + timeout_min * 60
    print(f"开始监控选课资格, 每 {interval}s 探测一次, 超时 {timeout_min} 分钟。Ctrl+C 退出。")
    n = 0
    while time.time() < deadline:
        try:
            n += 1
            d = c.eligibility()
            can = d.get("canEnroll")
            if logger:
                if logger.snapshot("eligibility.canEnroll", can):
                    print(f"[日志] 资格变化: {d.get('message','')} → canEnroll={can}")
            if can is False:
                if n % 10 == 1:
                    print(f"· 资格未放开 [{d.get('code')}]: {d.get('message')} (已探测 {n} 次, {datetime.now():%H:%M:%S})")
            else:
                print(f"🎉 {datetime.now():%H:%M:%S} 资格已放开!")
                if logger:
                    logger.snapshot("eligibility.canEnroll", True)
                if on_open:
                    on_open()
                return True
        except Exception as e:
            if n % 10 == 1:
                print("探测异常:", e)
        time.sleep(interval)
    print("监控超时退出。")
    return False


def interactive(c: GenchClient, args, logger: "ChangeLogger" = None) -> None:
    # 首先检查资格
    if not check_eligibility(c):
        if getattr(args, "monitor", False):
            watch_batches_and_eligibility(c, interval=max(3.0, float(args.interval) * 2),
                                          timeout_min=float(args.timeout) * 4,
                                          logger=logger,
                                          early_sec=float(getattr(args, "early", 1.0)))
        return
    if logger is not None:
        # 批次与资格快照 → gench_changes.log
        try:
            logger.snapshot("eligibility", c.eligibility())
        except Exception:
            pass
        try:
            logger.snapshot("active_batches", c.active_batches())
        except Exception:
            pass
    batches = c.active_batches()
    terms = items_of(c.req("GET", "academic-year-terms", params={"pageSize": 50}))
    term_id = batch_id = None
    if not batches:
        print("当前没有激活的选课批次 (student/enrollment-batches/active 返回空)。")
        print("可能: 批次未开放/已结束。脚本仍支持 watch 模式蹲点。")
        if terms:
            for i, t in enumerate(terms):
                print(f"[{i}] term={t['id']}  {t.get('academicYear')}-{t.get('termCode')} "
                      f"({t.get('startDate','')[:10]} ~ {t.get('endDate','')[:10]})")
            k = input("选择学期序号 (回车=最新第一条): ").strip()
            term_id = terms[int(k or 0)]["id"] if terms else None
        if not term_id:
            term_id = input("手动输入 academicYearTermId (回车跳过): ").strip()
        if not term_id:
            return
    else:
        for i, b in enumerate(batches):
            print(f"[{i}] 批次 id={b.get('id')}  {b.get('name')}  "
                  f"选退课 {b.get('enrollDropStartAt')} ~ {b.get('enrollDropEndAt')}  "
                  f"仅退课 {b.get('dropOnlyStartAt')} ~ {b.get('dropOnlyEndAt')}  "
                  f"term={b.get('academicYearTermId')}")
        k = input("选择批次序号 (回车=0): ").strip() or "0"
        batch = batches[int(k)]
        term_id, batch_id, batch_name = (str(batch["academicYearTermId"]), str(batch["id"]),
                                         batch.get("name", ""))
        print(f"已选批次: {batch_name}")

    if args.watch:
        watch(c, term_id, batch_id, args)
        return

    kw = input("搜索关键词(可空): ").strip() or None
    page = c.open_plans(term_id, batch_id, keyword=kw)
    plans = items_of(page)
    print(f"共 {page.get('total', len(plans))} 条")
    show(plans)
    if not plans:
        print("提示: 字段名可能与预期不同, 原始样例:", pick_exam_fields(plans) if plans else "无数据")
        # 打印一条原始记录帮助确认字段
        raw = c.req("GET", "student/class-plans/open",
                    params={"academicYearTermId": term_id, "pageIndex": 1, "pageSize": 1})
        print("原始返回:", json.dumps(raw, ensure_ascii=False)[:800])
        return
    k = int(input("输入要选的序号: ").strip())
    p = plans[k]
    class_plan_id = str(p["id"])
    course_id = str(p.get("courseId") or (p.get("course") or {}).get("id") or "")
    print("课程信息:", pick_exam_fields(p))
    try:
        chk = c.check(course_id, class_plan_id)
        print("check 结果:", json.dumps(chk, ensure_ascii=False)[:500] if chk is not None else "无")
    except Exception as e:
        print("check 异常(不阻断):", e)
    sure = input("确认选课? (y/N): ").strip().lower()
    if sure == "y":
        c.enroll(class_plan_id)
        print("✅ 选课请求已提交")
        print("我的选课:", json.dumps(c.my_enrollments(term_id), ensure_ascii=False)[:600])


def retry_call(fn, times=3, wait=1.0):
    for i in range(times):
        try:
            return fn()
        except Exception as e:
            if i == times - 1:
                raise
            print("  重试:", e)
            time.sleep(wait)


def watch(c: GenchClient, term_id: str, batch_id: Optional[str], args) -> None:
    """蹲点抢课: 持续刷新开放课程列表, 对目标课程检查并选课, 直到成功或超时"""
    targets = set()
    kw = input("目标课程关键词(逗号分隔多个): ").strip()
    kws = [k.strip() for k in kw.split(",") if k.strip()]
    interval = args.interval
    deadline = time.time() + args.timeout * 60
    print(f"开始蹲点, 每 {interval}s 刷一次, 超时 {args.timeout} 分钟。Ctrl+C 退出。")
    while time.time() < deadline:
        for k in kws or [""]:
            try:
                page = retry_call(lambda: c.open_plans(term_id, batch_id, keyword=k or None, size=100))
            except Exception as e:
                print("刷新失败:", e)
                continue
            plans = items_of(page)
            for p in plans:
                pid = str(p.get("id"))
                name = (p.get("course") or p).get("name", "")
                full = p.get("enrolledCount", p.get("selectedCount"))
                cap = p.get("capacity", p.get("quota"))
                has_seat = (cap is None) or (full is None) or (full < cap)
                if pid in targets:
                    continue
                if not has_seat:
                    continue
                print(f"发现有名额: {name}  id={pid}  {full}/{cap}")
                course_id = str(p.get("courseId") or (p.get("course") or {}).get("id") or "")
                try:
                    c.check(course_id, pid)
                except Exception as e:
                    print("  check:", e)
                try:
                    retry_call(lambda: c.enroll(pid))
                    print(f"✅ 已抢到: {name} (id={pid})")
                    targets.add(pid)
                except EnrollmentForbidden as e:
                    print(f"⛔ 资格被拒: {e}")
                    targets.add(pid)  # 不再对同一课程反复 403
                    # 抢到一门即转退出?取消注释以继续抢多门:
                    # return
                except Exception as e:
                    print("  抢课失败:", e)
        time.sleep(interval)
    print("超时退出。")


def main():
    import argparse
    ap = argparse.ArgumentParser(description="Gench 公选课平台选课脚本")
    ap.add_argument("--cookie=", help="", default=None)
    ap.add_argument("--watch", action="store_true", help="蹲点抢课模式")
    ap.add_argument("--monitor", action="store_true",
                    help="先查资格; 无资格则持续监控直到放开(或超时)")
    ap.add_argument("--interval", type=float, default=2.0, help="watch 轮询间隔秒(默认2)")
    ap.add_argument("--timeout", type=float, default=30, help="watch 超时分钟(默认30)")
    args = ap.parse_args()
    cookie = load_cookie()
    if args.__dict__.get("cookie"):
        cookie = args.cookie
    if not cookie:
        sys.exit("未配置 Cookie: 见文件头部说明")
    c = GenchClient(cookie)
    # 连通性自检
    try:
        c.req("GET", "student/class-plans/open", params={"pageIndex": 1, "pageSize": 1})
        print("登录态 OK")
    except PermissionError as e:
        sys.exit(str(e))
    cl = ChangeLogger()
    interactive(c, args, logger=cl)


if __name__ == "__main__":
    main()
