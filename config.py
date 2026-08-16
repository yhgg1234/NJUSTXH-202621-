"""
数据预处理配置文件
所有可配置参数集中在此文件中管理
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional

# ========== 列名映射：原始列名 -> 内部标准列名 ==========
FIELD_MAPPING = {
    'jd_id': 'jd_id',
    'source_platform': 'source_platform',
    'url': 'url',
    'job_title_raw': 'job_title',
    'company_raw': 'company',
    'industry_raw': 'industry',
    'city_raw': 'city',
    'education_required_raw': 'education',
    'experience_required_raw': 'experience',
    'project_experience_raw': 'project_experience',
    'responsibilities': 'responsibilities',
    'requirements': 'requirements',
    'raw_skills': 'raw_skills',
    'tech_stack': 'tech_stack',
    'certificates_raw': 'certificates',
    'crawled_at': 'collection_time',          # 使用爬取时间作为采集时间
    'overall_confidence': 'overall_confidence', # 保留原始置信度，但不用于质量评分
    'needs_human_review': 'needs_human_review',
    # 以下列未映射，将被丢弃（如 extracted_* 等）
}

# 必填字段（内部标准名）
REQUIRED_FIELDS = ['job_title', 'company', 'industry', 'city', 'responsibilities', 'requirements']

# 用于文本相似度的字段（内部标准名）
SIMILARITY_FIELDS = ['job_title', 'company', 'responsibilities', 'requirements', 'tech_stack', 'raw_skills']

# 质量评分中完整性检查的重要字段
IMPORTANT_FIELDS = ['job_title', 'company', 'industry', 'city', 'education', 'experience',
                    'responsibilities', 'requirements', 'tech_stack']


@dataclass
class CleaningConfig:
    """数据清洗配置"""
    required_fields: List[str] = field(default_factory=lambda: REQUIRED_FIELDS)
    
    min_text_length: Dict[str, int] = field(default_factory=lambda: {
        'responsibilities': 20,
        'requirements': 20,
        'job_title': 2,
    })
    
    outlier_rules: Dict[str, Dict] = field(default_factory=lambda: {
        'experience': {
            'min_years': 0,
            'max_years': 50,
            'pattern': r'^(\d+[-~]\d+年|\d+年以上?|\d+年以内|不限|经验不限)$'
        },
        'education': {
            'valid_values': ['不限', '高中', '中专', '大专', '本科', '硕士', '博士', '学历不限']
        }
    })
    
    max_days_since_collection: int = 90
    
    null_handling: Dict[str, str] = field(default_factory=lambda: {
        'company': 'fill',
        'job_title': 'drop',
        'industry': 'fill',
        'city': 'fill',
        'responsibilities': 'drop',
        'requirements': 'fill',
    })


@dataclass
class DeduplicationConfig:
    """去重配置"""
    simhash_threshold: float = 0.85
    minhash_jaccard_threshold: float = 0.7
    
    similarity_fields: Dict[str, float] = field(default_factory=lambda: {
        'job_title': 0.4,
        'company': 0.2,
        'responsibilities': 0.2,
        'requirements': 0.2,
    })
    
    exact_duplicate_tolerance: int = 3
    
    # 通胀关键词（通用）
    inflation_keywords: List[str] = field(default_factory=lambda: [
        '世界顶级', '全球领先', '行业第一', '最好', '最强',
        '完美', '极致', '颠覆性', '革命性', '独一无二'
    ])
    
    retention_strategy: str = 'latest'  # 'latest' or 'most_complete'


@dataclass
class LabelingConfig:
    """标注配置"""
    quality_weights: Dict[str, float] = field(default_factory=lambda: {
        'completeness': 0.3,
        'clarity': 0.25,
        'specificity': 0.25,
        'recency': 0.2
    })
    
    # ===== 通用技能词库（IT 及相关） =====
    skill_extraction_patterns: Dict[str, List[str]] = field(default_factory=lambda: {
        '编程语言': [
            'Python', 'Java', 'Go', 'C++', 'C#', 'JavaScript', 'TypeScript', 'R', 'Scala',
            'Ruby', 'PHP', 'Swift', 'Kotlin', 'Objective-C', 'Shell', 'Perl', 'Lua'
        ],
        '前端框架': [
            'React', 'Vue', 'Angular', 'Svelte', 'Next.js', 'Nuxt', 'jQuery', 'Bootstrap',
            'Tailwind', 'CSS', 'HTML5', 'Webpack', 'Vite'
        ],
        '后端框架': [
            'Spring', 'SpringBoot', 'SpringCloud', 'Django', 'Flask', 'FastAPI',
            'Gin', 'Beego', 'go-zero', 'Kratos', 'gRPC', 'Node.js', 'Express'
        ],
        '数据库': [
            'MySQL', 'PostgreSQL', 'Oracle', 'MongoDB', 'Redis', 'Elasticsearch',
            'HBase', 'Cassandra', 'InfluxDB', 'TiDB', 'OceanBase'
        ],
        '大数据与数据处理': [
            'Hadoop', 'Spark', 'Flink', 'Hive', 'Kafka', 'Storm', 'DataX', 'Sqoop',
            'Flume', 'ETL', '数仓', '数据湖', 'Presto', 'Doris', 'StarRocks'
        ],
        '云与容器': [
            'Docker', 'Kubernetes', 'K8s', 'OpenStack', 'AWS', 'Azure', 'GCP',
            '阿里云', '腾讯云', '华为云', 'Service Mesh', 'Istio', 'CI/CD', 'Jenkins',
            'GitLab CI', 'TeamCity', 'Ansible', 'Terraform'
        ],
        'AI与机器学习': [
            'TensorFlow', 'PyTorch', 'Scikit-learn', 'Keras', 'MXNet', 'PaddlePaddle',
            '深度学习', '机器学习', '强化学习', 'NLP', '计算机视觉', '语音识别',
            'LLM', '大模型', 'AIGC', '多模态', 'RAG', 'Agent', 'Prompt Engineering'
        ],
        '通用技能': [
            '项目管理', '沟通能力', '团队合作', '抗压能力', '逻辑思维', '分析能力',
            '学习能力', '解决问题', '文档撰写', '代码审查', '测试', '运维'
        ]
    })
    
    human_review_sample_rate: float = 0.1


@dataclass
class SplitConfig:
    """数据集划分配置"""
    train_ratio: float = 0.7
    val_ratio: float = 0.15
    test_ratio: float = 0.15
    
    stratify_fields: List[str] = field(default_factory=lambda: [
        'industry', 'city', 'education'
    ])
    
    random_state: int = 42
    min_samples_per_stratum: int = 2


CLEANING_CONFIG = CleaningConfig()
DEDUPLICATION_CONFIG = DeduplicationConfig()
LABELING_CONFIG = LabelingConfig()
SPLIT_CONFIG = SplitConfig()