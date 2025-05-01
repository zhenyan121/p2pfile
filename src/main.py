#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
P2P文件传输工具主程序
基于frp xtcp功能实现点对点文件传输
"""

import sys
import os
import logging
import time
from PyQt5.QtWidgets import QApplication, QMessageBox, QSplashScreen, QLabel
from PyQt5.QtGui import QPixmap, QColor, QPainter, QFont
from PyQt5.QtCore import Qt, QTimer

# 导入自定义模块
from ui.main_window import MainWindow
from frp.connection import FrpConnection
import threading

# 配置日志
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                   filename='p2pfile.log',
                   filemode='a')
logger = logging.getLogger('main')

# 确保下载目录存在
downloads_dir = os.path.join(os.getcwd(), "downloads")
os.makedirs(downloads_dir, exist_ok=True)

def create_splash_screen():
    """创建启动画面"""
    # 创建启动画面
    splash_pix = QPixmap(400, 300)
    splash_pix.fill(QColor('#FFDAC1'))  # 使用马卡龙暖色系
    
    # 添加文字
    painter = QPainter(splash_pix)
    painter.setPen(QColor('#6E6E6E'))
    painter.setFont(QFont("Arial", 20, QFont.Bold))
    painter.drawText(splash_pix.rect(), Qt.AlignCenter, "P2P文件传输工具
正在启动...")
    painter.end()
    
    splash = QSplashScreen(splash_pix)
    splash.show()
    return splash

def main():
    """主函数"""
    try:
        # 创建应用程序
        app = QApplication(sys.argv)
        
        # 显示启动画面
        splash = create_splash_screen()
        app.processEvents()
        
        # 设置应用程序样式
        app.setStyle('Fusion')
        
        # 设置样式表
        app.setStyleSheet("""
            QMainWindow, QDialog {
                background-color: #FFFFFF;
            }
            QPushButton {
                background-color: #FFB7B2;
                color: #6E6E6E;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #FF9AA2;
            }
            QPushButton:pressed {
                background-color: #F48B94;
            }
            QPushButton:disabled {
                background-color: #E0E0E0;
                color: #A0A0A0;
            }
            QProgressBar {
                border: 1px solid #B5EAD7;
                border-radius: 3px;
                text-align: center;
            }
            QProgressBar::chunk {
                background-color: #FF9AA2;
            }
        """)
        
        # 初始化FRP连接
        # 配置frp服务器信息
        server_addr = "frp.yourdomain.com"  # 替换为实际的frp服务器地址
        server_port = 7000  # 替换为实际的frp服务器端口
        token = "your_secure_auth.token"  # 替换为实际的auth.token认证令牌
        
        # 角色选择对话框
        msg_box = QMessageBox(None)
        msg_box.setWindowTitle('角色选择')
        msg_box.setText('请选择程序角色:')
        msg_box.setInformativeText('发送端：用于发送文件的一方
接收端：用于接收文件的一方

注意：双方必须选择不同的角色才能建立连接')
        msg_box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        msg_box.button(QMessageBox.Yes).setText('发送端')
        msg_box.button(QMessageBox.No).setText('接收端')
        choice = msg_box.exec_()
        role = 'server' if choice == QMessageBox.Yes else 'visitor'
        
        # 更新启动画面状态
        splash.showMessage(f"正在初始化 {role} 角色...", Qt.AlignBottom | Qt.AlignCenter, Qt.white)
        app.processEvents()
        
        # 连接参数输入对话框
        from PyQt5.QtWidgets import QDialog, QFormLayout, QLineEdit, QDialogButtonBox, QVBoxLayout
        
        param_dialog = QDialog(None)
        param_dialog.setWindowTitle('连接参数设置')
        param_dialog.setStyleSheet(f"""
            QDialog {{ background-color: #FFFFFF; }}
            QLabel {{ color: #6E6E6E; }}
            QLineEdit {{ 
                border: 1px solid #B5EAD7; 
                border-radius: 3px; 
                padding: 5px; 
                background-color: #FFDAC1; 
                color: #6E6E6E; 
            }}
            QPushButton {{ 
                background-color: #FFB7B2; 
                color: #6E6E6E; 
                border: none; 
                padding: 8px 16px; 
                border-radius: 4px; 
            }}
            QPushButton:hover {{ background-color: #FF9AA2; }}
            QPushButton:pressed {{ background-color: #F48B94; }}
        """)
        
        layout = QVBoxLayout(param_dialog)
        form_layout = QFormLayout()
        
        # 默认值
        default_secret_key = "p2pfiletransfer"
        default_server_name = "p2pfile"
        
        # 创建输入框
        secret_key_input = QLineEdit(default_secret_key)
        server_name_input = QLineEdit(default_server_name)
        
        # 添加到表单
        form_layout.addRow("密钥 (secret_key):", secret_key_input)
        form_layout.addRow("服务名称 (server_name):", server_name_input)
        
        # 添加说明标签
        info_label = QLabel("注意: 双方必须使用相同的密钥和服务名称才能建立连接")
        info_label.setStyleSheet("color: #6E6E6E; padding: 10px 0;")
        
        # 创建按钮
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(param_dialog.accept)
        button_box.rejected.connect(param_dialog.reject)
        button_box.button(QDialogButtonBox.Ok).setText("确定")
        button_box.button(QDialogButtonBox.Cancel).setText("取消")
        
        # 添加到布局
        layout.addLayout(form_layout)
        layout.addWidget(info_label)
        layout.addWidget(button_box)
        
        # 显示对话框
        result = param_dialog.exec_()
        
        # 如果用户点击取消，使用默认值
        if result == QDialog.Accepted:
            secret_key = secret_key_input.text().strip()
            server_name = server_name_input.text().strip()
            
            # 如果用户输入为空，使用默认值
            if not secret_key:
                secret_key = default_secret_key
            if not server_name:
                server_name = default_server_name
        else:
            secret_key = default_secret_key
            server_name = default_server_name
        
        # 创建FrpConnection实例
        frp_connection = FrpConnection(server_addr, server_port, token, role=role)
        
        # 生成frp配置文件，设置必要参数
        local_port = 7100  # 本地端口
        frp_connection.generate_config(local_port, secret_key=secret_key, server_name=server_name)
        
        # 更新启动画面状态
        splash.showMessage("正在连接到frp服务器...", Qt.AlignBottom | Qt.AlignCenter, Qt.white)
        app.processEvents()
