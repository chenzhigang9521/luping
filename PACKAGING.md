# 打包说明

本指南说明如何为不同平台打包录屏软件。

## 快速打包

### macOS 版本

在 macOS 系统上运行：

```bash
./build.sh
# 或
./build-all.sh mac
```

生成的文件：`dist/录屏软件.app`

### Windows 版本

在 Windows 系统上运行：

```cmd
build-windows.bat
```

生成的文件：`dist/录屏软件.exe`

## 详细说明

### 方法 1: 本地打包（推荐用于开发测试）

#### macOS
```bash
rye sync
./build.sh
```

#### Windows
```cmd
rye sync
build-windows.bat
```

### 方法 2: 使用 GitHub Actions（推荐用于发布）

1. 将代码推送到 GitHub
2. 创建并推送一个标签（例如 `v1.0.0`）：
   ```bash
   git tag v1.0.0
   git push origin v1.0.0
   ```
3. GitHub Actions 会自动在三个平台上构建：
   - macOS: `录屏软件-macos.zip`
   - Windows: `录屏软件-windows.zip`
   - Linux: `录屏软件-linux.tar.gz`
4. 在 GitHub 的 Actions 页面下载构建产物

### 方法 3: 使用 Docker（高级）

如果需要在一台机器上构建多个平台，可以使用 Docker：

```bash
# macOS 版本（在 macOS 上）
docker run --rm -v "$PWD:/app" -w /app python:3.9 bash -c "
  pip install rye pyinstaller
  rye sync
  rye run pyinstaller ...
"

# Windows 版本（需要 Windows 容器）
# 在 Windows 上运行或使用 Windows 容器
```

## 打包产物说明

### macOS
- **文件**: `录屏软件.app`
- **类型**: macOS 应用程序包
- **大小**: 约 120-150 MB
- **使用**: 双击即可运行，可以拖拽到 Applications 文件夹

### Windows
- **文件**: `录屏软件.exe`
- **类型**: Windows 可执行文件
- **大小**: 约 100-130 MB
- **使用**: 双击运行，可能需要管理员权限（用于屏幕录制）

### Linux
- **文件**: `录屏软件`
- **类型**: Linux 可执行文件
- **大小**: 约 100-130 MB
- **使用**: 需要执行权限 `chmod +x 录屏软件`

## 分发建议

1. **压缩文件**: 将打包产物压缩为 zip 或 tar.gz
2. **版本号**: 在文件名中包含版本号，如 `录屏软件-v1.0.0-macos.zip`
3. **说明文件**: 包含 README 说明系统要求和安装步骤
4. **数字签名**: 对于正式发布，建议对 macOS 和 Windows 版本进行代码签名

## 嵌入字体以保证 UI 一致性

为了在大量 Windows 机器上保证界面字体一致性，打包流程可以将开源字体一并包含在应用中：

- 将字体文件（`.ttf`/`.otf`）放入 `resources/fonts/`。
- 打包脚本 `tools/run_pyinstaller.py` 会把 `resources/fonts/*.ttf` 自动包含到构建产物（目标目录下的 `fonts/`）。
- 程序启动时会在进程级别尝试注册这些字体（Windows 使用 `AddFontResourceExW`），并把 Tk 的命名字体设置为嵌入字体，从而确保 UI 在没有预安装字体的机器上也能正常显示。

注意与合规：请确认用于分发的字体许可允许嵌入和再分发。推荐使用 Google Noto 字体（开源、适合多语言），或使用你们已有商用许可的字体文件。

## 常见问题

**Q: 可以在 macOS 上打包 Windows 版本吗？**
A: 不可以。PyInstaller 不支持交叉编译。需要在对应的操作系统上打包，或使用 GitHub Actions。

**Q: 打包后的文件很大？**
A: 这是正常的，因为包含了 Python 解释器和所有依赖库。这是独立可执行文件的特点。

**Q: 用户运行时报错？**
A: 
- macOS: 确保在"系统设置 > 隐私与安全性 > 屏幕录制"中授权
- Windows: 可能需要右键"以管理员身份运行"
- Linux: 确保有执行权限

**Q: 如何减小文件大小？**
A: 可以使用 `--exclude-module` 排除不需要的模块，但可能影响功能。建议保持完整打包以确保兼容性。
