# 开发环境

项目使用 Python 3.11 Conda 环境。当前移动硬盘上的环境位置为：

```text
F:\bird_dataset\.conda\envs\yuhen
```

在 PowerShell 中激活：

```powershell
& 'C:\Users\RAZOR\miniconda3\shell\condabin\conda-hook.ps1'
conda activate 'F:\bird_dataset\.conda\envs\yuhen'
```

不激活环境也可以直接调用项目解释器：

```powershell
& '.\.conda\envs\yuhen\python.exe' --version
```

在另一台装有 Conda 的 Windows 电脑上重新创建：

```powershell
conda env create --prefix '.\.conda\envs\yuhen' --file '.\environment.yml'
```

`.conda` 目录是本机生成环境，不属于项目源代码，也不应放入备份或版本控制。换电脑时使用 `environment.yml` 重新创建即可。
