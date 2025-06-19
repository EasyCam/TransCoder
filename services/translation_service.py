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
        """检测文本语言"""
        try:
            lang = detect(text)
            return lang
        except:
            return 'unknown'
    
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
            translation = self._translate_single(
                source_text=source_text,
                source_lang=source_lang,
                target_lang=target_lang,
                similar_translations=similar_translations.get(target_lang, []),
                terminology=terminology_dict,
                model=current_model
            )
            
            results['translations'][target_lang] = {
                'text': translation,
                'used_terminology': terminology_dict,
                'similar_references': similar_translations.get(target_lang, [])
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
            'zh': 'Chinese',
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
        
        prompt = f"Translate the following text from {lang_names.get(source_lang, source_lang)} to {lang_names.get(target_lang, target_lang)}:\n\n"
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
        
        prompt += "Please provide only the translation without any explanations or additional text."
        
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
        prefixes = ['Translation:', 'Translated:', '翻译:', '译文:', 'Output:', 'Result:']
        for prefix in prefixes:
            if translation.startswith(prefix):
                translation = translation[len(prefix):].strip()
        
        # 移除多余的换行符和空白
        translation = translation.strip()
        
        # 如果包含换行符，只取第一行（通常是实际翻译）
        lines = translation.split('\n')
        if len(lines) > 1:
            # 找到第一个非空行作为翻译结果
            for line in lines:
                line = line.strip()
                if line and not line.startswith('#') and not line.startswith('//'):
                    translation = line
                    break
        
        return translation.strip() 