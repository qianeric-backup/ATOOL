# 宿舍抢购工具 · 版本归档清单

本目录按版本归档历史 exe 成品。**每次更新流程（硬性约定）：**

1. 生成新版本 `vX.Y.Z`
2. **先复制现行文件做一份副本**（本目录下的 `releases/vX.Y.Z/`），再在副本上修改
3. 更新 `config.json` 中的版本号（若适用）与本份 `VERSIONS.md`
4. 打包 exe 放入对应版本目录，命名带版本号后缀（`xxx_vX.Y.Z.exe`）
5. 推送 GitHub（走 `python _git_push.py`，仓库 `qianeric-backup/ATOOL`）

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
