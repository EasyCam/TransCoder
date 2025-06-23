#!/bin/bash

# TransCoder 系统服务安装脚本

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_step() {
    echo -e "${BLUE}[STEP]${NC} $1"
}

# 检查权限
check_permissions() {
    if [[ $EUID -eq 0 ]]; then
        log_error "请不要使用root用户运行此脚本！"
        exit 1
    fi
    
    # 检查sudo权限
    if ! sudo -n true 2>/dev/null; then
        log_info "需要sudo权限来安装系统服务"
        sudo -v
    fi
}

# 检查环境
check_environment() {
    log_step "检查环境..."
    
    # 检查项目目录
    if [ ! -f "run.py" ] || [ ! -d "venv" ]; then
        log_error "请在已部署的TransCoder项目根目录下运行此脚本"
        exit 1
    fi
    
    # 获取项目绝对路径
    PROJECT_DIR=$(pwd)
    USER_NAME=$(whoami)
    
    log_info "项目目录: $PROJECT_DIR"
    log_info "用户名: $USER_NAME"
}

# 创建系统服务文件
create_service_files() {
    log_step "创建系统服务文件..."
    
    # 创建Ollama服务文件
    sudo tee /etc/systemd/system/ollama.service > /dev/null << EOF
[Unit]
Description=Ollama Service
After=network-online.target

[Service]
Type=exec
User=$USER_NAME
Group=$USER_NAME
ExecStart=/usr/local/bin/ollama serve
Environment="HOME=/home/$USER_NAME"
Environment="PATH=/usr/local/bin:/usr/bin:/bin"
Restart=always
RestartSec=3
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF
    
    # 创建TransCoder服务文件
    sudo tee /etc/systemd/system/transcoder.service > /dev/null << EOF
[Unit]
Description=TransCoder Multi-language Translation Platform
After=network-online.target ollama.service
Requires=ollama.service

[Service]
Type=exec
User=$USER_NAME
Group=$USER_NAME
WorkingDirectory=$PROJECT_DIR
ExecStart=$PROJECT_DIR/venv/bin/python run.py
Environment="PATH=$PROJECT_DIR/venv/bin:/usr/local/bin:/usr/bin:/bin"
Environment="PYTHONPATH=$PROJECT_DIR"
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF
    
    log_info "服务文件已创建"
}

# 启用服务
enable_services() {
    log_step "启用系统服务..."
    
    # 重新加载systemd
    sudo systemctl daemon-reload
    
    # 启用服务
    sudo systemctl enable ollama.service
    sudo systemctl enable transcoder.service
    
    log_info "服务已启用"
}

# 启动服务
start_services() {
    log_step "启动服务..."
    
    # 启动Ollama服务
    sudo systemctl start ollama.service
    sleep 5
    
    # 检查Ollama服务状态
    if sudo systemctl is-active --quiet ollama.service; then
        log_info "Ollama服务启动成功"
    else
        log_error "Ollama服务启动失败"
        sudo systemctl status ollama.service
        exit 1
    fi
    
    # 启动TransCoder服务
    sudo systemctl start transcoder.service
    sleep 3
    
    # 检查TransCoder服务状态
    if sudo systemctl is-active --quiet transcoder.service; then
        log_info "TransCoder服务启动成功"
    else
        log_error "TransCoder服务启动失败"
        sudo systemctl status transcoder.service
        exit 1
    fi
}

# 创建管理脚本
create_management_scripts() {
    log_step "创建服务管理脚本..."
    
    # 创建服务状态检查脚本
    cat > service_status.sh << 'EOF'
#!/bin/bash

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "TransCoder 服务状态"
echo "==================="

# 检查Ollama服务
if systemctl is-active --quiet ollama.service; then
    echo -e "Ollama服务:     ${GREEN}运行中${NC}"
else
    echo -e "Ollama服务:     ${RED}已停止${NC}"
fi

# 检查TransCoder服务
if systemctl is-active --quiet transcoder.service; then
    echo -e "TransCoder服务: ${GREEN}运行中${NC}"
else
    echo -e "TransCoder服务: ${RED}已停止${NC}"
fi

# 检查端口
if lsof -Pi :11434 -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo -e "Ollama端口:     ${GREEN}11434 (正常)${NC}"
else
    echo -e "Ollama端口:     ${RED}11434 (未监听)${NC}"
fi

if lsof -Pi :5000 -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo -e "TransCoder端口: ${GREEN}5000 (正常)${NC}"
else
    echo -e "TransCoder端口: ${RED}5000 (未监听)${NC}"
fi

echo ""
echo "访问地址: http://localhost:5000"
echo ""
echo "管理命令:"
echo "  启动服务: sudo systemctl start transcoder.service"
echo "  停止服务: sudo systemctl stop transcoder.service"
echo "  重启服务: sudo systemctl restart transcoder.service"
echo "  查看日志: sudo journalctl -u transcoder.service -f"
EOF
    
    chmod +x service_status.sh
    
    # 创建服务重启脚本
    cat > service_restart.sh << 'EOF'
#!/bin/bash

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${YELLOW}重启TransCoder服务...${NC}"

sudo systemctl restart ollama.service
sleep 3
sudo systemctl restart transcoder.service
sleep 3

echo -e "${GREEN}服务重启完成${NC}"
./service_status.sh
EOF
    
    chmod +x service_restart.sh
    
    log_info "管理脚本已创建: service_status.sh, service_restart.sh"
}

# 显示完成信息
show_completion_info() {
    echo ""
    echo "========================================"
    log_info "TransCoder 系统服务安装完成！"
    echo "========================================"
    echo ""
    echo "服务管理命令:"
    echo "  查看状态: ./service_status.sh"
    echo "  重启服务: ./service_restart.sh"
    echo "  启动服务: sudo systemctl start transcoder.service"
    echo "  停止服务: sudo systemctl stop transcoder.service"
    echo "  查看日志: sudo journalctl -u transcoder.service -f"
    echo ""
    echo "访问地址: http://localhost:5000"
    echo ""
    echo "服务现在会在系统启动时自动启动。"
    echo ""
}

# 主函数
main() {
    echo "========================================"
    echo "    TransCoder 系统服务安装"
    echo "========================================"
    echo ""
    
    check_permissions
    check_environment
    
    read -p "是否将TransCoder安装为系统服务？(y/n) [默认: y]: " install_service
    install_service=${install_service:-y}
    
    if [[ ! $install_service =~ ^[Yy]$ ]]; then
        log_info "安装已取消"
        exit 0
    fi
    
    create_service_files
    enable_services
    start_services
    create_management_scripts
    show_completion_info
}

main "$@" 