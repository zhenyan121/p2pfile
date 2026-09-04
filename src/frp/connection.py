#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
frp连接模块
实现frp xtcp连接功能
"""

import os
import subprocess
import time
import socket
import logging
import threading
import json
import tempfile

# 配置日志
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("frp.connection")


class FrpConnection:
    """frp连接类，负责frp xtcp连接的建立和管理"""

    def __init__(self, server_addr, server_port, token, role="server"):
        """
        初始化frp连接

        Args:
            server_addr: frp服务器地址
            server_port: frp服务器端口
            token: 认证令牌
            role: 角色，'server'或'visitor'
        """
        self.server_addr = server_addr
        self.server_port = server_port
        self.token = token
        self.role = role  # server或visitor
        self.local_port = None
        self.secret_key = None
        self.server_name = None
        self.config_path = None
        self.frpc_process = None
        self.connected = False
        self.peer_addr = None
        self.peer_port = None
        self.status_callback = None
        self.connection_status = "未连接"
        self.lock = threading.Lock()
        self.xtcp_started = False
        self.stcp_fallback = False
        self.connection_start_time = None

    def set_status_callback(self, callback):
        """
        设置状态回调函数

        Args:
            callback: 回调函数，接收状态信息
        """
        self.status_callback = callback

    def _update_status(self, status):
        """
        更新连接状态

        Args:
            status: 状态信息
        """
        self.connection_status = status
        if self.status_callback:
            self.status_callback(status)
        logger.info(f"连接状态: {status}")

    def set_config_path(self, config_path):
        """
        设置配置文件路径

        Args:
            config_path: 配置文件路径

        Returns:
            bool: 是否成功设置
        """
        if not os.path.exists(config_path):
            logger.error(f"配置文件不存在: {config_path}")
            return False

        self.config_path = config_path

        # 解析配置文件获取端口号
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                content = f.read()

            if self.role == "server":
                # 查找localPort
                import re

                match = re.search(r"localPort\s*=\s*(\d+)", content)
                if match:
                    self.local_port = int(match.group(1))
                    logger.info(f"从配置文件中读取localPort: {self.local_port}")
            else:  # visitor
                # 查找bindPort
                import re

                match = re.search(r"bindPort\s*=\s*(\d+)", content)
                if match:
                    self.local_port = int(match.group(1))
                    logger.info(f"从配置文件中读取bindPort: {self.local_port}")

        except Exception as e:
            logger.warning(f"解析配置文件端口失败: {e}")
            # 使用默认端口
            self.local_port = 7100

        logger.info(
            f"已设置frpc配置文件: {self.config_path}, 本地端口: {self.local_port}"
        )
        return True

    def start_frpc(self):
        """
        启动frpc进程

        Returns:
            bool: 是否成功启动
        """
        if not self.config_path:
            logger.error("未找到配置文件，无法启动frpc")
            return False

        try:
            # 获取frpc路径
            current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

            # 系统检测
            import platform

            system = platform.system().lower()
            if system == "windows":
                frpc_path = os.path.join(current_dir, "frpc.exe")
            else:
                frpc_path = os.path.join(current_dir, "frpc")

            # 检查frpc是否存在
            if not os.path.exists(frpc_path):
                logger.error(f"frpc程序不存在: {frpc_path}")
                self._update_status(f"frpc程序不存在: {frpc_path}")
                return False

            # 启动frpc
            cmd = [frpc_path, "-c", self.config_path]
            self.frpc_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
            )

            # 启动监控线程
            threading.Thread(target=self._monitor_frpc, daemon=True).start()

            self._update_status("正在连接frp服务器...")
            return True
        except Exception as e:
            logger.error(f"启动frpc失败: {e}")
            self._update_status(f"启动frpc失败: {e}")
            return False

        try:
            # 获取frpc路径
            current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

            # 系统检测
            import platform

            system = platform.system().lower()
            if system == "windows":
                frpc_path = os.path.join(current_dir, "frpc.exe")
            else:
                frpc_path = os.path.join(current_dir, "frpc")

            # 检查frpc是否存在
            if not os.path.exists(frpc_path):
                logger.error(f"frpc程序不存在: {frpc_path}")
                self._update_status(f"frpc程序不存在: {frpc_path}")
                return False

            # 启动frpc
            cmd = [frpc_path, "-c", self.config_path]
            self.frpc_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
            )

            # 启动监控线程
            threading.Thread(target=self._monitor_frpc, daemon=True).start()

            self._update_status("正在连接frp服务器...")
            return True
        except Exception as e:
            logger.error(f"启动frpc失败: {e}")
            self._update_status(f"启动frpc失败: {e}")
            return False

    def _monitor_frpc(self):
        """
        监控frpc进程输出
        """
        if not self.frpc_process:
            return

        connected = False
        self.connection_start_time = time.time()

        while self.frpc_process.poll() is None:
            if self.frpc_process.stdout:
                line = self.frpc_process.stdout.readline().strip()
                if not line:
                    continue

                logger.info(f"frpc输出: {line}")

                # 检测连接状态
                if "login to server success" in line:
                    self._update_status("已连接到frp服务器")
                    connected = True
                elif "start proxy success" in line:
                    self._update_status("代理启动成功")
                elif "xtcp" in line and "visitor" in line and "connected" in line:
                    self._update_status("P2P连接已建立")
                    self.xtcp_started = True
                    self.connected = True

                    # 尝试提取对方地址和端口
                    try:
                        # 示例: "[p2pfile_visitor] xtcp visitor connected: 127.0.0.1:7100"
                        parts = line.split("connected: ")[1].split(":")
                        self.peer_addr = parts[0]
                        self.peer_port = int(parts[1])
                        logger.info(
                            f"P2P连接对方地址: {self.peer_addr}:{self.peer_port}"
                        )

                        # 通知文件传输模块连接
                        if self.status_callback:
                            self.status_callback(
                                "p2p_connected",
                                {
                                    "peer_addr": self.peer_addr,
                                    "peer_port": self.peer_port,
                                },
                            )
                    except Exception as e:
                        logger.warning(f"无法解析P2P连接地址: {e}")
                elif "stcp" in line and "visitor" in line and "connected" in line:
                    self._update_status("STCP连接已建立（fallback）")
                    self.stcp_fallback = True
                    self.connected = True

                    # 尝试提取对方地址和端口
                    try:
                        # 示例: "[p2pfile_visitor] stcp visitor connected: 127.0.0.1:7100"
                        parts = line.split("connected: ")[1].split(":")
                        self.peer_addr = parts[0]
                        self.peer_port = int(parts[1])
                        logger.info(
                            f"STCP连接对方地址: {self.peer_addr}:{self.peer_port}"
                        )

                        # 通知文件传输模块连接
                        if self.status_callback:
                            self.status_callback(
                                "stcp_connected",
                                {
                                    "peer_addr": self.peer_addr,
                                    "peer_port": self.peer_port,
                                },
                            )
                    except Exception as e:
                        logger.warning(f"无法解析STCP连接地址: {e}")
                elif "error" in line.lower() or "fail" in line.lower():
                    self._update_status(f"frpc错误: {line}")

            # 超时检测：如果30秒内没有建立P2P连接，尝试使用STCP
            if connected and not self.xtcp_started and not self.stcp_fallback:
                elapsed_time = time.time() - self.connection_start_time
                if elapsed_time > 30:  # 30秒超时
                    logger.info("xtcp连接超时，将使用stcp作为fallback")
                    self._update_status("xtcp连接超时，使用stcp作为fallback")
                    # 这里可以添加切换到stcp的逻辑，但当前配置中已包含stcp，所以frpc会自动处理

        # 进程结束
        exit_code = self.frpc_process.poll()
        logger.info(f"frpc进程已退出，退出码: {exit_code}")
        self.connected = False
        self._update_status("frpc已断开连接")

    def stop_frpc(self):
        """
        停止frpc进程
        """
        if self.frpc_process:
            try:
                self.frpc_process.terminate()
                self.frpc_process.wait(timeout=5)
                logger.info("frpc进程已终止")
            except Exception as e:
                logger.error(f"终止frpc进程失败: {e}")
                try:
                    self.frpc_process.kill()
                except:
                    pass
            finally:
                self.frpc_process = None
                self.connected = False
                self._update_status("已断开连接")

    def get_connection_info(self):
        """
        获取连接信息

        Returns:
            dict: 连接信息
        """
        return {
            "role": self.role,
            "server_name": self.server_name,
            "local_port": self.local_port,
            "connected": self.connected,
            "status": self.connection_status,
            "peer_addr": self.peer_addr,
            "peer_port": self.peer_port,
        }

    def __del__(self):
        """
        析构函数，确保进程被终止
        """
        self.stop_frpc()
