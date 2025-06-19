import os
import json
import pandas as pd
import xml.etree.ElementTree as ET
from typing import Dict, List, Any
import config

class TerminologyService:
    def __init__(self):
        self.terminology_file = os.path.join(config.TERMINOLOGY_DB_PATH, 'terminology.json')
        self.terminology = self._load_terminology()
    
    def _load_terminology(self) -> Dict[str, Dict[str, str]]:
        """加载术语库"""
        if os.path.exists(self.terminology_file):
            with open(self.terminology_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}
    
    def _save_terminology(self):
        """保存术语库"""
        os.makedirs(config.TERMINOLOGY_DB_PATH, exist_ok=True)
        with open(self.terminology_file, 'w', encoding='utf-8') as f:
            json.dump(self.terminology, f, ensure_ascii=False, indent=2)
    
    def add_term(self, term: str, translations: Dict[str, str]) -> Dict[str, Any]:
        """添加术语"""
        try:
            self.terminology[term.lower()] = translations
            self._save_terminology()
            
            return {
                'success': True,
                'message': f'Term "{term}" added successfully',
                'total_terms': len(self.terminology)
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_relevant_terms(self, text: str, source_lang: str) -> Dict[str, Dict[str, str]]:
        """获取文本中的相关术语"""
        relevant_terms = {}
        text_lower = text.lower()
        
        for term, translations in self.terminology.items():
            if term in text_lower:
                relevant_terms[term] = translations
        
        return relevant_terms
    
    def import_terminology(self, file_path: str) -> Dict[str, Any]:
        """导入术语库"""
        try:
            file_ext = os.path.splitext(file_path)[1].lower()
            
            if file_ext == '.csv':
                return self._import_csv(file_path)
            elif file_ext == '.xlsx':
                return self._import_excel(file_path)
            elif file_ext == '.tbx':
                return self._import_tbx(file_path)
            elif file_ext == '.json':
                return self._import_json(file_path)
            else:
                return {
                    'success': False,
                    'error': f'Unsupported file format: {file_ext}'
                }
                
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def _import_csv(self, file_path: str) -> Dict[str, Any]:
        """导入CSV格式术语库"""
        try:
            df = pd.read_csv(file_path, encoding='utf-8')
            count = 0
            
            # 假设第一列是术语，其他列是各语言翻译
            for _, row in df.iterrows():
                term = str(row.iloc[0]).lower()
                translations = {}
                
                # 获取列名作为语言代码
                for col_idx, col_name in enumerate(df.columns[1:], 1):
                    if pd.notna(row.iloc[col_idx]):
                        lang_code = self._normalize_lang_code(col_name)
                        translations[lang_code] = str(row.iloc[col_idx])
                
                if term and translations:
                    self.terminology[term] = translations
                    count += 1
            
            self._save_terminology()
            
            return {
                'success': True,
                'imported': count,
                'message': f'Successfully imported {count} terms'
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f'CSV import failed: {str(e)}'
            }
    
    def _import_excel(self, file_path: str) -> Dict[str, Any]:
        """导入Excel格式术语库"""
        try:
            df = pd.read_excel(file_path)
            # 使用与CSV相同的逻辑
            return self._import_csv(file_path)
        except Exception as e:
            return {
                'success': False,
                'error': f'Excel import failed: {str(e)}'
            }
    
    def _import_tbx(self, file_path: str) -> Dict[str, Any]:
        """导入TBX格式术语库"""
        try:
            tree = ET.parse(file_path)
            root = tree.getroot()
            count = 0
            
            # TBX命名空间
            ns = {'tbx': 'urn:iso:std:iso:30042:ed-2'}
            
            for term_entry in root.findall('.//termEntry', ns):
                term_dict = {}
                
                for lang_set in term_entry.findall('.//langSet', ns):
                    lang = lang_set.get('lang') or lang_set.get('xml:lang')
                    
                    for tig in lang_set.findall('.//tig', ns):
                        term_elem = tig.find('.//term', ns)
                        if term_elem is not None and term_elem.text:
                            if not term_dict:
                                # 第一个术语作为主键
                                main_term = term_elem.text.lower()
                                term_dict['_main'] = main_term
                            else:
                                lang_code = self._normalize_lang_code(lang)
                                term_dict[lang_code] = term_elem.text
                
                if '_main' in term_dict:
                    main_term = term_dict.pop('_main')
                    self.terminology[main_term] = term_dict
                    count += 1
            
            self._save_terminology()
            
            return {
                'success': True,
                'imported': count,
                'message': f'Successfully imported {count} terms from TBX'
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f'TBX import failed: {str(e)}'
            }
    
    def _import_json(self, file_path: str) -> Dict[str, Any]:
        """导入JSON格式术语库"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            count = 0
            for term, translations in data.items():
                self.terminology[term.lower()] = translations
                count += 1
            
            self._save_terminology()
            
            return {
                'success': True,
                'imported': count,
                'message': f'Successfully imported {count} terms'
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f'JSON import failed: {str(e)}'
            }
    
    def export_terminology(self, format_type: str = 'csv') -> str:
        """导出术语库"""
        try:
            timestamp = pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')
            
            if format_type == 'csv':
                return self._export_csv(timestamp)
            elif format_type == 'xlsx':
                return self._export_excel(timestamp)
            elif format_type == 'tbx':
                return self._export_tbx(timestamp)
            elif format_type == 'json':
                return self._export_json(timestamp)
            else:
                raise ValueError(f'Unsupported export format: {format_type}')
                
        except Exception as e:
            raise Exception(f'Export failed: {str(e)}')
    
    def _export_csv(self, timestamp: str) -> str:
        """导出为CSV格式"""
        # 准备数据
        data = []
        all_langs = set()
        
        # 收集所有语言
        for translations in self.terminology.values():
            all_langs.update(translations.keys())
        
        all_langs = sorted(list(all_langs))
        
        # 构建数据行
        for term, translations in self.terminology.items():
            row = {'term': term}
            for lang in all_langs:
                row[lang] = translations.get(lang, '')
            data.append(row)
        
        # 创建DataFrame并导出
        df = pd.DataFrame(data)
        output_path = os.path.join(config.TERMINOLOGY_DB_PATH, f'terminology_{timestamp}.csv')
        df.to_csv(output_path, index=False, encoding='utf-8')
        
        return output_path
    
    def _export_excel(self, timestamp: str) -> str:
        """导出为Excel格式"""
        # 使用相同的数据准备逻辑
        output_path = os.path.join(config.TERMINOLOGY_DB_PATH, f'terminology_{timestamp}.xlsx')
        
        # 重用CSV导出的数据准备
        csv_path = self._export_csv(timestamp)
        df = pd.read_csv(csv_path)
        df.to_excel(output_path, index=False)
        
        # 删除临时CSV文件
        os.remove(csv_path)
        
        return output_path
    
    def _export_json(self, timestamp: str) -> str:
        """导出为JSON格式"""
        output_path = os.path.join(config.TERMINOLOGY_DB_PATH, f'terminology_{timestamp}.json')
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(self.terminology, f, ensure_ascii=False, indent=2)
        
        return output_path
    
    def _export_tbx(self, timestamp: str) -> str:
        """导出为TBX格式"""
        # 创建TBX根元素
        tbx = ET.Element('tbx', {
            'type': 'TBX-Basic',
            'style': 'dca',
            'xmlns': 'urn:iso:std:iso:30042:ed-2'
        })
        
        # 添加头部
        tbx_header = ET.SubElement(tbx, 'tbxHeader')
        file_desc = ET.SubElement(tbx_header, 'fileDesc')
        title_stmt = ET.SubElement(file_desc, 'titleStmt')
        title = ET.SubElement(title_stmt, 'title')
        title.text = 'TransCoder Terminology Database'
        
        # 添加正文
        text = ET.SubElement(tbx, 'text')
        body = ET.SubElement(text, 'body')
        
        # 添加术语条目
        for term, translations in self.terminology.items():
            term_entry = ET.SubElement(body, 'termEntry')
            
            # 添加源语言术语
            lang_set = ET.SubElement(term_entry, 'langSet', {'xml:lang': 'en'})
            tig = ET.SubElement(lang_set, 'tig')
            term_elem = ET.SubElement(tig, 'term')
            term_elem.text = term
            
            # 添加翻译
            for lang, translation in translations.items():
                lang_set = ET.SubElement(term_entry, 'langSet', {'xml:lang': lang})
                tig = ET.SubElement(lang_set, 'tig')
                term_elem = ET.SubElement(tig, 'term')
                term_elem.text = translation
        
        # 保存文件
        output_path = os.path.join(config.TERMINOLOGY_DB_PATH, f'terminology_{timestamp}.tbx')
        tree = ET.ElementTree(tbx)
        tree.write(output_path, encoding='utf-8', xml_declaration=True)
        
        return output_path
    
    def _normalize_lang_code(self, lang: str) -> str:
        """标准化语言代码"""
        lang_map = {
            'chinese': 'zh-cn',
            'simplified chinese': 'zh-cn',
            'traditional chinese': 'zh-tw',
            'classical chinese': 'zh-classical-cn',
            'classical chinese simplified': 'zh-classical-cn',
            'classical chinese traditional': 'zh-classical-tw',
            'mainland chinese': 'zh-cn',
            'hong kong chinese': 'zh-tw',
            'taiwan chinese': 'zh-tw',
            'macao chinese': 'zh-tw',
            'english': 'en',
            'japanese': 'ja',
            'korean': 'ko',
            'spanish': 'es',
            'french': 'fr',
            'german': 'de',
            'russian': 'ru',
            'arabic': 'ar',
            'portuguese': 'pt'
        }
        
        lang_lower = lang.lower()
        # 优先匹配完整映射
        if lang_lower in lang_map:
            return lang_map[lang_lower]
        
        # 如果是中文相关的简单代码，默认为大陆地区简体中文
        if lang_lower in ['zh', 'cn']:
            return 'zh-cn'
        elif lang_lower in ['tw', 'hk', 'mo']:
            return 'zh-tw'
        
        # 其他情况返回前两个字符
        return lang_lower[:2] if len(lang_lower) >= 2 else lang_lower
    
    def list_terms(self, page: int = 1, per_page: int = 50, search: str = '') -> Dict[str, Any]:
        """分页列出术语"""
        try:
            # 过滤术语
            filtered_terms = {}
            search_lower = search.lower()
            
            for term, translations in self.terminology.items():
                if not search or search_lower in term or any(search_lower in t.lower() for t in translations.values()):
                    filtered_terms[term] = translations
            
            # 分页
            total = len(filtered_terms)
            start = (page - 1) * per_page
            end = start + per_page
            
            terms_list = list(filtered_terms.items())[start:end]
            
            return {
                'success': True,
                'terms': [{'term': term, 'translations': translations} for term, translations in terms_list],
                'pagination': {
                    'page': page,
                    'per_page': per_page,
                    'total': total,
                    'pages': (total + per_page - 1) // per_page
                }
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def delete_term(self, term: str) -> Dict[str, Any]:
        """删除术语"""
        try:
            term_lower = term.lower()
            if term_lower in self.terminology:
                del self.terminology[term_lower]
                self._save_terminology()
                return {
                    'success': True,
                    'message': f'术语 "{term}" 已删除',
                    'total_terms': len(self.terminology)
                }
            else:
                return {
                    'success': False,
                    'error': f'术语 "{term}" 不存在'
                }
                
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def update_term(self, term: str, translations: Dict[str, str]) -> Dict[str, Any]:
        """更新术语"""
        try:
            term_lower = term.lower()
            if term_lower in self.terminology:
                self.terminology[term_lower] = translations
                self._save_terminology()
                return {
                    'success': True,
                    'message': f'术语 "{term}" 已更新'
                }
            else:
                return {
                    'success': False,
                    'error': f'术语 "{term}" 不存在'
                }
                
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取术语库统计信息"""
        try:
            total_terms = len(self.terminology)
            language_counts = {}
            
            for translations in self.terminology.values():
                for lang in translations.keys():
                    language_counts[lang] = language_counts.get(lang, 0) + 1
            
            return {
                'total_terms': total_terms,
                'language_counts': language_counts,
                'most_common_languages': sorted(language_counts.items(), key=lambda x: x[1], reverse=True)[:5]
            }
            
        except Exception as e:
            return {
                'error': str(e)
            } 