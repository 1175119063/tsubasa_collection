# iNaturalist MCP 与飞羽精灵

2026-10-23：实验已接入主应用的飞羽精灵侧栏和新物种表单。实现集中在 `../backend/app/inat_mcp/`，本目录三个同名文件保留兼容入口，实验与正式功能不再维护两份逻辑。

## 当前能做什么

1. 在飞羽精灵中选择“联网查物种”，输入中文鸟名或完整学名。
2. 中文名必要时经 Wikidata 标签/别名及 P225 转为学名，再查询 iNaturalist。多个同名条目展示学名候选，不直接认定第一个结果。
3. 查看目、科、属、种、简介与保护状态原文，以及来源链接、获取时间、是否使用缓存。
4. 在登记新物种时确认填入空白分类字段。已有分类冲突或来源缺少完整分类时停止；已有内容、亚种、保护等级与备注不会被覆盖。

该入口无需大模型或 API Key。查询只发送名称或编号，不上传观察、坐标或媒体。查询结果不是照片鉴定结果，也不自动保存物种。侧栏提供查阅；填入功能位于新物种录入区。普通精灵对话目前不会自行调用 MCP。

## 结构与运行

| 文件 | 作用 |
| --- | --- |
| `backend/app/inat_mcp/inat_api.py` | 上游 HTTP、缓存、名称消歧、资料规范化 |
| `backend/app/inat_mcp/mcp_server.py` | MCP JSON-RPC stdio，三个只读工具 |
| `backend/app/inat_mcp/mcp_client.py` | 子进程握手、串行请求、超时及退出 |
| `backend/app/online_species_service.py` | 应用查询边界、鸟类物种校验与草稿映射 |
| 本目录 `inat_api.py` / `mcp_server.py` / `mcp_client.py` | 指向上述模块的兼容入口 |
| `demo.py`、`probe_zh.py` | 显式联网实验与报告 |
| `build_aliases.py` | 只读个人数据库并生成实验别名表 |
| `tests_offline.py`、`fake_server.py`、`fixtures/` | 独立实验测试、模拟协议和固定响应样本 |

在项目根目录，用项目 Python 运行（开发环境也可用激活后的 `python`）：

```powershell
.\.conda\envs\tsubasa\python.exe mcp-lab\tests_offline.py
.\.conda\envs\tsubasa\python.exe mcp-lab\demo.py
```

`demo.py` 和 `probe_zh.py` 会联网。直接启动 `mcp-lab/mcp_server.py` 时，stdin/stdout 专用于换行分隔的 UTF-8 JSON-RPC，日志在 stderr。源码服务以 `python -m app.inat_mcp.mcp_server` 启动，工作目录为 `backend/`；打包程序以 `翼·时光记.exe --inat-mcp` 启动同一协议服务，不启动网页或应用数据库。

主应用 API：

- `GET /api/assistant/online-species/status`：本地配置状态，不联网探测，也不代表上游一定在线。
- `POST /api/assistant/online-species/search`：`{"query":"喜鹊"}`，返回已匹配详情或候选。
- `GET /api/assistant/online-species/{taxon_id}`：再次校验候选是有效鸟类物种，返回详情与分类草稿。

## 已修复的实验问题

- 无关 Wikidata 搜索命中不再被当成中文名称证据；同名条目、多个 P225、重复 ID 与不同 ID 的同名结果分别处理。弃用声明不参与解析。
- 中文同名条目的学名候选会被保留，不回退成无关的中文模糊搜索候选。Wikidata 请求失败会尝试 iNaturalist。
- 真实服务的未知工具、参数类型、正整数范围和额外参数错误正确返回 JSON-RPC 错误；布尔、浮点 taxon ID 不再被截断。
- 客户端检查协议版本，不声明未实现的 roots 能力；并发调用串行收发，握手失败和超时都会清理子进程。
- 缓存 key 有版本、原子替换、7 天 TTL、512 个条目上限；写入失败不会抹掉成功查询结果。

## 时限、缓存与限制

工具调用总预算 40 秒，客户端 45 秒硬超时，握手最多 10 秒；每次 HTTP 请求最多 8 秒且受剩余预算约束。每个服务进程内请求间隔至少 1.05 秒，429 显示稍后重试，不自动重试。应用同时只接受一个查询，避免阻塞队列。

应用缓存为 `data/.cache/inat/`，不进入资料 ZIP 备份；实验入口使用本目录 `cache/`。内部环境变量 `TSUBASA_INAT_CACHE_DIR` / `TSUBASA_INAT_ALIASES_DIR` 由应用传入，不需要手动配置。应用关闭开关为 `.env` 中的 `TSUBASA_ONLINE_SPECIES_ENABLED=false`。

实验支持 `aliases.example.json` 和 `aliases.local.json`，通过 `build_aliases.py` 从个人资料只读生成别名；应用查询明确禁用实验别名，避免悄悄覆盖同名候选。缓存、报告、个人别名表均由 Git 忽略。

尚未支持失效分类的同物异名链、完整亚种、保护等级权威核验、照片识别和图鉴批量修订。来源图片不自动下载；署名和许可证保留供核对。中文名可能缺失，不能把英文俗名填入中文字段。

## 验证

主项目 `tests/test_online_species.py` 覆盖真实 MCP 参数错误、缓存传输、并发、握手清理、名称歧义、降级、服务校验和 HTTP 边界，进入根目录 pytest 与 CI。`tests/test_online_species_browser.py` 覆盖模型离线时查询、错误重试、候选选择、空白填充、分类冲突、亚种保留及窄屏布局。独立实验的 `tests_offline.py` 仍需单独运行；其中 3 项在线测试仅在 `LAB_ONLINE=1` 时启用。

```powershell
python -m pytest tests/test_online_species.py -q
python -m pytest tests/test_online_species_browser.py -q
python mcp-lab/tests_offline.py
```

`fixtures/` 是固定样本，不是实时名录；历史样本成功不等于所有鸟名都能准确解析。联网验证也依赖上游可用性。

协议参考：[MCP 工具与错误处理](https://modelcontextprotocol.io/specification/2025-06-18/server/tools)、[初始化与版本协商](https://modelcontextprotocol.io/specification/2025-06-18/basic/lifecycle)、[iNaturalist API](https://api.inaturalist.org/v1/docs/)。
