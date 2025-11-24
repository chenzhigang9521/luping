# Windows 打包快速开始

## 最简单的方法

### 1. 安装 Rye
在 PowerShell 中运行：
```powershell
irm https://rye-up.com/get | iex
```

### 2. 进入项目目录
```cmd
cd 项目路径\luping
```

### 3. 运行打包脚本
```cmd
build-windows.bat
```

### 4. 完成！
打包完成后，`dist\录屏软件.exe` 就是可执行文件。

## 详细步骤

### 步骤 1: 安装 Rye

**PowerShell（推荐）**：
```powershell
irm https://rye-up.com/get | iex
```

**或者使用 pip**：
```cmd
pip install -m rye
```

### 步骤 2: 准备项目

1. 将项目文件夹复制到 Windows 机器
2. 打开命令提示符或 PowerShell
3. 进入项目目录：
   ```cmd
   cd C:\path\to\luping
   ```

### 步骤 3: 安装依赖

```cmd
rye sync
```

这会自动：
- 创建虚拟环境
- 安装所有依赖包
- 可能需要几分钟时间

### 步骤 4: 打包

**方法 A: 使用脚本（推荐）**
```cmd
build-windows.bat
```

**方法 B: 手动打包**
```cmd
rye run pyinstaller --clean --noconfirm --onefile --windowed --name="录屏软件" --add-data "recordings;recordings" --hidden-import pynput --hidden-import pynput.keyboard --hidden-import pynput.mouse --hidden-import pynput._util --hidden-import pynput._util.win32 luping\gui.py
```

### 步骤 5: 测试

1. 进入 `dist` 目录
2. 双击 `录屏软件.exe` 运行
3. 如果提示需要权限，右键选择"以管理员身份运行"

## 打包结果

- **文件位置**: `dist\录屏软件.exe`
- **文件大小**: 约 100-130 MB
- **类型**: 独立可执行文件，无需安装

## 分发

1. 将 `录屏软件.exe` 压缩为 zip 文件
2. 分发给其他用户
3. 用户解压后直接运行即可

## 注意事项

1. **首次运行**: 可能需要以管理员身份运行（用于屏幕录制权限）
2. **Windows Defender**: 可能会警告未签名的应用，选择"仍要运行"
3. **文件大小**: exe 文件较大是正常的，因为包含了 Python 和所有依赖

## 遇到问题？

查看 `Windows打包说明.md` 获取详细帮助。

