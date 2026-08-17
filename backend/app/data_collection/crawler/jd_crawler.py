# -*- coding: utf-8 -*-
"""
jd_crawler.py —— 合规爬虫主框架(调度 + 限速 + 去重 + PII 过滤 + 导出)
=========================================================================
用法:
    python jd_crawler.py --config config.yaml
    python jd_crawler.py --adapter public_search_demo --pages 3 --out demo.xlsx

合规护栏(硬编码, 不可轻易关掉):
    - 默认限速: 请求间隔 1.5~3.5s 随机抖动, 单平台最多 max_pages 页
    - PII 过滤: 含手机/邮箱/身份证/微信/QQ 的 JD 文本默认丢弃(见 filters)
    - 仅落公开 JD 文本字段, 不抓简历/个人信息
    - 不绕过验证码、不伪造指纹、不破解加密参数
"""
import sys, os, json, time, random, argparse
import yaml
from filters import is_clean, mask_pii
from adapters import get_adapter
from contract_exporter import export


def load_config(path):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def crawl(adapter, pages, crawled_month, drop_pii=True):
    all_records = []
    seen_hashes = set()
    dropped_pii = 0
    dropped_dup = 0
    for page in range(1, pages + 1):
        try:
            raw = adapter.fetch_page(page)
        except Exception as e:
            print(f"  [warn] page {page} fetch failed: {e}")
            break
        recs = adapter.parse(raw)
        for r in recs:
            # 1) PII 过滤(基于自由文本)
            if drop_pii and not is_clean(r):
                dropped_pii += 1
                continue
            # 2) 去重: 基于 (platform, external_id) -> url -> 正文
            key = (r.get("platform"), r.get("external_id"), r.get("url"),
                   (r.get("responsibilities", "") + r.get("requirements", ""))[:200])
            if key in seen_hashes:
                dropped_dup += 1
                continue
            seen_hashes.add(key)
            all_records.append(r)
        # 限速: 随机抖动, 避免固定频率被风控
        time.sleep(random.uniform(1.5, 3.5))
    return all_records, dropped_pii, dropped_dup


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--adapter", default=None, help="覆盖 config 里的 adapter 名")
    ap.add_argument("--pages", type=int, default=None, help="覆盖最大页数")
    ap.add_argument("--out", default=None, help="输出 xlsx 路径")
    ap.add_argument("--no-drop-pii", action="store_true", help="仅脱敏不丢弃(默认丢弃)")
    args = ap.parse_args()

    cfg = load_config(args.config) if os.path.exists(args.config) else {}
    adapter_name = args.adapter or cfg.get("adapter", "public_search_demo")
    pages = args.pages or cfg.get("max_pages", 3)
    out = args.out or cfg.get("out", "jd_crawled_demo.xlsx")
    crawled_month = cfg.get("crawled_month", "") or __import__("datetime").datetime.now().strftime("%Y-%m")

    print(f"[info] adapter={adapter_name} pages={pages} out={out} month={crawled_month}")
    adapter = get_adapter(adapter_name, cfg.get("adapter_cfg", {}))

    records, dropped_pii, dropped_dup = crawl(
        adapter, pages, crawled_month, drop_pii=not args.no_drop_pii)

    print(f"[info] 采集到 {len(records)} 条; 丢弃 PII={dropped_pii}; 去重={dropped_dup}")
    if not records:
        print("[warn] 无数据, 未写出文件")
        return

    out_df, report = export(records, out)
    print(f"[done] 已写出 {len(out_df)} 条 -> {out}")
    print(f"       平台数={report['source_platforms']} 岗位类型数={report['unique_job_titles']} jd_id唯一={report['jd_id_unique']}")


if __name__ == "__main__":
    main()
