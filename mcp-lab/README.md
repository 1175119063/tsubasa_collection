# iNat MCP 实验（mcp-lab）

一个使用 Python 标准库的独立实验目录，用于验证 iNaturalist 资料查询与本机 MCP stdio 通信。**当前尚未接入“登记新发现”、图鉴编辑或飞羽精灵。**

实验不修改主应用资料；`build_aliases.py` 会只读访问 `data/database.sqlite`，在本目录生成本地别名表。`demo.py`、在线测试和探针会访问外部服务，缓存与报告保存在本目录。

本文于 2026-10-22 对照代码复核。下面的在线样本与耗时是已有实验记录，不代表实时服务保证；代码审查发现的缺陷见“已知问题与接入前验收”。

目的是回答两个问题：

1. iNaturalist API 能不能支撑"新物种表单的在线预填充"？
2. 本机 MCP（stdio）在 Windows 单机应用里跑起来是什么手感，有哪些坑？

## 已验证的实验结果

- **学名查询样本成功**：`Chlidonias hybrida` 精确命中 `#62148`，带目/科/属祖先链。
- **中文自由文本不可靠**：`q=灰翅浮鸥` 返回 7177 条模糊结果，前 5 条是"有翅亚纲、鳞翅目、鞘翅目……"，目标物种不在其中。不能拿它直接做自动填充。
- **中文名有地区差异**：iNat 的 `zh-CN` 名称是"灰翅浮鸥"，中文维基条目叫"须浮鸥"，摘要里还写着"又名黑腹燕鷗、黑腹浮鷗"。所以别名层是必需品，不是优化项。
- **中文名可以桥接**：Wikidata 搜索"灰翅浮鸥"得到 Q233616，`P225` 是 `Chlidonias hybrida`，再用 iNat 精确匹配验证，最终仍落在 `#62148`。
- **摘要需要清洗**：`wikipedia_summary` 含 `<b>`/`<i>` 标签；默认照片许可为 `cc-by-nc`，`attribution` 完整。实验只保留链接、作者和许可，不下载图片。
- **MCP 基础链路跑通**：握手、工具列表、工具调用、超时、进程崩溃和通知不回包已有测试；部分异常只测了 fake server，不能据此认定真实服务完整符合协议。
- **延迟可接受**：中文名经 Wikidata 解析冷启动 6.5s，命中本地缓存后 0.03s；MCP 端缓存命中时整段演示 1.6s。
- **别名表有效**：从应用数据库只读出 39 组中文名/学名，加上示例共 41 条；"东方大苇莺" → `Acrocephalus orientalis` 直接命中。
- **测试记录**：原实验记录为 11 项离线、3 项在线通过；本次复核重新运行了 11 项离线测试，全部通过，3 项在线测试跳过。尚未覆盖下文列出的解析与协议缺陷。

实测输出（冷缓存）：

```text
[1] iNat scientific search: total=4 top=#62148 Chlidonias hybrida (1.5s)
[2] iNat Chinese free text: total=7177 exact_match_in_top5=False
    top=["Pterygota","Lepidoptera","Coleoptera","Hymenoptera","Hemiptera"]
[3] resolve 灰翅浮鸥 (no alias): via=wikidata -> #62148 (cold=6.50s warm=0.03s)
[5] MCP handshake: protocol=2025-06-18 server=tsubasa-inat-lab
    tools=['search_taxa','get_taxon','resolve_name']
[6] MCP search_taxa: cached=True
[8] MCP get_taxon: order=Charadriiformes family=Laridae genus=Chlidonias
    photo_license=cc-by-nc
[9] MCP tool error path: {"error":{"type":"inat_error","status":404}}
```

## 文件

| 文件 | 作用 |
| --- | --- |
| `inat_api.py` | 只读 iNat 客户端：搜索、取详情、中文名解析、30 天缓存、出处字段 |
| `mcp_server.py` | stdio MCP server，暴露 `search_taxa` / `get_taxon` / `resolve_name` |
| `mcp_client.py` | 手写 stdio MCP client：握手、按 id 收包、超时、stderr 排空 |
| `demo.py` | 端到端演示，输出到 `artifacts/` |
| `tests_offline.py` | 11 项离线测试（fake server + 真实响应 fixture），`LAB_ONLINE=1` 时加 3 项在线测试 |
| `fake_server.py` | 可切换 normal / silent / crash 的协议测试桩 |
| `build_aliases.py` | 只读应用数据库，生成 `aliases.local.json` |
| `probe_zh.py` | 中文名行为探针（也可复现 PowerShell 管道编码坑） |
| `fixtures/` | 实测保存的 iNat / Wikidata 响应 |
| `cache/`、`artifacts/`、`aliases.local.json` | 运行产物，已在 `mcp-lab/.gitignore` 中忽略 |

## 可以用来做什么

| 场景 | 可复用能力 | 当前边界 |
| --- | --- | --- |
| 登记新物种时辅助填表 | 按名称查询候选，获取学名、目科属、摘要及来源 | 需要先修复解析歧义，再增加候选选择和字段确认界面 |
| 为已有图鉴补充资料 | 查询外部资料，与用户内容并排核对 | 不自动覆盖简介、分类或个人观察笔记 |
| 中文别名查询 | 本地别名与 Wikidata 到学名的桥接 | 已有图鉴别名适合回查；不能保证新物种名称准确或唯一 |
| 飞羽精灵在线查询 | 通过三个只读 MCP 工具取得可追溯资料 | 当前没有接入助手，也没有联网开关或查询状态界面 |

当前工具不支持照片识鸟、鸟鸣识别、照片行为判断、完整亚种名单，也不能直接保证中国保护等级准确。保护状况返回的是来源条目集合，需要核对机构、地区和适用范围，不能直接当作主应用保护等级。

## 运行

在项目根目录执行。离线测试不需要联网或个人数据库；别名生成与演示单独按需运行。

```powershell
Set-Location .\mcp-lab
$env:LAB_ONLINE = '0'
& '..\.conda\envs\tsubasa\python.exe' tests_offline.py

# 可选：从已有图鉴生成本地别名
& '..\.conda\envs\tsubasa\python.exe' build_aliases.py
# 在线演示：访问 iNaturalist / Wikidata 并写入本目录的运行产物
& '..\.conda\envs\tsubasa\python.exe' demo.py
```

在线测试：

```powershell
$env:LAB_ONLINE = '1'
try {
    & '..\.conda\envs\tsubasa\python.exe' tests_offline.py
} finally {
    $env:LAB_ONLINE = '0'
}
```

> 优先执行 UTF-8 编码的 `.py` 文件。PowerShell 管道编码与 Python stdin 编码不一致时，中文字面量可能变成 `????`；不要把这种编码问题误判为在线搜索失败。

## 三个工具

- `search_taxa(query, locale, limit, rank)`：只做模糊候选，返回 `total_results` 和紧凑列表。
- `get_taxon(taxon_id, locale)`：祖先链、目/科/属、清洗后的摘要、保护状况、默认照片许可、`source_url` / `fetched_at` / `cached`。
- `resolve_name(name, locale, use_aliases, allow_wikidata)`：有本地别名或输入不含中文时先查 iNat；中文输入允许 Wikidata 时再走 P225 桥接，最后尝试 iNat 常见名精确匹配。无匹配时返回 `resolved=false` 和候选；上游异常当前可能直接中断。**`resolved=true` 只表示现有算法接受了匹配，不是无歧义保证。**

## 建议的首个接入流程（尚未实现）

**输入名称 → 展示候选 → 用户选择 → 获取详情 → 勾选字段 → 填入草稿 → 按现有流程保存。**

1. 前端可在 `ObservationSpeciesAssistant.vue` 中增加在线资料入口，展示中文名、学名、分类等级、来源和匹配方式；多个候选不自动选择第一项。
2. 后端确定性编排查询。学名、分类链和来源等结构化内容直接映射为建议；模型只作为可选的摘要整理步骤，不负责决定物种身份或重新生成分类。
3. 分类路径首先用于比较；与当前目科属不同时明确展示差异。接入前需更新主项目当前“本地资料辅助”的来源规则，不隐式覆盖它，也不绕过共享分类节点的编辑与影响预览。
4. 查询只读，填入仅改变表单草稿；最终保存沿用既有校验和事务。外部图片只提供参考链接及署名许可，不作为个人实拍凭证，不因查询成功创建已收录物种。
5. 可沿用主项目 `{extraction, citations}` 的响应方向，但需要补充字段级来源、实际查询 URL、抓取时间、匹配方式，以及适用的许可信息。名称解析失败、资料缺失和网络异常分别展示。
6. 联网发送查询名称及必要查询参数，不发送观察照片、坐标或整库资料。提供明确的联网说明、状态与超时；缓存命中也显示原始抓取时间。

打包方案仍待验证：可以研究同一 exe 的 `--mcp-inat` 子进程入口，或单独附带服务程序。客户端需要持续排空 stderr；当前实现仅适合串行调用，同一客户端并发请求会竞争收包队列，需要加串行锁或按请求 ID 分发结果。

## 已知问题与接入前验收

以下问题在本次复核时仍然存在，尚未修复：

| 优先级 | 问题与影响 | 修复及验收目标 |
| --- | --- | --- |
| 高 | Wikidata 选取首个描述符合条件且有 P225 的候选，未核对输入名称与候选标签/别名；随后学名精确匹配不能验证这一步关联正确 | 核对名称及别名，保留歧义；使用无关候选、同名多候选验证不会直接返回已确认结果 |
| 高 | `_exact_match` 接受第一个同名结果，没有验证唯一性，也未限定为鸟类物种 | 候选明确展示分类等级，主应用选择时校验鸟类与物种等级；多个有效结果要求选择 |
| 中 | Wikidata 超时或 HTTP 错误直接中断，iNat 常见名备用查询不执行 | 捕获分支失败，保留警告并尝试后续路径；模拟 503/超时验证 |
| 中 | 真实 server 的 `except Exception` 吞掉 `RpcError`，未知工具变成 `internal_error`；现有对应测试仅覆盖 fake server | 单独透传协议错误，对真实服务验证未知工具与参数错误 |
| 中 | `get_taxon` 使用 `int(taxon_id)`，例如 `1.9` 会查询编号 `1`，与声明的正整数 schema 不一致 | 严格校验类型、正数及额外参数；验证浮点、布尔、零、负数等输入 |
| 中 | 客户端未校验协商结果是否为支持的协议版本，声明 roots 能力但未处理 roots 请求 | 校验版本，只声明实际支持的能力；补充握手异常测试 |

还未实现 429 限流退避、统一的整次查询时限、缓存版本失效与容量控制，以及失效分类单元的同物异名链处理。缓存 TTL 为 30 天；多次外部请求的总耗时可能超过客户端默认 30 秒调用超时。缓存写入目前不是原子替换。

本次离线复现确认：注入与输入无关的 Wikidata 鸟类候选，现有代码仍可返回 `resolved=true`；模拟 Wikidata 503 时备用查询调用次数为零；真实服务的未知工具返回 `isError=true / internal_error`；浮点 taxon ID 被截断。这些是边界复现，不代表线上 API 实际返回了上述错误候选。

MCP 协议对照：[工具与错误处理](https://modelcontextprotocol.io/specification/2025-06-18/server/tools#error-handling)、[初始化与版本协商](https://modelcontextprotocol.io/specification/2025-06-18/basic/lifecycle)。

## 数据与验证边界

- `fixtures/` 是纳入版本控制的 API 响应样本；其中的时间、名称、状态和媒体链接不是实时数据，不能用单一样本推断所有查询的准确率。
- `cache/`、`artifacts/`、`aliases.local.json` 和 Python 缓存已忽略；个人数据库不进入实验提交。
- 根目录 pytest 的 `testpaths` 仅包含 `tests/`，当前 CI 不会自动运行本目录的 `tests_offline.py`；需要按上述命令单独执行。
- 本实验尚未修改主应用 API、UI、鉴权或打包。在线预填充属于后续方向，不是当前正式功能。
