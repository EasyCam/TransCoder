import ollama
from langdetect import detect
import config
import json
from typing import List, Dict, Any

class TranslationService:
    def __init__(self):
        self.client = ollama.Client(host=config.OLLAMA_HOST)
        self.default_model = config.OLLAMA_MODEL
        
    def get_available_models(self) -> List[str]:
        """获取可用的Ollama模型列表"""
        try:
            print(f"Connecting to Ollama at {config.OLLAMA_HOST}")
            models = self.client.list()
            print(f"Raw response from Ollama: {models}")
            
            if not models or 'models' not in models:
                print("No models found in response")
                return []
            
            # 修复：使用正确的字段名或属性访问
            model_names = []
            for model in models['models']:
                # 尝试多种可能的字段名
                if hasattr(model, 'model'):
                    model_names.append(model.model)
                elif hasattr(model, 'name'):
                    model_names.append(model.name)
                elif isinstance(model, dict):
                    if 'model' in model:
                        model_names.append(model['model'])
                    elif 'name' in model:
                        model_names.append(model['name'])
                else:
                    # 如果是字符串类型，直接使用
                    model_names.append(str(model))
            
            print(f"Found models: {model_names}")
            
            # 对模型名称进行排序
            return sorted(model_names)
        except ollama.ResponseError as e:
            print(f"Ollama response error: {e}")
            return []
        except ConnectionError as e:
            print(f"Connection error: {e}")
            raise Exception(f"无法连接到Ollama服务 ({config.OLLAMA_HOST})")
        except Exception as e:
            print(f"Error getting models: {e}")
            if "connection" in str(e).lower():
                raise Exception(f"Ollama服务连接失败，请确保服务正在运行")
            raise Exception(f"获取模型列表失败: {str(e)}")
    
    def detect_language(self, text: str) -> str:
        """检测文本语言，支持中文变体检测"""
        try:
            lang = detect(text)
            
            # 如果检测到中文，进一步判断是简体、繁体还是文言文
            if lang == 'zh' or lang.startswith('zh'):
                return self._detect_chinese_variant(text)
            
            return lang
        except:
            return 'unknown'
    
    def _detect_chinese_variant(self, text: str) -> str:
        """检测中文变体（大陆简体、港澳台繁体、文言文简体、文言文繁体）"""
        # 简单的启发式规则来区分中文变体
        
        # 文言文特征：文言虚词和语法结构
        classical_indicators = [
            '之', '其', '者', '也', '矣', '乎', '哉', '焉', '耳', '而已',
            '曰', '云', '谓', '所谓', '盖', '夫', '且', '若', '如', '于是',
            '然则', '故', '是故', '以为', '不亦', '岂不', '何不', '安得'
        ]
        
        # 繁体字特征（一些常见的繁简对照）
        traditional_chars = [
            '區', '國', '學', '經', '義', '時', '發', '當', '來', '對',
            '個', '會', '點', '這', '為', '關', '開', '間', '長', '門',
            '電', '話', '號', '車', '過', '問', '題', '現', '實', '際'
        ]
        
        # 计算各种特征的出现频率
        classical_score = sum(1 for indicator in classical_indicators if indicator in text)
        traditional_score = sum(1 for char in traditional_chars if char in text)
        
        text_length = len(text)
        
        # 如果文言文特征明显（考虑文本长度）
        if classical_score / max(text_length / 10, 1) > 0.3:
            # 判断是文言文简体还是繁体
            if traditional_score / max(text_length / 20, 1) > 0.2:
                return 'zh-classical-tw'  # 文言文繁体
            else:
                return 'zh-classical-cn'  # 文言文简体
        
        # 如果繁体字特征明显但不是文言文
        if traditional_score / max(text_length / 20, 1) > 0.2:
            return 'zh-tw'  # 港澳台地区现代文繁体
        
        # 默认返回大陆地区现代文简体
        return 'zh-cn'
    
    def translate(self, source_text: str, source_lang: str, target_langs: List[str], 
                 use_vector_db: bool = True, use_terminology: bool = True,
                 vector_db_service=None, terminology_service=None,
                 model: str = None) -> Dict[str, Any]:
        """执行多语种并行翻译"""
        
        # 使用指定的模型或默认模型
        current_model = model if model else self.default_model
        
        # 如果source_lang是auto，则自动检测
        if source_lang == 'auto':
            source_lang = self.detect_language(source_text)
        
        results = {
            'source_text': source_text,
            'source_lang': source_lang,
            'translations': {},
            'model_used': current_model
        }
        
        # 获取相似翻译和术语
        similar_translations = {}
        terminology_dict = {}
        
        if use_vector_db and vector_db_service:
            similar_translations = vector_db_service.search_similar_translations(source_text, k=3)
        
        if use_terminology and terminology_service:
            terminology_dict = terminology_service.get_relevant_terms(source_text, source_lang)
        
        # 对每个目标语言进行翻译
        for target_lang in target_langs:
            translation_result = self._translate_single_with_metrics(
                source_text=source_text,
                source_lang=source_lang,
                target_lang=target_lang,
                similar_translations=similar_translations.get(target_lang, []),
                terminology=terminology_dict,
                model=current_model
            )
            
            results['translations'][target_lang] = {
                'text': translation_result['text'],
                'used_terminology': terminology_dict,
                'similar_references': similar_translations.get(target_lang, []),
                'performance_metrics': translation_result['metrics']
            }
        
        return results
    
    def _translate_single(self, source_text: str, source_lang: str, target_lang: str,
                         similar_translations: List[Dict], terminology: Dict,
                         model: str) -> str:
        """翻译到单个目标语言"""
        
        # 构建翻译提示
        prompt = self._build_translation_prompt(
            source_text=source_text,
            source_lang=source_lang,
            target_lang=target_lang,
            similar_translations=similar_translations,
            terminology=terminology
        )
        
        try:
            response = self.client.chat(
                model=model,
                messages=[
                    {
                        'role': 'system',
                        'content': 'You are a professional translator with expertise in multiple languages. Translate accurately while preserving the original meaning, tone, and style.'
                    },
                    {
                        'role': 'user',
                        'content': prompt
                    }
                ]
            )
            
            translation = response['message']['content'].strip()
            
            # 清理翻译结果（去除可能的额外标记）
            translation = self._clean_translation(translation)
            
            return translation
            
        except Exception as e:
            print(f"Translation error with model {model}: {e}")
            return f"Translation failed: {str(e)}"
    
    def _build_translation_prompt(self, source_text: str, source_lang: str, 
                                 target_lang: str, similar_translations: List[Dict],
                                 terminology: Dict) -> str:
        """构建翻译提示"""
        
        lang_names = {
            'zh-cn': 'Simplified Chinese (Mainland China Modern Chinese)',
            'zh-tw': 'Traditional Chinese (Hong Kong, Macau, Taiwan Modern Chinese)',
            'zh-classical-cn': 'Classical Chinese (Simplified Characters)',
            'zh-classical-tw': 'Classical Chinese (Traditional Characters)',
            'en': 'English',
            'ja': 'Japanese',
            'ko': 'Korean',
            'es': 'Spanish',
            'fr': 'French',
            'de': 'German',
            'ru': 'Russian',
            'ar': 'Arabic',
            'pt': 'Portuguese'
        }
        
        # 构建更详细的翻译提示
        source_lang_desc = lang_names.get(source_lang, source_lang)
        target_lang_desc = lang_names.get(target_lang, target_lang)
        
        prompt = f"Translate the following text from {source_lang_desc} to {target_lang_desc}:\n\n"
        
        # 为中文变体添加特殊说明
        if target_lang == 'zh-cn':
            prompt += "Note: Please translate to Simplified Chinese used in Mainland China (中国大陆地区现代文简体) using modern simplified characters and contemporary expressions. Preserve all paragraphs and formatting from the original text.\n\n"
        elif target_lang == 'zh-tw':
            prompt += "Note: Please translate to Traditional Chinese used in Hong Kong, Macau, and Taiwan (中文港澳台地区现代文繁体) using traditional characters and expressions commonly used in these regions. Preserve all paragraphs and formatting from the original text.\n\n"
        elif target_lang == 'zh-classical-cn':
            prompt += "Note: Please translate to Classical Chinese using simplified characters (中文文言文简体) with classical literary style, ancient grammar patterns, but using simplified character forms. Preserve all paragraphs and formatting from the original text.\n\n"
        elif target_lang == 'zh-classical-tw':
            prompt += "Note: Please translate to Classical Chinese using traditional characters (中文文言文繁体) with classical literary style, ancient grammar patterns, and traditional character forms. Preserve all paragraphs and formatting from the original text.\n\n"
        
        prompt += f"Source text:\n{source_text}\n\n"
        
        # 添加相似翻译参考
        if similar_translations:
            prompt += "Reference translations for similar texts:\n"
            for ref in similar_translations[:3]:
                prompt += f"- Original: {ref['source'][:100]}...\n"
                prompt += f"  Translation: {ref['translation'][:100]}...\n"
            prompt += "\n"
        
        # 添加术语表
        if terminology:
            prompt += "Terminology to use:\n"
            for term, translations in terminology.items():
                if target_lang in translations:
                    prompt += f"- {term} → {translations[target_lang]}\n"
            prompt += "\n"
        
        prompt += "Please provide only the complete translation without any explanations or additional text. Ensure the entire source text is translated and preserve all paragraphs and line breaks."
        
        return prompt
    
    def _clean_translation(self, translation: str) -> str:
        """清理翻译结果"""
        # 移除思考过程标签
        if "<think>" in translation and "</think>" in translation:
            # 移除整个思考过程
            start = translation.find("<think>")
            end = translation.find("</think>") + 8
            translation = translation[:start] + translation[end:]
        
        # 移除可能的引号
        if translation.startswith('"') and translation.endswith('"'):
            translation = translation[1:-1]
        if translation.startswith("'") and translation.endswith("'"):
            translation = translation[1:-1]
        
        # 移除可能的"Translation:"前缀
        prefixes = [
            'Translation:', 'Translated:', '翻译:', '译文:', 'Output:', 'Result:',
            'Here is the translation:', 'The translation is:', '翻译结果:',
            'Improved translation:', 'Final translation:', '改进翻译:', '最终翻译:'
        ]
        for prefix in prefixes:
            if translation.startswith(prefix):
                translation = translation[len(prefix):].strip()
        
        # 移除多余的换行符和空白
        translation = translation.strip()
        
        # 改进的多行处理逻辑：保留完整的翻译内容，只移除明显的非翻译内容
        lines = translation.split('\n')
        if len(lines) > 1:
            # 移除明显的注释行和空行，但保留翻译内容
            cleaned_lines = []
            translation_started = False
            
            for line in lines:
                line = line.strip()
                
                # 跳过空行
                if not line:
                    if translation_started and cleaned_lines:
                        # 如果翻译已经开始且有内容，保留空行以保持格式
                        cleaned_lines.append('')
                    continue
                
                # 跳过明显的注释或元信息
                if (line.startswith('#') or 
                    line.startswith('//') or 
                    line.startswith('Note:') or
                    line.startswith('注:') or
                    line.startswith('备注:') or
                    line.lower().startswith('explanation:') or
                    line.lower().startswith('analysis:') or
                    line.lower().startswith('here is') or
                    line.lower().startswith('the translation') or
                    line.lower().startswith('翻译结果')):
                    continue
                
                # 跳过重复的前缀行
                is_prefix_line = False
                for prefix in prefixes:
                    if line.startswith(prefix):
                        is_prefix_line = True
                        break
                
                if is_prefix_line:
                    continue
                
                # 跳过过短的说明性行（可能是标题或说明）
                if len(line) < 5 and any(word in line.lower() for word in ['翻译', 'translation', '结果', 'result']):
                    continue
                
                # 这是有效的翻译内容
                translation_started = True
                cleaned_lines.append(line)
            
            # 如果清理后有内容，使用清理后的结果
            if cleaned_lines:
                translation = '\n'.join(cleaned_lines).strip()
        
        return translation.strip()
    
    def translate_streaming(self, source_text: str, source_lang: str, target_langs: List[str], 
                           use_vector_db: bool = True, use_terminology: bool = True,
                           vector_db_service=None, terminology_service=None,
                           model: str = None):
        """执行流式翻译，返回生成器"""
        
        # 使用指定的模型或默认模型
        current_model = model if model else self.default_model
        
        # 如果source_lang是auto，则自动检测
        if source_lang == 'auto':
            source_lang = self.detect_language(source_text)
        
        # 获取相似翻译和术语
        similar_translations = {}
        terminology_dict = {}
        
        if use_vector_db and vector_db_service:
            similar_translations = vector_db_service.search_similar_translations(source_text, k=3)
        
        if use_terminology and terminology_service:
            terminology_dict = terminology_service.get_relevant_terms(source_text, source_lang)
        
        # 对每个目标语言进行流式翻译
        for target_lang in target_langs:
            yield from self._translate_single_streaming(
                source_text=source_text,
                source_lang=source_lang,
                target_lang=target_lang,
                similar_translations=similar_translations.get(target_lang, []),
                terminology=terminology_dict,
                model=current_model
            )
    
    def _translate_single_streaming(self, source_text: str, source_lang: str, target_lang: str,
                                   similar_translations: List[Dict], terminology: Dict,
                                   model: str):
        """流式翻译到单个目标语言"""
        
        # 构建翻译提示
        prompt = self._build_translation_prompt(
            source_text=source_text,
            source_lang=source_lang,
            target_lang=target_lang,
            similar_translations=similar_translations,
            terminology=terminology
        )
        
        try:
            import time
            
            # 开始翻译这个语言
            start_time = time.time()
            yield {
                'type': 'start',
                'target_lang': target_lang,
                'model_used': model,
                'start_time': start_time
            }
            
            # 使用流式API
            stream = self.client.chat(
                model=model,
                messages=[
                    {
                        'role': 'system',
                        'content': 'You are a professional translator with expertise in multiple languages. Translate accurately while preserving the original meaning, tone, and style.'
                    },
                    {
                        'role': 'user',
                        'content': prompt
                    }
                ],
                stream=True
            )
            
            full_response = ""
            token_count = 0
            last_time = start_time
            
            for chunk in stream:
                if 'message' in chunk and 'content' in chunk['message']:
                    content = chunk['message']['content']
                    full_response += content
                    
                    # 估算token数量（简单按空格和字符数估算）
                    token_count += len(content.split()) + len(content) // 4
                    
                    current_time = time.time()
                    elapsed_time = current_time - start_time
                    
                    # 计算当前速度
                    tokens_per_second = token_count / elapsed_time if elapsed_time > 0 else 0
                    
                    # 发送增量内容
                    yield {
                        'type': 'content',
                        'target_lang': target_lang,
                        'content': content,
                        'full_content': full_response,
                        'token_count': token_count,
                        'elapsed_time': elapsed_time,
                        'tokens_per_second': round(tokens_per_second, 1)
                    }
                    
                    last_time = current_time
            
            # 清理最终结果
            cleaned_translation = self._clean_translation(full_response)
            end_time = time.time()
            total_time = end_time - start_time
            final_tokens_per_second = token_count / total_time if total_time > 0 else 0
            
            # 翻译完成
            yield {
                'type': 'complete',
                'target_lang': target_lang,
                'final_content': cleaned_translation,
                'raw_content': full_response,
                'total_tokens': token_count,
                'total_time': round(total_time, 2),
                'tokens_per_second': round(final_tokens_per_second, 1)
            }
            
        except Exception as e:
            print(f"Streaming translation error with model {model}: {e}")
            yield {
                'type': 'error',
                'target_lang': target_lang,
                'error': str(e)
            }
    
    def reflect_translation(self, source_text: str, translation: str, 
                           source_lang: str, target_lang: str, model: str = None) -> Dict[str, Any]:
        """对翻译进行反思，提出改进建议"""
        import time
        
        current_model = model if model else self.default_model
        start_time = time.time()
        
        # 构建反思提示
        prompt = self._build_reflection_prompt(
            source_text=source_text,
            translation=translation,
            source_lang=source_lang,
            target_lang=target_lang
        )
        
        try:
            response = self.client.chat(
                model=current_model,
                messages=[
                    {
                        'role': 'system',
                        'content': 'You are an expert translation critic and reviewer. Your task is to carefully analyze translations and provide constructive feedback for improvement. Focus on accuracy, fluency, cultural appropriateness, and style.'
                    },
                    {
                        'role': 'user',
                        'content': prompt
                    }
                ]
            )
            
            reflection = response['message']['content'].strip()
            cleaned_reflection = self._clean_reflection(reflection)
            
            end_time = time.time()
            total_time = end_time - start_time
            
            # 计算反思的性能指标
            word_count = len(cleaned_reflection.split())
            char_count = len(cleaned_reflection)
            estimated_tokens = word_count + char_count // 4
            tokens_per_second = estimated_tokens / total_time if total_time > 0 else 0
            
            return {
                'reflection': cleaned_reflection,
                'metrics': {
                    'tokens_per_second': round(tokens_per_second, 1),
                    'total_time': round(total_time, 2),
                    'total_tokens': estimated_tokens
                }
            }
            
        except Exception as e:
            print(f"Reflection error with model {current_model}: {e}")
            return {
                'reflection': f"反思失败: {str(e)}",
                'metrics': {
                    'tokens_per_second': 0,
                    'total_time': 0,
                    'total_tokens': 0
                }
            }
    
    def improve_translation(self, source_text: str, current_translation: str, 
                           reflection: str, source_lang: str, target_lang: str, 
                           model: str = None) -> Dict[str, Any]:
        """根据反思意见改进翻译"""
        import time
        
        current_model = model if model else self.default_model
        start_time = time.time()
        
        # 构建改进提示
        prompt = self._build_improvement_prompt(
            source_text=source_text,
            current_translation=current_translation,
            reflection=reflection,
            source_lang=source_lang,
            target_lang=target_lang
        )
        
        try:
            response = self.client.chat(
                model=current_model,
                messages=[
                    {
                        'role': 'system',
                        'content': 'You are a professional translator tasked with improving translations based on expert feedback. Create improved translations that address the specific issues mentioned in the feedback while maintaining accuracy and natural flow.'
                    },
                    {
                        'role': 'user',
                        'content': prompt
                    }
                ]
            )
            
            improved_translation = response['message']['content'].strip()
            cleaned_translation = self._clean_improved_translation(improved_translation)
            
            end_time = time.time()
            total_time = end_time - start_time
            
            # 计算改进的性能指标
            word_count = len(cleaned_translation.split())
            char_count = len(cleaned_translation)
            estimated_tokens = word_count + char_count // 4
            tokens_per_second = estimated_tokens / total_time if total_time > 0 else 0
            
            return {
                'improved_translation': cleaned_translation,
                'metrics': {
                    'tokens_per_second': round(tokens_per_second, 1),
                    'total_time': round(total_time, 2),
                    'total_tokens': estimated_tokens
                }
            }
            
        except Exception as e:
            print(f"Improvement error with model {current_model}: {e}")
            return {
                'improved_translation': f"改进失败: {str(e)}",
                'metrics': {
                    'tokens_per_second': 0,
                    'total_time': 0,
                    'total_tokens': 0
                }
            }
    
    def _build_reflection_prompt(self, source_text: str, translation: str, 
                                source_lang: str, target_lang: str) -> str:
        """构建反思提示"""
        
        lang_names = {
            'zh-cn': 'Simplified Chinese (Mainland China Modern Chinese)',
            'zh-tw': 'Traditional Chinese (Hong Kong, Macau, Taiwan Modern Chinese)',
            'zh-classical-cn': 'Classical Chinese (Simplified Characters)',
            'zh-classical-tw': 'Classical Chinese (Traditional Characters)',
            'en': 'English',
            'ja': 'Japanese',
            'ko': 'Korean',
            'es': 'Spanish',
            'fr': 'French',
            'de': 'German',
            'ru': 'Russian',
            'ar': 'Arabic',
            'pt': 'Portuguese'
        }
        
        source_lang_desc = lang_names.get(source_lang, source_lang)
        target_lang_desc = lang_names.get(target_lang, target_lang)
        
        prompt = f"""Please carefully review this translation and provide constructive feedback for improvement.

Source Language: {source_lang_desc}
Target Language: {target_lang_desc}

Source Text:
{source_text}

Current Translation:
{translation}

Please analyze the translation and provide specific feedback on:
1. Accuracy: Are there any mistranslations or omissions?
2. Fluency: Does the translation read naturally in the target language?
3. Style: Is the tone and register appropriate?
4. Cultural appropriateness: Are there any cultural nuances that could be better handled?
5. Terminology: Are technical terms or specific expressions properly translated?

Provide your feedback in a clear, constructive manner. Focus on specific issues and suggest improvements where needed. If the translation is already good, acknowledge its strengths while noting any minor areas for enhancement.

Please respond in Chinese (简体中文) for easier understanding."""
        
        return prompt
    
    def _build_improvement_prompt(self, source_text: str, current_translation: str, 
                                 reflection: str, source_lang: str, target_lang: str) -> str:
        """构建改进提示"""
        
        lang_names = {
            'zh-cn': 'Simplified Chinese (Mainland China Modern Chinese)',
            'zh-tw': 'Traditional Chinese (Hong Kong, Macau, Taiwan Modern Chinese)',
            'zh-classical-cn': 'Classical Chinese (Simplified Characters)',
            'zh-classical-tw': 'Classical Chinese (Traditional Characters)',
            'en': 'English',
            'ja': 'Japanese',
            'ko': 'Korean',
            'es': 'Spanish',
            'fr': 'French',
            'de': 'German',
            'ru': 'Russian',
            'ar': 'Arabic',
            'pt': 'Portuguese'
        }
        
        source_lang_desc = lang_names.get(source_lang, source_lang)
        target_lang_desc = lang_names.get(target_lang, target_lang)
        
        prompt = f"""Based on the expert feedback provided, please create an improved version of the translation.

Source Language: {source_lang_desc}
Target Language: {target_lang_desc}

Source Text:
{source_text}

Current Translation:
{current_translation}

Expert Feedback:
{reflection}

IMPORTANT INSTRUCTIONS:
1. Provide ONLY the improved translation text
2. Do NOT include any explanations, descriptions, or meta-text
3. Do NOT use phrases like "Here is the improved translation:", "Improved version:", etc.
4. Do NOT add any prefixes, suffixes, or commentary
5. Ensure the entire source text is translated and preserve all paragraphs and line breaks
6. Output ONLY the pure translation content

The improved translation should address the specific issues mentioned in the feedback while maintaining accuracy and natural flow."""
        
        return prompt
    
    def _clean_reflection(self, reflection: str) -> str:
        """清理反思结果"""
        # 移除可能的前缀
        prefixes = ['Feedback:', 'Review:', 'Analysis:', 'Reflection:', '反馈:', '评价:', '分析:', '反思:', 'Response:', '回应:']
        for prefix in prefixes:
            if reflection.startswith(prefix):
                reflection = reflection[len(prefix):].strip()
        
        # 移除思考过程标签
        if "<think>" in reflection and "</think>" in reflection:
            start = reflection.find("<think>")
            end = reflection.find("</think>") + 8
            reflection = reflection[:start] + reflection[end:]
        
        # 移除引号包围
        if reflection.startswith('"') and reflection.endswith('"'):
            reflection = reflection[1:-1]
        if reflection.startswith("'") and reflection.endswith("'"):
            reflection = reflection[1:-1]
        
        return reflection.strip()
    
    def _clean_improved_translation(self, translation: str) -> str:
        """清理改进的翻译结果，确保只保留纯净的翻译文本"""
        # 首先使用基础清理逻辑
        translation = self._clean_translation(translation)
        
        # 额外的改进翻译清理步骤
        lines = translation.split('\n')
        cleaned_lines = []
        
        for line in lines:
            line = line.strip()
            
            # 跳过空行
            if not line:
                continue
            
            # 跳过明显的说明性文本
            skip_patterns = [
                '改进后的翻译',
                '优化后的翻译', 
                '改进版本',
                '最终翻译',
                'improved translation',
                'optimized translation',
                'final translation',
                'revised translation',
                '修订后的翻译',
                '以下是',
                'here is',
                'the improved',
                'the optimized',
                'the final',
                'the revised'
            ]
            
            line_lower = line.lower()
            should_skip = False
            for pattern in skip_patterns:
                if pattern in line_lower:
                    should_skip = True
                    break
            
            if should_skip:
                continue
            
            # 跳过包含冒号的说明行（但保留正常的翻译内容）
            if ':' in line and len(line) < 50:
                # 检查是否是说明性文本
                explanation_indicators = ['翻译', 'translation', '版本', 'version', '改进', 'improved', '优化', 'optimized']
                if any(indicator in line_lower for indicator in explanation_indicators):
                    continue
            
            # 保留这一行
            cleaned_lines.append(line)
        
        # 如果清理后没有内容，返回原始文本的第一个非空行
        if not cleaned_lines:
            for line in translation.split('\n'):
                line = line.strip()
                if line and not any(pattern in line.lower() for pattern in ['翻译', 'translation']):
                    return line
            return translation.strip()
        
        # 返回清理后的内容，用换行符连接
        result = '\n'.join(cleaned_lines)
        
        # 最终检查：如果结果看起来仍然包含说明性文本，提取核心内容
        if len(result.split('\n')) > 3:  # 如果有太多行，可能包含说明
            # 找到最长的非说明性行作为主要翻译内容
            main_lines = []
            for line in cleaned_lines:
                if len(line) > 20 and not any(indicator in line.lower() for indicator in ['翻译', 'translation', '改进', 'improved']):
                    main_lines.append(line)
            
            if main_lines:
                result = '\n'.join(main_lines)
        
        return result.strip()
    
    def _translate_single_with_metrics(self, source_text: str, source_lang: str, target_lang: str,
                                     similar_translations: List[Dict], terminology: Dict,
                                     model: str) -> Dict[str, Any]:
        """翻译到单个目标语言，并返回性能指标"""
        import time
        
        start_time = time.time()
        
        # 翻译
        translation = self._translate_single(
            source_text=source_text,
            source_lang=source_lang,
            target_lang=target_lang,
            similar_translations=similar_translations,
            terminology=terminology,
            model=model
        )
        
        end_time = time.time()
        total_time = end_time - start_time
        
        # 计算token数量（简单估算：按空格分割的词数 + 字符数/4）
        word_count = len(translation.split())
        char_count = len(translation)
        estimated_tokens = word_count + char_count // 4
        
        # 计算tokens/s
        tokens_per_second = estimated_tokens / total_time if total_time > 0 else 0
        
        return {
            'text': translation,
            'metrics': {
                'tokens_per_second': round(tokens_per_second, 1),
                'total_time': round(total_time, 2),
                'total_tokens': estimated_tokens,
                'word_count': word_count
            }
        } 