# SEQ 双向转换器 - 使用说明

## 功能概述

本项目现已支持完整的双向转换功能：

### 模式 1: SEQ → 图像序列
- 将 Norpix StreamPix SEQ 文件转换为图像序列
- 支持输出格式：PNG、TIFF、BMP
- 支持位深度：8位、16位、24位
- 支持帧范围选择

### 模式 2: 图像序列 → SEQ/视频
- 将图像序列转换为 SEQ 文件
- 将图像序列转换为视频文件（AVI、MP4、MOV）
- 支持输入格式：PNG、BMP、TIFF
- 可配置帧率、编码器、质量等参数

## 文件说明

### 核心模块
- **seq_to_png.py** - SEQ 文件读取器（原有功能）
- **images_to_seq.py** - 图像序列 → SEQ 写入器（新增）
- **images_to_video.py** - 图像序列 → 视频转换器（新增）

### GUI 程序
- **seq_converter_gui.py** - 双向转换 GUI（新版）
- **seq_to_png_gui.py** - 原版 GUI（仅 SEQ → 图像，已备份）

## 使用方法

### 方法 1: GUI 界面（推荐）

运行双向转换 GUI：
```bash
python seq_converter_gui.py
```

界面包含两个模式，通过顶部的分段控件切换：

#### 模式 1: SEQ → 图像
1. 点击"浏览"选择 SEQ 文件
2. 选择输出目录
3. 设置参数：
   - 起始帧号 / 结束帧号
   - 文件名前缀（可使用时间戳）
   - 输出格式（PNG/TIFF/BMP）
4. 点击"开始转换"

#### 模式 2: 图像 → SEQ/视频
1. 点击"浏览"选择输入图像目录
2. 点击"浏览"指定输出文件路径
3. 选择输出类型：
   - **SEQ**: 转换为 Norpix StreamPix SEQ 文件
   - **AVI**: 转换为 AVI 视频
   - **MP4**: 转换为 MP4 视频
   - **MOV**: 转换为 MOV 视频
4. 设置参数：
   - 输入图像格式（全部/PNG/BMP/TIFF）
   - 帧率（fps）
   - **SEQ 专用**: 位深度（8/16/24）
   - **视频专用**: 编码器、质量
   - 帧范围（可选）
5. 点击"开始转换"

### 方法 2: 命令行

#### SEQ → 图像
```bash
python seq_to_png.py input.seq -o output_dir -f PNG
```

参数说明：
- `-o, --output`: 输出目录
- `-s, --start`: 起始帧号
- `-e, --end`: 结束帧号
- `-p, --prefix`: 文件名前缀
- `-f, --format`: 输出格式（PNG/TIFF/BMP）

#### 图像 → SEQ
```bash
python images_to_seq.py input_dir -o output.seq -r 30 -b 8
```

参数说明：
- `input_dir`: 输入图像目录
- `-o, --output`: 输出 SEQ 文件路径
- `-f, --format`: 图像格式（png/bmp/tiff/all）
- `-r, --framerate`: 帧率（默认 30）
- `-b, --bitdepth`: 位深度（8/16/24，默认 8）
- `-s, --start`: 起始帧号
- `-e, --end`: 结束帧号

#### 图像 → 视频
```bash
python images_to_video.py input_dir -o output.mp4 -r 30 -q high
```

参数说明：
- `input_dir`: 输入图像目录
- `-o, --output`: 输出视频文件路径
- `-f, --format`: 图像格式（png/bmp/tiff/all）
- `-r, --framerate`: 帧率（默认 30）
- `-c, --codec`: 视频编码器（auto/libxvid/libx264/libx265）
- `-q, --quality`: 视频质量（low/medium/high/best）
- `-s, --start`: 起始帧号
- `-e, --end`: 结束帧号

## 参数详解

### 图像格式
- **PNG**: 无损压缩，推荐用于质量要求高的场景
- **TIFF**: 无损，支持高位深度
- **BMP**: 无压缩，文件较大

### SEQ 位深度
- **8位**: 灰度图，文件较小
- **16位**: 高精度灰度图
- **24位**: RGB 彩色图

### 视频编码器
- **auto**: 根据输出格式自动选择
- **libxvid**: MPEG-4，适合 AVI
- **libx264**: H.264，通用性好，适合 MP4/MOV
- **libx265**: H.265，压缩率高，文件更小

### 视频质量
- **low**: 低质量，文件小
- **medium**: 中等质量
- **high**: 高质量，推荐
- **best**: 最佳质量，文件较大

## 依赖要求

### Python 包
```bash
pip install PyQt5 PyQt-Fluent-Widgets Pillow numpy
```

### FFmpeg（用于视频转换）
图像 → 视频功能需要安装 FFmpeg：

#### Windows
1. 下载 FFmpeg: https://ffmpeg.org/download.html
2. 解压到任意目录
3. 将 `bin` 目录添加到系统 PATH

#### 验证安装
```bash
ffmpeg -version
```

## 注意事项

### 文件命名规则
图像序列的文件名应包含序号，支持的格式：
- `frame_001.png`, `frame_002.png`, ...
- `img_00001.bmp`, `img_00002.bmp`, ...
- `image.001.tiff`, `image.002.tiff`, ...

程序会自动按序号排序。

### SEQ 格式兼容性
- 生成的 SEQ 文件遵循 Norpix StreamPix 格式规范
- 文件头固定为 8192 字节
- 支持的位深度：8位（灰度）、16位（灰度）、24位（RGB）

### 性能提示
- 大量图像转换可能需要较长时间
- 转换过程中可点击"停止"按钮取消操作
- 日志窗口会显示详细的转换进度

## 示例工作流

### 示例 1: SEQ → PNG → 编辑 → MP4
1. 使用模式 1 将 SEQ 转换为 PNG 序列
2. 使用图像编辑软件处理 PNG 文件
3. 使用模式 2 将 PNG 序列转换为 MP4 视频

### 示例 2: 多个 BMP → SEQ 归档
1. 准备 BMP 图像序列
2. 使用模式 2 选择"SEQ"输出类型
3. 设置合适的位深度和帧率
4. 生成 SEQ 文件用于归档或分析

## 故障排除

### 问题：视频转换失败
**解决方案**：
- 确保已安装 FFmpeg 并添加到 PATH
- 检查图像文件是否完整
- 尝试不同的编码器或质量设置

### 问题：SEQ 文件无法识别
**解决方案**：
- 确认 SEQ 文件是 Norpix StreamPix 格式
- 检查文件是否损坏
- 查看日志获取详细错误信息

### 问题：图像序号识别错误
**解决方案**：
- 确保文件名包含连续的数字序号
- 使用标准命名格式（如 `frame_001.png`）
- 避免文件名中有多组数字

## 版本历史

### v2.0（当前版本）
- ✅ 新增图像序列 → SEQ 功能
- ✅ 新增图像序列 → 视频功能（AVI/MP4/MOV）
- ✅ 全新双向转换 GUI
- ✅ 支持 PNG/BMP/TIFF 输入
- ✅ 可配置帧率、编码器、质量

### v1.0
- SEQ → PNG/TIFF/BMP 转换
- 基础 GUI 界面

## 技术支持

如有问题或建议，请查看项目文档或联系开发者。

---

**开发者**: Claude & User
**最后更新**: 2025-12-01
