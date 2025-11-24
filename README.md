# 录屏软件 (Luping)

一个简单易用的录屏软件，可以记录屏幕、键盘和鼠标操作。

## 功能特性

- 🎥 屏幕录制（30fps）
- ⌨️ 键盘操作记录
- 🖱️ 鼠标移动、点击和滚动记录
- 💾 自动保存视频文件和操作事件JSON文件
- 🎨 简洁美观的图形界面
- 📦 可打包为独立可执行文件

## 安装和使用

### 使用 Rye 管理（推荐）

1. **安装 Rye**（如果还没有安装）:
   ```bash
   curl -sSf https://rye-up.com/get | bash
   ```

2. **同步依赖**:
   ```bash
   rye sync
   ```

3. **运行程序**:
   ```bash
   rye run python main.py
   ```

   或者使用脚本命令：
   ```bash
   rye run luping
   ```

### 传统方式

如果你不使用 Rye，也可以使用 pip：

```bash
pip install -r requirements.txt
python gui.py
```

## 打包为可执行文件

### 快速打包

**macOS**:
```bash
./build.sh
# 或
./build-all.sh mac
```

**Windows**:
```cmd
# 1. 安装 Rye（如果还没有）
irm https://rye-up.com/get | iex

# 2. 同步依赖
rye sync

# 3. 打包
build-windows.bat
```

详细说明请查看 [Windows打包说明.md](Windows打包说明.md) 或 [Windows快速开始.md](Windows快速开始.md)

### 跨平台打包

由于 PyInstaller 不支持交叉编译，需要在对应系统上打包：

1. **本地打包**: 在 macOS 上打包 macOS 版本，在 Windows 上打包 Windows 版本
2. **GitHub Actions**: 推送到 GitHub 并创建标签，自动构建所有平台版本（推荐）
3. **详细说明**: 查看 [PACKAGING.md](PACKAGING.md)

打包后的文件将在 `dist/` 目录中：
- **macOS**: `录屏软件.app` (约 120MB)
- **Windows**: `录屏软件.exe` (约 100MB)
- **Linux**: `录屏软件` (约 100MB)

## 使用方法

1. 启动程序后，点击"开始录制"按钮
2. 程序会开始录制屏幕和所有键盘、鼠标操作
3. 点击"停止录制"按钮结束录制
4. 录制文件会自动保存到 `recordings/` 目录（或你指定的目录）

## 输出文件

每次录制会生成两个文件：

- `recording_YYYYMMDD_HHMMSS.mp4` - 屏幕录制视频
- `events_YYYYMMDD_HHMMSS.json` - 键盘和鼠标操作事件（JSON格式）

## 系统要求

- Python 3.8+
- macOS / Linux / Windows
- 需要屏幕录制权限（macOS需要在系统设置中授权）

## 注意事项

- 首次运行时，macOS 可能会要求授予屏幕录制权限
- 录制过程中会占用一定的系统资源
- 建议在录制前关闭不必要的应用程序以提高性能

## 许可证

MIT License
