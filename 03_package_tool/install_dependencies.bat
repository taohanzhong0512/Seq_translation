@echo off
chcp 65001 > nul
echo.
echo ╔════════════════════════════════════════════════════════╗
echo ║          安装 SEQ to PNG Converter 依赖                ║
echo ╚════════════════════════════════════════════════════════╝
echo.

echo [1/2] 更新 pip...
python -m pip install --upgrade pip

echo.
echo [2/2] 安装所需库...
python -m pip install -r requirements_gui.txt

if %errorlevel% equ 0 (
    echo.
    echo ╔════════════════════════════════════════════════════════╗
    echo ║                  ✓ 安装成功！                         ║
    echo ╚════════════════════════════════════════════════════════╝
    echo.
    echo 已安装的库:
    echo   - PyQt5 (GUI 框架)
    echo   - PyQt-Fluent-Widgets (Fluent Design)
    echo   - Pillow (图像处理)
    echo   - NumPy (数值计算)
    echo.
    echo 现在可以运行:
    echo   python seq_to_png_gui.py
    echo   或双击: run_gui.bat
    echo.
) else (
    echo.
    echo ╔════════════════════════════════════════════════════════╗
    echo ║                  ✗ 安装失败                           ║
    echo ╚════════════════════════════════════════════════════════╝
    echo.
    echo 请检查错误信息
    echo.
)

pause
