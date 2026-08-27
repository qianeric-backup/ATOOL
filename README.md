# 脚本工具软件

各种脚本/工具的集合，按使用场景分目录管理。各工具通过 GitHub Releases 发布 exe，源码与说明文档入库。

## 目录结构

- `抢课脚本/` — 建桥学院抢课助手（选课/抢课工具）
  - **`抢课助手.exe`（Release 资产，不入库）** — 桌面版（tkinter 原生 UI），双击直接弹出主窗口，无需浏览器
  - `app.py` — exe 入口（tkinter 主窗口 + EAMS 登录 + 抢课线程 + 服务器时间校准/预热/高频/成功即停 + 配置导入导出）
  - `gench_login.py` — 门户登录脚本（支持图形/腾讯/滑块验证码模式）
  - `gench_session.py` — 门户会话探测脚本
  - `README.md` — 使用说明
  - > 说明：本目录含浏览器真实 Cookie 的测试脚本（`_test_portal_cookie.local.py`）与逆向分析产物（`accountpassword.js`、`signin2.js`、`逆向报告.md`）仅本地留存，不入库。

- `宿舍抢购工具/` — 宿舍抢购工具（自动抢宿舍）
  - 源码与打包脚本在 `_dev/`，exe 归档在 `releases/`（按版本分目录，`VERSIONS.md` 为版本清单）
  - `GUI版本使用说明.md`、`config.json` 等使用文档
  - > 说明：`REVERSE_ENGINEERING_REPORT.md`、`_dev/` 中授权/密钥相关源码（`generate_key.py`、`activation.py`、`authorize_key.py` 等）为敏感逻辑，仅本地留存，不入库。

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
| `grab_course_v0.1.0.exe` | 抢课助手（抢课脚本） | 建桥学院选课/抢课，tkinter 原生 UI，双击弹出主窗口 |
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