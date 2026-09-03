# 曲线测定页实时日志、进度与画面预览设计规范

- **创建日期**：2026-09-03
- **状态**：Approved by User
- **目标组件**：`MeasurementStep.vue`、`MeasurementRunner`、WebSocket 事件体系

---

## 1. 背景与目标

在手柄响应曲线测定过程中（步骤 3：曲线测定），系统需要驱动虚拟手柄自动向右推杆，并由视觉算法持续采样画面特征点的位移，最终拟合出曲线。
当前界面缺乏中间过程的直观反馈：用户无法在测定过程中观察到手柄推杆时的游戏画面动态，也没有实时的日志输出了解当前点位的测量状态（如 Settle 等待、采样中、稳定性评分、单点速度计算及是否复测），且表格直到整个任务终态才一次性呈现。

本规范旨在完善该环节的用户体验与调试诊断能力：
1. **画面实时预览**：在测定界面内呈现目标游戏的实时 30 FPS 视频流，并以半透明高亮线框叠加当前 ROI 选区，直观反映游戏视角旋转与算法跟踪情况；
2. **终端风格实时日志**：实时输出包括测定启动、推杆动作、Settle 等待、光流采样、失稳复测、单点计算完成、测定结束及异常中止的完整日志流，支持时间戳、彩色状态标签、自动滚屏与一键复制；
3. **点位数据动态累积表**：测定每完成一个采样点，下方表格实时追加一行并高亮显示最新数据，无需等待全部任务结束。

---

## 2. 总体架构与数据流

```text
[ MeasurementRunner ] ──(publish)──> [ JobManager (job_progress) ]
       │                                     │
       ▼                                     ▼
[ CaptureService ] ──(PreviewFrame)──> [ EventHub ]
       │                                     │
  (30 FPS Jpeg)                              ▼
       │                             WebSocket (/api/ws/events)
       ▼                                     │
WebSocket (/api/ws/preview)                  ▼
       │                            [ sessionStore.ts ]
       │                                     │
       ▼                                     ▼
[ 实时画面视口 + ROI 叠加层 ] <───> [ 终端日志窗口 + 实时数据表 ]
               (MeasurementStep.vue)
```

1. **画面通道**：直接消费既有的 WebSocket `/api/ws/preview` 二进制 JPEG 帧，由 `sessionStore.livePreviewUrl` 响应式绑定。
2. **日志与进度通道**：`MeasurementRunner` 在执行关键生命周期节点时，通过 `publish` 回调向 `JobManager` 发送结构化阶段字典。`JobManager` 通过既有 `job_progress` 事件推送到 WebSocket 客户端。
3. **前端消费与呈现**：`sessionStore` 监听 `job_progress`，派发日志记录与中间点位数组；`MeasurementStep.vue` 实时渲染日志和动态行。

---

## 3. 后端数据契约与生命周期阶段

### 3.1 `job_progress` 数据包扩展规范

`MeasurementRunner` 在运行周期中发布具有 `phase` 字段的事件，保证与旧版字段（`current_point`, `total_points`, `input_value`）严格兼容：

```python
# 1. 测定开始
publish({
    "phase": "stage_start",
    "total_points": len(values),
    "range_mode": config.range_mode,
    "settle_ms": config.settle_ms,
    "sample_ms": config.sample_ms,
    "message": f"稳态测定启动: 共 {len(values)} 个采样点 (Settle: {config.settle_ms}ms, Sample: {config.sample_ms}ms)",
})

# 2. 单点进入稳定等待 (Settle)
publish({
    "phase": "point_settle",
    "current_point": index,
    "total_points": len(values),
    "input_value": input_value,
    "message": f"采样点 [{index}/{len(values)}] 右摇杆推杆至 {(input_value * 100):.1f}%，等待视口稳定 ({config.settle_ms}ms)...",
})

# 3. 单点启动光流采样
publish({
    "phase": "point_sampling",
    "current_point": index,
    "total_points": len(values),
    "input_value": input_value,
    "message": f"采样点 [{index}/{len(values)}] 视口已稳定，正在进行视觉光流跟踪采样 ({config.sample_ms}ms)...",
})

# 4. 单点低稳定性重试 (若触发)
publish({
    "phase": "point_retry",
    "current_point": index,
    "total_points": len(values),
    "input_value": input_value,
    "message": f"采样点 [{index}/{len(values)}] 稳定性得分较低 ({sample.stability_score * 100:.1f}%)，正在触发第 2 轮复测...",
})

# 5. 单点测定完成 (产生点位数据)
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

# 6. 测定全部完成
publish({
    "phase": "stage_completed",
    "valid_points": valid_count,
    "total_points": len(values),
    "message": f"全测定流程顺利完成: 共 {len(values)} 点，有效点 {valid_count} 个，正在生成最终响应曲线...",
})
```

---

## 4. 前端界面设计与交互

### 4.1 布局结构（`MeasurementStep.vue`）

页面划分为三大部分：
1. **参数配置与操作栏（顶栏）**：测定范围模式下拉框、采样点数下拉框、单点时延展示、开始/中止测定按钮。
2. **双栏实时监控区（中栏，12 栅格）**：
   * **左侧（6 列）：实时画面视口（Live Monitor）**
     * 响应式容器，呈现 30 FPS 实时游戏帧；
     * 当 `sessionStore.roi` 存在时，使用计算属性计算出等比例缩放后的 ROI 线框，以半透明靛蓝（Indigo）高亮覆盖在视口上方，四角带有细致瞄准角标；
     * 视口底部状态栏：显示画面就绪状态（`1920×1080 @ 120Hz`）、抓图后端名称及当前摇杆偏转方向动画。
   * **右侧（6 列）：进度卡片与终端日志窗口（Log Terminal）**
     * **任务进度指示器**：圆角微渐变卡片，显示当前进度条、点位（如 `7 / 17 点 (41%)`）、当前推杆百分比，以及阶段状态徽标（Settle、采样中、复测中、回中等）。
     * **终端日志控制台**：
       * 背景：深暗色 Slate-950，等宽字体 `font-mono text-xs`；
       * 顶部工具条：包含控制台标题、当前日志行数、**自动滚屏开关（Auto-scroll）**、**复制日志（Copy）**、**清空日志（Clear）**；
       * 滚动区域：高固定在约 320px，单行包含时间戳（灰色 `[HH:MM:SS]`）、类别徽标（彩色标签）、详细描述文本。
3. **实时累积数据表（底栏）**：
   * 表格字段包含：序号 `#`、输入推杆量、速度 (`px/s`)、归一化比例（全部完成后更新）、稳定性评分、有效性状态；
   * 每收到 `point_done` 阶段事件，自动在表格中追加一行，并对最新行添加柔和的呼吸高亮。

### 4.2 终端日志数据结构（TypeScript）

```typescript
export interface LogEntry {
  id: string
  timestamp: string // "17:42:05"
  level: 'info' | 'action' | 'settle' | 'sampling' | 'warn' | 'success' | 'error'
  message: string
}
```

---

## 5. 异常处理与边缘情况

1. **测定主动取消**：
   * 用户点击“中止当前任务”时，前端日志窗立即追加 `[ACTION] 用户已触发取消操作，等待硬件安全回中...`；
   * 后端通过 `JobCanceled` 捕获后，强制虚拟手柄回中，广播 `job_canceled` 事件，日志记录 `[WARN] 任务已成功中止，摇杆已归位`。
2. **窗口异常中断（最小化或意外退出）**：
   * 后端捕获守护线程检测到窗口最小化或失效时，抛出 `DomainError`；
   * 前端日志显示红色高亮 `[ERROR] 目标游戏窗口已最小化或关闭，测定已停止`，保障用户清晰获知失败原因。
3. **内存与性能保护**：
   * 日志数组维持上限 500 条（超出从头部弹出）；
   * 日志自动滚动使用 `requestAnimationFrame` 防抖节流；
   * ROI 预览叠加框计算使用纯 CSS 绝对定位与百分比转换，零额外 DOM 开销。

---

## 6. 验证计划

1. **后端单元测试**：
   * 在 `tests/test_measurement_runner.py` 中验证 `run()` 调用过程中 `publish` 回调收到的事件时序与各 `phase` 字典结构。
2. **前端类型与构建检查**：
   * 更新 `webui/src/types/api.ts` 中的 `JobProgress` 类型契约；
   * 运行 `npm run build`，确保无类型错误且产物编译通过。
3. **端到端集成验证**：
   * 运行测试桩服务或本地运行 `uv run gamecurveprobe`；
   * 进入步骤 3（曲线测定），点击开始稳态测定；
   * 验证画面预览流畅显示、ROI 高亮框位置无偏、终端日志随测定实时滚屏、单点表格实时增加。
