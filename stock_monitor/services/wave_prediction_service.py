"""
波浪预测历史管理服务

功能：
1. 记录波浪分析预测
2. 验证预测结果
3. 统计成功率
"""

import datetime
from typing import Optional

from stock_monitor.data.stock.stock_db import StockDatabase
from stock_monitor.utils.logger import app_logger


class WavePredictionService:
    """波浪预测历史管理服务"""

    def __init__(self, db: Optional[StockDatabase] = None):
        self.db = db or StockDatabase()

    def record_prediction(
        self,
        symbol: str,
        wave: str,
        trend: str,
        confidence: float,
        price_at_prediction: float,
        target_price: Optional[float] = None,
        timeframe: str = "daily",
        notes: str = "",
    ) -> int:
        """
        记录波浪分析预测

        Args:
            symbol: 股票代码
            wave: 波浪标识 (1-5, A, B, C)
            trend: 趋势方向 (bullish, bearish)
            confidence: 置信度 (0-100)
            price_at_prediction: 预测时的价格
            target_price: 目标价格
            timeframe: 时间周期
            notes: 备注

        Returns:
            预测记录ID
        """
        try:
            with self.db._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO wave_predictions
                    (symbol, wave, trend, confidence, price_at_prediction,
                     target_price, timeframe, notes)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        symbol,
                        wave,
                        trend,
                        confidence,
                        price_at_prediction,
                        target_price,
                        timeframe,
                        notes,
                    ),
                )
                conn.commit()
                prediction_id = cursor.lastrowid
                app_logger.info(
                    f"[波浪预测] 记录预测: {symbol} {wave}({trend}) @ {price_at_prediction}"
                )
                return prediction_id
        except Exception as e:
            app_logger.error(f"[波浪预测] 记录预测失败: {e}")
            return -1

    def verify_prediction(
        self,
        prediction_id: int,
        actual_outcome: str,
        current_price: float,
        notes: str = "",
    ) -> bool:
        """
        验证预测结果

        Args:
            prediction_id: 预测记录ID
            actual_outcome: 实际结果 ('correct', 'wrong', 'partial')
            current_price: 当前价格
            notes: 备注

        Returns:
            是否成功
        """
        try:
            with self.db._get_connection() as conn:
                cursor = conn.cursor()

                # 获取预测记录
                cursor.execute(
                    "SELECT price_at_prediction FROM wave_predictions WHERE id = ?",
                    (prediction_id,),
                )
                row = cursor.fetchone()
                if not row:
                    app_logger.warning(f"[波浪预测] 预测记录不存在: {prediction_id}")
                    return False

                price_at_prediction = row[0]
                profit_loss_pct = (
                    (current_price - price_at_prediction) / price_at_prediction * 100
                )

                cursor.execute(
                    """
                    UPDATE wave_predictions
                    SET is_verified = TRUE,
                        verification_time = ?,
                        actual_outcome = ?,
                        profit_loss_pct = ?,
                        notes = ?
                    WHERE id = ?
                    """,
                    (
                        datetime.datetime.now().isoformat(),
                        actual_outcome,
                        profit_loss_pct,
                        notes,
                        prediction_id,
                    ),
                )
                conn.commit()
                app_logger.info(
                    f"[波浪预测] 验证预测: ID={prediction_id}, 结果={actual_outcome}, "
                    f"盈亏={profit_loss_pct:.2f}%"
                )
                return True
        except Exception as e:
            app_logger.error(f"[波浪预测] 验证预测失败: {e}")
            return False

    def get_prediction_stats(self, symbol: Optional[str] = None) -> dict:
        """
        获取预测统计信息

        Args:
            symbol: 股票代码（可选，不传则统计所有）

        Returns:
            统计信息字典
        """
        try:
            with self.db._get_connection() as conn:
                cursor = conn.cursor()

                if symbol:
                    cursor.execute(
                        """
                        SELECT
                            COUNT(*) as total,
                            SUM(CASE WHEN actual_outcome = 'correct' THEN 1 ELSE 0 END) as correct,
                            SUM(CASE WHEN actual_outcome = 'wrong' THEN 1 ELSE 0 END) as wrong,
                            SUM(CASE WHEN actual_outcome = 'partial' THEN 1 ELSE 0 END) as partial,
                            AVG(profit_loss_pct) as avg_profit,
                            COUNT(CASE WHEN is_verified = TRUE THEN 1 END) as verified_count
                        FROM wave_predictions
                        WHERE symbol = ?
                        """,
                        (symbol,),
                    )
                else:
                    cursor.execute(
                        """
                        SELECT
                            COUNT(*) as total,
                            SUM(CASE WHEN actual_outcome = 'correct' THEN 1 ELSE 0 END) as correct,
                            SUM(CASE WHEN actual_outcome = 'wrong' THEN 1 ELSE 0 END) as wrong,
                            SUM(CASE WHEN actual_outcome = 'partial' THEN 1 ELSE 0 END) as partial,
                            AVG(profit_loss_pct) as avg_profit,
                            COUNT(CASE WHEN is_verified = TRUE THEN 1 END) as verified_count
                        FROM wave_predictions
                        """
                    )

                row = cursor.fetchone()
                if not row or row[0] == 0:
                    return {
                        "total": 0,
                        "correct": 0,
                        "wrong": 0,
                        "partial": 0,
                        "success_rate": 0,
                        "avg_profit": 0,
                        "verified_count": 0,
                    }

                total, correct, wrong, partial, avg_profit, verified_count = row
                correct = correct or 0
                wrong = wrong or 0
                partial = partial or 0
                avg_profit = avg_profit or 0
                verified_count = verified_count or 0

                success_rate = (
                    (correct / verified_count * 100) if verified_count > 0 else 0
                )

                return {
                    "total": total,
                    "correct": correct,
                    "wrong": wrong,
                    "partial": partial,
                    "success_rate": round(success_rate, 2),
                    "avg_profit": round(avg_profit, 2),
                    "verified_count": verified_count,
                }
        except Exception as e:
            app_logger.error(f"[波浪预测] 获取统计信息失败: {e}")
            return {
                "total": 0,
                "correct": 0,
                "wrong": 0,
                "partial": 0,
                "success_rate": 0,
                "avg_profit": 0,
                "verified_count": 0,
            }

    def get_recent_predictions(
        self, symbol: Optional[str] = None, limit: int = 10
    ) -> list[dict]:
        """
        获取最近的预测记录

        Args:
            symbol: 股票代码（可选）
            limit: 返回数量

        Returns:
            预测记录列表
        """
        try:
            with self.db._get_connection() as conn:
                cursor = conn.cursor()

                if symbol:
                    cursor.execute(
                        """
                        SELECT id, symbol, prediction_time, wave, trend, confidence,
                               price_at_prediction, target_price, timeframe, is_verified,
                               verification_time, actual_outcome, profit_loss_pct, notes
                        FROM wave_predictions
                        WHERE symbol = ?
                        ORDER BY prediction_time DESC
                        LIMIT ?
                        """,
                        (symbol, limit),
                    )
                else:
                    cursor.execute(
                        """
                        SELECT id, symbol, prediction_time, wave, trend, confidence,
                               price_at_prediction, target_price, timeframe, is_verified,
                               verification_time, actual_outcome, profit_loss_pct, notes
                        FROM wave_predictions
                        ORDER BY prediction_time DESC
                        LIMIT ?
                        """,
                        (limit,),
                    )

                rows = cursor.fetchall()
                predictions = []
                for row in rows:
                    predictions.append(
                        {
                            "id": row[0],
                            "symbol": row[1],
                            "prediction_time": row[2],
                            "wave": row[3],
                            "trend": row[4],
                            "confidence": row[5],
                            "price_at_prediction": row[6],
                            "target_price": row[7],
                            "timeframe": row[8],
                            "is_verified": row[9],
                            "verification_time": row[10],
                            "actual_outcome": row[11],
                            "profit_loss_pct": row[12],
                            "notes": row[13],
                        }
                    )

                return predictions
        except Exception as e:
            app_logger.error(f"[波浪预测] 获取最近预测失败: {e}")
            return []

    def get_unverified_predictions(self, days: int = 7) -> list[dict]:
        """
        获取未验证的预测记录

        Args:
            days: 多少天前的预测

        Returns:
            未验证的预测记录列表
        """
        try:
            with self.db._get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute(
                    """
                    SELECT id, symbol, prediction_time, wave, trend, confidence,
                           price_at_prediction, target_price, timeframe, notes
                    FROM wave_predictions
                    WHERE is_verified = FALSE
                      AND prediction_time >= datetime('now', ?)
                    ORDER BY prediction_time DESC
                    """,
                    (f"-{days} days",),
                )

                rows = cursor.fetchall()
                predictions = []
                for row in rows:
                    predictions.append(
                        {
                            "id": row[0],
                            "symbol": row[1],
                            "prediction_time": row[2],
                            "wave": row[3],
                            "trend": row[4],
                            "confidence": row[5],
                            "price_at_prediction": row[6],
                            "target_price": row[7],
                            "timeframe": row[8],
                            "notes": row[9],
                        }
                    )

                return predictions
        except Exception as e:
            app_logger.error(f"[波浪预测] 获取未验证预测失败: {e}")
            return []


# 全局实例
wave_prediction_service = WavePredictionService()
