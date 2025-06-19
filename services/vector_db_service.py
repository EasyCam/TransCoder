import os
import numpy as np
import faiss
import pickle
from sentence_transformers import SentenceTransformer
from typing import List, Dict, Any
import config

class VectorDBService:
    def __init__(self):
        self.model = SentenceTransformer(config.EMBEDDING_MODEL)
        self.index_path = os.path.join(config.VECTOR_DB_PATH, 'faiss_index.bin')
        self.metadata_path = os.path.join(config.VECTOR_DB_PATH, 'metadata.pkl')
        self.dimension = 384  # 多语言模型的维度
        
        # 加载或创建索引
        self._load_or_create_index()
    
    def _load_or_create_index(self):
        """加载或创建FAISS索引"""
        if os.path.exists(self.index_path) and os.path.exists(self.metadata_path):
            # 加载现有索引
            self.index = faiss.read_index(self.index_path)
            with open(self.metadata_path, 'rb') as f:
                self.metadata = pickle.load(f)
        else:
            # 创建新索引
            self.index = faiss.IndexFlatL2(self.dimension)
            self.metadata = []
    
    def add_translation_pair(self, source_text: str, translations: Dict[str, str]) -> Dict[str, Any]:
        """添加翻译对到向量数据库"""
        try:
            # 生成源文本的向量
            embedding = self.model.encode(source_text)
            
            # 添加到索引
            self.index.add(np.array([embedding]))
            
            # 保存元数据
            self.metadata.append({
                'source': source_text,
                'translations': translations,
                'embedding': embedding.tolist()
            })
            
            # 保存索引和元数据
            self._save_index()
            
            return {
                'success': True,
                'message': 'Translation pair added successfully',
                'total_pairs': len(self.metadata)
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def search_similar_translations(self, query_text: str, k: int = 5) -> Dict[str, List[Dict]]:
        """搜索相似的翻译"""
        if self.index.ntotal == 0:
            return {}
        
        try:
            # 生成查询向量
            query_embedding = self.model.encode(query_text)
            
            # 搜索最相似的k个结果
            k = min(k, self.index.ntotal)
            distances, indices = self.index.search(np.array([query_embedding]), k)
            
            # 组织结果
            results = {}
            for idx, distance in zip(indices[0], distances[0]):
                if idx < len(self.metadata):
                    item = self.metadata[idx]
                    similarity_score = 1 / (1 + distance)  # 转换距离为相似度分数
                    
                    for lang, translation in item['translations'].items():
                        if lang not in results:
                            results[lang] = []
                        
                        results[lang].append({
                            'source': item['source'],
                            'translation': translation,
                            'similarity': float(similarity_score)
                        })
            
            # 按相似度排序
            for lang in results:
                results[lang].sort(key=lambda x: x['similarity'], reverse=True)
            
            return results
            
        except Exception as e:
            print(f"Search error: {e}")
            return {}
    
    def _save_index(self):
        """保存索引和元数据"""
        os.makedirs(config.VECTOR_DB_PATH, exist_ok=True)
        faiss.write_index(self.index, self.index_path)
        with open(self.metadata_path, 'wb') as f:
            pickle.dump(self.metadata, f)
    
    def import_translation_memory(self, file_path: str, format_type: str = 'tmx') -> Dict[str, Any]:
        """导入翻译记忆库（TMX格式）"""
        try:
            if format_type == 'tmx':
                # 这里简化处理，实际应该使用专门的TMX解析库
                # 可以使用translate-toolkit或其他TMX处理库
                import xml.etree.ElementTree as ET
                
                tree = ET.parse(file_path)
                root = tree.getroot()
                
                count = 0
                for tu in root.findall('.//tu'):
                    source_text = None
                    translations = {}
                    
                    for tuv in tu.findall('tuv'):
                        lang = tuv.get('lang') or tuv.get('xml:lang')
                        seg = tuv.find('seg')
                        if seg is not None and seg.text:
                            if source_text is None:
                                source_text = seg.text
                            else:
                                translations[lang] = seg.text
                    
                    if source_text and translations:
                        self.add_translation_pair(source_text, translations)
                        count += 1
                
                return {
                    'success': True,
                    'imported': count,
                    'message': f'Successfully imported {count} translation pairs'
                }
            
            return {
                'success': False,
                'error': f'Unsupported format: {format_type}'
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def export_translation_memory(self, format_type: str = 'tmx') -> str:
        """导出翻译记忆库"""
        try:
            if format_type == 'tmx':
                import xml.etree.ElementTree as ET
                from datetime import datetime
                
                # 创建TMX根元素
                tmx = ET.Element('tmx', version='1.4')
                header = ET.SubElement(tmx, 'header', {
                    'creationtool': 'TransCoder',
                    'creationtoolversion': '1.0',
                    'datatype': 'plaintext',
                    'segtype': 'sentence',
                    'o-tmf': 'TMX',
                    'creationdate': datetime.now().strftime('%Y%m%dT%H%M%SZ')
                })
                
                body = ET.SubElement(tmx, 'body')
                
                # 添加翻译单元
                for item in self.metadata:
                    tu = ET.SubElement(body, 'tu')
                    
                    # 添加源文本
                    tuv_src = ET.SubElement(tu, 'tuv', {'xml:lang': 'en'})  # 假设源语言
                    seg_src = ET.SubElement(tuv_src, 'seg')
                    seg_src.text = item['source']
                    
                    # 添加翻译
                    for lang, translation in item['translations'].items():
                        tuv_tgt = ET.SubElement(tu, 'tuv', {'xml:lang': lang})
                        seg_tgt = ET.SubElement(tuv_tgt, 'seg')
                        seg_tgt.text = translation
                
                # 保存文件
                output_path = os.path.join(config.VECTOR_DB_PATH, f'export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.tmx')
                tree = ET.ElementTree(tmx)
                tree.write(output_path, encoding='utf-8', xml_declaration=True)
                
                return output_path
            
            raise ValueError(f'Unsupported format: {format_type}')
            
        except Exception as e:
            raise Exception(f'Export failed: {str(e)}')
    
    def list_translations(self, page: int = 1, per_page: int = 50, search: str = '') -> Dict[str, Any]:
        """分页列出翻译记忆"""
        try:
            # 过滤翻译记忆
            filtered_items = []
            search_lower = search.lower()
            
            for i, item in enumerate(self.metadata):
                if not search or search_lower in item['source'].lower() or \
                   any(search_lower in translation.lower() for translation in item['translations'].values()):
                    filtered_items.append({
                        'index': i,
                        'source': item['source'],
                        'translations': item['translations']
                    })
            
            # 分页
            total = len(filtered_items)
            start = (page - 1) * per_page
            end = start + per_page
            
            items_page = filtered_items[start:end]
            
            return {
                'success': True,
                'items': items_page,
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
    
    def delete_translation(self, index: int) -> Dict[str, Any]:
        """删除翻译记忆条目"""
        try:
            if 0 <= index < len(self.metadata):
                # 删除元数据
                removed_item = self.metadata.pop(index)
                
                # 重建索引（这是一个简化的方法，实际中可能需要更复杂的索引管理）
                self._rebuild_index()
                
                return {
                    'success': True,
                    'message': f'已删除翻译记忆条目',
                    'total_items': len(self.metadata)
                }
            else:
                return {
                    'success': False,
                    'error': f'无效的索引: {index}'
                }
                
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def _rebuild_index(self):
        """重建FAISS索引"""
        try:
            # 创建新索引
            self.index = faiss.IndexFlatL2(self.dimension)
            
            # 重新添加所有向量
            if self.metadata:
                embeddings = np.array([item['embedding'] for item in self.metadata])
                self.index.add(embeddings)
            
            # 保存索引
            self._save_index()
            
        except Exception as e:
            print(f"Error rebuilding index: {e}")
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取翻译记忆库统计信息"""
        try:
            total_items = len(self.metadata)
            language_counts = {}
            
            for item in self.metadata:
                for lang in item['translations'].keys():
                    language_counts[lang] = language_counts.get(lang, 0) + 1
            
            # 计算平均源文本长度
            avg_source_length = 0
            if self.metadata:
                total_length = sum(len(item['source']) for item in self.metadata)
                avg_source_length = total_length / total_items
            
            return {
                'total_items': total_items,
                'language_counts': language_counts,
                'most_common_languages': sorted(language_counts.items(), key=lambda x: x[1], reverse=True)[:5],
                'avg_source_length': round(avg_source_length, 1),
                'index_size': self.index.ntotal if hasattr(self, 'index') else 0
            }
            
        except Exception as e:
            return {
                'error': str(e)
            }
    
    def clear_all(self) -> Dict[str, Any]:
        """清空所有翻译记忆"""
        try:
            self.metadata = []
            self.index = faiss.IndexFlatL2(self.dimension)
            self._save_index()
            
            return {
                'success': True,
                'message': '已清空所有翻译记忆'
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            } 