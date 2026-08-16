#!/usr/bin/env python3
"""
数据预处理流水线主脚本

用法:
    python run_pipeline.py --input <输入文件> --output <输出目录>
    
示例:
    python run_pipeline.py --input data/raw/JD数据.xlsx --output data/processed/
"""

import argparse
import sys
import os

# 添加 src 目录到 Python 路径
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from pipeline import DataPreprocessingPipeline
from loguru import logger


def main():
    """主函数"""
    
    # 解析命令行参数
    parser = argparse.ArgumentParser(
        description='JD 数据预处理流水线',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  python run_pipeline.py --input data/raw/JD数据.xlsx --output data/processed/
  python run_pipeline.py -i input.xlsx -o output/
        """
    )
    
    parser.add_argument(
        '--input', '-i',
        required=True,
        help='输入文件路径（.xlsx 或 .csv）'
    )
    
    parser.add_argument(
        '--output', '-o',
        default='data/processed',
        help='输出目录（默认: data/processed）'
    )
    
    parser.add_argument(
        '--log-level',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        default='INFO',
        help='日志级别（默认: INFO）'
    )
    
    args = parser.parse_args()
    
    # 配置日志
    logger.remove()  # 移除默认处理器
    logger.add(
        sys.stderr,
        level=args.log_level,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
    )
    
    # 创建日志文件
    log_file = os.path.join(args.output, 'pipeline.log')
    os.makedirs(args.output, exist_ok=True)
    logger.add(log_file, level='DEBUG')
    
    # 验证输入文件
    if not os.path.exists(args.input):
        logger.error(f"输入文件不存在: {args.input}")
        sys.exit(1)
    
    # 运行流水线
    try:
        pipeline = DataPreprocessingPipeline(output_dir=args.output)
        datasets = pipeline.run(input_file=args.input)
        
        logger.info("\n✓ 流水线执行成功！")
        logger.info(f"\n输出文件位于: {args.output}/")
        logger.info("  - final_dataset.xlsx (完整数据集)")
        logger.info("  - train_set.xlsx (训练集)")
        logger.info("  - val_set.xlsx (验证集)")
        logger.info("  - test_set.xlsx (测试集)")
        logger.info("  - reports/ (各步骤详细报告)")
        logger.info("  - summary_report.json (总结报告)")
        
        return 0
        
    except Exception as e:
        logger.error(f"\n✗ 流水线执行失败: {str(e)}")
        logger.exception("详细错误信息:")
        return 1


if __name__ == '__main__':
    exit(main())
