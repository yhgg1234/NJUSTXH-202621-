#!/usr/bin/env python3
"""
快速启动脚本 - 一键运行数据预处理流水线

用法:
    python quick_start.py
    
或直接指定输入文件:
    python quick_start.py --input data.xlsx
"""

import argparse
import sys
import os

# 将项目根目录添加到 Python 路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.pipeline import DataPreprocessingPipeline
from loguru import logger


def main():
    """主函数"""
    
    parser = argparse.ArgumentParser(
        description='JD 数据预处理流水线 - 快速启动',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
默认输入文件: data.xlsx (当前目录)
默认输出目录: data/processed/

示例用法:
  python quick_start.py
  python quick_start.py --input data.xlsx
  python quick_start.py -i input.xlsx -o output/
        """
    )
    
    parser.add_argument(
        '--input', '-i',
        default='data.xlsx',   # 修改为当前目录下的 data.xlsx
        help='输入文件路径（默认: data.xlsx）'
    )
    
    parser.add_argument(
        '--output', '-o',
        default='data/processed',
        help='输出目录（默认: data/processed）'
    )
    
    args = parser.parse_args()
    
    # 配置日志
    logger.remove()
    logger.add(
        sys.stderr,
        level='INFO',
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
    )
    
    # 创建日志文件
    log_file = os.path.join(args.output, 'pipeline.log')
    os.makedirs(args.output, exist_ok=True)
    logger.add(log_file, level='DEBUG')
    
    # 验证输入文件
    if not os.path.exists(args.input):
        logger.error(f"❌ 输入文件不存在: {args.input}")
        logger.info("\n请检查文件路径是否正确，或使用 --input 参数指定正确的文件路径")
        logger.info(f"\n当前工作目录: {os.getcwd()}")
        return 1
    
    logger.info(f"✓ 输入文件: {args.input}")
    logger.info(f"✓ 输出目录: {args.output}")
    
    # 运行流水线
    try:
        pipeline = DataPreprocessingPipeline(output_dir=args.output)
        datasets = pipeline.run(input_file=args.input)
        
        logger.info("\n" + "=" * 80)
        logger.info("✅ 流水线执行成功！")
        logger.info("=" * 80)
        logger.info(f"\n 输出文件位于: {os.path.abspath(args.output)}/")
        logger.info("\n生成的文件:")
        logger.info("  📊 final_dataset.xlsx          - 完整的高质量数据集")
        logger.info("   train_set.xlsx              - 训练集")
        logger.info("  🔍 val_set.xlsx                - 验证集")
        logger.info("  🧪 test_set.xlsx               - 测试集")
        logger.info("   reports/                    - 各步骤详细报告")
        logger.info("  📝 summary_report.json         - 总结报告")
        logger.info("  📝 needs_human_review.xlsx     - 需要人工校验的数据（如有）")
        logger.info("=" * 80)
        
        logger.info("\n 下一步操作建议:")
        logger.info("  1. 查看总结报告: cat data/processed/summary_report.json")
        logger.info("  2. 进行人工校验: python scripts/human_in_the_loop.py --input data/processed/needs_human_review.xlsx")
        logger.info("  3. 使用训练集开始模型训练")
        logger.info("=" * 80)
        
        return 0
        
    except Exception as e:
        logger.error(f"\n❌ 流水线执行失败: {str(e)}")
        logger.exception("详细错误信息:")
        return 1


if __name__ == '__main__':
    exit(main())