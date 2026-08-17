# -*- coding: utf-8 -*-
"""
filters.py —— 合规护栏: 在落库前过滤掉个人信息(PII)
====================================================
仅针对"岗位职责/任职要求"等自由文本做 PII 脱敏。绝不抓取简历背后的姓名/电话/邮箱等。
命中较多 PII 的记录会在 crawler 层被标记/丢弃(默认丢弃, 可配置为仅脱敏)。
"""
import re

# 手机号(中国大陆 1xx)
RE_PHONE = re.compile(r"(?<![\d])(?:1[3-9]\d{9})(?![\d])")
# 邮箱
RE_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
# 身份证(18 位, 粗略)
RE_IDCARD = re.compile(r"(?<!\d)(?:\d{17}[\dXx]|\d{15})(?!\d)")
# 常见即时通讯/微信
RE_WECHAT = re.compile(r"(微信|WeChat|微信号)[\s:：]*[A-Za-z0-9_-]{5,}", re.I)
# qq
RE_QQ = re.compile(r"(?<![\d])(?:[1-9]\d{4,11})(?![\d])")

PII_PATTERNS = [RE_PHONE, RE_EMAIL, RE_IDCARD, RE_WECHAT, RE_QQ]

MASK = "[已脱敏]"


def count_pii(text):
    """返回文本中 PII 命中次数。"""
    if not text:
        return 0
    n = 0
    for pat in PII_PATTERNS:
        n += len(pat.findall(text))
    return n


def mask_pii(text):
    """把文本中的 PII 替换为 [已脱敏]。"""
    if not text:
        return text
    for pat in PII_PATTERNS:
        text = pat.sub(MASK, text)
    return text


def is_clean(record, max_pii=0):
    """
    判断一条 JD 记录是否"干净"。
    record: dict(契约原始字段: responsibilities/requirements/raw_text 等)
    默认: 任何 PII 都视为不干净(返回 False), 由 crawler 决定是否丢弃。
    """
    texts = [str(record.get(k, "")) for k in
             ("responsibilities", "requirements", "raw_text", "company_raw", "city_raw")]
    total = sum(count_pii(t) for t in texts)
    return total <= max_pii
