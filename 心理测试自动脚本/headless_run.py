# -*- coding: utf-8 -*-
"""命令行驱动: 登录 → 探测待测项 → 拉题 → AI 选择最健康答案 → 固化模板 → (可选)提交。

用法:
  python headless_run.py --account 学号 [--password 密码] [--submit] [--strategy healthiest]
默认密码 = 学号 + "#"
"""
from __future__ import annotations

import argparse
import sys
import warnings

warnings.filterwarnings("ignore")

from core import store
from core.client import PsyClient
from core.solver import build_template_section, decisions_to_map, solve_paper


def main():
    ap = argparse.ArgumentParser(description="心理测评自动答题(命令行)")
    ap.add_argument("--account", required=True)
    ap.add_argument("--password", default=None, help="默认为 学号#")
    ap.add_argument("--base", default=None)
    ap.add_argument("--strategy", default="healthiest",
                    help="healthiest | fixed:A | fixed:B")
    ap.add_argument("--submit", action="store_true", help="实际提交(默认只固化不提交)")
    ap.add_argument("--paper", default=None, help="只处理名称包含该关键字的量表")
    args = ap.parse_args()

    pwd = args.password or (args.account + "#")
    cli = PsyClient(base=args.base or __import__("core.client", fromlist=["DEFAULT_BASE"]).DEFAULT_BASE,
                    log=lambda s: print(s, flush=True))

    j = cli.login(args.account, pwd)
    if j.get("Code") != 0:
        sys.exit("登录失败: " + str(j.get("Message")))
    info = cli.get_my_info()
    print("当前用户:", info.get("RealName"), info.get("DeptName"))

    items = cli.get_publish_tests()
    pending = [it for it in items if it["status"] == "待测试"]
    print(f"共 {len(items)} 个量表, 待测试 {len(pending)} 个:")
    for it in items:
        mark = "★" if it["status"] == "待测试" else " "
        print(f"  {mark} [{it['subject']}] {it['paper_name']}({it['paper_code']}) "
              f"{it['question_count']}题 {it['status']}")

    if args.paper:
        pending = [it for it in pending if args.paper in it["paper_name"] or args.paper in it["paper_code"]]

    template = store.load_template()
    for it in pending:
        print(f"\n===== 拉取题目: {it['paper_name']} =====")
        paper = cli.get_paper(it["paper_id"], it["publish_id"], it["comtyp"])
        print(f"题目数: {len(paper.questions)}, PaperResultId: {paper.result_id}")
        decisions = solve_paper(paper.questions,
                                store.get_paper_template(template, it["paper_name"]),
                                args.strategy)
        for d in decisions[:6]:
            print(f"  {d.number:>3}. {d.question}  → {d.opt}:{d.opt_name}  ({d.reason})")
        print("  ...")
        section = build_template_section(paper.paper_id, paper.paper_name, decisions)
        store.upsert_paper(template, paper.paper_name, section)
        store.save_template(template)
        print("已固化模板 →", store.TEMPLATE_PATH)

        if args.submit:
            r = cli.submit_paper(paper, decisions_to_map(decisions))
            if r.get("Code") == 0:
                print(f"✔ {paper.paper_name} 提交成功")
            else:
                print(f"✘ {paper.paper_name} 提交失败: {r.get('Message')}")

    print("\n完成。")


if __name__ == "__main__":
    main()
