#!/bin/bash

# 给所有脚本添加执行权限

echo "正在给脚本添加执行权限..."

# 主要脚本
chmod +x setup.sh
chmod +x start.sh  # 这个会在setup.sh中生成
chmod +x stop.sh   # 这个会在setup.sh中生成
chmod +x quick_start.sh
chmod +x install_service.sh

# 测试脚本
chmod +x test_*.py
chmod +x test_environment.py

# 运行脚本
chmod +x run.py

echo "执行权限添加完成！"
echo ""
echo "可用的脚本："
echo "  ./setup.sh          - 一键部署（首次使用）"
echo "  ./quick_start.sh     - 快速启动"
echo "  ./install_service.sh - 安装为系统服务"
echo ""
echo "部署后生成的脚本："
echo "  ./start.sh           - 标准启动"
echo "  ./stop.sh            - 强制停止"
echo ""
echo "使用步骤："
echo "1. 环境检测：python test_environment.py"
echo "2. 首次部署：./setup.sh (智能检测现有包)"
echo "3. 日常启动：./start.sh 或 ./quick_start.sh"
echo "4. 停止服务：./stop.sh" 