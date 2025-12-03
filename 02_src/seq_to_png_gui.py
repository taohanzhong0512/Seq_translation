import sys
import os
from pathlib import Path
from PyQt5.QtWidgets import QApplication, QWidget, QFileDialog
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QIcon, QPixmap, QPalette, QColor, QBrush, QPainter
from qfluentwidgets import (
    PushButton, LineEdit, SpinBox, ComboBox, ProgressBar,
    setTheme, Theme, FluentIcon, InfoBar, InfoBarPosition,
    CardWidget, BodyLabel, StrongBodyLabel, TransparentPushButton
)
from PyQt5.QtWidgets import QVBoxLayout, QHBoxLayout, QGridLayout, QSizePolicy, QLabel

from seq_to_png import SeqReader


def resource_path(relative_path):
    """获取资源文件的绝对路径，支持打包后的环境"""
    try:
        # PyInstaller 创建临时文件夹，将路径存储在 _MEIPASS 中
        base_path = sys._MEIPASS
    except Exception:
        # 开发环境中使用相对路径
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)


class ConvertThread(QThread):
    """后台转换线程"""
    progress = pyqtSignal(int, int)  # current, total
    finished = pyqtSignal(bool, str)  # success, message
    log = pyqtSignal(str)  # log message

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
            # 创建 SeqReader
            reader = SeqReader(self.seq_file)

            # 读取文件头
            self.log.emit("正在读取 SEQ 文件头信息...")
            success = reader.read_header()

            if not success:
                self.finished.emit(False, "无法识别 SEQ 文件格式")
                return

            # 确定帧范围
            if self.end_frame is None or self.end_frame <= 0:
                self.end_frame = reader.frame_count

            self.end_frame = min(self.end_frame, reader.frame_count)

            if self.start_frame >= self.end_frame:
                self.finished.emit(False, "起始帧号必须小于结束帧号")
                return

            # 格式化图像格式
            self.format = self.format.upper()
            if self.format not in ["PNG", "TIFF", "BMP"]:
                self.finished.emit(False, f"不支持的图像格式 '{self.format}'")
                return

            # 获取文件扩展名
            ext = self.format.lower()
            if self.format == "TIFF":
                ext = "tif"

            self.log.emit(f"开始转换: 帧 {self.start_frame} 到 {self.end_frame-1} (共 {self.end_frame - self.start_frame} 帧)")
            self.log.emit(f"输出格式: {self.format}")

            # 创建输出目录
            if not os.path.exists(self.output_dir):
                os.makedirs(self.output_dir)
                self.log.emit(f"创建输出目录: {self.output_dir}")

            # 计算参数
            bytes_per_pixel = reader.bit_depth // 8
            if reader.bit_depth % 8 != 0:
                bytes_per_pixel += 1

            expected_image_size = reader.width * reader.height * bytes_per_pixel

            if reader.true_image_size > 0:
                frame_size = reader.true_image_size
            else:
                frame_size = expected_image_size

            # 转换帧
            import numpy as np
            from PIL import Image

            with open(self.seq_file, 'rb') as f:
                for frame_num in range(self.start_frame, self.end_frame):
                    if not self._is_running:
                        self.finished.emit(False, "转换已取消")
                        return

                    # 跳转到指定帧
                    offset = reader.header_size + frame_num * frame_size
                    f.seek(offset)

                    # 读取帧数据
                    frame_data = f.read(frame_size)

                    if len(frame_data) < frame_size:
                        self.log.emit(f"警告: 帧 {frame_num} 数据不完整，跳过")
                        continue

                    # 跳过帧头
                    if reader.frame_header_size > 0:
                        frame_data = frame_data[reader.frame_header_size:]

                    # 解析图像数据
                    if reader.bit_depth == 8:
                        img_array = np.frombuffer(frame_data, dtype=np.uint8)
                        expected_pixels = reader.width * reader.height
                        actual_bytes = len(img_array)

                        if actual_bytes >= expected_pixels:
                            bytes_per_row = actual_bytes // reader.height
                            img_array = img_array[:reader.height * bytes_per_row].reshape((reader.height, bytes_per_row))
                            img_array = img_array[:, :reader.width]
                        else:
                            img_array = img_array.reshape((reader.height, reader.width))

                        img = Image.fromarray(img_array, mode='L')

                    elif reader.bit_depth == 16:
                        img_array = np.frombuffer(frame_data, dtype=np.uint16)
                        expected_pixels = reader.width * reader.height
                        actual_pixels = len(img_array)

                        if actual_pixels >= expected_pixels:
                            pixels_per_row = actual_pixels // reader.height
                            img_array = img_array[:reader.height * pixels_per_row].reshape((reader.height, pixels_per_row))
                            img_array = img_array[:, :reader.width]
                        else:
                            img_array = img_array.reshape((reader.height, reader.width))

                        img_array_8bit = (img_array / 256).astype(np.uint8)
                        img = Image.fromarray(img_array_8bit, mode='L')

                    elif reader.bit_depth == 24:
                        img_array = np.frombuffer(frame_data, dtype=np.uint8)
                        expected_bytes = reader.width * reader.height * 3
                        actual_bytes = len(img_array)

                        if actual_bytes >= expected_bytes:
                            bytes_per_row = actual_bytes // reader.height
                            img_array = img_array[:reader.height * bytes_per_row].reshape((reader.height, bytes_per_row))
                            img_array = img_array[:, :reader.width * 3]
                            img_array = img_array.reshape((reader.height, reader.width, 3))
                        else:
                            img_array = img_array.reshape((reader.height, reader.width, 3))

                        img = Image.fromarray(img_array, mode='RGB')

                    else:
                        self.finished.emit(False, f"不支持的位深度: {reader.bit_depth}")
                        return

                    # 保存图像
                    output_filename = f"{self.prefix}_{frame_num:06d}.{ext}"
                    output_path = os.path.join(self.output_dir, output_filename)
                    img.save(output_path, format=self.format)

                    # 发送进度
                    self.progress.emit(frame_num - self.start_frame + 1, self.end_frame - self.start_frame)

            self.finished.emit(True, f"成功转换 {self.end_frame - self.start_frame} 帧!")

        except Exception as e:
            import traceback
            error_msg = f"转换失败: {str(e)}\n{traceback.format_exc()}"
            self.log.emit(error_msg)
            self.finished.emit(False, str(e))

    def stop(self):
        self._is_running = False


class SeqToPngGUI(QWidget):
    def __init__(self):
        super().__init__()
        self.convert_thread = None
        self.initUI()

    def initUI(self):
        self.setWindowTitle('SEQ to PNG Converter')
        self.resize(850, 700)

        # 设置窗口图标
        icon_path = resource_path(os.path.join('image', 'DCS_Application_Logo.ico'))
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        else:
            # 开发环境备用路径
            icon_path_dev = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'image', 'DCS_Application_Logo.ico')
            if os.path.exists(icon_path_dev):
                self.setWindowIcon(QIcon(icon_path_dev))

        # 设置窗口背景为白色
        self.setStyleSheet("""
            SeqToPngGUI {
                background-color: #f5f5f5;
            }
        """)

        # 主布局
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)

        # 标题栏布局（包含 SIOM logo）
        header_layout = QHBoxLayout()

        # 标题
        title_label = StrongBodyLabel('SEQ 文件转图像序列', self)
        title_label.setStyleSheet('font-size: 24px; font-weight: bold; color: #0078d7;')
        header_layout.addWidget(title_label)

        header_layout.addStretch()

        # SIOM logo
        siom_logo_path = resource_path(os.path.join('image', 'SIOM_logo.png'))
        if not os.path.exists(siom_logo_path):
            # 开发环境备用路径
            siom_logo_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'image', 'SIOM_logo.png')

        if os.path.exists(siom_logo_path):
            siom_label = QLabel(self)
            siom_pixmap = QPixmap(siom_logo_path)
            # 调整 logo 大小
            siom_pixmap = siom_pixmap.scaled(80, 80, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            siom_label.setPixmap(siom_pixmap)
            header_layout.addWidget(siom_label)

        main_layout.addLayout(header_layout)

        # 文件选择卡片
        file_card = CardWidget(self)
        file_card.setStyleSheet("""
            CardWidget {
                background-color: white;
                border-radius: 10px;
            }
        """)
        file_layout = QVBoxLayout(file_card)
        file_layout.setContentsMargins(20, 20, 20, 20)
        file_layout.setSpacing(12)

        # SEQ 文件选择
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

        # 输出目录选择
        output_label = BodyLabel('输出目录:', file_card)
        output_label.setStyleSheet('color: #1a1a1a; font-size: 14px; font-weight: 500;')
        file_layout.addWidget(output_label)

        output_h_layout = QHBoxLayout()
        self.output_path_edit = LineEdit(file_card)
        self.output_path_edit.setPlaceholderText('选择输出目录...')
        self.output_path_edit.setReadOnly(True)
        output_h_layout.addWidget(self.output_path_edit)

        self.output_browse_btn = PushButton('浏览', file_card, FluentIcon.FOLDER)
        self.output_browse_btn.clicked.connect(self.browse_output_dir)
        output_h_layout.addWidget(self.output_browse_btn)
        file_layout.addLayout(output_h_layout)

        main_layout.addWidget(file_card)

        # 参数设置卡片
        param_card = CardWidget(self)
        param_card.setStyleSheet("""
            CardWidget {
                background-color: white;
                border-radius: 10px;
            }
        """)
        param_layout = QGridLayout(param_card)
        param_layout.setContentsMargins(20, 20, 20, 20)
        param_layout.setSpacing(12)

        # 起始帧
        start_label = BodyLabel('起始帧号:', param_card)
        start_label.setStyleSheet('color: #1a1a1a; font-size: 14px; font-weight: 500;')
        param_layout.addWidget(start_label, 0, 0)
        self.start_frame_spin = SpinBox(param_card)
        self.start_frame_spin.setRange(0, 999999)
        self.start_frame_spin.setValue(0)
        self.start_frame_spin.setMinimumWidth(150)
        param_layout.addWidget(self.start_frame_spin, 0, 1)

        # 结束帧
        end_label = BodyLabel('结束帧号:', param_card)
        end_label.setStyleSheet('color: #1a1a1a; font-size: 14px; font-weight: 500;')
        param_layout.addWidget(end_label, 0, 2)
        self.end_frame_spin = SpinBox(param_card)
        self.end_frame_spin.setRange(0, 999999)
        self.end_frame_spin.setValue(0)
        self.end_frame_spin.setSpecialValueText('全部')
        self.end_frame_spin.setMinimumWidth(150)
        param_layout.addWidget(self.end_frame_spin, 0, 3)

        # 文件名前缀
        prefix_label = BodyLabel('文件名前缀:', param_card)
        prefix_label.setStyleSheet('color: #1a1a1a; font-size: 14px; font-weight: 500;')
        param_layout.addWidget(prefix_label, 1, 0)

        # 前缀输入框和按钮的水平布局
        prefix_h_layout = QHBoxLayout()
        self.prefix_edit = LineEdit(param_card)
        self.prefix_edit.setPlaceholderText('输出文件名前缀（留空则使用时间戳）')
        prefix_h_layout.addWidget(self.prefix_edit)

        self.timestamp_btn = TransparentPushButton('使用时间戳', param_card, FluentIcon.DATE_TIME)
        self.timestamp_btn.clicked.connect(self.use_timestamp_prefix)
        self.timestamp_btn.setToolTip('点击使用当前时间戳作为前缀')
        prefix_h_layout.addWidget(self.timestamp_btn)

        param_layout.addLayout(prefix_h_layout, 1, 1, 1, 3)

        # 输出格式
        format_label = BodyLabel('输出格式:', param_card)
        format_label.setStyleSheet('color: #1a1a1a; font-size: 14px; font-weight: 500;')
        param_layout.addWidget(format_label, 2, 0)
        self.format_combo = ComboBox(param_card)
        self.format_combo.addItems(['PNG', 'TIFF', 'BMP'])
        self.format_combo.setCurrentIndex(0)
        self.format_combo.setMinimumWidth(150)
        param_layout.addWidget(self.format_combo, 2, 1)

        main_layout.addWidget(param_card)

        # 进度卡片
        progress_card = CardWidget(self)
        progress_card.setStyleSheet("""
            CardWidget {
                background-color: white;
                border-radius: 10px;
            }
        """)
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
        self.progress_label.setStyleSheet('color: #1a1a1a; font-size: 13px;')
        progress_layout.addWidget(self.progress_label)

        main_layout.addWidget(progress_card)

        # 日志卡片
        log_card = CardWidget(self)
        log_card.setStyleSheet("""
            CardWidget {
                background-color: white;
                border-radius: 10px;
            }
        """)
        log_layout = QVBoxLayout(log_card)
        log_layout.setContentsMargins(20, 20, 20, 20)
        log_layout.setSpacing(12)

        log_title = BodyLabel('日志:', log_card)
        log_title.setStyleSheet('color: #1a1a1a; font-size: 14px; font-weight: 500;')
        log_layout.addWidget(log_title)

        from PyQt5.QtWidgets import QTextEdit
        self.log_text = QTextEdit(log_card)
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(150)
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

        main_layout.addWidget(log_card)

        # 按钮布局
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.start_btn = PushButton('开始转换', self, FluentIcon.PLAY)
        self.start_btn.clicked.connect(self.start_conversion)
        self.start_btn.setMinimumWidth(140)
        self.start_btn.setMinimumHeight(40)
        self.start_btn.setStyleSheet("""
            PushButton {
                background-color: rgba(255, 255, 255, 0.95);
                color: #0078d7;
                border: 2px solid rgba(255, 255, 255, 0.6);
                border-radius: 6px;
                font-size: 15px;
                font-weight: bold;
                padding: 8px 16px;
            }
            PushButton:hover {
                background-color: rgba(255, 255, 255, 1);
                border: 2px solid rgba(255, 255, 255, 0.8);
            }
            PushButton:pressed {
                background-color: rgba(240, 240, 240, 0.95);
            }
        """)
        button_layout.addWidget(self.start_btn)

        button_layout.addSpacing(10)

        self.stop_btn = PushButton('停止', self, FluentIcon.CANCEL)
        self.stop_btn.clicked.connect(self.stop_conversion)
        self.stop_btn.setEnabled(False)
        self.stop_btn.setMinimumWidth(140)
        self.stop_btn.setMinimumHeight(40)
        self.stop_btn.setStyleSheet("""
            PushButton {
                background-color: rgba(255, 255, 255, 0.95);
                color: #e74856;
                border: 2px solid rgba(255, 255, 255, 0.6);
                border-radius: 6px;
                font-size: 15px;
                font-weight: bold;
                padding: 8px 16px;
            }
            PushButton:hover {
                background-color: rgba(255, 255, 255, 1);
                border: 2px solid rgba(255, 255, 255, 0.8);
            }
            PushButton:pressed {
                background-color: rgba(240, 240, 240, 0.95);
            }
            PushButton:disabled {
                background-color: rgba(255, 255, 255, 0.5);
                color: rgba(128, 128, 128, 0.7);
                border: 2px solid rgba(200, 200, 200, 0.4);
            }
        """)
        button_layout.addWidget(self.stop_btn)

        main_layout.addLayout(button_layout)

        # 设置主题为浅色（科学蓝主题）
        setTheme(Theme.LIGHT)

        # 应用科学蓝配色
        from qfluentwidgets import setThemeColor
        setThemeColor(QColor(0, 120, 215))  # 科学蓝色

    def browse_seq_file(self):
        """浏览 SEQ 文件"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            '选择 SEQ 文件',
            '',
            'SEQ Files (*.seq);;All Files (*.*)'
        )
        if file_path:
            self.seq_path_edit.setText(file_path)
            # 自动设置输出目录
            if not self.output_path_edit.text():
                seq_basename = os.path.splitext(os.path.basename(file_path))[0]
                output_dir = os.path.join(os.path.dirname(file_path), f"{seq_basename}_frames")
                self.output_path_edit.setText(output_dir)
            self.add_log(f'选择文件: {file_path}')

    def browse_output_dir(self):
        """浏览输出目录"""
        dir_path = QFileDialog.getExistingDirectory(
            self,
            '选择输出目录',
            ''
        )
        if dir_path:
            self.output_path_edit.setText(dir_path)
            self.add_log(f'输出目录: {dir_path}')

    def add_log(self, message):
        """添加日志"""
        self.log_text.append(message)

    def use_timestamp_prefix(self):
        """使用当前时间戳作为前缀"""
        from datetime import datetime
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        self.prefix_edit.setText(timestamp)
        self.add_log(f'已设置前缀为时间戳: {timestamp}')

    def start_conversion(self):
        """开始转换"""
        seq_file = self.seq_path_edit.text()
        output_dir = self.output_path_edit.text()

        # 验证输入
        if not seq_file:
            InfoBar.error(
                title='错误',
                content='请选择 SEQ 文件',
                parent=self,
                position=InfoBarPosition.TOP,
                duration=3000
            )
            return

        if not os.path.exists(seq_file):
            InfoBar.error(
                title='错误',
                content='SEQ 文件不存在',
                parent=self,
                position=InfoBarPosition.TOP,
                duration=3000
            )
            return

        if not output_dir:
            InfoBar.error(
                title='错误',
                content='请选择输出目录',
                parent=self,
                position=InfoBarPosition.TOP,
                duration=3000
            )
            return

        # 获取参数
        start_frame = self.start_frame_spin.value()
        end_frame = self.end_frame_spin.value() if self.end_frame_spin.value() > 0 else None

        # 如果前缀为空，使用时间戳（精确到秒）
        prefix = self.prefix_edit.text()
        if not prefix:
            from datetime import datetime
            prefix = datetime.now().strftime('%Y%m%d_%H%M%S')
            self.add_log(f'未指定前缀，自动使用时间戳: {prefix}')

        format = self.format_combo.currentText()

        # 清空日志和进度
        self.log_text.clear()
        self.progress_bar.setValue(0)
        self.progress_label.setText('准备开始...')

        # 禁用控件
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.seq_browse_btn.setEnabled(False)
        self.output_browse_btn.setEnabled(False)

        # 创建并启动转换线程
        self.convert_thread = ConvertThread(seq_file, output_dir, start_frame, end_frame, prefix, format)
        self.convert_thread.progress.connect(self.on_progress)
        self.convert_thread.finished.connect(self.on_finished)
        self.convert_thread.log.connect(self.add_log)
        self.convert_thread.start()

        self.add_log('=' * 50)
        self.add_log('开始转换...')

    def stop_conversion(self):
        """停止转换"""
        if self.convert_thread and self.convert_thread.isRunning():
            self.add_log('正在停止转换...')
            self.convert_thread.stop()
            self.convert_thread.wait()

    def on_progress(self, current, total):
        """更新进度"""
        progress = int((current / total) * 100)
        self.progress_bar.setValue(progress)
        self.progress_label.setText(f'已处理: {current}/{total} 帧 ({progress}%)')

    def on_finished(self, success, message):
        """转换完成"""
        # 恢复控件
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.seq_browse_btn.setEnabled(True)
        self.output_browse_btn.setEnabled(True)

        self.add_log('=' * 50)

        if success:
            self.progress_bar.setValue(100)
            self.progress_label.setText('转换完成!')
            self.add_log(f'成功: {message}')
            InfoBar.success(
                title='成功',
                content=message,
                parent=self,
                position=InfoBarPosition.TOP,
                duration=5000
            )
        else:
            self.progress_label.setText('转换失败')
            self.add_log(f'失败: {message}')
            InfoBar.error(
                title='错误',
                content=message,
                parent=self,
                position=InfoBarPosition.TOP,
                duration=5000
            )


def main():
    app = QApplication(sys.argv)

    # 设置应用样式
    app.setStyle('Fusion')

    window = SeqToPngGUI()
    window.show()

    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
