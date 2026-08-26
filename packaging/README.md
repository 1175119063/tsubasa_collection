# Windows 打包、安装与更新

`build-release.ps1` 生成不含个人资料的目录版和 ZIP。`build-installer.ps1` 只接受 `packaging/release` 内已经审阅的空白目录版，并调用 Inno Setup 6 生成当前用户安装器。

安装器使用固定 AppId，升级时覆盖程序文件但不覆盖既有 `data`；卸载时同样保留 `data`、`backups` 和 `updates`。不要把真实个人资料复制进公开发行目录。

构建安装器前需要单独安装 Inno Setup 6：

```powershell
.\packaging\build-installer.ps1 -Version 0.2.0
```

脚本同时生成草稿 `update-manifest.json`。发布前必须把 `installer_url` 从占位地址改成真实 HTTPS 下载地址，并重新核对版本和 SHA-256。客户端通过环境变量 `TSUBASA_UPDATE_MANIFEST_URL` 指定该清单。

更新流程只负责检查版本、下载和校验安装包，不会替换正在运行的程序。用户应先在首页创建完整备份，关闭翼·时光记，再运行已校验的安装包。

当前仓库仅包含构建基础设施；除非明确执行构建脚本，否则不会创建或发布 release。
