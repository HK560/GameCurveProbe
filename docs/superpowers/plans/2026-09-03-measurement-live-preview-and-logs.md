# 曲线测定页实时日志、进度与画面预览 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为曲线测定页面（`MeasurementStep.vue`）提供实时 30 FPS 画面视口（带 ROI 叠加框）、终端风格的实时测定诊断日志控制台，以及测定过程中动态追加行的实时点位数据表。

**Architecture:** 
- 后端在 `MeasurementRunner` 执行的各生命周期节点（开始、推杆稳定等待、光流采样、失稳复测、单点测定完成、全部完成）发布带有 `phase` 的细粒度进度字典，通过 WebSocket `job_progress` 管道流式传输；
- 画面直接复用底层的 `/api/ws/preview` 二进制 JPEG 流（`sessionStore.livePreviewUrl`），并在前端以纯 CSS 响应式叠加 ROI 框；
- 前端 `sessionStore` 监听事件维护日志流与动态点位列表，`MeasurementStep.vue` 呈现左侧实时监控、右侧进度/终端日志、下方实时数据表的双栏响应式布局。

**Tech Stack:** 
- Python 3.13, FastAPI, WebSocket, OpenCV
- Vue 3, TypeScript, Vite, Pinia, TailwindCSS, Lucide-Vue-Next

## Global Constraints

- 保持后端 `publish` 的向后兼容性（继续提供 `current_point`, `total_points`, `input_value`）；
- 单一活动硬件任务互斥与安全回中保证不变；
- 终端日志最大条数限制为 500 条（FIFO 淘汰）；
- 前端 TypeScript 严格无编译错误，`npm run build` 成功。

---

### Task 1: Backend: `MeasurementRunner` 结构化多阶段生命周期事件发布

**Files:**
- Modify: `src/gamecurveprobe/services/measurement_runner.py:50-115`
- Modify: `tests/test_measurement_runner.py`

**Interfaces:**
- Consumes: `MeasurementRunner.run(config, cancel_event, publish, roi, noise)`
- Produces: `publish({"phase": str, "current_point": int, "total_points": int, "input_value": float, ...})` 具有 `stage_start`, `point_settle`, `point_sampling`, `point_retry`, `point_done`, `stage_completed` 事件。

- [ ] **Step 1: 编写测试用例覆盖生命周期事件发布**

在 `tests/test_measurement_runner.py` 中添加测试：
```python
def test_measurement_runner_publishes_lifecycle_phases():
    # Arrange mock controller, capture, estimator, sampler
    # Verify events contains 'stage_start', 'point_settle', 'point_sampling', 'point_done', 'stage_completed'
```

- [ ] **Step 2: 运行测试确认当前未发布这些 phase**

Run: `uv run pytest tests/test_measurement_runner.py -k test_measurement_runner_publishes_lifecycle_phases`
Expected: FAIL

- [ ] **Step 3: 修改 `MeasurementRunner` 发布各阶段事件**

在 `src/gamecurveprobe/services/measurement_runner.py` 中：
```python
# 1. 测定开始
publish({
    "phase": "stage_start",
    "total_points": len(values),
    "current_point": 0,
    "input_value": 0.0,
    "range_mode": config.range_mode,
    "settle_ms": config.settle_ms,
    "sample_ms": config.sample_ms,
    "message": f"稳态测定启动: 共 {len(values)} 个采样点 (Settle: {config.settle_ms}ms, Sample: {config.sample_ms}ms)",
})

# 循环中每次推杆：
publish({
    "phase": "point_settle",
    "current_point": index,
    "total_points": len(values),
    "input_value": input_value,
    "message": f"采样点 [{index}/{len(values)}] 右摇杆推杆至 {(input_value * 100):.1f}%，等待视口稳定 ({config.settle_ms}ms)...",
})

# Settle 结束后进入采样：
publish({
    "phase": "point_sampling",
    "current_point": index,
    "total_points": len(values),
    "input_value": input_value,
    "message": f"采样点 [{index}/{len(values)}] 正在进行视觉光流跟踪采样 ({config.sample_ms}ms)...",
})

# 若重试：
publish({
    "phase": "point_retry",
    "current_point": index,
    "total_points": len(values),
    "input_value": input_value,
    "message": f"采样点 [{index}/{len(values)}] 稳定性得分较低 ({sample.stability_score * 100:.1f}%)，正在触发第 2 轮复测...",
})

# 单点完成后：
publish({
    "phase": "point_done",
    "current_point": index,
    "total_points": len(values),
    "input_value": input_value,
    "point": {
        "input": point.input,
        "velocity_px_s": point.velocity_px_s,
        "normalized_speed": None,
        "stability": point.stability,
        "valid": point.valid,
        "attempts": point.attempts,
    },
    "message": f"采样点 [{index}/{len(values)}] 测定完成: 速度 {point.velocity_px_s} px/s, 稳定性 {point.stability * 100:.1f}%, 判定: {'有效' if point.valid else '无效'}",
})

# 全部完成后：
publish({
    "phase": "stage_completed",
    "current_point": len(values),
    "total_points": len(values),
    "input_value": values[-1] if values else 1.0,
    "valid_points": valid_count,
    "message": f"全测定流程完成: 共 {len(values)} 点，有效点 {valid_count} 个",
})
```

- [ ] **Step 4: 运行测试确认通过**

Run: `uv run pytest tests/test_measurement_runner.py`
Expected: PASS

- [ ] **Step 5: 提交更改**

```bash
git add src/gamecurveprobe/services/measurement_runner.py tests/test_measurement_runner.py
git commit -m "feat: publish structured lifecycle events during measurement"
```

---

### Task 2: Frontend Types & Store: 扩展 `JobProgress` 契约与 `sessionStore` 状态

**Files:**
- Modify: `webui/src/types/api.ts`
- Modify: `webui/src/stores/session.ts`

**Interfaces:**
- `JobProgress`: 增加可选字段 `phase?: string`, `message?: string`, `point?: MeasurementPoint`, `range_mode?: string`, `settle_ms?: number`, `sample_ms?: number`, `valid_points?: number`
- `LogEntry`: `{ id: string; timestamp: string; level: 'info' | 'action' | 'settle' | 'sampling' | 'warn' | 'success' | 'error'; message: string }`
- `sessionStore`: 暴露 `measurementLogs: Ref<LogEntry[]>`, `livePoints: Ref<MeasurementPoint[]>`, `addLog(level, msg)`, `clearLogs()`

- [ ] **Step 1: 在 `webui/src/types/api.ts` 中扩展类型**

添加 `LogEntry` 接口并扩展 `JobProgress`。

- [ ] **Step 2: 在 `webui/src/stores/session.ts` 中管理日志与中间数据**

在 `sessionStore` 中增加：
- `measurementLogs = ref<LogEntry[]>([])`
- `livePoints = ref<MeasurementPoint[]>([])`
- 在 `handleWsEvent` 中，当收到 `job_progress` 且有 `payload.data.message` 时，自动生成 `LogEntry` 追加到 `measurementLogs`（限制 500 条）；若 `payload.data.phase === 'point_done'` 且有 `payload.data.point`，追加到 `livePoints`；
- 当收到 `job_status` (state: running) 或启动新任务时，清空 `livePoints` 并插入启动日志；
- 当收到 `job_canceled` 或 `job_failed` 时，追加对应告警/错误日志。

- [ ] **Step 3: 运行 TypeScript 编译检查**

Run: `npm --prefix webui run build`
Expected: 编译通过无错误

- [ ] **Step 4: 提交更改**

```bash
git add webui/src/types/api.ts webui/src/stores/session.ts
git commit -m "feat: add measurement logs and live points tracking in session store"
```

---

### Task 3: Frontend Component: 构建实时画面视口与 ROI 叠加框

**Files:**
- Modify: `webui/src/components/MeasurementStep.vue`

**Interfaces:**
- 消费: `sessionStore.livePreviewUrl`, `sessionStore.capture`, `sessionStore.roi`, `progressData`
- 产生: 实时视频监控画面，根据原画面宽高与当前容器宽高计算出 ROI 坐标百分比，用高亮边框和四角标记叠加显示。

- [ ] **Step 1: 构建左侧监控卡片模板与 ROI 坐标百分比计算**

在 `MeasurementStep.vue` 中定义计算属性：
```typescript
const roiBoxStyle = computed(() => {
  if (!sessionStore.roi || !sessionStore.capture) return null
  const { x, y, width, height } = sessionStore.roi
  const capW = sessionStore.capture.width || 1920
  const capH = sessionStore.capture.height || 1080
  return {
    left: `${(x / capW) * 100}%`,
    top: `${(y / capH) * 100}%`,
    width: `${(width / capW) * 100}%`,
    height: `${(height / capH) * 100}%`,
  }
})
```

- [ ] **Step 2: 渲染视频流与叠加层**

在左侧卡片中展示 `img :src="sessionStore.livePreviewUrl"`，并覆盖绝对定位的 `div :style="roiBoxStyle"`，附带高亮边框、发光效果及追踪标签。

- [ ] **Step 3: 运行前端构建验证**

Run: `npm --prefix webui run build`
Expected: PASS

- [ ] **Step 4: 提交代码**

```bash
git add webui/src/components/MeasurementStep.vue
git commit -m "feat: add live camera viewport with ROI overlay to measurement step"
```

---

### Task 4: Frontend Component: 构建终端风格实时日志窗口与自动滚屏

**Files:**
- Modify: `webui/src/components/MeasurementStep.vue`

**Interfaces:**
- 消费: `sessionStore.measurementLogs`, `sessionStore.clearLogs`
- 特性: 终端外观 (`font-mono text-xs bg-slate-950`)、时间戳、彩色 Level 徽标、自动滚动到最新日志（带用户滚动暂停检测与一键恢复按钮）、一键复制日志文本。

- [ ] **Step 1: 实现自动滚动与复制控制**

```typescript
const logContainerRef = ref<HTMLElement | null>(null)
const autoScroll = ref(true)
const copySuccess = ref(false)

function onLogScroll() {
  if (!logContainerRef.value) return
  const { scrollTop, scrollHeight, clientHeight } = logContainerRef.value
  // 用户手动往上滚超过 30px 则暂停自动滚屏
  autoScroll.value = scrollHeight - (scrollTop + clientHeight) < 30
}

watch(
  () => sessionStore.measurementLogs.length,
  async () => {
    if (autoScroll.value) {
      await nextTick()
      if (logContainerRef.value) {
        logContainerRef.value.scrollTop = logContainerRef.value.scrollHeight
      }
    }
  }
)
```

- [ ] **Step 2: 编写终端外观模板与级别彩色标签**

在右侧下半部分构建 Terminal UI：
- `[INFO]` 灰青色
- `[ACTION]` 靛紫色
- `[SETTLE]` 琥珀色
- `[SAMPLING]` 浅蓝色
- `[WARN]` 橙黄色
- `[RESULT]` 翡翠绿
- `[ERROR]` 玫瑰红

- [ ] **Step 3: 运行前端构建验证**

Run: `npm --prefix webui run build`
Expected: PASS

- [ ] **Step 4: 提交代码**

```bash
git add webui/src/components/MeasurementStep.vue
git commit -m "feat: add terminal-style real-time log window in measurement step"
```

---

### Task 5: Frontend Component: 构建实时累积动态采样点表格

**Files:**
- Modify: `webui/src/components/MeasurementStep.vue`

**Interfaces:**
- 消费: `sessionStore.livePoints` (测定进行中) 与 `sessionStore.lastResult.points` (测定完成/已有数据)
- 特性: 测定进行中表格展示 `displayPoints`，每增加一个点平滑追加新行，高亮最新一行。

- [ ] **Step 1: 整合 `displayPoints` 计算属性**

```typescript
const displayPoints = computed(() => {
  if (isRunning.value && sessionStore.livePoints.length > 0) {
    return sessionStore.livePoints
  }
  return lastResult.value?.points || sessionStore.livePoints
})
```

- [ ] **Step 2: 渲染动态表格**

支持测定中实时更新：点序号、推杆百分比、测量速度 (`px/s`)、稳定性得分、有效性徽标。

- [ ] **Step 3: 运行构建与单元测试**

Run: `npm --prefix webui run build`
Run: `uv run pytest`
Expected: 全部 PASS

- [ ] **Step 4: 提交代码**

```bash
git add webui/src/components/MeasurementStep.vue
git commit -m "feat: enable real-time incremental data table in measurement step"
```

---

### Task 6: 联调验证与产物交付

**Files:**
- Test verification: Python suite + WebUI build + Stub server live test

- [ ] **Step 1: 运行全量 Python 测试套件**

Run: `uv run pytest`
Expected: 100% PASS

- [ ] **Step 2: 运行前端生产打包构建**

Run: `npm --prefix webui run build`
Expected: 0 warnings, 0 errors

- [ ] **Step 3: 启动测试桩验证**

Run stub server or verify app endpoints:
验证 `/api/ws/events` 与 `/api/ws/preview` 正常分发 `phase` 事件。

- [ ] **Step 4: 提交最终文档与总结**
