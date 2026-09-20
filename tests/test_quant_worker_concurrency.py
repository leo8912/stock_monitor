"""T11 并发修复回归测试

覆盖：
- G-10：``MarketDataAdapter`` 使用「每线程独立 requests.Session」
- G-11：``QuantWorker.symbols`` 存副本 + 读取快照，避免并发迭代错乱
- G-12：信号缓存采用「临时文件 + os.replace」原子写，避免读到半截内容
"""

import json
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import requests

import stock_monitor.core.data.market_data_adapter as mda
from stock_monitor.core.workers import quant_worker as qw
from stock_monitor.core.workers.quant_worker import QuantWorker


def _make_worker() -> QuantWorker:
    """构造一个可用（协作对象为 Mock）的 QuantWorker。"""
    fetcher = MagicMock()
    fetcher.market_adapter = MagicMock()
    fetcher.name_registry = MagicMock()
    with patch("stock_monitor.data.stock.stock_db.StockDatabase"):
        return QuantWorker(fetcher, "https://test.webhook")


def _make_adapter_with_fake_sina() -> "mda.MarketDataAdapter":
    """构造 MarketDataAdapter，easyquotation.use 返回带真实 Session 的假 Sina。"""
    fake_easyquotation = MagicMock()
    fake_sina = MagicMock()
    fake_sina._session = requests.Session()
    fake_easyquotation.use.return_value = fake_sina
    with patch.dict(sys.modules, {"easyquotation": fake_easyquotation}):
        return mda.MarketDataAdapter()


class TestThreadLocalSession(unittest.TestCase):
    """G-10：requests.Session 必须每线程独立。"""

    def test_same_thread_returns_same_session(self):
        adapter = _make_adapter_with_fake_sina()
        self.assertIs(adapter._session, adapter._session)

    def test_different_thread_gets_different_session(self):
        adapter = _make_adapter_with_fake_sina()
        main_session = adapter._session

        result = {}

        def _worker():
            result["session"] = adapter._session

        t = threading.Thread(target=_worker)
        t.start()
        t.join()

        self.assertIn("session", result)
        self.assertIsNot(result["session"], main_session)


class TestEasyquotationSharedSessionReplaced(unittest.TestCase):
    """A4：easyquotation 共享 Session 必须被替换为每线程独立代理。"""

    def test_shared_session_replaced_by_thread_local_proxy(self):
        adapter = _make_adapter_with_fake_sina()
        self.assertIsInstance(adapter._sina._session, mda._ThreadLocalSession)

    def test_proxy_yields_per_thread_session(self):
        adapter = _make_adapter_with_fake_sina()
        proxy = adapter._sina._session
        main_session = proxy._current_session()

        result = {}

        def _worker():
            result["session"] = proxy._current_session()

        t = threading.Thread(target=_worker)
        t.start()
        t.join()

        self.assertIn("session", result)
        self.assertIsNot(result["session"], main_session)


class TestSymbolsSnapshot(unittest.TestCase):
    """G-11：symbols 存副本 + 快照。"""

    def test_set_symbols_stores_copy(self):
        worker = _make_worker()
        source = ["sh600000", "sz000001"]
        worker.set_symbols(source)

        # 主线程随后修改传入 list，不应影响 worker
        source.append("sh600001")
        self.assertEqual(worker.symbols, ["sh600000", "sz000001"])

    def test_snapshot_is_independent_copy(self):
        worker = _make_worker()
        worker.set_symbols(["sh600000"])

        snap = worker._symbols_snapshot()
        snap.append("sz000001")

        # 修改快照不影响内部状态
        self.assertEqual(worker.symbols, ["sh600000"])
        self.assertEqual(worker._symbols_snapshot(), ["sh600000"])


class TestAtomicSignalCacheSave(unittest.TestCase):
    """G-12：信号缓存原子写。"""

    def _run_in_tmp(self, func):
        with tempfile.TemporaryDirectory() as d:
            tmp_dir = Path(d)
            cache_file = tmp_dir / "signal_cache.json"
            with (
                patch.object(qw, "CACHE_DIR", tmp_dir),
                patch.object(qw, "SIGNAL_CACHE_FILE", cache_file),
            ):
                func(tmp_dir, cache_file)

    def test_save_writes_valid_json_without_tmp_residue(self):
        worker = _make_worker()
        worker._signal_states = {
            ("sh600000", "MACD金叉"): {"last_score": 3, "last_push_ts": 1.0}
        }

        def _assert(tmp_dir: Path, cache_file: Path):
            worker._save_signal_cache()
            self.assertTrue(cache_file.exists())
            data = json.loads(cache_file.read_text(encoding="utf-8"))
            self.assertEqual(
                data, {"sh600000::MACD金叉": {"last_score": 3, "last_push_ts": 1.0}}
            )
            # 无临时文件残留
            self.assertEqual(list(tmp_dir.glob("*.tmp*")), [])

        self._run_in_tmp(_assert)

    def test_concurrent_writers_keep_file_valid(self):
        """多个写线程并发保存后，文件始终为完整合法 JSON，且无临时文件残留。"""
        worker = _make_worker()
        worker._signal_states = {
            ("sh600000", "sig"): {"last_score": 1, "last_push_ts": 0.0}
        }
        errors = []

        def _writer():
            try:
                for _ in range(40):
                    worker._save_signal_cache()
            except Exception as exc:  # pragma: no cover - 失败即记录
                errors.append(exc)

        def _assert(tmp_dir: Path, cache_file: Path):
            threads = [threading.Thread(target=_writer) for _ in range(4)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

            self.assertEqual(errors, [])
            self.assertEqual(list(tmp_dir.glob("*.tmp*")), [])
            json.loads(cache_file.read_text(encoding="utf-8"))

        self._run_in_tmp(_assert)

    def test_reader_never_sees_partial_content(self):
        """写线程持续原子替换时，读方要么读到完整内容，要么短暂不可读（Windows），
        绝不读到半截内容。这正是 G-12 修复要保证的性质。"""
        worker = _make_worker()
        big_states = {
            (f"sh{i:06d}", "sig"): {"last_score": i, "last_push_ts": float(i)}
            for i in range(400)
        }
        expected = {f"{sym}::{sig}": v for (sym, sig), v in big_states.items()}
        worker._signal_states = big_states

        problems = []
        stop = threading.Event()

        def _writer():
            while not stop.is_set():
                worker._save_signal_cache()

        def _reader(cache_file: Path):
            while not stop.is_set():
                try:
                    raw = cache_file.read_text(encoding="utf-8")
                except OSError:
                    # Windows：替换瞬间文件句柄可能短暂不可读，属预期，文件未损坏
                    continue
                try:
                    parsed = json.loads(raw)
                except json.JSONDecodeError as exc:
                    problems.append(exc)  # 读到半截 → 说明写非原子
                    continue
                if parsed != expected:
                    problems.append(ValueError("读到不完整内容"))

        def _assert(tmp_dir: Path, cache_file: Path):
            threads = [
                threading.Thread(target=_writer),
                threading.Thread(target=_writer),
                threading.Thread(target=_reader, args=(cache_file,)),
                threading.Thread(target=_reader, args=(cache_file,)),
            ]
            for t in threads:
                t.start()
            time.sleep(0.4)
            stop.set()
            for t in threads:
                t.join()

            self.assertEqual(problems, [], f"读到半截/异常内容: {problems}")
            self.assertEqual(list(tmp_dir.glob("*.tmp*")), [])
            json.loads(cache_file.read_text(encoding="utf-8"))

        self._run_in_tmp(_assert)


if __name__ == "__main__":
    unittest.main()
