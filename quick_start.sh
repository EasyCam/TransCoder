#!/bin/bash

# TransCoder 快速启动脚本
# 适用于已经部署过的环境

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

# 检查环境
check_environment() {
    log_step "检查运行环境..."
    
    # 检查是否在项目目录
    if [ ! -f "run.py" ] || [ ! -f "requirements.txt" ]; then
        log_error "请在TransCoder项目根目录下运行此脚本"
        exit 1
    fi
    
    # 检查Python依赖
    log_info "检查Python依赖..."
    missing_packages=()
    
    # 检查核心依赖
    if ! python3 -c "import flask" 2>/dev/null; then
        missing_packages+=("flask")
    fi
    if ! python3 -c "import ollama" 2>/dev/null; then
        missing_packages+=("ollama")
    fi
    if ! python3 -c "import faiss" 2>/dev/null; then
        missing_packages+=("faiss-cpu")
    fi
    if ! python3 -c "import sentence_transformers" 2>/dev/null; then
        missing_packages+=("sentence-transformers")
    fi
    
    if [ ${#missing_packages[@]} -gt 0 ]; then
        log_warn "发现缺失的Python包: ${missing_packages[*]}"
        read -p "是否现在安装缺失的包？(y/n) [默认: y]: " install_now
        install_now=${install_now:-y}
        
        if [[ $install_now =~ ^[Yy]$ ]]; then
            log_info "安装缺失的包..."
            pip3 install "${missing_packages[@]}"
            
            # 重新检查
            if ! python3 -c "import flask, ollama, faiss, sentence_transformers" 2>/dev/null; then
                log_error "安装后依然有包缺失，请运行 ./setup.sh 进行完整部署"
                exit 1
            fi
            log_info "包安装成功"
        else
            log_error "Python依赖不完整，请先运行 ./setup.sh 进行完整部署"
            exit 1
        fi
    else
        log_info "Python依赖检查通过"
    fi
    
    # 检查Ollama
    if ! command -v ollama &> /dev/null; then
        log_error "Ollama未安装，请先运行 ./setup.sh 进行完整部署"
        exit 1
    fi
    
    log_info "环境检查通过"
}

# 启动Ollama服务
start_ollama() {
    log_step "启动Ollama服务..."
    
    if pgrep -x "ollama" > /dev/null; then
        log_info "Ollama服务已在运行"
    else
        log_info "启动Ollama服务..."
        nohup ollama serve > ollama.log 2>&1 &
        sleep 3
    fi
    
    # 等待服务就绪
    local max_attempts=15
    local attempt=1
    
    while [ $attempt -le $max_attempts ]; do
        if curl -s http://localhost:11434/api/version > /dev/null 2>&1; then
            log_info "Ollama服务已就绪"
            break
        fi
        
        if [ $attempt -eq $max_attempts ]; then
            log_error "Ollama服务启动超时"
            log_error "请检查 ollama.log 文件获取错误信息"
            exit 1
        fi
        
        log_warn "等待Ollama服务启动... ($attempt/$max_attempts)"
        sleep 2
        ((attempt++))
    done
}

# 检查模型
check_models() {
    log_step "检查AI模型..."
    
    local models=$(ollama list | grep -v "NAME" | wc -l)
    if [ $models -eq 0 ]; then
        log_warn "没有发现已安装的模型"
        log_info "正在下载默认模型 qwen3:0.6b..."
        ollama pull qwen3:0.6b
    else
        log_info "发现 $models 个已安装的模型"
    fi
}

# 启动TransCoder
start_transcoder() {
    log_step "启动TransCoder..."
    
    # 检查端口
    if lsof -Pi :6000 -sTCP:LISTEN -t >/dev/null 2>&1; then
        log_error "端口6000已被占用"
        log_error "请运行 ./stop.sh 停止其他服务，或使用其他端口"
        exit 1
    fi
    
    # 检查Python依赖
    if ! python3 -c "import flask, ollama, faiss" 2>/dev/null; then
        log_warn "Python依赖可能不完整，正在重新安装..."
        pip3 install -r requirements.txt
    fi
    
    # 启动应用
    log_info "启动TransCoder应用..."
    log_info "访问地址: http://localhost:6000"
    log_info "按 Ctrl+C 停止服务"
    echo ""
    
    python3 run.py
}

# 主函数
main() {
    echo "========================================"
    echo "    TransCoder 快速启动"
    echo "========================================"
    echo ""
    
    check_environment
    start_ollama
    check_models
    start_transcoder
}

# 捕获Ctrl+C信号
trap 'echo -e "\n${YELLOW}[WARN]${NC} 正在停止服务..."; exit 0' INT

main "$@" 