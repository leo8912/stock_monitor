from dataclasses import dataclass
from typing import Optional


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


class StockRowDataPool:
    """StockRowData 对象池（减少 GC 压力）"""

    def __init__(self, initial_size: int = 200):
        self._pool: list[StockRowData] = []
        self._available: set[int] = set()
        self._max_size = initial_size
        self._stats = {"created": 0, "recycled": 0, "expanded": 0}

        # 预分配对象
        for _ in range(initial_size):
            self._pool.append(StockRowData("", "", "", "", "", ""))
            self._available.add(len(self._pool) - 1)

    def acquire(self) -> StockRowData:
        """从对象池获取对象"""
        if self._available:
            idx = self._available.pop()
            self._stats["recycled"] += 1
            return self._pool[idx]

        # 池耗尽，创建新对象
        new_obj = StockRowData("", "", "", "", "", "")
        self._pool.append(new_obj)
        self._stats["expanded"] += 1
        self._stats["created"] += 1
        return new_obj

    def release(self, obj: StockRowData) -> None:
        """释放对象回对象池"""
        try:
            idx = self._pool.index(obj)
            if idx not in self._available:
                # 重置对象状态
                obj.code = ""
                obj.name = ""
                obj.price = "--"
                obj.change_str = "--"
                obj.color_hex = "#e6eaf3"
                obj.seal_vol = ""
                obj.seal_type = ""
                obj.large_order_info = ""
                obj.recent_net_out = 0.0
                obj.auction_price = 0.0
                obj.auction_vol = 0.0
                obj.auction_intensity = 0.0
                self._available.add(idx)
        except ValueError:
            # 对象不在池中，忽略
            pass

    @property
    def stats(self) -> dict:
        """获取对象池统计信息"""
        return {
            "total": len(self._pool),
            "available": len(self._available),
            "in_use": len(self._pool) - len(self._available),
            **self._stats,
        }

    def reset_stats(self) -> None:
        """重置统计信息"""
        self._stats = {"created": 0, "recycled": 0, "expanded": 0}


# 全局对象池实例
_stock_row_pool: Optional[StockRowDataPool] = None


def get_stock_row_pool(size: int = 200) -> StockRowDataPool:
    """获取全局 StockRowData 对象池"""
    global _stock_row_pool
    if _stock_row_pool is None:
        _stock_row_pool = StockRowDataPool(size)
    return _stock_row_pool
