# API 管理与模型接入

本文说明首页“API 管理”的运行边界、密钥存储和飞羽精灵模型路由。

## 当前集成

| 集成 | 用途 | 是否联网 |
| --- | --- | --- |
| 高德 Web 服务 | 中文地点搜索、地址与经纬度转换 | 是 |
| 本地 Ollama | 结构化提取、田野筛选、项目说明；默认开放式对话 | 否 |
| OpenAI 兼容服务 | 可选的开放式多轮对话 | 是 |

地图底图使用 OpenStreetMap，Leaflet 脚本和样式当前从 `unpkg.com` 按需加载，因此显示交互地图也需要网络。

## 飞羽精灵路由

```text
用户消息
├── 精灵对话 ── 本地 Ollama（默认）或所选外部模型
├── 分类字段提取 ── 本地 Ollama + JSON Schema + 程序校验
├── 田野筛选解析 ── 本地 Ollama + JSON Schema + 数据库名称匹配
└── 页面功能说明 ── 本地 Ollama + 项目内置说明
```

外部提供方只扩大开放式对话能力，不参与业务资料写入。任何模型结果都不能绕过现有 API 校验、直接操作数据库或自动保存表单。外部回复按自然语言接收，不要求模型生成固定 JSON、建议列表或字段名；若服务商仍返回兼容的 `answer`/`suggestions` JSON，程序也能继续解析。

问题明显涉及本地记录时，后端会按名称匹配，只附加回答所需的馆藏总数和命中物种、地点或远征摘要。询问“哪些记录”、日期等明细时，最多附加二十笔命中物种记录的时间与地点。普通闲聊不附加馆藏数据。

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

集成配置保存在 `data/integrations.dat`，整个 JSON 载荷使用 Windows DPAPI 加密：

1. 优先使用当前 Windows 用户范围；
2. 如果服务进程未加载用户配置文件而导致用户范围不可用，退回本机范围；
3. 本机范围仍依赖 `data` 目录和文件的访问权限，拥有文件读取权限的同机账户可能具备解密条件；
4. 页面与摘要接口只返回末四位提示，不返回完整 Key；
5. HTTP 错误和应用日志不得拼接 Authorization 请求头或明文 Key。

`integrations.dat` 不进入资料库 ZIP 备份，也不应加入 Git。DPAPI 密文具有 Windows 环境绑定属性，迁移后应重新填写全部 Key。

## 后端接口

- `GET /api/integrations`：读取脱敏配置摘要和本地模型信息；
- `PUT /api/integrations/amap`：保存或清除高德 Key；
- `POST /api/integrations/amap/test`：执行一次高德地点搜索测试；
- `PUT /api/integrations/llm`：选择本地/外部提供方并保存外部配置；
- `POST /api/integrations/llm/test`：向已保存的外部模型发送最小连接测试；
- `POST /api/assistant/chat`：执行多轮精灵对话。

管理接口只面向绑定在 `127.0.0.1` 的单用户本地应用。若未来允许局域网或公网访问，必须先增加身份认证、CSRF 防护、访问审计和更严格的出站地址策略。
