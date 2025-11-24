# Windows 打包说明

## 前置要求

### 1. 安装 Python 3.9+
- 下载并安装 Python 3.9 或更高版本
- 下载地址：https://www.python.org/downloads/
- 安装时勾选 "Add Python to PATH"

### 2. 安装 Rye
打开 PowerShell 或命令提示符，运行：

```powershell
irm https://rye-up.com/get | iex
```

或者使用 pip：

```cmd
pip install -m rye
```

### 3. 准备项目文件
将整个项目文件夹复制到 Windows 机器上。

## 打包步骤

### 方法 1: 使用批处理脚本（推荐）

1. **打开命令提示符或 PowerShell**
   - 在项目目录中，按住 Shift + 右键
   - 选择"在此处打开 PowerShell 窗口"或"在此处打开命令提示符窗口"

2. **同步依赖**
   ```cmd
   rye sync
   ```
   这会自动安装所有依赖包。

3. **运行打包脚本**
   ```cmd
   build-windows.bat
   ```

4. **等待打包完成**
   - 打包过程可能需要几分钟
   - 完成后会在 `dist/` 目录生成 `录屏软件.exe`

### 方法 2: 手动打包

如果批处理脚本不工作，可以手动运行：

```cmd
rye run pyinstaller --clean --noconfirm --onefile --windowed --name="录屏软件" --add-data "recordings;recordings" --hidden-import pynput --hidden-import pynput.keyboard --hidden-import pynput.mouse --hidden-import pynput._util --hidden-import pynput._util.win32 luping\gui.py
```

## 打包后的文件

打包完成后，会在 `dist/` 目录生成：
- **录屏软件.exe** - 可执行文件（约 100-130 MB）

## 分发应用

1. **测试应用**
   - 双击 `dist/录屏软件.exe` 运行
   - 测试录制功能是否正常

2. **压缩分发**
   - 将 `录屏软件.exe` 压缩为 zip 文件
   - 可以分发给其他 Windows 用户

3. **注意事项**
   - Windows Defender 可能会警告未签名的应用
   - 用户需要点击"更多信息" > "仍要运行"
   - 或者右键选择"以管理员身份运行"（用于屏幕录制权限）

## 常见问题

### Q: 打包时提示找不到 rye？
A: 确保 Rye 已正确安装，并且已添加到 PATH 环境变量中。

### Q: 打包时提示找不到 Python？
A: 确保 Python 已安装并添加到 PATH，或者使用 `rye sync` 会自动安装 Python。

### Q: 打包失败，提示缺少模块？
A: 运行 `rye sync` 确保所有依赖都已安装。

### Q: 生成的 exe 文件很大？
A: 这是正常的，因为包含了 Python 解释器和所有依赖库。这是独立可执行文件的特点。

### Q: 运行时提示缺少 DLL？
A: 可能需要安装 Visual C++ Redistributable：
- 下载地址：https://aka.ms/vs/17/release/vc_redist.x64.exe

### Q: 无法录制屏幕？
A: 
- 确保以管理员身份运行（右键 > 以管理员身份运行）
- Windows 10/11 可能需要屏幕录制权限

## 使用 GitHub Actions 自动打包（推荐）

如果你有 GitHub 账号，可以使用 GitHub Actions 自动打包：

1. 将代码推送到 GitHub
2. 创建标签：`git tag v1.0.0 && git push origin v1.0.0`
3. GitHub Actions 会自动构建 Windows 版本
4. 在 Actions 页面下载构建产物

详细说明请查看 `.github/workflows/build.yml`

