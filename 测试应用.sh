#!/bin/bash
# 测试应用并显示输出

echo "启动录屏软件（带控制台输出）..."
echo ""

APP_PATH="dist/录屏软件.app/Contents/MacOS/录屏软件"

if [ ! -f "$APP_PATH" ]; then
    echo "错误: 找不到应用"
    exit 1
fi

# 直接运行可执行文件，查看输出
"$APP_PATH" 2>&1

