from sacrebleu import corpus_bleu
from bert_score import score as bert_score
from rouge_score import rouge_scorer
import nltk
from typing import Dict, List, Any
import numpy as np

# 下载必要的NLTK数据
try:
    nltk.download('punkt', quiet=True)
except:
    pass

class EvaluationService:
    def __init__(self):
        self.rouge_scorer = rouge_scorer.RougeScorer(['rouge1', 'rouge2', 'rougeL'], use_stemmer=True)
    
    def evaluate(self, source_text: str, translated_text: str, 
                reference_text: str = None, metrics: List[str] = None) -> Dict[str, Any]:
        """评价翻译质量"""
        
        if metrics is None:
            metrics = ['bleu', 'bert_score', 'rouge']
        
        results = {}
        
        # 如果没有参考翻译，则只计算一些基本指标
        if not reference_text:
            results['length_ratio'] = len(translated_text) / len(source_text) if source_text else 0
            results['warning'] = 'No reference translation provided. Limited metrics available.'
            return results
        
        # BLEU分数
        if 'bleu' in metrics:
            try:
                bleu_score = self._calculate_bleu(translated_text, reference_text)
                results['bleu'] = bleu_score
            except Exception as e:
                results['bleu_error'] = str(e)
        
        # BERT Score
        if 'bert_score' in metrics:
            try:
                bert_scores = self._calculate_bert_score(translated_text, reference_text)
                results['bert_score'] = bert_scores
            except Exception as e:
                results['bert_score_error'] = str(e)
        
        # ROUGE分数
        if 'rouge' in metrics:
            try:
                rouge_scores = self._calculate_rouge(translated_text, reference_text)
                results['rouge'] = rouge_scores
            except Exception as e:
                results['rouge_error'] = str(e)
        
        # TER (Translation Error Rate)
        if 'ter' in metrics:
            try:
                ter_score = self._calculate_ter(translated_text, reference_text)
                results['ter'] = ter_score
            except Exception as e:
                results['ter_error'] = str(e)
        
        # 计算综合评分
        results['overall_score'] = self._calculate_overall_score(results)
        
        return results
    
    def _calculate_bleu(self, hypothesis: str, reference: str) -> Dict[str, float]:
        """计算BLEU分数"""
        try:
            # 使用sacrebleu计算BLEU分数
            bleu = corpus_bleu([hypothesis], [[reference]])
            
            return {
                'score': bleu.score,
                'precisions': bleu.precisions,
                'bp': bleu.bp,  # brevity penalty
                'ratio': bleu.ratio,
                'hyp_len': bleu.hyp_len,
                'ref_len': bleu.ref_len
            }
        except Exception as e:
            print(f"BLEU calculation error: {e}")
            return {'score': 0.0, 'error': str(e)}
    
    def _calculate_bert_score(self, hypothesis: str, reference: str) -> Dict[str, float]:
        """计算BERT Score"""
        try:
            # 计算BERT分数
            P, R, F1 = bert_score(
                [hypothesis], 
                [reference], 
                lang='zh',  # 可以根据实际语言调整
                verbose=False
            )
            
            return {
                'precision': float(P[0]),
                'recall': float(R[0]),
                'f1': float(F1[0])
            }
        except Exception as e:
            print(f"BERT Score calculation error: {e}")
            return {'f1': 0.0, 'error': str(e)}
    
    def _calculate_rouge(self, hypothesis: str, reference: str) -> Dict[str, Dict[str, float]]:
        """计算ROUGE分数"""
        try:
            scores = self.rouge_scorer.score(reference, hypothesis)
            
            result = {}
            for key, score in scores.items():
                result[key] = {
                    'precision': score.precision,
                    'recall': score.recall,
                    'fmeasure': score.fmeasure
                }
            
            return result
        except Exception as e:
            print(f"ROUGE calculation error: {e}")
            return {'error': str(e)}
    
    def _calculate_ter(self, hypothesis: str, reference: str) -> float:
        """计算TER (Translation Error Rate)"""
        try:
            # 简化的TER计算
            # 实际应该使用专门的TER计算库
            from difflib import SequenceMatcher
            
            # 分词
            hyp_tokens = hypothesis.split()
            ref_tokens = reference.split()
            
            # 计算编辑距离
            matcher = SequenceMatcher(None, ref_tokens, hyp_tokens)
            distance = len(ref_tokens) + len(hyp_tokens) - 2 * sum(match.size for match in matcher.get_matching_blocks())
            
            # TER = 编辑距离 / 参考译文长度
            ter = distance / len(ref_tokens) if ref_tokens else 0
            
            return {
                'score': ter,
                'normalized': min(ter, 1.0)  # 归一化到0-1
            }
        except Exception as e:
            print(f"TER calculation error: {e}")
            return {'score': 1.0, 'error': str(e)}
    
    def _calculate_overall_score(self, results: Dict[str, Any]) -> float:
        """计算综合评分"""
        scores = []
        weights = {
            'bleu': 0.25,
            'bert_score': 0.35,
            'rouge': 0.25,
            'ter': 0.15
        }
        
        # BLEU分数
        if 'bleu' in results and isinstance(results['bleu'], dict) and 'score' in results['bleu']:
            scores.append(results['bleu']['score'] / 100.0 * weights['bleu'])
        
        # BERT Score
        if 'bert_score' in results and isinstance(results['bert_score'], dict) and 'f1' in results['bert_score']:
            scores.append(results['bert_score']['f1'] * weights['bert_score'])
        
        # ROUGE分数（使用ROUGE-L的F1）
        if 'rouge' in results and isinstance(results['rouge'], dict) and 'rougeL' in results['rouge']:
            rouge_f1 = results['rouge']['rougeL'].get('fmeasure', 0)
            scores.append(rouge_f1 * weights['rouge'])
        
        # TER（反向，因为TER越低越好）
        if 'ter' in results and isinstance(results['ter'], dict) and 'normalized' in results['ter']:
            ter_score = 1.0 - results['ter']['normalized']
            scores.append(ter_score * weights['ter'])
        
        # 如果没有任何有效分数，返回0
        if not scores:
            return 0.0
        
        # 返回加权平均分数（0-100）
        return sum(scores) / sum(weights[m] for m in weights if any(m in str(s) for s in scores)) * 100
    
    def batch_evaluate(self, translations: List[Dict[str, str]], 
                      references: List[Dict[str, str]] = None) -> List[Dict[str, Any]]:
        """批量评价翻译"""
        results = []
        
        for i, trans in enumerate(translations):
            ref = references[i] if references and i < len(references) else None
            
            eval_result = {
                'index': i,
                'source': trans.get('source', ''),
                'translation': trans.get('translation', ''),
                'evaluations': {}
            }
            
            if ref:
                eval_result['evaluations'] = self.evaluate(
                    trans.get('source', ''),
                    trans.get('translation', ''),
                    ref.get('translation', '')
                )
            
            results.append(eval_result)
        
        return results 