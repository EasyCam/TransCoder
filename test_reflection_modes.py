#!/usr/bin/env python3
"""
测试反思翻译模式功能
"""

import requests
import json
import time

# 测试配置
BASE_URL = "http://localhost:5000"
TEST_TEXT = "人工智能技术正在快速发展，它将深刻改变我们的生活方式。"
SOURCE_LANG = "zh-cn"
TARGET_LANG = "en"
MODEL = "qwen3:0.6b"

def test_simple_translation():
    """测试简单翻译"""
    print("=== 测试简单翻译 ===")
    
    data = {
        "source_text": TEST_TEXT,
        "source_lang": SOURCE_LANG,
        "target_langs": [TARGET_LANG],
        "model": MODEL
    }
    
    try:
        response = requests.post(f"{BASE_URL}/api/translate", json=data)
        if response.status_code == 200:
            result = response.json()
            translation = result['translations'][TARGET_LANG]['text']
            print(f"原文: {TEST_TEXT}")
            print(f"译文: {translation}")
            return translation
        else:
            print(f"翻译失败: {response.text}")
            return None
    except Exception as e:
        print(f"请求失败: {e}")
        return None

def test_reflection(source_text, translation):
    """测试反思功能"""
    print("\n=== 测试反思功能 ===")
    
    data = {
        "source_text": source_text,
        "translation": translation,
        "source_lang": SOURCE_LANG,
        "target_lang": TARGET_LANG,
        "model": MODEL
    }
    
    try:
        response = requests.post(f"{BASE_URL}/api/translate/reflect", json=data)
        if response.status_code == 200:
            result = response.json()
            reflection = result['reflection']
            print(f"反思意见: {reflection}")
            return reflection
        else:
            print(f"反思失败: {response.text}")
            return None
    except Exception as e:
        print(f"请求失败: {e}")
        return None

def test_improvement(source_text, current_translation, reflection):
    """测试改进功能"""
    print("\n=== 测试改进功能 ===")
    
    data = {
        "source_text": source_text,
        "current_translation": current_translation,
        "reflection": reflection,
        "source_lang": SOURCE_LANG,
        "target_lang": TARGET_LANG,
        "model": MODEL
    }
    
    try:
        response = requests.post(f"{BASE_URL}/api/translate/improve", json=data)
        if response.status_code == 200:
            result = response.json()
            improved_translation = result['improved_translation']
            print(f"改进译文: {improved_translation}")
            return improved_translation
        else:
            print(f"改进失败: {response.text}")
            return None
    except Exception as e:
        print(f"请求失败: {e}")
        return None

def test_reflection_workflow():
    """测试完整的反思翻译工作流"""
    print("开始测试反思翻译工作流...")
    print(f"测试文本: {TEST_TEXT}")
    print(f"源语言: {SOURCE_LANG} -> 目标语言: {TARGET_LANG}")
    print(f"使用模型: {MODEL}")
    print("-" * 60)
    
    # 第一步：简单翻译
    translation = test_simple_translation()
    if not translation:
        print("初始翻译失败，测试终止")
        return
    
    # 第二步：反思
    reflection = test_reflection(TEST_TEXT, translation)
    if not reflection:
        print("反思失败，测试终止")
        return
    
    # 第三步：改进
    improved_translation = test_improvement(TEST_TEXT, translation, reflection)
    if not improved_translation:
        print("改进失败，测试终止")
        return
    
    print("\n" + "=" * 60)
    print("反思翻译工作流测试完成！")
    print(f"初始译文: {translation}")
    print(f"最终译文: {improved_translation}")
    print("=" * 60)

def check_server():
    """检查服务器是否运行"""
    try:
        response = requests.get(f"{BASE_URL}/api/models")
        if response.status_code == 200:
            models = response.json()
            print(f"服务器运行正常，可用模型: {len(models.get('models', []))} 个")
            return True
        else:
            print(f"服务器响应异常: {response.status_code}")
            return False
    except Exception as e:
        print(f"无法连接到服务器: {e}")
        print("请确保TransCoder服务正在运行 (python run.py)")
        return False

if __name__ == "__main__":
    print("TransCoder 反思翻译模式测试")
    print("=" * 60)
    
    # 检查服务器状态
    if not check_server():
        exit(1)
    
    # 运行测试
    test_reflection_workflow() 