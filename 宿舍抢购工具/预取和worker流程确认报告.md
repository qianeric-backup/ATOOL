# 预取和worker流程确认报告

## 确认结果

### ✅ 已确认：预取不会调用worker，提前抢不会影响预取

## 详细流程分析

### 1. 完整抢购流程

#### 代码位置: `_dev/grab_dorm.py` 第384-429行

```python
def grab(self, start_ts=None, dry_run=False):
    if dry_run:
        print("[DRY-RUN] 演练模式: 仅登录/查询/校时, 不提交抢购")
        self.sync_time()
        return None
    self.sync_time()
    if start_ts is None:
        if self.open_time is None:
            # 服务器未返回开放时间(buysdt): 提示并稍后自动重新查询, 不视为账号失败
            keys = sorted(self.dorm.keys()) if (self.dorm and isinstance(self.dorm, dict)) else []
            print(f"[WAIT] 服务器未返回开放时间(buysdt); 当前宿舍字段={keys}, 5s 后重新查询...")
            self._stop.wait(5)
            return None
        start_ts = self.open_time
    remain = start_ts - self.local_now()
    if remain > 0:
        print(f"[WAIT] 距离开放还有 {remain:.1f}s, "
              f"提前 {self.ahead_ms}ms 于 {time.strftime('%H:%M:%S', time.localtime(start_ts))} "
              f"(服务器时间) 开始抢购")
        # 方案A: 开放前预取验证码 (deadline = 开放前 2s), 成功后开抢瞬间直接提交
        if self.enable_prefetch:
            prefetch_deadline = start_ts - 2.0
            if remain > 12:
                # 距开放较远: 先睡到开放前 ~10s 再开始预取, 避免缓存码过早
                self._sleep_until(prefetch_deadline - 10.0)
            elif remain > 2:
                pass  # 已在预取窗口内, 直接开始
            self.prefetch_captcha(deadline=prefetch_deadline,
                                  prefer_ai=self.ai_ocr is not None)
        else:
            print("[PREFETCH] 预取已关闭, 开抢后直接现场取码提交")
        # 等待到开放点(按服务器时间), 不提前试探: 提前提交会触发 507 并消耗一次性验证码
        self._sleep_until(start_ts)
    elif remain < -600:
        print(f"[WARN] 开放时间已过 {abs(remain):.0f}s, 继续尝试 (可能已售罄)")

    results = []
    threads = []
    for i in range(self.concurrency):
        t = threading.Thread(target=self.worker, args=(self.did, results),
                             name=f"grab-{i + 1}", daemon=True)
        threads.append(t)
        t.start()
    for t in threads:
        t.join()
    return self.success_info
```

### 2. 流程顺序分析

#### 步骤1: 时间同步
- **代码**: `self.sync_time()`
- **作用**: 校准本地时钟与服务器时钟

#### 步骤2: 等待开放时间
- **代码**: `self._sleep_until(start_ts)`
- **作用**: 等待到开放时间点

#### 步骤3: 预取验证码（开放前2秒）
- **代码**: `self.prefetch_captcha(deadline=prefetch_deadline, prefer_ai=self.ai_ocr is not None)`
- **作用**: 开放前2秒开始预取验证码
- **关键**: 预取阶段**不会启动worker**

#### 步骤4: 启动worker（开放时间到达后）
- **代码**: `threads.append(t)` 和 `t.start()`
- **作用**: 启动worker线程进行抢购
- **关键**: worker在预取完成后才启动

### 3. 预取阶段分析

#### 预取阶段代码: 第404-412行
```python
if self.enable_prefetch:
    prefetch_deadline = start_ts - 2.0
    if remain > 12:
        # 距开放较远: 先睡到开放前 ~10s 再开始预取, 避免缓存码过早
        self._sleep_until(prefetch_deadline - 10.0)
    elif remain > 2:
        pass  # 已在预取窗口内, 直接开始
    self.prefetch_captcha(deadline=prefetch_deadline,
                          prefer_ai=self.ai_ocr is not None)
```

#### 关键发现:
1. **预取时间**: 开放前2秒开始预取
2. **预取方式**: 调用 `prefetch_captcha()` 方法
3. **预取内容**: 只预取验证码，不启动worker
4. **预取结果**: 缓存到 `self.cached_yzm`

### 4. worker启动分析

#### worker启动代码: 第420-428行
```python
results = []
threads = []
for i in range(self.concurrency):
    t = threading.Thread(target=self.worker, args=(self.did, results),
                         name=f"grab-{i + 1}", daemon=True)
    threads.append(t)
    t.start()
for t in threads:
    t.join()
```

#### 关键发现:
1. **启动时间**: 预取完成后才启动worker
2. **启动方式**: 创建多线程并发抢购
3. **worker内容**: 使用预取的验证码或现场取码
4. **不干扰预取**: worker启动时预取已经完成

### 5. 提前抢购分析

#### 提前抢购代码: 第399-416行
```python
remain = start_ts - self.local_now()
if remain > 0:
    print(f"[WAIT] 距离开放还有 {remain:.1f}s, "
          f"提前 {self.ahead_ms}ms 于 {time.strftime('%H:%M:%S', time.localtime(start_ts))} "
          f"(服务器时间) 开始抢购")
    # 方案A: 开放前预取验证码 (deadline = 开放前 2s), 成功后开抢瞬间直接提交
    if self.enable_prefetch:
        prefetch_deadline = start_ts - 2.0
        if remain > 12:
            # 距开放较远: 先睡到开放前 ~10s 再开始预取, 避免缓存码过早
            self._sleep_until(prefetch_deadline - 10.0)
        elif remain > 2:
            pass  # 已在预取窗口内, 直接开始
        self.prefetch_captcha(deadline=prefetch_deadline,
                              prefer_ai=self.ai_ocr is not None)
    else:
        print("[PREFETCH] 预取已关闭, 开抢后直接现场取码提交")
    # 等待到开放点(按服务器时间), 不提前试探: 提前提交会触发 507 并消耗一次性验证码
    self._sleep_until(start_ts)
```

#### 关键发现:
1. **提前量**: `ahead_ms` 参数控制提前多少毫秒开始
2. **预取时机**: 开放前2秒开始预取
3. **不提前提交**: 注释明确说明"不提前试探: 提前提交会触发 507 并消耗一次性验证码"
4. **等待开放**: 预取后等待到开放时间点

## 流程总结

### 1. 预取阶段（开放前2秒）
- **时间**: 开放前2秒开始
- **内容**: 只预取验证码，不启动worker
- **方式**: AI+ddddocr双识别投票
- **结果**: 缓存验证码到 `self.cached_yzm`

### 2. 等待阶段（预取完成后）
- **时间**: 预取完成后到开放时间
- **内容**: 等待开放时间点
- **方式**: `self._sleep_until(start_ts)`
- **关键**: 不提前提交，避免触发507错误

### 3. 抢购阶段（开放时间到达后）
- **时间**: 开放时间到达后
- **内容**: 启动worker线程并发抢购
- **方式**: 使用预取的验证码或现场取码
- **关键**: worker启动时预取已经完成

## 关键问题解答

### 1. 预取会不会调用worker？
**答案: 不会**
- 预取阶段只调用 `prefetch_captcha()` 方法
- 预取完成后才启动worker线程
- 预取和worker是两个独立的阶段

### 2. 提前抢会不会影响预取？
**答案: 不会**
- 提前抢是指提前多少毫秒开始抢购
- 预取是在开放前2秒开始
- 提前抢不会干扰预取过程
- 注释明确说明"不提前试探: 提前提交会触发 507 并消耗一次性验证码"

### 3. 预取和worker的关系？
**答案: 顺序执行**
1. 预取阶段：开放前2秒开始预取验证码
2. 等待阶段：等待开放时间点
3. 抢购阶段：开放时间到达后启动worker

## 建议

### 1. 保持当前流程
- 预取阶段：AI+ddddocr双识别投票
- 等待阶段：等待开放时间点
- 抢购阶段：worker使用预取的验证码

### 2. 优化建议
1. **预取时间**: 可根据网络状况调整预取时间
2. **提前量**: 可根据服务器响应时间调整ahead_ms参数
3. **重试策略**: 可优化worker的重试策略

### 3. 测试验证
在服务器恢复后测试：
1. 预取阶段是否正常工作
2. worker启动是否正常
3. 提前抢是否影响预取

## 附录

### 相关代码位置
1. **grab函数**: `_dev/grab_dorm.py` 第384-429行
2. **prefetch_captcha函数**: `_dev/grab_dorm.py` 第276-307行
3. **worker函数**: `_dev/grab_dorm.py` 第332-381行

### 关键代码行
1. `self.prefetch_captcha(deadline=prefetch_deadline, prefer_ai=self.ai_ocr is not None)` - 预取验证码（第411-412行）
2. `t = threading.Thread(target=self.worker, args=(self.did, results), name=f"grab-{i + 1}", daemon=True)` - 启动worker（第423-424行）
3. `# 等待到开放点(按服务器时间), 不提前试探: 提前提交会触发 507 并消耗一次性验证码` - 注释说明（第415行）

### 确认时间
- **确认时间**: 2026-08-22 17:45:00
- **确认人**: AI助手
- **确认结果**: 预取不会调用worker，提前抢不会影响预取