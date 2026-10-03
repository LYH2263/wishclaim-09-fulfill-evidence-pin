"""渠道枚举：前后端唯一事实源。

决策：渠道使用**枚举**而非自由文本 —— 杜绝空白/错别字，保证角标、摘要
等读模型可稳定聚合渲染；前端不硬编码渠道，一律走 GET /api/fulfillment/channels。
"""

CHANNELS = [
    {"value": "offline_handover", "label": "当面交付", "short": "面交", "icon": "🤝"},
    {"value": "express_delivery", "label": "快递寄送", "short": "快递", "icon": "📦"},
    {"value": "photo_confirm", "label": "照片确认", "short": "照片", "icon": "📸"},
    {"value": "digital_giftcard", "label": "数字礼品卡", "short": "卡券", "icon": "🎟️"},
]

_VALUES = {c["value"] for c in CHANNELS}
_INDEX = {c["value"]: c for c in CHANNELS}


def list_channels() -> list[dict]:
    return [dict(c) for c in CHANNELS]


def is_valid(value: str | None) -> bool:
    return isinstance(value, str) and value in _VALUES


def label_of(value: str) -> str:
    return _INDEX[value]["label"]


def short_of(value: str) -> str:
    return _INDEX[value]["short"]


def icon_of(value: str) -> str:
    return _INDEX[value]["icon"]
