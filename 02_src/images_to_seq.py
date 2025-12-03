"""
图像序列到 SEQ 格式转换器
支持将 PNG/BMP/TIFF 图像序列转换为 Norpix StreamPix SEQ 文件
"""

import os
import struct
from PIL import Image
import numpy as np
from datetime import datetime
import argparse


class SeqWriter:
    """SEQ 文件写入器，支持 Norpix StreamPix 格式"""

    def __init__(self, output_path, width=None, height=None, bit_depth=8, frame_rate=30.0):
        """
        初始化 SEQ 写入器

        Args:
            output_path: 输出的 SEQ 文件路径
            width: 图像宽度（如果为 None，从第一张图片自动检测）
            height: 图像高度（如果为 None，从第一张图片自动检测）
            bit_depth: 位深度 (8, 16, 24)
            frame_rate: 帧率 (fps)
        """
        self.output_path = output_path
        self.width = width
        self.height = height
        self.bit_depth = bit_depth
        self.frame_rate = frame_rate
        self.frame_count = 0
        self.header_size = 8192  # SEQ 文件头固定大小
        self.file_handle = None

    def _create_header(self, first_image_path):
        """
        创建 SEQ 文件头（8192 字节）

        Args:
            first_image_path: 第一张图片的路径，用于检测图像尺寸

        Returns:
            bytes: 8192 字节的文件头数据
        """
        # 从第一张图片获取尺寸信息
        with Image.open(first_image_path) as img:
            if self.width is None or self.height is None:
                self.width, self.height = img.size
                print(f"从图像检测到尺寸: {self.width} x {self.height}")

            # 根据图像模式确定位深度
            if self.bit_depth is None:
                if img.mode == 'L':
                    self.bit_depth = 8
                elif img.mode == 'RGB':
                    self.bit_depth = 24
                elif img.mode == 'I;16':
                    self.bit_depth = 16
                else:
                    # 尝试转换
                    if img.mode == 'RGBA':
                        self.bit_depth = 24  # 转为 RGB
                    else:
                        self.bit_depth = 8   # 默认 8 位
                print(f"从图像模式 '{img.mode}' 检测到位深度: {self.bit_depth}")

        # 创建 8192 字节的空头部
        header = bytearray(self.header_size)

        # 魔数: 0xFEED (偏移 0-3)
        struct.pack_into('<I', header, 0, 0xFEED)

        # 文件名 (偏移 4-27, 24 字节)
        filename = os.path.basename(self.output_path)[:23]  # 最多 23 字节 + null
        struct.pack_into('24s', header, 4, filename.encode('ascii', errors='ignore'))

        # 版本号 (偏移 28-31) - 使用版本 5
        struct.pack_into('<I', header, 28, 5)

        # 文件头大小 (偏移 32-35)
        struct.pack_into('<I', header, 32, self.header_size)

        # 描述 (偏移 36-547, 512 字节)
        description = f"Created by SEQ Converter on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        struct.pack_into('512s', header, 36, description.encode('ascii', errors='ignore'))

        # 图像宽度 (偏移 548-551)
        struct.pack_into('<I', header, 548, self.width)

        # 图像高度 (偏移 552-555)
        struct.pack_into('<I', header, 552, self.height)

        # 位深度 - 标称 (偏移 556-559)
        struct.pack_into('<I', header, 556, self.bit_depth)

        # 位深度 - 实际 (偏移 560-563)
        struct.pack_into('<I', header, 560, self.bit_depth)

        # 计算图像大小
        bytes_per_pixel = self.bit_depth // 8
        image_size = self.width * self.height * bytes_per_pixel

        # 图像大小 (偏移 564-567)
        struct.pack_into('<I', header, 564, image_size)

        # 图像格式 (偏移 568-571)
        # 100 = 未压缩灰度, 200 = 未压缩 BGR
        image_format = 200 if self.bit_depth == 24 else 100
        struct.pack_into('<I', header, 568, image_format)

        # 分配的帧数 (偏移 572-575) - 先设为 0，稍后更新
        struct.pack_into('<I', header, 572, 0)

        # Origin (偏移 576-577) - 左上角
        struct.pack_into('<H', header, 576, 0)

        # TrueImageSize (偏移 580-583) - 每帧的总大小（包括帧头）
        # 对于简单格式，帧头可以为 0
        struct.pack_into('<I', header, 580, image_size)

        # 建议帧率 (偏移 584-591, double)
        struct.pack_into('<d', header, 584, self.frame_rate)

        # DescriptionFormat (偏移 592-595) - 0 表示无特殊格式
        struct.pack_into('<I', header, 592, 0)

        # Reference frame (偏移 596-599)
        struct.pack_into('<I', header, 596, 0)

        # Fixed size (偏移 600-603)
        struct.pack_into('<I', header, 600, image_size)

        # Flags (偏移 604-607) - 0 表示无特殊标志
        struct.pack_into('<I', header, 604, 0)

        # Bayer pattern (偏移 608-611) - 0 表示无 Bayer
        struct.pack_into('<I', header, 608, 0)

        # BayerPattern (偏移 612-615)
        struct.pack_into('<I', header, 612, 0)

        # Crop (偏移 616-623, 4 个 short)
        struct.pack_into('<HHHH', header, 616, 0, 0, 0, 0)

        # Compression format (偏移 624-627)
        struct.pack_into('<I', header, 624, 0)  # 0 = 无压缩

        # GPS 数据 (偏移 628-635)
        struct.pack_into('<II', header, 628, 0, 0)

        # UUID (偏移 636-651, 16 字节) - 全 0
        struct.pack_into('16s', header, 636, b'\x00' * 16)

        # 其余字节保持为 0

        return bytes(header)

    def write_images(self, image_paths, progress_callback=None):
        """
        将图像序列写入 SEQ 文件

        Args:
            image_paths: 图像文件路径列表（已排序）
            progress_callback: 进度回调函数 callback(current, total)

        Returns:
            bool: 是否成功
        """
        if not image_paths:
            print("错误: 没有提供图像文件")
            return False

        try:
            # 创建文件头
            print(f"正在创建 SEQ 文件头...")
            header = self._create_header(image_paths[0])

            # 打开输出文件
            with open(self.output_path, 'wb') as f:
                # 写入文件头
                f.write(header)

                # 写入每一帧
                total_frames = len(image_paths)
                print(f"开始写入 {total_frames} 帧图像数据...")

                for i, img_path in enumerate(image_paths):
                    try:
                        # 读取图像
                        with Image.open(img_path) as img:
                            # 确保图像尺寸正确
                            if img.size != (self.width, self.height):
                                print(f"警告: 图像 {img_path} 尺寸 {img.size} 与预期 ({self.width}, {self.height}) 不符，将调整大小")
                                img = img.resize((self.width, self.height), Image.LANCZOS)

                            # 根据位深度转换图像
                            if self.bit_depth == 8:
                                # 灰度图
                                if img.mode != 'L':
                                    img = img.convert('L')
                                img_array = np.array(img, dtype=np.uint8)
                            elif self.bit_depth == 16:
                                # 16 位灰度图
                                if img.mode != 'I;16':
                                    img = img.convert('L')
                                    img_array = np.array(img, dtype=np.uint8)
                                    img_array = img_array.astype(np.uint16) * 256
                                else:
                                    img_array = np.array(img, dtype=np.uint16)
                            elif self.bit_depth == 24:
                                # RGB 彩色图 -> BGR (SEQ 使用 BGR 顺序)
                                if img.mode == 'RGBA':
                                    img = img.convert('RGB')
                                elif img.mode != 'RGB':
                                    img = img.convert('RGB')
                                img_array = np.array(img, dtype=np.uint8)
                                # 转换 RGB -> BGR
                                img_array = img_array[:, :, ::-1]
                            else:
                                print(f"错误: 不支持的位深度 {self.bit_depth}")
                                return False

                            # 写入图像数据（注意：这里不写入帧头，因为 TrueImageSize = ImageSize）
                            img_bytes = img_array.tobytes()
                            f.write(img_bytes)

                            self.frame_count += 1

                            # 进度回调
                            if progress_callback:
                                progress_callback(i + 1, total_frames)

                            if (i + 1) % 100 == 0 or (i + 1) == total_frames:
                                print(f"已写入 {i + 1}/{total_frames} 帧")

                    except Exception as e:
                        print(f"错误: 处理图像 {img_path} 时出错: {e}")
                        return False

                # 更新文件头中的帧数
                f.seek(572)  # 偏移 572: 分配的帧数
                f.write(struct.pack('<I', self.frame_count))

            print(f"\n成功创建 SEQ 文件: {self.output_path}")
            print(f"总帧数: {self.frame_count}")
            print(f"分辨率: {self.width} x {self.height}")
            print(f"位深度: {self.bit_depth} 位")
            print(f"帧率: {self.frame_rate} fps")

            return True

        except Exception as e:
            print(f"错误: 写入 SEQ 文件时出错: {e}")
            return False


def get_sequence_number(filename):
    """
    从文件名中提取序列号
    支持多种命名格式
    """
    import re

    # 尝试匹配常见的序列号格式
    patterns = [
        r'_(\d+)\.\w+$',           # name_001.png
        r'\.(\d+)\.\w+$',           # name.001.png
        r'(\d+)\.\w+$',             # 001.png
        r'frame_?(\d+)',            # frame001 or frame_001
        r'img_?(\d+)',              # img001 or img_001
    ]

    for pattern in patterns:
        match = re.search(pattern, filename, re.IGNORECASE)
        if match:
            return int(match.group(1))

    # 如果找不到，返回一个很大的数
    return float('inf')


def images_to_seq(input_directory, output_seq_file, image_format='png',
                  width=None, height=None, bit_depth=8, frame_rate=30.0,
                  start_frame=None, end_frame=None):
    """
    将图像序列转换为 SEQ 文件

    Args:
        input_directory: 输入图像目录
        output_seq_file: 输出 SEQ 文件路径
        image_format: 图像格式 ('png', 'bmp', 'tiff')
        width: 图像宽度（None 为自动检测）
        height: 图像高度（None 为自动检测）
        bit_depth: 位深度 (8, 16, 24)
        frame_rate: 帧率
        start_frame: 起始帧号（None 为从头开始）
        end_frame: 结束帧号（None 为到末尾）

    Returns:
        bool: 是否成功
    """
    if not os.path.isdir(input_directory):
        print(f"错误: 输入目录 '{input_directory}' 不存在")
        return False

    # 获取所有图像文件
    extensions = {
        'png': ['.png'],
        'bmp': ['.bmp'],
        'tiff': ['.tiff', '.tif'],
        'all': ['.png', '.bmp', '.tiff', '.tif', '.jpg', '.jpeg']
    }

    valid_exts = extensions.get(image_format.lower(), extensions['all'])
    image_files = [f for f in os.listdir(input_directory)
                   if os.path.splitext(f)[1].lower() in valid_exts]

    if not image_files:
        print(f"错误: 在目录 '{input_directory}' 中未找到图像文件")
        return False

    # 排序
    image_files.sort(key=get_sequence_number)

    # 应用帧范围
    if start_frame is not None or end_frame is not None:
        start_idx = (start_frame - 1) if start_frame else 0
        end_idx = end_frame if end_frame else len(image_files)
        image_files = image_files[start_idx:end_idx]

    print(f"找到 {len(image_files)} 个图像文件")

    # 生成完整路径
    image_paths = [os.path.join(input_directory, f) for f in image_files]

    # 创建 SeqWriter 并写入
    writer = SeqWriter(output_seq_file, width, height, bit_depth, frame_rate)

    def progress_callback(current, total):
        percent = (current / total) * 100
        print(f"\r进度: {current}/{total} ({percent:.1f}%)", end='', flush=True)

    success = writer.write_images(image_paths, progress_callback)
    print()  # 换行

    return success


def main():
    """命令行入口"""
    parser = argparse.ArgumentParser(description='将图像序列转换为 SEQ 文件')
    parser.add_argument('input_dir', help='输入图像目录')
    parser.add_argument('-o', '--output', required=True, help='输出 SEQ 文件路径')
    parser.add_argument('-f', '--format', default='all',
                       choices=['png', 'bmp', 'tiff', 'all'],
                       help='图像格式 (默认: all)')
    parser.add_argument('-w', '--width', type=int, help='图像宽度（自动检测）')
    parser.add_argument('-H', '--height', type=int, help='图像高度（自动检测）')
    parser.add_argument('-b', '--bitdepth', type=int, default=8,
                       choices=[8, 16, 24],
                       help='位深度 (默认: 8)')
    parser.add_argument('-r', '--framerate', type=float, default=30.0,
                       help='帧率 (默认: 30.0)')
    parser.add_argument('-s', '--start', type=int, help='起始帧号')
    parser.add_argument('-e', '--end', type=int, help='结束帧号')

    args = parser.parse_args()

    success = images_to_seq(
        args.input_dir,
        args.output,
        args.format,
        args.width,
        args.height,
        args.bitdepth,
        args.framerate,
        args.start,
        args.end
    )

    return 0 if success else 1


if __name__ == "__main__":
    exit(main())
