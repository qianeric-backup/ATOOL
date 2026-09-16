# 脚本工具软件

各种脚本/工具的集合，按使用场景分目录管理。各工具通过 GitHub Releases 发布 exe，源码与说明文档入库。

## 目录结构

- `教务抢课脚本/` — 建桥学院抢课助手（教务处选课系统，原 `抢课脚本/`）
  - **`抢课助手.exe`（Release 资产，不入库）** — 桌面版（tkinter 原生 UI），双击直接弹出主窗口，无需浏览器
  - `app.py` — exe 入口（tkinter 主窗口 + EAMS 登录 + 抢课线程 + 服务器时间校准/预热/高频/成功即停 + 配置导入导出）
  - `probe_batch.py` — 选课 API 只读探测（token 从环境变量 `GENCH_CS_TOKEN` 注入）
  - `gench_login.py` — 门户登录脚本（支持图形/腾讯/滑块验证码模式）
  - `gench_session.py` — 门户会话探测脚本
  - `README.md` — 使用说明（含 API 探测结论表）
  - `build-linux.sh` / `build-windows.bat` / `CI-workflow-build_course_grab.yml` — 双平台打包脚本与 CI 交付副本
  - > 说明：本目录含浏览器真实 Cookie 的测试脚本（`_test_portal_cookie.local.py`）与逆向分析产物（`.probe/` 前端快照、`cs_menu_dump.html` 等）仅本地留存，不入库。

- `公选课抢课脚本/` — Gench 公选课选课助手（PublicElectivePlatform，原 `allxuanke/`）
  - `gench_enroll.py` / `gench_enroll_gui.py` — 公选课选课 CLI / GUI（tkinter）
  - `probe_batch.py` — 批次/资格探测（Cookie 走 `--cookie=` / 环境变量 `GENCH_COOKIE` / 本地 `cookies.txt`）
  - `公选课全部课程_*.xlsx`、`课程名一览.png` — 课程数据快照
  - `recon/` — 前端 JS 逆向参考快照（公开静态资源）
  - `build_windows.bat`、`run.sh` — 构建/运行脚本
  - > 说明：`cookies.txt`、`cookies_portal.txt`、`gench_config.json`（真实登录态）与构建产物（`Gench选课助手.exe/-linux`）仅本地留存，不入库。

- `心理测试自动脚本/` — 心理测评自动答题工具（16PF / UPI 等量表）
  - `main.py` / `headless_run.py` — GUI / 命令行入口（自动登录、探测待测项、拉题、AI 最健康作答、拟真提交）
  - `core/` — 登录客户端（RSA 复现 jsencrypt）、作答求解器、本地存储
  - `config/template.json` — 作答模板（按题面固化，可导入导出复用）
  - `mock/` + `mock_data/` — 本地 mock 服务器与数据快照（`run_mock.sh` 一键联调）
  - `requirements.txt`、`run_gui.sh` — 依赖清单与一键启动（`pylibs/` 运行时自动装到本地，不入库）
  - > 说明：`probe/`（前端快照与真实 Cookie）、`pylibs/`（~1.1GB vendored 依赖）仅本地留存，不入库。

- `宿舍抢购工具/` — 宿舍抢购工具（自动抢宿舍）
  - 源码与打包脚本在 `_dev/`（`grab_dorm.py`、`gui.py`、`gui_key.py`、`fp_tool.py`、`mock_server.py` 等），exe 归档在 `releases/`（按版本分目录，`VERSIONS.md` 为版本清单）
  - `GUI版本使用说明.md`、`多开使用说明.md`、`多开exe使用说明.md`、`性能报告.md`、`config.json` 等使用文档
  - > 说明：`REVERSE_ENGINEERING_REPORT.md`、`_dev/` 中授权/密钥相关源码（`generate_key.py`、`activation.py`、`authorize_key.py` 等）为敏感逻辑，仅本地留存，不入库；历史测试产物（`test_*.py`、验证码截图、测试/对比/分析报告）已精简出库，仅本地临时复测时出现。

- `CPP漫展抢购/` — CPP 漫展购票工具（cppTickerBuy）
  - `使用说明.md` — 使用说明
  - `同类软件推荐.md` — 同类软件对比推荐
  - > 说明：`repo/`（第三方仓库）、`config.json`、`cookies.json`、`app.log`、`tmp/` 为运行时文件（含真实登录态），仅本地留存，不入库；exe `cppTicKerBuy.exe` 以 Release 资产发布。

- `VPS部署/` — VPS 部署相关脚本
  - `deploy_3xui.py` — 3X-UI + VLESS+Reality 一键部署（多客户端 Clash 订阅）
  - `deploy_newapi.sh` — new-api（Codex/OpenAI 中转站）Docker 一键部署
  - `Dockerfile.lite` — new-api 轻量化多阶段构建（仅 Go 编译，不跑 bun/rsbuild）
  - `newapi-lite-deploy/` — lite 版一键部署/重建/回滚脚本（`deploy_lite.sh`）与 `README.md`
  - > 说明：`VPS台账.md`（服务器凭据/IP/密钥）、`reasonix.toml`、`new-api-src/` 完整源码树与 `new-api-lite-src.tar.gz` 仅本地留存，不入库。

## Releases

可执行文件通过 GitHub Releases 发布。Release 资产为英文文件名，对应工具中文名如下：

| 下载文件名 | 工具中文名 | 说明 |
|---|---|---|
| `grab_course_v0.1.0.exe` | 抢课助手（教务抢课脚本） | 建桥学院选课/抢课，tkinter 原生 UI，双击弹出主窗口 |
| `grab_dorm_single_account_v1.2.6.exe` | 抢宿舍工具（单账号） | 单账号自动抢宿舍，已按 v1.2.6 归档 |
| `grab_dorm_multi_account_v1.2.6.exe` | 抢宿舍工具（多账号） | 多账号自动抢宿舍，已按 v1.2.6 归档 |
| `gui_key.exe` | 授权KEY签发工具 | 生成 / 签发授权 KEY |
| `fp_tool.exe` | 读取机器指纹工具 | 读取本机机器指纹 |
| `cppTicKerBuy.exe` | CPP 漫展购票工具 | CPP 漫展自动购票 |

> 宿舍抢购工具版本归档 exe 的完整清单（含 fixed / protected / sp 变体）见 `宿舍抢购工具/releases/VERSIONS.md`。

## 更新约定

仓库内各工具按以下常规流程更新：

1. 升版本号（源码 `__version__` / 文档同步）；
2. 归档 exe 到对应 `releases/vX.Y.Z/`（宿舍工具按 `VERSIONS.md` 约定）；
3. 发布 GitHub Release（exe 用 ASCII 文件名，中文工具名以 README 表映射）；
4. 推送源码到仓库（`origin/main`）。

## 敏感信息约定

- **以下内容一律不入库**（本地留存）：含真实凭据的文件（Cookie、配置、台账、密钥）、逆向分析产物、第三方仓库镜像、大体积源码包/tar.gz；
- 代码内不得硬编码真实服务器 IP、账号密码、API Key；示例统一用占位符（如 `<SERVER_IP>`）；
- 提交前检查 `git status` 确认未误加敏感文件，必要时补充 `.gitignore` 规则。