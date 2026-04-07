# 📌 审查快速参考卡片

## 🎯 一页纸总结

**项目:** 股票监控系统 PyQt6+量化分析
**审查日期:** 2026-04-03
**综合评分:** 7.0/10 → 目标 8.2/10 (+17%)
**预计工作量:** 6周（含测试）

---

## 📊 核心指标

| 指标 | 当前 | 目标 | 优先级 |
|-----|------|------|--------|
| 告警可靠性 | 96% | 99% | 🔴 P0 |
| 测试覆盖 | 35% | 85% | 🔴 P0 |
| 扫描速度 | 21s | 12s | 🟠 P1 |
| 架构评分 | 7/10 | 8.5/10 | 🟠 P1 |
| 代码复杂度 | 6.5 | <5 | 🟡 P2 |

---

## 🔴 5大关键缺陷

```
1. 分发无重试    → 网络波动丢失告警 ~20%        [2天修复]
2. 缓存无持久化  → 应用重启重复告警             [2天修复]
3. 缓存无容量    → 内存泄漏风险               [1天修复]
4. core层太大    → 职责混乱难维护             [3周改进]
5. 测试不足      → 覆盖率仅35%                [1周改进]
```

---

## 📅 快速行动计划

### 第1-2周 [关键缺陷修复 - 4项任务]
- ✅ Task 1: 分发重试 (2天)
- ✅ Task 2: 缓存持久化 (2天)
- ✅ Task 3: 缓存容量 (1天)
- ✅ Task 4: 线程池限制 (1天)

**预期效果:** 告警可靠性 96%→99% ✨

### 第3周 [配置与监控]
- Task 5: 配置优化
- Task 6: 超时保护
- Task 7: 信号检查

### 第4-5周 [架构与测试]
- 模块重组
- 测试补充 (+50 tests)

### 第6周 [性能优化]
- 预缓存 (+30%)
- 指标缓存 (+40%)

---

## 代码示例

### 🔴 问题1: 分发无重试

**当前 (问题):**
```python
def dispatch_alert(config, signal):
    try:
        resp = requests.post(url, json=payload, timeout=10)
        if resp.ok:
            return True
    except Exception:
        return False  # ❌ 直接失败
```

**改进 (解决):**
```python
@retry(max_attempts=3, backoff_factor=0.5)
def dispatch_alert(config, signal):
    # ... 会自动重试3次，时间间隔为 0.5s, 1s, 2s
```

**工作量:** 30分钟
**文件:** `stock_monitor/services/notifier.py`

---

### 🔴 问题2: 缓存无持久化

**当前 (问题):**
```python
_alert_cache = set()  # ❌ 内存中，应用重启就丢了
```

**改进 (解决):**
```python
def __init__(self):
    self._alert_cache = self._load_from_disk()  # 启动时恢复

def run(self):
    if time.time() % 300 == 0:  # 每5分钟
        self._save_to_disk()  # 持久化缓存
```

**工作量:** 2天
**文件:** `stock_monitor/core/workers/quant_worker.py`

---

### 🟠 问题3: 缓存无容量限制

**当前 (问题):**
```python
_avg_vol_cache = {}  # ❌ 无限增长（1年积累365条）
_auction_cache = {}  # ❌ 同样问题
```

**改进 (解决):**
```python
class LRUCacheWithTTL:
    def set(self, key, value):
        while len(self.cache) >= self.max_size:  # ✅ 容量检查
            self._evict_oldest()
        self.cache[key] = value
```

**工作量:** 1天
**文件:** `stock_monitor/core/quant_engine.py`

---

## 🧪 验证步骤

完成修复后运行：

```bash
# 1. 单元测试
pytest tests/test_notifier_service.py -v

# 2. 集成测试
pytest tests/integration/test_alert_flow.py -v

# 3. 手动验证
# - 启动应用，检查告警缓存是否保存
# - 重启应用，验证是否恢复缓存
# - 模拟网络超时，验证是否重试
```

---

## 📞 关键联系

**报告文档:**
- `CODE_REVIEW_EXECUTIVE_SUMMARY.md` - 全面总结
- `PHASE1_ARCHITECTURE_REVIEW.md` - 架构分析
- `PHASE2_QUANT_ENGINE_REVIEW.md` - 指标分析
- `PHASE3_ALERT_DELIVERY_REVIEW.md` - 告警分析
- `IMPLEMENTATION_GUIDE.md` - 详细实施指南

**推荐阅读顺序:**
1. 本卡片 (5分钟) ← 现在
2. `CODE_REVIEW_EXECUTIVE_SUMMARY.md` (10分钟)
3. 按优先级深入各PHASE报告

---

## ⏱️ 预算时间

| 任务 | 开发 | 测试 | Code Review | 总计 |
|-----|------|------|-----------|------|
| P0 Task 1-4 | 6天 | 2天 | 1天 | **9天** |
| P1 Task 5-7 | 3天 | 1天 | 1天 | **5天** |
| 架构重组 | 10天 | 3天 | 2天 | **15天** |
| 测试补充 | 8天 | 2天 | 1天 | **11天** |
| **总计** | **27天** | **8天** | **5天** | **40天** |

*基于3人团队，能达成并行工作*

---

## ✅ 完成指标

当所有改进完成时，应该看到：

- ✅ 告警可靠性到达 99%+
- ✅ 测试覆盖率 >80%
- ✅ 无内存泄漏迹象 (8小时运行不超500MB)
- ✅ 扫描耗时 <15秒
- ✅ 架构评分 8.5/10+

---

**开始改进！** 👇
从 `IMPLEMENTATION_GUIDE.md` 的任务1开始 🚀
