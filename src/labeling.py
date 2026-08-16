"""
数据标注模块：质量评分、标签生成、人工校验标记
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional
from datetime import datetime
from loguru import logger
import re
import jieba
import sys
sys.path.append('..')
from config import LABELING_CONFIG, IMPORTANT_FIELDS


class DataLabeler:
    def __init__(self, config=None):
        self.config = config or LABELING_CONFIG
        self.labeling_report = {}
        
    def label(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, Dict]:
        logger.info("开始数据标注流程...")
        self.labeling_report = {'total_records': len(df), 'steps': []}
        df = self._calculate_quality_scores(df)
        df = self._extract_skill_tags(df)
        df = self._generate_industry_tags(df)
        df = self._generate_city_level_tags(df)
        df = self._generate_job_level_tags(df)
        df = self._flag_for_human_review(df)
        self.labeling_report['labeled_count'] = len(df)
        self.labeling_report['high_quality_count'] = int((df['quality_score'] >= 0.8).sum()) if 'quality_score' in df.columns else 0
        self.labeling_report['needs_review_count'] = int(df['needs_human_review'].sum()) if 'needs_human_review' in df.columns else 0
        logger.info(f"标注完成！高质量: {self.labeling_report['high_quality_count']}, 需校验: {self.labeling_report['needs_review_count']}")
        return df, self.labeling_report
    
    def _calculate_quality_scores(self, df: pd.DataFrame) -> pd.DataFrame:
        weights = self.config.quality_weights
        completeness = df.apply(self._calculate_completeness, axis=1)
        clarity = df.apply(self._calculate_clarity, axis=1)
        specificity = df.apply(self._calculate_specificity, axis=1)
        recency = df.apply(self._calculate_recency, axis=1)
        
        qs = (weights['completeness']*completeness +
              weights['clarity']*clarity +
              weights['specificity']*specificity +
              weights['recency']*recency)
        
        df['quality_completeness'] = completeness
        df['quality_clarity'] = clarity
        df['quality_specificity'] = specificity
        df['quality_recency'] = recency
        df['quality_score'] = qs
        
        self.labeling_report['steps'].append({
            'step': 'calculate_quality_scores',
            'weights': weights,
            'avg_quality_score': float(qs.mean()),
            'min': float(qs.min()),
            'max': float(qs.max())
        })
        return df
    
    def _calculate_completeness(self, row: pd.Series) -> float:
        # 所有可能字段
        all_fields = ['jd_id','source_platform','url','job_title','company','industry','city',
                      'education','experience','project_experience','responsibilities','requirements',
                      'raw_skills','tech_stack','certificates','collection_time']
        important = IMPORTANT_FIELDS
        score = 0
        total_weight = 0
        for f in all_fields:
            if f in row.index:
                val = row[f]
                weight = 2 if f in important else 1
                if pd.notna(val) and str(val).strip() and str(val)!='nan':
                    score += weight
                total_weight += weight
        return score / total_weight if total_weight else 0
    
    def _calculate_clarity(self, row: pd.Series) -> float:
        text_fields = ['responsibilities', 'requirements']
        scores = []
        for f in text_fields:
            if f not in row.index:
                continue
            text = str(row.get(f, ''))
            if not text or text=='nan':
                scores.append(0)
                continue
            s = 0
            length = len(text)
            if 50 <= length <= 2000:
                s += 0.3
            elif length < 50:
                s += 0.1
            else:
                s += 0.2
            if any(p in text for p in ['，','。','；','、','\n']):
                s += 0.3
            if re.search(r'\d+', text):
                s += 0.2
            if len(set(text)) / len(text) > 0.3:
                s += 0.2
            scores.append(min(s, 1.0))
        return np.mean(scores) if scores else 0
    
    def _calculate_specificity(self, row: pd.Series) -> float:
        # 通用技术指标：使用技术关键词、年限、学历等
        text_fields = ['responsibilities', 'requirements', 'tech_stack', 'raw_skills']
        scores = []
        for f in text_fields:
            if f not in row.index:
                continue
            text = str(row.get(f, ''))
            if not text or text=='nan':
                scores.append(0)
                continue
            s = 0
            # 出现技术关键词（从技能词库中取一部分作为信号）
            all_skills = []
            for category, skills in self.config.skill_extraction_patterns.items():
                all_skills.extend(skills)
            # 匹配任意技能词
            if any(skill.lower() in text.lower() for skill in all_skills[:50]):  # 取前50个避免过重
                s += 0.3
            if re.search(r'\d+\s*年', text):
                s += 0.3
            if re.search(r'本科|硕士|博士|大专|PMP|CPA|CFA', text):
                s += 0.2
            if re.search(r'工程|建筑|金融|医药|制造|科技|互联网', text):
                s += 0.2
            scores.append(min(s, 1.0))
        return np.mean(scores) if scores else 0
    
    def _calculate_recency(self, row: pd.Series) -> float:
        if 'collection_time' not in row.index:
            return 0.5
        t = row['collection_time']
        if pd.isna(t):
            return 0.5
        if isinstance(t, datetime):
            dt = t
        else:
            try:
                dt = pd.to_datetime(t)
            except:
                return 0.5
        days = (datetime.now() - dt).days
        if days <= 30:
            return 1.0
        elif days <= 90:
            return 0.7
        elif days <= 180:
            return 0.4
        else:
            return 0.1
    
    def _extract_skill_tags(self, df: pd.DataFrame) -> pd.DataFrame:
        import re
        skill_dict = {}
        for category, skills in self.config.skill_extraction_patterns.items():
            for skill in skills:
                # 构建正则模式，确保匹配独立单词
                skill_dict[re.escape(skill)] = category  # 使用 re.escape 转义特殊字符

        if not skill_dict:
            logger.warning("技能词库为空，跳过技能提取")
            return df

        extracted = []
        for _, row in df.iterrows():
            text_fields = ['responsibilities', 'requirements', 'raw_skills', 'tech_stack']
            combined = ' '.join([str(row.get(f, '')) for f in text_fields if f in row.index]).lower()
            found = {}
            for skill_pattern, category in skill_dict.items():
                # 使用正则边界匹配（注意英文单词边界，中文需考虑空格）
                # 对于中文字符，\b 不适用，我们改用前后空格或标点来分割
                # 简单处理：匹配 skill_pattern 作为独立词（前后为空格、标点或开头结尾）
                # 使用 lookaround 确保独立
                pattern = r'(?<![a-zA-Z])' + skill_pattern + r'(?![a-zA-Z])'  # 确保前后不是字母
                if re.search(pattern, combined, re.IGNORECASE):
                    if category not in found:
                        found[category] = []
                    found[category].append(skill_pattern)  # 保留原始大小写显示？建议用原 skill
            extracted.append(found)

        df = df.copy()
        df['extracted_skills'] = extracted
        for category in self.config.skill_extraction_patterns.keys():
            df[f'skill_{category}'] = df['extracted_skills'].apply(lambda x: ', '.join(x.get(category, [])))
        return df
    
    def _generate_industry_tags(self, df: pd.DataFrame) -> pd.DataFrame:
        # 简单映射，可根据实际调整
        mapping = {
            '互联网': ['互联网','IT','软件','网络','科技'],
            '人工智能': ['AI','人工智能','机器学习','深度学习'],
            '大数据': ['大数据','数据分析','数据挖掘'],
            '金融': ['金融','银行','保险','证券'],
            '电商': ['电商','电子商务','零售'],
            '游戏': ['游戏','娱乐'],
            '教育': ['教育','培训'],
            '医疗': ['医疗','健康','医药'],
            '汽车': ['汽车','新能源'],
            '房地产': ['房地产','建筑','物业'],
            '制造业': ['制造','工业','生产'],
            '咨询': ['咨询','顾问'],
            '媒体': ['媒体','广告','营销'],
        }
        def classify(industry_str):
            if pd.isna(industry_str) or industry_str=='nan':
                return '其他'
            ind = str(industry_str).lower()
            for std, keywords in mapping.items():
                for kw in keywords:
                    if kw.lower() in ind:
                        return std
            return '其他'
        df['industry_tag'] = df['industry'].apply(classify)
        return df
    
    def _generate_city_level_tags(self, df: pd.DataFrame) -> pd.DataFrame:
        levels = {
            '一线': ['北京','上海','广州','深圳'],
            '新一线': ['成都','杭州','武汉','西安','南京','重庆','天津','苏州','长沙','郑州'],
            '二线': ['东莞','青岛','沈阳','宁波','昆明','济南','合肥','佛山','哈尔滨','福州']
        }
        def classify(city_str):
            if pd.isna(city_str) or city_str=='nan':
                return '未知'
            city = str(city_str).strip()
            for level, cities in levels.items():
                for c in cities:
                    if c in city:
                        return level
            return '其他'
        df['city_level'] = df['city'].apply(classify)
        return df
    
    def _generate_job_level_tags(self, df: pd.DataFrame) -> pd.DataFrame:
        keywords = {
            '初级': ['初级','助理','实习','应届','0-1年','1年以下'],
            '中级': ['中级','1-3年','2-4年','3-5年'],
            '高级': ['高级','资深','专家','5-10年','8年以上'],
            '管理': ['主管','经理','总监','负责人','leader','manager','合伙人']
        }
        def classify(row):
            title = str(row.get('job_title','')).lower()
            exp = str(row.get('experience','')).lower()
            combined = title + ' ' + exp
            for level, kw_list in keywords.items():
                for kw in kw_list:
                    if kw.lower() in combined:
                        return level
            return '其他'
        df['job_level'] = df.apply(classify, axis=1)
        return df
    
    def _flag_for_human_review(self, df: pd.DataFrame) -> pd.DataFrame:
        flags = []
        for idx, row in df.iterrows():
            need = False
            if 'quality_score' in row.index and row['quality_score'] < 0.6:
                need = True
            if 'contains_inflation' in row.index and row['contains_inflation']:
                need = True
            if np.random.random() < self.config.human_review_sample_rate:
                need = True
            flags.append(need)
        df['needs_human_review'] = flags
        return df
    
    def get_labeling_report(self) -> Dict:
        return self.labeling_report