# SEQ to PNG Converter - 完整发布包

## 📦 文件夹说明

```
SEQ_Converter_Release/
├── 01_可执行文件/           ← 🚀 直接运行的程序
├── 02_源代码/               ← 💻 Python 源代码
├── 03_打包工具/             ← 🔧 重新打包所需文件
├── 04_文档说明/             ← 📖 所有说明文档
├── 05_资源文件/             ← 🎨 图标和图片资源
└── README.md               ← 📄 本文件
```

---

## 🚀 快速开始

### 普通用户：直接使用

1. 进入 `01_可执行文件` 文件夹
2. 双击 `SEQ_to_PNG_Converter.exe`
3. 开始使用！

**无需安装任何软件！**

---

## 💻 开发者：修改和打包

### 环境准备

#### 1. 安装 Python
- Python 3.10 或更高版本
- 下载：https://www.python.org/downloads/

#### 2. 安装依赖
```bash
# 进入打包工具文件夹
cd 03_打包工具

# 双击运行（或命令行）
install_dependencies.bat
```

### 修改源代码

#### 1. 编辑代码
- 主程序：`02_源代码/seq_to_png_gui.py`
- 核心模块：`02_源代码/seq_to_png.py`

#### 2. 测试运行
```bash
# 在 02_源代码 目录下
python seq_to_png_gui.py
```

### 重新打包

#### 方法一：使用批处理脚本（推荐）

1. 将以下文件复制到**项目根目录**：
   ```
   02_源代码/seq_to_png_gui.py
   02_源代码/seq_to_png.py
   03_打包工具/seq_converter.spec
   03_打包工具/build_with_spec.bat
   ```

2. 确保 `05_资源文件/image/` 在正确位置

3. 双击运行 `build_with_spec.bat`

4. 打包完成后，新的 EXE 文件在 `dist` 文件夹

#### 方法二：手动命令行

```bash
# 1. 准备目录结构
# 确保项目根目录有以下结构：
# project/
# ├── code/
# │   ├── seq_to_png_gui.py
# │   ├── seq_to_png.py
# │   └── seq_converter.spec
# └── image/
#     ├── DCS_Application_Logo.ico
#     ├── DCS_icon_multi.ico
#     └── SIOM_logo.png

# 2. 进入代码目录
cd code

# 3. 运行打包命令
python -m PyInstaller seq_converter.spec --noconfirm

# 4. 完成！查看 dist 文件夹
```

---

## 📋 详细打包步骤

### 步骤 1: 准备项目结构

**必需的目录结构：**
```
DCS_script/                    ← 项目根目录
├── code/                      ← 代码目录
│   ├── seq_to_png_gui.py     ← GUI 主程序
│   ├── seq_to_png.py         ← 核心转换模块
│   ├── seq_converter.spec    ← PyInstaller 配置
│   └── build_with_spec.bat   ← 打包脚本
└── image/                     ← 资源目录
    ├── DCS_Application_Logo.ico
    ├── DCS_icon_multi.ico    ← 多尺寸图标
    └── SIOM_logo.png
```

### 步骤 2: 安装打包工具

```bash
# 安装 PyInstaller
pip install pyinstaller

# 或使用提供的脚本
cd 03_打包工具
install_dependencies.bat
```

### 步骤 3: 配置文件说明

#### seq_converter.spec 配置文件
这个文件控制打包行为：

```python
# 关键配置项：
datas=[
    # 图标文件会被打包到 image 目录
    ('../image/SIOM_logo.png', 'image'),
    ('../image/DCS_Application_Logo.ico', 'image'),
]

# 隐藏导入（确保所有依赖都被打包）
hiddenimports=[
    'PyQt5',
    'qfluentwidgets',
    'PIL',
    'numpy',
    # ... 其他依赖
]

# 图标设置
icon='../image/DCS_icon_multi.ico'  # EXE 文件图标
```

### 步骤 4: 执行打包

#### 使用批处理脚本（最简单）
```bash
cd code
build_with_spec.bat
```

#### 使用 Python 命令
```bash
cd code
python -m PyInstaller seq_converter.spec --clean --noconfirm
```

**参数说明：**
- `--clean`: 清理临时文件
- `--noconfirm`: 自动覆盖旧文件

### 步骤 5: 验证结果

打包成功后，检查：
```
code/
├── dist/
│   └── SEQ_to_PNG_Converter.exe  ← ✅ 最终产品
└── build/                         ← 临时文件（可删除）
```

**测试清单：**
- ✅ EXE 文件可以双击运行
- ✅ 窗口标题栏显示图标
- ✅ 界面右上角显示 SIOM logo
- ✅ 所有功能正常工作

---

## 🔍 常见问题

### Q1: 打包失败，提示找不到模块？
**A**: 安装缺失的依赖
```bash
pip install -r requirements_gui.txt
```

### Q2: 打包后运行出错？
**A**: 检查以下几点：
1. 图标文件路径是否正确（spec 文件中）
2. 是否所有依赖都在 hiddenimports 中
3. 查看 build 目录下的 warn 文件

### Q3: 图标不显示？
**A**:
1. EXE 文件图标：检查 spec 文件中 icon 参数
2. 窗口图标：确保资源文件在 datas 中
3. 清除图标缓存或重启

### Q4: 打包后文件太大？
**A**:
- 正常大小：约 91 MB
- 包含完整的 Python + PyQt5 + qfluentwidgets
- 如需减小：可以排除不必要的模块

### Q5: 如何修改图标？
**A**:
1. 替换 `image` 目录下的图标文件
2. 使用多尺寸图标（16×16 到 256×256）
3. 重新打包

---

## 📚 文件说明

### 源代码文件

#### seq_to_png_gui.py
- GUI 主程序
- 使用 PyQt5 + qfluentwidgets
- 包含界面设计和事件处理

#### seq_to_png.py
- 核心转换模块
- SEQ 文件解析
- PNG 图像生成

### 打包文件

#### seq_converter.spec
- PyInstaller 配置文件
- 控制打包行为
- 指定资源文件和依赖

#### build_with_spec.bat
- 一键打包脚本
- 自动清理和构建
- 显示详细进度

#### requirements_gui.txt
- Python 依赖列表
- 用于开发环境安装

#### install_dependencies.bat
- 自动安装所有依赖
- 适合开发环境设置

---

## 🎯 打包最佳实践

### 1. 版本控制
每次打包前，记录：
- 版本号
- 修改内容
- 打包日期

### 2. 测试流程
打包后必须测试：
1. ✅ 在干净的 Windows 系统上运行
2. ✅ 测试所有功能
3. ✅ 验证图标显示
4. ✅ 检查错误处理

### 3. 文件管理
- 保留源代码备份
- 保存 spec 配置文件
- 记录依赖版本

### 4. 发布前检查
- [ ] 版本号更新
- [ ] 测试所有功能
- [ ] 更新文档
- [ ] 准备发布说明

---

## 💡 优化建议

### 减小文件大小
```python
# 在 spec 文件中排除不需要的模块
excludes=[
    'matplotlib',
    'scipy',  # 如果不需要
    'test',
    'unittest',
]
```

### 加快启动速度
- 使用 `--onefile` 打包（已使用）
- 考虑使用 `upx` 压缩（已启用）

### 提升兼容性
- 在目标 Windows 版本上测试
- 使用相对路径加载资源
- 处理各种异常情况

---

## 📞 技术支持

### 遇到问题？

1. **查看文档**
   - 查看 `04_文档说明` 中的详细文档

2. **检查日志**
   - 开发环境：查看终端输出
   - 打包后：查看 `build/warn-*.txt`

3. **常用命令**
   ```bash
   # 查看 PyInstaller 版本
   pyinstaller --version

   # 查看 Python 版本
   python --version

   # 列出已安装的包
   pip list
   ```

---

## ✨ 版本历史

### v1.0 (2025-11-10)
- ✅ 初始版本
- ✅ 完整的 GUI 界面
- ✅ 支持 SEQ 到 PNG 转换
- ✅ Fluent Design 风格
- ✅ 完整的打包配置

---

## 📄 许可证

本项目仅供内部使用。

---

*最后更新: 2025-11-10*
*Python 版本: 3.14.0*
*PyInstaller 版本: 6.16.0*
