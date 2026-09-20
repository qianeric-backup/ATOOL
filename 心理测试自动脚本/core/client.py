# -*- coding: utf-8 -*-
"""心理测评平台 HTTP 客户端。

站点: https://xlcp.gench.edu.cn:8085 (ASP.NET MVC, 会话 Cookie 鉴权)

协议要点(逆向自前端 JS):
- 登录:  POST /Home/UserLogin,  account/PWD 均为 RSA(PKCS1 v1.5) 加密, 公钥硬编码于 /Scripts/login.js
- 验证码: 仅前端校验(与 #code_box 文本比对), 服务端不接收验证码字段;
          兼容图片验证码站点 —— 命中 <img> 时自动用 ddddocr 识别
- 待测项: POST /PsyTest/GetPublishTest {Version:"0"}   (IsTest=0 且 IsCanTest=1 即待测)
- 题目:  POST /PsyTest/GetPaperAllInfo {PaperID, IsTemp:"1", PublishId, ComTypCode}
- 提交:  POST /PsyTest/SumitPaperInfo (注意站点拼写 Sumit), TmpResult = ";qid|aid|start|end||0"...
"""
from __future__ import annotations

import base64
import json
import random
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta

import requests
from Crypto.Cipher import PKCS1_v1_5
from Crypto.PublicKey import RSA

try:  # 可选依赖: 仅在目标站点为真图片验证码时需要
    import ddddocr  # type: ignore

    _OCR = None

    def _get_ocr():
        global _OCR
        if _OCR is None:
            _OCR = ddddocr.DdddOcr(show_ad=False)
        return _OCR

    HAS_DDDDOCR = True
except Exception:  # pragma: no cover
    HAS_DDDDOCR = False

    def _get_ocr():  # type: ignore
        raise RuntimeError("ddddocr 未安装: pip install ddddocr")


DEFAULT_BASE = "https://xlcp.gench.edu.cn:8085"
UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1"
)
RSA_PUBKEY = (
    "MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQCP4ScAkCWwuyP6Rq5vWSHi8prr8RkUuH5F4lPxO/ZZE5VkH2stG81TCPdVnQhMURj2k2rohjujExcjsiHedUmuT34U"
    "iLfBsvcZFzDTijiwXIqNJag8RzNQ5h8JGbXZ7BS3TaBtb0670klF/O0FSGHwzTBJ+oY7ounj/V7w2bg3yQIDAQAB"
)
TIME_FMT = "%Y-%m-%d %H:%M:%S"


def deep_json(x):
    """站点接口返回双层 JSON 编码(字符串套 JSON), 循环解包。"""
    while isinstance(x, str):
        x = json.loads(x)
    return x


def rsa_encrypt(plain: str, pubkey_b64: str = RSA_PUBKEY) -> str:
    key = RSA.import_key(base64.b64decode(pubkey_b64.replace(" ", "")))
    cipher = PKCS1_v1_5.new(key)
    return base64.b64encode(cipher.encrypt(plain.encode("utf-8"))).decode()


@dataclass
class Question:
    qid: str
    number: int
    name: str
    answers: list = field(default_factory=list)  # [{aid,opt,name,score,skip_id,skip_num}]
    raw: dict = field(default_factory=dict)


@dataclass
class Paper:
    paper_id: str
    paper_name: str
    paper_code: str
    publish_id: str
    result_id: str
    treatment_id: str
    comtyp: str
    questions: list = field(default_factory=list)  # [Question]
    raw: dict = field(default_factory=dict)


class PsyClient:
    """一个客户端实例 = 一个会话。线程安全性: 串行使用。"""

    def __init__(self, base: str = DEFAULT_BASE, verify: bool = False,
                 min_interval: float = 0.45, log=None):
        self.base = base.rstrip("/")
        self.verify = verify
        self.min_interval = min_interval
        self._last_req = 0.0
        self.log = log or (lambda s: None)
        self.session = requests.Session()
        self.session.verify = verify
        self.session.headers.update({
            "User-Agent": UA,
            "X-Requested-With": "XMLHttpRequest",
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Origin": self.base,
        })
        self.account: str | None = None

    # ---------- 底层 ----------
    def _pace(self):
        wait = self.min_interval - (time.time() - self._last_req)
        if wait > 0:
            time.sleep(wait)

    def _req(self, method: str, path: str, **kw) -> requests.Response:
        self._pace()
        url = path if path.startswith("http") else self.base + path
        r = self.session.request(method, url, timeout=30, **kw)
        self._last_req = time.time()
        return r

    def _post_json(self, path: str, data: dict, referer: str = "/PsyTest/Index?f=1") -> dict:
        r = self._req("POST", path, data=data,
                      headers={"Referer": self.base + referer,
                               "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"})
        try:
            return deep_json(r.text)
        except Exception:
            return {"Code": -100, "Message": f"响应解析失败: {r.text[:200]}"}

    # ---------- 登录 ----------
    def get_login_captcha(self):
        """拉登录页, 返回 (html, kind, payload)。

        kind='text'  -> payload 为 #code_box 中的 4 位文本(前端生成, 服务端不校验)
        kind='image' -> payload 为验证码图片 bytes, 需 ddddocr
        """
        r = self._req("GET", "/Home/Login?t=PsyTest&f=1")
        html = r.text
        m = re.search(r'<div[^>]*id="code_box"[^>]*>\s*(.*?)\s*</div>', html, re.S)
        if m:
            text = re.sub(r"<[^>]+>", "", m.group(1)).strip()
            if text:
                return html, "text", text
        m = re.search(r'<img[^>]+(?:id|src)[^>]*>', html)
        img = None
        for m2 in re.finditer(r'<img[^>]+src="([^"]+)"[^>]*>', html):
            src = m2.group(1)
            if re.search(r"(code|verify|valid|captcha|yzm)", src, re.I):
                img = src
                break
        if img:
            ir = self._req("GET", img if img.startswith("http") else self.base + img)
            return html, "image", ir.content
        return html, "none", ""

    @staticmethod
    def ocr_image(data: bytes) -> str:
        return _get_ocr().classification(data)

    def login(self, account: str, password: str, captcha: str | None = None) -> dict:
        """登录。captcha 为空时自动从登录页解析/OCR。"""
        html, kind, payload = self.get_login_captcha()
        if captcha is None:
            if kind == "text":
                captcha = payload
                self.log(f"验证码(前端文本,自动获取): {captcha}")
            elif kind == "image":
                if not HAS_DDDDOCR:
                    raise RuntimeError("该站点为图片验证码, 需要 ddddocr: pip install ddddocr")
                captcha = self.ocr_image(payload)
                self.log(f"验证码(ddddocr 识别): {captcha}")
            else:
                captcha = "0000"  # 服务端不校验
        data = {"account": rsa_encrypt(account), "PWD": rsa_encrypt(password)}
        r = self._req("POST", "/Home/UserLogin", data=data,
                      headers={"Referer": self.base + "/Home/Login?t=PsyTest&f=1",
                               "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"})
        try:
            j = deep_json(r.text)
        except Exception:
            j = {"Code": -100, "Message": r.text[:200]}
        if j.get("Code") == 0:
            self.account = account
            self.log(f"登录成功: {account}")
        else:
            self.log(f"登录失败: {j.get('Message', j)}")
        return j

    def check_login(self) -> bool:
        j = self._post_json("/Home/CheckLogin", {})
        # 站点语义: Code=1(或0) 已登录 / -1 未登录; 旧版 `!= -1` 会把"响应解析失败"
        # (-100, 会话失效返回登录页 HTML) 误判为已登录; -100 一律视为未登录
        return j.get("Code") in (0, 1)

    def get_my_info(self) -> dict:
        j = self._post_json("/Mine/GetMyInfo", {})
        if isinstance(j, dict) and j.get("Code") == -1:
            return {}
        return j if isinstance(j, dict) else {}

    # ---------- 待测项探测 ----------
    def get_publish_tests(self) -> list[dict]:
        """返回展平后的量表列表, 每项含 publish/paper/状态字段。"""
        j = self._post_json("/PsyTest/GetPublishTest", {"Version": "0"})
        if j.get("Code") != 0:
            self.log(f"GetPublishTest 失败: {j.get('Message')}")
            return []
        out = []
        for pub in j.get("Data") or []:
            for it in pub.get("List") or []:
                out.append({
                    "publish_id": pub.get("PublishID", ""),
                    "subject": pub.get("PublishSubject", ""),
                    "valid": f"{pub.get('ValidStartDate','')} ~ {pub.get('ValidEndDate','')}",
                    "paper_id": it.get("PaperID", ""),
                    "paper_code": it.get("PaperCode", ""),
                    "paper_name": it.get("PaperName", ""),
                    "recommend": re.sub(r"<[^>]+>", "", it.get("PaperRecommend", "") or ""),
                    "question_count": it.get("QuestionCount", 0),
                    "comtyp": (it.get("ComTypCode") or "001"),
                    "is_test": int(it.get("IsTest") or 0),
                    "is_can_test": int(it.get("IsCanTest") or 0),
                    "status": "已完成" if int(it.get("IsTest") or 0) > 0
                              else ("待测试" if int(it.get("IsCanTest") or 0) == 1 else "不可测"),
                })
        return out

    def get_gauge_classify(self) -> list[dict]:
        """自测量表分类(供探索用)。"""
        j = self._post_json("/PsyTest/GetGaugeClassifyInfo", {"PaperID": "0", "PageCount": "20"})
        if j.get("Code") != 0:
            return []
        return j.get("Data") or []

    # ---------- 拉取题目 ----------
    def get_paper(self, paper_id: str, publish_id: str, comtyp: str = "001") -> Paper:
        j = self._post_json("/PsyTest/GetPaperAllInfo",
                            {"PaperID": paper_id, "IsTemp": "1",
                             "PublishId": publish_id, "ComTypCode": comtyp})
        if j.get("Code") != 0:
            raise RuntimeError(f"获取题目失败: {j.get('Message')}")
        p = (j.get("Data") or [{}])[0]
        qs = []
        for q in p.get("QuestionList") or []:
            answers = [{
                "aid": a.get("AnswerId", ""),
                "opt": a.get("AnswerOptions", ""),
                "name": (a.get("AnswerName") or "").strip(),
                "score": a.get("AnswerScore", 0.0),
                "skip_id": a.get("SkipToQuestionId", "0"),
                "skip_num": a.get("SkipToQuestionNumber", 0) or 0,
            } for a in (q.get("AnswerList") or [])]
            qs.append(Question(qid=q.get("QuestionId", ""),
                               number=q.get("QuestionNumber", 0),
                               name=(q.get("QuestionName") or "").strip(),
                               answers=answers, raw=q))
        return Paper(paper_id=p.get("PaperId", paper_id),
                     paper_name=p.get("PaperName", ""),
                     paper_code=p.get("PaperCode", ""),
                     publish_id=p.get("PublishId", publish_id),
                     result_id=p.get("PaperResultId", ""),
                     treatment_id=str(p.get("TreatmentId", "0") or "0"),
                     comtyp=p.get("ComTypCode") or comtyp,
                     questions=qs, raw=p)

    # ---------- 提交 ----------
    def submit_paper(self, paper: Paper, decisions: dict, *,
                     humanize: bool = True, start_dt: datetime | None = None) -> dict:
        """decisions: {qid: aid}。humanize=True 时逐题时间随机铺开, 拟真作答节奏。"""
        n = len(paper.questions)
        if n == 0:
            raise RuntimeError("该量表没有题目")
        now = start_dt or datetime.now()
        if humanize:
            t0 = now - timedelta(seconds=random.randint(40, 120) + n * random.uniform(2.0, 5.5))
        else:
            t0 = now - timedelta(seconds=n * 2)
        tmp_parts = []
        t = t0
        for q in paper.questions:
            aid = decisions.get(q.qid)
            if not aid:
                continue
            start = t
            step = random.uniform(1.8, 4.5) if humanize else 1.0
            end = start + timedelta(seconds=step)
            t = end
            # 与前端 GetTmpAnswer 完全一致: ;QuestionID|AnswerId|Start|End|AnswerResult|PAnswerID
            tmp_parts.append(f";{q.qid}|{aid}|{start.strftime(TIME_FMT)}|{end.strftime(TIME_FMT)}||0")
        tmp_result = "".join(tmp_parts)
        payload = {
            "PaperId": paper.paper_id,
            "PaperResultId": paper.result_id,
            "PublishId": paper.publish_id,
            "PaperTestProgress": "0",
            "TreatmentId": paper.treatment_id,
            "StartDateTime": t0.strftime(TIME_FMT),
            "EndDateTime": datetime.now().strftime(TIME_FMT),
            "ModuleId": "APP",
            "ComTypCode": paper.comtyp,
            "TmpResult": tmp_result,
            "IsSimple": "1",
        }
        j = self._post_json("/PsyTest/SumitPaperInfo", payload)
        if j.get("Code") == 0:
            self.log(f"提交成功: {paper.paper_name}")
        else:
            self.log(f"提交失败: {j.get('Message', j)}")
        return j

    def save_tmp(self, paper: Paper, decisions: dict, progress: int) -> dict:
        """临时保存(断点续测用)。"""
        parts = [f";{q.qid}|{decisions[q.qid]}|{datetime.now().strftime(TIME_FMT)}|{datetime.now().strftime(TIME_FMT)}||0"
                 for q in paper.questions if q.qid in decisions]
        payload = {
            "PaperId": paper.paper_id,
            "PaperResultId": paper.result_id,
            "PublishId": paper.publish_id,
            "PaperTestProgress": str(progress),
            "TreatmentId": paper.treatment_id,
            "StartDateTime": datetime.now().strftime(TIME_FMT),
            "EndDateTime": datetime.now().strftime(TIME_FMT),
            "ModuleId": "APP",
            "ComTypCode": paper.comtyp,
            "TmpResult": "".join(parts),
            "IsSimple": "1",
        }
        return self._post_json("/PsyTest/SaveTmpPaperInfo", payload)

    # ---------- 会话持久化 ----------
    def export_session(self) -> dict:
        return {"base": self.base, "cookies": self.session.cookies.get_dict()}

    def import_session(self, state: dict):
        self.base = state.get("base", self.base)
        for k, v in (state.get("cookies") or {}).items():
            self.session.cookies.set(k, v)
