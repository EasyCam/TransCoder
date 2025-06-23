#!/usr/bin/env python3
"""
测试翻译文本清理功能
"""

import requests
import json

# 测试配置
BASE_URL = "http://localhost:6000"

def test_reflection_cleaning():
    """测试反思翻译的文本清理功能"""
    print("测试反思翻译的文本清理功能")
    print("=" * 50)
    
    test_cases = [
        {
            "name": "简单英译中",
            "source_text": "Hello, how are you today?",
            "source_lang": "en",
            "target_lang": "zh-cn"
        },
        {
            "name": "中译英",
            "source_text": "人工智能技术正在快速发展，它将深刻改变我们的生活方式。",
            "source_lang": "zh-cn", 
            "target_lang": "en"
        },
        {
            "name": "长文本翻译",
            "source_text": "Machine learning is a subset of artificial intelligence that provides systems the ability to automatically learn and improve from experience without being explicitly programmed. Machine learning focuses on the development of computer programs that can access data and use it to learn for themselves.",
            "source_lang": "en",
            "target_lang": "zh-cn"
        }
    ]
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n{i}. 测试案例: {test_case['name']}")
        print(f"源文本: {test_case['source_text'][:50]}...")
        
        try:
            # 第一步：初始翻译
            print("  步骤1: 初始翻译")
            initial_response = requests.post(f"{BASE_URL}/api/translate", json={
                "source_text": test_case['source_text'],
                "source_lang": test_case['source_lang'],
                "target_langs": [test_case['target_lang']]
            }, timeout=30)
            
            if initial_response.status_code != 200:
                print(f"  ❌ 初始翻译失败: {initial_response.text}")
                continue
                
            initial_result = initial_response.json()
            initial_translation = initial_result['translations'][test_case['target_lang']]['text']
            print(f"  初始翻译: {initial_translation}")
            
            # 第二步：反思
            print("  步骤2: 反思分析")
            reflection_response = requests.post(f"{BASE_URL}/api/translate/reflect", json={
                "source_text": test_case['source_text'],
                "translation": initial_translation,
                "source_lang": test_case['source_lang'],
                "target_lang": test_case['target_lang']
            }, timeout=30)
            
            if reflection_response.status_code != 200:
                print(f"  ❌ 反思失败: {reflection_response.text}")
                continue
                
            reflection_result = reflection_response.json()
            reflection = reflection_result['reflection']
            print(f"  反思意见: {reflection[:100]}...")
            
            # 第三步：改进翻译
            print("  步骤3: 改进翻译")
            improvement_response = requests.post(f"{BASE_URL}/api/translate/improve", json={
                "source_text": test_case['source_text'],
                "current_translation": initial_translation,
                "reflection": reflection,
                "source_lang": test_case['source_lang'],
                "target_lang": test_case['target_lang']
            }, timeout=30)
            
            if improvement_response.status_code != 200:
                print(f"  ❌ 改进失败: {improvement_response.text}")
                continue
                
            improvement_result = improvement_response.json()
            improved_translation = improvement_result['improved_translation']
            
            # 检查清理效果
            print(f"  改进翻译: {improved_translation}")
            
            # 验证清理质量
            quality_issues = []
            
            # 检查是否包含说明性文本
            explanation_patterns = [
                '改进后的翻译', '优化后的翻译', 'improved translation', 
                'here is', '以下是', '翻译结果', 'translation:'
            ]
            
            for pattern in explanation_patterns:
                if pattern.lower() in improved_translation.lower():
                    quality_issues.append(f"包含说明性文本: '{pattern}'")
            
            # 检查是否有多余的换行或格式问题
            lines = improved_translation.split('\n')
            if len(lines) > 3 and len(test_case['source_text'].split('\n')) <= 2:
                quality_issues.append("可能包含多余的换行或格式")
            
            # 检查是否过短（可能清理过度）
            if len(improved_translation.strip()) < 10:
                quality_issues.append("翻译结果过短，可能清理过度")
            
            if quality_issues:
                print(f"  ⚠️  质量问题: {'; '.join(quality_issues)}")
            else:
                print(f"  ✅ 清理质量良好")
                
            print(f"  对比:")
            print(f"    初始: {initial_translation}")
            print(f"    改进: {improved_translation}")
            
        except Exception as e:
            print(f"  ❌ 测试失败: {e}")

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
    print("TransCoder 翻译文本清理功能测试")
    print("=" * 50)
    
    if check_server():
        test_reflection_cleaning()
    else:
        print("请先启动TransCoder服务器") 