# 快速开始指南

## 使用 Rye 管理项目

### 1. 初始化 Rye 项目（如果还没有）

```bash
rye init
```

### 2. 同步依赖

```bash
rye sync
```

这会自动安装所有依赖包到虚拟环境中。

### 3. 运行程序

```bash
rye run python main.py
```

或者使用项目脚本：

```bash
rye run luping
```

### 4. 打包为可执行文件

```bash
./build.sh
```

打包脚本会自动：
- 检测操作系统类型
- 选择最适合的打包模式
- 清理旧的构建文件
- 生成可执行文件或 .app bundle

**macOS 用户**：打包后会生成 `dist/录屏软件.app`，可以直接双击运行或分发给其他用户。

打包后的文件在 `dist/录屏软件`（macOS/Linux）或 `dist/录屏软件.exe`（Windows）

## 首次使用

1. 运行程序后，macOS 可能会弹出权限请求
2. 需要在"系统设置 > 隐私与安全性 > 屏幕录制"中授权
3. 点击"开始录制"开始录制
4. 点击"停止录制"结束录制
5. 文件会自动保存到 `recordings/` 目录

## 项目结构

```
luping/
├── pyproject.toml      # Rye 项目配置和依赖
├── main.py             # 主入口文件
├── build.sh            # 打包脚本
├── README.md           # 项目说明
├── luping/             # 主包目录
│   ├── __init__.py
│   ├── gui.py          # GUI 界面
│   └── recorder.py     # 录制核心功能
└── recordings/         # 录制文件输出目录（自动创建）
```

## 常见问题

**Q: 如何更改输出目录？**
A: 在程序界面中点击"更改输出目录"按钮选择新目录。

**Q: 打包后的文件很大？**
A: 这是正常的，因为包含了 Python 解释器和所有依赖。可以使用 `--onefile` 打包为单个文件。

**Q: 录制时卡顿？**
A: 可以降低帧率，修改 `recorder.py` 中的 `time.sleep(1/30)` 为更大的值（如 `1/15` 为 15fps）。
