"""
数据预处理主流程管道
"""

import pandas as pd
import numpy as np
from typing import Dict, Optional
from loguru import logger
import json
import os
from datetime import datetime

from .data_cleaning import DataCleaner
from .deduplication import Deduplicator
from .labeling import DataLabeler
from .dataset_split import DatasetSplitter
from config import FIELD_MAPPING


class DataPreprocessingPipeline:
    def __init__(self, output_dir: str = 'data/processed'):
        self.output_dir = output_dir
        self.reports = {}
        self.cleaner = DataCleaner()
        self.deduplicator = Deduplicator()
        self.labeler = DataLabeler()
        self.splitter = DatasetSplitter()
        
    def run(self, input_file: str) -> Dict[str, pd.DataFrame]:
        logger.info("="*80)
        logger.info("开始 JD 数据预处理流水线")
        logger.info(f"输入: {input_file}, 输出: {self.output_dir}")
        start = datetime.now()
        
        try:
            df = self._load_data(input_file)
            logger.info(f"加载完成，共 {len(df)} 条记录")
            
            # 应用列名映射
            df = self._apply_field_mapping(df)
            logger.info(f"映射后列名: {list(df.columns)}")
            
            # 清洗
            logger.info("\n[Step 2/5] 数据清洗...")
            df, cleaning_report = self.cleaner.clean(df)
            self.reports['cleaning'] = cleaning_report
            
            # 去重
            logger.info("\n[Step 3/5] 数据去重...")
            df, dedup_report = self.deduplicator.deduplicate(df)
            self.reports['deduplication'] = dedup_report
            
            # 标注
            logger.info("\n[Step 4/5] 数据标注...")
            df, labeling_report = self.labeler.label(df)
            self.reports['labeling'] = labeling_report
            
            # 划分
            logger.info("\n[Step 5/5] 数据集划分...")
            datasets, split_report = self.splitter.split(df)
            self.reports['splitting'] = split_report
            
            # 保存
            self._save_results(datasets, df)
            
            duration = (datetime.now()-start).total_seconds()
            # 传入 datasets 以正确统计数量
            self._generate_summary_report(duration, datasets)
            
            logger.info("\n✓ 流水线执行成功！总耗时: {:.2f}s".format(duration))
            return datasets
        except Exception as e:
            logger.error(f"✗ 执行失败: {e}")
            raise
    
    def _load_data(self, input_file: str) -> pd.DataFrame:
        if not os.path.exists(input_file):
            raise FileNotFoundError(f"文件不存在: {input_file}")
        ext = os.path.splitext(input_file)[1].lower()
        if ext == '.xlsx':
            return pd.read_excel(input_file)
        elif ext == '.csv':
            return pd.read_csv(input_file, encoding='utf-8')
        else:
            raise ValueError(f"不支持格式: {ext}")
    
    def _apply_field_mapping(self, df: pd.DataFrame) -> pd.DataFrame:
        # 只映射存在的列
        rename_dict = {k: v for k, v in FIELD_MAPPING.items() if k in df.columns}
        df = df.rename(columns=rename_dict)
        # 删除未映射的无关列（可选）
        return df
    
    def _save_results(self, datasets: Dict[str, pd.DataFrame], final_df: pd.DataFrame):
        os.makedirs(self.output_dir, exist_ok=True)
        # 完整数据集
        final_path = os.path.join(self.output_dir, 'final_dataset.xlsx')
        final_df.to_excel(final_path, index=False)
        logger.info(f"✓ 保存完整数据集: {final_path}")
        
        # 划分集
        self.splitter.export_datasets(datasets, self.output_dir)
        
        # 报告
        reports_dir = os.path.join(self.output_dir, 'reports')
        os.makedirs(reports_dir, exist_ok=True)
        for name, report in self.reports.items():
            with open(os.path.join(reports_dir, f'{name}_report.json'), 'w', encoding='utf-8') as f:
                json.dump(report, f, ensure_ascii=False, indent=2, default=str)
            logger.info(f"✓ 保存 {name} 报告")
        
        # 需人工校验
        if 'needs_human_review' in final_df.columns:
            review_df = final_df[final_df['needs_human_review']]
            if len(review_df) > 0:
                review_path = os.path.join(self.output_dir, 'needs_human_review.xlsx')
                review_df.to_excel(review_path, index=False)
                logger.info(f"✓ 保存需人工校验数据 ({len(review_df)} 条)")
    
    def _generate_summary_report(self, duration: float, datasets: Dict[str, pd.DataFrame]):
        """生成总结报告，需要传入 datasets 以正确统计各集数量"""
        summary = {
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'duration_seconds': duration,
            'data_flow': {
                'original': self.reports['cleaning']['original_count'],
                'after_cleaning': self.reports['cleaning']['final_count'],
                'after_deduplication': self.reports['deduplication']['final_count'],
                'final': self.reports['labeling']['labeled_count']
            },
            'quality_metrics': {
                'high_quality_count': self.reports['labeling'].get('high_quality_count', 0),
                'needs_review_count': self.reports['labeling'].get('needs_review_count', 0)
            },
            'dataset_splits': {
                'train': datasets['train'].shape[0],
                'val': datasets['val'].shape[0],
                'test': datasets['test'].shape[0]
            }
        }
        with open(os.path.join(self.output_dir, 'summary_report.json'), 'w', encoding='utf-8') as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
        logger.info("✓ 保存总结报告")