# -*- coding: utf-8 -*-
"""
adapters.py —— 可插拔的"平台适配器"
=====================================
每个平台一个 Adapter, 负责: fetch_page(page) 拉一页原始响应; parse(raw) 把响应解析成 JD 记录 dict。
框架(jd_crawler.py)负责调度、限速、去重、过滤、导出。

内置两个示例:
  1. PublicSearchAdapter  —— 演示用, 返回 mock 数据, 不联网, 用于跑通框架/验证契约格式。
  2. LoggedInTemplateAdapter —— 登录态平台模板: 你用浏览器 DevTools 抓到职位列表接口后,
     把 url_template / headers(含你自己的 Cookie) / parse() 填好即可。绝不含验证码破解/指纹伪造。

新增平台: 继承 BaseAdapter, 实现 fetch_page + parse, 在 config.yaml 里登记即可。
"""
import time
import requests


class BaseAdapter:
    name = "base"
    platform = ""          # 中文平台名, 写入 source_platform
    max_pages = 1

    def __init__(self, cfg=None):
        self.cfg = cfg or {}

    def fetch_page(self, page):
        raise NotImplementedError

    def parse(self, raw):
        raise NotImplementedError

    def make_record(self, d, crawled_month):
        d = dict(d)
        d["platform"] = self.platform
        d["crawled_month"] = crawled_month
        return d


class PublicSearchAdapter(BaseAdapter):
    """演示适配器: 返回内置 mock JD, 不联网。用于验证框架与契约导出。"""
    name = "public_search_demo"
    platform = "国聘"   # 政府/国企公开招聘, 合规度最高, 作为 demo 平台
    max_pages = 2

    def fetch_page(self, page):
        # 模拟"翻页"返回不同 mock 数据
        mock = [
            dict(url=f"https://www.iguopin.com/job/{1000+page}-{i}",
                 job_title=f"数据分析师(实习)" if i % 3 == 0 else f"大数据开发工程师(示例{i})",
                 company=f"示例科技{i}公司", industry="信息技术", city="北京" if i % 2 else "上海",
                 responsibilities="负责业务数据清洗、指标体系搭建与可视化。",
                 requirements="熟悉 SQL/Python, 了解 Hadoop/Spark 生态。",
                 raw_skills="SQL,Python,Spark", tech_stack="Hadoop,Spark", certificates="",
                 education="本科", experience="1-3年", project_exp="有数据平台项目经验优先。",
         external_id=f"IGP{1000+page}{i}")
    for i in range(1, 6)
        ]
        time.sleep(0.01)  # 模拟网络延迟
        return mock

    def parse(self, raw):
        # raw 已是 list[dict], 直接转记录
        return [self.make_record(d, self.cfg.get("crawled_month", "")) for d in raw]


class LoggedInTemplateAdapter(BaseAdapter):
    """
    登录态平台模板(以 BOSS/智联/拉勾等为例)。
    ---------------------------------------------------------------
    使用方法(合规前提: 仅用你自己的账号、仅抓公开 JD、遵守平台 ToS):
      1. 浏览器登录目标平台;
      2. F12 -> Network, 翻到职位列表页, 找到返回 JD 列表的 XHR 接口;
      3. 复制该请求的:
           - 完整 URL(把分页参数换成 {page} 占位) -> 填入本类 URL_TEMPLATE
           - Request Headers(尤其是 Cookie / Authorization / User-Agent) -> 填入 HEADERS
      4. 按实际 JSON 结构, 补全 parse() 里"提取单条 JD"的字段映射;
      5. 在 config.yaml 把 platform / url_template / headers / max_pages 配好。
    注意: 脚本只做"带你的登录态请求你抓到的公开接口", 不含任何验证码破解、
          设备指纹伪造、加密参数逆向。平台有风控, 请保持低频(见 config 限速)。
    """
    name = "logged_in_template"
    platform = "BOSS直聘"
    max_pages = 5

    # ↓↓↓ 下面三项需要你抓包后填 ↓↓↓
    URL_TEMPLATE = "https://www.zhipin.com/wapi/zpgeek/search/joblist.json?page={page}&city=101010100&query=Java"
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (你的浏览器 UA)",
        "Cookie": "填你从 DevTools 复制的 Cookie(仅用自己账号)",
        # "Authorization": "Bearer xxx"  # 若接口需要
    }
    # ↑↑↑ 上面三项需要你抓包后填 ↑↑↑

    def __init__(self, cfg=None):
        super().__init__(cfg)
        # 允许从 config 覆盖
        self.URL_TEMPLATE = (cfg or {}).get("url_template") or self.URL_TEMPLATE
        self.HEADERS = (cfg or {}).get("headers") or self.HEADERS
        self.platform = (cfg or {}).get("platform") or self.platform
        self.max_pages = (cfg or {}).get("max_pages", self.max_pages)

    def fetch_page(self, page):
        url = self.URL_TEMPLATE.format(page=page)
        # timeout + 简单容错; 不重试绕过风控
        resp = requests.get(url, headers=self.HEADERS, timeout=15)
        resp.raise_for_status()
        return resp.json()

    def parse(self, raw):
        """
        模板占位: 你需要按实际 JSON 结构补全。
        假设接口返回 {"zpData": {"jobList": [ {...}, ... ]}}, 每条含文本字段。
        下面给出映射示例, 字段名请改成真实接口返回的 key。
        """
        job_list = raw.get("zpData", {}).get("jobList", [])
        records = []
        for j in job_list:
            d = dict(
                url=j.get("jobUrl") or j.get("url", ""),
                job_title=j.get("jobName", ""),
                company=j.get("brandName") or j.get("company", ""),
                industry=j.get("industry", ""),
                city=j.get("cityName") or j.get("city", ""),
                responsibilities=j.get("jobDescription") or j.get("responsibilities", ""),
                requirements=j.get("jobRequirement") or j.get("requirements", ""),
                raw_skills=j.get("skills", ""),
                tech_stack=j.get("techStack", ""),
                certificates="",
                education=j.get("education", ""),
                experience=j.get("workYear", ""),
                project_exp="",
                external_id=str(j.get("encryptId") or j.get("jobId") or ""),
            )
            records.append(self.make_record(d, self.cfg.get("crawled_month", "")))
        return records


def get_adapter(name, cfg=None):
    return {
        "public_search_demo": PublicSearchAdapter,
        "logged_in_template": LoggedInTemplateAdapter,
    }[name](cfg)
