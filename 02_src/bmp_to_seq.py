import os
import ffmpeg
from PIL import Image
import re # 用于更灵活地从文件名中提取数字

def get_sequence_number(filename):
    """
    尝试从文件名中提取数字序列号。
    优先匹配文件名末尾的数字。
    例如：
    "continuous_pic_1000_00_0_00_20251014154820511_1.bmp" -> 1
    "continuous_pic_1000_00_0_00_20251014154820511_10.bmp" -> 10
    "frame_001.bmp" -> 1
    """
    # 尝试匹配文件名末尾的数字（可能前面有下划线）
    match = re.search(r'_(\d+)\.bmp$', filename, re.IGNORECASE)
    if match:
        return int(match.group(1))

    # 如果末尾没有数字，尝试匹配文件名中的其他数字（例如 %04d 格式）
    # 这个部分可能需要根据你的实际文件名进行调整
    # 例如，如果你的文件名是 continuous_pic_1000_...
    # 你可能需要一个更复杂的正则表达式来提取你想要作为序列号的数字
    # 但通常，FFmpeg 处理图像序列时，会寻找一个主要的数字序列。
    # 对于你提供的文件名，末尾的 _1, _2, _3 是最明显的序列。

    # 如果以上都匹配不到，返回一个非常大的数，让它排在后面（或者根据需要调整）
    return float('inf')

def convert_dynamic_bmps_to_avi(input_directory: str, output_avi_file: str, frame_rate: int = 30, temp_prefix: str = "temp_frame_"):
    """
    将文件名结构复杂的 BMP 图像转换为 AVI 视频文件。
    通过重命名文件为统一序列模式来解决。

    Args:
        input_directory: 包含 BMP 图像的目录路径。
        output_avi_file: 输出的 .avi 文件路径。
        frame_rate: 视频的帧率 (每秒帧数)。
        temp_prefix: 重命名临时文件的前缀。
    """
    if not os.path.isdir(input_directory):
        print(f"错误: 输入目录 '{input_directory}' 不存在。")
        return

    # 1. 获取所有 BMP 文件
    bmp_files = [f for f in os.listdir(input_directory) if f.lower().endswith('.bmp')]
    if not bmp_files:
        print(f"错误: 在目录 '{input_directory}' 中未找到 BMP 文件。")
        return

    # 2. 根据文件名末尾的数字进行排序
    #    我们使用 get_sequence_number 函数来提取排序依据
    bmp_files.sort(key=get_sequence_number)

    print(f"找到 {len(bmp_files)} 个 BMP 文件。")

    # 3. 验证第一张图片以获取尺寸
    first_original_image_path = os.path.join(input_directory, bmp_files[0])
    try:
        with Image.open(first_original_image_path) as img:
            width, height = img.size
            print(f"第一张图片尺寸: {width}x{height}")
    except Exception as e:
        print(f"错误: 无法读取第一张 BMP 文件 '{first_original_image_path}' 来获取尺寸信息: {e}")
        return

    # 4. 重命名文件为统一序列模式
    temp_files = []
    max_digits = len(str(len(bmp_files))) # 计算需要多少位数来表示最大帧数，例如 5 帧需要 1 位，100 帧需要 3 位
    for i, filename in enumerate(bmp_files):
        # 生成新的文件名，例如 temp_frame_00001.bmp
        new_filename = f"{temp_prefix}{i+1:0{max_digits}d}.bmp"
        original_path = os.path.join(input_directory, filename)
        new_path = os.path.join(input_directory, new_filename)

        try:
            os.rename(original_path, new_path)
            temp_files.append(new_filename) # 记录重命名后的文件名
            # print(f"重命名: '{filename}' -> '{new_filename}'") # 打印重命名过程（可选）
        except OSError as e:
            print(f"错误: 重命名文件 '{filename}' 到 '{new_filename}' 失败: {e}")
            # 如果重命名失败，可能需要停止或处理
            return

    # 5. 构建 FFmpeg 输入模式 (使用重命名后的文件)
    #    现在文件名是 temp_frame_00001.bmp, temp_frame_00002.bmp ...
    #    所以模式是 temp_frame_%0Nd.bmp
    #    其中 N 是 max_digits
    input_pattern_for_ffmpeg = os.path.join(input_directory, f"{temp_prefix}%0{max_digits}d.bmp")

    print(f"使用的 FFmpeg 输入模式 (重命名后): {input_pattern_for_ffmpeg}")

    try:
        print(f"开始转换为 AVI 视频 (帧率: {frame_rate} fps)...")
        stream = ffmpeg.input(input_pattern_for_ffmpeg, framerate=frame_rate)
        stream = ffmpeg.output(stream, output_avi_file, vcodec='libxvid', pix_fmt='yuv420p')
        ffmpeg.run(stream, overwrite_output=True, capture_stdout=True, capture_stderr=True)

        print(f"成功创建 AVI 视频文件: {output_avi_file}")

    except ffmpeg.Error as e:
        print(f"FFmpeg 转换错误:")
        print(f"  STDOUT: {e.stdout.decode('utf8', errors='ignore')}")
        print(f"  STDERR: {e.stderr.decode('utf8', errors='ignore')}")
    except FileNotFoundError:
        print(f"错误: FFmpeg 可执行文件未找到。请确保 FFmpeg 已正确安装并添加到系统 PATH。")
    except Exception as e:
        print(f"发生未知错误: {e}")
    finally:
        # 6. 清理重命名后的临时文件 (可选)
        print("正在清理临时文件...")
        for temp_filename in temp_files:
            temp_path = os.path.join(input_directory, temp_filename)
            try:
                os.remove(temp_path)
                # print(f"已删除临时文件: {temp_filename}") # 打印删除过程（可选）
            except OSError as e:
                print(f"警告: 删除临时文件 '{temp_filename}' 失败: {e}")
        print("清理完成。")


# --- 如何使用 ---
if __name__ == "__main__":
    # input_directory = r"E:\code\DCS_script\data_mingqi\2-500mw-3000ns(理想数据)" # <--- 请确保此路径正确

    input_directory = r"E:\data\液滴定位测试图片与结果\first_point_output_images\\"
    output_avi_filename = "1_output_video_renamed.avi"
    video_frame_rate = 30

    if not os.path.isdir(input_directory):
        print(f"错误: 指定的输入目录 '{input_directory}' 不存在。请检查路径是否正确。")
    else:
        convert_dynamic_bmps_to_avi(input_directory, output_avi_filename, frame_rate=video_frame_rate)
