"""
去重模块：精确去重、SimHash、MinHash、抄袭检测、通胀检测
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Set, Optional
from loguru import logger
import jieba
import re
from collections import defaultdict
import sys
sys.path.append('..')
from config import DEDUPLICATION_CONFIG, FIELD_MAPPING, SIMILARITY_FIELDS


class Deduplicator:
    def __init__(self, config=None):
        self.config = config or DEDUPLICATION_CONFIG
        self.dedup_report = {}

    def deduplicate(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, Dict]:
        logger.info("开始数据去重流程...")
        original_count = len(df)
        self.dedup_report = {'original_count': original_count, 'steps': []}

        df = self._remove_exact_duplicates(df)
        df = self._detect_simhash_duplicates(df)
        df = self._detect_minhash_duplicates(df)
        df = self._detect_plagiarism(df)
        df = self._detect_inflation(df)
        df = self._apply_retention_strategy(df)

        final_count = len(df)
        self.dedup_report.update({
            'final_count': final_count,
            'removed_count': original_count - final_count,
            'removal_rate': f"{(original_count-final_count)/original_count*100:.2f}%" if original_count>0 else "0%"
        })
        logger.info(f"数据去重完成！原始: {original_count}, 最终: {final_count}")
        return df, self.dedup_report

    def _remove_exact_duplicates(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        修改点：优先使用唯一标识符去重，避免因业务字段填充导致大量误删。
        """
        # 1. 优先使用唯一标识
        if 'jd_id' in df.columns:
            key_fields = ['jd_id']
        elif 'url' in df.columns:
            key_fields = ['url']
        else:
            # 若没有唯一标识，则使用更丰富的组合（加上经验和学历）
            key_fields = ['company', 'job_title', 'city', 'experience', 'education']

        existing = [f for f in key_fields if f in df.columns]
        if not existing:
            logger.warning("没有可用于精确去重的字段，跳过")
            return df

        dup = df.duplicated(subset=existing, keep='first')
        removed = dup.sum()
        df = df[~dup]

        self.dedup_report['steps'].append({
            'step': 'remove_exact_duplicates',
            'key_fields': existing,
            'duplicate_count': int(removed),
            'remaining': len(df)
        })
        logger.info(f"移除完全重复记录: {removed} 条 (基于 {existing})")
        return df

    def _detect_simhash_duplicates(self, df: pd.DataFrame) -> pd.DataFrame:
        try:
            from simhash import Simhash
        except ImportError:
            logger.warning("simhash 未安装，跳过")
            return df

        df['simhash_text'] = df.apply(self._build_similarity_text, axis=1)
        simhashes = []
        for text in df['simhash_text']:
            if pd.isna(text) or text == '':
                simhashes.append(None)
            else:
                words = jieba.lcut(str(text))
                simhashes.append(Simhash(words).value)
        df = df.copy()
        df['simhash_value'] = simhashes

        similar_pairs = self._find_similar_simhash_pairs(df)
        to_remove = set()
        for idx1, idx2, sim in similar_pairs:
            if sim >= self.config.simhash_threshold:
                to_remove.add(idx2)  # 保留第一个
        df = df.drop(index=list(to_remove))

        self.dedup_report['steps'].append({
            'step': 'detect_simhash_duplicates',
            'threshold': self.config.simhash_threshold,
            'similar_pairs_found': len(similar_pairs),
            'removed_count': len(to_remove),
            'remaining': len(df)
        })
        logger.info(f"SimHash 移除 {len(to_remove)} 条")
        df = df.drop(columns=['simhash_text','simhash_value'], errors='ignore')
        return df

    def _detect_minhash_duplicates(self, df: pd.DataFrame) -> pd.DataFrame:
        try:
            from datasketch import MinHash
        except ImportError:
            logger.warning("datasketch 未安装，跳过")
            return df

        minhashes = []
        for _, row in df.iterrows():
            text = self._build_similarity_text(row)
            if pd.isna(text) or text == '':
                minhashes.append(None)
                continue
            words = set(jieba.lcut(str(text)))
            mh = MinHash(num_perm=128)
            for w in words:
                mh.update(w.encode('utf8'))
            minhashes.append(mh)
        df = df.copy()
        df['minhash_obj'] = minhashes

        similar_pairs = self._find_similar_minhash_pairs(df)
        to_remove = set()
        for idx1, idx2, jaccard in similar_pairs:
            if jaccard >= self.config.minhash_jaccard_threshold:
                to_remove.add(idx2)
        df = df.drop(index=list(to_remove))

        self.dedup_report['steps'].append({
            'step': 'detect_minhash_duplicates',
            'jaccard_threshold': self.config.minhash_jaccard_threshold,
            'similar_pairs_found': len(similar_pairs),
            'removed_count': len(to_remove),
            'remaining': len(df)
        })
        logger.info(f"MinHash 移除 {len(to_remove)} 条")
        df = df.drop(columns=['minhash_obj'], errors='ignore')
        return df

    def _detect_plagiarism(self, df: pd.DataFrame) -> pd.DataFrame:
        text_fields = ['responsibilities', 'requirements']
        existing = [f for f in text_fields if f in df.columns]
        if not existing:
            return df
        plag_indices = self._find_plagiarized_records(df, existing)
        if plag_indices:
            df = df.drop(index=plag_indices)
        self.dedup_report['steps'].append({
            'step': 'detect_plagiarism',
            'fields_checked': existing,
            'plagiarism_count': len(plag_indices),
            'remaining': len(df)
        })
        logger.info(f"检测到抄袭记录 {len(plag_indices)} 条")
        return df

    def _detect_inflation(self, df: pd.DataFrame) -> pd.DataFrame:
        keywords = self.config.inflation_keywords
        text_fields = ['job_title', 'responsibilities', 'requirements']
        existing = [f for f in text_fields if f in df.columns]
        flags = []
        for _, row in df.iterrows():
            has = False
            for f in existing:
                text = str(row.get(f, ''))
                if any(kw in text for kw in keywords):
                    has = True
                    break
            flags.append(has)
        df = df.copy()
        df['contains_inflation'] = flags
        self.dedup_report['steps'].append({
            'step': 'detect_inflation',
            'inflation_keywords': keywords,
            'inflation_count': sum(flags),
            'inflation_rate': f"{sum(flags)/len(df)*100:.2f}%" if len(df)>0 else "0%"
        })
        logger.info(f"检测到 {sum(flags)} 条通胀词汇")
        return df

    def _apply_retention_strategy(self, df: pd.DataFrame) -> pd.DataFrame:
        strategy = self.config.retention_strategy
        if strategy == 'most_complete':
            df['completeness_score'] = df.apply(self._calculate_completeness_score, axis=1)
            # 如果去重键是jd_id，则不应再按公司+岗位去重，否则会重复删除。此处保留原逻辑，但可考虑去除
            # 为避免重复删除，如果已有jd_id去重，此处可跳过或使用其他键
            # 简单起见，如果'jd_id'存在，则按jd_id去重（但已经被去重过，所以这里可能无效）
            # 我们保留原逻辑，但注意：如果之前已按jd_id去重，这里再次去重可能不会删除任何记录
            # 若没有jd_id，则按原逻辑
            if 'jd_id' in df.columns:
                key = ['jd_id']
            elif 'url' in df.columns:
                key = ['url']
            else:
                key = ['company', 'job_title', 'city']
            df = df.sort_values('completeness_score', ascending=False)
            df = df.drop_duplicates(subset=key, keep='first')
            df = df.drop(columns=['completeness_score'])
        elif strategy == 'latest':
            if 'collection_time' in df.columns:
                # 同样，使用唯一键去重
                if 'jd_id' in df.columns:
                    key = ['jd_id']
                elif 'url' in df.columns:
                    key = ['url']
                else:
                    key = ['company', 'job_title', 'city']
                df = df.sort_values('collection_time', ascending=False)
                df = df.drop_duplicates(subset=key, keep='first')
        self.dedup_report['steps'].append({'step': 'apply_retention_strategy', 'strategy': strategy})
        return df

    def _build_similarity_text(self, row: pd.Series) -> str:
        fields = list(self.config.similarity_fields.keys())
        texts = []
        for f in fields:
            if f in row.index and pd.notna(row[f]):
                texts.append(str(row[f]))
        return ' '.join(texts)

    def _find_similar_simhash_pairs(self, df: pd.DataFrame) -> List[Tuple[int, int, float]]:
        pairs = []
        indices = df.index.tolist()
        for i in range(len(indices)):
            for j in range(i+1, min(i+10, len(indices))):
                idx1, idx2 = indices[i], indices[j]
                h1, h2 = df.loc[idx1, 'simhash_value'], df.loc[idx2, 'simhash_value']
                if h1 is None or h2 is None:
                    continue
                dist = bin(h1 ^ h2).count('1')
                sim = 1 - dist/64
                if sim >= self.config.simhash_threshold * 0.8:
                    pairs.append((idx1, idx2, sim))
        return pairs

    def _find_similar_minhash_pairs(self, df: pd.DataFrame) -> List[Tuple[int, int, float]]:
        pairs = []
        indices = df.index.tolist()
        for i in range(len(indices)):
            for j in range(i+1, min(i+10, len(indices))):
                idx1, idx2 = indices[i], indices[j]
                mh1, mh2 = df.loc[idx1, 'minhash_obj'], df.loc[idx2, 'minhash_obj']
                if mh1 is None or mh2 is None:
                    continue
                jac = mh1.jaccard(mh2)
                if jac >= self.config.minhash_jaccard_threshold * 0.8:
                    pairs.append((idx1, idx2, jac))
        return pairs

    def _find_plagiarized_records(self, df: pd.DataFrame, fields: List[str]) -> List[int]:
        plag = []
        text_index = {}
        for idx, row in df.iterrows():
            combined = ' '.join([str(row.get(f,'')) for f in fields])
            if combined.strip():
                text_index[idx] = combined
        indices = list(text_index.keys())
        compared = set()
        for i in range(len(indices)):
            for j in range(i+1, min(i+20, len(indices))):
                idx1, idx2 = indices[i], indices[j]
                pair = tuple(sorted([idx1, idx2]))
                if pair in compared:
                    continue
                compared.add(pair)
                t1, t2 = text_index[idx1], text_index[idx2]
                if len(t1)>0 and len(t2)>0:
                    common = len(set(t1) & set(t2))
                    total = len(set(t1) | set(t2))
                    if total > 0 and common/total > 0.9:
                        if len(t1) >= len(t2):
                            plag.append(idx2)
                        else:
                            plag.append(idx1)
        return list(set(plag))

    def _calculate_completeness_score(self, row: pd.Series) -> float:
        important = ['company','job_title','industry','city','education','experience','responsibilities','requirements','tech_stack']
        score = sum(1 for f in important if f in row.index and pd.notna(row[f]) and str(row[f]).strip() and str(row[f])!='nan')
        return score / len(important) if important else 0

    def get_dedup_report(self) -> Dict:
        return self.dedup_report