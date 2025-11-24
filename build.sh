#!/bin/bash
# 打包脚本 - 使用 PyInstaller 打包为可执行文件

echo "开始打包录屏软件..."

# 确保在项目根目录
cd "$(dirname "$0")"

# 检测操作系统
OS="$(uname -s)"
case "${OS}" in
    Darwin*)
        echo "检测到 macOS，使用 onedir 模式创建 .app bundle"
        # macOS 上使用 onedir + windowed 模式创建 .app bundle
        rye run pyinstaller --clean --noconfirm --onedir \
            --windowed \
            --name="录屏软件" \
            --add-data "recordings:recordings" \
            --hidden-import pynput \
            --hidden-import pynput.keyboard \
            --hidden-import pynput.mouse \
            --hidden-import pynput._util \
            --hidden-import pynput._util.darwin \
            luping/gui.py
        
        if [ $? -eq 0 ]; then
            echo ""
            echo "打包完成！"
            echo ".app bundle 位于: dist/录屏软件.app"
            
            # 修复权限问题
            echo ""
            echo "修复应用权限..."
            xattr -cr "dist/录屏软件.app"
            chmod +x "dist/录屏软件.app/Contents/MacOS/录屏软件"
            
            echo ""
            echo "⚠️  首次运行提示："
            echo "如果应用无法打开，请右键点击应用，选择'打开'"
            echo "或者在'系统设置 > 隐私与安全性'中允许运行"
            echo ""
            echo "💡 也可以运行 ./fix-app.sh 来修复权限问题"
        else
            echo "打包失败，请检查错误信息"
            exit 1
        fi
        ;;
    Linux*)
        echo "检测到 Linux，使用 onefile 模式"
        rye run pyinstaller --clean --noconfirm --onefile \
            --name="录屏软件" \
            --add-data "recordings:recordings" \
            luping/gui.py
        
        if [ $? -eq 0 ]; then
            echo ""
            echo "打包完成！可执行文件位于: dist/录屏软件"
            echo "可以将 dist/录屏软件 分发给用户使用"
        else
            echo "打包失败，请检查错误信息"
            exit 1
        fi
        ;;
    MINGW*|MSYS*|CYGWIN*)
        echo "检测到 Windows，使用 onefile + windowed 模式"
        rye run pyinstaller --clean --noconfirm --onefile \
            --windowed \
            --name="录屏软件" \
            --add-data "recordings;recordings" \
            luping/gui.py
        
        if [ $? -eq 0 ]; then
            echo ""
            echo "打包完成！可执行文件位于: dist/录屏软件.exe"
            echo "可以将 dist/录屏软件.exe 分发给用户使用"
        else
            echo "打包失败，请检查错误信息"
            exit 1
        fi
        ;;
    *)
        echo "未知操作系统: ${OS}"
        echo "使用默认配置（onefile 模式）"
        rye run pyinstaller --clean --noconfirm --onefile \
            --name="录屏软件" \
            --add-data "recordings:recordings" \
            luping/gui.py
        
        if [ $? -eq 0 ]; then
            echo ""
            echo "打包完成！可执行文件位于 dist/ 目录"
        else
            echo "打包失败，请检查错误信息"
            exit 1
        fi
        ;;
esac
