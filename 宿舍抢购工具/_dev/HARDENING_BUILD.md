# 加固构建说明（HARDENING_BUILD）

本文档说明如何在本地用 **PyArmor 混淆 + PyInstaller** 重新打包加固版
`grab_dorm_multi_account.exe` / `grab_dorm_single_account.exe`。
此流程用于修复 REVERSE_ENGINEERING_REPORT.md 中发现的授权保护缺陷，并保留本次
验证码环节的提速改动。

## 环境要求

- Python 3.12
- `pyinstaller>=6`、`pyarmor>=9`（本目录构建于 Pyarmor 9.2.6 / PyInstaller 6.22）
- 运行依赖：`requests`、`ddddocr`、`onnxruntime`、`numpy`、`opencv-python`

## 加固要点

1. **激活 KEY 校验**（`activation.py`）：
   - 固定 KEY 以不可逆 SHA-256 哈希比对（不存明文）。
   - 绑定 KEY 派生种子通过 XOR+base64 编码内置（`_EMBED_MASTER`），**无需外部
     license.key** 即可校验（gui_key 签发的绑定 KEY 直接可用）；可选在 exe 同目录
     放置 `license.key`（或 `GRAB_DORM_LICENSE`）覆盖内置种子以更换密钥。
2. **PyArmor 混淆业务模块**（grab_dorm / gui / activation），增加静态逆向门槛。
3. **PyInstaller 常规打包**（PyInstaller v6 已移除 `--key`，字节码加密由 PyArmor 承担）。

## 提速要点（保留的改动）

- **验证码预取流水线**（`grab_dorm.py`）：开抢前在等待开放的期间预取并识别验证码到
  缓存，到点直接用缓存提交（省去开抢瞬间约 500ms 拉图耗时）；提交后异步预取下一张，
  重试轮直接用缓存。多账号为每账号独立会话并发竞速。
- **校时 3 次往返**（`sync_time(rounds=3)`）取中位数，省约 1s 一次性准备开销。

## 打包步骤

```powershell
# 1) 在 _dev 目录（包含明文 grab_dorm.py / gui.py / activation.py）
cd 宿舍抢购工具/_dev

# 2) 用 PyArmor 生成混淆产物（trial 版适用 obf-code 1；勿用 obf-code 2，会 license 超限）
#    --pack onefile 会自动收集同目录所需资源并混淆 grab_dorm / gui / activation
pyarmor gen --pack onefile -O dist_obf_onefile grab_dorm.py

# 3) PyArmor 会在 .pyarmor\pack\dist 生成混淆后的脚本与 pyarmor_runtime_000000，
#    并在 .pyarmor\pack 放置 hook-pyarmor_runtime_000000.py；
#    同时覆盖当前目录 grab_dorm.spec。此时需把 ddddocr/onnx 模型数据补齐进 spec：
#    在 Analysis 的 datas/binaries/hiddenimports 加入 collect_all('ddddocr') 与
#    collect_all('onnxruntime')，并让入口指向 .pyarmor/pack/dist/grab_dorm.py、
#    hookspath=['.pyarmor/pack']。

# 4) 用 spec 完整打包（会嵌入 onnx 模型，产物约 170MB）
python -m PyInstaller --noconfirm --distpath dist_glob --workpath build grab_dorm.spec

# 5) 产物在 dist_glob\grab_dorm.exe；按发布用途复制为
#    ..\grab_dorm_multi_account.exe 或 ..\grab_dorm_single_account.exe
#    copy dist_glob\grab_dorm.exe ..\grab_dorm_multi_account.exe
```

## 验证

- 错误 KEY：`grab_dorm.exe --enrollid 1 --idcard 2 --key WRONG` → 退出码 2，
  提示"激活KEY无效"。
- 正确固定 KEY：`grab_dorm.exe --key "<有效KEY>"` → 打印 `[ACTIVATION] 激活校验通过`。
- 正确 KEY 下 `ddddocr 已加载`（确认 onnx 模型已内嵌）。
- 提速：真实环境开抢首提交用预取缓存（日志 `[PREFETCH]`），首提交约 0.4s（无缓存基线约 0.94s）。

## 注意

- git 仓库中的 `grab_dorm.spec` 为**可复现的原版**（指向明文源码），因为 PyArmor 混淆
  产物（`.pyarmor/`）不入 git；要做加固构建需先按上面第 2 步跑 `pyarmor gen --pack`。
- PyArmor 为 trial 版：仅混淆代码（obf-code 1），无法对抗顶级逆向；根治需服务端授权。
- `activation.py`、`generate_key.py` 为授权敏感逻辑，已按项目约定不提交 git。
- 本仓库的 `.gitignore` 已排除 `.pyarmor/`、`dist_*/`、`build/`、`_obf/` 等构建产物。
