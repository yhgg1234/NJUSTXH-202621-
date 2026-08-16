"""
数据清洗模块
功能：过滤无效记录、规范化文本、异常值检测、时滞识别
"""

import pandas as pd
import numpy as np
import re
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
from loguru import logger
import sys
sys.path.append('..')
from config import CLEANING_CONFIG, FIELD_MAPPING, IMPORTANT_FIELDS


class DataCleaner:
    def __init__(self, config=None):
        self.config = config or CLEANING_CONFIG
        self.cleaning_report = {}
        
    def clean(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, Dict]:
        logger.info("开始数据清洗流程...")
        original_count = len(df)
        self.cleaning_report = {'original_count': original_count, 'steps': []}
        
        # 1. 基础过滤
        df = self._filter_invalid_records(df)
        # 2. 空值处理
        df = self._handle_null_values(df)
        # 3. 文本规范化
        df = self._normalize_text_fields(df)
        # 4. 异常值检测
        df = self._detect_and_handle_outliers(df)
        # 5. 时滞检测
        df = self._detect_stale_data(df)
        # 6. 标准化字段（如经验、学历）
        df = self._standardize_fields(df)
        
        final_count = len(df)
        removed_count = original_count - final_count
        self.cleaning_report.update({
            'final_count': final_count,
            'removed_count': removed_count,
            'removal_rate': f"{removed_count/original_count*100:.2f}%" if original_count>0 else "0%"
        })
        logger.info(f"数据清洗完成！原始: {original_count}, 最终: {final_count}, 移除: {removed_count}")
        return df, self.cleaning_report
    
    def _filter_invalid_records(self, df: pd.DataFrame) -> pd.DataFrame:
        initial = len(df)
        required = self.config.required_fields
        missing = df[required].isnull().any(axis=1)
        df = df[~missing]
        step_info = {'step': 'filter_invalid_records', 'removed_by_missing_required': int(missing.sum()), 'remaining': len(df)}
        
        for field, min_len in self.config.min_text_length.items():
            if field in df.columns:
                too_short = df[field].astype(str).str.len() < min_len
                df = df[~too_short]
                step_info[f'removed_by_{field}_too_short'] = int(too_short.sum())
        
        self.cleaning_report['steps'].append(step_info)
        logger.info(f"过滤无效记录: {initial} -> {len(df)}")
        return df
    
    def _handle_null_values(self, df: pd.DataFrame) -> pd.DataFrame:
        for field, strategy in self.config.null_handling.items():
            if field not in df.columns:
                continue
            null_count = df[field].isnull().sum()
            if strategy == 'drop':
                df = df.dropna(subset=[field])
            elif strategy == 'fill':
                if field == 'company':
                    df[field] = df[field].fillna('未知公司')
                elif field == 'industry':
                    df[field] = df[field].fillna('其他')
                elif field == 'city':
                    df[field] = df[field].fillna('未知')
                else:
                    df[field] = df[field].fillna('')
        self.cleaning_report['steps'].append({'step': 'handle_null_values', 'strategy': self.config.null_handling})
        return df
    
    def _normalize_text_fields(self, df: pd.DataFrame) -> pd.DataFrame:
        text_fields = ['job_title', 'company', 'industry', 'city', 'responsibilities', 'requirements', 
                       'raw_skills', 'tech_stack', 'certificates']
        for field in text_fields:
            if field in df.columns:
                df[field] = df[field].astype(str).str.strip()
                df[field] = df[field].str.replace(r'[\r\n]+', ' ', regex=True)
                df[field] = df[field].str.replace(r'\s+', ' ', regex=True)
                df[field] = df[field].replace('nan', '')
        self.cleaning_report['steps'].append({'step': 'normalize_text_fields', 'fields_processed': text_fields})
        return df
    
    def _detect_and_handle_outliers(self, df: pd.DataFrame) -> pd.DataFrame:
        if 'experience' in df.columns:
            df = self._clean_experience_field(df)
        if 'education' in df.columns:
            df = self._clean_education_field(df)
        if 'collection_time' in df.columns:
            df = self._clean_collection_time_field(df)
        self.cleaning_report['steps'].append({'step': 'detect_and_handle_outliers', 'fields_checked': ['experience','education','collection_time']})
        return df
    
    def _clean_experience_field(self, df: pd.DataFrame) -> pd.DataFrame:
        def normalize_experience(exp_str):
            if pd.isna(exp_str) or exp_str == 'nan':
                return '不限'
            exp_str = str(exp_str).strip()
            numbers = re.findall(r'\d+', exp_str)
            if not numbers:
                return '不限'
            if len(numbers) == 1:
                num = int(numbers[0])
                if '以上' in exp_str or '+' in exp_str:
                    return f'{num}年以上'
                elif '以内' in exp_str or '以下' in exp_str:
                    return f'{num}年以内'
                else:
                    return f'{num}年'
            elif len(numbers) >= 2:
                return f'{numbers[0]}-{numbers[1]}年'
            return exp_str
        df['experience_std'] = df['experience'].apply(normalize_experience)
        return df
    
    def _clean_education_field(self, df: pd.DataFrame) -> pd.DataFrame:
        mapping = {
            '不限':'不限','无要求':'不限','高中':'高中','中专':'中专',
            '大专':'大专','专科':'大专','本科':'本科','学士':'本科',
            '硕士':'硕士','研究生':'硕士','博士':'博士'
        }
        def normalize(edu_str):
            if pd.isna(edu_str) or edu_str == 'nan':
                return '不限'
            edu_str = str(edu_str).strip()
            if edu_str in mapping:
                return mapping[edu_str]
            for key, val in mapping.items():
                if key in edu_str:
                    return val
            return '其他'
        df['education_std'] = df['education'].apply(normalize)
        return df
    
    def _clean_collection_time_field(self, df: pd.DataFrame) -> pd.DataFrame:
        def parse_date(date_str):
            if pd.isna(date_str) or date_str == 'nan':
                return None
            date_str = str(date_str).strip()
            fmts = ['%Y-%m-%d','%Y/%m/%d','%Y年%m月%d日','%Y-%m-%d %H:%M:%S','%Y/%m/%d %H:%M:%S']
            for fmt in fmts:
                try:
                    return datetime.strptime(date_str, fmt)
                except:
                    continue
            return None
        df['collection_time_parsed'] = df['collection_time'].apply(parse_date)
        return df
    
    def _detect_stale_data(self, df: pd.DataFrame) -> pd.DataFrame:
        if 'collection_time_parsed' not in df.columns:
            return df
        now = datetime.now()
        threshold = now - timedelta(days=self.config.max_days_since_collection)
        df['is_stale'] = df['collection_time_parsed'].apply(lambda x: True if x and x < threshold else False)
        stale_count = df['is_stale'].sum()
        self.cleaning_report['steps'].append({
            'step': 'detect_stale_data',
            'threshold_days': self.config.max_days_since_collection,
            'stale_count': int(stale_count),
            'stale_rate': f"{stale_count/len(df)*100:.2f}%" if len(df)>0 else "0%"
        })
        logger.info(f"检测到 {stale_count} 条过时数据")
        return df
    
    def _standardize_fields(self, df: pd.DataFrame) -> pd.DataFrame:
        # 将标准化列替换原列
        if 'experience_std' in df.columns:
            df = df.drop(columns=['experience'], errors='ignore')
            df = df.rename(columns={'experience_std': 'experience'})
        if 'education_std' in df.columns:
            df = df.drop(columns=['education'], errors='ignore')
            df = df.rename(columns={'education_std': 'education'})
        if 'collection_time_parsed' in df.columns:
            df = df.drop(columns=['collection_time'], errors='ignore')
            df = df.rename(columns={'collection_time_parsed': 'collection_time'})
        self.cleaning_report['steps'].append({'step': 'standardize_fields'})
        return df
    
    def get_cleaning_report(self) -> Dict:
        return self.cleaning_report