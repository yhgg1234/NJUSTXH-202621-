"""
数据预处理流水线单元测试
"""

import unittest
import pandas as pd
import numpy as np
import sys
import os

# 添加 src 目录到路径
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from data_cleaning import DataCleaner
from deduplication import Deduplicator
from labeling import DataLabeler
from dataset_split import DatasetSplitter


def create_sample_data(n=20):
    """创建测试用的样本数据"""
    
    data = {
        'JD编号': [f'JD{i:05d}' for i in range(1, n + 1)],
        '数据来源平台': ['Boss直聘', '智联招聘', '拉勾', '前程无忧'] * (n // 4 + 1)[:n],
        '原始链接': [f'https://example.com/job/{i:03d}' for i in range(1, n + 1)],
        '采集时间': pd.date_range('2026-05-01', periods=n, freq='D').strftime('%Y-%m-%d').tolist(),
        '岗位名称': ['Python工程师', 'Java开发工程师', '数据分析师', '前端工程师',
                     'Python工程师', '算法工程师', '测试工程师', '产品经理',
                     'Python工程师', '运维工程师', 'UI设计师', '架构师',
                     'Python工程师', '大数据工程师', '安全工程师', '项目经理',
                     'Python工程师', '机器学习工程师', 'DBA', '技术总监'][:n],
        '公司名称': [f'示例科技公司{i}' for i in range(1, n + 1)],
        '所属行业': ['人工智能', '软件开发', '大数据', '互联网',
                     '人工智能', '人工智能', '软件开发', '互联网',
                     '人工智能', '互联网', '互联网', '软件开发',
                     '人工智能', '大数据', '互联网', '互联网',
                     '人工智能', '人工智能', '软件开发', '互联网'][:n],
        '工作城市': ['北京', '上海', '广州', '深圳', '杭州', '成都', '武汉', '南京',
                     '北京', '上海', '广州', '深圳', '杭州', '成都', '武汉', '南京',
                     '北京', '上海', '广州', '深圳'][:n],
        '学历要求': ['本科', '本科', '本科', '本科', '硕士', '本科', '本科', '本科',
                     '本科', '本科', '本科', '硕士', '本科', '本科', '本科', '本科',
                     '本科', '博士', '本科', '本科'][:n],
        '经验要求': ['1-3年', '3-5年', '1-3年', '1-3年', '3-5年', '3-5年', '1-3年', '3-5年',
                     '1-3年', '3-5年', '1-3年', '5-10年', '1-3年', '3-5年', '3-5年', '5-10年',
                     '1-3年', '5-10年', '3-5年', '8年以上'][:n],
        '项目经验要求': ['有Python项目经验', '有Java项目经验', '有数据分析项目经验', '有前端项目经验',
                         '有Python项目经验', '有算法项目经验', '有测试项目经验', '有产品项目经验',
                         '有Python项目经验', '有运维项目经验', '有设计项目经验', '有架构项目经验',
                         '有Python项目经验', '有大数据项目经验', '有安全项目经验', '有管理项目经验',
                         '有Python项目经验', '有ML项目经验', '有数据库项目经验', '有技术管理项目经验'][:n],
        '岗位职责': [
            '负责公司核心产品的Python后端开发，参与系统架构设计，编写高质量代码，进行代码审查。',
            '负责Java后端服务开发，参与微服务架构设计，优化系统性能，编写技术文档。',
            '负责业务数据分析，构建数据指标体系，输出数据报告，为业务决策提供支持。',
            '负责公司Web产品的前端开发，使用React/Vue框架，优化用户体验。',
            '负责公司AI平台的Python开发，参与模型训练和部署，优化算法性能。',
            '负责机器学习算法研发，参与模型设计和优化，推动算法落地应用。',
            '负责产品质量保障，编写测试用例，执行自动化测试，跟踪缺陷修复。',
            '负责产品规划和设计，收集用户需求，制定产品路线图，协调研发团队。',
            '负责公司Python后端开发，参与系统设计和优化，编写技术文档。',
            '负责服务器运维和监控，保障系统稳定运行，处理线上故障。',
            '负责产品UI设计，输出设计稿，参与设计评审，维护设计规范。',
            '负责系统架构设计和技术选型，指导团队开发，解决技术难题。',
            '负责Python后端开发，参与系统架构设计，编写高质量代码。',
            '负责大数据平台开发，参与数据管道设计，优化数据处理性能。',
            '负责系统安全评估和防护，进行安全审计，处理安全事件。',
            '负责项目管理，制定项目计划，协调资源，跟踪项目进度。',
            '负责公司Python后端开发，参与系统设计和优化。',
            '负责机器学习模型研发，参与算法优化和部署。',
            '负责数据库管理和优化，保障数据安全和高可用。',
            '负责技术团队管理，制定技术方向，推动技术创新。'
        ][:n],
        '任职要求': [
            '本科及以上学历，计算机相关专业；熟悉Python、Django/Flask；了解MySQL、Redis；有1-3年后端开发经验。',
            '本科及以上学历，计算机相关专业；熟悉Java、Spring Boot；了解MySQL、Redis；有3-5年后端开发经验。',
            '本科及以上学历，统计或数学相关专业；熟悉SQL、Python；了解Tableau、PowerBI；有数据分析经验。',
            '本科及以上学历，计算机相关专业；熟悉HTML/CSS/JavaScript；了解React或Vue；有前端开发经验。',
            '硕士及以上学历，计算机或AI相关专业；熟悉Python、PyTorch/TensorFlow；了解NLP或CV；有算法研发经验。',
            '硕士及以上学历，计算机相关专业；熟悉Python、机器学习算法；了解深度学习框架；有ML项目经验。',
            '本科及以上学历，计算机相关专业；熟悉测试理论和方法；了解自动化测试工具；有QA经验。',
            '本科及以上学历；熟悉产品设计方法论；了解数据分析；有产品经理经验。',
            '本科及以上学历，计算机相关专业；熟悉Python、Web框架；了解数据库；有后端开发经验。',
            '本科及以上学历，计算机相关专业；熟悉Linux、Shell；了解Docker、K8s；有运维经验。',
            '本科及以上学历，设计相关专业；熟悉Figma、Sketch；了解设计规范；有UI设计经验。',
            '本科及以上学历，计算机相关专业；熟悉分布式系统；了解微服务架构；有架构设计经验。',
            '本科及以上学历，计算机相关专业；熟悉Python、后端框架；了解数据库；有开发经验。',
            '本科及以上学历，计算机相关专业；熟悉Hadoop/Spark；了解数据仓库；有大数据开发经验。',
            '本科及以上学历，计算机相关专业；熟悉网络安全；了解渗透测试；有安全经验。',
            '本科及以上学历；熟悉项目管理方法论；了解敏捷开发；有PM经验。',
            '本科及以上学历，计算机相关专业；熟悉Python；有后端开发经验。',
            '博士学历，计算机或数学相关专业；熟悉机器学习、深度学习；有算法研究经验。',
            '本科及以上学历，计算机相关专业；熟悉MySQL/PostgreSQL；了解数据库优化；有DBA经验。',
            '本科及以上学历，计算机相关专业；熟悉技术管理；了解架构设计；有团队管理经验。'
        ][:n],
        '原始技能词': [
            'Python; Django; MySQL; Redis', 'Java; Spring Boot; MySQL',
            'SQL; Python; Tableau', 'HTML; CSS; JavaScript; React',
            'Python; PyTorch; NLP', 'Python; TensorFlow; ML',
            '测试; 自动化; Selenium', '产品设计; 数据分析',
            'Python; Flask; MySQL', 'Linux; Docker; K8s',
            'Figma; Sketch; UI', '架构; 微服务; 分布式',
            'Python; Django', 'Hadoop; Spark; SQL',
            '安全; 渗透测试', '项目管理; 敏捷',
            'Python', 'ML; 深度学习', 'MySQL; DBA', '技术管理; 架构'
        ][:n],
        '技术栈': [
            'Python; FastAPI; LangChain; Neo4j; Milvus',
            'Java; Spring Boot; MySQL; Redis; Docker',
            'SQL; Python; Excel; Power BI',
            'HTML; CSS; JavaScript; React; Vue',
            'Python; PyTorch; LangChain; Embedding',
            'Python; TensorFlow; Scikit-learn',
            'Python; Selenium; pytest',
            'Axure; Figma; SQL',
            'Python; FastAPI; MySQL',
            'Linux; Docker; Kubernetes; Ansible',
            'Figma; Adobe XD; Sketch',
            'Java; Spring Cloud; MySQL; Redis',
            'Python; Django; PostgreSQL',
            'Hadoop; Spark; Hive; Flink',
            'Python; Burp Suite; Nmap',
            'Jira; Confluence; Excel',
            'Python; Flask',
            'Python; PyTorch; CUDA',
            'MySQL; PostgreSQL; Oracle',
            'Java; Python; 架构设计'
        ][:n],
        '证书要求': ['无硬性要求'] * n,
        '备注': ['示例数据，可替换'] * n
    }
    
    df = pd.DataFrame(data)
    
    # 添加一些噪声数据用于测试清洗功能
    if n >= 5:
        # 添加一条空记录
        df.loc[n] = [None] * len(df.columns)
        df.loc[n, 'JD编号'] = f'JD{n+1:05d}'
        
        # 添加一条重复记录
        df.loc[n + 1] = df.iloc[0].copy()
        df.loc[n + 1, 'JD编号'] = f'JD{n+2:05d}'
    
    return df


class TestDataCleaning(unittest.TestCase):
    """测试数据清洗模块"""
    
    def setUp(self):
        """测试前准备"""
        self.df = create_sample_data(10)
        self.cleaner = DataCleaner()
    
    def test_clean_basic(self):
        """测试基本清洗功能"""
        cleaned_df, report = self.cleaner.clean(self.df)
        
        self.assertIsInstance(cleaned_df, pd.DataFrame)
        self.assertIsInstance(report, dict)
        self.assertIn('original_count', report)
        self.assertIn('final_count', report)
        self.assertIn('steps', report)
    
    def test_filter_invalid_records(self):
        """测试无效记录过滤"""
        # 创建包含空值的测试数据
        df = self.df.copy()
        df.loc[0, '岗位名称'] = None
        df.loc[1, '公司名称'] = None
        
        cleaned_df, _ = self.cleaner.clean(df)
        
        # 岗位名称为空的记录应该被删除
        self.assertNotIn(0, cleaned_df.index)
    
    def test_normalize_text(self):
        """测试文本规范化"""
        df = self.df.copy()
        df.loc[0, '岗位名称'] = '  Python  工程师  '
        
        cleaned_df, _ = self.cleaner.clean(df)
        
        # 检查空格是否被清理
        self.assertEqual(cleaned_df.loc[0, '岗位名称'].strip(), 'Python  工程师')


class TestDeduplication(unittest.TestCase):
    """测试去重模块"""
    
    def setUp(self):
        """测试前准备"""
        self.df = create_sample_data(10)
        self.deduplicator = Deduplicator()
    
    def test_deduplicate_basic(self):
        """测试基本去重功能"""
        dedup_df, report = self.deduplicator.deduplicate(self.df)
        
        self.assertIsInstance(dedup_df, pd.DataFrame)
        self.assertIsInstance(report, dict)
        self.assertIn('original_count', report)
        self.assertIn('final_count', report)
    
    def test_exact_duplicate_removal(self):
        """测试完全重复记录移除"""
        df = self.df.copy()
        
        # 添加完全重复的记录
        df.loc[len(df)] = df.iloc[0].copy()
        
        dedup_df, _ = self.deduplicator.deduplicate(df)
        
        # 应该移除重复记录
        self.assertLess(len(dedup_df), len(df))


class TestLabeling(unittest.TestCase):
    """测试标注模块"""
    
    def setUp(self):
        """测试前准备"""
        self.df = create_sample_data(10)
        self.labeler = DataLabeler()
    
    def test_label_basic(self):
        """测试基本标注功能"""
        labeled_df, report = self.labeler.label(self.df)
        
        self.assertIsInstance(labeled_df, pd.DataFrame)
        self.assertIsInstance(report, dict)
        
        # 检查是否添加了质量评分列
        self.assertIn('质量评分', labeled_df.columns)
        self.assertIn('行业标签', labeled_df.columns)
        self.assertIn('城市等级', labeled_df.columns)
    
    def test_quality_score_range(self):
        """测试质量评分范围"""
        labeled_df, _ = self.labeler.label(self.df)
        
        # 质量评分应该在0-1之间
        self.assertTrue((labeled_df['质量评分'] >= 0).all())
        self.assertTrue((labeled_df['质量评分'] <= 1).all())


class TestDatasetSplit(unittest.TestCase):
    """测试数据集划分模块"""
    
    def setUp(self):
        """测试前准备"""
        self.df = create_sample_data(20)
        self.labeler = DataLabeler()
        self.splitter = DatasetSplitter()
    
    def test_split_basic(self):
        """测试基本划分功能"""
        # 先标注
        labeled_df, _ = self.labeler.label(self.df)
        
        # 再划分
        datasets, report = self.splitter.split(labeled_df)
        
        self.assertIsInstance(datasets, dict)
        self.assertIn('train', datasets)
        self.assertIn('val', datasets)
        self.assertIn('test', datasets)
        
        # 检查总数是否一致
        total = sum(len(ds) for ds in datasets.values())
        self.assertEqual(total, len(labeled_df))


if __name__ == '__main__':
    unittest.main()
