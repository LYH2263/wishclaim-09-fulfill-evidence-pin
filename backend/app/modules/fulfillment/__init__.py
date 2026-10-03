"""核销举证（fulfillment proof）。

- channels:  渠道枚举，前后端唯一事实源（前端通过 API 下发获取，不自造常量）
- preview:   claimed 状态下的举证包预览（摘要 + 渠道枚举），纯读、不改 status
- freeze:    完整举证校验 + 快照冻结写库；缺字段/空白拒绝；fulfilled 后禁止再改
- projection: 从冻结快照派生墙角标 / 已完成摘要 / 详情举证区三路读模型
"""

from . import channels, freeze, preview, projection  # noqa: F401
