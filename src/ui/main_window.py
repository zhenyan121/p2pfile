#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
主窗口UI模块
实现文件传输工具的主界面
"""

import os
import sys
import time
import threading
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QPushButton, QLabel, QProgressBar, QFileDialog,
    QListWidget, QListWidgetItem, QMessageBox, QSplitter,
    QFrame, QSizePolicy, QTabWidget, QTextEdit, QComboBox
)
from PyQt5.QtCore import Qt, QSize, pyqtSignal, QThread, QTimer, QEventLoop
from PyQt5.QtGui import QColor, QPalette, QFont, QIcon
import qtawesome as qta

# 导入自定义模块
from transfer.file_transfer import FileTransfer

# 配色方案 - 马卡龙暖色系
COLORS = {
    'primary': '#FF9AA2',  # 粉红
    'secondary': '#FFB7B2',  # 浅粉
    'accent': '#FFDAC1',  # 杏色
    'light': '#E2F0CB',  # 浅绿
    'highlight': '#B5EAD7',  # 薄荷绿
    'text': '#6E6E6E',  # 深灰
    'background': '#FFFFFF',  # 白色
    'success': '#C7CEEA',  # 淡紫
    'warning': '#FFCCB6',  # 橙色
    'error': '#F48B94',  # 红色
}

class MainWindow(QMainWindow):
    """主窗口类"""
    
    def __init__(self, frp_connection):
        """
        初始化主窗口
        
        Args:
            frp_connection: FrpConnection实例
        """
        super().__init__()
        
        self.frp_connection = frp_connection
        self.file_transfer = None
        self.transfer_active = False
        self.current_file = None
        self.transfer_history = []
        
        # 设置窗口属性
        self.setWindowTitle("P2P文件传输工具")
        self.setMinimumSize(800, 600)
        
        # 初始化UI
        self._init_ui()
        
        # 设置frp连接状态回调
        self.frp_connection.set_status_callback(self.update_connection_status)
        
        # 启动定时器，定期更新状态
        self.status_timer = QTimer(self)
        self.status_timer.timeout.connect(self.update_status)
        self.status_timer.start(1000)  # 每秒更新一次
        
        # 初始化文件传输
        self._init_file_transfer()
    
    def _init_ui(self):
        """
        初始化UI
        """
        # 设置中央窗口部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 主布局
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)
        
        # 状态栏
        self.status_bar = QLabel("未连接")
        self.status_bar.setStyleSheet(f"color: {COLORS['text']}; padding: 5px;")
        self.statusBar().addWidget(self.status_bar)
        
        # 连接状态面板
        connection_frame = QFrame()
        connection_frame.setFrameShape(QFrame.StyledPanel)
        connection_frame.setStyleSheet(f"background-color: {COLORS['accent']}; border-radius: 5px;")
        connection_layout = QHBoxLayout(connection_frame)
        
        # 连接状态标签
        self.connection_status_label = QLabel("未连接")
        self.connection_status_label.setStyleSheet(f"color: {COLORS['text']}; font-weight: bold;")
        connection_layout.addWidget(self.connection_status_label)
        
        # 连接信息
        self.connection_info_label = QLabel("")
        connection_layout.addWidget(self.connection_info_label, 1)
        
        # 添加到主布局
        main_layout.addWidget(connection_frame)
        
        # 创建选项卡
        tabs = QTabWidget()
        tabs.setStyleSheet(f"QTabBar::tab:selected {{background-color: {COLORS['primary']}; color: white;}}")
        
        # 文件传输选项卡
        transfer_tab = QWidget()
        transfer_layout = QVBoxLayout(transfer_tab)
        
        # 文件选择区域
        file_frame = QFrame()
        file_frame.setFrameShape(QFrame.StyledPanel)
        file_frame.setStyleSheet(f"background-color: {COLORS['light']}; border-radius: 5px;")
        file_layout = QHBoxLayout(file_frame)
        
        # 文件选择按钮
        self.select_file_btn = QPushButton("选择文件")
        self.select_file_btn.setStyleSheet(f"background-color: {COLORS['primary']}; color: white; padding: 8px;")
        self.select_file_btn.clicked.connect(self.select_file)
        file_layout.addWidget(self.select_file_btn)
        
        # 当前文件标签
        self.current_file_label = QLabel("未选择文件")
        file_layout.addWidget(self.current_file_label, 1)
        
        # 发送按钮
        self.send_file_btn = QPushButton("发送文件")
        self.send_file_btn.setStyleSheet(f"background-color: {COLORS['highlight']}; color: {COLORS['text']}; padding: 8px;")
        self.send_file_btn.setEnabled(False)
        self.send_file_btn.clicked.connect(self.send_file)
        file_layout.addWidget(self.send_file_btn)
        
        transfer_layout.addWidget(file_frame)
        
        # 传输进度区域
        progress_frame = QFrame()
        progress_frame.setFrameShape(QFrame.StyledPanel)
        progress_frame.setStyleSheet(f"background-color: {COLORS['secondary']}; border-radius: 5px;")
        progress_layout = QVBoxLayout(progress_frame)
        
        # 传输状态标签
        self.transfer_status_label = QLabel("就绪")
        progress_layout.addWidget(self.transfer_status_label)
        
        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setStyleSheet(f"QProgressBar {{border: 1px solid {COLORS['text']}; border-radius: 3px; text-align: center;}} "
                                       f"QProgressBar::chunk {{background-color: {COLORS['primary']}; width: 10px;}}")
        progress_layout.addWidget(self.progress_bar)
        
        # 传输信息
        transfer_info_layout = QHBoxLayout()
        
        # 传输速度
        self.speed_label = QLabel("速度: 0 KB/s")
        transfer_info_layout.addWidget(self.speed_label)
        
        # 已传输大小
        self.transferred_label = QLabel("已传输: 0 KB / 0 KB")
        transfer_info_layout.addWidget(self.transferred_label)
        
        # 剩余时间
        self.time_label = QLabel("剩余时间: --:--")
        transfer_info_layout.addWidget(self.time_label)
        
        progress_layout.addLayout(transfer_info_layout)
        
        transfer_layout.addWidget(progress_frame)
        
        # 传输历史列表
        history_frame = QFrame()
        history_frame.setFrameShape(QFrame.StyledPanel)
        history_frame.setStyleSheet(f"background-color: {COLORS['success']}; border-radius: 5px;")
        history_layout = QVBoxLayout(history_frame)
        
        history_label = QLabel("传输历史")
        history_label.setStyleSheet("font-weight: bold;")
        history_layout.addWidget(history_label)
        
        self.history_list = QListWidget()
        self.history_list.setStyleSheet(f"background-color: white; border: 1px solid {COLORS['text']};")
        history_layout.addWidget(self.history_list)
        
        transfer_layout.addWidget(history_frame)
        
        # 添加传输选项卡
        tabs.addTab(transfer_tab, "文件传输")
        
        # 日志选项卡
        log_tab = QWidget()
        log_layout = QVBoxLayout(log_tab)
        
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        log_layout.addWidget(self.log_text)
        
        tabs.addTab(log_tab, "日志")
        
        # 设置选项卡
        settings_tab = QWidget()
        settings_layout = QVBoxLayout(settings_tab)
        
        # 设置项
        settings_frame = QFrame()
        settings_frame.setFrameShape(QFrame.StyledPanel)
        settings_frame.setStyleSheet(f"background-color: {COLORS['light']}; border-radius: 5px;")
        settings_form = QVBoxLayout(settings_frame)
        
        # 下载目录设置
        download_layout = QHBoxLayout()
        download_layout.addWidget(QLabel("下载目录:"))
        self.download_path_label = QLabel(os.path.join(os.getcwd(), "downloads"))
        download_layout.addWidget(self.download_path_label, 1)
        self.change_download_btn = QPushButton("更改")
        self.change_download_btn.clicked.connect(self.change_download_path)
        download_layout.addWidget(self.change_download_btn)
        settings_form.addLayout(download_layout)
        
        settings_layout.addWidget(settings_frame)
        settings_layout.addStretch(1)
        
        tabs.addTab(settings_tab, "设置")
        
        # 添加选项卡到主布局
        main_layout.addWidget(tabs)
    
    def _init_file_transfer(self):
        """
        初始化文件传输
        """
        # 获取连接信息
        conn_info = self.frp_connection.get_connection_info()
        local_port = conn_info.get('local_port', 0)
        
        # 创建文件传输实例
        self.file_transfer = FileTransfer(host='127.0.0.1', port=local_port, callback=self.transfer_callback)
        
        # 如果是接收端，开始监听
        if self.frp_connection.role == 'visitor':
            self.file_transfer.listen()
    
    def update_connection_status(self, status):
        """
        更新连接状态
        
        Args:
            status: 状态信息
        """
        self.connection_status_label.setText(f"状态: {status}")
        self.status_bar.setText(status)
        
        # 更新连接信息
        conn_info = self.frp_connection.get_connection_info()
        role = "发送端" if conn_info.get('role') == 'server' else "接收端"
        port = conn_info.get('local_port', 0)
        
        info_text = f"角色: {role} | 端口: {port}"
        if conn_info.get('connected'):
            peer_addr = conn_info.get('peer_addr', 'Unknown')
            peer_port = conn_info.get('peer_port', 0)
            info_text += f" | 对方地址: {peer_addr}:{peer_port}"
        
        self.connection_info_label.setText(info_text)
        
        # 记录日志
        self.log(f"连接状态: {status}")
        
        # 如果连接已建立，启用发送按钮
        if conn_info.get('connected') and self.current_file:
            self.send_file_btn.setEnabled(True)
    
    def update_status(self):
        """
        定期更新状态
        """
        # 更新连接状态
        conn_info = self.frp_connection.get_connection_info()
        
        # 如果传输活动，更新传输状态
        if self.transfer_active and self.file_transfer:
            # 获取传输信息
            transferred = self.file_transfer.transferred_size
            total = self.file_transfer.file_size
            speed = self.file_transfer.speed
            
            # 更新进度条
            if total > 0:
                progress = int(transferred / total * 100)
                self.progress_bar.setValue(progress)
            
            # 更新传输信息
            self.speed_label.setText(f"速度: {self._format_size(speed)}/s")
            self.transferred_label.setText(f"已传输: {self._format_size(transferred)} / {self._format_size(total)}")
            
            # 计算剩余时间
            if speed > 0:
                remaining_seconds = (total - transferred) / speed
                minutes = int(remaining_seconds / 60)
                seconds = int(remaining_seconds % 60)
                self.time_label.setText(f"剩余时间: {minutes:02d}:{seconds:02d}")
            else:
                self.time_label.setText("剩余时间: --:--")
    
    def select_file(self):
        """
        选择要发送的文件
        """
        file_path, _ = QFileDialog.getOpenFileName(self, "选择文件", "", "所有文件 (*)")
        if file_path:
            self.current_file = file_path
            file_name = os.path.basename(file_path)
            self.current_file_label.setText(file_name)
            
            # 如果已连接，启用发送按钮
            if self.frp_connection.connected:
                self.send_file_btn.setEnabled(True)
            
            # 记录日志
            self.log(f"已选择文件: {file_path}")
    
    def send_file(self):
        """
        发送文件
        """
        if not self.current_file or not self.frp_connection.connected:
            return
        
        # 获取连接信息
        conn_info = self.frp_connection.get_connection_info()
        peer_addr = conn_info.get('peer_addr', '127.0.0.1')
        peer_port = conn_info.get('peer_port', conn_info.get('local_port', 0))
        
        # 开始传输
        threading.Thread(target=self._send_file_thread, args=(peer_addr, peer_port), daemon=True).start()
    
    def _send_file_thread(self, host, port):
        """
        文件发送线程
        
        Args:
            host: 目标主机
            port: 目标端口
        """
        try:
            # 连接到对方
            if not self.file_transfer.connect(host, port):
                self.log(f"无法连接到对方: {host}:{port}")
                return
            
            # 发送文件
            self.transfer_active = True
            self.transfer_status_label.setText("正在发送文件...")
            self.progress_bar.setValue(0)
            
            success = self.file_transfer.send_file(self.current_file)
            
            if success:
                self.transfer_status_label.setText("文件发送成功")
                self.log(f"文件发送成功: {self.current_file}")
                
                # 添加到历史记录
                self._add_history(os.path.basename(self.current_file), "发送", "成功")
            else:
                self.transfer_status_label.setText("文件发送失败")
                self.log(f"文件发送失败: {self.current_file}")
                
                # 添加到历史记录
                self._add_history(os.path.basename(self.current_file), "发送", "失败")
        except Exception as e:
            self.transfer_status_label.setText(f"发送错误: {e}")
            self.log(f"发送文件时出错: {e}")
            self._add_history(os.path.basename(self.current_file), "发送", "错误")
        finally:
            self.transfer_active = False
    
    def transfer_callback(self, event, data):
        """
        传输回调函数
        
        Args:
            event: 事件类型
            data: 事件数据
            
        Returns:
            bool: 是否接受传输请求
        """
        if event == 'request':
            # 传输请求
            file_name = data.get('file_name', 'unknown')
            file_size = data.get('file_size', 0)
            
            # 在UI线程中显示确认对话框
            accept = False
            
            def show_confirm():
                nonlocal accept
                msg = QMessageBox()
                msg.setWindowTitle("文件传输请求")
                msg.setText(f"收到文件传输请求:\n文件名: {file_name}\n大小: {self._format_size(file_size)}")
                msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
                msg.button(QMessageBox.Yes).setText("接受")
                msg.button(QMessageBox.No).setText("拒绝")
                if msg.exec_() == QMessageBox.Yes:
                    accept = True
            
            # 在UI线程中执行
            # 由于BlockingQueuedConnection需要等待执行完成，这里使用事件循环等待
            from PyQt5.QtCore import QEventLoop
            loop = QEventLoop()
            
            def on_confirm_done():
                loop.quit()
            
            # 将确认对话框和事件循环退出连接起来
            timer = QTimer()
            timer.setSingleShot(True)
            timer.timeout.connect(lambda: [show_confirm(), on_confirm_done()])
            timer.start(0)
            
            # 等待对话框完成
            loop.exec_()
            
            if accept:
                self.log(f"接受文件传输请求: {file_name}, 大小: {self._format_size(file_size)}")
                self.transfer_status_label.setText(f"正在接收: {file_name}")
                self.transfer_active = True
                self.progress_bar.setValue(0)
            else:
                self.log(f"拒绝文件传输请求: {file_name}")
            
            return accept
        
        elif event == 'progress':
            # 传输进度
            pass  # 由update_status处理
        
        elif event == 'complete':
            # 传输完成
            file_path = data.get('file_path', '')
            file_name = os.path.basename(file_path)
            
            self.log(f"文件接收完成: {file_path}")
            self.transfer_status_label.setText(f"接收完成: {file_name}")
            self._add_history(file_name, "接收", "成功")
            self.transfer_active = False
        
        elif event == 'error':
            # 传输错误
            error = data.get('error', 'Unknown error')
            file_name = data.get('file_name', 'unknown')
            
            self.log(f"传输错误: {error}, 文件: {file_name}")
            self.transfer_status_label.setText(f"传输错误: {file_name}")
            self._add_history(file_name, "接收", "错误")
            self.transfer_active = False
        
        return True
    
    def _execute_in_main_thread(self, func):
        """
        在主线程中执行函数
        
        Args:
            func: 要执行的函数
        """
        func()
    
    def _add_history(self, file_name, action, status):
        """
        添加传输历史记录
        
        Args:
            file_name: 文件名
            action: 动作（发送/接收）
            status: 状态（成功/失败/错误）
        """
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        item_text = f"{timestamp} - {action} - {file_name} - {status}"
        
        # 设置颜色
        color = COLORS['success'] if status == "成功" else COLORS['error']
        
        # 在UI线程中添加
        def add_item():
            item = QListWidgetItem(item_text)
            item.setForeground(QColor(color))
            self.history_list.insertItem(0, item)  # 添加到顶部
        
        # 在UI线程中执行
        # 直接在主线程中执行，避免使用QMetaObject.invokeMethod
        # 因为Qt不支持直接传递Python callable对象作为参数
        QTimer.singleShot(0, add_item)
        
        # 添加到历史记录
        self.transfer_history.append({
            'timestamp': timestamp,
            'file_name': file_name,
            'action': action,
            'status': status
        })
    
    def change_download_path(self):
        """
        更改下载目录
        """
        dir_path = QFileDialog.getExistingDirectory(self, "选择下载目录", self.download_path_label.text())
        if dir_path:
            self.download_path_label.setText(dir_path)
            self.log(f"下载目录已更改为: {dir_path}")
    
    def log(self, message):
        """
        添加日志
        
        Args:
            message: 日志消息
        """
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        log_message = f"[{timestamp}] {message}"
        
        # 在UI线程中添加
        def add_log():
            self.log_text.append(log_message)
        
        # 在UI线程中执行
        # 直接在主线程中执行，避免使用QMetaObject.invokeMethod
        # 因为Qt不支持直接传递Python callable对象作为参数
        QTimer.singleShot(0, add_log)
    
    def _format_size(self, size_bytes):
        """
        格式化文件大小
        
        Args:
            size_bytes: 字节大小
            
        Returns:
            str: 格式化后的大小
        """
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes/1024:.2f} KB"
        elif size_bytes < 1024 * 1024 * 1024:
            return f"{size_bytes/(1024*1024):.2f} MB"
        else:
            return f"{size_bytes/(1024*1024*1024):.2f} GB"
    
    def closeEvent(self, event):
        """
        窗口关闭事件
        
        Args:
            event: 关闭事件
        """
        # 停止frpc
        self.frp_connection.stop_frpc()
        
        # 关闭文件传输
        if self.file_transfer:
            # 关闭连接
            pass
        
        event.accept()