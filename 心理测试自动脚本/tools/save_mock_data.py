# -*- coding: utf-8 -*-
"""抓取真实站点数据 -> mock_data/（用真实账号一次性拉齐，供本地 mock 使用）。"""
import json
import sys
import warnings

warnings.filterwarnings("ignore")
sys.path.insert(0, ".")

from core.client import PsyClient

BASE = "https://xlcp.gench.edu.cn:8085"
ACCOUNT = sys.argv[1] if len(sys.argv) > 1 else "2611999"

import re


def capture():
    cli = PsyClient(base=BASE, min_interval=0.4, log=print)
    j = cli.login(ACCOUNT, ACCOUNT + "#")
    assert j.get("Code") == 0, j

    # 用户信息(原始双层JSON字符串也保存)
    raw = cli._req("POST", "/Mine/GetMyInfo", data={},
                   headers={"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"}).text
    open("mock_data/mine_myinfo.json", "w", encoding="utf-8").write(raw)

    raw = cli._req("POST", "/PsyTest/GetPublishTest", data={"Version": "0"},
                   headers={"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"}).text
    open("mock_data/psytest_getpublishtest.json", "w", encoding="utf-8").write(raw)

    items = cli.get_publish_tests()
    seen = set()
    for it in items:
        pid = it["paper_id"]
        if pid in seen:
            continue
        seen.add(pid)
        paper = cli.get_paper(pid, it["publish_id"], it["comtyp"])
        name = it["paper_code"].replace("/", "_")
        # 直接保存 GetPaperAllInfo 原始响应更保真: 用 paper.raw 重新组成外层
        out = {"Code": 0, "Message": "获得量表信息(Post)成功",
               "Data": [dict(paper.raw)]}
        open(f"mock_data/paper_allinfo_{pid}_{name}.json", "w", encoding="utf-8").write(
            json.dumps(json.dumps(out, ensure_ascii=False), ensure_ascii=False))
        print(f"已抓取 {it['paper_name']} 题数={len(paper.questions)}")
    print("capture 完成")


if __name__ == "__main__":
    import pathlib
    pathlib.Path("mock_data").mkdir(exist_ok=True)
    capture()
