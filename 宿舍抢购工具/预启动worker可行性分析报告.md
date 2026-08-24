# 预启动worker可行性分析报告

## 可行性分析

### ✅ 结论：预启动worker可行，但需要考虑多个因素

## 详细分析

### 1. 当前worker启动逻辑

#### 代码位置: `_dev/grab_dorm.py` 第420-429行
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
return self.success_info
```

#### 当前流程:
1. **预取验证码**: 开放前2秒开始预取
2. **等待开放**: 等待到开放时间点
3. **启动worker**: 开放时间到达后启动worker线程
4. **worker执行**: 使用预取的验证码或现场取码

### 2. 预启动worker的可行性

#### 2.1 可行性分析

##### 优点:
1. **减少启动延迟**: worker提前启动，减少线程创建和启动时间
2. **提高响应速度**: 开放时间到达后立即提交验证码
3. **竞速优势**: 比其他用户更早提交请求

##### 缺点:
1. **验证码消耗**: 提前提交可能触发507错误，消耗一次性验证码
2. **服务器限制**: 服务器可能拒绝提前提交的请求
3. **会话问题**: 提前启动可能导致会话过期

#### 2.2 技术可行性

##### 代码修改方案:
```python
# 方案1: 预启动worker（开放前1秒启动）
if remain > 1:
    # 预启动worker
    for i in range(self.concurrency):
        t = threading.Thread(target=self.worker, args=(self.did, results),
                             name=f"grab-{i + 1}", daemon=True)
        threads.append(t)
        t.start()
    # 等待到开放时间
    self._sleep_until(start_ts)
else:
    # 正常启动worker
    for i in range(self.concurrency):
        t = threading.Thread(target=self.worker, args=(self.did, results),
                             name=f"grab-{i + 1}", daemon=True)
        threads.append(t)
        t.start()
```

### 3. 预启动worker的风险分析

#### 3.1 507错误风险
- **风险等级**: 高
- **触发条件**: 提前提交验证码
- **后果**: 消耗一次性验证码，需要重新获取

#### 3.2 服务器限制风险
- **风险等级**: 中
- **触发条件**: 服务器拒绝提前请求
- **后果**: 请求被拒绝，需要重试

#### 3.3 会话过期风险
- **风险等级**: 低
- **触发条件**: worker运行时间过长
- **后果**: 会话过期，需要重新登录

### 4. 预启动worker的优化方案

#### 4.1 方案1: 延迟预启动
- **启动时间**: 开放前1秒
- **优点**: 减少507错误风险
- **缺点**: 启动延迟仍然存在

#### 4.2 方案2: 条件预启动
- **启动条件**: 只在预取成功时预启动
- **优点**: 避免验证码浪费
- **缺点**: 需要额外的条件判断

#### 4.3 方案3: 智能预启动
- **启动策略**: 根据网络状况动态调整启动时间
- **优点**: 最优化启动时间
- **缺点**: 实现复杂

### 5. 预启动worker的具体实现

#### 5.1 修改grab函数
```python
def grab(self, start_ts=None, dry_run=False):
    # ... 前面的代码不变 ...
    
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
        
        # 预启动worker（开放前1秒启动）
        if remain > 1:
            print(f"[PRE-START] 预启动worker线程...")
            results = []
            threads = []
            for i in range(self.concurrency):
                t = threading.Thread(target=self.worker, args=(self.did, results),
                                     name=f"grab-{i + 1}", daemon=True)
                threads.append(t)
                t.start()
            # 等待到开放时间
            self._sleep_until(start_ts)
        else:
            # 正常启动worker
            results = []
            threads = []
            for i in range(self.concurrency):
                t = threading.Thread(target=self.worker, args=(self.did, results),
                                     name=f"grab-{i + 1}", daemon=True)
                threads.append(t)
                t.start()
    elif remain < -600:
        print(f"[WARN] 开放时间已过 {abs(remain):.0f}s, 继续尝试 (可能已售罄)")
        # 正常启动worker
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

#### 5.2 修改worker函数
```python
def worker(self, did, results):
    n = 0
    while not self._stop.is_set():
        if self.max_retries is not None and n >= self.max_retries:
            break
        n += 1
        try:
            # 检查是否到达开放时间
            if self.open_time is not None:
                remain = self.open_time - self.local_now()
                if remain > 0:
                    # 还未到开放时间，等待
                    print(f"[WORKER] 等待开放时间，剩余 {remain:.1f}s")
                    self._stop.wait(min(remain, 1.0))
                    continue
            
            # 方案A: 首轮优先用预取缓存码 (0ms 取码), 用后即失效; 失败则现场取码
            if self.cached_yzm is not None:
                yzm = self.cached_yzm
                self.cached_yzm = None   # 一次性: 无论成败都作废, 防止重放
                print(f"[PREFETCH-USE] 第{n}次尝试使用预取验证码 '{yzm}' 直接提交")
                res = self.set_dorm(did, yzm)
                ok = res.get("suc") is True
                detail = res
            else:
                ok, detail = self.one_attempt(did)
            if ok:
                with self._lock:
                    self.success_info = {"worker": threading.current_thread().name,
                                         "attempt": n, "detail": detail}
                self._stop.set()
                print(f"[OK] 第{n}次尝试成功! 宿舍 did={did} {detail}")
                return
            emsg = str(detail.get("emsg", ""))
            if emsg:
                print(f"[RETRY-{n}] {emsg}")
            else:
                print(f"[RETRY-{n}] 未知结果: {detail}")
            # 登录过期/失效 -> 自动重新登录后继续
            if ("登录" in emsg or "过期" in emsg) and emsg != "登录失败: 录取通知书编号或身份证号错误":
                print("[LOGIN] 检测到会话失效, 自动重新登录...")
                try:
                    self.login()
                except Exception as le:
                    print(f"[LOGIN] 重新登录失败: {le}")
        except Exception as e:
            print(f"[RETRY-{n}] 请求异常: {e}")
        # 距开放时间还很远时, 加大间隔; 临近时快速重试
        wait = self.interval_ms / 1000.0
        try:
            if self.open_time is not None:
                remain = self.open_time - self.local_now()
                if remain > 60:
                    wait = min(wait, 5.0)
                elif remain > 5:
                    wait = min(wait, 1.0)
        except Exception:
            pass
        self._stop.wait(wait)
    results.append(n)
```

## 结论

### 1. 可行性结论
- **预启动worker可行**: 技术上可以实现
- **需要考虑风险**: 507错误、服务器限制、会话过期
- **需要优化方案**: 延迟预启动、条件预启动、智能预启动

### 2. 推荐方案
- **方案**: 延迟预启动（开放前1秒启动）
- **优点**: 减少507错误风险，提高响应速度
- **实现**: 修改grab函数和worker函数

### 3. 注意事项
1. **监控服务器响应**: 根据服务器响应调整启动时间
2. **处理507错误**: 实现507错误的自动重试机制
3. **会话管理**: 确保worker运行期间会话不过期

### 4. 测试验证
在服务器恢复后测试：
1. 预启动worker是否正常工作
2. 507错误发生率
3. 整体抢购成功率

## 附录

### 相关代码位置
1. **grab函数**: `_dev/grab_dorm.py` 第384-429行
2. **worker函数**: `_dev/grab_dorm.py` 第332-381行

### 关键代码行
1. `t = threading.Thread(target=self.worker, args=(self.did, results), name=f"grab-{i + 1}", daemon=True)` - 启动worker（第423-424行）
2. `# 等待到开放点(按服务器时间), 不提前试探: 提前提交会触发 507 并消耗一次性验证码` - 注释说明（第415行）

### 确认时间
- **确认时间**: 2026-08-22 17:55:00
- **确认人**: AI助手
- **确认结果**: 预启动worker可行，但需要考虑风险和优化方案