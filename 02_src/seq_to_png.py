import os
import struct
import numpy as np
from PIL import Image
import argparse


class SeqReader:
    """
    读取 .seq 文件并将帧转换为 PNG 图像

    SEQ 文件格式通常由相机厂商定义，常见的格式包含:
    - 文件头信息（宽度、高度、帧数等）
    - 每帧的图像数据
    """

    def __init__(self, seq_file_path):
        self.seq_file_path = seq_file_path
        self.width = 2560
        self.height = 1916
        self.frame_count = 0
        self.bit_depth = 8
        self.header_size = 8192  # 默认文件头部大小
        self.frame_header_size = 0  # 每帧前的头部大小
        self.true_image_size = 0  # 从文件头读取的实际图像大小

    def read_header(self):
        """
        读取 SEQ 文件头信息 - Norpix Sequence 格式

        Norpix Sequence 格式结构:
        - 文件头: 8192 字节 (固定)
        - 每帧结构: 帧头(时间戳等) + 图像数据
        """
        print("jog read_header")
        with open(self.seq_file_path, 'rb') as f:
            # 读取足够的头部数据
            header = f.read(8192)

            try:
                # 检查魔数 (0xFEED)
                magic = struct.unpack('<I', header[0:4])[0]
                if magic == 0xFEED:
                    print("检测到 Norpix StreamPix 格式")

                    # 解析头部信息
                    name = header[4:28].decode('ascii', errors='ignore').strip('\x00')
                    version = struct.unpack('<I', header[28:32])[0]
                    header_size = struct.unpack('<I', header[32:36])[0]
                    description = header[36:548].decode('ascii', errors='ignore').strip('\x00')

                    self.width = struct.unpack('<I', header[548:552])[0]
                    self.height = struct.unpack('<I', header[552:556])[0]
                    image_bit_depth = struct.unpack('<I', header[556:560])[0]
                    image_bit_depth_real = struct.unpack('<I', header[560:564])[0]
                    image_size_bytes = struct.unpack('<I', header[564:568])[0]
                    image_format = struct.unpack('<I', header[568:572])[0]
                    allocated_frames = struct.unpack('<I', header[572:576])[0]
                    origin = struct.unpack('<I', header[576:580])[0]
                    true_image_size = struct.unpack('<I', header[580:584])[0]
                    suggested_frame_rate = struct.unpack('<d', header[584:592])[0]  # double

                    # 偏移量信息
                    desc_format = struct.unpack('<I', header[592:596])[0]
                    reference_frame = struct.unpack('<I', header[596:600])[0]
                    fixed_size = struct.unpack('<I', header[600:604])[0]
                    flags = struct.unpack('<I', header[604:608])[0]

                    # 关键: 读取 Bayer 图像格式 (608-612)
                    bayer = struct.unpack('<I', header[608:612])[0]

                    # 时间偏移
                    time_offset_low = struct.unpack('<I', header[612:616])[0]
                    time_offset_high = struct.unpack('<I', header[616:620])[0]

                    # 扩展头部大小 (620-624)
                    extended_header_size = struct.unpack('<I', header[620:624])[0]

                    # 压缩格式 (624-628)
                    compression_format = struct.unpack('<I', header[624:628])[0]

                    # 参考时间戳
                    reference_time_s = struct.unpack('<I', header[628:632])[0]
                    reference_time_ms = struct.unpack('<H', header[632:634])[0]
                    reference_time_us = struct.unpack('<H', header[634:636])[0]

                    # 设置参数
                    self.header_size = header_size  # 通常是 8192
                    self.bit_depth = image_bit_depth_real
                    self.true_image_size = true_image_size

                    # 计算帧数
                    file_size = os.path.getsize(self.seq_file_path)

                    # Norpix格式: 每帧前面有帧头信息
                    # TrueImageSize 和 实际图像大小的差值就是帧头大小
                    bytes_per_pixel = image_bit_depth_real // 8
                    if bytes_per_pixel == 0:
                        bytes_per_pixel = 1
                    expected_image_size = self.width * self.height * bytes_per_pixel

                    # 帧头大小 = TrueImageSize - 实际图像大小
                    self.frame_header_size = true_image_size - expected_image_size

                    # 每帧总大小 = TrueImageSize
                    total_frame_size = true_image_size
                    self.frame_count = (file_size - self.header_size) // total_frame_size

                    print(f"Norpix 文件信息:")
                    print(f"  版本: {version}")
                    print(f"  文件头大小: {self.header_size} 字节")
                    print(f"  图像尺寸: {self.width} x {self.height}")
                    print(f"  位深度: {image_bit_depth_real} bit")
                    print(f"  图像格式代码: {image_format}")
                    print(f"  真实图像大小: {true_image_size} 字节")
                    print(f"  扩展头部大小: {extended_header_size} 字节")
                    print(f"  每帧头部大小: {self.frame_header_size} 字节")
                    print(f"  压缩格式: {compression_format}")
                    print(f"  建议帧率: {suggested_frame_rate} fps")
                    print(f"  计算帧数: {self.frame_count}")

                    return True

            except Exception as e:
                print(f"解析 Norpix 格式失败: {e}")
                import traceback
                traceback.print_exc()

            # 如果解析失败，尝试手动指定参数
            print("无法自动识别 SEQ 格式，请手动指定参数")
            return False

    def extract_frames(self, output_dir, start_frame=0, end_frame=None, prefix="frame", format="PNG"):
        """
        提取帧并保存为图像文件

        Args:
            output_dir: 输出目录
            start_frame: 起始帧号 (从0开始)
            end_frame: 结束帧号 (不包含)，None表示到最后一帧
            prefix: 输出文件名前缀
            format: 图像格式 (PNG, TIFF, BMP)
        """
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
            print(f"创建输出目录: {output_dir}")

        if end_frame is None:
            end_frame = self.frame_count

        # 确保帧号范围有效
        start_frame = max(0, start_frame)
        end_frame = min(end_frame, self.frame_count)

        if start_frame >= end_frame:
            print("错误: 起始帧号必须小于结束帧号")
            return

        # 格式化图像格式
        format = format.upper()
        if format not in ["PNG", "TIFF", "BMP"]:
            print(f"错误: 不支持的图像格式 '{format}'，仅支持 PNG, TIFF, BMP")
            return

        # 获取文件扩展名
        ext = format.lower()
        if format == "TIFF":
            ext = "tif"

        print(f"正在提取帧 {start_frame} 到 {end_frame-1}，格式: {format}...")

        # 计算每帧的字节数
        bytes_per_pixel = self.bit_depth // 8
        if self.bit_depth % 8 != 0:
            bytes_per_pixel += 1

        # 计算实际图像数据大小
        expected_image_size = self.width * self.height * bytes_per_pixel

        # 如果有真实图像大小,使用它;否则计算
        if self.true_image_size > 0:
            frame_size = self.true_image_size
        else:
            frame_size = expected_image_size

        with open(self.seq_file_path, 'rb') as f:
            for frame_num in range(start_frame, end_frame):
                # 跳转到指定帧的位置 (文件头 + 帧号 * TrueImageSize)
                offset = self.header_size + frame_num * frame_size
                f.seek(offset)

                # 读取整个帧数据
                frame_data = f.read(frame_size)

                if len(frame_data) < frame_size:
                    print(f"警告: 帧 {frame_num} 数据不完整，跳过 (读取 {len(frame_data)}/{frame_size} 字节)")
                    continue

                # 跳过帧头部分（如果存在）
                if self.frame_header_size > 0:
                    frame_data = frame_data[self.frame_header_size:]

                # 根据位深度解析数据
                if self.bit_depth == 8:
                    # 8位灰度图
                    img_array = np.frombuffer(frame_data, dtype=np.uint8)

                    # 检查是否有行填充字节
                    expected_pixels = self.width * self.height
                    actual_bytes = len(img_array)
                    print("jog actual_bytes")
                    if actual_bytes >= expected_pixels:
                        # 计算行步长（stride）- 每行实际占用的字节数
                        bytes_per_row = actual_bytes // self.height

                        if bytes_per_row > self.width and frame_num == start_frame:
                            print(f"检测到行填充: 每行 {bytes_per_row} 字节 (图像宽度: {self.width}, 填充: {bytes_per_row - self.width} 字节)")

                        # 使用步长重新整形数据，然后裁剪到实际宽度
                        img_array = img_array[:self.height * bytes_per_row].reshape((self.height, bytes_per_row))
                        img_array = img_array[:, :self.width]  # 只取前 width 列，丢弃填充字节
                    else:
                        print(f"警告: 数据不足 ({actual_bytes} < {expected_pixels})")
                        img_array = img_array.reshape((self.height, self.width))

                    img = Image.fromarray(img_array, mode='L')

                elif self.bit_depth == 16:
                    # 16位灰度图
                    img_array = np.frombuffer(frame_data, dtype=np.uint16)

                    # 检查是否有行填充
                    expected_pixels = self.width * self.height
                    actual_pixels = len(img_array)

                    if actual_pixels >= expected_pixels:
                        # 计算行步长（每行实际像素数）
                        pixels_per_row = actual_pixels // self.height

                        if pixels_per_row > self.width and frame_num == start_frame:
                            print(f"检测到行填充: 每行 {pixels_per_row} 像素 (图像宽度: {self.width}, 填充: {pixels_per_row - self.width} 像素)")

                        # 使用步长重新整形数据，然后裁剪到实际宽度
                        img_array = img_array[:self.height * pixels_per_row].reshape((self.height, pixels_per_row))
                        img_array = img_array[:, :self.width]  # 只取前 width 列
                    else:
                        print(f"警告: 数据不足 ({actual_pixels} < {expected_pixels})")
                        img_array = img_array.reshape((self.height, self.width))

                    # 转换为8位用于显示
                    img_array_8bit = (img_array / 256).astype(np.uint8)
                    img = Image.fromarray(img_array_8bit, mode='L')

                elif self.bit_depth == 24:
                    # 24位彩色图 (RGB)
                    img_array = np.frombuffer(frame_data, dtype=np.uint8)

                    # 检查是否有行填充
                    expected_bytes = self.width * self.height * 3
                    actual_bytes = len(img_array)

                    if actual_bytes >= expected_bytes:
                        # 计算行步长
                        bytes_per_row = actual_bytes // self.height

                        if bytes_per_row > self.width * 3 and frame_num == start_frame:
                            print(f"检测到行填充: 每行 {bytes_per_row} 字节 (图像宽度: {self.width * 3} 字节, 填充: {bytes_per_row - self.width * 3} 字节)")

                        # 使用步长重新整形数据，然后裁剪到实际宽度
                        img_array = img_array[:self.height * bytes_per_row].reshape((self.height, bytes_per_row))
                        img_array = img_array[:, :self.width * 3]  # 只取前 width*3 列
                        img_array = img_array.reshape((self.height, self.width, 3))
                    else:
                        print(f"警告: 数据不足 ({actual_bytes} < {expected_bytes})")
                        img_array = img_array.reshape((self.height, self.width, 3))

                    img = Image.fromarray(img_array, mode='RGB')

                else:
                    print(f"不支持的位深度: {self.bit_depth}")
                    return

                # 保存为指定格式
                output_filename = f"{prefix}_{frame_num:06d}.{ext}"
                output_path = os.path.join(output_dir, output_filename)
                img.save(output_path, format=format)

                if (frame_num - start_frame + 1) % 10 == 0:
                    print(f"已处理 {frame_num - start_frame + 1}/{end_frame - start_frame} 帧")

        print(f"完成! 共提取 {end_frame - start_frame} 帧到目录: {output_dir}")


def seq_to_png(seq_file, output_dir=None, start_frame=0, end_frame=None,
               prefix='frame', width=None, height=None, bitdepth=8, format='PNG'):
    """
    将 SEQ 文件转换为图像序列

    Args:
        seq_file: SEQ 文件路径
        output_dir: 输出目录 (默认: seq文件同名目录)
        start_frame: 起始帧号 (默认: 0)
        end_frame: 结束帧号 (默认: None, 表示全部)
        prefix: 输出文件名前缀 (默认: 'frame')
        width: 手动指定图像宽度 (默认: None, 自动识别)
        height: 手动指定图像高度 (默认: None, 自动识别)
        bitdepth: 手动指定位深度 (默认: 8)
        format: 图像格式 (默认: 'PNG', 可选: 'TIF', 'BMP')

    Returns:
        bool: 成功返回 True, 失败返回 False

    Example:
        # 最简单的调用
        seq_to_png('input.seq')

        # 指定输出目录和格式
        seq_to_png('input.seq', output_dir='output_frames', format='TIF')

        # 只提取部分帧
        seq_to_png('input.seq', start_frame=0, end_frame=100)

        # 手动指定图像参数
        seq_to_png('input.seq', width=640, height=480, bitdepth=8, format='BMP')
    """
    # 检查输入文件是否存在
    if not os.path.exists(seq_file):
        print(f"错误: 文件 '{seq_file}' 不存在")
        return False

    # 确定输出目录
    if output_dir is None:
        seq_basename = os.path.splitext(os.path.basename(seq_file))[0]
        output_dir = os.path.join(os.path.dirname(seq_file), f"{seq_basename}_frames")

    # 创建 SeqReader 对象
    reader = SeqReader(seq_file)

    # 尝试读取文件头
    success = reader.read_header()

    # 如果自动读取失败，使用手动参数
    if not success:
        if width is None or height is None:
            print("错误: 无法自动识别 SEQ 格式，请手动指定 width 和 height 参数")
            return False

        print(f"使用手动参数: {width}x{height}, {bitdepth} bit")
        reader.width = 1916
        reader.height = 2560
        reader.bit_depth = bitdepth

        # 计算帧数
        file_size = os.path.getsize(seq_file)
        bytes_per_pixel = bitdepth // 8
        frame_size = width * height * bytes_per_pixel
        reader.frame_count = (file_size - reader.header_size) // frame_size
        print(f"估算帧数: {reader.frame_count}")

    # 提取帧
    reader.extract_frames(
        output_dir=output_dir,
        start_frame=start_frame,
        end_frame=end_frame,
        prefix=prefix,
        format=format
    )

    return True


def main():
    """
    主函数：解析命令行参数并执行转换
    """
    parser = argparse.ArgumentParser(description='将 SEQ 文件转换为图像序列')
    parser.add_argument('seq_file', help='输入的 SEQ 文件路径')
    parser.add_argument('-o', '--output', default=None, help='输出目录 (默认: seq文件同名目录)')
    parser.add_argument('-s', '--start', type=int, default=0, help='起始帧号 (默认: 0)')
    parser.add_argument('-e', '--end', type=int, default=None, help='结束帧号 (默认: 全部)')
    parser.add_argument('-p', '--prefix', default='frame', help='输出文件名前缀 (默认: frame)')
    parser.add_argument('-f', '--format', default='PNG', choices=['PNG', 'TIFF', 'BMP'], help='输出图像格式 (默认: PNG)')
    parser.add_argument('-w', '--width', type=int, default=None, help='手动指定图像宽度')
    parser.add_argument('-H', '--height', type=int, default=None, help='手动指定图像高度')
    parser.add_argument('-b', '--bitdepth', type=int, default=8, choices=[8, 16, 24], help='手动指定位深度 (默认: 8)')

    args = parser.parse_args()

    # 调用核心函数
    seq_to_png(
        seq_file=args.seq_file,
        output_dir=args.output,
        start_frame=args.start,
        end_frame=args.end,
        prefix=args.prefix,
        width=args.width,
        height=args.height,
        bitdepth=args.bitdepth,
        format=args.format
    )


if __name__ == "__main__":
    # 如果直接运行脚本，使用示例路径
    import sys

    if len(sys.argv) == 1:
        # 没有命令行参数，使用默认示例
        print("=" * 60)
        print("SEQ 转图像序列脚本 - 示例模式")
        print("=" * 60)
        print("\n使用方法:")
        print("  python seq_to_png.py <seq文件路径> [选项]")
        print("\n选项:")
        print("  -o, --output <dir>      输出目录")
        print("  -s, --start <n>         起始帧号")
        print("  -e, --end <n>           结束帧号")
        print("  -p, --prefix <str>      输出文件名前缀")
        print("  -f, --format <fmt>      输出格式 (PNG|TIFF|BMP, 默认: PNG)")
        print("  -w, --width <n>         手动指定图像宽度")
        print("  -H, --height <n>        手动指定图像高度")
        print("  -b, --bitdepth <8|16|24> 手动指定位深度")
        print("\n示例:")
        print("  python seq_to_png.py input.seq")
        print("  python seq_to_png.py input.seq -o output_frames -s 0 -e 100")
        print("  python seq_to_png.py input.seq -f TIFF")
        print("  python seq_to_png.py input.seq -f BMP -w 640 -H 480 -b 8")
        print("\n" + "=" * 60)

        # 使用项目中的示例文件
        example_seq = r"G:\4th\CAM1_droplet_images_2025-11-04_15_51_20.seq"
        if os.path.exists(example_seq):
            print(f"\n找到示例文件: {example_seq}")
            response = input("是否处理这个文件? (y/n): ")
            if response.lower() == 'y':
                sys.argv = ['seq_to_png.py', example_seq]
                main()
        else:
            print(f"\n示例文件不存在: {example_seq}")
    else:
        main()
