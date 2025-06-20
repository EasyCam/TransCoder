#!/usr/bin/env python3
"""
快速测试反思翻译功能修复
"""

import requests
import json
import time

# 测试配置
BASE_URL = "http://localhost:5000"
TEST_TEXT = "Hello world"
SOURCE_LANG = "en"
TARGET_LANG = "zh-cn"

def test_reflection_api():
    """测试反思翻译API"""
    print("测试反思翻译API...")
    
    # 1. 先进行简单翻译
    print("1. 进行初始翻译...")
    data = {
        "source_text": TEST_TEXT,
        "source_lang": SOURCE_LANG,
        "target_langs": [TARGET_LANG]
    }
    
    try:
        response = requests.post(f"{BASE_URL}/api/translate", json=data, timeout=30)
        if response.status_code == 200:
            result = response.json()
            translation = result['translations'][TARGET_LANG]['text']
            print(f"初始翻译: {translation}")
            
            # 2. 测试反思API
            print("2. 测试反思API...")
            reflect_data = {
                "source_text": TEST_TEXT,
                "translation": translation,
                "source_lang": SOURCE_LANG,
                "target_lang": TARGET_LANG
            }
            
            reflect_response = requests.post(f"{BASE_URL}/api/translate/reflect", 
                                           json=reflect_data, timeout=30)
            if reflect_response.status_code == 200:
                reflect_result = reflect_response.json()
                reflection = reflect_result['reflection']
                print(f"反思结果: {reflection}")
                
                # 3. 测试改进API
                print("3. 测试改进API...")
                improve_data = {
                    "source_text": TEST_TEXT,
                    "current_translation": translation,
                    "reflection": reflection,
                    "source_lang": SOURCE_LANG,
                    "target_lang": TARGET_LANG
                }
                
                improve_response = requests.post(f"{BASE_URL}/api/translate/improve", 
                                               json=improve_data, timeout=30)
                if improve_response.status_code == 200:
                    improve_result = improve_response.json()
                    improved = improve_result['improved_translation']
                    print(f"改进翻译: {improved}")
                    print("✅ 所有API测试通过！")
                    return True
                else:
                    print(f"❌ 改进API失败: {improve_response.text}")
                    return False
            else:
                print(f"❌ 反思API失败: {reflect_response.text}")
                return False
        else:
            print(f"❌ 翻译API失败: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        return False

def check_server():
    """检查服务器状态"""
    try:
        response = requests.get(f"{BASE_URL}/api/models", timeout=10)
        if response.status_code == 200:
            print("✅ 服务器运行正常")
            return True
        else:
            print(f"❌ 服务器响应异常: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ 无法连接服务器: {e}")
        return False

if __name__ == "__main__":
    print("TransCoder 反思翻译修复验证")
    print("=" * 40)
    
    if check_server():
        test_reflection_api()
    else:
        print("请先启动TransCoder服务器") 