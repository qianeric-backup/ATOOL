# 脚本工具软件

各种脚本工具的集合。

## 目录结构

- `VPS部署/` — VPS 部署相关脚本
  - `deploy_3xui.py` — 3x-ui 部署脚本
  - `deploy_newapi.sh` — new-api 部署脚本
- `宿舍抢购工具/` — 宿舍抢购工具
  - `config.json` — 配置文件
  - `性能报告.md` — 性能报告文档
  - `_dev/` — 源码与未打包的脚本（`*.exe` 成品通过 GitHub Releases 发布）
  - （可执行文件 `*.exe` 通过 GitHub Releases 发布，见下表）

## Releases

可执行文件通过 GitHub Releases 发布，请到 Releases 页面下载。Release 资产为英文文件名，对应的工具中文名如下：

| 下载文件名 | 工具中文名 | 说明 |
|---|---|---|
| `grab_dorm_single_account.exe` | 抢宿舍工具（单账号） | 单账号自动抢宿舍 |
| `grab_dorm_multi_account.exe` | 抢宿舍工具（多账号） | 多账号自动抢宿舍 |
| `gui_key.exe` | 授权KEY签发工具 | 生成 / 签发授权 KEY |
| `fp_tool.exe` | 读取机器指纹工具 | 读取本机机器指纹 |

