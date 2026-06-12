from dataclasses import dataclass


@dataclass
class StockRowData:
    """
    股票单行显示数据对象
    代替原本散落且脆弱的多值 tuple 传递方案
    """

    code: str
    name: str
    price: str
    change_str: str
    color_hex: str
    seal_vol: str
    seal_type: str
    large_order_info: str = ""
    recent_net_out: float = 0.0
    # 集合竞价相关字段 [NEW]
    auction_price: float = 0.0
    auction_vol: float = 0.0
    auction_intensity: float = 0.0
    # 暗盘资金字段 [NEW]
    dark_flow_wan: float = 0.0  # 暗盘净流入（万元）
    dark_flow_valid: bool = False  # 是否有有效暗盘数据
    dark_flow_consecutive_days: int = 0  # 连续流入(正)/流出(负)天数

    @property
    def hash_key(self) -> tuple:
        """用于 LRU 缓存比较与渲染状态更新判断"""
        return (
            self.price,
            self.change_str,
            self.color_hex,
            self.seal_vol,
            self.seal_type,
            self.large_order_info,
            self.recent_net_out,
        )
