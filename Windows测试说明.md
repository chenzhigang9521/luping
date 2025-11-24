# Windows 版本测试说明

## 打包步骤

### 1. 在 Windows 机器上准备环境

1. **安装 Rye**
   ```powershell
   irm https://rye-up.com/get | iex
   ```

2. **进入项目目录**
   ```cmd
   cd C:\path\to\luping
   ```

3. **同步依赖**
   ```cmd
   rye sync
   ```

### 2. 运行打包脚本

```cmd
build-windows.bat
```

打包完成后，会在 `dist\` 目录生成 `录屏软件.exe`

## 测试要点

### 1. 基本功能测试

- [ ] 应用能正常启动，不崩溃
- [ ] 界面正常显示
- [ ] 可以点击"开始录制"按钮
- [ ] 可以点击"停止录制"按钮
- [ ] 录制文件正常生成（视频和 events.json）

### 2. 键盘鼠标监听测试

**Windows 版本应该支持完整的键盘和鼠标监听**：

- [ ] 键盘监听正常启动（查看控制台输出或 events.json）
- [ ] 鼠标监听正常启动（查看控制台输出或 events.json）
- [ ] 录制时按键盘，events.json 中应该有键盘事件
- [ ] 录制时点击鼠标，events.json 中应该有鼠标事件
- [ ] 录制时移动鼠标，events.json 中应该有鼠标移动事件（可能很多）

### 3. 事件文件检查

停止录制后，检查 `recordings\events_*.json` 文件：

```json
[
  {
    "type": "keyboard",
    "action": "press",
    "key": "a",
    "timestamp": 1234567890.123
  },
  {
    "type": "mouse",
    "action": "click",
    "button": "left",
    "x": 100,
    "y": 200,
    "timestamp": 1234567890.456
  }
]
```

### 4. 权限测试

- [ ] 普通用户权限下能否正常录制
- [ ] 是否需要管理员权限（通常不需要，但某些 Windows 版本可能需要）

## 预期行为

### Windows 版本（与 macOS 不同）

✅ **Windows 版本应该：**
- 键盘监听正常工作
- 鼠标监听正常工作
- 不需要特殊权限（除了可能的屏幕录制权限）
- 应用不会崩溃

❌ **macOS 版本：**
- 键盘监听正常工作
- 鼠标监听已禁用（避免崩溃）
- 需要辅助功能权限

## 如果遇到问题

### 问题 1: 应用无法启动

- 检查是否安装了 Visual C++ Redistributable
- 下载地址：https://aka.ms/vs/17/release/vc_redist.x64.exe

### 问题 2: 键盘鼠标事件没有记录

- 检查控制台输出，看是否有"键盘监听已启动"和"鼠标监听已启动"
- 检查 events.json 文件是否为空
- 确保在录制时进行了键盘鼠标操作

### 问题 3: Windows Defender 警告

- 这是正常的，因为应用未签名
- 点击"更多信息" > "仍要运行"
- 或者添加到 Windows Defender 排除列表

### 问题 4: 无法录制屏幕

- 尝试右键以管理员身份运行
- 检查 Windows 屏幕录制权限设置

## 对比 macOS 版本

| 功能 | macOS | Windows |
|------|-------|---------|
| 屏幕录制 | ✅ | ✅ |
| 键盘监听 | ✅ | ✅ |
| 鼠标监听 | ❌ (已禁用) | ✅ |
| 需要特殊权限 | 辅助功能权限 | 通常不需要 |

## 测试完成后

如果 Windows 版本测试通过，说明：
1. ✅ 打包配置正确
2. ✅ pynput 模块正确包含
3. ✅ Windows 上键盘鼠标监听正常工作

可以放心分发给 Windows 用户使用！

