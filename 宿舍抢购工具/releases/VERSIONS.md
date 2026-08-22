# 宿舍抢购工具 · 版本归档清单

本目录按版本归档历史 exe 成品。**每次更新流程（硬性约定）：**

1. 生成新版本 `vX.Y.Z`
2. **先复制现行文件做一份副本**（本目录下的 `releases/vX.Y.Z/`），再在副本上修改
3. 更新 `config.json` 中的版本号（若适用）与本份 `VERSIONS.md`
4. 打包 exe 放入对应版本目录，命名带版本号后缀（`xxx_vX.Y.Z.exe`）
5. 推送 GitHub（走 `python _git_push.py`，仓库 `qianeric-backup/ATOOL`）

---

## v1.2.6 — 立即启动 worker（修正 ahead_ms 提前提交问题）

> 归档日期：2026-08-22。源码在 `_dev/`（`grab_dorm.py __version__ = "1.2.6"`）。

**本次变更（在 v1.2.5 基础上修正时序）：**

1. **立即启动 worker**：移除 v1.2.5 的"开放前 1s 预启动 worker"逻辑，改为
   开放时间到达后立即启动——避免提前提交触发 `507 暂未开放` 并消耗一次性验证码；
2. **移除 worker 开放时间检查**（已在开放后启动，无需再查）；
3. **保留**：连接池优化（HTTPAdapter）、智能重试（按错误类型调间隔）、
   预取双识别投票（AI+ddddocr，默认 glm-4v-plus-0111）；
4. **config.json 支持 AI 配置**：`ai_key` / `ai_base` / `ai_model` 字段可被
   `main()` 读取（优先级 命令行 > config > 环境变量/默认）；
5. 版本号 1.2.5 → 1.2.6（gui.py docstring/标题、README 同步）。

**源码版本对应关系**：

- **v1.2.6** → `_dev/` 目录中的源码（`python grab_dorm.py --version` 输出 1.2.6）
- **v1.2.5** → 本目录 `v1.2.5/src/` 中的源码副本
- **v1.2.4** → 本目录 `v1.2.4/src/` 中的源码副本
- **v1.2.3** → 本目录 `v1.2.3/src/` 中的源码副本
- **v1.2.2** → 本目录 `v1.2.2/src/` 中的源码副本
- **v1.2.1** → 本目录 `v1.2.1/src/` 中的源码副本
- **v1.2.0** → 本目录 `v1.2.0/src/` 中的源码副本
- **v1.1.0** → 本目录 `v1.1.0/src/` 中的源码副本

---

## v1.2.5 — 连接池 + 智能重试 + 预启动 worker

> 归档日期：2026-08-22。源码在 `_dev/`（`grab_dorm_v1.2.5.py`）。

**本次变更（性能优化）：**

1. **预启动 worker**：开放前 1 秒启动 worker 线程（v1.2.6 已改为立即启动）；
2. **连接池优化**：使用 `HTTPAdapter` 连接池复用连接，减少建立时间；
3. **智能重试**：根据错误类型智能调整重试间隔；
4. **开放时间检查**：worker 启动时检查开放时间，未到则等待；
5. 版本号 1.2.4 → 1.2.5。

---

## v1.2.4 — 预取双识别投票 + 默认模型 glm-4v-plus-0111

> 归档日期：2026-08-24。源码在 `_dev/`（`grab_dorm.py __version__ = "1.2.4"`）。

**本次变更（真实环境实测驱动的模型/策略优化）：**

1. **默认 AI 模型切换为 `glm-4v-plus-0111`**（智谱）：真实环境 10 次实测码有效率
   **60%（全场最高）**、识别率 100%、延迟 0.4-0.9s；对比 glm-4v-flash（0%）、
   glm-4v-plus（40%）、qwen3-vl-flash（40%）、ddddocr（50%）；
2. **预取阶段双识别投票**（`prefetch_captcha`）：AI 与 ddddocr 识别同一张图——
   - 一致 → 缓存（高可信，实测一致时 4/4 全对）；
   - 不一致 → 用 ddddocr（ddddocr 0 错误提交）；
   - ddddocr 失败 → 用 AI 结果兜底；
   - 都失败 → 换图重试。
   双识别**仅用于预取**（开放前时间充足）；开放后重试保持 ddddocr 单识别快节奏。
3. 版本号 1.2.3 → 1.2.4。

**源码版本对应关系**：

- **v1.2.4** → `_dev/` 目录中的源码（`python grab_dorm.py --version` 输出 1.2.4）
- **v1.2.3** → 本目录 `v1.2.3/src/` 中的源码副本
- **v1.2.2** → 本目录 `v1.2.2/src/` 中的源码副本
- **v1.2.1** → 本目录 `v1.2.1/src/` 中的源码副本
- **v1.2.0** → 本目录 `v1.2.0/src/` 中的源码副本
- **v1.1.0** → 本目录 `v1.1.0/src/` 中的源码副本

---

## v1.2.3 — 预取开关 + AI 配置置灰

> 归档日期：2026-08-24。源码在 `_dev/`（`grab_dorm.py __version__ = "1.2.3"`）。

**本次变更（预取可控开关）：**

1. **新增"启用验证码预取"开关**（GUI 勾选框 + CLI `--no-prefetch`）：
   - 开启（默认）：方案 A 预取流水线（开放前预取验证码，开抢瞬间直接提交）；
   - 关闭：跳过预取，开抢后 worker 直接现场取码提交（等效 v1.1.0 行为）；
2. **关闭时 AI 配置置灰**：GUI 中关闭预取后，「AI Key / AI Base / AI 模型」三个
   输入框自动置灰不可用（`DormGrabber.enable_prefetch=False` 时 AI 也无意义）；
3. 版本号 1.2.2 → 1.2.3。

**源码版本对应关系**：

- **v1.2.3** → `_dev/` 目录中的源码（`python grab_dorm.py --version` 输出 1.2.3）
- **v1.2.2** → 本目录 `v1.2.2/src/` 中的源码副本
- **v1.2.1** → 本目录 `v1.2.1/src/` 中的源码副本
- **v1.2.0** → 本目录 `v1.2.0/src/` 中的源码副本
- **v1.1.0** → 本目录 `v1.1.0/src/` 中的源码副本

---

## v1.2.2 — AI 识别默认切换为智谱 GLM-4V-Flash

> 归档日期：2026-08-24。源码在 `_dev/`（`grab_dorm.py __version__ = "1.2.2"`）。

**本次变更（AI 识别默认配置 + GUI 完整配置项）：**

1. **默认 AI 模型切换为智谱 `glm-4v-flash`**（国内直连、便宜）：
   - `AiCaptchaOcr` 默认 `base_url = https://open.bigmodel.cn/api/paas/v4`、`model = glm-4v-flash`；
   - 仍可被环境变量 `GRAB_DORM_AI_BASE` / `GRAB_DORM_AI_MODEL` 或 CLI `--ai-base` / `--ai-model` 覆盖；
2. **GUI 增加「AI Base(可选)」输入框**：预填智谱地址，配合已有的「AI Key」「AI 模型」，
   GUI 内即可完整配置 AI 识别（只填 Key 也能用默认智谱配置）；
3. 版本号 1.2.1 → 1.2.2。

**源码版本对应关系**：

- **v1.2.2** → `_dev/` 目录中的源码（`python grab_dorm.py --version` 输出 1.2.2）
- **v1.2.1** → 本目录 `v1.2.1/src/` 中的源码副本
- **v1.2.0** → 本目录 `v1.2.0/src/` 中的源码副本
- **v1.1.0** → 本目录 `v1.1.0/src/` 中的源码副本

---

## v1.2.1 — GUI 多账号版接入 AI 预取识别

> 归档日期：2026-08-24。源码在 `_dev/`（`grab_dorm.py __version__ = "1.2.1"`）。

**本次变更（多账号并发 + AI 识别）：**

1. **GUI 多账号版支持 AI 预取识别**：界面新增「AI Key(可选)」与「AI 模型(可选)」
   输入框，填写 API Key 即启用 AI 预取（OpenAI 兼容），留空则降级 ddddocr；
2. **每个账号独立会话并发**：多账号每个 `DormGrabber` 独立会话/独立验证码槽位，
   各自预取互不覆盖（服务器按 `JSESSIONID` 隔离）；
3. 版本号 1.2.0 → 1.2.1（grab_dorm.py `__version__`、gui.py 标题/docstring）。

**源码版本对应关系**：

- **v1.2.1** → `_dev/` 目录中的源码（`python grab_dorm.py --version` 输出 1.2.1）
- **v1.2.0** → 本目录 `v1.2.0/src/` 中的源码副本
- **v1.1.0** → 本目录 `v1.1.0/src/` 中的源码副本

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
