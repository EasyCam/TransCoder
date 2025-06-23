#!/usr/bin/env python3
"""
TransCoder 环境检测测试脚本
测试智能依赖检测功能
"""

import sys
import importlib
import subprocess

def check_package(package_name, import_name=None):
    """检查包是否已安装"""
    if import_name is None:
        import_name = package_name
    
    try:
        importlib.import_module(import_name)
        return True
    except ImportError:
        return False

def get_package_version(package_name):
    """获取包版本"""
    try:
        result = subprocess.run([sys.executable, '-m', 'pip', 'show', package_name], 
                              capture_output=True, text=True, check=False)
        if result.returncode == 0:
            for line in result.stdout.split('\n'):
                if line.startswith('Version:'):
                    return line.split(':', 1)[1].strip()
        return "未知版本"
    except:
        return "未知版本"

def main():
    """主测试函数"""
    print("TransCoder 环境检测测试")
    print("=" * 50)
    
    # 核心依赖包检测
    core_packages = {
        'flask': 'flask',
        'ollama': 'ollama', 
        'faiss-cpu': 'faiss',
        'sentence-transformers': 'sentence_transformers',
        'numpy': 'numpy',
        'pandas': 'pandas'
    }
    
    # 可选的大型包检测
    optional_packages = {
        'torch': 'torch',
        'tensorflow': 'tensorflow',
        'transformers': 'transformers',
        'bert-score': 'bert_score'
    }
    
    print("核心依赖检测:")
    print("-" * 30)
    missing_core = []
    
    for package, import_name in core_packages.items():
        if check_package(package, import_name):
            version = get_package_version(package)
            print(f"✅ {package:<20} (版本: {version})")
        else:
            print(f"❌ {package:<20} (缺失)")
            missing_core.append(package)
    
    print(f"\n可选包检测 (现有环境保护):")
    print("-" * 30)
    existing_optional = []
    
    for package, import_name in optional_packages.items():
        if check_package(package, import_name):
            version = get_package_version(package)
            print(f"✅ {package:<20} (版本: {version}) - 将跳过安装")
            existing_optional.append(package)
        else:
            print(f"⚪ {package:<20} (未安装)")
    
    print(f"\n检测结果总结:")
    print("=" * 50)
    
    if missing_core:
        print(f"❌ 缺失核心包 ({len(missing_core)}个): {', '.join(missing_core)}")
        print("   建议运行: pip install " + " ".join(missing_core))
    else:
        print("✅ 所有核心依赖都已安装")
    
    if existing_optional:
        print(f"🛡️  现有环境保护 ({len(existing_optional)}个): {', '.join(existing_optional)}")
        print("   这些包将被跳过安装，避免环境冲突")
    
    print(f"\nPython版本: {sys.version}")
    print(f"pip版本: ", end="")
    try:
        result = subprocess.run([sys.executable, '-m', 'pip', '--version'], 
                              capture_output=True, text=True, check=False)
        print(result.stdout.strip())
    except:
        print("无法获取")
    
    print("\n建议:")
    if missing_core:
        print("- 运行 ./setup.sh 进行智能安装")
        print("- 或使用 pip install -r requirements-minimal.txt")
    else:
        print("- 环境已就绪，可以直接运行 ./start.sh 或 python run.py")

if __name__ == "__main__":
    main() 