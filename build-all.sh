#!/bin/bash
# 打包脚本 - 支持指定目标平台打包

echo "录屏软件打包工具"
echo "=================="
echo ""

# 确保在项目根目录
cd "$(dirname "$0")"

# 检查参数
TARGET="${1:-auto}"

case "${TARGET}" in
    mac|macos|darwin)
        echo "打包 macOS 版本..."
        echo ""
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
            echo "✅ macOS 打包完成！"
            echo "📦 .app bundle 位于: dist/录屏软件.app"
            
            # 修复权限问题
            echo ""
            echo "修复应用权限..."
            xattr -cr "dist/录屏软件.app"
            chmod +x "dist/录屏软件.app/Contents/MacOS/录屏软件"
            
            echo ""
            echo "⚠️  首次运行提示："
            echo "   如果应用无法打开，请右键点击应用，选择'打开'"
            echo "   或者运行: ./fix-app.sh"
            echo ""
            echo "💡 可以将整个 录屏软件.app 分发给用户使用"
        else
            echo "❌ macOS 打包失败"
            exit 1
        fi
        ;;
    
    win|windows)
        echo "⚠️  注意：在 macOS 上无法直接打包 Windows 版本"
        echo ""
        echo "请使用以下方法之一："
        echo ""
        echo "方法 1: 在 Windows 系统上运行："
        echo "  ./build.sh"
        echo ""
        echo "方法 2: 使用 GitHub Actions 自动打包（推荐）"
        echo "  查看 .github/workflows/build.yml"
        echo ""
        echo "方法 3: 使用 Docker（需要 Windows 容器）"
        echo ""
        exit 1
        ;;
    
    auto|"")
        # 自动检测当前系统
        OS="$(uname -s)"
        case "${OS}" in
            Darwin*)
                echo "检测到 macOS，开始打包..."
                echo ""
                rye run pyinstaller --clean --noconfirm --onedir \
                    --windowed \
                    --name="录屏软件" \
                    --add-data "recordings:recordings" \
                    luping/gui.py
                
                if [ $? -eq 0 ]; then
                    echo ""
                    echo "✅ macOS 打包完成！"
                    echo "📦 .app bundle 位于: dist/录屏软件.app"
                else
                    echo "❌ 打包失败"
                    exit 1
                fi
                ;;
            Linux*)
                echo "检测到 Linux，开始打包..."
                echo ""
                rye run pyinstaller --clean --noconfirm --onefile \
                    --name="录屏软件" \
                    --add-data "recordings:recordings" \
                    luping/gui.py
                
                if [ $? -eq 0 ]; then
                    echo ""
                    echo "✅ Linux 打包完成！"
                    echo "📦 可执行文件位于: dist/录屏软件"
                else
                    echo "❌ 打包失败"
                    exit 1
                fi
                ;;
            *)
                echo "未知操作系统: ${OS}"
                exit 1
                ;;
        esac
        ;;
    
    *)
        echo "用法: ./build-all.sh [mac|win|auto]"
        echo ""
        echo "参数："
        echo "  mac     - 打包 macOS 版本"
        echo "  win     - 显示 Windows 打包说明"
        echo "  auto    - 自动检测系统并打包（默认）"
        echo ""
        exit 1
        ;;
esac

