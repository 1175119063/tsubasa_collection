# 飞羽精灵本地模型

安装并启动 Ollama 后，在项目根目录运行：

```powershell
ollama pull qwen3.5:2b-q4_K_M
ollama cp qwen3.5:2b-q4_K_M feiyu-jingling
```

验证：

```powershell
ollama list
```

应用默认连接 `http://127.0.0.1:11434`，模型名称和连接地址可以通过 `.env` 修改。
上下文长度、温度和最大输出长度由应用在每次请求中设置，因此模型别名只负责隔离底层模型名称。

常用检查命令：

```powershell
ollama list
ollama ps
```

`ollama list` 中应出现 `feiyu-jingling:latest`；产生一次请求后，`ollama ps` 会显示模型是否已载入以及使用 CPU/GPU 的比例。模型的第一次请求包含载入时间，应用默认允许等待 120 秒。

若不希望启用本地助手，可在 `.env` 中设置：

```dotenv
TSUBASA_FEATHER_ASSISTANT_ENABLED=false
```
