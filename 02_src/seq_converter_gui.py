"""
双向 SEQ 转换器 GUI
支持:
- SEQ → PNG/BMP/TIFF
- PNG/BMP/TIFF → SEQ
- PNG/BMP/TIFF → AVI/MP4/MOV
"""

import sys
import os
from pathlib import Path
from PyQt5.QtWidgets import QApplication, QWidget, QFileDialog, QTextEdit
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QIcon, QPixmap, QColor
from qfluentwidgets import (
    PushButton, LineEdit, SpinBox, ComboBox, ProgressBar, DoubleSpinBox,
    setTheme, Theme, FluentIcon, InfoBar, InfoBarPosition,
    CardWidget, BodyLabel, StrongBodyLabel, TransparentPushButton,
    Pivot, qrouter, SegmentedWidget
)
from PyQt5.QtWidgets import QVBoxLayout, QHBoxLayout, QGridLayout, QStackedWidget, QLabel
from PyQt5.QtGui import QPainter, QPen, QFont
from PyQt5.QtCore import QRect, QPoint

# 导入转换模块
from seq_to_png import SeqReader
from images_to_seq import SeqWriter, get_sequence_number as get_seq_number
from images_to_video import convert_images_to_video
from seq_to_seq import SeqCropper


def resource_path(relative_path):
    """获取资源文件的绝对路径，支持打包后的环境"""
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


class ImagePreviewWidget(QWidget):
    """带刻度尺和ROI显示的图像预览控件"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.pixmap = None
        self.original_width = 0
        self.original_height = 0
        self.roi_center_x = 0
        self.roi_center_y = 0
        self.roi_width = 0
        self.roi_height = 0
        self.show_roi = False

        # 刻度尺参数
        self.ruler_width = 50  # 刻度尺宽度（左侧）
        self.ruler_height = 40  # 刻度尺高度（上侧）

        # 设置最小尺寸
        self.setMinimumSize(800, 600)

        # 设置背景
        self.setStyleSheet("""
            ImagePreviewWidget {
                background-color: #f9f9f9;
                border: 2px solid #e0e0e0;
                border-radius: 8px;
            }
        """)

    def set_image(self, pixmap, original_width, original_height):
        """设置要显示的图像"""
        self.pixmap = pixmap
        self.original_width = original_width
        self.original_height = original_height
        self.update()

    def set_roi(self, center_x, center_y, width, height):
        """设置ROI参数"""
        self.roi_center_x = center_x
        self.roi_center_y = center_y
        self.roi_width = width
        self.roi_height = height
        self.show_roi = True
        self.update()

    def clear(self):
        """清空显示"""
        self.pixmap = None
        self.show_roi = False
        self.update()

    def paintEvent(self, event):
        """绘制事件"""
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        if self.pixmap is None:
            # 显示提示文本
            painter.setPen(QPen(QColor(150, 150, 150)))
            painter.setFont(QFont('Microsoft YaHei', 12))
            painter.drawText(self.rect(), Qt.AlignCenter, '选择 SEQ 文件后显示预览')
            return

        # 计算图像显示区域（留出刻度尺空间）
        image_rect = QRect(
            self.ruler_width,
            self.ruler_height,
            self.width() - self.ruler_width - 10,
            self.height() - self.ruler_height - 10
        )

        # 缩放图像以适应显示区域
        scaled_pixmap = self.pixmap.scaled(
            image_rect.size(),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation
        )

        # 计算缩放比例
        scale_x = scaled_pixmap.width() / self.original_width
        scale_y = scaled_pixmap.height() / self.original_height

        # 居中显示图像
        x_offset = image_rect.x() + (image_rect.width() - scaled_pixmap.width()) // 2
        y_offset = image_rect.y() + (image_rect.height() - scaled_pixmap.height()) // 2

        # 绘制图像
        painter.drawPixmap(x_offset, y_offset, scaled_pixmap)

        # 绘制刻度尺
        self.draw_rulers(painter, x_offset, y_offset, scaled_pixmap.width(), scaled_pixmap.height(), scale_x, scale_y)

        # 绘制ROI框
        if self.show_roi:
            self.draw_roi(painter, x_offset, y_offset, scale_x, scale_y)

    def draw_rulers(self, painter, x_offset, y_offset, img_width, img_height, scale_x, scale_y):
        """绘制刻度尺"""
        painter.setPen(QPen(QColor(80, 80, 80)))
        painter.setFont(QFont('Arial', 9))

        # 水平刻度尺（上方）
        ruler_y = y_offset - 8
        num_ticks_x = min(10, self.original_width // 200)
        if num_ticks_x < 4:
            num_ticks_x = 5

        for i in range(num_ticks_x + 1):
            x_pos = x_offset + (img_width * i) // num_ticks_x
            # 刻度线
            painter.drawLine(x_pos, ruler_y, x_pos, ruler_y - 8)
            # 刻度值
            pixel_value = int((self.original_width * i) / num_ticks_x)
            text_width = 50
            painter.drawText(x_pos - text_width//2, ruler_y - 25, text_width, 20, Qt.AlignCenter, str(pixel_value))

        # 垂直刻度尺（左侧）
        ruler_x = x_offset - 8
        num_ticks_y = min(10, self.original_height // 200)
        if num_ticks_y < 4:
            num_ticks_y = 5

        for i in range(num_ticks_y + 1):
            y_pos = y_offset + (img_height * i) // num_ticks_y
            # 刻度线
            painter.drawLine(ruler_x, y_pos, ruler_x - 8, y_pos)
            # 刻度值
            pixel_value = int((self.original_height * i) / num_ticks_y)
            text_width = 45
            painter.drawText(ruler_x - text_width - 3, y_pos - 10, text_width, 20, Qt.AlignRight | Qt.AlignVCenter, str(pixel_value))

    def draw_roi(self, painter, x_offset, y_offset, scale_x, scale_y):
        """绘制ROI框"""
        # 计算ROI在缩放后的位置
        roi_x = self.roi_center_x - self.roi_width // 2
        roi_y = self.roi_center_y - self.roi_height // 2

        scaled_roi_x = int(roi_x * scale_x) + x_offset
        scaled_roi_y = int(roi_y * scale_y) + y_offset
        scaled_roi_width = int(self.roi_width * scale_x)
        scaled_roi_height = int(self.roi_height * scale_y)

        # 绘制ROI矩形框（红色，2像素宽）
        pen = QPen(QColor(255, 0, 0))
        pen.setWidth(2)
        pen.setStyle(Qt.SolidLine)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawRect(scaled_roi_x, scaled_roi_y, scaled_roi_width, scaled_roi_height)

        # 绘制中心十字线
        center_x = scaled_roi_x + scaled_roi_width // 2
        center_y = scaled_roi_y + scaled_roi_height // 2
        cross_size = 10

        pen.setStyle(Qt.DashLine)
        painter.setPen(pen)
        painter.drawLine(center_x - cross_size, center_y, center_x + cross_size, center_y)
        painter.drawLine(center_x, center_y - cross_size, center_x, center_y + cross_size)

        # 绘制ROI信息文本
        painter.setPen(QPen(QColor(255, 0, 0)))
        painter.setFont(QFont('Arial', 9, QFont.Bold))
        info_text = f'ROI: {self.roi_width} × {self.roi_height}'
        text_x = scaled_roi_x + 5
        text_y = scaled_roi_y - 5

        # 绘制文本背景
        text_rect = painter.fontMetrics().boundingRect(info_text)
        text_rect.adjust(-3, -1, 3, 1)
        text_rect.moveTo(text_x, text_y - text_rect.height())
        painter.fillRect(text_rect, QColor(255, 255, 255, 200))

        # 绘制文本
        painter.drawText(text_x, text_y, info_text)


class SeqToImagesThread(QThread):
    """SEQ → 图像序列转换线程"""
    progress = pyqtSignal(int, int)
    finished = pyqtSignal(bool, str)
    log = pyqtSignal(str)

    def __init__(self, seq_file, output_dir, start_frame, end_frame, prefix, format='PNG'):
        super().__init__()
        self.seq_file = seq_file
        self.output_dir = output_dir
        self.start_frame = start_frame
        self.end_frame = end_frame
        self.prefix = prefix
        self.format = format
        self._is_running = True

    def run(self):
        try:
            reader = SeqReader(self.seq_file)
            self.log.emit("正在读取 SEQ 文件头信息...")

            if not reader.read_header():
                self.finished.emit(False, "无法识别 SEQ 文件格式")
                return

            if self.end_frame is None or self.end_frame <= 0:
                self.end_frame = reader.frame_count
            self.end_frame = min(self.end_frame, reader.frame_count)

            if self.start_frame >= self.end_frame:
                self.finished.emit(False, "起始帧号必须小于结束帧号")
                return

            self.format = self.format.upper()
            if self.format not in ["PNG", "TIFF", "BMP"]:
                self.finished.emit(False, f"不支持的图像格式 '{self.format}'")
                return

            ext = self.format.lower()
            if self.format == "TIFF":
                ext = "tif"

            self.log.emit(f"开始转换: 帧 {self.start_frame} 到 {self.end_frame-1} (共 {self.end_frame - self.start_frame} 帧)")

            if not os.path.exists(self.output_dir):
                os.makedirs(self.output_dir)

            bytes_per_pixel = reader.bit_depth // 8
            if reader.bit_depth % 8 != 0:
                bytes_per_pixel += 1

            expected_image_size = reader.width * reader.height * bytes_per_pixel
            frame_size = reader.true_image_size if reader.true_image_size > 0 else expected_image_size

            import numpy as np
            from PIL import Image

            with open(self.seq_file, 'rb') as f:
                for frame_num in range(self.start_frame, self.end_frame):
                    if not self._is_running:
                        self.finished.emit(False, "转换已取消")
                        return

                    # 使用修正后的逻辑：跳转到帧位置，只读取图像数据部分
                    offset = reader.header_size + frame_num * frame_size
                    f.seek(offset)

                    # 只读取精确的图像数据，忽略时间戳和填充
                    frame_data = f.read(reader.image_size_bytes)

                    if len(frame_data) < reader.image_size_bytes:
                        self.log.emit(f"警告: 帧 {frame_num} 数据不完整，跳过")
                        continue

                    # 处理不同位深度（现在 frame_data 只包含图像数据，不含时间戳和填充）
                    try:
                        if reader.bit_depth == 8:
                            img_array = np.frombuffer(frame_data, dtype=np.uint8).reshape((reader.height, reader.width))
                            img = Image.fromarray(img_array, mode='L')
                        elif reader.bit_depth == 16:
                            img_array = np.frombuffer(frame_data, dtype=np.uint16).reshape((reader.height, reader.width))
                            if self.format == 'TIFF':
                                img = Image.fromarray(img_array, mode='I;16')
                            else:
                                img_array_8bit = (img_array / 256).astype(np.uint8)
                                img = Image.fromarray(img_array_8bit, mode='L')
                        elif reader.bit_depth == 24:
                            img_array = np.frombuffer(frame_data, dtype=np.uint8).reshape((reader.height, reader.width, 3))
                            img = Image.fromarray(img_array, mode='RGB')
                        else:
                            self.log.emit(f"警告: 帧 {frame_num} 的位深度不受支持 ({reader.bit_depth})，已跳过")
                            continue
                    except ValueError as ve:
                        self.log.emit(f"错误: 处理帧 {frame_num} 时发生数据错误 (可能尺寸不匹配): {ve}")
                        continue

                    output_filename = f"{self.prefix}_{frame_num:06d}.{ext}"
                    output_path = os.path.join(self.output_dir, output_filename)
                    img.save(output_path, format=self.format)

                    self.progress.emit(frame_num - self.start_frame + 1, self.end_frame - self.start_frame)

            self.finished.emit(True, f"成功转换 {self.end_frame - self.start_frame} 帧!")

        except Exception as e:
            import traceback
            error_msg = f"转换失败: {str(e)}\n{traceback.format_exc()}"
            self.log.emit(error_msg)
            self.finished.emit(False, str(e))

    def stop(self):
        self._is_running = False


class ImagesToSeqThread(QThread):
    """图像序列 → SEQ 转换线程"""
    progress = pyqtSignal(int, int)
    finished = pyqtSignal(bool, str)
    log = pyqtSignal(str)

    def __init__(self, input_dir, output_file, image_format, bit_depth, frame_rate, start_frame, end_frame):
        super().__init__()
        self.input_dir = input_dir
        self.output_file = output_file
        self.image_format = image_format
        self.bit_depth = bit_depth
        self.frame_rate = frame_rate
        self.start_frame = start_frame
        self.end_frame = end_frame
        self._is_running = True

    def run(self):
        try:
            self.log.emit(f"正在扫描图像文件...")

            # 获取图像文件列表
            extensions = {
                'png': ['.png'],
                'bmp': ['.bmp'],
                'tiff': ['.tiff', '.tif'],
                'all': ['.png', '.bmp', '.tiff', '.tif', '.jpg', '.jpeg']
            }
            valid_exts = extensions.get(self.image_format.lower(), extensions['all'])
            image_files = [f for f in os.listdir(self.input_dir)
                          if os.path.splitext(f)[1].lower() in valid_exts]

            if not image_files:
                self.finished.emit(False, "未找到图像文件")
                return

            image_files.sort(key=get_seq_number)

            # 应用帧范围
            if self.start_frame is not None or self.end_frame is not None:
                start_idx = (self.start_frame - 1) if self.start_frame else 0
                end_idx = self.end_frame if self.end_frame else len(image_files)
                image_files = image_files[start_idx:end_idx]

            self.log.emit(f"找到 {len(image_files)} 个图像文件")

            image_paths = [os.path.join(self.input_dir, f) for f in image_files]

            # 创建 SEQ 写入器
            writer = SeqWriter(self.output_file, None, None, self.bit_depth, self.frame_rate)

            def progress_callback(current, total):
                if self._is_running:
                    self.progress.emit(current, total)

            self.log.emit("开始写入 SEQ 文件...")
            success = writer.write_images(image_paths, progress_callback)

            if success:
                self.finished.emit(True, f"成功创建 SEQ 文件，共 {len(image_files)} 帧")
            else:
                self.finished.emit(False, "SEQ 写入失败")

        except Exception as e:
            import traceback
            error_msg = f"转换失败: {str(e)}\n{traceback.format_exc()}"
            self.log.emit(error_msg)
            self.finished.emit(False, str(e))

    def stop(self):
        self._is_running = False


class ImagesToVideoThread(QThread):
    """图像序列 → 视频转换线程"""
    progress = pyqtSignal(int, int)
    finished = pyqtSignal(bool, str)
    log = pyqtSignal(str)

    def __init__(self, input_dir, output_file, image_format, frame_rate, video_codec, quality, start_frame, end_frame):
        super().__init__()
        self.input_dir = input_dir
        self.output_file = output_file
        self.image_format = image_format
        self.frame_rate = frame_rate
        self.video_codec = video_codec
        self.quality = quality
        self.start_frame = start_frame
        self.end_frame = end_frame
        self._is_running = True

    def run(self):
        try:
            self.log.emit("开始转换为视频...")

            success = convert_images_to_video(
                self.input_dir,
                self.output_file,
                self.image_format.lower(),
                int(self.frame_rate),
                self.video_codec,
                self.quality,
                self.start_frame,
                self.end_frame
            )

            if success:
                self.finished.emit(True, "成功创建视频文件")
            else:
                self.finished.emit(False, "视频转换失败")

        except Exception as e:
            import traceback
            error_msg = f"转换失败: {str(e)}\n{traceback.format_exc()}"
            self.log.emit(error_msg)
            self.finished.emit(False, str(e))

    def stop(self):
        self._is_running = False


class SeqRoiCropThread(QThread):
    """SEQ ROI 裁剪线程"""
    progress = pyqtSignal(int, int)
    finished = pyqtSignal(bool, str)
    log = pyqtSignal(str)

    def __init__(self, input_seq, output_seq, roi_center_x, roi_center_y, roi_width, roi_height):
        super().__init__()
        self.input_seq = input_seq
        self.output_seq = output_seq
        self.roi_center_x = roi_center_x
        self.roi_center_y = roi_center_y
        self.roi_width = roi_width
        self.roi_height = roi_height
        self._is_running = True

    def run(self):
        try:
            self.log.emit(f"正在加载 SEQ 文件头信息...")

            cropper = SeqCropper(self.input_seq)

            if not cropper.load_header():
                self.finished.emit(False, "无法加载 SEQ 文件头")
                return

            self.log.emit(f"原始图像尺寸: {cropper.reader.width} x {cropper.reader.height}")
            self.log.emit(f"总帧数: {cropper.reader.frame_count}")
            self.log.emit(f"ROI 中心: ({self.roi_center_x}, {self.roi_center_y})")
            self.log.emit(f"ROI 尺寸: {self.roi_width} x {self.roi_height}")

            def progress_callback(current, total):
                if self._is_running:
                    self.progress.emit(current, total)

            self.log.emit("开始裁剪...")
            success, roi_x, roi_y, message = cropper.crop_to_new_seq(
                self.output_seq,
                self.roi_center_x,
                self.roi_center_y,
                self.roi_width,
                self.roi_height,
                progress_callback
            )

            if success:
                self.finished.emit(True, f"裁剪成功!\nROI 左上角坐标: ({roi_x}, {roi_y})\n{message}")
            else:
                self.finished.emit(False, message)

        except Exception as e:
            import traceback
            error_msg = f"裁剪失败: {str(e)}\n{traceback.format_exc()}"
            self.log.emit(error_msg)
            self.finished.emit(False, str(e))

    def stop(self):
        self._is_running = False


class ConverterGUI(QWidget):
    def __init__(self):
        super().__init__()
        self.convert_thread = None
        self.initUI()

    def initUI(self):
        self.setWindowTitle('SEQ 双向转换器')
        self.resize(900, 800)

        # 设置窗口图标
        icon_path = resource_path(os.path.join('image', 'DCS_Application_Logo.ico'))
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        else:
            icon_path_dev = os.path.join(os.path.dirname(os.path.dirname(__file__)), '05_resource', 'image', 'DCS_Application_Logo.ico')
            if os.path.exists(icon_path_dev):
                self.setWindowIcon(QIcon(icon_path_dev))

        self.setStyleSheet("ConverterGUI { background-color: #f5f5f5; }")

        # 主布局
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)

        # 标题栏
        header_layout = QHBoxLayout()
        title_label = StrongBodyLabel('SEQ 双向转换器', self)
        title_label.setStyleSheet('font-size: 24px; font-weight: bold; color: #0078d7;')
        header_layout.addWidget(title_label)
        header_layout.addStretch()

        # SIOM logo
        siom_logo_path = resource_path(os.path.join('image', 'SIOM_logo.png'))
        if not os.path.exists(siom_logo_path):
            siom_logo_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '05_resource', 'image', 'SIOM_logo.png')

        if os.path.exists(siom_logo_path):
            siom_label = QLabel(self)
            siom_pixmap = QPixmap(siom_logo_path).scaled(80, 80, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            siom_label.setPixmap(siom_pixmap)
            header_layout.addWidget(siom_label)

        main_layout.addLayout(header_layout)

        # 模式切换
        self.mode_pivot = SegmentedWidget(self)
        self.mode_pivot.addItem(routeKey='seq_to_images', text='SEQ → 图像', onClick=lambda: self.switch_mode(0))
        self.mode_pivot.addItem(routeKey='images_to_output', text='图像 → SEQ/视频', onClick=lambda: self.switch_mode(1))
        self.mode_pivot.addItem(routeKey='seq_roi_crop', text='SEQ ROI 裁剪', onClick=lambda: self.switch_mode(2))
        self.mode_pivot.setCurrentItem('seq_to_images')
        main_layout.addWidget(self.mode_pivot)

        # 创建水平布局：左侧是内容区，右侧是进度和日志
        content_h_layout = QHBoxLayout()
        content_h_layout.setSpacing(15)

        # 左侧：内容区域（包含堆叠窗口和按钮）
        left_content_widget = QWidget()
        left_content_layout = QVBoxLayout(left_content_widget)
        left_content_layout.setContentsMargins(0, 0, 0, 0)
        left_content_layout.setSpacing(15)

        # 堆叠窗口：用于切换不同模式的界面
        self.stacked_widget = QStackedWidget(self)

        # 创建三个模式的界面
        self.seq_to_images_widget = self.create_seq_to_images_ui()
        self.images_to_output_widget = self.create_images_to_output_ui()
        self.seq_roi_crop_widget = self.create_seq_roi_crop_ui()

        self.stacked_widget.addWidget(self.seq_to_images_widget)
        self.stacked_widget.addWidget(self.images_to_output_widget)
        self.stacked_widget.addWidget(self.seq_roi_crop_widget)

        left_content_layout.addWidget(self.stacked_widget)

        # 按钮区域（在左侧内容区底部）
        self.create_button_ui(left_content_layout)

        # 将左侧内容添加到水平布局
        content_h_layout.addWidget(left_content_widget, stretch=7)  # 左侧占70%

        # 右侧：共享的进度和日志区域
        self.create_shared_ui(content_h_layout)

        # 将水平布局添加到主布局
        main_layout.addLayout(content_h_layout)

        # 设置主题
        setTheme(Theme.LIGHT)
        from qfluentwidgets import setThemeColor
        setThemeColor(QColor(0, 120, 215))

    def switch_mode(self, index):
        """切换模式"""
        self.stacked_widget.setCurrentIndex(index)

    def create_seq_to_images_ui(self):
        """创建 SEQ → 图像界面"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 10, 0, 0)
        layout.setSpacing(15)

        # 文件选择卡片
        file_card = CardWidget(widget)
        file_card.setStyleSheet("CardWidget { background-color: white; border-radius: 10px; }")
        file_layout = QVBoxLayout(file_card)
        file_layout.setContentsMargins(20, 20, 20, 20)
        file_layout.setSpacing(12)

        # SEQ 文件
        seq_label = BodyLabel('输入 SEQ 文件:', file_card)
        seq_label.setStyleSheet('color: #1a1a1a; font-size: 14px; font-weight: 500;')
        file_layout.addWidget(seq_label)

        seq_h_layout = QHBoxLayout()
        self.seq_path_edit = LineEdit(file_card)
        self.seq_path_edit.setPlaceholderText('选择 .seq 文件...')
        self.seq_path_edit.setReadOnly(True)
        seq_h_layout.addWidget(self.seq_path_edit)

        self.seq_browse_btn = PushButton('浏览', file_card, FluentIcon.FOLDER)
        self.seq_browse_btn.clicked.connect(self.browse_seq_file)
        seq_h_layout.addWidget(self.seq_browse_btn)
        file_layout.addLayout(seq_h_layout)

        # 输出目录
        output_label = BodyLabel('输出目录:', file_card)
        output_label.setStyleSheet('color: #1a1a1a; font-size: 14px; font-weight: 500;')
        file_layout.addWidget(output_label)

        output_h_layout = QHBoxLayout()
        self.output_dir_edit = LineEdit(file_card)
        self.output_dir_edit.setPlaceholderText('选择输出目录...')
        self.output_dir_edit.setReadOnly(True)
        output_h_layout.addWidget(self.output_dir_edit)

        self.output_dir_browse_btn = PushButton('浏览', file_card, FluentIcon.FOLDER)
        self.output_dir_browse_btn.clicked.connect(self.browse_output_dir)
        output_h_layout.addWidget(self.output_dir_browse_btn)
        file_layout.addLayout(output_h_layout)

        layout.addWidget(file_card)

        # 参数设置卡片
        param_card = CardWidget(widget)
        param_card.setStyleSheet("CardWidget { background-color: white; border-radius: 10px; }")
        param_layout = QVBoxLayout(param_card)
        param_layout.setContentsMargins(20, 20, 20, 20)
        param_layout.setSpacing(12)

        # 第一行：起始帧和结束帧
        row1_layout = QHBoxLayout()
        row1_layout.addWidget(BodyLabel('起始帧号:', param_card))
        self.s2i_start_spin = SpinBox(param_card)
        self.s2i_start_spin.setRange(0, 999999)
        self.s2i_start_spin.setValue(0)
        self.s2i_start_spin.setFixedWidth(120)
        row1_layout.addWidget(self.s2i_start_spin)

        row1_layout.addSpacing(20)
        row1_layout.addWidget(BodyLabel('结束帧号:', param_card))
        self.s2i_end_spin = SpinBox(param_card)
        self.s2i_end_spin.setRange(0, 999999)
        self.s2i_end_spin.setValue(0)
        self.s2i_end_spin.setSpecialValueText('全部')
        self.s2i_end_spin.setFixedWidth(120)
        row1_layout.addWidget(self.s2i_end_spin)
        row1_layout.addStretch()
        param_layout.addLayout(row1_layout)

        # 第二行：文件名前缀
        row2_layout = QHBoxLayout()
        row2_layout.addWidget(BodyLabel('文件名前缀:', param_card))
        self.s2i_prefix_edit = LineEdit(param_card)
        self.s2i_prefix_edit.setPlaceholderText('留空则使用时间戳')
        self.s2i_prefix_edit.setFixedWidth(200)
        row2_layout.addWidget(self.s2i_prefix_edit)

        self.timestamp_btn = TransparentPushButton('使用时间戳', param_card, FluentIcon.DATE_TIME)
        self.timestamp_btn.clicked.connect(lambda: self.use_timestamp(self.s2i_prefix_edit))
        row2_layout.addWidget(self.timestamp_btn)
        row2_layout.addStretch()
        param_layout.addLayout(row2_layout)

        # 第三行：输出格式
        row3_layout = QHBoxLayout()
        row3_layout.addWidget(BodyLabel('输出格式:', param_card))
        self.s2i_format_combo = ComboBox(param_card)
        self.s2i_format_combo.addItems(['PNG', 'TIFF', 'BMP'])
        self.s2i_format_combo.setFixedWidth(120)
        row3_layout.addWidget(self.s2i_format_combo)
        row3_layout.addStretch()
        param_layout.addLayout(row3_layout)

        layout.addWidget(param_card)

        return widget

    def create_images_to_output_ui(self):
        """创建 图像 → SEQ/视频 界面"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 10, 0, 0)
        layout.setSpacing(15)

        # 文件选择卡片
        file_card = CardWidget(widget)
        file_card.setStyleSheet("CardWidget { background-color: white; border-radius: 10px; }")
        file_layout = QVBoxLayout(file_card)
        file_layout.setContentsMargins(20, 20, 20, 20)
        file_layout.setSpacing(12)

        # 输入目录
        input_label = BodyLabel('输入图像目录:', file_card)
        input_label.setStyleSheet('color: #1a1a1a; font-size: 14px; font-weight: 500;')
        file_layout.addWidget(input_label)

        input_h_layout = QHBoxLayout()
        self.input_dir_edit = LineEdit(file_card)
        self.input_dir_edit.setPlaceholderText('选择包含图像的目录...')
        self.input_dir_edit.setReadOnly(True)
        input_h_layout.addWidget(self.input_dir_edit)

        self.input_dir_browse_btn = PushButton('浏览', file_card, FluentIcon.FOLDER)
        self.input_dir_browse_btn.clicked.connect(self.browse_input_dir)
        input_h_layout.addWidget(self.input_dir_browse_btn)
        file_layout.addLayout(input_h_layout)

        # 输出文件
        output_file_label = BodyLabel('输出文件:', file_card)
        output_file_label.setStyleSheet('color: #1a1a1a; font-size: 14px; font-weight: 500;')
        file_layout.addWidget(output_file_label)

        output_file_h_layout = QHBoxLayout()
        self.output_file_edit = LineEdit(file_card)
        self.output_file_edit.setPlaceholderText('选择输出文件路径...')
        self.output_file_edit.setReadOnly(True)
        output_file_h_layout.addWidget(self.output_file_edit)

        self.output_file_browse_btn = PushButton('浏览', file_card, FluentIcon.SAVE)
        self.output_file_browse_btn.clicked.connect(self.browse_output_file)
        output_file_h_layout.addWidget(self.output_file_browse_btn)
        file_layout.addLayout(output_file_h_layout)

        layout.addWidget(file_card)

        # 参数设置卡片
        param_card = CardWidget(widget)
        param_card.setStyleSheet("CardWidget { background-color: white; border-radius: 10px; }")
        param_layout = QVBoxLayout(param_card)
        param_layout.setContentsMargins(20, 20, 20, 20)
        param_layout.setSpacing(12)

        # 第一行：输出类型和输入格式
        row1_layout = QHBoxLayout()
        row1_layout.addWidget(BodyLabel('输出类型:', param_card))
        self.i2o_output_type_combo = ComboBox(param_card)
        self.i2o_output_type_combo.addItems(['SEQ', 'AVI', 'MP4', 'MOV'])
        self.i2o_output_type_combo.currentIndexChanged.connect(self.on_output_type_changed)
        self.i2o_output_type_combo.setFixedWidth(120)
        row1_layout.addWidget(self.i2o_output_type_combo)

        row1_layout.addSpacing(20)
        row1_layout.addWidget(BodyLabel('输入图像格式:', param_card))
        self.i2o_image_format_combo = ComboBox(param_card)
        self.i2o_image_format_combo.addItems(['全部', 'PNG', 'BMP', 'TIFF'])
        self.i2o_image_format_combo.setFixedWidth(120)
        row1_layout.addWidget(self.i2o_image_format_combo)
        row1_layout.addStretch()
        param_layout.addLayout(row1_layout)

        # 第二行：帧率和位深度/编码
        row2_layout = QHBoxLayout()
        row2_layout.addWidget(BodyLabel('帧率 (fps):', param_card))
        self.i2o_framerate_spin = DoubleSpinBox(param_card)
        self.i2o_framerate_spin.setRange(1.0, 240.0)
        self.i2o_framerate_spin.setValue(30.0)
        self.i2o_framerate_spin.setDecimals(1)
        self.i2o_framerate_spin.setFixedWidth(120)
        row2_layout.addWidget(self.i2o_framerate_spin)

        row2_layout.addSpacing(20)
        # SEQ 特有参数：位深度
        self.seq_bitdepth_label = BodyLabel('位深度:', param_card)
        row2_layout.addWidget(self.seq_bitdepth_label)
        self.i2o_bitdepth_combo = ComboBox(param_card)
        self.i2o_bitdepth_combo.addItems(['8', '16', '24'])
        self.i2o_bitdepth_combo.setCurrentIndex(0)
        self.i2o_bitdepth_combo.setFixedWidth(120)
        row2_layout.addWidget(self.i2o_bitdepth_combo)

        # 视频特有参数：编码
        self.video_codec_label = BodyLabel('视频编码:', param_card)
        row2_layout.addWidget(self.video_codec_label)
        self.i2o_codec_combo = ComboBox(param_card)
        self.i2o_codec_combo.addItems(['auto', 'libxvid', 'libx264', 'libx265'])
        self.i2o_codec_combo.setFixedWidth(120)
        row2_layout.addWidget(self.i2o_codec_combo)
        row2_layout.addStretch()
        param_layout.addLayout(row2_layout)

        # 第三行：视频质量
        row3_layout = QHBoxLayout()
        self.video_quality_label = BodyLabel('视频质量:', param_card)
        row3_layout.addWidget(self.video_quality_label)
        self.i2o_quality_combo = ComboBox(param_card)
        self.i2o_quality_combo.addItems(['low', 'medium', 'high', 'best'])
        self.i2o_quality_combo.setCurrentIndex(2)
        self.i2o_quality_combo.setFixedWidth(120)
        row3_layout.addWidget(self.i2o_quality_combo)
        row3_layout.addStretch()
        param_layout.addLayout(row3_layout)

        # 第四行：帧范围
        row4_layout = QHBoxLayout()
        row4_layout.addWidget(BodyLabel('起始帧号:', param_card))
        self.i2o_start_spin = SpinBox(param_card)
        self.i2o_start_spin.setRange(0, 999999)
        self.i2o_start_spin.setValue(0)
        self.i2o_start_spin.setSpecialValueText('起始')
        self.i2o_start_spin.setFixedWidth(120)
        row4_layout.addWidget(self.i2o_start_spin)

        row4_layout.addSpacing(20)
        row4_layout.addWidget(BodyLabel('结束帧号:', param_card))
        self.i2o_end_spin = SpinBox(param_card)
        self.i2o_end_spin.setRange(0, 999999)
        self.i2o_end_spin.setValue(0)
        self.i2o_end_spin.setSpecialValueText('末尾')
        self.i2o_end_spin.setFixedWidth(120)
        row4_layout.addWidget(self.i2o_end_spin)
        row4_layout.addStretch()
        param_layout.addLayout(row4_layout)

        layout.addWidget(param_card)

        # 初始化参数显示
        self.on_output_type_changed(0)

        return widget

    def create_seq_roi_crop_ui(self):
        """创建 SEQ ROI 裁剪界面"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 10, 0, 0)
        layout.setSpacing(15)

        # 文件选择卡片
        file_card = CardWidget(widget)
        file_card.setStyleSheet("CardWidget { background-color: white; border-radius: 10px; }")
        file_layout = QVBoxLayout(file_card)
        file_layout.setContentsMargins(20, 20, 20, 20)
        file_layout.setSpacing(12)

        # 输入 SEQ 文件
        input_label = BodyLabel('输入 SEQ 文件:', file_card)
        input_label.setStyleSheet('color: #1a1a1a; font-size: 14px; font-weight: 500;')
        file_layout.addWidget(input_label)

        input_h_layout = QHBoxLayout()
        self.roi_input_seq_edit = LineEdit(file_card)
        self.roi_input_seq_edit.setPlaceholderText('选择 .seq 文件...')
        self.roi_input_seq_edit.setReadOnly(True)
        input_h_layout.addWidget(self.roi_input_seq_edit)

        self.roi_input_browse_btn = PushButton('浏览', file_card, FluentIcon.FOLDER)
        self.roi_input_browse_btn.clicked.connect(self.browse_roi_input_seq)
        input_h_layout.addWidget(self.roi_input_browse_btn)
        file_layout.addLayout(input_h_layout)

        # 输出 SEQ 文件
        output_label = BodyLabel('输出 SEQ 文件:', file_card)
        output_label.setStyleSheet('color: #1a1a1a; font-size: 14px; font-weight: 500;')
        file_layout.addWidget(output_label)

        output_h_layout = QHBoxLayout()
        self.roi_output_seq_edit = LineEdit(file_card)
        self.roi_output_seq_edit.setPlaceholderText('选择输出文件路径...')
        self.roi_output_seq_edit.setReadOnly(True)
        output_h_layout.addWidget(self.roi_output_seq_edit)

        self.roi_output_browse_btn = PushButton('浏览', file_card, FluentIcon.SAVE)
        self.roi_output_browse_btn.clicked.connect(self.browse_roi_output_seq)
        output_h_layout.addWidget(self.roi_output_browse_btn)
        file_layout.addLayout(output_h_layout)

        layout.addWidget(file_card)

        # 图像预览卡片
        preview_card = CardWidget(widget)
        preview_card.setStyleSheet("CardWidget { background-color: white; border-radius: 10px; }")
        preview_layout = QVBoxLayout(preview_card)
        preview_layout.setContentsMargins(20, 20, 20, 20)
        preview_layout.setSpacing(12)

        preview_title = BodyLabel('图像预览 (红色框为ROI区域):', preview_card)
        preview_title.setStyleSheet('color: #1a1a1a; font-size: 14px; font-weight: 500;')
        preview_layout.addWidget(preview_title)

        # 预览图像控件（自定义控件，支持刻度尺和ROI显示）
        self.roi_preview_widget = ImagePreviewWidget(preview_card)
        preview_layout.addWidget(self.roi_preview_widget)

        # 帧号选择和浏览按钮
        frame_h_layout = QHBoxLayout()
        frame_h_layout.addWidget(BodyLabel('预览帧号:', preview_card))
        self.roi_preview_frame_spin = SpinBox(preview_card)
        self.roi_preview_frame_spin.setRange(0, 0)
        self.roi_preview_frame_spin.setValue(0)
        self.roi_preview_frame_spin.setEnabled(False)
        frame_h_layout.addWidget(self.roi_preview_frame_spin)

        self.roi_preview_btn = PushButton('刷新预览', preview_card, FluentIcon.VIEW)
        self.roi_preview_btn.clicked.connect(self.preview_roi_frame)
        self.roi_preview_btn.setEnabled(False)
        frame_h_layout.addWidget(self.roi_preview_btn)

        frame_h_layout.addStretch()
        preview_layout.addLayout(frame_h_layout)

        layout.addWidget(preview_card)

        # ROI 参数设置卡片
        roi_param_card = CardWidget(widget)
        roi_param_card.setStyleSheet("CardWidget { background-color: white; border-radius: 10px; }")
        roi_param_layout = QVBoxLayout(roi_param_card)
        roi_param_layout.setContentsMargins(20, 20, 20, 20)
        roi_param_layout.setSpacing(12)

        # 第一行：ROI 中心坐标
        row1_layout = QHBoxLayout()
        row1_layout.addWidget(BodyLabel('ROI 中心 X:', roi_param_card))
        self.roi_center_x_spin = SpinBox(roi_param_card)
        self.roi_center_x_spin.setRange(0, 9999)
        self.roi_center_x_spin.setValue(1280)
        self.roi_center_x_spin.setFixedWidth(120)
        row1_layout.addWidget(self.roi_center_x_spin)

        row1_layout.addSpacing(20)
        row1_layout.addWidget(BodyLabel('ROI 中心 Y:', roi_param_card))
        self.roi_center_y_spin = SpinBox(roi_param_card)
        self.roi_center_y_spin.setRange(0, 9999)
        self.roi_center_y_spin.setValue(958)
        self.roi_center_y_spin.setFixedWidth(120)
        row1_layout.addWidget(self.roi_center_y_spin)
        row1_layout.addStretch()
        roi_param_layout.addLayout(row1_layout)

        # 第二行：ROI 尺寸
        row2_layout = QHBoxLayout()
        row2_layout.addWidget(BodyLabel('ROI 宽度:', roi_param_card))
        self.roi_width_spin = SpinBox(roi_param_card)
        self.roi_width_spin.setRange(1, 9999)
        self.roi_width_spin.setValue(800)
        self.roi_width_spin.setFixedWidth(120)
        row2_layout.addWidget(self.roi_width_spin)

        row2_layout.addSpacing(20)
        row2_layout.addWidget(BodyLabel('ROI 高度:', roi_param_card))
        self.roi_height_spin = SpinBox(roi_param_card)
        self.roi_height_spin.setRange(1, 9999)
        self.roi_height_spin.setValue(600)
        self.roi_height_spin.setFixedWidth(120)
        row2_layout.addWidget(self.roi_height_spin)
        row2_layout.addStretch()
        roi_param_layout.addLayout(row2_layout)

        # 添加提示信息
        info_label = BodyLabel('提示: 输出文件名将自动添加 ROI 左上角坐标后缀', roi_param_card)
        info_label.setStyleSheet('color: #666666; font-size: 12px; font-style: italic;')
        roi_param_layout.addWidget(info_label)

        layout.addWidget(roi_param_card)

        # 存储 cropper 对象
        self.seq_cropper = None

        # 连接 ROI 参数变化信号
        self.roi_center_x_spin.valueChanged.connect(self.update_roi_preview)
        self.roi_center_y_spin.valueChanged.connect(self.update_roi_preview)
        self.roi_width_spin.valueChanged.connect(self.update_roi_preview)
        self.roi_height_spin.valueChanged.connect(self.update_roi_preview)

        return widget

    def on_output_type_changed(self, index):
        """输出类型改变时更新界面"""
        output_type = self.i2o_output_type_combo.currentText()
        is_seq = (output_type == 'SEQ')

        # SEQ 特有参数
        self.seq_bitdepth_label.setVisible(is_seq)
        self.i2o_bitdepth_combo.setVisible(is_seq)

        # 视频特有参数
        self.video_codec_label.setVisible(not is_seq)
        self.i2o_codec_combo.setVisible(not is_seq)
        self.video_quality_label.setVisible(not is_seq)
        self.i2o_quality_combo.setVisible(not is_seq)

    def create_shared_ui(self, h_layout):
        """创建共享的进度和日志区域（右侧竖向布局）"""
        # 右侧容器
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(15)

        # 进度卡片
        progress_card = CardWidget(right_widget)
        progress_card.setStyleSheet("CardWidget { background-color: white; border-radius: 10px; }")
        progress_layout = QVBoxLayout(progress_card)
        progress_layout.setContentsMargins(20, 20, 20, 20)
        progress_layout.setSpacing(12)

        progress_title = BodyLabel('转换进度:', progress_card)
        progress_title.setStyleSheet('color: #1a1a1a; font-size: 14px; font-weight: 500;')
        progress_layout.addWidget(progress_title)

        self.progress_bar = ProgressBar(progress_card)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        progress_layout.addWidget(self.progress_bar)

        self.progress_label = BodyLabel('等待开始...', progress_card)
        self.progress_label.setAlignment(Qt.AlignCenter)
        progress_layout.addWidget(self.progress_label)

        right_layout.addWidget(progress_card)

        # 日志卡片（占据剩余空间）
        log_card = CardWidget(right_widget)
        log_card.setStyleSheet("CardWidget { background-color: white; border-radius: 10px; }")
        log_layout = QVBoxLayout(log_card)
        log_layout.setContentsMargins(20, 20, 20, 20)
        log_layout.setSpacing(12)

        log_title = BodyLabel('日志:', log_card)
        log_title.setStyleSheet('color: #1a1a1a; font-size: 14px; font-weight: 500;')
        log_layout.addWidget(log_title)

        self.log_text = QTextEdit(log_card)
        self.log_text.setReadOnly(True)
        self.log_text.setStyleSheet("""
            QTextEdit {
                background-color: #f9f9f9;
                color: #1a1a1a;
                border: 1px solid #e0e0e0;
                border-radius: 8px;
                padding: 10px;
                font-family: Consolas, 'Microsoft YaHei', monospace;
                font-size: 13px;
            }
        """)
        log_layout.addWidget(self.log_text)

        right_layout.addWidget(log_card, stretch=1)  # 日志卡片占据剩余空间

        # 将右侧容器添加到水平布局
        h_layout.addWidget(right_widget, stretch=3)  # 右侧占30%

    def create_button_ui(self, v_layout):
        """创建按钮区域"""
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.start_btn = PushButton('开始转换', self, FluentIcon.PLAY)
        self.start_btn.clicked.connect(self.start_conversion)
        self.start_btn.setMinimumWidth(140)
        self.start_btn.setMinimumHeight(40)
        button_layout.addWidget(self.start_btn)

        button_layout.addSpacing(10)

        self.stop_btn = PushButton('停止', self, FluentIcon.CANCEL)
        self.stop_btn.clicked.connect(self.stop_conversion)
        self.stop_btn.setEnabled(False)
        self.stop_btn.setMinimumWidth(140)
        self.stop_btn.setMinimumHeight(40)
        button_layout.addWidget(self.stop_btn)

        v_layout.addLayout(button_layout)

    def browse_seq_file(self):
        """浏览 SEQ 文件"""
        file_path, _ = QFileDialog.getOpenFileName(self, '选择 SEQ 文件', '', 'SEQ Files (*.seq);;All Files (*.*)')
        if file_path:
            self.seq_path_edit.setText(file_path)
            if not self.output_dir_edit.text():
                seq_basename = os.path.splitext(os.path.basename(file_path))[0]
                output_dir = os.path.join(os.path.dirname(file_path), f"{seq_basename}_frames")
                self.output_dir_edit.setText(output_dir)
            self.add_log(f'选择文件: {file_path}')

    def browse_output_dir(self):
        """浏览输出目录"""
        dir_path = QFileDialog.getExistingDirectory(self, '选择输出目录', '')
        if dir_path:
            self.output_dir_edit.setText(dir_path)
            self.add_log(f'输出目录: {dir_path}')

    def browse_input_dir(self):
        """浏览输入目录"""
        dir_path = QFileDialog.getExistingDirectory(self, '选择输入图像目录', '')
        if dir_path:
            self.input_dir_edit.setText(dir_path)
            self.add_log(f'输入目录: {dir_path}')

    def browse_output_file(self):
        """浏览输出文件"""
        output_type = self.i2o_output_type_combo.currentText().lower()
        filters = {
            'seq': 'SEQ Files (*.seq)',
            'avi': 'AVI Files (*.avi)',
            'mp4': 'MP4 Files (*.mp4)',
            'mov': 'MOV Files (*.mov)'
        }
        file_filter = filters.get(output_type, 'All Files (*.*)')

        file_path, _ = QFileDialog.getSaveFileName(self, '保存输出文件', '', file_filter)
        if file_path:
            # 确保文件扩展名正确
            if not file_path.lower().endswith(f'.{output_type}'):
                file_path += f'.{output_type}'
            self.output_file_edit.setText(file_path)
            self.add_log(f'输出文件: {file_path}')

    def browse_roi_input_seq(self):
        """浏览 ROI 裁剪的输入 SEQ 文件"""
        file_path, _ = QFileDialog.getOpenFileName(self, '选择 SEQ 文件', '', 'SEQ Files (*.seq);;All Files (*.*)')
        if file_path:
            self.roi_input_seq_edit.setText(file_path)

            # 自动生成输出文件名
            if not self.roi_output_seq_edit.text():
                seq_dir = os.path.dirname(file_path)
                seq_basename = os.path.splitext(os.path.basename(file_path))[0]
                output_path = os.path.join(seq_dir, f"{seq_basename}_ROI.seq")
                self.roi_output_seq_edit.setText(output_path)

            # 加载 SEQ 文件头信息
            self.seq_cropper = SeqCropper(file_path)
            if self.seq_cropper.load_header():
                # 启用预览功能
                self.roi_preview_frame_spin.setEnabled(True)
                self.roi_preview_frame_spin.setRange(0, self.seq_cropper.reader.frame_count - 1)
                self.roi_preview_btn.setEnabled(True)

                # 更新 ROI 参数范围
                self.roi_center_x_spin.setRange(0, self.seq_cropper.reader.width)
                self.roi_center_x_spin.setValue(self.seq_cropper.reader.width // 2)
                self.roi_center_y_spin.setRange(0, self.seq_cropper.reader.height)
                self.roi_center_y_spin.setValue(self.seq_cropper.reader.height // 2)
                self.roi_width_spin.setRange(1, self.seq_cropper.reader.width)
                self.roi_height_spin.setRange(1, self.seq_cropper.reader.height)

                self.add_log(f'选择文件: {file_path}')
                self.add_log(f'图像尺寸: {self.seq_cropper.reader.width} x {self.seq_cropper.reader.height}')
                self.add_log(f'总帧数: {self.seq_cropper.reader.frame_count}')

                # 自动预览第一帧
                self.preview_roi_frame()
            else:
                InfoBar.error(title='错误', content='无法加载 SEQ 文件头', parent=self, position=InfoBarPosition.TOP, duration=3000)

    def browse_roi_output_seq(self):
        """浏览 ROI 裁剪的输出 SEQ 文件"""
        file_path, _ = QFileDialog.getSaveFileName(self, '保存输出 SEQ 文件', '', 'SEQ Files (*.seq)')
        if file_path:
            if not file_path.lower().endswith('.seq'):
                file_path += '.seq'
            self.roi_output_seq_edit.setText(file_path)
            self.add_log(f'输出文件: {file_path}')

    def preview_roi_frame(self):
        """预览指定帧"""
        if not self.seq_cropper or not self.seq_cropper.header_loaded:
            InfoBar.warning(title='提示', content='请先选择 SEQ 文件', parent=self, position=InfoBarPosition.TOP, duration=2000)
            return

        frame_num = self.roi_preview_frame_spin.value()
        img = self.seq_cropper.get_frame_image(frame_num)

        if img:
            # 转换为 QPixmap
            import io
            img_byte_arr = io.BytesIO()
            img.save(img_byte_arr, format='PNG')
            img_byte_arr.seek(0)

            pixmap = QPixmap()
            pixmap.loadFromData(img_byte_arr.read())

            # 设置图像到预览控件
            self.roi_preview_widget.set_image(
                pixmap,
                self.seq_cropper.reader.width,
                self.seq_cropper.reader.height
            )

            # 更新ROI显示
            self.update_roi_preview()

            self.add_log(f'预览帧 {frame_num}')
        else:
            InfoBar.error(title='错误', content=f'无法读取帧 {frame_num}', parent=self, position=InfoBarPosition.TOP, duration=3000)

    def update_roi_preview(self):
        """更新ROI预览显示"""
        if hasattr(self, 'roi_preview_widget') and self.roi_preview_widget.pixmap is not None:
            self.roi_preview_widget.set_roi(
                self.roi_center_x_spin.value(),
                self.roi_center_y_spin.value(),
                self.roi_width_spin.value(),
                self.roi_height_spin.value()
            )

    def use_timestamp(self, line_edit):
        """使用时间戳"""
        from datetime import datetime
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        line_edit.setText(timestamp)
        self.add_log(f'设置前缀: {timestamp}')

    def add_log(self, message):
        """添加日志"""
        self.log_text.append(message)

    def start_conversion(self):
        """开始转换"""
        mode_index = self.stacked_widget.currentIndex()

        if mode_index == 0:
            # SEQ → 图像
            self.start_seq_to_images()
        elif mode_index == 1:
            # 图像 → SEQ/视频
            self.start_images_to_output()
        else:
            # SEQ ROI 裁剪
            self.start_seq_roi_crop()

    def start_seq_to_images(self):
        """SEQ → 图像转换"""
        seq_file = self.seq_path_edit.text()
        output_dir = self.output_dir_edit.text()

        if not seq_file or not os.path.exists(seq_file):
            InfoBar.error(title='错误', content='请选择有效的 SEQ 文件', parent=self, position=InfoBarPosition.TOP, duration=3000)
            return

        if not output_dir:
            InfoBar.error(title='错误', content='请选择输出目录', parent=self, position=InfoBarPosition.TOP, duration=3000)
            return

        start_frame = self.s2i_start_spin.value()
        end_frame = self.s2i_end_spin.value() if self.s2i_end_spin.value() > 0 else None
        prefix = self.s2i_prefix_edit.text() or self.get_timestamp()
        format = self.s2i_format_combo.currentText()

        self.reset_ui()
        self.convert_thread = SeqToImagesThread(seq_file, output_dir, start_frame, end_frame, prefix, format)
        self.connect_thread_signals()
        self.convert_thread.start()

    def start_images_to_output(self):
        """图像 → SEQ/视频转换"""
        input_dir = self.input_dir_edit.text()
        output_file = self.output_file_edit.text()

        if not input_dir or not os.path.isdir(input_dir):
            InfoBar.error(title='错误', content='请选择有效的输入目录', parent=self, position=InfoBarPosition.TOP, duration=3000)
            return

        if not output_file:
            InfoBar.error(title='错误', content='请指定输出文件', parent=self, position=InfoBarPosition.TOP, duration=3000)
            return

        output_type = self.i2o_output_type_combo.currentText()
        image_format = self.i2o_image_format_combo.currentText()
        if image_format == '全部':
            image_format = 'all'

        frame_rate = self.i2o_framerate_spin.value()
        start_frame = self.i2o_start_spin.value() if self.i2o_start_spin.value() > 0 else None
        end_frame = self.i2o_end_spin.value() if self.i2o_end_spin.value() > 0 else None

        self.reset_ui()

        if output_type == 'SEQ':
            bit_depth = int(self.i2o_bitdepth_combo.currentText())
            self.convert_thread = ImagesToSeqThread(input_dir, output_file, image_format, bit_depth, frame_rate, start_frame, end_frame)
        else:
            codec = self.i2o_codec_combo.currentText()
            quality = self.i2o_quality_combo.currentText()
            self.convert_thread = ImagesToVideoThread(input_dir, output_file, image_format, frame_rate, codec, quality, start_frame, end_frame)

        self.connect_thread_signals()
        self.convert_thread.start()

    def start_seq_roi_crop(self):
        """SEQ ROI 裁剪"""
        input_seq = self.roi_input_seq_edit.text()
        output_seq = self.roi_output_seq_edit.text()

        if not input_seq or not os.path.exists(input_seq):
            InfoBar.error(title='错误', content='请选择有效的输入 SEQ 文件', parent=self, position=InfoBarPosition.TOP, duration=3000)
            return

        if not output_seq:
            InfoBar.error(title='错误', content='请指定输出 SEQ 文件', parent=self, position=InfoBarPosition.TOP, duration=3000)
            return

        # 获取 ROI 参数
        roi_center_x = self.roi_center_x_spin.value()
        roi_center_y = self.roi_center_y_spin.value()
        roi_width = self.roi_width_spin.value()
        roi_height = self.roi_height_spin.value()

        # 计算 ROI 左上角坐标用于文件名
        roi_x = roi_center_x - roi_width // 2
        roi_y = roi_center_y - roi_height // 2

        # 自动修改输出文件名，添加 ROI 坐标后缀
        output_dir = os.path.dirname(output_seq)
        output_basename = os.path.splitext(os.path.basename(output_seq))[0]

        # 移除可能已存在的 ROI 后缀
        if '_ROI_' in output_basename:
            output_basename = output_basename.split('_ROI_')[0]

        # 添加新的 ROI 坐标后缀
        output_basename_with_roi = f"{output_basename}_ROI_{roi_x}_{roi_y}"
        output_seq = os.path.join(output_dir, f"{output_basename_with_roi}.seq")
        self.roi_output_seq_edit.setText(output_seq)

        self.reset_ui()
        self.convert_thread = SeqRoiCropThread(input_seq, output_seq, roi_center_x, roi_center_y, roi_width, roi_height)
        self.connect_thread_signals()
        self.convert_thread.start()

    def reset_ui(self):
        """重置 UI 状态"""
        self.log_text.clear()
        self.progress_bar.setValue(0)
        self.progress_label.setText('准备开始...')
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.add_log('=' * 50)
        self.add_log('开始转换...')

    def connect_thread_signals(self):
        """连接线程信号"""
        self.convert_thread.progress.connect(self.on_progress)
        self.convert_thread.finished.connect(self.on_finished)
        self.convert_thread.log.connect(self.add_log)

    def stop_conversion(self):
        """停止转换"""
        if self.convert_thread and self.convert_thread.isRunning():
            self.add_log('正在停止转换...')
            self.convert_thread.stop()
            self.convert_thread.wait()

    def on_progress(self, current, total):
        """更新进度"""
        if total > 0:
            progress = int((current / total) * 100)
            self.progress_bar.setValue(progress)
            self.progress_label.setText(f'已处理: {current}/{total} 帧 ({progress}%)')

    def on_finished(self, success, message):
        """转换完成"""
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.add_log('=' * 50)

        if success:
            self.progress_bar.setValue(100)
            self.progress_label.setText('转换完成!')
            self.add_log(f'成功: {message}')
            InfoBar.success(title='成功', content=message, parent=self, position=InfoBarPosition.TOP, duration=5000)
        else:
            self.progress_label.setText('转换失败')
            self.add_log(f'失败: {message}')
            InfoBar.error(title='错误', content=message, parent=self, position=InfoBarPosition.TOP, duration=5000)

    def get_timestamp(self):
        """获取时间戳"""
        from datetime import datetime
        return datetime.now().strftime('%Y%m%d_%H%M%S')


def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    window = ConverterGUI()
    window.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
