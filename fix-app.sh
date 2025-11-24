#!/bin/bash
# 修复 macOS .app 无法打开的问题

echo "修复录屏软件.app 的权限问题..."
echo ""

APP_PATH="dist/录屏软件.app"

if [ ! -d "$APP_PATH" ]; then
    echo "错误: 找不到 $APP_PATH"
    echo "请先运行 ./build.sh 打包应用"
    exit 1
fi

# 移除隔离属性（quarantine）
echo "1. 移除隔离属性..."
xattr -cr "$APP_PATH"

# 添加执行权限
echo "2. 设置执行权限..."
chmod +x "$APP_PATH/Contents/MacOS/录屏软件"

echo ""
echo "✅ 修复完成！"
echo ""
echo "如果仍然无法打开，请尝试："
echo "1. 右键点击应用，选择'打开'（会弹出安全提示，选择'打开'）"
echo "2. 或者在'系统设置 > 隐私与安全性'中允许运行"
echo ""
echo "现在可以尝试打开应用："
echo "   open '$APP_PATH'"

