# 抢课助手（建桥学院抢课脚本）v0.3.0

> 上海建桥学院（`my.gench.edu.cn` / `eams.gench.edu.cn`）选课/抢课辅助工具。
> 桌面 exe（`抢课助手.exe`）为 **tkinter 原生 UI**：双击直接弹出主窗口，无需浏览器。

---

## 一、发布内容

| 文件 | 说明 |
|------|------|
| `抢课助手.exe` | 桌面版（PyInstaller 打包，双击运行弹出 tkinter 主窗口；**Release 资产，不入库**） |
| `app.py` | 桌面 exe 入口：tkinter 原生 UI + Cookie 登录 + 抢课线程 + 配置导入导出 + 多开实例 |
| `抢课助手.spec` | PyInstaller 打包配置（重打包 exe 用） |
| `gench_login.py` | 门户登录脚本（逆向自门户登录页源码，支持图形/腾讯/滑块验证码模式） |
| `gench_session.py` | 门户会话探测脚本（浏览器 Cookie → 门户菜单 → 定位选课应用） |
| `README.md` | 本说明 |

> 注：本目录下其余文件（`逆向报告.md` 等逆向分析产物、含真实登录 Cookie 的测试脚本）仅本地留存，不入库。

---

## 二、使用说明

### Linux 适配（v0.3.0 起）

**一键启动器 `抢课助手.sh`（推荐，自动自检依赖）**
```bash
./抢课助手.sh                                   # GUI 桌面版
./抢课助手.sh --cli --help                      # CLI 无头模式（参数透传）
./抢课助手.sh --cli --config 抢课配置-2611999.json --targets 1001,1002 --poll 10
./抢课助手.sh --cli --cookie "cs-course-select-student-token=..." --search 高数
```
脚本会自检 `python3 / requests / tkinter`：缺 requests 自动 pip 安装；
缺 tkinter 时 GUI 给出 `apt install python3-tk` 指引、`--cli` 直接放行。

**依赖安装**
```bash
sudo apt update && sudo apt install -y python3 python3-tk   # GUI 需要 python3-tk
pip3 install requests                                        # 网络请求
```

**方式一：GUI 桌面版（有显示环境）**
```bash
python3 app.py
```
中文字体自动回退（微软雅黑 → Noto Sans CJK SC → 文泉驿正黑 → DejaVu Sans）。

**方式二：CLI 无头版（服务器/VPS/无显示器，推荐）**
```bash
# 从浏览器复制整串 Cookie（须含 cs-course-select-student-token）
python3 app.py --cli --cookie "SESSION=...; cs-course-select-student-token=..."

# 或使用 GUI 导出的 JSON 配置
python3 app.py --cli --config 抢课配置-2611999.json --targets 1001,1002

# 轮次未开放时保持轮询等待（每 10s 一次，开抢自动触发）
python3 app.py --cli --cookie "..." --poll 10 --interval-ms 150 --prestart 5 --targets 1001,1002

# 先预览课程（不开抢）
python3 app.py --cli --cookie "..." --search 高数 --turn-id 1
```
说明：CLI 自动从 `/multiple-students` 解析内部学生 ID，无需手动填；Ctrl+C 停止；
可配合 systemd timer / crontab 常驻：
```text
* * * * * cd /path/to/抢课脚本 && python3 app.py --cli --config 抢课配置.json \
         --poll 15 --targets 1001,1002 >> 抢课.log 2>&1
```

**Linux 打包（PyInstaller 生成同名二进制 `抢课助手`）**
```bash
pip3 install pyinstaller
pyinstaller 抢课助手.spec
# dist/抢课助手   —— Linux 版自动 console=True，CLI 日志可见
```

### 桌面版（Windows exe，推荐）

1. 下载 `抢课助手.exe`（GitHub Releases 资产）并双击运行；
2. 直接弹出 tkinter 主窗口：登录（Cookie）、实时状态、选课轮次、
   课程分页列表、抢课控制（预热/毫秒间隔/无限次/成功即停）、运行日志、保活常驻；
3. **登录（Cookie）**：浏览器登录 EAMS 后，按 F12 → Network 找到
   `eams.gench.edu.cn` 请求，复制整串 Cookie（须含
   `cs-course-select-student-token` 选课 token）粘贴导入；
4. 页面自动载入选课轮次与课程列表（分页），自动取轮次开抢时间，
   设定抢课参数（**预热秒数/间隔毫秒/最多抢 N 次（0=无限）/成功即停**），到点自动抢课，实时日志；
5. **多开**：点「新开窗口」可启动第二个实例（独立进程、独立登录/抢课）；
6. **配置导入/导出**：可导出/导入配置文件（含 Cookie、预热、间隔、次数）。

### 登录原理（逆向确认）

- 选课接口：`https://eams.gench.edu.cn/course-selection-api/api/v1/student/course-select`；
- 抢课 token：`cs-course-select-student-token` JWT（从 Cookie 提取，脚本自动识别）；
- 服务器时间校准：`GET /course-selection-api/api/v1/student/course-select/getCurrentDateTime`，
  用于预热定时抢课（避免本地时钟偏差）。

---

## 三、安全说明

- 本工具仅用于**个人选课**，请遵守学校教务系统使用规则，勿用于刷课/抢课牟利或影响校园网正常运行；
- 脚本导出的配置含当前登录态 Cookie，请勿外传；
- 运行时只向 `eams.gench.edu.cn` 发起选课请求，不上传任何账号数据到第三方。

---

## 四、变更记录

- **v0.3.1（Linux 适配，2026-09-01）**：
  - 新增 **CLI 无头模式**（`--cli`）：Cookie/配置载入 → 自动解析内部学生ID → 轮次轮询等待（`--poll`）→ 开抢（预热/间隔/次数可控），无需 tkinter/显示器，可 cron/systemd 常驻；
  - tkinter 缺失时优雅降级：提示 `apt install python3-tk` 并引导 CLI；
  - 中文字体自动回退（微软雅黑 → Noto CJK → 文泉驿 → DejaVu），Linux GUI 不再方块字；
    **实测补充**：现代 Linux 桌面 fontconfig 已把 Tk 默认字体解析为 Noto Sans CJK SC，
    无需额外配置；脚本仍保留字体枚举 + fc-match 探测兜底（旧/精简桌面环境用）；
  - 多开参数 `creationflags` 仅 Windows 生效（Linux 不再报错）；
  - 开抢时间解析提取为模块级 `turn_start_target_ts()`（GUI/CLI 共用）；
  - `抢课助手.spec` 平台自适应：Linux 打包 `console=True`（CLI 日志可见），Windows 保持 `console=False`（无黑窗）。
- **v0.3.0（逆向校准优化，2026-09-01）**：
  - **修复选课结果轮询失联**：add-request 响应 `data` 即 requestId（纯值），原按 `data.id` 解析会取空导致永远等不到结果；
  - 结果轮询 10×2s，`resend`（服务端要求重发）自动重提，最多自动重发 2 次；
  - 适配服务端频控 `RequestLimitException`：触发后指数退避 3→30s，正常请求间隔 ±25% 随机抖动（避开全校整齐节拍）；
  - 新增 `/std-count` 容量预检：满员低频等待、连续满员自动停止，避免空转狂打；`--limit` 余量实时显示已保留；
  - 令牌过期或 401 立即止损，日志提示重新复制 Cookie；
  - 登录协议改为 course-selection-api 真实链路（`login-salt`+`login`，`SHA1(salt-明文)`，`needCaptcha` 流程返回 captchaToken）；
  - 课程列表搜索框接线（关键词同时命中课程名与授课代码）；
  - 开抢前自动复校服务器时钟（校准超 2 分钟时）。
- **v0.2.1（小增强）**：导出配置文件名自动带当前学号（如 `抢课配置-2023xxxx.json`），
  便于多账号区分；学号未解析时回退默认名 `抢课配置.json`；
- **v0.2.0（功能增强）**：
  - 登录改为**纯 Cookie 登录**（移除账密输入，避免滑块验证码）；
  - 新增**多开**（「新开窗口」按钮，独立进程/独立登录/独立抢课）；
  - 新增**配置导入/导出**（JSON，含 Cookie/预热/间隔/次数）；
  - 抢课间隔改为**毫秒**、**最多次数支持 0 = 无限**、自动取轮次开抢时间；
  - 新增 `抢课助手.spec`（打包配置入库）；
- **v0.1.0（tkinter 原生 UI 版）**：由本地 Web 页面改为 tkinter 原生主窗口，
  新增服务器时间校准/预热/高频抢课/成功即停/保活常驻；删除旧的 `web/` 页面与命令行版；
- v0.1.0（初始版）：桌面 exe + 本地 Web 页面，支持 EAMS 账密登录 / Cookie 导入、
  轮次与课程自动加载、定时抢课与实时日志。