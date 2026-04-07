import json
import os
import time
from typing import Any, Optional

# Deleted:import akshare as ak
from stock_monitor.config.manager import get_config_dir
from stock_monitor.utils.logger import app_logger


class FinancialFilter:
    """基本面财务异常过滤器"""

    def __init__(self):
        # 缓存目录位于 .stock_monitor/cache/financials
        self.cache_dir = os.path.join(get_config_dir(), "cache", "financials")
        os.makedirs(self.cache_dir, exist_ok=True)
        self.cache_expiry = 24 * 3600  # 缓存有效期24小时

    def get_financial_audit(self, symbol: str) -> dict[str, Any]:
        """
        获取股票财务审计结果

        Returns:
            dict: {
                'rating': '🔴'|'🟡'|'🟢',
                'score_offset': int,  # 评分修正值
                'reasons': list[str], # 风险理由
                'details': dict       # 详细指标
            }
        """
        # 转换 symbol 格式，akshare 常用 6 位数字
        raw_symbol = symbol
        s_lower = symbol.lower()
        if s_lower.startswith(("sh", "sz")):
            raw_symbol = symbol[2:]
        elif s_lower.startswith(("sh", "sz")):  # 冗余检查，以防大小写混合
            raw_symbol = symbol[2:]

        data = self._get_cached_data(raw_symbol)
        if not data:
            data = self._fetch_and_cache(raw_symbol)

        if not data:
            return {
                "rating": "🟢",
                "score_offset": 0,
                "reasons": ["无法获取财务数据，默认跳过"],
                "details": {},
            }

        return self._audit_data(data)

    def _audit_data(self, data: list[dict[str, Any]]) -> dict[str, Any]:
        """审计财务数据"""
        if not data:
            return {"rating": "🟢", "score_offset": 0, "reasons": [], "details": {}}

        # 取最近一期报告
        latest = data[0]
        reasons = []
        score_offset = 0

        def parse_pct(val: Any) -> float:
            if val is None or val == "--":
                return 0.0
            if isinstance(val, (int, float)):
                return float(val)
            try:
                return float(str(val).replace("%", ""))
            except (ValueError, TypeError):
                return 0.0

        # 1. 净利润同比增长率 (Net Profit Growth)
        growth = parse_pct(latest.get("净利润同比增长率"))
        if growth < -50:
            reasons.append(f"净利暴跌({growth}%)")
            score_offset -= 4
        elif growth < -20:
            reasons.append(f"净利下滑({growth}%)")
            score_offset -= 2

        # 2. 净资产收益率 (ROE)
        roe = parse_pct(latest.get("净资产收益率"))
        if roe < 0:
            reasons.append(f"ROE为负({roe}%)")
            score_offset -= 3
        elif roe < 3:
            reasons.append(f"ROE极低({roe}%)")
            score_offset -= 1

        # 3. 资产负债率 (Debt Ratio)
        debt = parse_pct(latest.get("资产负债率"))
        if debt > 85:
            reasons.append(f"负债率极高({debt}%)")
            score_offset -= 3
        elif debt > 70:
            reasons.append(f"负债率偏高({debt}%)")
            score_offset -= 1

        # 确定评级
        rating = "🟢"
        label = "[财务稳健]"
        if score_offset <= -5:
            rating = "🔴"
            label = "[💣 财务严重高危]"
        elif score_offset <= -2:
            rating = "🟡"
            label = "[⚠️ 基本面一般/偏弱]"

        return {
            "rating": rating,
            "label": label,
            "score_offset": max(-10, score_offset),  # 最多扣10分
            "reasons": reasons,
            "details": {
                "growth": latest.get("净利润同比增长率"),
                "roe": latest.get("净资产收益率"),
                "debt": latest.get("资产负债率"),
                "period": latest.get("报告期"),
            },
        }

    def _get_cached_data(self, symbol: str) -> Optional[list[dict[str, Any]]]:
        """读取本地缓存"""
        cache_path = os.path.join(self.cache_dir, f"{symbol}.json")
        if not os.path.exists(cache_path):
            return None

        # 检查是否过期
        if time.time() - os.path.getmtime(cache_path) > self.cache_expiry:
            return None

        try:
            with open(cache_path, encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            app_logger.debug(f"财务缓存文件不存在 {symbol}")
            return None
        except json.JSONDecodeError as e:
            app_logger.error(f"财务缓存 JSON 解析失败 {symbol}: {e}")
            return None
        except OSError as e:
            app_logger.error(f"读取财务缓存 IO 错误 {symbol}: {e}")
            return None

    def _fetch_and_cache(self, symbol: str) -> Optional[list[dict[str, Any]]]:
        """抓取并缓存数据"""
        try:
            # 延迟导入 akshare - 在打包环境中更可靠
            import akshare as ak

            app_logger.info(f"正在从 AkShare 抓取财务摘要：{symbol}")
            # 使用同花顺摘要接口
            df = ak.stock_financial_abstract_ths(symbol=symbol, indicator="主要指标")
            if df.empty:
                return None

            data = df.head(10).to_dict("records")
            cache_path = os.path.join(self.cache_dir, f"{symbol}.json")
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            return data
        except (ImportError, ModuleNotFoundError) as e:
            app_logger.error(f"akshare 导入失败 {symbol}: {e}")
            return None
        except (ValueError, KeyError) as e:
            app_logger.error(f"财务数据解析失败 {symbol}: {e}")
            return None
        except OSError as e:
            app_logger.error(f"财务缓存写入失败 {symbol}: {e}")
            return None
