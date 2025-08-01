#!/bin/bash

# TransCoder 一键部署脚本 for Ubuntu 24.04
# 作者: EasyCam
# 版本: 1.0

set -e  # 遇到错误立即退出

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 日志函数
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

# 检查是否为root用户
check_root() {
    if [[ $EUID -eq 0 ]]; then
        log_error "请不要使用root用户运行此脚本！"
        exit 1
    fi
}

# 检查Ubuntu版本
check_ubuntu_version() {
    log_step "检查Ubuntu版本..."
    
    if ! grep -q "Ubuntu" /etc/os-release; then
        log_error "此脚本仅支持Ubuntu系统"
        exit 1
    fi
    
    VERSION=$(lsb_release -rs)
    if [[ $(echo "$VERSION >= 20.04" | bc -l) -eq 0 ]]; then
        log_warn "建议使用Ubuntu 20.04或更高版本，当前版本: $VERSION"
    else
        log_info "Ubuntu版本检查通过: $VERSION"
    fi
}

# 更新系统包
update_system() {
    log_step "更新系统包..."
    
    sudo apt update
    sudo apt upgrade -y
    
    log_info "系统包更新完成"
}

# 安装基础依赖
install_dependencies() {
    log_step "安装基础依赖..."
    
    # 安装Python和pip
    sudo apt install -y python3 python3-pip python3-venv python3-dev
    
    # 安装编译工具
    sudo apt install -y build-essential
    
    # 安装curl和wget
    sudo apt install -y curl wget
    
    # 安装git
    sudo apt install -y git
    
    # 安装其他必要工具
    sudo apt install -y bc lsb-release
    
    log_info "基础依赖安装完成"
}

# 安装Ollama
install_ollama() {
    log_step "安装Ollama..."
    
    if command -v ollama &> /dev/null; then
        log_info "Ollama已安装，跳过安装步骤"
        return
    fi
    
    # 下载并安装Ollama
    curl -fsSL https://ollama.ai/install.sh | sh
    
    # 检查安装是否成功
    if command -v ollama &> /dev/null; then
        log_info "Ollama安装成功"
    else
        log_error "Ollama安装失败"
        exit 1
    fi
}

# 启动Ollama服务
start_ollama_service() {
    log_step "启动Ollama服务..."
    
    # 检查Ollama是否已经在运行
    if pgrep -x "ollama" > /dev/null; then
        log_info "Ollama服务已在运行"
        return
    fi
    
    # 启动Ollama服务
    nohup ollama serve > /dev/null 2>&1 &
    
    # 等待服务启动
    sleep 5
    
    # 检查服务是否启动成功
    if pgrep -x "ollama" > /dev/null; then
        log_info "Ollama服务启动成功"
    else
        log_error "Ollama服务启动失败"
        exit 1
    fi
}

# 下载推荐模型
download_models() {
    log_step "下载推荐的AI模型..."
    
    # 等待Ollama服务完全启动
    sleep 3
    
    # 检查Ollama服务是否可用
    local max_attempts=10
    local attempt=1
    
    while [ $attempt -le $max_attempts ]; do
        if curl -s http://localhost:11434/api/version > /dev/null 2>&1; then
            log_info "Ollama服务已就绪"
            break
        fi
        
        if [ $attempt -eq $max_attempts ]; then
            log_error "Ollama服务启动超时"
            exit 1
        fi
        
        log_info "等待Ollama服务启动... (尝试 $attempt/$max_attempts)"
        sleep 5
        ((attempt++))
    done
    
    # 下载默认模型
    log_info "下载默认模型 qwen3:0.6b (轻量级，适合快速体验)..."
    ollama pull qwen3:0.6b
    
    # 询问是否下载更多模型
    echo ""
    read -p "是否下载更多模型？(y/n) [默认: n]: " download_more
    download_more=${download_more:-n}
    
    if [[ $download_more =~ ^[Yy]$ ]]; then
        log_info "下载中等质量模型 qwen3:4b..."
        ollama pull qwen3:4b
        
        log_info "下载轻量级英文模型 llama3.2:1b..."
        ollama pull llama3.2:1b
        
        read -p "是否下载高质量模型 qwen3:8b？(需要更多时间和存储空间) (y/n) [默认: n]: " download_large
        download_large=${download_large:-n}
        
        if [[ $download_large =~ ^[Yy]$ ]]; then
            log_info "下载高质量模型 qwen3:8b..."
            ollama pull qwen3:8b
        fi
    fi
    
    log_info "模型下载完成"
}

# 检查Python包是否已安装
check_python_package() {
    local package_name=$1
    local import_name=${2:-$1}  # 如果没有提供import名称，使用包名
    
    python3 -c "import $import_name" 2>/dev/null
    return $?
}

# 智能安装Python依赖
install_python_dependencies() {
    log_step "检查并安装Python依赖..."
    
    # 读取requirements.txt并检查每个包
    local packages_to_install=()
    local existing_packages=()
    
    # 核心包检查映射 (包名 -> 导入名)
    declare -A package_imports=(
        ["torch"]="torch"
        ["tensorflow"]="tensorflow"
        ["transformers"]="transformers"
        ["sentence-transformers"]="sentence_transformers"
        ["faiss-cpu"]="faiss"
        ["numpy"]="numpy"
        ["pandas"]="pandas"
        ["flask"]="flask"
        ["ollama"]="ollama"
        ["nltk"]="nltk"
        ["sacrebleu"]="sacrebleu"
        ["bert-score"]="bert_score"
        ["rouge-score"]="rouge_score"
        ["langdetect"]="langdetect"
        ["python-dotenv"]="dotenv"
        ["waitress"]="waitress"
        ["flask-cors"]="flask_cors"
        ["openpyxl"]="openpyxl"
    )
    
    log_info "检查已安装的包..."
    
    # 检查核心包
    for package in "${!package_imports[@]}"; do
        import_name="${package_imports[$package]}"
        if check_python_package "$package" "$import_name"; then
            existing_packages+=("$package")
            log_info "✓ $package 已安装，跳过"
        else
            packages_to_install+=("$package")
        fi
    done
    
    # 选择requirements文件
    local requirements_file="requirements.txt"
    if [ -f "requirements-minimal.txt" ]; then
        log_info "发现最小化依赖文件，将优先使用以避免环境冲突"
        requirements_file="requirements-minimal.txt"
    fi
    
    # 检查requirements文件中的其他包
    if [ -f "$requirements_file" ]; then
        while IFS= read -r line; do
            # 跳过空行和注释
            [[ -z "$line" || "$line" =~ ^[[:space:]]*# ]] && continue
            
            # 提取包名（去除版本号）
            package=$(echo "$line" | sed 's/[><=!].*//' | sed 's/\[.*\]//' | xargs)
            
            # 跳过已检查的核心包
            if [[ " ${!package_imports[@]} " =~ " $package " ]]; then
                continue
            fi
            
            # 检查其他包
            if check_python_package "$package"; then
                existing_packages+=("$package")
            else
                packages_to_install+=("$package")
            fi
        done < "$requirements_file"
    fi
    
    # 显示检查结果
    if [ ${#existing_packages[@]} -gt 0 ]; then
        log_info "已安装的包 (${#existing_packages[@]}个): ${existing_packages[*]}"
    fi
    
    if [ ${#packages_to_install[@]} -gt 0 ]; then
        log_warn "需要安装的包 (${#packages_to_install[@]}个): ${packages_to_install[*]}"
        
        # 询问用户是否继续安装
        echo ""
        read -p "是否安装缺失的Python包？(y/n) [默认: y]: " install_missing
        install_missing=${install_missing:-y}
        
        if [[ $install_missing =~ ^[Yy]$ ]]; then
            # 创建临时requirements文件，只包含需要安装的包
            local temp_requirements=$(mktemp)
            
            for package in "${packages_to_install[@]}"; do
                # 从requirements文件中找到完整的包声明
                if [ -f "$requirements_file" ]; then
                    grep -i "^$package" "$requirements_file" >> "$temp_requirements" 2>/dev/null || echo "$package" >> "$temp_requirements"
                else
                    echo "$package" >> "$temp_requirements"
                fi
            done
            
            log_info "安装缺失的包..."
            pip3 install -r "$temp_requirements"
            
            # 清理临时文件
            rm -f "$temp_requirements"
        else
            log_warn "跳过安装缺失的包，某些功能可能无法正常工作"
        fi
    else
        log_info "所有Python依赖都已安装！"
    fi
    
    log_info "Python依赖检查完成"
}

# 创建配置文件
create_config() {
    log_step "创建配置文件..."
    
    if [ ! -f ".env" ]; then
        cp env.example .env
        log_info "配置文件 .env 已创建"
    else
        log_info "配置文件已存在，跳过创建"
    fi
    
    # 创建必要的目录
    mkdir -p data/terminology
    mkdir -p data/vector_db
    mkdir -p uploads
    
    log_info "必要目录已创建"
}

# 测试安装
test_installation() {
    log_step "测试安装..."
    
    # 测试Python导入
    python3 -c "
import flask
import ollama
import numpy
import faiss
import sentence_transformers
print('所有Python依赖导入成功')
"
    
    # 测试Ollama连接
    if curl -s http://localhost:11434/api/version > /dev/null 2>&1; then
        log_info "Ollama服务连接正常"
    else
        log_error "Ollama服务连接失败"
        exit 1
    fi
    
    # 列出已安装的模型
    log_info "已安装的模型:"
    ollama list
    
    log_info "安装测试通过"
}

# 创建启动脚本
create_start_script() {
    log_step "创建启动脚本..."
    
    cat > start.sh << 'EOF'
#!/bin/bash

# TransCoder 启动脚本

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
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

# 检查Ollama服务
check_ollama() {
    if ! pgrep -x "ollama" > /dev/null; then
        log_info "启动Ollama服务..."
        nohup ollama serve > /dev/null 2>&1 &
        sleep 5
    fi
    
    # 等待Ollama服务就绪
    local max_attempts=10
    local attempt=1
    
    while [ $attempt -le $max_attempts ]; do
        if curl -s http://localhost:11434/api/version > /dev/null 2>&1; then
            log_info "Ollama服务已就绪"
            break
        fi
        
        if [ $attempt -eq $max_attempts ]; then
            log_error "Ollama服务启动失败"
            exit 1
        fi
        
        log_warn "等待Ollama服务启动... (尝试 $attempt/$max_attempts)"
        sleep 3
        ((attempt++))
    done
}

# 检查Python依赖
check_python_deps() {
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
                log_error "安装后依然有包缺失，请检查安装是否成功"
                exit 1
            fi
            log_info "包安装成功"
        else
            log_error "Python依赖不完整，请先安装缺失的包"
            exit 1
        fi
    else
        log_info "Python依赖检查通过"
    fi
}

# 启动TransCoder
start_transcoder() {
    log_info "启动TransCoder..."
    
    # 检查端口是否被占用
    if lsof -Pi :5555 -sTCP:LISTEN -t >/dev/null ; then
        log_error "端口5555已被占用，请先关闭占用该端口的程序"
        exit 1
    fi
    
    # 检查Python依赖
    check_python_deps
    
    # 启动应用
    python3 run.py
}

# 主函数
main() {
    echo "启动TransCoder多语种翻译平台..."
    echo "========================================"
    
    check_ollama
    start_transcoder
}

main "$@"
EOF
    
    chmod +x start.sh
    log_info "启动脚本 start.sh 已创建"
}

# 创建停止脚本
create_stop_script() {
    log_step "创建停止脚本..."
    
    cat > stop.sh << 'EOF'
#!/bin/bash

# TransCoder 强制停止脚本

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
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

# 停止TransCoder
stop_transcoder() {
    log_info "停止TransCoder应用..."
    
    # 查找并终止Python进程
    local pids=$(pgrep -f "run.py\|app.py")
    if [ -n "$pids" ]; then
        echo "$pids" | xargs kill -TERM 2>/dev/null || true
        sleep 3
        
        # 如果还在运行，强制终止
        local remaining_pids=$(pgrep -f "run.py\|app.py")
        if [ -n "$remaining_pids" ]; then
            log_warn "强制终止TransCoder进程..."
            echo "$remaining_pids" | xargs kill -KILL 2>/dev/null || true
        fi
        
        log_info "TransCoder应用已停止"
    else
        log_info "TransCoder应用未在运行"
    fi
}

# 停止Ollama服务
stop_ollama() {
    log_info "停止Ollama服务..."
    
    local pids=$(pgrep -x "ollama")
    if [ -n "$pids" ]; then
        echo "$pids" | xargs kill -TERM 2>/dev/null || true
        sleep 3
        
        # 如果还在运行，强制终止
        local remaining_pids=$(pgrep -x "ollama")
        if [ -n "$remaining_pids" ]; then
            log_warn "强制终止Ollama进程..."
            echo "$remaining_pids" | xargs kill -KILL 2>/dev/null || true
        fi
        
        log_info "Ollama服务已停止"
    else
        log_info "Ollama服务未在运行"
    fi
}

# 清理端口
cleanup_ports() {
    log_info "清理相关端口..."
    
    # 查找占用5555端口的进程
    local port_5555_pids=$(lsof -ti:5555)
    if [ -n "$port_5555_pids" ]; then
        log_warn "强制终止占用端口5555的进程..."
        echo "$port_5555_pids" | xargs kill -KILL 2>/dev/null || true
    fi
    
    # 查找占用11434端口的进程（Ollama默认端口）
    local port_11434_pids=$(lsof -ti:11434)
    if [ -n "$port_11434_pids" ]; then
        log_warn "强制终止占用端口11434的进程..."
        echo "$port_11434_pids" | xargs kill -KILL 2>/dev/null || true
    fi
    
    log_info "端口清理完成"
}

# 显示状态
show_status() {
    echo ""
    log_info "进程状态检查:"
    
    if pgrep -f "run.py\|app.py" > /dev/null; then
        log_warn "TransCoder进程仍在运行"
    else
        log_info "TransCoder进程已停止"
    fi
    
    if pgrep -x "ollama" > /dev/null; then
        log_warn "Ollama进程仍在运行"
    else
        log_info "Ollama进程已停止"
    fi
    
    if lsof -Pi :5555 -sTCP:LISTEN -t >/dev/null 2>&1; then
        log_warn "端口5555仍被占用"
    else
        log_info "端口5555已释放"
    fi
    
    if lsof -Pi :11434 -sTCP:LISTEN -t >/dev/null 2>&1; then
        log_warn "端口11434仍被占用"
    else
        log_info "端口11434已释放"
    fi
}

# 主函数
main() {
    echo "强制停止TransCoder及相关服务..."
    echo "=================================="
    
    stop_transcoder
    
    read -p "是否同时停止Ollama服务？(y/n) [默认: n]: " stop_ollama_choice
    stop_ollama_choice=${stop_ollama_choice:-n}
    
    if [[ $stop_ollama_choice =~ ^[Yy]$ ]]; then
        stop_ollama
    fi
    
    cleanup_ports
    show_status
    
    echo ""
    log_info "停止操作完成"
}

main "$@"
EOF
    
    chmod +x stop.sh
    log_info "停止脚本 stop.sh 已创建"
}

# 显示完成信息
show_completion_info() {
    echo ""
    echo "========================================"
    log_info "TransCoder 部署完成！"
    echo "========================================"
    echo ""
    echo "使用方法："
    echo "  启动服务:  ./start.sh"
    echo "  停止服务:  ./stop.sh"
    echo ""
    echo "访问地址:  http://localhost:5555"
    echo ""
    echo "已安装的模型："
    ollama list | grep -E "NAME|qwen|llama" | head -10
    echo ""
    log_info "享受使用TransCoder多语种翻译平台！"
    echo ""
}

# 主函数
main() {
    echo "========================================"
    echo "    TransCoder 一键部署脚本"
    echo "    Ubuntu 24.04 版本"
    echo "    作者: EasyCam"
    echo "========================================"
    echo ""
    
    check_root
    check_ubuntu_version
    
    # 询问是否继续
    read -p "是否继续安装？(y/n) [默认: y]: " continue_install
    continue_install=${continue_install:-y}
    
    if [[ ! $continue_install =~ ^[Yy]$ ]]; then
        log_info "安装已取消"
        exit 0
    fi
    
    update_system
    install_dependencies
    install_ollama
    start_ollama_service
    download_models
    install_python_dependencies
    create_config
    test_installation
    create_start_script
    create_stop_script
    show_completion_info
}

# 执行主函数
main "$@" 