"""
图像序列到视频转换器
支持将 PNG/BMP/TIFF 图像序列转换为 AVI/MP4/MOV 视频文件
"""

import os
import re
from PIL import Image
import argparse


def get_sequence_number(filename):
    """
    从文件名中提取数字序列号
    支持多种命名格式

    Examples:
        "frame_001.png" -> 1
        "img_00010.bmp" -> 10
        "continuous_pic_1000_00_0_00_20251014154820511_1.bmp" -> 1
    """
    # 尝试匹配文件名末尾的数字（最常见的格式）
    match = re.search(r'_(\d+)\.\w+$', filename, re.IGNORECASE)
    if match:
        return int(match.group(1))

    # 尝试匹配 .数字.扩展名 格式
    match = re.search(r'\.(\d+)\.\w+$', filename, re.IGNORECASE)
    if match:
        return int(match.group(1))

    # 尝试匹配纯数字文件名
    match = re.search(r'(\d+)\.\w+$', filename, re.IGNORECASE)
    if match:
        return int(match.group(1))

    # 如果都匹配不到，返回一个很大的数，让它排在后面
    return float('inf')


def convert_images_to_video(input_directory, output_video_file,
                           image_format='all', frame_rate=30,
                           video_codec='auto', quality='high',
                           start_frame=None, end_frame=None,
                           temp_prefix="temp_frame_"):
    """
    将图像序列转换为视频文件

    Args:
        input_directory: 包含图像的目录路径
        output_video_file: 输出视频文件路径
        image_format: 输入图像格式 ('png', 'bmp', 'tiff', 'all')
        frame_rate: 视频帧率 (每秒帧数)
        video_codec: 视频编码器
            - 'auto': 根据输出格式自动选择
            - 'libxvid': AVI (MPEG-4)
            - 'libx264': MP4/MOV (H.264)
            - 'libx265': MP4/MOV (H.265)
        quality: 视频质量 ('low', 'medium', 'high', 'best')
        start_frame: 起始帧号 (None 为从头开始)
        end_frame: 结束帧号 (None 为到末尾)
        temp_prefix: 临时文件的前缀

    Returns:
        bool: 是否成功
    """
    try:
        import ffmpeg
    except ImportError:
        print("错误: 未安装 ffmpeg-python 库")
        print("请运行: pip install ffmpeg-python")
        return False

    if not os.path.isdir(input_directory):
        print(f"错误: 输入目录 '{input_directory}' 不存在")
        return False

    # 确定要处理的图像格式
    extensions = {
        'png': ['.png'],
        'bmp': ['.bmp'],
        'tiff': ['.tiff', '.tif'],
        'all': ['.png', '.bmp', '.tiff', '.tif', '.jpg', '.jpeg']
    }

    valid_exts = extensions.get(image_format.lower(), extensions['all'])

    # 获取所有图像文件
    image_files = [f for f in os.listdir(input_directory)
                   if os.path.splitext(f)[1].lower() in valid_exts]

    if not image_files:
        print(f"错误: 在目录 '{input_directory}' 中未找到图像文件")
        return False

    # 根据文件名中的数字进行排序
    image_files.sort(key=get_sequence_number)

    # 应用帧范围过滤
    if start_frame is not None or end_frame is not None:
        start_idx = (start_frame - 1) if start_frame else 0
        end_idx = end_frame if end_frame else len(image_files)
        image_files = image_files[start_idx:end_idx]

    print(f"找到 {len(image_files)} 个图像文件")

    if not image_files:
        print("错误: 应用帧范围过滤后没有图像文件")
        return False

    # 验证第一张图片以获取尺寸
    first_image_path = os.path.join(input_directory, image_files[0])
    try:
        with Image.open(first_image_path) as img:
            width, height = img.size
            print(f"图像尺寸: {width} x {height}")
    except Exception as e:
        print(f"错误: 无法读取图像 '{first_image_path}': {e}")
        return False

    # 重命名文件为统一序列模式（FFmpeg 要求）
    temp_files = []
    max_digits = len(str(len(image_files)))

    print(f"正在准备临时文件...")
    for i, filename in enumerate(image_files):
        # 获取文件扩展名
        ext = os.path.splitext(filename)[1]

        # 生成新的文件名，例如 temp_frame_00001.png
        new_filename = f"{temp_prefix}{i+1:0{max_digits}d}{ext}"
        original_path = os.path.join(input_directory, filename)
        new_path = os.path.join(input_directory, new_filename)

        try:
            os.rename(original_path, new_path)
            temp_files.append(new_filename)
        except OSError as e:
            print(f"错误: 重命名文件 '{filename}' 失败: {e}")
            # 恢复已重命名的文件
            _cleanup_temp_files(input_directory, temp_files, image_files[:i])
            return False

    # 获取临时文件的扩展名（应该都相同）
    temp_ext = os.path.splitext(temp_files[0])[1] if temp_files else '.png'

    # 构建 FFmpeg 输入模式
    input_pattern = os.path.join(input_directory, f"{temp_prefix}%0{max_digits}d{temp_ext}")
    print(f"FFmpeg 输入模式: {input_pattern}")

    # 确定视频编码器
    if video_codec == 'auto':
        output_ext = os.path.splitext(output_video_file)[1].lower()
        if output_ext == '.avi':
            video_codec = 'libxvid'
        elif output_ext in ['.mp4', '.mov']:
            video_codec = 'libx264'
        else:
            video_codec = 'libx264'  # 默认
            print(f"警告: 未识别的输出格式 '{output_ext}'，使用默认编码器 libx264")

    print(f"使用编码器: {video_codec}")

    # 根据质量设置确定 CRF 值（仅对 libx264/libx265 有效）
    crf_values = {
        'low': 28,
        'medium': 23,
        'high': 18,
        'best': 15
    }
    crf = crf_values.get(quality, 23)

    try:
        print(f"开始转换为视频 (帧率: {frame_rate} fps, 质量: {quality})...")

        # 构建 FFmpeg 命令
        stream = ffmpeg.input(input_pattern, framerate=frame_rate)

        # 根据编码器选择输出参数
        if video_codec == 'libxvid':
            # MPEG-4 (XVID) for AVI
            stream = ffmpeg.output(stream, output_video_file,
                                 vcodec='libxvid',
                                 pix_fmt='yuv420p',
                                 qscale=5)  # qscale: 1-31, lower = better
        elif video_codec in ['libx264', 'libx265']:
            # H.264 or H.265 for MP4/MOV
            stream = ffmpeg.output(stream, output_video_file,
                                 vcodec=video_codec,
                                 pix_fmt='yuv420p',
                                 crf=crf,
                                 preset='medium')
        else:
            # 通用编码器
            stream = ffmpeg.output(stream, output_video_file,
                                 vcodec=video_codec,
                                 pix_fmt='yuv420p')

        # 执行转换
        ffmpeg.run(stream, overwrite_output=True, capture_stdout=True, capture_stderr=True)

        print(f"成功创建视频文件: {output_video_file}")
        print(f"总帧数: {len(image_files)}")
        print(f"分辨率: {width} x {height}")
        print(f"帧率: {frame_rate} fps")
        success = True

    except ffmpeg.Error as e:
        print(f"FFmpeg 转换错误:")
        stderr = e.stderr.decode('utf8', errors='ignore') if e.stderr else ''
        stdout = e.stdout.decode('utf8', errors='ignore') if e.stdout else ''
        print(f"  STDERR: {stderr}")
        if stdout:
            print(f"  STDOUT: {stdout}")
        success = False

    except FileNotFoundError:
        print(f"错误: FFmpeg 可执行文件未找到")
        print(f"请确保 FFmpeg 已正确安装并添加到系统 PATH")
        success = False

    except Exception as e:
        print(f"发生未知错误: {e}")
        success = False

    finally:
        # 清理临时文件
        print("正在清理临时文件...")
        _cleanup_temp_files(input_directory, temp_files, image_files)
        print("清理完成")

    return success


def _cleanup_temp_files(input_directory, temp_files, original_files):
    """
    清理临时文件，恢复原始文件名

    Args:
        input_directory: 目录路径
        temp_files: 临时文件名列表
        original_files: 原始文件名列表
    """
    for temp_filename, orig_filename in zip(temp_files, original_files):
        temp_path = os.path.join(input_directory, temp_filename)
        orig_path = os.path.join(input_directory, orig_filename)

        if os.path.exists(temp_path):
            try:
                os.rename(temp_path, orig_path)
            except OSError as e:
                print(f"警告: 恢复文件 '{temp_filename}' -> '{orig_filename}' 失败: {e}")


def main():
    """命令行入口"""
    parser = argparse.ArgumentParser(
        description='将图像序列转换为视频文件',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
示例:
  %(prog)s input_dir -o output.avi
  %(prog)s input_dir -o output.mp4 -f png -r 60
  %(prog)s input_dir -o output.mov -c libx264 -q best
        '''
    )

    parser.add_argument('input_dir', help='输入图像目录')
    parser.add_argument('-o', '--output', required=True,
                       help='输出视频文件路径')
    parser.add_argument('-f', '--format', default='all',
                       choices=['png', 'bmp', 'tiff', 'all'],
                       help='输入图像格式 (默认: all)')
    parser.add_argument('-r', '--framerate', type=float, default=30.0,
                       help='视频帧率 (默认: 30)')
    parser.add_argument('-c', '--codec', default='auto',
                       choices=['auto', 'libxvid', 'libx264', 'libx265'],
                       help='视频编码器 (默认: auto)')
    parser.add_argument('-q', '--quality', default='high',
                       choices=['low', 'medium', 'high', 'best'],
                       help='视频质量 (默认: high)')
    parser.add_argument('-s', '--start', type=int,
                       help='起始帧号')
    parser.add_argument('-e', '--end', type=int,
                       help='结束帧号')

    args = parser.parse_args()

    success = convert_images_to_video(
        args.input_dir,
        args.output,
        args.format,
        args.framerate,
        args.codec,
        args.quality,
        args.start,
        args.end
    )

    return 0 if success else 1


if __name__ == "__main__":
    exit(main())
