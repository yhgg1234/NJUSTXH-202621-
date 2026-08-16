#!/usr/bin/env python3
"""
Human-in-the-Loop 人工校验工具

用于对自动标注的结果进行人工审核和修正

用法:
    python human_in_the_loop.py --input <需要校验的文件>
    
示例:
    python human_in_the_loop.py --input data/processed/needs_human_review.xlsx
"""

import argparse
import pandas as pd
import sys
import os
from typing import List, Dict
from loguru import logger


class HumanReviewTool:
    """人工校验工具"""
    
    def __init__(self):
        self.reviewed_data = []
        self.statistics = {
            'total': 0,
            'approved': 0,
            'modified': 0,
            'rejected': 0
        }
    
    def run(self, input_file: str, output_file: str = None):
        """运行人工校验流程
        
        Args:
            input_file: 需要校验的文件路径
            output_file: 输出文件路径（可选）
        """
        
        if not os.path.exists(input_file):
            logger.error(f"输入文件不存在: {input_file}")
            return
        
        # 加载数据
        logger.info(f"加载待校验数据: {input_file}")
        df = pd.read_excel(input_file)
        
        self.statistics['total'] = len(df)
        logger.info(f"共 {len(df)} 条记录需要校验")
        
        # 显示关键字段
        display_columns = [
            'jd_id', 'job_title', 'company', 'industry',
            'city', 'quality_score', 'industry_tag', 'city_level',
            'job_level', 'needs_human_review'
        ]
        
        existing_columns = [col for col in display_columns if col in df.columns]
        
        # 添加校验结果列
        if '校验结果' not in df.columns:
            df['校验结果'] = ''
        if '修改意见' not in df.columns:
            df['修改意见'] = ''
        
        print("\n" + "=" * 80)
        print("Human-in-the-Loop 人工校验工具")
        print("=" * 80)
        print("\n操作说明:")
        print("  - 输入 'a' 或 'approve': 通过（数据正确）")
        print("  - 输入 'm' 或 'modify': 需要修改（会提示输入修改意见）")
        print("  - 输入 'r' 或 'reject': 拒绝（数据错误，应删除）")
        print("  - 输入 's' 或 'skip': 跳过（稍后处理）")
        print("  - 输入 'q' 或 'quit': 退出并保存")
        print("  - 输入 'b' 或 'batch': 批量操作（例如: 'a 10' 表示连续通过10条）")
        print("=" * 80)
        
        # 逐条展示并校验
        for idx in range(len(df)):
            row = df.iloc[idx]
            
            print(f"\n[{idx + 1}/{len(df)}] JD编号: {row.get('JD编号', 'N/A')}")
            print("-" * 80)
            
            # 显示关键信息
            for col in existing_columns:
                value = row[col]
                if pd.notna(value) and str(value).strip():
                    print(f"{col}: {value}")
            
            # 获取用户输入
            while True:
                try:
                    user_input = input("\n>> 校验结果 (a/m/r/s/q/b): ").strip().lower()
                    
                    if user_input in ['a', 'approve', '通过']:
                        df.at[idx, '校验结果'] = '通过'
                        self.statistics['approved'] += 1
                        break
                        
                    elif user_input in ['m', 'modify', '修改']:
                        comment = input(">> 请输入修改意见: ").strip()
                        df.at[idx, '校验结果'] = '需修改'
                        df.at[idx, '修改意见'] = comment
                        self.statistics['modified'] += 1
                        break
                        
                    elif user_input in ['r', 'reject', '拒绝']:
                        df.at[idx, '校验结果'] = '拒绝'
                        self.statistics['rejected'] += 1
                        break
                        
                    elif user_input in ['s', 'skip', '跳过']:
                        df.at[idx, '校验结果'] = '待处理'
                        break
                        
                    elif user_input in ['q', 'quit', '退出']:
                        # 保存并退出
                        self._save_results(df, output_file or input_file.replace('.xlsx', '_reviewed.xlsx'))
                        logger.info("已保存校验结果并退出")
                        return
                        
                    elif user_input.startswith('b ') or user_input.startswith('batch '):
                        # 批量操作
                        parts = user_input.split()
                        if len(parts) >= 2:
                            action = parts[1].lower()
                            count = int(parts[2]) if len(parts) > 2 else 5
                            
                            for i in range(count):
                                if idx + i >= len(df):
                                    break
                                
                                if action in ['a', 'approve']:
                                    df.at[idx + i, '校验结果'] = '通过'
                                    self.statistics['approved'] += 1
                                elif action in ['r', 'reject']:
                                    df.at[idx + i, '校验结果'] = '拒绝'
                                    self.statistics['rejected'] += 1
                            
                            logger.info(f"已批量处理 {min(count, len(df) - idx)} 条记录")
                            break
                        else:
                            print("用法: b <action> [count]，例如: b a 10")
                            
                    else:
                        print("无效输入，请输入 a/m/r/s/q/b")
                        
                except KeyboardInterrupt:
                    # Ctrl+C 中断时保存
                    self._save_results(df, output_file or input_file.replace('.xlsx', '_reviewed.xlsx'))
                    logger.info("检测到中断，已保存校验结果")
                    return
                except Exception as e:
                    print(f"错误: {e}")
        
        # 完成所有记录的校验
        self._save_results(df, output_file or input_file.replace('.xlsx', '_reviewed.xlsx'))
        
        # 打印统计信息
        self._print_statistics()
    
    def _save_results(self, df: pd.DataFrame, output_file: str):
        """保存校验结果"""
        
        df.to_excel(output_file, index=False)
        logger.info(f"✓ 已保存校验结果到: {output_file}")
        
        # 分离不同结果的记录
        approved_df = df[df['校验结果'] == '通过']
        rejected_df = df[df['校验结果'] == '拒绝']
        modified_df = df[df['校验结果'] == '需修改']
        pending_df = df[df['校验结果'].isin(['', '待处理'])]
        
        output_dir = os.path.dirname(output_file)
        
        if len(approved_df) > 0:
            approved_file = os.path.join(output_dir, 'approved_records.xlsx')
            approved_df.to_excel(approved_file, index=False)
            logger.info(f"✓ 已通过记录 ({len(approved_df)} 条): {approved_file}")
        
        if len(rejected_df) > 0:
            rejected_file = os.path.join(output_dir, 'rejected_records.xlsx')
            rejected_df.to_excel(rejected_file, index=False)
            logger.info(f"✓ 已拒绝记录 ({len(rejected_df)} 条): {rejected_file}")
        
        if len(modified_df) > 0:
            modified_file = os.path.join(output_dir, 'modified_records.xlsx')
            modified_df.to_excel(modified_file, index=False)
            logger.info(f"✓ 需修改记录 ({len(modified_df)} 条): {modified_file}")
        
        if len(pending_df) > 0:
            pending_file = os.path.join(output_dir, 'pending_records.xlsx')
            pending_df.to_excel(pending_file, index=False)
            logger.info(f"✓ 待处理记录 ({len(pending_df)} 条): {pending_file}")
    
    def _print_statistics(self):
        """打印统计信息"""
        
        print("\n" + "=" * 80)
        print("校验统计")
        print("=" * 80)
        print(f"总记录数: {self.statistics['total']}")
        print(f"已通过: {self.statistics['approved']} ({self.statistics['approved']/self.statistics['total']*100:.1f}%)")
        print(f"需修改: {self.statistics['modified']} ({self.statistics['modified']/self.statistics['total']*100:.1f}%)")
        print(f"已拒绝: {self.statistics['rejected']} ({self.statistics['rejected']/self.statistics['total']*100:.1f}%)")
        print(f"待处理: {self.statistics['total'] - self.statistics['approved'] - self.statistics['modified'] - self.statistics['rejected']}")
        print("=" * 80)


def main():
    """主函数"""
    
    parser = argparse.ArgumentParser(
        description='Human-in-the-Loop 人工校验工具',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        '--input', '-i',
        required=True,
        help='需要校验的文件路径'
    )
    
    parser.add_argument(
        '--output', '-o',
        help='输出文件路径（可选，默认为输入文件名_reviewed.xlsx）'
    )
    
    args = parser.parse_args()
    
    # 配置日志
    logger.remove()
    logger.add(sys.stderr, level='INFO')
    
    # 运行校验工具
    tool = HumanReviewTool()
    tool.run(args.input, args.output)


if __name__ == '__main__':
    main()
