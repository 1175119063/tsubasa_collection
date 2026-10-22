# 翼·时光记 macOS Docker 部署

此部署方式适用于安装了 Docker Desktop 的 macOS。它不需要在 Mac 上安装 Python、Conda 或 SQLite。

## 启动

在本目录执行：

```bash
docker compose up -d --build
```

然后访问 <http://127.0.0.1:8000>。停止服务：

```bash
docker compose down
```

数据库、照片、缩略图和录音都保存在本目录的 `data/` 中，请定期使用应用内备份功能。首次启动或升级
前不要删除这个目录。若 8000 端口被占用，可以将 `docker-compose.yml` 中的端口改为
`127.0.0.1:8001:8000`，再访问 <http://127.0.0.1:8001>。

## 当前部署限制

- 默认 Compose 写的是 `8000:8000`，会在宿主机所有接口发布端口。本机个人使用应将其改为 `127.0.0.1:8000:8000`；当前应用没有多人访问认证。
- 当前只绑定 `./data:/app/data`。应用备份与下载更新位于容器内的 `/app/backups`、`/app/updates`，不会随 `data` 一起持久化；应将备份下载到宿主机，或自行增加相应绑定目录后再重建容器。
- 当前 Dockerfile 和发布工作流没有复制 `docs/assistant/`，因此依赖内置页面说明的精灵对话和页面帮助不能按 Windows 源码环境的能力描述为开箱可用。
- 默认 Ollama 地址是容器自身的 `127.0.0.1:11434`，不会自动连接宿主机 Ollama；使用本地模型需要单独配置可从容器访问的服务地址。
- 资料库 ZIP 不包含 `data/knowledge/` 和 `data/integrations.dat`；迁移本地文献及密钥配置时单独处理。

以上是当前部署代码的边界，本次文档核对没有修改 Compose、Dockerfile 或发布工作流。
