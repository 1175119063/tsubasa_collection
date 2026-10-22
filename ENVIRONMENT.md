# 开发环境

项目使用 Python 3.11 Conda 环境。当前工作区中的环境位置为：

```text
F:\bird_dataset\.conda\envs\tsubasa
```

在 PowerShell 中激活：

```powershell
& 'C:\Users\RAZOR\miniconda3\shell\condabin\conda-hook.ps1'
conda activate 'F:\bird_dataset\.conda\envs\tsubasa'
```

不激活环境也可以直接调用项目解释器：

```powershell
& '.\.conda\envs\tsubasa\python.exe' --version
```

在另一台装有 Conda 的 Windows 电脑上重新创建：

```powershell
conda env create --prefix '.\.conda\envs\tsubasa' --file '.\environment.yml'
```

`.conda` 目录是本机生成环境，不属于项目源代码，也不应放入备份或版本控制。换电脑时使用 `environment.yml` 重新创建即可。

这里所说的“不应放入备份”仅指可重新生成的 `.conda` 环境。真实观察资料位于项目根目录的 `data`，必须单独完整备份；重新创建 Conda 环境不会恢复数据库、照片或录音。

启动翼·时光记时，同一时间只运行一个服务实例。推荐在根目录执行：

```powershell
.\start-demo.ps1
```

使用 `Ctrl+C` 停止服务。若出现 `Errno 10048`，表示 `127.0.0.1:8000` 已被另一份运行中的翼·时光记占用，应先关闭旧实例。

## 本地模型环境

飞羽精灵需要单独安装 Ollama。项目的 Python 环境不包含模型权重；换电脑时需要重新安装 Ollama，并在项目根目录执行：

```powershell
.\packaging\ollama\setup.ps1
```

默认模型服务地址是 `http://127.0.0.1:11434`，应用内模型名是 `feiyu-jingling`。可复制 `.env.example` 中的 `TSUBASA_FEATHER_ASSISTANT_*` 配置进行覆盖。Ollama 的模型目录由 Ollama 自己管理，不应复制进项目的 `data` 或资料库备份。

## API 管理与外部模型

首页底部的“API 管理”可以维护：

- 高德地图 Web 服务 Key；
- 天地图浏览器端 Key；
- 飞羽精灵的对话提供方：本地 Ollama 或 OpenAI Chat Completions 兼容服务；
- 外部模型的 Base URL、模型名称和 API Key。

外部服务的 Base URL 应填写完整 HTTPS 地址，通常以 `/v1` 结尾，例如：

```text
https://api.example.com/v1
```

本机开发服务允许 `http://127.0.0.1`、`http://localhost` 和 `http://[::1]`，非本机地址必须使用 HTTPS。应用会在 Base URL 后规范化拼接 `/chat/completions`。

配置保存在 `data/integrations.dat`，使用跨平台本地 JSON 格式，不绑定特定操作系统、用户或机器。文件中包含明文密钥，应依赖本机账户和目录权限保护；配置页面和 API 摘要只返回密钥末四位；天地图浏览器端 Key 例外地通过地图配置接口提供给页面，用于瓦片请求。

`integrations.dat` 不包含在“完整备份资料库”的 ZIP 中，也不应提交版本控制。换电脑或复制发行包后，应重新填写密钥，或单独安全迁移该文件。启用外部模型后，开放式“精灵对话”、田野记录查询 skill 和本地资料研究可使用对应服务商；分类字段提取和页面功能说明继续使用本地 Ollama。数据库查询始终在本机执行。

高德地图也可以继续通过 `.env` 的 `TSUBASA_AMAP_WEB_SERVICE_KEY` 提供，天地图浏览器端 Key 可以通过 `TSUBASA_TIANDITU_BROWSER_KEY` 提供。只要在 API 管理中保存新的 Key，就会改用本地配置文件中的值；主动清除表示明确停用当前 Key，因此不会自动回退到 `.env`。

本地资料研究的原文片段及出处可能发送给所选外部模型，详见 [API 管理与模型接入](docs/API-MANAGEMENT.md)。`data/knowledge/` 不包含在资料库 ZIP 中，换电脑时应单独迁移。
