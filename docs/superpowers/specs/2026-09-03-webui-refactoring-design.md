# GameCurveProbe WebUI 全面重构设计规范

- **创建/修订日期**：2026-09-03
- **状态**：Approved by User
- **目标版本**：2.0
- **适用平台**：Windows 10/11，本机单用户

## 1. 目标与非目标

### 1.1 目标

将现有 PySide6 客户端一次性重构为 FastAPI + WebSocket + Vue 3 WebUI。最终版本必须支持：

1. 选择并捕获目标游戏窗口；
2. 在实时预览上选择 ROI，获得纹理和跟踪质量诊断；
3. 采集画面底噪，通过人工观察辅助标定内外死区；
4. 在有效行程或全行程内执行可取消的稳态响应测量；
5. 展示 `px/s` 与归一化响应曲线，给出有置信度约束的曲线分类；
6. 下载版本化 JSON、CSV，复制 TSV；
7. 导入本版本 JSON 进行离线查看和比较；
8. 在正常结束、取消、异常和进程退出时保证虚拟手柄回中。

### 1.2 非目标

- 局域网或公网访问、多用户、多会话并发；
- 任务历史数据库、云同步、账号或遥测；
- Y 轴及负方向的正式测量；
- 自动识别游戏内外死区或自动修改游戏设置；
- 360° 标定、`deg/s` 和角速度换算；
- 动态响应测量；
- 系统托盘、浏览器关闭即退出；
- 旧会话 JSON 的自动迁移。

## 2. 现状与迁移决策

当前 `main_window.py` 混合界面、数据绑定、线程、Win32 生命周期与绘图；旧 IPC HTTP 接口并非面向 WebUI 设计；现有稳态 runner 同步阻塞，取消只改变会话状态，不能可靠中断硬件循环；数据模型仍包含 yaw360、动态响应和角速度字段。

本次采用**一次性全面切换**，最终产物不提供双架构或兼容模式。实施时遵循“先建新链路并验证，再删除旧链路”，但所有工作在同一重构版本完成，不发布中间兼容版本。

最终删除：

- `src/gamecurveprobe/gui/`；
- `src/gamecurveprobe/services/http_server.py`；
- `src/gamecurveprobe/services/yaw360_calibration_runner.py`；
- 动态响应占位代码；
- PySide6 依赖、旧 GUI/IPC/yaw360 测试；
- `yaw360_timeout_ms`、`yaw_deg_per_px`、`deg_per_sec` 等字段；
- `--ipc-only` 及相关文档入口。

窗口枚举、底噪、稳态采样、回中和打包等仍有价值的旧行为，必须先由新测试覆盖。

## 3. 技术栈与总体架构

### 3.1 技术栈

- Python >= 3.13；
- FastAPI、Uvicorn、Pydantic；
- OpenCV、NumPy；
- WGC 主捕获后端和 DXGI 备用后端；
- vgamepad 与 ViGEmBus；
- Vue 3、TypeScript、Vite、Pinia；
- TailwindCSS v4、ECharts、Lucide-Vue-Next；
- PyInstaller。

WGC 的目标是降低黑屏概率，不承诺“绝不黑屏”或固定达到 120 FPS。具体 Python 库必须在开发初期验证 Python 3.13、目标 Windows 版本和 PyInstaller 支持；允许在不改变 `CaptureBackend` 契约的前提下替换实现库。

### 3.2 运行架构

```text
Vue SPA
  │ REST：配置、命令、查询、导入导出
  │ WebSocket：预览、运动、进度、状态
  ▼
FastAPI
  ├─ AppContext              应用资源所有权与生命周期
  ├─ SessionService          唯一活动会话、配置与结果
  ├─ JobManager              唯一活动任务、取消与进度
  ├─ CaptureService          捕获选择、帧分发与健康监测
  ├─ ControllerService       vgamepad 独占访问与强制回中
  ├─ DeadzoneProbeService    人工试推及租约
  ├─ MeasurementRunner       与 Web 框架无关的测量流程
  ├─ RoiAnalyzer             ROI 质量分析
  └─ ExportService           JSON、CSV 与导入验证
```

核心约束：

- Uvicorn 仅绑定 loopback；产品 UI 不提供绑定 `0.0.0.0` 的选项；
- 单进程、单活动会话、同一时间最多一个硬件任务；
- REST 是所有硬件写操作的唯一入口，WebSocket 只推送事件；
- OpenCV、抓屏和手柄等阻塞工作在后台线程运行，不阻塞事件循环；
- 后端服务不依赖 FastAPI 或 Vue；API 使用 Pydantic DTO，不暴露内部 dataclass；
- FastAPI lifespan 创建和销毁 `AppContext`；所有退出路径执行取消、回中和捕获释放。

### 3.3 建议目录

```text
src/gamecurveprobe/
├── app.py
├── models.py
├── events.py
├── errors.py
├── api/{server,routes,websocket,schemas}.py
├── backends/
│   ├── capture/{base,wgc_backend,dxcam_backend,stub}.py
│   └── controller/{base,vgamepad_backend,stub}.py
├── services/
│   ├── session_service.py
│   ├── job_manager.py
│   ├── capture_service.py
│   ├── controller_service.py
│   ├── deadzone_probe_service.py
│   ├── measurement_runner.py
│   ├── idle_noise_runner.py
│   └── export_service.py
├── vision/{motion_estimator,roi_analyzer}.py
└── web/                    Vite 生产构建产物

frontend/
├── src/{api,assets,components,stores,types}/
├── package.json
└── vite.config.ts
```

## 4. 领域模型、资源所有权与状态机

应用启动时创建唯一 `session_id`。底噪标定和稳态测量每次创建新的 `job_id`；本版本只保留当前任务和最近一次完整结果，不持久化历史任务。

```text
会话：unconfigured → ready → measuring → completed
          │           │         │           │
          └───────────┴─────────┴──────────→ error

任务：queued → running → completed
                 ├→ canceling → canceled
                 └→ failed

捕获：detached → attaching → attached → degraded
```

状态转换由领域服务执行，API handler 不直接修改状态。任务进入终态后不可复用。

会话的 `error` 表示当前配置或资源需要用户干预，不代表进程不可恢复；重新绑定捕获、修正配置或完成一次新任务后可回到 `ready`。同一时间只保留一个 `active_job`，终态任务作为 `last_job` 快照保留到下一任务创建。

资源互斥规则：

- 预览可以持续使用捕获设备；
- 测量时 `CaptureService` 将帧供给测量器，并向预览发送限速副本；
- 死区试推与稳态测量互斥；
- 底噪只占用捕获资源，但不得与稳态测量并行；
- 冲突请求返回 `409 RESOURCE_BUSY`，不得覆盖正在运行的任务；
- 取消先进入 `canceling`。只有 runner 退出且完成 `neutral()` 后才能进入 `canceled`。

`ControllerService` 串行化所有手柄写入。取消时先设置取消令牌，再通过同一串行通道提交高优先级 `neutral()`；runner 在任何后续写入前检查令牌，因此 API 线程不会与测量线程并发写手柄。

## 5. REST API

所有 API 均位于 `/api`。除健康检查和 SPA 静态资源外，REST 与 WebSocket 都要求启动时生成的随机令牌。

| 方法与路径 | 说明 | 主要响应 |
|---|---|---|
| `GET /api/health` | 服务和依赖状态 | 服务、控制器、WGC、DXGI、前端资源状态 |
| `GET /api/session` | 当前会话快照 | 会话、资源状态、最近任务摘要 |
| `GET /api/windows` | 可捕获窗口 | 稳定的窗口 DTO 列表 |
| `POST /api/capture/attach` | 绑定窗口 | 实际后端、帧尺寸、诊断信息 |
| `POST /api/capture/detach` | 释放捕获 | 捕获状态 |
| `PUT /api/session/roi` | 设置并评价 ROI | ROI、分数、指标与建议代码 |
| `GET /api/session/config` | 读取配置 | 配置、约束和预设 |
| `PUT /api/session/config` | 原子更新配置 | 校验后的完整配置 |
| `PUT /api/session/deadzones` | 更新双死区 | 双死区和约束 |
| `POST /api/deadzone/probe` | 启动试推 | 租约和当前输出 |
| `PUT /api/deadzone/probe` | 设置绝对输出 | 当前输出和租约截止时间 |
| `DELETE /api/deadzone/probe` | 结束试推并回中 | 非活动状态 |
| `POST /api/jobs/idle-noise` | 创建底噪任务 | `202`、job 快照 |
| `POST /api/jobs/measurement` | 创建测量任务 | `202`、job 快照 |
| `GET /api/jobs/{job_id}` | 查询任务 | job 快照 |
| `DELETE /api/jobs/{job_id}` | 请求取消 | `202`、`canceling` |
| `GET /api/result` | 最近完整结果 | 版本化结果 DTO |
| `GET /api/result/export?format=csv` | 下载 CSV | 附件响应 |
| `GET /api/result/export?format=json` | 下载 JSON | 附件响应 |
| `POST /api/result/import` | 导入结果供离线分析 | 经校验的结果 DTO |

`POST /api/capture/attach` 支持 `backend: auto | wgc | dxcam`。`auto` 允许健康检查失败后回退；用户强制指定后端时不自动替换，以保留可诊断性。

关键请求 DTO 固定如下：

- 捕获绑定：`{window_id: int, backend: "auto" | "wgc" | "dxcam", target_fps: 30..240}`；
- ROI：`{x: int, y: int, width: int, height: int}`，均以原始帧像素表示；
- 会话配置：`{preset, point_count, repeats, settle_ms, sample_ms, range_mode}`；
- 双死区：`{inner_deadzone: float, outer_deadzone: float}`；
- 启动试推：`{direction: "x_positive", initial_output: float, step: float}`；
- 更新试推：`{output: float}`，每次成功更新同时续租；即使输出值未变化也可用于续租；
- 创建测量任务不复制配置，请求体只含 `{}`；JobManager 在接收请求时原子快照当前配置；
- 导入结果使用 `multipart/form-data` 单文件字段 `file`，最大 5 MiB。

统一错误格式：

```json
{"error":{"code":"RESOURCE_BUSY","message":"A measurement is already running.","details":{}}}
```

状态码约定：参数语义错误为 `400`，不存在为 `404`，状态冲突为 `409`，DTO 校验为 `422`，未知故障为 `500`，硬件不可用为 `503`。

客户端不能提交导出目录。导出使用下载响应，避免任意文件写入。TSV 由前端从结果 DTO 生成。窗口 API 使用独立 DTO：`{id, title, pid, process_name, width, height}`。

## 6. WebSocket 协议

连接地址为 `/ws/events?session_id=...&token=...`。它只推送事件，不接收改变硬件状态的命令。

```json
{"seq":42,"type":"job.progress","job_id":"job-id","timestamp":"2026-09-03T12:00:00Z","payload":{}}
```

事件类型：`capture.status`、`motion.sample`、`roi.quality`、`job.state`、`job.progress`、`session.result`、`system.warning`，以及二进制 JPEG `preview.frame`。

二进制帧采用固定信封：4 字节 ASCII magic `GCPF`、1 字节协议版本、2 字节大端 JSON 头长度、UTF-8 JSON 头、剩余全部为 JPEG。JSON 头包含 `seq`、`frame_id`、`monotonic_ns`、`width`、`height` 和 `jpeg_length`；长度不一致时客户端丢弃该帧。

可靠性规则：

- 状态和进度事件使用有界队列；
- 每个连接的预览队列容量为 1，新帧覆盖旧帧，慢客户端不能阻塞捕获；
- 预览默认上限 30 FPS、JPEG quality 75，测量时可降至 15 FPS；
- WebSocket 断开不取消后台任务；
- 重连后先通过 REST 恢复快照，再接收新事件；
- `seq` 用于检测漏事件，不提供历史重放；
- 页面断开后，活动试推由租约看门狗回中。

## 7. 捕获、帧与 ROI

### 7.1 捕获契约

```python
attach(window_id, target_fps) -> CaptureInfo
read(timeout_ms) -> Frame | None
health() -> CaptureHealth
close() -> None
```

`Frame` 统一为 BGR `uint8`、窗口客户区坐标、单调时钟时间戳和递增帧号。ROI 始终使用捕获帧坐标，不使用屏幕绝对坐标。

`auto` 先尝试 WGC，在 2 秒观察窗内获得至少 10 个尺寸一致的连续帧且重复率低于 80% 后认定可工作，否则尝试 DXGI。全黑诊断使用连续 10 帧亮度均值和标准差均不高于 1 的保守规则；该规则触发警告和自动回退，但用户仍可强制选择后端以处理本身就是黑暗场景的游戏。诊断报告请求 FPS、实际 FPS、丢帧、重复帧、亮度异常和最终后端。

窗口最小化、关闭、尺寸变化和设备丢失产生 `capture.status`。尺寸变化时旧 ROI 失效；若正在测量，任务失败并安全回中，不静默缩放 ROI。

### 7.2 ROI 质量

ROI 评分使用灰度梯度、角点数、边缘方向分布和短时跟踪成功率，返回：

- `score`：0 到 100；
- `level`：`poor | fair | good | excellent`；
- 指标明细；
- 稳定的建议代码及本地化文案键。

越界或宽、高任一小于 32 像素的 ROI 拒绝保存。`poor` 只警告；开始测量时重新检查，连续 10 帧中位跟踪点少于 8 或中位置信度低于 0.35 时拒绝任务。这些阈值作为后端常量集中管理，前端从配置约束 DTO 读取，不得重复硬编码。Canvas 必须保留显示坐标到原始帧坐标的确定性映射，并为该转换编写单元测试。

## 8. 双死区人工试推

`inner_deadzone` 和 `outer_deadzone` 是测量区间标记，不会修改游戏设置。本版本使用人工观察、工具辅助，不宣称自动识别死区。

- 内死区：从低值增加，用户观察到游戏开始稳定转动后确认；
- 外死区：从高值降低，用户观察到转速开始下降后，将此前仍保持满速的点确认为外死区；
- 首版只支持右摇杆 X 正方向；
- 前端通过绝对输出值更新，避免重试请求导致 `delta` 累积；
- 默认步长 `0.005`，另提供 `0.001` 和 `0.01`；
- 始终校验 `0 ≤ inner < outer ≤ 1`；
- 进入下一阶段前必须退出试推并确认回中。

试推租约默认 2 秒，前端每 500ms 续租。续租中断、页面断开、服务退出或异常都会使租约失效并触发回中。服务端不能依赖浏览器发送清理命令。

## 9. 底噪与稳态测量

底噪默认采样 1.2 秒，使用稳健分位数计算 X/Y 噪声阈值，同时保存有效帧、置信度和分布统计。测量值扣除对应阈值，结果不得小于零。

稳态流程：

```text
校验配置与资源
→ 获取控制器独占权
→ 每点：回中 → 等待 → 施加输入 → settle → sample
→ 质量不足最多重试一次
→ 多次结果取中位数
→ 最终回中并释放资源
→ 生成结果与分析
```

runner 接收 `threading.Event` 取消令牌。所有等待拆成可中断短等待，采样循环也检查取消令牌，不允许用一次长 `sleep()` 阻止取消。

- `active_range`：在 `[inner_deadzone, outer_deadzone]` 等距排点；
- `full`：在 `[0, 1]` 排点并强制包含 inner/outer，去重后实际点数可能略高于预设。

| 预设 | 点数 | 重复 | Settle | Sample |
|---|---:|---:|---:|---:|
| 快速 | 9 | 1 | 250ms | 500ms |
| 标准 | 17 | 2 | 300ms | 700ms |
| 高精 | 33 | 2 | 500ms | 1000ms |

预计时长根据真实配置、回中等待和重试预算动态计算。单点失败仍保留该点，但标记 `valid=false`，不得用 `0 px/s` 冒充有效测量。当有效点少于 5 个或少于计划点数的 60% 时，任务以 `MEASUREMENT_QUALITY_LOW` 失败并保留诊断结果。

## 10. 结果、分析与导入导出

正式结果只使用 `px/s` 和归一化速度：

```json
{
  "schema_version": 1,
  "session_id": "session-id",
  "captured_at": "2026-09-03T12:00:00Z",
  "environment": {
    "window_title": "Game",
    "capture_backend": "wgc",
    "requested_fps": 120,
    "actual_fps": 87.4,
    "frame_size": [1920, 1080],
    "roi": {"x": 0, "y": 0, "width": 300, "height": 200}
  },
  "config": {"inner_deadzone": 0.05,"outer_deadzone": 0.92,"range_mode": "active_range"},
  "points": [{
    "input": 0.05,
    "velocity_px_s": 0.0,
    "normalized_speed": 0.0,
    "stability": 0.91,
    "valid": true,
    "attempts": 2
  }],
  "analysis": {"curve_type": "linear","confidence": 0.82,"metrics": {}},
  "warnings": []
}
```

曲线类型为 `linear | exponential | s_curve | undetermined`。分类对归一化有效点分别拟合线性、幂函数和单调 logistic 候选，使用归一化 RMSE 评分。最佳模型必须满足 NRMSE ≤ 0.12，且比第二名至少低 0.02；否则返回 `undetermined`。`confidence` 定义为截断至 `[0,1]` 的 `1 - NRMSE`。拟合失败或有效点少于 5 个也返回 `undetermined`。算法和阈值作为独立纯函数与集中常量实现并测试。

CSV 固定列：

```text
Input,Velocity_px_s,Normalized_Ratio,Stability,Valid,Attempts
```

JSON 是版本化结果包。导入只进入离线分析模式，不能恢复硬件状态或直接启动测量。只接受 `schema_version=1`；其他版本返回 `UNSUPPORTED_SCHEMA_VERSION`。

## 11. 前端四阶段向导

Pinia 只保存界面快照与连接状态，后端是会话、任务和结果的唯一事实来源。刷新后先读取 REST 快照，再连接 WebSocket。

1. **捕获与 ROI**：选择窗口和 `auto/WGC/DXGI`；展示实际后端、FPS、尺寸、丢帧和健康状态；Canvas 拖选 ROI；使用 `ResizeObserver` 维护坐标映射。
2. **环境与死区**：双死区滑块、精确输入、人工试推、步长和租约状态；展示底噪任务进度、有效帧和阈值。
3. **稳态测量**：预设、范围、动态预计时间；修改高级参数后显示“自定义”；运行中锁定配置和窗口，只开放取消；展示进度、稳定性、波形和限速预览。
4. **分析与导出**：ECharts 显示有效/无效点、死区线和拟合结果；下载 CSV/JSON、复制 TSV。导入后进入明确标识的离线分析模式；前端内存中最多保留一个导入结果，可将它与最近一次实测结果叠加比较。导入不会覆盖后端最近实测结果，刷新页面后导入结果消失。

## 12. 错误处理与安全不变量

领域错误代码：

- `WINDOW_GONE`：刷新窗口并返回第一阶段；
- `CAPTURE_BLACK_FRAME` / `CAPTURE_STALLED`：提示切换后端，`auto` 可回退一次；
- `ROI_INVALIDATED`：要求重新选择 ROI；
- `CONTROLLER_UNAVAILABLE`：提供 ViGEmBus/vgamepad 指引；
- `RESOURCE_BUSY`：展示占用任务；
- `MEASUREMENT_QUALITY_LOW`：保留诊断并允许重测；
- `UNSUPPORTED_SCHEMA_VERSION`：拒绝导入并说明版本；
- `INTERNAL_ERROR`：向用户显示短错误码，堆栈只写本地日志。

发生任何错误后必须满足：手柄已回中或服务持续重试并报告致命状态；试推租约失效；任务终态可查询；捕获可重连或明确 `detached`；API 不泄漏堆栈。

安全要求：

- 仅监听 loopback；
- 启动时生成至少 128 bit 随机令牌。自动打开 URL 将令牌放在 fragment 中，SPA 读取后从地址栏移除并仅保存在内存；REST 使用 `Authorization: Bearer`，WebSocket 因浏览器 API 限制使用查询参数；
- REST 与 WebSocket 验证令牌和 Origin，不启用宽泛 CORS；
- 限制请求体、JSON 导入、ROI、帧尺寸、JPEG 和事件队列大小；
- 不接受客户端文件路径；
- 端口冲突时选择随机空闲端口，不终止其他进程。

## 13. 启动、关闭与打包

`app.py` 支持 `--port`、`--no-browser` 和日志参数。若保留 `--host`，只接受 loopback 地址。监听成功后才打开浏览器。

浏览器关闭不代表后端退出。进程退出时设置全局取消令牌，最多等待任务 3 秒，随后无论任务线程状态如何都通过 `ControllerService` 尝试回中并断开手柄，再关闭捕获和事件分发。若硬件调用本身无法在 3 秒内返回，记录致命错误并继续进程退出；该限制和行为必须用阻塞 stub 测试。

```text
npm ci
→ npm run typecheck
→ npm run test
→ npm run build
→ 复制 dist 到 src/gamecurveprobe/web/
→ pytest
→ PyInstaller
→ 启动打包产物执行 smoke test
```

要求：Vite 开发服务器代理 FastAPI；生产环境托管静态文件并对未知非 API 路径回退 `index.html`；wheel 和 PyInstaller 显式包含 `web/`；spec 收集 vgamepad、WGC 和原生 DLL；依赖缺失时友好降级；构建只清理经过解析验证的前端产物目录；README 和用户指南删除旧启动说明。

## 14. 实施阶段与删除门槛

1. 定义 DTO、错误、结果 schema、事件和状态机，以测试冻结契约；
2. 重构无框架核心层，实现可取消 runner 和资源服务；
3. 实现 WGC、统一 DXGI、健康检查、回退和 ROI 坐标；
4. 实现 FastAPI lifespan、REST、WebSocket、安全和静态托管；
5. 用 stub 完成后端垂直链路；
6. 实现 Vue 四阶段闭环，再加入视觉润色和高级图表；
7. 接入真实硬件，验证异常、取消和退出回中；
8. 新链路测试通过后删除旧 GUI、IPC、yaw360、动态占位及依赖；
9. 更新打包、README、用户指南和锁文件；
10. 删除旧代码后重新执行完整测试和纯净 Windows 打包验收。

删除门槛以新能力的测试覆盖为准，不以“新文件已创建”为准。Git 历史承担回退能力，生产代码不保留废弃适配器。

## 15. 测试矩阵

### 15.1 自动化测试

- 单元：DTO、状态机、排点、取消、ROI、噪声、分类、导入导出；
- 服务：stub 下的成功、失败、超时、取消和 cleanup，逐项断言 `neutral()`；
- API：端点、状态码、令牌、Origin、资源冲突、下载和导入限制；
- WebSocket：事件顺序、重连、慢客户端、最新帧覆盖和队列上限；
- 前端：store、坐标转换、向导守卫、错误映射和 TSV；
- E2E：stub 下完成选择窗口、ROI、标定、测量、分析和导出；
- 打包 smoke：静态资源、SPA fallback、捕获模块导入和控制器缺失降级。

### 15.2 Windows 硬件验收

覆盖 WGC/DXGI、双显卡、多显示器、100/125/150% DPI、窗口缩放/最小化/关闭/跨屏、ViGEmBus 缺失、测量中取消、服务退出、设备丢失和纯净 Windows EXE。

### 15.3 性能与稳定性

- 测量期间 FastAPI 事件循环保持响应；
- 预览队列和内存有界；
- 慢客户端不降低捕获或测量速率；
- 连续运行 30 分钟无持续内存增长；
- 记录实际捕获性能，不以 120 FPS 必达作为验收承诺。

## 16. 完成定义

以下条件全部满足才视为完成：

1. 最终 EXE 可启动并自动打开 WebUI；
2. 用户可完成窗口、ROI、底噪、双死区试推、测量、分析和导入导出闭环；
3. 页面刷新或 WebSocket 重连不会丢失任务状态；
4. 取消、异常、关闭路径均有证据证明手柄回中；
5. `auto` 在 WGC 不健康时可尝试 DXGI，并展示诊断；
6. 结果只含 `px/s` 与归一化速度；
7. 不存在任意路径写入、宽泛 CORS、无界帧队列或阻塞事件循环；
8. PySide6、旧 IPC、yaw360、动态占位及引用全部移除；
9. Python、前端、E2E 和 PyInstaller smoke test 全部通过；
10. README 与用户指南准确反映最终行为。
