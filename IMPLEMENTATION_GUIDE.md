# 🎯 审查实施指南 - 快速入门

## 如何使用这份审查报告

### 📖 报告阅读顺序

1. **首先阅读** `CODE_REVIEW_EXECUTIVE_SUMMARY.md`
   - 5分钟快速获取整体情况
   - 了解20个缺陷的优先级排序
   - 确定团队投入的方向

2. **按优先级深入**
   - 🔴 **P0级缺陷** → 阅读 PHASE3 (告警机制)
   - 🟠 **P1级缺陷** → 阅读 PHASE2 (指标引擎性能)
   - 🟡 **P2级改进** → 阅读 PHASE1 (架构重组)

3. **技术细节查阅**
   - 具体改进代码示例已在各报告中详述
   - 建议直接copy代码片段进行改进

---

## 🚀 立即行动 - 第1周任务

### 任务1: 分发重试机制 (预计2天)

**文件:** `stock_monitor/services/notifier.py`

**改进步骤:**
```python
# 步骤1: 增加重试装饰器
import time
from typing import Callable

def retry(max_attempts=3, backoff_factor=0.5):
    """重试装饰器 - 指数退避"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt < max_attempts - 1:
                        wait_time = backoff_factor * (2 ** attempt)
                        app_logger.warning(
                            f"{func.__name__}失败(尝试{attempt+1}/{max_attempts}), "
                            f"{wait_time}秒后重试: {e}"
                        )
                        time.sleep(wait_time)
                    else:
                        raise
            return False
        return wrapper
    return decorator

# 步骤2: 应用到关键方法
@retry(max_attempts=3)
def send_wecom_app_message(cls, config, title, description):
    # ... 现有代码
    pass

# 步骤3: 测试
# python -m pytest tests/test_notifier_retry.py
```

**验收标准:**
- [ ] 网络超时自动重试3次
- [ ] 重试间隔符合指数退避 (0.5s, 1s, 2s)
- [ ] 所有重试都失败时降级到Webhook
- [ ] 日志记录每次重试

**检查清单:**
```bash
# 1. 确保测试通过
pytest tests/test_notifier_service.py -v -k retry

# 2. 手动测试：模拟网络超时
# 在mock中返回timeout，验证是否重试

# 3. 代码review
# 检查backoff时间是否合理
# 检查是否有过多阻塞（最长等待时间: 4.5秒）
```

---

### 任务2: 缓存持久化 (预计2天)

**文件:** `stock_monitor/core/workers/quant_worker.py`

**改进步骤:**
```python
import json
import os
from datetime import datetime

class QuantWorker(QThread):
    CACHE_DIR = ".stock_monitor/cache"

    def __init__(self):
        super().__init__()
        self._alert_cache = self._load_alert_cache()
        # ... 其他初始化

    def _load_alert_cache(self):
        """启动时从磁盘加载缓存"""
        today = datetime.now().strftime("%Y-%m-%d")
        cache_file = os.path.join(self.CACHE_DIR, f"alerts_{today}.json")

        # 创建目录
        os.makedirs(self.CACHE_DIR, exist_ok=True)

        try:
            if os.path.exists(cache_file):
                with open(cache_file, 'r') as f:
                    data = json.load(f)
                    app_logger.info(f"加载当日缓存: {len(data)}条记录")
                    return set(data)
        except Exception as e:
            app_logger.error(f"加载缓存失败: {e}")

        return set()

    def _save_alert_cache(self):
        """定期保存缓存到磁盘"""
        today = datetime.now().strftime("%Y-%m-%d")
        cache_file = os.path.join(self.CACHE_DIR, f"alerts_{today}.json")

        try:
            os.makedirs(self.CACHE_DIR, exist_ok=True)
            with open(cache_file, 'w') as f:
                json.dump(list(self._alert_cache), f)
        except Exception as e:
            app_logger.error(f"保存缓存失败: {e}")

    def run(self):
        """主循环中定期保存"""
        last_save_time = time.time()

        while self._is_running:
            try:
                # ... 现有扫描逻辑

                # 每5分钟保存一次缓存
                if time.time() - last_save_time > 300:
                    self._save_alert_cache()
                    last_save_time = time.time()

            except Exception as e:
                app_logger.error(f"运行异常: {e}")

            self.msleep(1000)
```

**验收标准:**
- [ ] 应用启动时加载前一天缓存
- [ ] 每5分钟保存一次缓存
- [ ] 应用重启后不重复告警
- [ ] 缓存文件大小 <1MB

---

### 任务3: 缓存容量限制 (预计1天)

**文件:** `stock_monitor/core/quant_engine.py`

**改进步骤:**
```python
class LRUCacheWithTTL:
    def __init__(self, max_size=128, default_ttl=60):
        self.cache = {}
        self.order = []  # LRU顺序
        self.max_size = max_size
        self.default_ttl = default_ttl
        self.hits = 0
        self.misses = 0

    def set(self, key, value, ttl_override=None):
        """设置值，超过容量时淘汰最久未使用项"""
        if key in self.cache:
            self._remove(key)

        # 当缓存满时，淘汰最久未使用的项
        while len(self.cache) >= self.max_size and self.order:
            oldest_key = self.order.pop(0)
            evicted = self._remove(oldest_key)
            app_logger.debug(f"淘汰缓存: {oldest_key} (年龄: {evicted}s)")

        self.cache[key] = [value, time.time(), 0]
        self.order.append(key)

    def _remove(self, key):
        """删除键并返回该缓存的年龄"""
        if key not in self.cache:
            return 0

        value, timestamp, count = self.cache[key]
        age = time.time() - timestamp

        del self.cache[key]
        if key in self.order:
            self.order.remove(key)

        return age

    def get_stats(self):
        """获取缓存统计，便于监控"""
        total = self.hits + self.misses
        rate = (self.hits / total * 100) if total else 0

        # 计算平均年龄
        now = time.time()
        ages = [(now - self.cache[k][1]) for k in self.cache]
        avg_age = sum(ages) / len(ages) if ages else 0

        return {
            "size": len(self.cache),
            "max_size": self.max_size,
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": f"{rate:.1f}%",
            "avg_age_seconds": f"{avg_age:.1f}",
        }

# 测试
def test_cache_eviction():
    cache = LRUCacheWithTTL(max_size=3)

    cache.set("a", "value1")
    cache.set("b", "value2")
    cache.set("c", "value3")

    # 缓存满了，添加第4个应该淘汰最旧的"a"
    cache.set("d", "value4")

    assert cache.get("a") is None  # "a"已被淘汰
    assert cache.get("d") == "value4"  # "d"存在
    assert len(cache.cache) == 3
```

**验收标准:**
- [ ] 缓存大小限制在max_size以内
- [ ] LRU淘汰正确运行
- [ ] 缓存统计信息准确

---

### 任务4: 线程池限制 (预计1天)

**文件:** `stock_monitor/core/workers/quant_worker.py`

**改进步骤:**
```python
from concurrent.futures import ThreadPoolExecutor, as_completed
import os

def perform_scan_parallel(self):
    """使用受限的线程池并行扫描"""
    # 根据CPU核数确定线程数，最多4个
    max_workers = min(4, os.cpu_count() or 2)

    app_logger.info(
        f"开始并行扫描: {len(self.symbols)}只股票, "
        f"线程数:{max_workers}"
    )

    scan_started_time = time.time()

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # 提交所有任务
        futures = {
            executor.submit(self._scan_single_symbol, symbol): symbol
            for symbol in self.symbols
        }

        completed_count = 0
        error_count = 0

        try:
            # 使用as_completed获取完成结果
            for future in as_completed(futures, timeout=120):
                symbol = futures[future]
                try:
                    result = future.result(timeout=5)
                    completed_count += 1

                    if completed_count % 10 == 0:
                        app_logger.info(
                            f"扫描进度: {completed_count}/{len(self.symbols)}"
                        )
                except Exception as e:
                    error_count += 1
                    app_logger.error(f"扫描{symbol}失败: {e}")

        except concurrent.futures.TimeoutError:
            app_logger.error("并行扫描总体超时(120秒)")

    elapsed = time.time() - scan_started_time
    app_logger.info(
        f"扫描完成: {completed_count}成功, "
        f"{error_count}失败, 耗时{elapsed:.1f}秒"
    )

def _scan_single_symbol(self, symbol: str):
    """扫描单个股票的独立方法"""
    try:
        # 获取数据
        daily_df = self.engine.fetch_bars(symbol, category=9, offset=100)
        if daily_df.empty:
            return None

        # 扫描信号
        signals = self.engine.scan_all_timeframes(symbol)
        # ... 后续处理

        return signals
    except Exception as e:
        app_logger.error(f"_scan_single_symbol异常: {e}")
        raise
```

**验收标准:**
- [ ] 线程数不超过CPU核数+1
- [ ] 无线程泄漏
- [ ] 总超时时间限制在2分钟以内

---

## 📋 第2周任务预览

- [ ] **Task 5:** 配置装载优化 (缓存配置，5分钟间隔更新)
- [ ] **Task 6:** 报告生成超时保护 (30秒超时)
- [ ] **Task 7:** 信号变化检查 (防止虚假重复)

---

## 🧪 验证清单

完成前4个任务后，运行以下测试验证：

```bash
# 1. 单元测试
pytest tests/test_notifier_service.py -v
pytest tests/test_quant_engine.py::TestLRUCache -v
pytest tests/test_quant_worker.py::TestParallelScan -v

# 2. 集成测试
pytest tests/integration/test_alert_flow.py -v

# 3. 性能测试
python -m pytest tests/performance_test.py -v -k "parallel_scan"

# 4. 手动验证
# 启动应用，在 11:35 检查晨盘复盘报告是否成功发送
# 验证告警缓存是否持久化到 .stock_monitor/cache/
```

---

## 📞 常见问题 (FAQ)

**Q: 如果我们做不完这6周的全部改进呢？**
A: 优先做P0缺陷（前1-2周），这能立即提升告警可靠性从96%到99%。架构重组可以后续逐步进行。

**Q: 需要停掉线上应用吗？**
A: 前4个任务可以hotfix不需要停应用。建议在非交易时段（15:00-18:00）进行。重大架构改动则需要停应用。

**Q: 报告中的改进代码能直接用吗？**
A: 可以，报告中的代码都是可编译的示例。但生产前务必经过充分测试和code review。

**Q: 如何确认改进是否有效？**
A: 查看每个任务的"验收标准"和"检查清单"。更重要的是运行对应的单元测试套件。

---

## 📊 进度跟踪表

打印这个表格并粘贴到团队的看板上：

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
任务                        状态    完成度   负责人
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
P0-1: 分发重试             [ ]     0%     _____
P0-2: 缓存持久化           [ ]     0%     _____
P0-3: 缓存容量限制         [ ]     0%     _____
P0-4: 线程池限制           [ ]     0%     _____
P1-1: 配置装载优化         [ ]     0%     _____
P1-2: 报告超时保护         [ ]     0%     _____
P1-3: 信号变化检查         [ ]     0%     _____
────────────────────────────────────────────────
架构重组                     [ ]     0%     _____
测试补充                     [ ]     0%     _____
性能优化                     [ ]     0%     _____
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

**审查文档已完成！**
下一步：选择第1个任务开始分发重试机制的改进 ✅
