# 抢课助手（建桥学院抢课脚本）v0.1.0

> 上海建桥学院（`my.gench.edu.cn` / `eams.gench.edu.cn`）选课/抢课辅助工具。
> 桌面 exe（`抢课助手.exe`）+ 本地 Web 页面：所有人工操作变成输入框，选课数据自动载入，到点自动抢课。

---

## 一、发布内容

| 文件 | 说明 |
|------|------|
| `抢课助手.exe` | 桌面版（PyInstaller 打包，双击运行，自动打开本地 Web 页面） |
| `app.py` | exe 入口后端：本地 Web 服务 + EAMS 登录 + 抢课线程（标准库 http.server，无 Web 框架依赖） |
| `抢课脚本.py` | 命令行版：EAMS 账密登录向导 / 登录态校验 / 选课接口定位 / 抢课 |
| `gench_login.py` | 门户登录脚本（逆向自门户登录页源码，支持图形/腾讯/滑块验证码模式） |
| `gench_session.py` | 门户会话探测脚本（浏览器 Cookie → 门户菜单 → 定位选课应用） |
| `web/index.html` | 本地 Web 页面（单文件 UI） |
| `抢课助手.spec` | PyInstaller 打包配置 |
| `README.md` | 本说明 |

> 注：本目录下其余文件（`accountpassword.js`、`signin2.js`、`逆向报告.md` 等）为逆向分析产物，本地留存不入库；含真实登录 Cookie 的测试脚本亦不入库。

---

## 二、使用说明

### 桌面版（推荐）

1. 下载 `抢课助手.exe`（GitHub Releases 资产）并双击运行；
2. 自动启动本地 Web 服务并打开浏览器页面（动态分配端口，支持多开）；
3. 登录方式二选一：
   - **EAMS 账密登录**：输入学号/密码，后端自动取盐 → SHA1 提交（无需验证码，失败触发滑块时按提示处理）；
   - **Cookie 导入**：浏览器登录 EAMS 后复制整串 Cookie 粘贴导入；
4. 页面自动载入选课轮次与课程列表；
5. 设定目标课程与抢课参数（间隔/次数），到点自动抢课，实时日志。

### 命令行版

```bash
python 抢课脚本.py --eams-login            # EAMS 账密登录向导（人工输密码）
python 抢课脚本.py --eams-login --check    # 登录后只探测，不抢课
python 抢课脚本.py --eams-login --save     # 登录成功后保存 EAMS 会话 Cookie
python 抢课脚本.py --eams-check            # 用已保存的 EAMS 会话探测
```

### 登录原理（逆向确认）

- EAMS 密码登录：`GET /student/login-salt` 取盐 → `密码 = SHA1(salt + '-' + 密码)` → `POST /student/login`；
- 选课接口：`https://eams.gench.edu.cn/course-selection-api/api/v1/student/course-select`；
- 抢课 token：访问选课页自动换取 `cs-course-select-student-token` JWT；
- 门户登录支持验证码模式：1=直接登录、2=图形验证码、3=腾讯验证码、4=滑块验证码。

---

## 三、安全说明

- 本工具仅用于**个人选课**，请遵守学校教务系统使用规则，勿用于刷课/抢课牟利或影响校园网正常运行；
- 脚本导出的配置含当前登录态 Cookie，请勿外传；
- 运行时只与本机 `127.0.0.1` 通信，不上传任何账号数据。

---

## 四、v0.1.0 变更记录

- 首个正式发布版本：桌面 exe（本地 Web UI）+ 命令行版，支持 EAMS 账密登录 / Cookie 导入、轮次与课程自动加载、定时抢课与实时日志。