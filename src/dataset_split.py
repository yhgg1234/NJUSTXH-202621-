"""
数据集划分模块

功能：
- 分层采样（按行业、城市、学历等维度）
- 训练集/验证集/测试集划分
- 数据平衡性检查
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional
from loguru import logger
from sklearn.model_selection import train_test_split
import sys
sys.path.append('..')
from config import SPLIT_CONFIG


class DatasetSplitter:
    """数据集划分器"""
    
    def __init__(self, config=None):
        """初始化划分器
        
        Args:
            config: 划分配置，默认使用全局配置
        """
        self.config = config or SPLIT_CONFIG
        self.split_report = {}
        
    def split(self, df: pd.DataFrame) -> Tuple[Dict[str, pd.DataFrame], Dict]:
        """执行完整的数据集划分流程
        
        Args:
            df: 标注后的DataFrame
            
        Returns:
            datasets: 字典，包含 'train', 'val', 'test' 三个键
            report: 划分报告字典
        """
        logger.info("开始数据集划分流程...")
        
        original_count = len(df)
        self.split_report = {
            'original_count': original_count,
            'steps': []
        }
        
        # 1. 创建分层字段
        stratify_column = self._create_stratify_column(df)
        
        # 2. 第一次划分：训练集 vs (验证集+测试集)
        train_df, temp_df = self._first_split(df, stratify_column)
        
        # 3. 第二次划分：验证集 vs 测试集
        val_df, test_df = self._second_split(temp_df, stratify_column)
        
        # 4. 验证划分结果
        self._validate_splits(train_df, val_df, test_df, stratify_column)
        
        datasets = {
            'train': train_df.reset_index(drop=True),
            'val': val_df.reset_index(drop=True),
            'test': test_df.reset_index(drop=True)
        }
        
        # 5. 生成统计报告
        self._generate_statistics(datasets, stratify_column)
        
        logger.info(f"数据集划分完成！训练集: {len(train_df)}, 验证集: {len(val_df)}, 测试集: {len(test_df)}")
        
        return datasets, self.split_report
    
    def _create_stratify_column(self, df: pd.DataFrame) -> str:
        """创建用于分层的组合列
        
        将多个分层字段组合成一个字符串列
        """
        stratify_fields = self.config.stratify_fields
        existing_fields = [f for f in stratify_fields if f in df.columns]
        
        if not existing_fields:
            logger.warning("没有可用的分层字段，使用均匀采样")
            df['_stratify_key'] = 'all'
            return '_stratify_key'
        
        # 组合分层字段
        df['_stratify_key'] = df[existing_fields].apply(
            lambda row: '_'.join([str(v) if pd.notna(v) else 'unknown' for v in row]),
            axis=1
        )
        
        # 统计各层的样本数
        stratum_counts = df['_stratify_key'].value_counts()
        
        # 过滤掉样本数太少的层
        min_samples = self.config.min_samples_per_stratum
        valid_strata = stratum_counts[stratum_counts >= min_samples].index
        
        # 将小样本层合并为"other"
        df.loc[~df['_stratify_key'].isin(valid_strata), '_stratify_key'] = 'other'
        
        self.split_report['steps'].append({
            'step': 'create_stratify_column',
            'stratify_fields': existing_fields,
            'num_strata': len(df['_stratify_key'].unique()),
            'min_samples_per_stratum': min_samples
        })
        
        logger.info(f"创建分层列，共 {len(df['_stratify_key'].unique())} 个层")
        
        return '_stratify_key'
    
    def _first_split(self, df: pd.DataFrame, stratify_column: str) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """第一次划分：训练集 vs (验证集+测试集)
        
        按照 train_ratio : (val_ratio + test_ratio) 的比例划分
        """
        train_ratio = self.config.train_ratio
        remaining_ratio = 1 - train_ratio
        
        try:
            train_df, temp_df = train_test_split(
                df,
                train_size=train_ratio,
                stratify=df[stratify_column] if stratify_column in df.columns else None,
                random_state=self.config.random_state
            )
        except ValueError as e:
            # 如果分层失败（某些层样本太少），退化为普通划分
            logger.warning(f"分层划分失败: {e}，使用普通随机划分")
            train_df, temp_df = train_test_split(
                df,
                train_size=train_ratio,
                random_state=self.config.random_state
            )
        
        self.split_report['steps'].append({
            'step': 'first_split',
            'train_ratio': train_ratio,
            'train_count': len(train_df),
            'remaining_count': len(temp_df)
        })
        
        return train_df, temp_df
    
    def _second_split(self, temp_df: pd.DataFrame, stratify_column: str) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """第二次划分：验证集 vs 测试集
        
        按照 val_ratio : test_ratio 的比例划分剩余数据
        """
        val_ratio = self.config.val_ratio
        test_ratio = self.config.test_ratio
        
        # 计算在剩余数据中的比例
        remaining_total = val_ratio + test_ratio
        val_in_remaining = val_ratio / remaining_total
        
        try:
            val_df, test_df = train_test_split(
                temp_df,
                train_size=val_in_remaining,
                stratify=temp_df[stratify_column] if stratify_column in temp_df.columns else None,
                random_state=self.config.random_state + 1  # 使用不同的随机种子
            )
        except ValueError as e:
            # 如果分层失败，退化为普通划分
            logger.warning(f"分层划分失败: {e}，使用普通随机划分")
            val_df, test_df = train_test_split(
                temp_df,
                train_size=val_in_remaining,
                random_state=self.config.random_state + 1
            )
        
        self.split_report['steps'].append({
            'step': 'second_split',
            'val_ratio_in_remaining': val_in_remaining,
            'val_count': len(val_df),
            'test_count': len(test_df)
        })
        
        return val_df, test_df
    
    def _validate_splits(self, train_df: pd.DataFrame, val_df: pd.DataFrame, 
                         test_df: pd.DataFrame, stratify_column: str):
        """验证划分结果的合理性"""
        
        total = len(train_df) + len(val_df) + len(test_df)
        
        actual_train_ratio = len(train_df) / total
        actual_val_ratio = len(val_df) / total
        actual_test_ratio = len(test_df) / total
        
        expected_train_ratio = self.config.train_ratio
        expected_val_ratio = self.config.val_ratio
        expected_test_ratio = self.config.test_ratio
        
        # 检查比例偏差
        tolerance = 0.05  # 允许5%的偏差
        
        validation_issues = []
        
        if abs(actual_train_ratio - expected_train_ratio) > tolerance:
            validation_issues.append(
                f"训练集比例偏差过大: {actual_train_ratio:.2%} vs {expected_train_ratio:.2%}"
            )
        
        if abs(actual_val_ratio - expected_val_ratio) > tolerance:
            validation_issues.append(
                f"验证集比例偏差过大: {actual_val_ratio:.2%} vs {expected_val_ratio:.2%}"
            )
        
        if abs(actual_test_ratio - expected_test_ratio) > tolerance:
            validation_issues.append(
                f"测试集比例偏差过大: {actual_test_ratio:.2%} vs {expected_test_ratio:.2%}"
            )
        
        # 检查是否有重叠
        train_ids = set(train_df.index)
        val_ids = set(val_df.index)
        test_ids = set(test_df.index)
        
        if train_ids & val_ids:
            validation_issues.append("训练集和验证集存在重叠")
        
        if train_ids & test_ids:
            validation_issues.append("训练集和测试集存在重叠")
        
        if val_ids & test_ids:
            validation_issues.append("验证集和测试集存在重叠")
        
        self.split_report['validation'] = {
            'passed': len(validation_issues) == 0,
            'issues': validation_issues,
            'actual_ratios': {
                'train': f"{actual_train_ratio:.2%}",
                'val': f"{actual_val_ratio:.2%}",
                'test': f"{actual_test_ratio:.2%}"
            }
        }
        
        if validation_issues:
            logger.warning(f"划分验证发现问题: {validation_issues}")
        else:
            logger.info("划分验证通过")
    
    def _generate_statistics(self, datasets: Dict[str, pd.DataFrame], stratify_column: str):
        """生成各数据集的统计信息"""
        
        statistics = {}
        
        for dataset_name, df in datasets.items():
            stats = {
                'count': len(df),
                'quality_score_mean': float(df['quality_score'].mean()) if 'quality_score' in df.columns else None,
                'quality_score_std': float(df['quality_score'].std()) if 'quality_score' in df.columns else None,
            }
            
            # 各字段的分布
            distribution_fields = ['industry_tag', 'city_level', 'job_level', 'education']
            for field in distribution_fields:
                if field in df.columns:
                    stats[f'{field}_distribution'] = df[field].value_counts().to_dict()
            
            statistics[dataset_name] = stats
        
        self.split_report['statistics'] = statistics
        
        # 打印简要统计
        logger.info("=" * 60)
        logger.info("数据集划分统计:")
        for name, stats in statistics.items():
            logger.info(f"\n{name.upper()} 集 ({stats['count']} 条):")
            logger.info(f"  平均质量评分: {stats['quality_score_mean']:.3f}" if stats['quality_score_mean'] else "  无质量评分")
            
            if '行业标签_distribution' in stats:
                logger.info(f"  行业分布: {dict(list(stats['行业标签_distribution'].items())[:5])}")
        
        logger.info("=" * 60)
    
    def get_split_report(self) -> Dict:
        """获取划分报告"""
        return self.split_report
    
    def export_datasets(self, datasets: Dict[str, pd.DataFrame], output_dir: str):
        """导出数据集到文件
        
        Args:
            datasets: 划分后的数据集字典
            output_dir: 输出目录
        """
        import os
        
        os.makedirs(output_dir, exist_ok=True)
        
        for name, df in datasets.items():
            filename = f"{name}_set.xlsx"
            filepath = os.path.join(output_dir, filename)
            
            # 删除内部使用的临时列
            cols_to_drop = [col for col in df.columns if col.startswith('_')]
            df_export = df.drop(columns=cols_to_drop, errors='ignore')
            
            df_export.to_excel(filepath, index=False)
            logger.info(f"已导出 {name} 集到: {filepath}")
