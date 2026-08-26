# new-api 轻量化套皮 一键部署包

> 本包为 **new-api（Codex 中转站）套皮 + 轻量化改造** 的完整可部署成果。
> 改造内容：**全局去动画、去除透明蒙版/毛玻璃、锁定纯净中性配色**（Lite Skin 覆盖层）。

---

## 一、内容结构

```
newapi-lite-deploy/
├── new-api-lite-src.tar.gz      # 服务器拉回的完整源码包（含 web/dist、Lite Skin、deploy_lite.sh）
├── new-api-src/                 # 已解压的源码目录（可一键部署/重建）
│   ├── Dockerfile.lite          # 轻量化构建文件（仅 Go 编译，不跑 bun/rsbuild）
│   ├── deploy_lite.sh           # 一键部署脚本（自动装 docker + 构建 + 替换/回滚）
│   ├── web/dist/                # 已构建前端产物（含 lite-skin.css、index.html）
│   └── ...（Go 源码全套）
├── deploy_lite.sh               # 与包内同名脚本的副本（便于直接拷到服务器）
└── README.md                    # 本说明
```

---

## 二、一键部署（在服务器执行）

把 `new-api-src/` 目录（或整个包，或仅 `deploy_lite.sh`）传到服务器任意位置
（如 `/data/new-api-src`），然后：

```bash
cd /data/new-api-src
chmod +x ./deploy_lite.sh
./deploy_lite.sh
```

脚本会自动：
1. **自动安装 Docker**（若服务器未装 docker，用 get.docker.com 官方脚本安装，
   仅支持 Ubuntu/Debian 系；已装则跳过）
2. 前置检查（docker、dist/lite-skin.css、index.html 引用）
3. 幂等构建镜像 `new-api-lite:latest`（镜像已存在则跳过；`--rebuild` 强制重建）
4. 替换容器 `new-api`（**数据卷 `/data/new-api` 保留**，配置/渠道/令牌/倍率不丢）
5. 健康检查（HTTP 200 + lite-skin.css 200 验证皮肤生效）

常用参数：

| 参数 | 说明 |
|------|------|
| `--port N` | 对外端口（默认 3000） |
| `--data DIR` | 数据卷目录（默认 /data/new-api） |
| `--rebuild` | 强制重新构建镜像 |
| `--restore` | 回滚到旧镜像 `calciumion/new-api:latest` |

---

## 三、回滚

```bash
./deploy_lite.sh --restore
```
- 旧镜像 `calciumion/new-api:latest` 仍在服务器，回滚不丢数据。
- 数据卷始终保留，回滚只是换镜像。

---

## 四、改造清单（Lite Skin 覆盖层）

覆盖层写在 `web/src/styles/lite-skin.css`，经 `web/dist/index.html` 的
`<link rel="stylesheet" href="/lite-skin.css">` 引入（不参与 Tailwind 打包，
独立文件,可随时移除还原）。

| 项 | 效果 |
|----|------|
| 动画 | 全部禁用（animation/transition: none），弹窗/抽屉/滚动/hover 动效全关 |
| 蒙版 | backdrop-blur 全移除；半透明面板改实底；弹窗遮罩改不透明中性深色 |
| 配色 | 锁定中性纯色（黑白灰），浅/深色跟随系统，不受彩色主题预设影响 |

---

## 五、数据与安全

- 数据卷 `/data/new-api`（数据库 `one-api.db`）——替换容器不动它。
- 服务器内存仅 1G：**构建只在服务器跑 Go 编译**，前端 dist 由本机构建后随包携带，避免 OOM、不额外占磁盘/swap。
- 服务器保留源码目录 `/data/new-api-src`，重建仅需 `docker build -f Dockerfile.lite -t new-api-lite .`

---

## 六、验证记录（部署当日）

- 镜像 `new-api-lite:latest` 295MB，容器 `new-api` 运行中（Up 已确认）。
- `/lite-skin.css` HTTP 200（4482 字节，含 Lite Skin 标记）。
- 渠道 SiliconFlow + DeepSeek 均在；分组倍率 default=2（价格 2 倍）保留。
- 管理端 http://<SERVER_IP>:3000 登录正常。