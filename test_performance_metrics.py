#!/usr/bin/env python3
"""
测试所有翻译模式的性能指标显示
"""

import requests
import json
import time

# 测试配置
BASE_URL = "http://localhost:5000"
TEST_TEXT = "Hello, how are you today?"
SOURCE_LANG = "en"
TARGET_LANG = "zh-cn"
MODEL = "qwen3:0.6b"

def test_simple_translation():
    """测试简单翻译模式的性能指标"""
    print("=== 测试简单翻译模式 ===")
    
    data = {
        "source_text": TEST_TEXT,
        "source_lang": SOURCE_LANG,
        "target_langs": [TARGET_LANG],
        "model": MODEL
    }
    
    try:
        start_time = time.time()
        response = requests.post(f"{BASE_URL}/api/translate", json=data)
        end_time = time.time()
        
        if response.status_code == 200:
            result = response.json()
            translation = result['translations'][TARGET_LANG]
            
            print(f"翻译结果: {translation['text']}")
            
            # 检查性能指标
            if 'performance_metrics' in translation:
                metrics = translation['performance_metrics']
                print(f"✅ 性能指标:")
                print(f"  - tokens/s: {metrics.get('tokens_per_second', 'N/A')}")
                print(f"  - 总时间: {metrics.get('total_time', 'N/A')}s")
                print(f"  - 总tokens: {metrics.get('total_tokens', 'N/A')}")
                print(f"  - 实际耗时: {end_time - start_time:.2f}s")
            else:
                print("❌ 未找到性能指标")
                
            return translation
        else:
            print(f"❌ 翻译失败: {response.text}")
            return None
    except Exception as e:
        print(f"❌ 请求失败: {e}")
        return None

def test_reflection_api():
    """测试反思API的性能指标"""
    print("\n=== 测试反思API ===")
    
    # 先获取初始翻译
    translation_result = test_simple_translation()
    if not translation_result:
        return None
    
    data = {
        "source_text": TEST_TEXT,
        "translation": translation_result['text'],
        "source_lang": SOURCE_LANG,
        "target_lang": TARGET_LANG,
        "model": MODEL
    }
    
    try:
        start_time = time.time()
        response = requests.post(f"{BASE_URL}/api/translate/reflect", json=data)
        end_time = time.time()
        
        if response.status_code == 200:
            result = response.json()
            
            print(f"反思结果: {result['reflection'][:100]}...")
            
            # 检查性能指标
            if 'metrics' in result:
                metrics = result['metrics']
                print(f"✅ 反思性能指标:")
                print(f"  - tokens/s: {metrics.get('tokens_per_second', 'N/A')}")
                print(f"  - 总时间: {metrics.get('total_time', 'N/A')}s")
                print(f"  - 总tokens: {metrics.get('total_tokens', 'N/A')}")
                print(f"  - 实际耗时: {end_time - start_time:.2f}s")
            else:
                print("❌ 未找到反思性能指标")
                
            return result
        else:
            print(f"❌ 反思失败: {response.text}")
            return None
    except Exception as e:
        print(f"❌ 请求失败: {e}")
        return None

def test_improvement_api():
    """测试改进API的性能指标"""
    print("\n=== 测试改进API ===")
    
    # 先获取反思结果
    reflection_result = test_reflection_api()
    if not reflection_result:
        return None
    
    data = {
        "source_text": TEST_TEXT,
        "current_translation": "你好，你今天怎么样？",
        "reflection": reflection_result['reflection'],
        "source_lang": SOURCE_LANG,
        "target_lang": TARGET_LANG,
        "model": MODEL
    }
    
    try:
        start_time = time.time()
        response = requests.post(f"{BASE_URL}/api/translate/improve", json=data)
        end_time = time.time()
        
        if response.status_code == 200:
            result = response.json()
            
            print(f"改进结果: {result['improved_translation']}")
            
            # 检查性能指标
            if 'metrics' in result:
                metrics = result['metrics']
                print(f"✅ 改进性能指标:")
                print(f"  - tokens/s: {metrics.get('tokens_per_second', 'N/A')}")
                print(f"  - 总时间: {metrics.get('total_time', 'N/A')}s")
                print(f"  - 总tokens: {metrics.get('total_tokens', 'N/A')}")
                print(f"  - 实际耗时: {end_time - start_time:.2f}s")
            else:
                print("❌ 未找到改进性能指标")
                
            return result
        else:
            print(f"❌ 改进失败: {response.text}")
            return None
    except Exception as e:
        print(f"❌ 请求失败: {e}")
        return None

def check_server():
    """检查服务器状态"""
    try:
        response = requests.get(f"{BASE_URL}/api/models", timeout=10)
        if response.status_code == 200:
            models = response.json()
            print(f"✅ 服务器运行正常，可用模型: {len(models.get('models', []))} 个")
            return True
        else:
            print(f"❌ 服务器响应异常: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ 无法连接服务器: {e}")
        return False

if __name__ == "__main__":
    print("TransCoder 性能指标测试")
    print("=" * 50)
    
    if check_server():
        print(f"测试文本: {TEST_TEXT}")
        print(f"源语言: {SOURCE_LANG} -> 目标语言: {TARGET_LANG}")
        print(f"使用模型: {MODEL}")
        print("-" * 50)
        
        # 测试所有API的性能指标
        test_simple_translation()
        test_improvement_api()
        
        print("\n" + "=" * 50)
        print("性能指标测试完成！")
        print("前端界面中应该能看到所有翻译模式都显示tokens/s")
    else:
        print("请先启动TransCoder服务器") 