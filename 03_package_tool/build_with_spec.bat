@echo off
chcp 65001 > nul
cls
echo.
echo ╔════════════════════════════════════════════════════════╗
echo ║     SEQ to PNG Converter - 可执行文件打包工具          ║
echo ╚════════════════════════════════════════════════════════╝
echo.

echo [步骤 1/4] 检查并安装依赖...
echo.
python -m pip install --upgrade pip -q
python -m pip install pyinstaller -q
if %errorlevel% neq 0 (
    echo ✗ 依赖安装失败
    pause
    exit /b 1
)
echo ✓ 依赖检查完成
echo.

echo [步骤 2/4] 清理旧文件...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist __pycache__ rmdir /s /q __pycache__
echo ✓ 清理完成
echo.

echo [步骤 3/4] 开始打包...
echo.
pyinstaller seq_converter.spec --clean

if %errorlevel% neq 0 (
    echo.
    echo ╔════════════════════════════════════════════════════════╗
    echo ║                    ✗ 打包失败                         ║
    echo ╚════════════════════════════════════════════════════════╝
    echo.
    pause
    exit /b 1
)

echo.
echo [步骤 4/4] 验证输出...
echo.

if exist "dist\SEQ_to_PNG_Converter.exe" (
    echo ╔════════════════════════════════════════════════════════╗
    echo ║                    ✓ 打包成功！                       ║
    echo ╚════════════════════════════════════════════════════════╝
    echo.
    echo 输出文件: dist\SEQ_to_PNG_Converter.exe
    echo.
    echo 文件大小:
    dir "dist\SEQ_to_PNG_Converter.exe" | find "SEQ_to_PNG_Converter.exe"
    echo.
    echo ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    echo  使用说明:
    echo ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    echo  1. 可执行文件位于: dist\SEQ_to_PNG_Converter.exe
    echo  2. 可以直接复制到其他 Windows 电脑运行
    echo  3. 无需安装 Python 或任何依赖
    echo  4. 双击即可运行
    echo ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    echo.

    choice /C YN /M "是否打开输出目录"
    if errorlevel 2 goto :end
    if errorlevel 1 start dist
) else (
    echo ╔════════════════════════════════════════════════════════╗
    echo ║              ✗ 未找到输出文件                         ║
    echo ╚════════════════════════════════════════════════════════╝
    echo.
)

:end
echo.
pause
