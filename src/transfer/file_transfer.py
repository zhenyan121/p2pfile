#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
文件传输模块
负责文件的发送、接收和断点续传功能
"""

import os
import socket
import time
import json
import hashlib
import threading
import logging
from tqdm import tqdm

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('transfer.file_transfer')

# 常量定义
BUFFER_SIZE = 8192  # 缓冲区大小
CHUNK_SIZE = 1024 * 1024  # 文件分块大小，1MB
HEADER_SIZE = 1024  # 头信息大小
COMMAND_SIZE = 64  # 命令大小

# 命令类型
CMD_REQUEST = 'REQUEST'  # 请求传输
CMD_ACCEPT = 'ACCEPT'    # 接受传输
CMD_REJECT = 'REJECT'    # 拒绝传输
CMD_DATA = 'DATA'        # 数据传输
CMD_RESUME = 'RESUME'    # 恢复传输
CMD_COMPLETE = 'COMPLETE'  # 传输完成
CMD_ERROR = 'ERROR'      # 传输错误


class FileTransfer:
    """文件传输类，负责文件的发送和接收"""
    
    def __init__(self, host='127.0.0.1', port=0, callback=None):
        """
        初始化文件传输
        
        Args:
            host: 主机地址
            port: 端口号
            callback: 回调函数，用于通知传输进度和状态
        """
        self.host = host
        self.port = port
        self.callback = callback
        self.socket = None
        self.connected = False
        self.transfer_active = False
        self.transfer_paused = False
        self.transfer_completed = False
        self.transfer_error = None
        self.file_size = 0
        self.transferred_size = 0
        self.start_time = 0
        self.speed = 0  # 传输速度，字节/秒
        self.current_file = None
        self.current_file_path = None
        self.resume_info = None
        self.lock = threading.Lock()
    
    def connect(self, host=None, port=None):
        """
        连接到对方
        
        Args:
            host: 主机地址，如果为None则使用初始化时的值
            port: 端口号，如果为None则使用初始化时的值
            
        Returns:
            bool: 是否成功连接
        """
        if host:
            self.host = host
        if port:
            self.port = port
        
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((self.host, self.port))
            self.connected = True
            logger.info(f"已连接到 {self.host}:{self.port}")
            return True
        except Exception as e:
            logger.error(f"连接失败: {e}")
            self.connected = False
            return False
    
    def listen(self):
        """
        监听连接
        
        Returns:
            bool: 是否成功开始监听
        """
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.bind((self.host, self.port))
            self.socket.listen(1)
            logger.info(f"开始监听 {self.host}:{self.port}")
            
            # 获取实际绑定的端口（如果初始端口为0）
            self.host, self.port = self.socket.getsockname()
            logger.info(f"实际监听地址: {self.host}:{self.port}")
            
            # 启动接收线程
            threading.Thread(target=self._accept_connection, daemon=True).start()
            return True
        except Exception as e:
            logger.error(f"监听失败: {e}")
            return False
    
    def _accept_connection(self):
        """
        接受连接
        """
        try:
            client_socket, client_address = self.socket.accept()
            logger.info(f"接受连接: {client_address}")
            self.socket = client_socket
            self.connected = True
            
            # 启动接收线程
            threading.Thread(target=self._receive_loop, daemon=True).start()
        except Exception as e:
            logger.error(f"接受连接失败: {e}")
    
    def _receive_loop(self):
        """
        接收循环
        """
        while self.connected:
            try:
                # 接收命令
                command_data = self.socket.recv(COMMAND_SIZE)
                if not command_data:
                    logger.info("连接已关闭")
                    self.connected = False
                    break
                
                command = command_data.decode().strip()
                logger.info(f"收到命令: {command}")
                
                # 处理命令
                if command == CMD_REQUEST:
                    self._handle_request()
                elif command == CMD_DATA:
                    self._handle_data()
                elif command == CMD_RESUME:
                    self._handle_resume()
                elif command == CMD_COMPLETE:
                    self._handle_complete()
                elif command == CMD_ERROR:
                    self._handle_error()
                else:
                    logger.warning(f"未知命令: {command}")
            except Exception as e:
                logger.error(f"接收循环出错: {e}")
                self.connected = False
                break
    
    def _handle_request(self):
        """
        处理传输请求
        """
        try:
            # 接收头信息
            header_data = self.socket.recv(HEADER_SIZE)
            header = json.loads(header_data.decode())
            
            file_name = header.get('file_name')
            file_size = header.get('file_size')
            file_hash = header.get('file_hash')
            
            logger.info(f"收到传输请求: {file_name}, 大小: {file_size} 字节")
            
            # 通知回调
            if self.callback:
                accepted = self.callback('request', {
                    'file_name': file_name,
                    'file_size': file_size,
                    'file_hash': file_hash
                })
            else:
                accepted = True
            
            # 发送响应
            if accepted:
                # 准备接收文件
                self.current_file_path = os.path.join(os.getcwd(), 'downloads', file_name)
                os.makedirs(os.path.dirname(self.current_file_path), exist_ok=True)
                
                # 检查是否存在未完成的传输
                resume_path = f"{self.current_file_path}.resume"
                if os.path.exists(resume_path):
                    try:
                        with open(resume_path, 'r') as f:
                            self.resume_info = json.load(f)
                        
                        # 发送恢复传输命令
                        self._send_command(CMD_RESUME)
                        resume_header = {
                            'file_name': file_name,
                            'transferred_size': self.resume_info.get('transferred_size', 0)
                        }
                        self.socket.sendall(json.dumps(resume_header).encode().ljust(HEADER_SIZE))
                        
                        # 准备接收剩余数据
                        self.file_size = file_size
                        self.transferred_size = self.resume_info.get('transferred_size', 0)
                        self.current_file = open(self.current_file_path, 'ab')
                    except Exception as e:
                        logger.error(f"恢复传输失败: {e}")
                        # 如果恢复失败，则重新开始传输
                        self._send_command(CMD_ACCEPT)
                        self.current_file = open(self.current_file_path, 'wb')
                        self.file_size = file_size
                        self.transferred_size = 0
                else:
                    # 发送接受命令
                    self._send_command(CMD_ACCEPT)
                    self.current_file = open(self.current_file_path, 'wb')
                    self.file_size = file_size
                    self.transferred_size = 0
                
                # 开始传输
                self.transfer_active = True
                self.transfer_paused = False
                self.transfer_completed = False
                self.transfer_error = None
                self.start_time = time.time()
            else:
                # 发送拒绝命令
                self._send_command(CMD_REJECT)
        except Exception as e:
            logger.error(f"处理传输请求失败: {e}")
            self._send_command(CMD_ERROR)
    
    def _handle_data(self):
        """
        处理数据传输
        """
        if not self.transfer_active or self.transfer_paused:
            logger.warning("传输未激活或已暂停，忽略数据")
            return
        
        try:
            # 接收数据块大小
            size_data = self.socket.recv(8)
            chunk_size = int.from_bytes(size_data, byteorder='big')
            
            # 接收数据块
            received_size = 0
            chunk_data = b''
            while received_size < chunk_size:
                data = self.socket.recv(min(BUFFER_SIZE, chunk_size - received_size))
                if not data:
                    raise Exception("连接已关闭")
                chunk_data += data
                received_size += len(data)
            
            # 写入文件
            self.current_file.write(chunk_data)
            self.transferred_size += chunk_size
            
            # 计算传输速度
            elapsed_time = time.time() - self.start_time
            if elapsed_time > 0:
                self.speed = self.transferred_size / elapsed_time
            
            # 保存断点续传信息
            self._save_resume_info()
            
            # 通知回调
            if self.callback:
                self.callback('progress', {
                    'transferred_size': self.transferred_size,
                    'file_size': self.file_size,
                    'speed': self.speed,
                    'progress': self.transferred_size / self.file_size if self.file_size > 0 else 0
                })
        except Exception as e:
            logger.error(f"处理数据传输失败: {e}")
            self.transfer_error = str(e)
            self.transfer_active = False
            self._send_command(CMD_ERROR)
    
    def _handle_resume(self):
        """
        处理恢复传输
        """
        try:
            # 接收头信息
            header_data = self.socket.recv(HEADER_SIZE)
            header = json.loads(header_data.decode())
            
            file_name = header.get('file_name')
            transferred_size = header.get('transferred_size', 0)
            
            logger.info(f"恢复传输: {file_name}, 已传输: {transferred_size} 字节")
            
            # 设置文件指针
            if self.current_file:
                self.current_file.seek(transferred_size)
            
            # 更新传输状态
            self.transferred_size = transferred_size
            self.transfer_active = True
            self.transfer_paused = False
            self.start_time = time.time()
            
            # 继续发送数据
            self._send_file_data()
        except Exception as e:
            logger.error(f"处理恢复传输失败: {e}")
            self.transfer_error = str(e)
            self.transfer_active = False
            self._send_command(CMD_ERROR)
    
    def _handle_complete(self):
        """
        处理传输完成
        """
        try:
            # 接收头信息
            header_data = self.socket.recv(HEADER_SIZE)
            header = json.loads(header_data.decode())
            
            file_hash = header.get('file_hash')
            
            # 关闭文件
            if self.current_file:
                self.current_file.close()
                self.current_file = None
            
            # 验证文件完整性
            calculated_hash = self._calculate_file_hash(self.current_file_path)
            if calculated_hash == file_hash:
                logger.info("文件传输完成，校验成功")
                self.transfer_completed = True
                
                # 删除断点续传信息
                resume_path = f"{self.current_file_path}.resume"
                if os.path.exists(resume_path):
                    os.remove(resume_path)
            else:
                logger.error(f"文件校验失败: {calculated_hash} != {file_hash}")
                self.transfer_error = "文件校验失败"
            
            # 通知回调
            if self.callback:
                self.callback('complete', {
                    'file_path': self.current_file_path,
                    'file_size': self.file_size,
                    'success': self.transfer_completed,
                    'error': self.transfer_error
                })
            
            # 重置传输状态
            self.transfer_active = False
        except Exception as e:
            logger.error(f"处理传输完成失败: {e}")
            self.transfer_error = str(e)
            self.transfer_active = False
            
            # 通知回调
            if self.callback:
                self.callback('error', {
                    'error': str(e)
                })
    
    def _handle_error(self):
        """
        处理传输错误
        """
        try:
            # 接收错误信息
            error_data = self.socket.recv(HEADER_SIZE)
            error_info = json.loads(error_data.decode())
            
            error_message = error_info.get('error', '未知错误')
            logger.error(f"传输错误: {error_message}")
            
            # 更新传输状态
            self.transfer_error = error_message
            self.transfer_active = False
            
            # 关闭文件
            if self.current_file:
                self.current_file.close()
                self.current_file = None
            
            # 通知回调
            if self.callback:
                self.callback('error', {
                    'error': error_message
                })
        except Exception as e:
            logger.error(f"处理传输错误失败: {e}")
    
    def send_file(self, file_path):
        """
        发送文件
        
        Args:
            file_path: 文件路径
            
        Returns:
            bool: 是否成功开始发送
        """
        if not self.connected:
            logger.error("未连接，无法发送文件")
            return False
        
        try:
            # 检查文件是否存在
            if not os.path.exists(file_path):
                logger.error(f"文件不存在: {file_path}")
                return False
            
            # 获取文件信息
            file_size = os.path.getsize(file_path)
            file_name = os.path.basename(file_path)
            file_hash = self._calculate_file_hash(file_path)
            
            # 发送请求命令
            self._send_command(CMD_REQUEST)
            
            # 发送头信息
            header = {
                'file_name': file_name,
                'file_size': file_size,
                'file_hash': file_hash
            }
            self.socket.sendall(json.dumps(header).encode().ljust(HEADER_SIZE))
            
            # 等待响应
            command_data = self.socket.recv(COMMAND_SIZE)
            command = command_data.decode().strip()
            
            if command == CMD_ACCEPT:
                # 开始发送文件
                logger.info(f"对方接受传输: {file_name}")
                self.current_file_path = file_path
                self.current_file = open(file_path, 'rb')
                self.file_size = file_size
                self.transferred_size = 0
                self.transfer_active = True
                self.transfer_paused = False
                self.transfer_completed = False
                self.transfer_error = None
                self.start_time = time.time()
                
                # 启动发送线程
                threading.Thread(target=self._send_file_data, daemon=True).start()
                return True
            elif command == CMD_RESUME:
                # 处理恢复传输
                header_data = self.socket.recv(HEADER_SIZE)
                header = json.loads(header_data.decode())
                
                transferred_size = header.get('transferred_size', 0)
                logger.info(f"恢复传输: {file_name}, 已传输: {transferred_size} 字节")
                
                # 打开文件并设置指针
                self.current_file_path = file_path
                self.current_file = open(file_path, 'rb')
                self.current_file.seek(transferred_size)
                self.file_size = file_size
                self.transferred_size = transferred_size
                self.transfer_active = True
                self.transfer_paused = False
                self.transfer_completed = False
                self.transfer_error = None
                self.start_time = time.time()
                
                # 启动发送线程
                threading.Thread(target=self._send_file_data, daemon=True).start()
                return True
            elif command == CMD_REJECT:
                # 对方拒绝传输
                logger.info(f"对方拒绝传输: {file_name}")
                
                # 通知回调
                if self.callback:
                    self.callback('rejected', {
                        'file_path': file_path,
                        'file_name': file_name
                    })
                return False
            else:
                logger.warning(f"未知响应: {command}")
                return False
        except Exception as e:
            logger.error(f"发送文件失败: {e}")
            return False
    
    def _send_file_data(self):
        """
        发送文件数据
        """
        try:
            # 分块读取并发送文件
            while self.transfer_active and not self.transfer_paused:
                with self.lock:
                    # 读取数据块
                    chunk = self.current_file.read(CHUNK_SIZE)
                    if not chunk:
                        # 文件传输完成
                        break
                    
                    # 发送数据命令
                    self._send_command(CMD_DATA)
                    
                    # 发送数据块大小
                    self.socket.sendall(len(chunk).to_bytes(8, byteorder='big'))
                    
                    # 发送数据块
                    self.socket.sendall(chunk)
                    
                    # 更新传输状态
                    self.transferred_size += len(chunk)
                    
                    # 计算传输速度
                    elapsed_time = time.time() - self.start_time
                    if elapsed_time > 0:
                        self.speed = self.transferred_size / elapsed_time
                    
                    # 通知回调
                    if self.callback:
                        self.callback('progress', {
                            'transferred_size': self.transferred_size,
                            'file_size': self.file_size,
                            'speed': self.speed,
                            'progress': self.transferred_size / self.file_size if self.file_size > 0 else 0
                        })
                    
                    # 控制发送速度，避免占用过多资源
                    time.sleep(0.001)
            
            # 发送完成命令
            if self.transfer_active and not self.transfer_paused and not self.transfer_error:
                self._send_command(CMD_COMPLETE)
                
                # 发送完成信息
                complete_info = {
                    'file_hash': self._calculate_file_hash(self.current_file_path)
                }
                self.socket.sendall(json.dumps(complete_info).encode().ljust(HEADER_SIZE))
                
                # 更新传输状态
                self.transfer_completed = True
                self.transfer_active = False
                
                # 关闭文件
                if self.current_file:
                    self.current_file.close()
                    self.current_file = None
                
                logger.info("文件发送完成")
                
                # 通知回调
                if self.callback:
                    self.callback('complete', {
                        'file_path': self.current_file_path,
                        'file_size': self.file_size,
                        'success': True
                    })
        except Exception as e:
            logger.error(f"发送文件数据失败: {e}")
            self.transfer_error = str(e)
            self.transfer_active = False
            
            # 发送错误命令
            self._send_command(CMD_ERROR)
            error_info = {
                'error': str(e)
            }
            self.socket.sendall(json.dumps(error_info).encode().ljust(HEADER_SIZE))
            
            # 关闭文件
            if self.current_file:
                self.current_file.close()
                self.current_file = None
            
            # 通知回调
            if self.callback:
                self.callback('error', {
                    'error': str(e)
                })
    
    def pause_transfer(self):
        """
        暂停传输
        
        Returns:
            bool: 是否成功暂停
        """
        if not self.transfer_active:
            logger.warning("传输未激活，无法暂停")
            return False
        
        with self.lock:
            self.transfer_paused = True
            logger.info("传输已暂停")
            
            # 保存断点续传信息
            self._save_resume_info()
            
            # 通知回调
            if self.callback:
                self.callback('paused', {
                    'transferred_size': self.transferred_size,
                    'file_size': self.file_size
                })
            
            return True
    
    def resume_transfer(self):
        """
        恢复传输
        
        Returns:
            bool: 是否成功恢复
        """
        if not self.transfer_active or not self.transfer_paused:
            logger.warning("传输未暂停，无法恢复")
            return False
        
        with self.lock:
            self.transfer_paused = False
            self.start_time = time.time()  # 重置开始时间
            logger.info("传输已恢复")
            
            # 通知回调
            if self.callback:
                self.callback('resumed', {
                    'transferred_size': self.transferred_size,
                    'file_size': self.file_size
                })
            
            # 如果是发送方，继续发送数据
            if self.current_file and self.current_file.mode == 'rb':
                threading.Thread(target=self._send_file_data, daemon=True).start()
            
            return True
    
    def cancel_transfer(self):
        """
        取消传输
        
        Returns:
            bool: 是否成功取消
        """
        if not self.transfer_active:
            logger.warning("传输未激活，无法取消")
            return False
        
        with self.lock:
            self.transfer_active = False
            self.transfer_error = "用户取消传输"
            logger.info("传输已取消")
            
            # 关闭文件
            if self.current_file:
                self.current_file.close()
                self.current_file = None
            
            # 发送错误命令
            self._send_command(CMD_ERROR)
            error_info = {
                'error': "用户取消传输"
            }
            self.socket.sendall(json.dumps(error_info).encode().ljust(HEADER_SIZE))
            
            # 通知回调
            if self.callback:
                self.callback('cancelled', {
                    'transferred_size': self.transferred_size,
                    'file_size': self.file_size
                })
            
            return True
    
    def _send_command(self, command):
        """
        发送命令
        
        Args:
            command: 命令
        """
        try:
            self.socket.sendall(command.encode().ljust(COMMAND_SIZE))
        except Exception as e:
            logger.error(f"发送命令失败: {e}")
            self.connected = False
    
    def _calculate_file_hash(self, file_path):
        """
        计算文件哈希值
        
        Args:
            file_path: 文件路径
            
        Returns:
            str: 文件哈希值
        """
        if not os.path.exists(file_path):
            return ""
        
        try:
            hash_md5 = hashlib.md5()
            with open(file_path, 'rb') as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_md5.update(chunk)
            return hash_md5.hexdigest()
        except Exception as e:
            logger.error(f"计算文件哈希值失败: {e}")
            return ""
    
    def _save_resume_info(self):
        """
        保存断点续传信息
        """
        if not self.current_file_path:
            return
        
        try:
            resume_info = {
                'file_path': self.current_file_path,
                'file_size': self.file_size,
                'transferred_size': self.transferred_size,
                'timestamp': time.time()
            }
            
            resume_path = f"{self.current_file_path}.resume"
            with open(resume_path, 'w') as f:
                json.dump(resume_info, f)
        except Exception as e:
            logger.error(f"保存断点续传信息失败: {e}")
    
    def close(self):
        """
        关闭连接
        """
        # 取消传输
        if self.transfer_active:
            self.cancel_transfer()
        
        # 关闭套接字
        if self.socket:
            try:
                self.socket.close()
            except Exception as e:
                logger.error(f"关闭套接字失败: {e}")
            finally:
                self.socket = None
                self.connected = False
        
        logger.info("连接已关闭")
    
    def __del__(self):
        """
        析构函数，确保资源被释放
        """
        self.close()

    def _save_progress(self):
        """保存传输进度到状态文件"""
        progress_file = f'{self.current_file_path}.progress'
        progress_data = {
            'file_size': self.file_size,
            'transferred': self.transferred_size,
            'timestamp': time.time()
        }
        with open(progress_file, 'w') as f:
            json.dump(progress_data, f)
    
    def _load_progress(self):
        """加载最近传输进度"""
        progress_file = f'{self.current_file_path}.progress'
        if os.path.exists(progress_file):
            try:
                with open(progress_file, 'r') as f:
                    data = json.load(f)
                    return data['transferred']
            except Exception as e:
                logger.warning(f'加载进度文件失败: {e}')
        return 0
    
    def _clean_progress(self):
        """清除进度文件"""
        progress_file = f'{self.current_file_path}.progress'
        if os.path.exists(progress_file):
            try:
                os.remove(progress_file)
            except Exception as e:
                logger.warning(f'删除进度文件失败: {e}')