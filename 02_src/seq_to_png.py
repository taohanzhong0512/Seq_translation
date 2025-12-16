import os
import struct
import numpy as np
from PIL import Image
import argparse


class SeqReader:
    """
    Reads .seq files based on the NorPix Sequence File Format,
    with logic corrected according to the provided C++ source code.
    """

    def __init__(self, seq_file_path):
        self.seq_file_path = seq_file_path
        self.width = 0
        self.height = 0
        self.bit_depth = 0
        self.image_format = 0
        self.image_size_bytes = 0
        self.true_image_size = 0  # This will be the calculated, padded size of a full frame block
        self.frame_count = 0
        self.frame_rate = 0.0
        self.header_size = 8192  # The first image frame starts at this offset
        self.frame_header_size = 0 # Kept for GUI compatibility

    def _calculate_true_image_size(self, image_size_bytes):
        """
        Calculates the padded size of a frame block, mimicking the C++ source.
        TrueImageSize = ImageSizeBytes + 8 bytes for timestamp,
                        then padded to be a multiple of 8192.
        """
        # Add 8 bytes for the timestamp
        size_with_timestamp = image_size_bytes + 8
        
        # Pad to the nearest multiple of 8192
        alignment = 8192
        if size_with_timestamp % alignment == 0:
            return size_with_timestamp
        else:
            return ((size_with_timestamp // alignment) + 1) * alignment

    def read_header(self):
        """
        Reads the header of the Norpix .seq file and calculates the correct TrueImageSize.
        """
        if not os.path.exists(self.seq_file_path):
            print(f"Error: File not found at {self.seq_file_path}")
            return False

        try:
            with open(self.seq_file_path, 'rb') as f:
                header = f.read(1024)

                magic_number = struct.unpack('<I', header[0:4])[0]
                if magic_number != 0xFEED:
                    print(f"Error: Invalid magic number. Expected 0xFEED, got {hex(magic_number)}")
                    return False

                # Parse CImageInfo structure
                self.width = struct.unpack('<I', header[548:552])[0]
                self.height = struct.unpack('<I', header[552:556])[0]
                self.bit_depth = struct.unpack('<I', header[560:564])[0]
                self.image_size_bytes = struct.unpack('<I', header[564:568])[0]
                self.image_format = struct.unpack('<I', header[568:572])[0]

                # This is the key part: calculate the TrueImageSize based on the C++ logic
                self.true_image_size = self._calculate_true_image_size(self.image_size_bytes)
                
                # The frame count from the header might be correct, but we can also verify it
                self.frame_count = struct.unpack('<I', header[572:576])[0]
                self.frame_rate = struct.unpack('<d', header[584:592])[0]

                # Validation and recalculation if necessary
                if self.width == 0 or self.height == 0 or self.bit_depth == 0:
                    print("Error: Header data seems invalid.")
                    return False
                
                file_size = os.path.getsize(self.seq_file_path)
                if file_size > self.header_size and self.true_image_size > 0:
                    calculated_frame_count = (file_size - self.header_size) // self.true_image_size
                    # If the header frame count is 0 or seems wrong, use the calculated one
                    if self.frame_count == 0 or self.frame_count > calculated_frame_count:
                        self.frame_count = calculated_frame_count
                else:
                    self.frame_count = 0

                print("Norpix SEQ file header parsed successfully (with C++ logic):")
                print(f"  - Dimensions: {self.width}x{self.height}")
                print(f"  - Bit Depth: {self.bit_depth} bits")
                print(f"  - Image Size (raw): {self.image_size_bytes} bytes")
                print(f"  - True Image Size (calculated, padded): {self.true_image_size} bytes")
                print(f"  - Frame Count: {self.frame_count}")
                print(f"  - Frame Rate: {self.frame_rate} fps")

                return True

        except Exception as e:
            print(f"An error occurred while reading the header: {e}")
            import traceback
            traceback.print_exc()
            return False

    def extract_frames(self, output_dir, start_frame=0, end_frame=None, prefix="frame", format="PNG"):
        """
        Extracts frames using the corrected logic.
        """
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        if end_frame is None or end_frame > self.frame_count:
            end_frame = self.frame_count

        format = format.upper()
        ext = 'tif' if format == 'TIFF' else format.lower()

        print(f"Extracting frames {start_frame} to {end_frame - 1}...")

        with open(self.seq_file_path, 'rb') as f:
            for i in range(start_frame, end_frame):
                # The offset calculation is now correct
                offset = self.header_size + i * self.true_image_size
                f.seek(offset)
                
                frame_data = f.read(self.image_size_bytes)

                if len(frame_data) < self.image_size_bytes:
                    print(f"Warning: Frame {i} is incomplete. Skipping.")
                    continue

                try:
                    if self.bit_depth == 8:
                        img_array = np.frombuffer(frame_data, dtype=np.uint8).reshape((self.height, self.width))
                        img = Image.fromarray(img_array, mode='L')
                    elif self.bit_depth == 16:
                        img_array = np.frombuffer(frame_data, dtype=np.uint16).reshape((self.height, self.width))
                        if format == 'TIFF':
                             img = Image.fromarray(img_array, mode='I;16')
                        else:
                            img_array_8bit = (img_array / 256).astype(np.uint8)
                            img = Image.fromarray(img_array_8bit, mode='L')
                    elif self.bit_depth == 24:
                        img_array = np.frombuffer(frame_data, dtype=np.uint8).reshape((self.height, self.width, 3))
                        img = Image.fromarray(img_array, mode='RGB')
                    else:
                        print(f"Unsupported bit depth: {self.bit_depth}")
                        continue

                    output_filename = f"{prefix}_{i:06d}.{ext}"
                    output_path = os.path.join(output_dir, output_filename)
                    img.save(output_path, format=format)

                except Exception as e:
                    print(f"Error processing frame {i}: {e}")
        
        print(f"Extraction complete. {end_frame - start_frame} frames saved to {output_dir}")


def seq_to_png(seq_file, output_dir=None, start_frame=0, end_frame=None,
               prefix='frame', width=None, height=None, bitdepth=8, format='PNG'):
    if not os.path.exists(seq_file):
        print(f"错误: 文件 '{seq_file}' 不存在")
        return False

    if output_dir is None:
        seq_basename = os.path.splitext(os.path.basename(seq_file))[0]
        output_dir = os.path.join(os.path.dirname(seq_file), f"{seq_basename}_frames")

    reader = SeqReader(seq_file)
    if not reader.read_header():
        print("无法解析 SEQ 文件头，转换失败。")
        return False

    reader.extract_frames(
        output_dir=output_dir,
        start_frame=start_frame,
        end_frame=end_frame,
        prefix=prefix,
        format=format
    )
    return True


def main():
    parser = argparse.ArgumentParser(description='将 SEQ 文件转换为图像序列')
    parser.add_argument('seq_file', help='输入的 SEQ 文件路径')
    parser.add_argument('-o', '--output', default=None, help='输出目录 (默认: seq文件同名目录)')
    parser.add_argument('-s', '--start', type=int, default=0, help='起始帧号 (默认: 0)')
    parser.add_argument('-e', '--end', type=int, default=None, help='结束帧号 (默认: 全部)')
    parser.add_argument('-p', '--prefix', default='frame', help='输出文件名前缀 (默认: frame)')
    parser.add_argument('-f', '--format', default='PNG', choices=['PNG', 'TIFF', 'BMP'], help='输出图像格式 (默认: PNG)')
    # Manual override arguments are no longer necessary if the header is parsed correctly
    # but can be kept for edge cases if needed.
    
    args = parser.parse_args()

    seq_to_png(
        seq_file=args.seq_file,
        output_dir=args.output,
        start_frame=args.start,
        end_frame=args.end,
        prefix=args.prefix,
        format=args.format
    )


if __name__ == "__main__":
    main()
