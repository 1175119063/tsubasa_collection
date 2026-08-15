# 羽迹

本地鸟类观察记录与个人图鉴。当前仓库包含 FastAPI 后端和一套最小可用 Demo。

## 启动

在项目根目录运行：

```powershell
.\start-demo.ps1
```

也可以直接运行：

```powershell
& '.\.conda\envs\yuhen\python.exe' -m uvicorn app.main:app --app-dir backend --reload
```

然后访问：

```text
http://127.0.0.1:8000
```

页面入口：

- 首页：`http://127.0.0.1:8000/`
- 观察记录：`http://127.0.0.1:8000/observations`
- 个人图鉴：`http://127.0.0.1:8000/dex`

新增观察时，选择 JPEG/JPG 照片后会自动尝试读取 EXIF 拍摄时间；如照片没有可用的时间信息，仍可手动填写。

API 文档：

```text
http://127.0.0.1:8000/docs
```

开发数据默认保存在项目根目录的 `data` 中。该目录已被忽略，不属于源代码。

## 测试

```powershell
& '.\.conda\envs\yuhen\python.exe' -m pytest
```
