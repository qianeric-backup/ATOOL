# 抢课助手（建桥学院抢课脚本）v0.2.0

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

### 桌面版（推荐）

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