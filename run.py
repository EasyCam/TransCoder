#!/usr/bin/env python
"""
TransCoder 启动脚本
"""
import os
import sys
from waitress import serve
from app import app
import config

def main():
    """主函数"""
    # 检查是否在生产环境运行
    if not config.DEBUG:
        # 生产环境使用waitress
        print("Starting TransCoder in production mode...")
        print(f"Server running on http://0.0.0.0:6000")
        serve(app, host='0.0.0.0', port=6000)
    else:
        # 开发环境使用Flask内置服务器
        print("Starting TransCoder in development mode...")
        print(f"Server running on http://localhost:6000")
        app.run(debug=True, host='0.0.0.0', port=6000)

if __name__ == '__main__':
    main() 