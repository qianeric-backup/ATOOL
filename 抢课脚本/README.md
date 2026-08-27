# 抢课助手（建桥学院抢课脚本）v0.1.0

> 上海建桥学院（`my.gench.edu.cn` / `eams.gench.edu.cn`）选课/抢课辅助工具。
> 桌面 exe（`抢课助手.exe`）为 **tkinter 原生 UI**：双击直接弹出主窗口，无需浏览器。

---

## 一、发布内容

| 文件 | 说明 |
|------|------|
| `抢课助手.exe` | 桌面版（PyInstaller 打包，双击运行弹出 tkinter 主窗口；**Release 资产，不入库**） |
| `app.py` | 桌面 exe 入口：tkinter 原生 UI + EAMS 登录（Cookie/账密）+ 抢课线程 + 配置导入导出 |
| `gench_login.py` | 门户登录脚本（逆向自门户登录页源码，支持图形/腾讯/滑块验证码模式） |
| `gench_session.py` | 门户会话探测脚本（浏览器 Cookie → 门户菜单 → 定位选课应用） |
| `README.md` | 本说明 |

> 注：本目录下其余文件（`逆向报告.md` 等逆向分析产物、含真实登录 Cookie 的测试脚本）仅本地留存，不入库。

---

## 二、使用说明

### 桌面版（推荐）

1. 下载 `抢课助手.exe`（GitHub Releases 资产）并双击运行；
2. 直接弹出 tkinter 主窗口：登录（Cookie/账密）、实时状态、选课轮次、
   课程分页列表、抢课控制（预热/高频/成功即停）、运行日志、保活常驻；
3. 登录方式二选一：
   - **Cookie 导入（推荐）**：浏览器登录 EAMS 后，按 F12 → Network 找到
     `eams.gench.edu.cn` 请求，复制整串 Cookie（须含
     `cs-course-select-student-token` 选课 token）粘贴导入；
   - **EAMS 账密登录**：输入学号/密码，后端自动取盐 → SHA1 提交
     （当前 EAMS 无需验证码；失败触发滑块时按提示用 Cookie 方式登录）；
4. 页面自动载入选课轮次与课程列表（分页），设定目标课程与抢课参数
   （预热秒数/间隔/最大次数/成功即停），到点自动抢课，实时日志。

### 登录原理（逆向确认）

- EAMS 密码登录：`GET /student/login-salt` 取盐 → `密码 = SHA1(salt + '-' + 密码)` → `POST /student/login`；
- 选课接口：`https://eams.gench.edu.cn/course-selection-api/api/v1/student/course-select`；
- 抢课 token：`cs-course-select-student-token` JWT（可从 Cookie 或选课页提取，脚本自动识别）；
- 服务器时间校准：`GET /course-selection-api/api/v1/student/course-select/getCurrentDateTime`，
  用于预热定时抢课（避免本地时钟偏差）。

---

## 三、安全说明

- 本工具仅用于**个人选课**，请遵守学校教务系统使用规则，勿用于刷课/抢课牟利或影响校园网正常运行；
- 脚本导出的配置含当前登录态 Cookie，请勿外传；
- 运行时只向 `eams.gench.edu.cn` 发起选课请求，不上传任何账号数据到第三方。

---

## 四、v0.1.0 变更记录

- **v0.1.0（tkinter 原生 UI 版）**：由本地 Web 页面改为 tkinter 原生主窗口，
  新增服务器时间校准/预热/高频抢课/成功即停/保活常驻；删除旧的 `web/` 页面与命令行版；
- v0.1.0（初始版）：桌面 exe + 本地 Web 页面，支持 EAMS 账密登录 / Cookie 导入、
  轮次与课程自动加载、定时抢课与实时日志。