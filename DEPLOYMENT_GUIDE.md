# TransCoder Ubuntu 24.04 部署指南

## 概述

本指南提供了在Ubuntu 24.04系统上一键部署和管理TransCoder多语种翻译平台的完整解决方案。

## 系统要求

- **操作系统**: Ubuntu 20.04+ (推荐 24.04)
- **内存**: 最低 8GB RAM (推荐 16GB+)
- **存储**: 最低 20GB 可用空间
- **网络**: 稳定的互联网连接（用于下载模型）
- **权限**: 普通用户账户 + sudo权限

## 快速开始

### 1. 一键部署（首次安装）

```bash
# 克隆项目
git clone https://github.com/EasyCam/TransCoder.git
cd TransCoder

# 给脚本添加执行权限
chmod +x setup.sh

# 运行一键部署脚本
./setup.sh
```

**部署过程包括：**
- 系统包更新
- 安装Python 3和相关依赖
- 安装Ollama AI引擎
- 下载推荐的AI模型
- **智能检测现有Python包**（避免破坏现有环境）
- 安装缺失的Python依赖包
- 创建配置文件
- 测试安装完整性

### 2. 启动服务

部署完成后，使用以下命令启动：

```bash
# 方式1: 使用自动生成的启动脚本
./start.sh

# 方式2: 使用快速启动脚本
./quick_start.sh
```

### 3. 访问应用

在浏览器中访问：http://localhost:6000

## 脚本说明

### 主要脚本

| 脚本名称 | 功能描述 | 使用场景 |
|---------|---------|---------|
| `setup.sh` | 一键部署脚本 | 首次安装时使用 |
| `start.sh` | 标准启动脚本 | 日常启动服务 |
| `quick_start.sh` | 快速启动脚本 | 已部署环境的快速启动 |
| `stop.sh` | 强制停止脚本 | 停止所有相关服务 |
| `install_service.sh` | 系统服务安装 | 将应用安装为系统服务 |

### 服务管理脚本（安装系统服务后）

| 脚本名称 | 功能描述 |
|---------|---------|
| `service_status.sh` | 查看服务状态 |
| `service_restart.sh` | 重启服务 |

## 详细使用说明

### 一键部署脚本 (setup.sh)

**功能特点：**
- 自动检测系统环境
- **智能检测现有Python包**（如torch、tensorflow等）
- 智能跳过已安装的组件，避免环境冲突
- 交互式模型选择
- 完整性测试验证

**使用方法：**
```bash
./setup.sh
```

**部署选项：**
- 基础安装：只下载默认轻量级模型
- 完整安装：下载多个质量不同的模型
- 自定义安装：根据需求选择特定模型

### 启动脚本 (start.sh)

**功能特点：**
- 自动启动Ollama服务
- 检查端口占用
- 激活Python虚拟环境
- 启动TransCoder应用

**使用方法：**
```bash
./start.sh
```

### 快速启动脚本 (quick_start.sh)

**适用场景：**
- 环境已经部署完成
- 需要快速启动服务
- 日常开发使用

**功能特点：**
- 环境完整性检查
- 自动模型检测
- 依赖完整性验证

**使用方法：**
```bash
./quick_start.sh
```

### 停止脚本 (stop.sh)

**功能特点：**
- 优雅停止TransCoder进程
- 可选择是否停止Ollama服务
- 强制清理占用端口
- 显示停止后状态

**使用方法：**
```bash
./stop.sh
```

**停止选项：**
- 仅停止TransCoder
- 同时停止Ollama服务
- 强制清理所有相关进程

### 系统服务安装 (install_service.sh)

**功能特点：**
- 创建systemd服务文件
- 配置自动启动
- 生成管理脚本
- 服务依赖管理

**使用方法：**
```bash
./install_service.sh
```

**安装后的优势：**
- 开机自动启动
- 系统级别的服务管理
- 自动故障恢复
- 日志集成

## 系统服务管理

### 安装为系统服务

```bash
# 安装系统服务
./install_service.sh

# 查看服务状态
./service_status.sh

# 重启服务
./service_restart.sh
```

### 系统服务命令

```bash
# 启动服务
sudo systemctl start transcoder.service

# 停止服务
sudo systemctl stop transcoder.service

# 重启服务
sudo systemctl restart transcoder.service

# 查看服务状态
sudo systemctl status transcoder.service

# 查看实时日志
sudo journalctl -u transcoder.service -f

# 禁用自动启动
sudo systemctl disable transcoder.service

# 启用自动启动
sudo systemctl enable transcoder.service
```

## 模型管理

### 查看已安装模型

```bash
ollama list
```

### 下载新模型

```bash
# 轻量级模型（适合快速体验）
ollama pull qwen3:0.6b
ollama pull llama3.2:1b

# 中等质量模型（平衡性能和质量）
ollama pull qwen3:4b
ollama pull llama3.2:3b

# 高质量模型（最佳翻译质量）
ollama pull qwen3:8b
ollama pull llama3.2:7b
```

### 删除模型

```bash
ollama rm <model_name>
```

## 故障排除

### 常见问题

#### 1. Ollama服务启动失败

**症状：**
```
[ERROR] Ollama服务启动失败
```

**解决方案：**
```bash
# 检查Ollama安装
which ollama

# 手动启动Ollama
ollama serve

# 检查端口占用
lsof -i :11434
```

#### 2. 端口被占用

**症状：**
```
[ERROR] 端口6000已被占用
```

**解决方案：**
```bash
# 查找占用进程
lsof -i :6000

# 停止占用进程
./stop.sh

# 或手动终止进程
sudo kill -9 <PID>
```

#### 3. Python依赖问题

**症状：**
```
ModuleNotFoundError: No module named 'xxx'
```

**解决方案：**
```bash
# 激活虚拟环境
source venv/bin/activate

# 重新安装依赖
pip install -r requirements.txt

# 或重新部署
./setup.sh
```

#### 4. 模型下载失败

**症状：**
```
Error: failed to download model
```

**解决方案：**
```bash
# 检查网络连接
curl -I https://ollama.ai

# 手动下载模型
ollama pull qwen3:0.6b

# 检查磁盘空间
df -h
```

### 日志查看

```bash
# TransCoder应用日志
tail -f transcoder.log

# Ollama服务日志
tail -f ollama.log

# 系统服务日志（如果安装了系统服务）
sudo journalctl -u transcoder.service -f
sudo journalctl -u ollama.service -f
```

### 重置环境

```bash
# 停止所有服务
./stop.sh

# 删除虚拟环境
rm -rf venv

# 重新部署
./setup.sh
```

## 性能优化

### 硬件优化

1. **内存**：确保至少8GB RAM，推荐16GB+
2. **存储**：使用SSD可显著提升模型加载速度
3. **GPU**：如有NVIDIA GPU，Ollama会自动使用GPU加速

### 软件优化

1. **模型选择**：
   - 快速响应：使用qwen3:0.6b或llama3.2:1b
   - 平衡质量：使用qwen3:4b或llama3.2:3b
   - 最佳质量：使用qwen3:8b或llama3.2:7b

2. **并发设置**：
   - 调整worker进程数量
   - 优化内存使用

3. **网络优化**：
   - 使用本地网络访问
   - 配置反向代理（如nginx）

## 安全建议

1. **防火墙配置**：
```bash
# 只允许本地访问
sudo ufw allow from 127.0.0.1 to any port 6000

# 或允许特定网段访问
sudo ufw allow from 192.168.1.0/24 to any port 6000
```

2. **用户权限**：
   - 不要使用root用户运行服务
   - 使用专用的服务账户

3. **数据备份**：
   - 定期备份术语库和翻译记忆库
   - 备份配置文件

## 更新升级

### 更新TransCoder代码

```bash
# 停止服务
./stop.sh

# 拉取最新代码
git pull origin main

# 更新依赖
source venv/bin/activate
pip install -r requirements.txt

# 重启服务
./start.sh
```

### 更新Ollama

```bash
# 更新Ollama
curl -fsSL https://ollama.ai/install.sh | sh

# 重启服务
./service_restart.sh  # 如果使用系统服务
# 或
./stop.sh && ./start.sh
```

## 卸载

### 完全卸载

```bash
# 停止服务
./stop.sh

# 删除系统服务（如果安装了）
sudo systemctl stop transcoder.service ollama.service
sudo systemctl disable transcoder.service ollama.service
sudo rm /etc/systemd/system/transcoder.service
sudo rm /etc/systemd/system/ollama.service
sudo systemctl daemon-reload

# 删除Ollama
sudo rm /usr/local/bin/ollama
sudo rm -rf ~/.ollama

# 删除项目文件
cd ..
rm -rf TransCoder
```

## 技术支持

如果遇到问题，请：

1. 查看日志文件获取详细错误信息
2. 检查系统资源使用情况
3. 参考本文档的故障排除部分
4. 在GitHub仓库提交Issue

---

**版本**: 1.0  
**最后更新**: 2025年1月  
**适用系统**: Ubuntu 20.04+ 