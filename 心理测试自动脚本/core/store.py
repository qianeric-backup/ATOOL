# -*- coding: utf-8 -*-
"""配置(模板)持久化: 固化选择 / 导入 / 导出。"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"
TEMPLATE_PATH = CONFIG_DIR / "template.json"
PROFILE_PATH = CONFIG_DIR / "profile.json"

TEMPLATE_VERSION = 2


def _ensure_dir():
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def load_template(path: str | Path | None = None) -> dict:
    """返回 {papers: {量表名: {paper_id, paper_name, answers:{题key:...}}}}"""
    p = Path(path) if path else TEMPLATE_PATH
    if not p.exists():
        return {"version": TEMPLATE_VERSION, "papers": {}}
    with open(p, encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict) or "papers" not in data:
        # 兼容单量表导出格式
        if isinstance(data, dict) and "answers" in data:
            return {"version": TEMPLATE_VERSION,
                    "papers": {data.get("paper_name", "未命名"): data}}
        return {"version": TEMPLATE_VERSION, "papers": {}}
    return data


def save_template(data: dict, path: str | Path | None = None):
    _ensure_dir()
    p = Path(path) if path else TEMPLATE_PATH
    data.setdefault("version", TEMPLATE_VERSION)
    data["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    tmp = str(p) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, p)


def upsert_paper(template: dict, paper_key: str, section: dict) -> dict:
    papers = template.setdefault("papers", {})
    old = papers.get(paper_key, {})
    merged = dict(old.get("answers") or {})
    merged.update(section["answers"])  # 新选择覆盖同题
    papers[paper_key] = {
        "paper_id": section.get("paper_id", old.get("paper_id", "")),
        "paper_name": section.get("paper_name", old.get("paper_name", "")),
        "answers": merged,
    }
    return papers[paper_key]


def get_paper_template(template: dict, paper_key: str) -> dict:
    sec = (template.get("papers") or {}).get(paper_key) or {}
    return sec.get("answers") or {}


def export_to(template: dict, path: str):
    save_template(template, path)


def import_from(path: str, template: dict | None = None) -> dict:
    """导入外部模板 JSON, 合并进本地模板(按量表合并, 同题不覆盖已有? —— 以导入为准)。"""
    incoming = load_template(path)
    base = template if template is not None else load_template()
    papers = base.setdefault("papers", {})
    for key, sec in (incoming.get("papers") or {}).items():
        old = papers.get(key, {})
        merged = dict(old.get("answers") or {})
        merged.update(sec.get("answers") or {})
        papers[key] = {"paper_id": sec.get("paper_id", old.get("paper_id", "")),
                       "paper_name": sec.get("paper_name", old.get("paper_name", "")),
                       "answers": merged}
    save_template(base)
    return base


def load_profile() -> dict:
    p = PROFILE_PATH
    if p.exists():
        try:
            with open(p, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def save_profile(profile: dict):
    _ensure_dir()
    profile = dict(profile)
    profile.pop("password", None)  # 不落盘密码
    with open(PROFILE_PATH, "w", encoding="utf-8") as f:
        json.dump(profile, f, ensure_ascii=False, indent=2)
