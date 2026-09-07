# API 管理与模型接入

本文说明首页“API 管理”的运行边界、密钥存储和飞羽精灵模型路由。

## 当前集成

| 集成 | 用途 | 是否联网 |
| --- | --- | --- |
| 高德 Web 服务 | 中文地点搜索、地址与经纬度转换 | 是 |
| 天地图 WMTS | 大陆地区优先使用的矢量底图与中文注记 | 是 |
| 本地 Ollama | 结构化提取、项目说明；未配置外部服务时的对话和田野查询降级 | 否 |
| OpenAI 兼容服务 | 可选的开放式多轮对话与田野记录查询 skill | 是 |

Leaflet 脚本和样式随 Vue 前端在本机提供。配置天地图浏览器端 Key 后，地点选点与探索地图优先加载天地图矢量底图和中文注记；图层控件可以手动切换 OpenStreetMap，天地图初始加载连续失败或八秒内没有返回瓦片时也会自动切换。未配置天地图时直接使用 OpenStreetMap。两种底图均需要网络。

## 飞羽精灵路由

```text
用户消息
├── 精灵对话 ── 本地 Ollama（默认）或所选外部模型
├── 分类字段提取 ── 本地 Ollama + JSON Schema + 程序校验
├── 田野记录查询 ── 所选外部模型（否则本地降级）+ JSON Schema + 只读 SQL 执行器
└── 页面功能说明 ── 本地 Ollama + 项目内置说明
```

外部提供方可以扩大开放式对话和田野查询理解能力，但不参与业务资料写入。任何模型结果都不能绕过现有 API 校验、直接修改数据库或自动保存表单。开放式回复按自然语言接收；田野查询使用通用 Chat Completions 消息要求模型生成参数化 JSON 查询计划，不依赖特定厂商的工具调用协议。

田野查询只开放 `field_observations` 和 `field_observation_taxa` 两个临时只读视图。执行器只接受单条 `SELECT` 或 `WITH ... SELECT`，强制返回观察 ID，并拒绝写操作、多语句、底层表、数据库结构操作和超时查询；单次最多向页面返回 500 笔记录。数据库以只读模式打开，最终命中记录仍由本机程序确定。

问题明显涉及本地记录时，后端会按名称匹配，只附加回答所需的记录总数和命中物种、地点或远征摘要。询问“哪些记录”、日期等明细时，最多附加二十笔命中物种记录的时间与地点。普通闲聊不附加记录数据。

## OpenAI 兼容协议

外部服务需要以下配置：

- `Base URL`：完整 HTTPS 地址，通常为 `https://host.example/v1`；
- `model`：服务商要求的模型标识；
- `API Key`：用于 Bearer 鉴权。

本机回环地址允许 HTTP，远程地址强制 HTTPS。服务端会把 Base URL 规范化为 Chat Completions 地址：

| 输入 | 请求地址 |
| --- | --- |
| `https://host.example` | `https://host.example/v1/chat/completions` |
| `https://host.example/v1` | `https://host.example/v1/chat/completions` |
| `https://host.example/openai/v1` | `https://host.example/openai/v1/chat/completions` |
| 已包含 `/chat/completions` | 原样使用 |

请求采用非流式 `POST`，包含 `model`、`messages`、`temperature`、`max_tokens` 和 `stream: false`。开放式对话要求直接返回自然语言，不启用 JSON Schema。当前不实现厂商专有协议、Responses API、工具调用或流式输出。

## 密钥存储

集成配置保存在 `data/integrations.dat`，使用带格式头的跨平台本地 JSON：

1. 配置不绑定 Windows 用户或机器，可在受信任的设备间单独迁移；
2. 文件中包含明文 Key，必须依赖本机账户、目录和文件权限保护；
3. 页面与配置摘要接口只返回末四位提示；天地图 Key 是浏览器端密钥，`GET /api/map/config` 会将其交给本机页面并随 WMTS 瓦片请求发送；
4. HTTP 错误和应用日志不得拼接 Authorization 请求头或明文 Key；

`integrations.dat` 不进入资料库 ZIP 备份，也不应加入 Git。换电脑后可重新填写全部 Key，或在保护好明文密钥的前提下单独安全迁移该文件。

## 后端接口

- `GET /api/integrations`：读取脱敏配置摘要和本地模型信息；
- `PUT /api/integrations/amap`：保存或清除高德 Key；
- `POST /api/integrations/amap/test`：执行一次高德地点搜索测试；
- `PUT /api/integrations/tianditu`：保存或清除天地图浏览器端 Key；
- `POST /api/integrations/tianditu/test`：请求一张矢量瓦片以验证 Key 和网络；
- `GET /api/map/config`：返回搜索可用状态、底图提供方和本机页面加载底图所需配置；
- `PUT /api/integrations/llm`：选择本地/外部提供方并保存外部配置；
- `POST /api/integrations/llm/test`：向已保存的外部模型发送最小连接测试；
- `POST /api/assistant/chat`：执行多轮精灵对话。
- `POST /api/backups`：创建完整资料库备份；
- `POST /api/backups/restore`：上传、校验并恢复完整备份；
- `GET /api/exports/observations.csv`：导出全部田野记录；
- `GET /api/updates/status`：检查可选 HTTPS 更新清单；
- `POST /api/updates/download`：下载并校验版本号更高的安装包。

管理接口只面向绑定在 `127.0.0.1` 的单用户本地应用。若未来允许局域网或公网访问，必须先增加身份认证、CSRF 防护、访问审计和更严格的出站地址策略。
