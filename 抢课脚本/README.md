# 抢课助手（建桥学院抢课脚本）v0.3.3

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

**打包（Linux / Windows 双平台）**

```bash
# Linux（本机，推荐一键脚本）
./build-linux.sh
# 等价于: pip3 install pyinstaller && pyinstaller 抢课助手.spec
# 产物: dist/抢课助手 —— GUI/CLI 双模式（console=True，CLI 日志可见）
# 注意: 产物与构建机 glibc 版本绑定，老系统报错时用 启动器抢课助手.sh 跑源码
```

```text
# Windows（三种方式任选）
1) 双击 build-windows.bat        —— 本机一键打包 → dist\抢课助手.exe（无黑窗）
2) GitHub Actions CI             —— push 到 main（改动 抢课脚本/**）自动双平台构建，
                                    Actions 页面取 artifact；推 v* tag 自动发 Release
3) Windows 手动                  —— 装 Python 3.12（勾选 tcl/tk）后:
                                    pip install pyinstaller requests
                                    pyinstaller 抢课助手.spec
```

> PyInstaller 不支持交叉编译：exe 须在 Windows 上构建（本地 bat 或 CI），
> Linux 二进制须在 Linux 上构建；`抢课助手.spec` 平台自适应（Windows console=False /
> Linux console=True）。CI workflow 交付副本见 `CI-workflow-build_course_grab.yml`，
> 生效需复制到仓库根 `.github/workflows/build_course_grab.yml`。

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

### API 探测结论（v0.3.3，2026-09-12 实测）

| 端点 | 方法 | 鉴权 | 实测结论 |
|------|------|------|----------|
| `/getCurrentDateTime` | GET | Authorization 头 | 正常，返回服务器北京时间字符串 |
| `/multiple-students` | GET | Authorization 头 | 返回内部学生 ID（`data[0].id`）与学院/专业信息 |
| `/students` | GET | Authorization 头 | 学生 token 返回 `data:[]`（代理/多学生账号场景专用） |
| `/open-turns/{内部ID}` | GET | Authorization 头 | 正常；**用学号访问 → 500**（见下） |
| `/query-lesson/{sid}/{turnId}` | POST | Authorization 头 | 载荷 turnId/studentId/semesterId/pageNo/pageSize/canSelect |
| `/std-count?lessonIds=a,b` | GET | Authorization 复数 CSV | 空结果返回 `data:{}`（字典按 lessonId 键） |
| `/add-request` | POST only | Authorization 头 | GET → 500 `HttpRequestMethodNotSupportedException` |
| `/add-drop-response/{sid}/{reqId}` | GET | Authorization 头 | 处理中返回 `data:null` |

关键发现：

1. **JWT 必须放 `Authorization` 请求头**：仅凭 `cs-course-select-student-token`
   Cookie 访问一律 401；`Authorization: <JWT>`（无需 Bearer 前缀）即通过。
   脚本 `api_headers()` 现有做法正确。
2. **越权防护有效（正面结论）**：`/open-turns/2611999`（用学号替代内部 ID）→
   HTTP 500 + `UnauthorizedDataAccessException: 选课学生和登录用户不符`，
   服务端校验路径参数与 JWT 身份绑定，**水平越权（IDOR）被拦截**。
3. **信息泄露（低危 finding）**：异常路径返回完整 Java 堆栈与框架指纹
   （Spring Boot / Shiro / `com.supwisdom.eams.*` 类名、行号），
   错误 JSON 的 `timestamp` 为 UTC 而 `getCurrentDateTime` 为北京时间（+8h），
   建议（校方）：全局异常处理器脱敏 + 时区统一。
4. 非 选课时段所有业务端点均安全降级（空轮次/空页/`data:null`），无未授权可读写面。

---

## 三、安全说明

- 本工具仅用于**个人选课**，请遵守学校教务系统使用规则，勿用于刷课/抢课牟利或影响校园网正常运行；
- 脚本导出的配置含当前登录态 Cookie，请勿外传；
- 运行时只向 `eams.gench.edu.cn` 发起选课请求，不上传任何账号数据到第三方。

---

## 四、变更记录

- **v0.3.3（live API 探测 + 时延优化，2026-09-12）**：
  - **连接池复用（本次最大提速）**：`cs_get/cs_post` 由模块级 `requests.get/post`
    （每发请求完整重走 TCP+TLS 握手）改为共享 `Session` + `HTTPAdapter(pool_maxsize=32)`；
    实测同一会话 `getCurrentDateTime` 连发 **91ms（首轮握手）→ 18ms（复用），约 5 倍**；
  - **开抢精度**：新增 `smart_wait_until()`（GUI/CLI 共用）—— 预热远段 0.5s 步长 sleep、
    末段 1s busy-spin，到点偏差实测 0ms（旧版 sleep 粒度 Linux ~1ms / Windows ~15ms）；
  - **结果轮询自适应**：`add-drop-response` 间隔 0.4/0.8/1.5/2s…
    （多数结果 <1s 就绪；旧版固定先睡 2s，成功路径平均白等 1.5s+）；
  - **容量预检节流**：纯时间节流 ≥5s 一次 + 开抢前 5s 宽限期不打
    （旧版高频模式每 5 次 add-request 就夹一发 std-count，吞吐近乎砍半）；
  - **CLI 满员检测修复**：直接 `--targets` 时先 `load_courses(page_size=500)` 建
    limitCount 缓存 —— 旧版 `check_capacity` 查不到 limit，「满员自动停止」形同虚设；
  - `add-request` 超时收紧为 `(3,6)s`（高峰期卡死请求不再阻塞 15s，配合 resend 逻辑）；
  - 403 与 401 同步止损（Shiro 会话失效两种返回都可能出现）；
  - 节拍抖动改 `random.uniform`（旧版 `(i*常数)%100` 为确定性序列，重跑节拍相同）；
  - CLI 长等待中复校服务器时钟（每 120s）；token 剩余时间显示防御空值。
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