# -*- coding: utf-8 -*-
"""“心理健康”作答求解器 + 模板固化。

策略:
1. 模板命中(题面文本精确/模糊匹配) —— 他人复用同一量表时直接复用选择
2. 选项分值最低(AnswerScore 最小 = 症状最轻) —— 适用于症状类量表(UPI/SCL-90 等)
3. 极性启发:
   - 反向题(题面积极: 良好/开朗/朝气蓬勃/受欢迎...) → 选肯定项(有/是/经常)
   - 症状题(默认) → 选否定项(没有/否/无/从不)
   - 程度量表(从无..严重) → 症状题选最轻, 反向题选最重
4. 兜底: 中间选项, 标记为“建议人工复核”
"""
from __future__ import annotations

import difflib
import re
from dataclasses import dataclass

POSITIVE_HINTS = (
    "良好", "开朗", "朝气蓬勃", "受欢迎", "人缘", "愉快", "身体健康", "满意",
    "自信", "成功", "幸福", "活泼", "坚强", "乐观", "精力充沛", "心情好",
)

# 选项名 -> 症状强度等级(0 最轻)
INTENSITY = [
    ("从无|从不|从来不|从来没有|完全没有|没有|无|不|否|极少|没有过", 0),
    ("很轻|很少|轻微|稍微|几乎不|较少|比较少", 1),
    ("中等|有时|偶尔|一般|偶尔有|说不清", 2),
    ("偏重|经常|常常|较多|相当多|比较多|常常有", 3),
    ("严重|总是|一直|老是|全部|非常|总是有", 4),
]

AFFIRM_WORDS = {"有", "是", "对", "符合", "经常", "总是", "正确", "同意"}
DENY_WORDS = {"没有", "否", "无", "从不", "不是", "不同意", "从来没有"}


def normalize(text: str) -> str:
    """题面文本归一化, 作为模板 key。"""
    if not text:
        return ""
    t = text.strip().lower()
    t = re.sub(r"[\s\d\.\、\,\。\?\?\!\!\:：;；\"\'\(\)（）\[\]【】\-—_·]+", "", t)
    return t


@dataclass
class Decision:
    qid: str
    number: int
    question: str
    aid: str
    opt: str
    opt_name: str
    reason: str


def _intensity(opt_name: str) -> int | None:
    for pat, lvl in INTENSITY:
        if re.fullmatch(pat, opt_name.strip()):
            return lvl
    for pat, lvl in INTENSITY:
        if re.search(pat, opt_name.strip()):
            return lvl
    return None


def _is_positive(question: str) -> bool:
    q = question
    if re.search(r"(不|没有|无法|缺乏|难受|痛苦)", q) and any(h in q for h in POSITIVE_HINTS):
        return False
    return any(h in q for h in POSITIVE_HINTS)


def _pick_by_polarity(qname: str, answers: list[dict]) -> tuple[int, str]:
    positive = _is_positive(qname)
    # 1) 是/否二值: 反向题选肯定, 症状题选否定
    affirm_idx = deny_idx = None
    for i, a in enumerate(answers):
        name = a["name"].strip()
        if name in AFFIRM_WORDS and affirm_idx is None:
            affirm_idx = i
        if name in DENY_WORDS and deny_idx is None:
            deny_idx = i
    if positive and affirm_idx is not None:
        return affirm_idx, "反向题(积极表述)→肯定项"
    if not positive and deny_idx is not None:
        return deny_idx, "症状题→否定项(症状最轻)"
    # 2) 程度量表: 按强度等级
    levels = [(i, _intensity(a["name"])) for i, a in enumerate(answers)]
    if all(lvl is not None for _, lvl in levels):
        key = (lambda x: x[1]) if not positive else (lambda x: -x[1])
        best = min(levels, key=key)
        tag = "反向题→程度最重(积极)" if positive else "症状题→程度最轻"
        return best[0], tag
    return -1, ""


def solve_question(q, template: dict | None = None, strategy: str = "healthiest") -> tuple[int, str]:
    """返回 (选项下标, 依据说明)。strategy: healthiest | fixed:<字母>"""
    answers = q.answers
    if not answers:
        raise ValueError(f"题 {q.number} 无选项")
    # 0) 固定字母策略
    if strategy.startswith("fixed:"):
        letter = strategy.split(":", 1)[1].strip().upper()
        for i, a in enumerate(answers):
            if a["opt"].upper() == letter:
                return i, f"固定选择 {letter}"
    # 1) 模板命中
    if template:
        key = normalize(q.name)
        hit = template.get(key)
        if hit is None and key:  # 模糊匹配
            for k, v in template.items():
                if k and difflib.SequenceMatcher(None, key, k).ratio() >= 0.92:
                    hit = v
                    break
        if hit:
            want_opt = (hit.get("opt") or "").upper()
            want_name = (hit.get("option_name") or "").strip()
            for i, a in enumerate(answers):
                if want_opt and a["opt"].upper() == want_opt:
                    return i, "模板命中"
                if want_name and a["name"] == want_name:
                    return i, "模板命中"
    # 2) 分值最低
    if strategy == "healthiest":
        scores = [float(a.get("score") or 0) for a in answers]
        lo = min(scores)
        hi = max(scores)
        if hi > lo:
            lows = [i for i, s in enumerate(scores) if s == lo]
            if len(lows) == 1:
                return lows[0], f"最低症状分({lo:g})"
            # 并列最低 → 极性判断
            idx, why = _pick_by_polarity(q.name, answers)
            if idx >= 0:
                return idx, why + "(最低分并列)"
            return lows[0], f"最低症状分({lo:g},并列取首个)"
        # 3) 全部同分 → 极性启发
        idx, why = _pick_by_polarity(q.name, answers)
        if idx >= 0:
            return idx, why
    # 4) 兜底: 中间选项
    mid = len(answers) // 2
    return mid, "无规则命中,选中间项(建议复核)"


def solve_paper(questions, template: dict | None = None, strategy: str = "healthiest") -> list[Decision]:
    """questions: [Question]; 返回逐题 Decision 列表。"""
    out: list[Decision] = []
    for q in questions:
        idx, why = solve_question(q, template, strategy)
        a = q.answers[idx]
        out.append(Decision(qid=q.qid, number=q.number, question=q.name,
                            aid=a["aid"], opt=a["opt"], opt_name=a["name"], reason=why))
    return out


def decisions_to_map(decisions: list[Decision]) -> dict:
    return {d.qid: d.aid for d in decisions}


def build_template_section(paper_id: str, paper_name: str, decisions: list[Decision]) -> dict:
    """固化: 题面 -> 选项。"""
    answers = {}
    for d in decisions:
        answers[normalize(d.question)] = {
            "number": d.number,
            "question": d.question,
            "opt": d.opt,
            "option_name": d.opt_name,
            "answer_id": d.aid,
            "reason": d.reason,
        }
    return {"paper_id": paper_id, "paper_name": paper_name, "answers": answers}
