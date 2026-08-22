# 宿舍抢购工具 · 版本归档清单

本目录按版本归档历史 exe 成品。**每次更新流程（硬性约定）：**

1. 生成新版本 `vX.Y.Z`
2. **先复制现行文件做一份副本**（本目录下的 `releases/vX.Y.Z/`），再在副本上修改
3. 更新 `config.json` 中的版本号（若适用）与本份 `VERSIONS.md`
4. 打包 exe 放入对应版本目录，命名带版本号后缀（`xxx_vX.Y.Z.exe`）
5. 推送 GitHub（走 `python _git_push.py`，仓库 `qianeric-backup/ATOOL`）

---

## v1.2.0 — 方案A：预取 + AI 识别 + 服务器时间触发

> 归档日期：2026-08-24。源码在 `_dev/`（`grab_dorm.py __version__ = "1.2.0"`），
> exe 待打包后放入 `v1.2.0/`。

**本次变更（方案A 提速：开放前预取验证码 + 开抢瞬间直接提交）：**

1. **预取流水线**：开放前 ~12s 窗口内预取验证码（deadline = 开放点 − 2s），
   成功后缓存，开抢瞬间直接提交（0ms 取码，首提交 ≈ 0.43s，省约 0.6s）；
2. **AI 识别（可选）**：新增 `AiCaptchaOcr`（OpenAI 兼容 Chat Completions 接口），
   预取阶段优先用 AI（准确率 85~95% vs ddddocr 69%），失败自动降级 ddddocr；
   配置：`--ai-key/--ai-base/--ai-model` 或环境变量 `GRAB_DORM_AI_KEY/BASE/MODEL`，
   `--no-ai` 可禁用；
3. **服务器时间触发**：提交按服务器时间卡点（`_sleep_until(start_ts)`），不再用
   `ahead_ms` 提前试探——提前提交会触发 `507 暂未开放` 并消耗一次性验证码
   （见 REVERSE_ENGINEERING_REPORT.md §5.3 实测结论）；
4. **缓存码一次性**：worker 首轮优先用缓存码，无论成败用后即置空，防重放。

| 归档文件名（待打包） | 工具说明 | 构建变体 |
|---|---|---|
| `grab_dorm_multi_v1.2.0_*.exe` | 多账号 · 方案A | fixed/protected/sp |
| `grab_dorm_single_v1.2.0_*.exe` | 单账号 · 方案A | fixed/protected/sp |

**源码版本对应关系**：

- **v1.2.0** → `_dev/` 目录中的源码即为 v1.2.0（`grab_dorm.py __version__ = "1.2.0"`，
  `python grab_dorm.py --version` 可查）
- **v1.1.0** → 本目录 `v1.1.0/src/` 中的源码副本（grab_dorm.py / gui.py / mock_server.py）

---

## v1.1.0 —（归档基线 · 新起点）

> 归档日期：2026-08-22。本版本为目录整理时的归档基线版本号，对应
> `宿舍抢购工具/` 根目录原有 6 个 exe（fixed / protected / sp 三个构建变体）。

| 归档文件名 | 工具说明 | 构建变体 |
|---|---|---|
| `grab_dorm_multi_fixed_v1.1.0.exe` | 多账号 · 修复版 | fixed |
| `grab_dorm_multi_protected_v1.1.0.exe` | 多账号 · 加固保护版 | protected |
| `grab_dorm_multi_sp_v1.1.0.exe` | 多账号 · pyarmor 混淆版 | sp |
| `grab_dorm_single_fixed_v1.1.0.exe` | 单账号 · 修复版 | fixed |
| `grab_dorm_single_account_protected_v1.1.0.exe` | 单账号 · 加固保护版 | protected |
| `grab_dorm_single_sp_v1.1.0.exe` | 单账号 · pyarmor 混淆版 | sp |

**说明：**

- **fixed** —— 普通 PyInstaller 单文件版
- **protected** —— 加固/保护版（需授权 KEY 激活）
- **sp** —— pyarmor 混淆版（源码混淆后打包）
- `grab_dorm_multi_sp` 与 `grab_dorm_single_sp` 文件大小相同（`170153081` 字节）为当时的构建现象。

> 源码位于上一级 `_dev/`；后续版本对应源码变更在 `_dev/` 中维护。

## 源码版本对应关系

- **v1.1.0** → `_dev/` 目录中的源码即为 v1.1.0 基线：
  - `grab_dorm.py`：`__version__ = "1.1.0"`（`python grab_dorm.py --version` 可查）
