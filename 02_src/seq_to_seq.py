"""
SEQ 文件 ROI 裁剪工具
支持根据 ROI 参数裁剪 SEQ 文件并生成新的 SEQ 文件
"""

import os
import struct
import numpy as np
from PIL import Image
from seq_to_png import SeqReader


class SeqCropper:
    """SEQ 文件 ROI 裁剪器"""

    def __init__(self, seq_file_path):
        """
        初始化裁剪器

        Args:
            seq_file_path: 输入 SEQ 文件路径
        """
        self.seq_file_path = seq_file_path
        self.reader = SeqReader(seq_file_path)
        self.header_loaded = False

    def _calculate_true_image_size(self, image_size_bytes):
        """
        计算 TrueImageSize，按照 NorPix C++ 实现的逻辑
        TrueImageSize = ImageSizeBytes + 8 字节时间戳，然后对齐到 8192 的倍数

        Args:
            image_size_bytes: 原始图像数据大小

        Returns:
            int: 对齐后的 TrueImageSize
        """
        # 添加 8 字节时间戳
        size_with_timestamp = image_size_bytes + 8

        # 对齐到 8192 的倍数
        alignment = 8192
        if size_with_timestamp % alignment == 0:
            return size_with_timestamp
        else:
            return ((size_with_timestamp // alignment) + 1) * alignment

    def load_header(self):
        """加载 SEQ 文件头信息"""
        if not self.header_loaded:
            success = self.reader.read_header()
            if success:
                self.header_loaded = True
            return success
        return True

    def get_frame_image(self, frame_num):
        """
        读取单帧图像并返回 PIL Image 对象

        Args:
            frame_num: 帧号 (从0开始)

        Returns:
            PIL Image 对象，失败返回 None
        """
        if not self.header_loaded:
            if not self.load_header():
                return None

        if frame_num < 0 or frame_num >= self.reader.frame_count:
            print(f"错误: 帧号 {frame_num} 超出范围 (0-{self.reader.frame_count-1})")
            return None

        # 计算每帧的字节数
        bytes_per_pixel = self.reader.bit_depth // 8
        if self.reader.bit_depth % 8 != 0:
            bytes_per_pixel += 1

        expected_image_size = self.reader.width * self.reader.height * bytes_per_pixel
        frame_size = self.reader.true_image_size if self.reader.true_image_size > 0 else expected_image_size

        try:
            with open(self.seq_file_path, 'rb') as f:
                # 跳转到指定帧
                offset = self.reader.header_size + frame_num * frame_size
                f.seek(offset)

                # 读取帧数据
                frame_data = f.read(frame_size)

                if len(frame_data) < frame_size:
                    print(f"警告: 帧 {frame_num} 数据不完整")
                    return None

                # 跳过帧头
                if self.reader.frame_header_size > 0:
                    frame_data = frame_data[self.reader.frame_header_size:]

                # 解析图像数据
                if self.reader.bit_depth == 8:
                    img_array = np.frombuffer(frame_data, dtype=np.uint8)
                    expected_pixels = self.reader.width * self.reader.height
                    actual_bytes = len(img_array)

                    if actual_bytes >= expected_pixels:
                        bytes_per_row = actual_bytes // self.reader.height
                        img_array = img_array[:self.reader.height * bytes_per_row].reshape((self.reader.height, bytes_per_row))
                        img_array = img_array[:, :self.reader.width]
                    else:
                        img_array = img_array.reshape((self.reader.height, self.reader.width))

                    img = Image.fromarray(img_array, mode='L')

                elif self.reader.bit_depth == 16:
                    img_array = np.frombuffer(frame_data, dtype=np.uint16)
                    expected_pixels = self.reader.width * self.reader.height
                    actual_pixels = len(img_array)

                    if actual_pixels >= expected_pixels:
                        pixels_per_row = actual_pixels // self.reader.height
                        img_array = img_array[:self.reader.height * pixels_per_row].reshape((self.reader.height, pixels_per_row))
                        img_array = img_array[:, :self.reader.width]
                    else:
                        img_array = img_array.reshape((self.reader.height, self.reader.width))

                    img_array_8bit = (img_array / 256).astype(np.uint8)
                    img = Image.fromarray(img_array_8bit, mode='L')

                elif self.reader.bit_depth == 24:
                    img_array = np.frombuffer(frame_data, dtype=np.uint8)
                    expected_bytes = self.reader.width * self.reader.height * 3
                    actual_bytes = len(img_array)

                    if actual_bytes >= expected_bytes:
                        bytes_per_row = actual_bytes // self.reader.height
                        img_array = img_array[:self.reader.height * bytes_per_row].reshape((self.reader.height, bytes_per_row))
                        img_array = img_array[:, :self.reader.width * 3]
                        img_array = img_array.reshape((self.reader.height, self.reader.width, 3))
                    else:
                        img_array = img_array.reshape((self.reader.height, self.reader.width, 3))

                    img = Image.fromarray(img_array, mode='RGB')

                else:
                    print(f"不支持的位深度: {self.reader.bit_depth}")
                    return None

                return img

        except Exception as e:
            print(f"读取帧失败: {e}")
            import traceback
            traceback.print_exc()
            return None

    def crop_to_new_seq(self, output_seq_path, roi_center_x, roi_center_y, roi_width, roi_height, progress_callback=None):
        """
        根据 ROI 裁剪 SEQ 文件并创建新的 SEQ 文件

        Args:
            output_seq_path: 输出 SEQ 文件路径
            roi_center_x: ROI 中心 X 坐标
            roi_center_y: ROI 中心 Y 坐标
            roi_width: ROI 宽度
            roi_height: ROI 高度
            progress_callback: 进度回调函数 callback(current, total)

        Returns:
            tuple: (success: bool, roi_top_left_x: int, roi_top_left_y: int, message: str)
        """
        if not self.header_loaded:
            if not self.load_header():
                return False, 0, 0, "无法加载 SEQ 文件头"

        try:
            # 计算 ROI 的左上角坐标
            roi_x = roi_center_x - roi_width // 2
            roi_y = roi_center_y - roi_height // 2

            # 确保 ROI 在图像范围内
            if roi_x < 0 or roi_y < 0 or (roi_x + roi_width) > self.reader.width or (roi_y + roi_height) > self.reader.height:
                error_msg = f"ROI 超出图像范围\n"
                error_msg += f"图像尺寸: {self.reader.width} x {self.reader.height}\n"
                error_msg += f"ROI 范围: ({roi_x}, {roi_y}) 到 ({roi_x + roi_width}, {roi_y + roi_height})"
                return False, roi_x, roi_y, error_msg

            print(f"开始裁剪 SEQ 文件...")
            print(f"  原始图像尺寸: {self.reader.width} x {self.reader.height}")
            print(f"  ROI 中心: ({roi_center_x}, {roi_center_y})")
            print(f"  ROI 尺寸: {roi_width} x {roi_height}")
            print(f"  ROI 左上角: ({roi_x}, {roi_y})")

            # 计算每帧的字节数
            bytes_per_pixel = self.reader.bit_depth // 8
            if self.reader.bit_depth % 8 != 0:
                bytes_per_pixel += 1

            expected_image_size = self.reader.width * self.reader.height * bytes_per_pixel
            frame_size = self.reader.true_image_size if self.reader.true_image_size > 0 else expected_image_size

            # 计算新的图像大小
            new_image_size = roi_width * roi_height * bytes_per_pixel
            # 使用正确的 TrueImageSize 计算方法（包括时间戳和对齐）
            new_true_image_size = self._calculate_true_image_size(new_image_size)

            print(f"  新图像数据大小: {new_image_size} 字节")
            print(f"  新 TrueImageSize (对齐后): {new_true_image_size} 字节")

            # 准备新的文件头
            with open(self.seq_file_path, 'rb') as f_in:
                # 读取原始文件头
                original_header = bytearray(f_in.read(self.reader.header_size))

                # 修改头部信息
                struct.pack_into('<I', original_header, 548, roi_width)  # 新宽度
                struct.pack_into('<I', original_header, 552, roi_height)  # 新高度
                struct.pack_into('<I', original_header, 564, new_image_size)  # ImageSizeBytes
                struct.pack_into('<I', original_header, 580, new_true_image_size)  # TrueImageSize

                # 创建输出文件
                with open(output_seq_path, 'wb') as f_out:
                    # 写入修改后的头部
                    f_out.write(original_header)

                    # 逐帧处理
                    for frame_num in range(self.reader.frame_count):
                        # 跳转到原始帧位置
                        offset = self.reader.header_size + frame_num * frame_size
                        f_in.seek(offset)

                        # 读取帧数据
                        frame_data = f_in.read(frame_size)

                        if len(frame_data) < frame_size:
                            print(f"警告: 帧 {frame_num} 数据不完整，跳过")
                            continue

                        # 跳过帧头
                        if self.reader.frame_header_size > 0:
                            frame_data = frame_data[self.reader.frame_header_size:]

                        # 解析图像数据并裁剪
                        if self.reader.bit_depth == 8:
                            img_array = np.frombuffer(frame_data, dtype=np.uint8)
                            expected_pixels = self.reader.width * self.reader.height
                            actual_bytes = len(img_array)

                            if actual_bytes >= expected_pixels:
                                bytes_per_row = actual_bytes // self.reader.height
                                img_array = img_array[:self.reader.height * bytes_per_row].reshape((self.reader.height, bytes_per_row))
                                img_array = img_array[:, :self.reader.width]
                            else:
                                img_array = img_array.reshape((self.reader.height, self.reader.width))

                            # 裁剪 ROI 区域
                            roi_array = img_array[roi_y:roi_y+roi_height, roi_x:roi_x+roi_width]

                        elif self.reader.bit_depth == 16:
                            img_array = np.frombuffer(frame_data, dtype=np.uint16)
                            expected_pixels = self.reader.width * self.reader.height
                            actual_pixels = len(img_array)

                            if actual_pixels >= expected_pixels:
                                pixels_per_row = actual_pixels // self.reader.height
                                img_array = img_array[:self.reader.height * pixels_per_row].reshape((self.reader.height, pixels_per_row))
                                img_array = img_array[:, :self.reader.width]
                            else:
                                img_array = img_array.reshape((self.reader.height, self.reader.width))

                            # 裁剪 ROI 区域
                            roi_array = img_array[roi_y:roi_y+roi_height, roi_x:roi_x+roi_width]

                        elif self.reader.bit_depth == 24:
                            img_array = np.frombuffer(frame_data, dtype=np.uint8)
                            expected_bytes = self.reader.width * self.reader.height * 3
                            actual_bytes = len(img_array)

                            if actual_bytes >= expected_bytes:
                                bytes_per_row = actual_bytes // self.reader.height
                                img_array = img_array[:self.reader.height * bytes_per_row].reshape((self.reader.height, bytes_per_row))
                                img_array = img_array[:, :self.reader.width * 3]
                                img_array = img_array.reshape((self.reader.height, self.reader.width, 3))
                            else:
                                img_array = img_array.reshape((self.reader.height, self.reader.width, 3))

                            # 裁剪 ROI 区域
                            roi_array = img_array[roi_y:roi_y+roi_height, roi_x:roi_x+roi_width, :]

                        else:
                            return False, roi_x, roi_y, f"不支持的位深度: {self.reader.bit_depth}"

                        # 写入裁剪后的帧数据
                        img_bytes = roi_array.tobytes()
                        f_out.write(img_bytes)

                        # 写入 8 字节时间戳（按照 NorPix 格式）
                        # 时间戳格式：4字节时间 + 2字节毫秒 + 2字节微秒
                        import time
                        timestamp_time_t = int(time.time())
                        timestamp_ms = int((time.time() - timestamp_time_t) * 1000)
                        timestamp_us = 0  # 微秒部分设为 0

                        f_out.write(struct.pack('<I', timestamp_time_t))  # 4 字节时间
                        f_out.write(struct.pack('<H', timestamp_ms))      # 2 字节毫秒
                        f_out.write(struct.pack('<H', timestamp_us))      # 2 字节微秒

                        # 填充到 TrueImageSize
                        bytes_written = len(img_bytes) + 8  # 图像数据 + 时间戳
                        padding_size = new_true_image_size - bytes_written
                        if padding_size > 0:
                            f_out.write(b'\x00' * padding_size)

                        # 进度回调
                        if progress_callback:
                            progress_callback(frame_num + 1, self.reader.frame_count)

            success_msg = f"成功裁剪 {self.reader.frame_count} 帧\n"
            success_msg += f"新图像尺寸: {roi_width} x {roi_height}\n"
            success_msg += f"ROI 左上角: ({roi_x}, {roi_y})"

            print(f"裁剪完成! 新文件: {output_seq_path}")
            print(f"  新图像尺寸: {roi_width} x {roi_height}")
            print(f"  总帧数: {self.reader.frame_count}")

            return True, roi_x, roi_y, success_msg

        except Exception as e:
            error_msg = f"裁剪失败: {str(e)}"
            print(error_msg)
            import traceback
            traceback.print_exc()
            return False, 0, 0, error_msg


def crop_seq_file(input_seq, output_seq, roi_center_x, roi_center_y, roi_width, roi_height):
    """
    裁剪 SEQ 文件的便捷函数

    Args:
        input_seq: 输入 SEQ 文件路径
        output_seq: 输出 SEQ 文件路径
        roi_center_x: ROI 中心 X 坐标
        roi_center_y: ROI 中心 Y 坐标
        roi_width: ROI 宽度
        roi_height: ROI 高度

    Returns:
        bool: 成功返回 True，失败返回 False
    """
    if not os.path.exists(input_seq):
        print(f"错误: 输入文件不存在: {input_seq}")
        return False

    cropper = SeqCropper(input_seq)
    success, roi_x, roi_y, message = cropper.crop_to_new_seq(
        output_seq, roi_center_x, roi_center_y, roi_width, roi_height
    )

    if success:
        print(f"\n成功!")
        print(f"输出文件: {output_seq}")
        print(f"ROI 左上角坐标: ({roi_x}, {roi_y})")
    else:
        print(f"\n失败: {message}")

    return success


if __name__ == "__main__":
    # 测试示例
    print("=" * 60)
    print("SEQ 文件 ROI 裁剪工具")
    print("=" * 60)
    print("\n使用方法:")
    print("  from seq_to_seq import crop_seq_file")
    print("  crop_seq_file('input.seq', 'output.seq', center_x, center_y, width, height)")
    print("\n" + "=" * 60)
