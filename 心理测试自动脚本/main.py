# -*- coding: utf-8 -*-
"""心理测评自动答题 - PySide6 GUI

功能:
- 登录(学号+密码[默认学号#]+验证码自动处理: 前端文本直接读取 / 图片验证码 ddddocr OCR)
- 自动探测待测试项(GetPublishTest: IsTest=0 且 IsCanTest=1)
- 拉取题目并按“心理健康”策略生成答案, 逐题可改
- 固化当前选择到本地模板(JSON), 支持导入/导出, 他人复用
- 一键提交全部已装载量表(拟真逐题耗时)
"""
from __future__ import annotations

import sys
import traceback
import warnings

warnings.filterwarnings("ignore")

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QColor, QFont, QImage, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QCheckBox, QComboBox, QFileDialog,
    QFormLayout, QGroupBox, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
    QMainWindow, QMessageBox, QPlainTextEdit, QPushButton, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget,
)

from core import store
from core.client import DEFAULT_BASE, PsyClient
from core.solver import (
    Decision,
    build_template_section,
    decisions_to_map,
    solve_paper,
)

APP_TITLE = "心理测评自动答题工具"


# ---------------------------------------------------------------- workers
class Worker(QThread):
    """通用任务线程: run() 里执行 fn, 结果经 done 发出。"""
    done = Signal(object)
    fail = Signal(str)
    log = Signal(str)

    def __init__(self, fn, parent=None):
        super().__init__(parent)
        self._fn = fn

    def run(self):
        try:
            result = self._fn(lambda s: self.log.emit(s))
            self.done.emit(result)
        except Exception as e:  # noqa: BLE001
            self.fail.emit(f"{type(e).__name__}: {e}")


# ---------------------------------------------------------------- main window
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_TITLE)
        self.resize(1080, 760)

        self.client: PsyClient | None = None
        self.template = store.load_template()
        # session_papers: {paper_name: {"item":…, "paper": Paper, "decisions":[Decision]}}
        self.session_papers: dict[str, dict] = {}
        self.publish_items: list[dict] = []
        self._busy = False
        self._submit_queue: list[str] = []
        self._submit_ok: list[str] = []
        self._submit_err: list[str] = []

        self._build_ui()
        self._restore_profile()

    # ------------------------------------------------ UI 构建
    def _restore_profile(self):
        prof = store.load_profile()
        self.ed_account.setText(prof.get("account", ""))
        self.ed_site.setText(prof.get("site", DEFAULT_BASE))

    def _save_profile(self):
        store.save_profile({"account": self.ed_account.text().strip(),
                            "site": self.ed_site.text().strip()})

    def _build_login_box(self):
        box = QGroupBox("登录")
        form = QFormLayout(box)

        self.ed_site = QLineEdit(self)
        self.ed_site.setPlaceholderText(DEFAULT_BASE)
        form.addRow("站点地址", self.ed_site)

        self.ed_account = QLineEdit(self)
        self.ed_account.setPlaceholderText("学号")
        form.addRow("学号", self.ed_account)

        self.ck_auto_pwd = QCheckBox("密码 = 学号 + #", self)
        self.ck_auto_pwd.setChecked(True)
        self.ed_password = QLineEdit(self)
        self.ed_password.setEchoMode(QLineEdit.Password)
        self.ed_password.setPlaceholderText("留空且勾选上方时自动为 学号#")
        hp = QHBoxLayout()
        hp.addWidget(self.ed_password, 1)
        hp.addWidget(self.ck_auto_pwd)
        form.addRow("密码", hp)

        self.ed_captcha = QLineEdit(self)
        self.ed_captcha.setPlaceholderText("自动识别, 一般无需手填")
        self.lb_captcha = QLabel("-", self)
        self.lb_captcha.setStyleSheet(
            "background:#ff4400;color:#fff;padding:4px 10px;font-weight:bold;")
        self.btn_refresh_captcha = QPushButton("刷新验证码", self)
        hb = QHBoxLayout()
        hb.addWidget(self.ed_captcha, 1)
        hb.addWidget(self.lb_captcha)
        hb.addWidget(self.btn_refresh_captcha)
        form.addRow("验证码", hb)

        self.btn_login = QPushButton("登 录", self)
        self.btn_login.setStyleSheet("font-weight:bold;")
        self.lb_user = QLabel("未登录", self)
        hl = QHBoxLayout()
        hl.addWidget(self.btn_login, 0)
        hl.addWidget(self.lb_user, 1)
        form.addRow(hl)

        self.ed_account.textChanged.connect(self._autofill_pwd)
        self.ck_auto_pwd.toggled.connect(self._autofill_pwd)
        self.btn_login.clicked.connect(self.do_login)
        self.btn_refresh_captcha.clicked.connect(self.do_refresh_captcha)
        return box

    def _autofill_pwd(self):
        if self.ck_auto_pwd.isChecked():
            self.ed_password.setText(self.ed_account.text().strip() + "#")

    def _build_action_box(self):
        box = QGroupBox("操作")
        h = QHBoxLayout(box)
        self.cb_strategy = QComboBox(self)
        self.cb_strategy.addItems(["最健康(智能)", "固定A", "固定B", "固定C"])
        self.cb_strategy.setToolTip("固定字母策略用于人格类量表(如16PF)按字母统一作答")
        self.ck_humanize = QCheckBox("拟真作答节奏", self)
        self.ck_humanize.setChecked(True)
        self.ck_humanize.setToolTip("逐题随机 2~6 秒, 拉满作答耗时, 避免秒交被风控")

        self.btn_detect = QPushButton("① 自动探测待测项")
        self.btn_freeze = QPushButton("固化当前选择到模板")
        self.btn_import = QPushButton("导入配置")
        self.btn_export = QPushButton("导出配置")
        self.btn_submit = QPushButton("提交所选量表")
        self.btn_submit.setStyleSheet("color:#b00;font-weight:bold;")
        for b in (self.btn_detect, self.btn_freeze, self.btn_import,
                  self.btn_export, self.btn_submit):
            b.clicked.connect(lambda _, x=b: self._on_action(x))
        h.addWidget(self.btn_detect)
        h.addWidget(QLabel("策略:"))
        h.addWidget(self.cb_strategy)
        h.addWidget(self.ck_humanize)
        h.addStretch(1)
        h.addWidget(self.btn_freeze)
        h.addWidget(self.btn_import)
        h.addWidget(self.btn_export)
        h.addWidget(self.btn_submit)
        return box

    def _build_tables(self):
        self.lb_paper = QLabel("已装载题目: (无)", self)
        self.cb_paper = QComboBox(self)
        self.cb_paper.currentTextChanged.connect(self.show_paper_decisions)

        self.tbl_pending = QTableWidget(self)
        self.tbl_pending.setColumnCount(6)
        self.tbl_pending.setHorizontalHeaderLabels(
            ["选", "发布主题", "量表", "题数", "有效期", "状态"])
        self.tbl_pendinghorizontal = None
        self.tbl_pending.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.Stretch)
        self.tbl_pending.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tbl_pending.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tbl_pending.itemChanged.connect(self._on_pending_check_changed)

        self.tbl_decide = QTableWidget(self)
        self.tbl_decide.setColumnCount(4)
        self.tbl_decide.setHorizontalHeaderLabels(["题号", "题面", "选择", "依据"])
        self.tbl_decide.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.Stretch)
        self.tbl_decide.horizontalHeader().setSectionResizeMode(
            3, QHeaderView.Stretch)
        self.tbl_decide.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tbl_decide.itemDoubleClicked.connect(self._on_decide_dclick)

    def _build_ui(self):
        central = QWidget(self)
        root = QVBoxLayout(central)
        root.addWidget(self._build_login_box())
        root.addWidget(self._build_action_box())

        self._build_tables()
        root.addWidget(QLabel("待测试项(勾选后点“提交所选量表”; 双击行可直接拉取该量表):"))
        root.addWidget(self.tbl_pending, 3)
        pbar = QHBoxLayout()
        pbar.addWidget(self.lb_paper)
        pbar.addWidget(self.cb_paper, 1)
        root.addLayout(pbar)
        root.addWidget(QLabel("题目决策(双击“选择”列循环切换 A/B/C...):"))
        root.addWidget(self.tbl_decide, 5)

        self.txt_log = QPlainTextEdit(self)
        self.txt_log.setReadOnly(True)
        self.txt_log.setFont(QFont("Consolas", 9))
        self.txt_log.setMaximumHeight(140)
        root.addWidget(self.txt_log)
        self.setCentralWidget(central)

    # ------------------------------------------------ 日志/忙碌
    def log(self, msg: str):
        self.txt_log.appendPlainText(f"[{QTime_now()}] {msg}")

    def _set_busy(self, busy: bool, note: str = ""):
        self._busy = busy
        for b in (self.btn_login, self.btn_detect, self.btn_freeze,
                  self.btn_import, self.btn_export, self.btn_submit,
                  self.btn_refresh_captcha):
            b.setEnabled(not busy)
        self.setWindowTitle(APP_TITLE + (f" - {note}" if note else ""))

    # ------------------------------------------------ 登录
    def _make_client(self) -> PsyClient:
        base = self.ed_site.text().strip() or DEFAULT_BASE
        cli = PsyClient(base=base, log=lambda s: None)
        return cli

    def do_refresh_captcha(self):
        if self._busy:
            return
        if self.client is None:
            self.client = self._make_client()
        self._set_busy(True, "获取验证码")
        w = Worker(lambda log: self.client.get_login_captcha())
        w.log.connect(self.log)
        w.done.connect(self._on_captcha)
        w.fail.connect(lambda e: self._on_fail(e, "验证码获取失败"))
        w.start()
        self._worker = w

    def _on_captcha(self, result):
        self._set_busy(False)
        html, kind, payload = result
        if kind == "text":
            self.lb_captcha.setText(payload)
            self.ed_captcha.setText(payload)
            self.log(f"验证码(前端文本,自动读取): {payload}")
        elif kind == "image":
            img = QImage.fromData(payload)
            self.lb_captcha.setPixmap(QPixmap.fromImage(img).scaled(
                self.lb_captcha.size() * 2))
            if self.client.HAS_DDDDOCR:
                code = self.client.ocr_image(payload)
                self.ed_captcha.setText(code)
                self.log(f"验证码(ddddocr识别): {code}")
            else:
                self.log("图片验证码已显示, 请手填(或安装 ddddocr)")
        else:
            self.lb_captcha.setText("无")
            self.log("登录页无验证码元素, 用占位值即可")

    def do_login(self):
        if self._busy:
            return
        account = self.ed_account.text().strip()
        if not account:
            QMessageBox.warning(self, APP_TITLE, "请输入学号")
            return
        pwd = self.ed_password.text().strip()
        if self.ck_auto_pwd.isChecked() and not pwd:
            pwd = account + "#"
        if self.client is None:
            self.client = self._make_client()
        captcha = self.ed_captcha.text().strip() or None
        self._save_profile()
        self._set_busy(True, "登录中")
        self.log(f"开始登录: {account}")

        def task(log):
            j = self.client.login(account, pwd, captcha)
            if j.get("Code") != 0:
                return {"Code": j.get("Code", -1), "Message": j.get("Message", "登录失败")}
            # 用户信息同样在工作线程拉取, 避免 GUI 主线程网络阻塞导致卡死
            log("获取用户信息...")
            return {"Code": 0, "login": j, "info": self.client.get_my_info()}

        w = Worker(task)
        w.log.connect(self.log)
        w.done.connect(self._on_login)
        w.fail.connect(lambda e: self._on_fail(e, "登录失败"))
        w.start()
        self._worker = w

    def _on_login(self, result):
        if result.get("Code") == 0:
            info = result.get("info") or {}
            name = info.get("RealName", "")
            dept = info.get("DeptName", "")
            self.lb_user.setText(f"✔ {name}  {dept}")
            self.log(f"登录成功: {name}({self.client.account}) {dept}")
            self._set_busy(False)
            self.do_detect()
        else:
            self._set_busy(False)
            QMessageBox.critical(self, APP_TITLE,
                                 f"登录失败: {result.get('Message', result)}")

    def _on_fail(self, err: str, title: str):
        self._set_busy(False)
        self.log(f"[失败] {err}")
        QMessageBox.critical(self, APP_TITLE, f"{title}\n{err}")

    # ------------------------------------------------ 探测/拉取/作答
    def _strategy(self) -> str:
        s = self.cb_strategy.currentText()
        if s.startswith("固定"):
            return "fixed:" + s[-1]
        return "healthiest"

    def do_detect(self):
        if self._busy or self.client is None:
            self.log("请先登录")
            return
        self._set_busy(True, "探测待测项")
        w = Worker(lambda log: self.client.get_publish_tests())
        w.log.connect(self.log)
        w.done.connect(self._on_detect)
        w.fail.connect(lambda e: self._on_fail(e, "探测失败"))
        w.start()
        self._worker = w

    def _on_detect(self, items):
        self._set_busy(False)
        self.publish_items = items
        self.tbl_pending.setRowCount(0)
        self.tbl_pending.blockSignals(True)
        for it in items:
            row = self.tbl_pending.rowCount()
            self.tbl_pending.insertRow(row)
            vals = [it["subject"], f"{it['paper_name']}({it['paper_code']})",
                    str(it["question_count"] or ""), it["valid"], it["status"]]
            chk = QTableWidgetItem()
            chk.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
            chk.setCheckState(Qt.Checked if it["status"] == "待测试" else Qt.Unchecked)
            self.tbl_pending.setItem(row, 0, chk)
            for c, v in enumerate(vals, start=1):
                cell = QTableWidgetItem(v)
                if it["status"] == "待测试":
                    cell.setForeground(QColor("#c00"))
                elif it["status"] == "已完成":
                    cell.setForeground(QColor("#0a0"))
                self.tbl_pending.setItem(row, c, cell)
        self.tbl_pending.blockSignals(False)
        n_pending = sum(1 for i in items if i["status"] == "待测试")
        self.log(f"探测完成: 共{len(items)}个量表, 待测试{n_pending}个")
        if n_pending == 0 and items:
            self.log("全部量表已完成 ✔")

    def _on_pending_check_changed(self, _item):
        pass  # 勾选仅作为提交范围标记

    def _selected_pending(self) -> list[dict]:
        out = []
        for row in range(self.tbl_pending.rowCount()):
            if row >= len(self.publish_items):
                continue
            if self.tbl_pending.item(row, 0).checkState() == Qt.Checked:
                out.append(self.publish_items[row])
        return out

    def do_fetch_solve(self, item: dict | None = None):
        """拉取题目并 AI 作答。item 为空时处理所有勾选的待测项。"""
        if self._busy:
            return
        targets = [item] if item else self._selected_pending()
        targets = [t for t in targets if t and t["status"] == "待测试"]
        if not targets:
            QMessageBox.information(self, APP_TITLE, "没有勾选任何待测试项")
            return
        tpl_papers = self.template.get("papers") or {}
        self._set_busy(True, "拉取题目并AI作答")

        def task(log):
            for it in targets:
                if self.client is None:
                    raise RuntimeError("未登录")
                log(f"拉取: {it['paper_name']}")
                paper = self.client.get_paper(it["paper_id"], it["publish_id"], it["comtyp"])
                tpl = tpl_papers.get(it["paper_name"], {}).get("answers") or {}
                decisions = solve_paper(paper.questions, tpl, self._strategy())
                self.session_papers[it["paper_name"]] = {
                    "item": it, "paper": paper, "decisions": decisions}
                log(f"完成: {it['paper_name']} {len(decisions)}题")
            return list(self.session_papers.keys())

        w = Worker(task)
        w.log.connect(self.log)
        w.done.connect(self._on_fetched)
        w.fail.connect(lambda e: self._on_fail(e, "拉取/作答失败"))
        w.start()
        self._worker = w

    def _on_fetched(self, paper_names):
        self._set_busy(False)
        self.cb_paper.blockSignals(True)
        cur = self.cb_paper.currentText()
        self.cb_paper.clear()
        self.cb_paper.addItems(paper_names)
        if cur in paper_names:
            self.cb_paper.setCurrentText(cur)
        self.cb_paper.blockSignals(False)
        if paper_names:
            self.cb_paper.setCurrentText(paper_names[-1])
            self.show_paper_decisions(paper_names[-1])
        self.log("AI作答完成, 可在下方逐题双击修改, 然后“固化当前选择到模板”")

    def show_paper_decisions(self, paper_name: str):
        entry = self.session_papers.get(paper_name)
        if not entry:
            self.lb_paper.setText(f"已装载题目: (无)")
            return
        paper, decisions = entry["paper"], entry["decisions"]
        self.lb_paper.setText(
            f"已装载题目: {paper_name}  {len(decisions)}题")
        self.tbl_decide.setRowCount(0)
        for r, d in enumerate(decisions):
            self.tbl_decide.insertRow(r)
            for c, v in enumerate([str(d.number), d.question,
                                   f"{d.opt}:{d.opt_name}", d.reason]):
                self.tbl_decide.setItem(r, c, QTableWidgetItem(v))
            if d.reason.startswith("无规则"):
                self.tbl_decide.item(r, 3).setForeground(QColor("#b60"))

    def _on_decide_dclick(self, item):
        if item.column() != 2:
            return
        row, paper_name = item.row(), self.cb_paper.currentText()
        entry = self.session_papers.get(paper_name)
        if not entry:
            return
        d = entry["decisions"][row]
        q = next((x for x in entry["paper"].questions if x.qid == d.qid), None)
        if not q or len(q.answers) < 2:
            return
        opts = q.answers
        # 循环切换到下一选项
        try:
            cur_idx = next(i for i, a in enumerate(opts) if a["aid"] == d.aid)
        except StopIteration:
            cur_idx = 0
        a = opts[(cur_idx + 1) % len(opts)]
        d.aid, d.opt, d.opt_name, d.reason = a["aid"], a["opt"], a["name"], "人工指定"
        self.show_paper_decisions(paper_name)

    # ------------------------------------------------ 固化/导入/导出
    def do_freeze(self):
        if not self.session_papers:
            QMessageBox.information(self, APP_TITLE, "还没有装载任何题目(先探测并拉取)")
            return
        for name, entry in self.session_papers.items():
            section = build_template_section(entry["paper"].paper_id,
                                             name, entry["decisions"])
            store.upsert_paper(self.template, name, section)
        store.save_template(self.template)
        total = sum(len(s["answers"]) for s in self.template["papers"].values())
        self.log(f"已固化 {len(self.session_papers)} 个量表 → {store.TEMPLATE_PATH}"
                 f" (模板合计{total}题)")

    def do_import(self):
        path, _ = QFileDialog.getOpenFileName(self, "导入配置", "",
                                              "模板 JSON (*.json)")
        if not path:
            return
        try:
            self.template = store.import_from(path, self.template)
            n_papers = len(self.template.get("papers") or {})
            n_ans = sum(len(s.get("answers") or {}) for s in self.template["papers"].values())
            self.log(f"导入成功: {n_papers} 个量表 / {n_ans} 题 ← {path}")
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, APP_TITLE, f"导入失败: {e}")

    def do_export(self):
        path, _ = QFileDialog.getSaveFileName(self, "导出配置", "psy_template.json",
                                              "模板 JSON (*.json)")
        if not path:
            return
        try:
            store.export_to(self.template, path)
            self.log(f"导出成功 → {path}")
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, APP_TITLE, f"导出失败: {e}")

    # ------------------------------------------------ 提交
    def do_submit(self):
        if self._busy:
            return
        selected = self._selected_pending()
        names = [n for n in self.session_papers if self.session_papers[n]["item"] in selected]
        if not names:
            QMessageBox.information(
                self, APP_TITLE,
                "请先“拉取题目并AI作答”(处理勾选的待测项), 再点击提交")
            return
        names = [n for n in names if self.session_papers[n]["item"]["status"] == "待测试"]
        if not names:
            return
        humanize = self.ck_humanize.isChecked()
        self._submit_queue = list(names)
        self._submit_ok.clear()
        self._submit_err.clear()
        self._set_busy(True, "提交中")
        self.log(f"开始提交 {len(names)} 个量表: {', '.join(names)}")
        self._submit_next(humanize)

    def _submit_next(self, humanize=True):
        if not self._submit_queue:
            self._set_busy(False)
            concl = ", ".join(self._submit_ok)
            self.log(f"提交批次结束: 成功{len(self._submit_ok)}个 "
                     f"{('✔ ' + concl) if concl else ''}"
                     + (f"; 失败: {self._submit_err}" if self._submit_err else ""))
            self.do_detect()
            return
        name = self._submit_queue.pop(0)
        entry = self.session_papers[name]

        def task(log, entry=entry, humanize=humanize):
            paper = entry["paper"]
            decisions = decisions_to_map(entry["decisions"])
            r = self.client.submit_paper(paper, decisions, humanize=humanize)
            if r.get("Code") != 0:
                raise RuntimeError(f"{name}: {r.get('Message', r)}")
            return r

        w = Worker(task)
        w.log.connect(self.log)
        w.done.connect(lambda _r, n=name: self._after_one_submit(n, humanize))
        w.fail.connect(lambda e, n=name: self._submit_one_failed(n, e, humanize))
        w.start()
        self._worker = w

    def _after_one_submit(self, name, humanize=True):
        self._submit_ok.append(name)
        self.log(f"✔ 已提交: {name}")
        self._submit_next(humanize)

    def _submit_one_failed(self, name, err: str, humanize=True):
        self._submit_err.append(f"{name}({err})")
        self.log(f"✘ 提交失败: {name} - {err}")
        self._submit_next(humanize)

    # ------------------------------------------------ action dispatch
    def _on_action(self, btn: QPushButton):
        try:
            if btn is self.btn_detect:
                self.do_detect()
            elif btn is self.btn_freeze:
                self.do_freeze()
            elif btn is self.btn_import:
                self.do_import()
            elif btn is self.btn_export:
                self.do_export()
            elif btn is self.btn_submit:
                self.do_submit()
        except Exception as e:  # noqa: BLE001
            self.log(f"操作异常: {e}")


def QTime_now() -> str:
    from datetime import datetime
    return datetime.now().strftime("%H:%M:%S")


def main():
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
