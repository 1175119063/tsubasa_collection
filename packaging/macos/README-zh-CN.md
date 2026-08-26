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
`8001:8000`，再访问 <http://127.0.0.1:8001>。
