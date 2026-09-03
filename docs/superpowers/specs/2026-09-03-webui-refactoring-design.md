# GameCurveProbe WebUI 全面重构设计规范 (Design Spec)

- **创建日期**: 2026-09-03
- **状态**: Approved by User
- **目标**: 将原基于 PySide6 的桌面客户端彻底重构为现代化的 **FastAPI + WebSocket + Vue 3 (TailwindCSS v4 + ECharts)** WebUI 架构；解决抓屏黑屏痛点，精简废弃功能，强化参数指引，优化内外双死区调节与曲线导出体验。

---

## 1. 背景与重构动因

1. **原 GUI 体验不佳且职责过度耦合**：
   - 原界面基于 PySide6 构建，`main_window.py` 接近 900 行，将布局、双向数据绑定、Win32 消息循环、线程生命周期管理和绘图混合在一起；
   - 界面缺乏现代设计感，参数密集且缺乏说明，新手难以理解各参数意义；
   - 存在大量未启用的占位功能（如禁用的动态响应 Dynamic Response）。
2. **抓屏黑屏与兼容性痛点**：
   - 现有抓屏引擎仅依赖 `dxcam`（基于 DXGI 桌面复制）。在双显卡笔记本（Optimus）、跨多显示器、部分独占全屏或缩放场景下，极易发生抓取失败或返回纯黑画面的情况。
3. **冗余功能需清理**：
   - 原项目中为外部脚本预留的独立 IPC HTTP 服务（`http_server.py`）无实际使用场景；
   - 原 360° 旋转比例标定耗时漫长且容易因旋转丢特征点，且核心需求仅为测量手柄推量与视角转速的相对响应趋势，确认彻底剔除。
4. **功能需求增强**：
   - 内死区（Inner Deadzone）与外死区（Outer Deadzone / 饱和阈值）需同时支持双向调节与交互式标定；
   - 稳态测量需支持智能聚焦在 `[内死区, 外死区]` 有效响应区间，提供开箱即用的预设挡位（快速/标准/高精）；
   - 提供更规范的 CSV、游戏预设 JSON 及一键复制表格。

---

## 2. 总体技术架构与技术栈

### 2.1 技术栈选型
- **后端架构**：
  - **语言与运行时**：Python >= 3.13
  - **Web 与通信框架**：`FastAPI` + `uvicorn` + `websockets`
  - **视觉与光流计算**：`OpenCV` (cv2.calcOpticalFlowPyrLK) + `numpy`
  - **抓屏双引擎**：
    - **主引擎**：`windows-capture`（基于微软官方 Windows Graphics Capture / WGC，原生窗口捕获，无黑屏，支持 120+ FPS，Direct3D 11 硬件加速）；
    - **备用引擎**：`dxcam`（DXGI 桌面复制，保留用于特殊环境备选）。
  - **手柄模拟**：`vgamepad` (基于 Windows ViGEmBus 驱动)
- **前端架构**：
  - **框架**：Vue 3 + TypeScript
  - **构建工具**：Vite
  - **样式**：TailwindCSS v4（`@tailwindcss/vite` 原生驱动，深色工业风玻璃态设计）
  - **状态管理**：Pinia
  - **图表**：ECharts
  - **图标**：Lucide-Vue-Next
- **打包分发**：
  - 前端执行 `npm run build` 生成静态资源至 `src/gamecurveprobe/web/`；
  - Python 后端通过 FastAPI 的 `StaticFiles` 挂载；
  - 启动应用时通过 Python `webbrowser.open()` 自动调起系统默认浏览器；
  - PyInstaller 仅打包 Python 运行时、依赖与前端静态产物，彻底剔除 PySide6 150MB+ 体积包袱。

---

## 3. 系统目录与模块划分

```text
GameCurveProbe/
├── pyproject.toml                     # 移除 PySide6，加入 fastapi, uvicorn, websockets, windows-capture
├── src/
│   └── gamecurveprobe/
│       ├── __init__.py
│       ├── __main__.py                # CLI 入口
│       ├── app.py                     # 初始化服务、组装依赖、启动 Uvicorn、打开浏览器
│       ├── models.py                  # 精简后的核心数据结构（配置、测点、结果模型）
│       │
│       ├── api/                       # [新增] Web 服务与 API 通道
│       │   ├── __init__.py
│       │   ├── server.py              # FastAPI 应用构建、静态托管挂载、生命周期管理
│       │   ├── routes.py              # 窗口列表、配置、标定、测量、导出等 REST 接口
│       │   └── websocket.py           # /ws/live 实时抓屏帧流、光流速度、测量进度广播
│       │
│       ├── backends/                  # 底层硬件与系统接口抽象
│       │   ├── capture/
│       │   │   ├── base.py            # BaseCaptureBackend 抽象基类
│       │   │   ├── wgc_backend.py     # [新增] 基于 windows-capture (WGC) 的窗口捕获引擎
│       │   │   ├── dxcam_backend.py   # 原 DXGI 引擎（备用）
│       │   │   └── stub.py            # 测试用模拟捕获桩
│       │   └── controller/
│       │       ├── base.py
│       │       ├── vgamepad_backend.py
│       │       └── stub.py
│       │
│       ├── services/                  # 核心测量与业务编排
│       │   ├── window_service.py      # Win32 窗口枚举与信息获取
│       │   ├── session_service.py     # 会话管理、状态转换与生命周期
│       │   ├── measurement_runner.py  # [重构] 统一稳态测量调度器（支持中断与进度回调）
│       │   ├── deadzone_service.py    # [重构] 内外双死区交互式调节与标定
│       │   └── idle_noise_runner.py   # 静态底噪采样服务
│       │
│       └── vision/
│           ├── motion_estimator.py    # 光流测速与 Sobel 纹理加权
│           └── roi_analyzer.py        # [新增] ROI 区域纹理丰富度与跟踪质量评估
│
├── frontend/                          # [新增] Vue 3 SPA 前端项目
│   ├── package.json
│   ├── vite.config.ts
│   ├── src/
│   │   ├── main.ts
│   │   ├── App.vue
│   │   ├── assets/                    # 全局 TailwindCSS v4 样式
│   │   ├── stores/                    # Pinia 状态中心（sessionStore, previewStore）
│   │   ├── api/                       # Axios / Fetch 封装与 WebSocket 连接
│   │   └── components/
│   │       ├── layout/                # 顶部导航、步骤向导栏、系统连接状态
│   │       ├── step1-capture/         # 窗口选择、引擎切换、Canvas 抓屏与 ROI 拖拽诊断
│   │       ├── step2-calibrate/       # 内外死区双滑块微调、摇杆交互、底噪一键标定
│   │       ├── step3-measure/         # 预设挡位(快速/标准/高精)、高级折叠参数、动态进度大屏
│   │       └── step4-dashboard/       # ECharts 交互曲线、特征标记、分析总结与导出面板
│
└── tests/                             # 自动化测试用例
    ├── api/                           # FastAPI 接口自动化测试
    ├── backends/                      # 抓屏与手柄测试
    ├── services/                      # 核心服务逻辑与测试状态机测试
    └── vision/                        # 光流与 ROI 评估测试
```

---

## 4. 详细接口设计 (API & WebSocket)

### 4.1 REST API 规范

所有请求响应采用标准 JSON 格式：

| 端点 | 方法 | 说明 | 请求体 / 参数 | 响应 |
| :--- | :--- | :--- | :--- | :--- |
| `/api/system/health` | GET | 服务健康检查与依赖就绪状态 (ViGEm/WGC) | 无 | `{status: "ok", controller_ready: bool}` |
| `/api/windows` | GET | 列出当前所有可见游戏窗口 | 无 | `{windows: [{id, title, pid, width, height}]}` |
| `/api/capture/attach` | POST | 绑定目标窗口并指定抓屏引擎 | `{window_id: int, backend: "wgc" \| "dxcam"}` | `{attached: bool, engine: str}` |
| `/api/session/roi` | POST | 设置当前跟踪的 ROI 区域 | `{x: int, y: int, width: int, height: int}` | `{roi: {...}, quality_score: float, tip: str}` |
| `/api/session/config` | GET | 获取当前会话配置及默认挡位预设 | 无 | `{config: {...}, presets: {...}}` |
| `/api/session/config` | PUT | 更新当前会话配置 | `{capture_fps, point_count, settle_ms, ...}` | `{config: {...}}` |
| `/api/deadzone/set` | POST | 直接更新内外死区数值 | `{inner_deadzone: float, outer_deadzone: float}` | `{inner_deadzone, outer_deadzone}` |
| `/api/deadzone/probe-start` | POST | 启动死区交互式试推模式 | `{initial_value: float, direction: "inner" \| "outer"}` | `{active: bool, current_output: float}` |
| `/api/deadzone/probe-step` | POST | 试推模式下单步增减摇杆推量 | `{delta: float}` | `{current_output: float}` |
| `/api/deadzone/probe-stop` | POST | 退出死区试推模式并回中 | 无 | `{active: false}` |
| `/api/calibrate/idle-noise` | POST | 执行画面底噪采样（静止 1.2s） | 无 | `{noise_floor_x: float, noise_floor_y: float}` |
| `/api/measurement/start` | POST | 启动稳态测定任务 | `{range_mode: "active_range" \| "full"}` | `{job_id: str, state: "running"}` |
| `/api/measurement/cancel` | POST | 中断当前测量任务（立即手柄回中） | 无 | `{state: "canceled"}` |
| `/api/session/result` | GET | 获取最新测量曲线数据与拟合特征 | 无 | `{points: [...], metrics: {...}}` |
| `/api/session/export` | POST | 导出文件并保存到指定路径或返回下载 | `{format: "csv" \| "json", output_dir?: str}` | `{file_path?: str, content?: str}` |

### 4.2 WebSocket 规范 (`/ws/live`)

客户端连接后，服务端以紧凑 JSON 或混合二进制流推送：
- **画面流 (Frame Event)**：
  - 抓屏画面经过 JPEG 压缩后传输（默认 30~60 FPS，体积极低），前端通过 Canvas 或 `Blob` 渲染；
- **运动向量 (Motion Event)**：
  - 格式：`{type: "motion", vx: float, vy: float, tracked_points: int, confidence: float}`；
- **测量进度 (Progress Event)**：
  - 格式：`{type: "progress", current_point: int, total_points: int, input_value: float, current_speed: float, stability: float, percent: int}`；
- **任务完成/失败 (Status Event)**：
  - 格式：`{type: "status", state: "idle" | "running" | "completed" | "failed", message: str}`。

---

## 5. 前端向导交互流程与各环节设计

### 阶段 1：画面捕获与 ROI 诊断 (Capture & ROI)
- **目标窗口下拉**：自动列出所有桌面应用（可一键刷新）；
- **抓取引擎选择**：默认为 **现代窗口捕获 (WGC - 推荐)**，备选 **桌面复制 (DXGI)**；
- **实时画板与 ROI 交互**：
  - 用户在 Canvas 画面上直接用鼠标拖出跟踪方框；
  - **ROI 质量智能评价**：
    - 后端计算 ROI 内部梯度丰富度与边缘方向比率；
    - 前端显示评级徽章：⭐⭐⭐⭐⭐“极佳纹理”，并在选区较平滑时给出具体建议（例如：“避免天空与纯色墙壁，请选取窗框、地面或明显砖石边缘”）。

### 阶段 2：环境标定与死区调节 (Calibrations & Dual Deadzone)
- **内外死区双向控制卡片**：
  - **联动双滑块**：清晰标明 `0.00 ~ 内死区 (静止)` $\to$ `内死区 ~ 外死区 (有效反应)` $\to$ `外死区 ~ 1.00 (满速饱和)`；
  - **精确数值输入**：支持手动填入数值（如 `0.045`）；
  - **交互式试推测试**：点击“试推摇杆”，可在网页上微调数值并同时观察游戏画面是否刚好开始转动，一键锁定临界值。
- **底噪快速采样卡片**：
  - 一键保持静止 1.2 秒，自动剔除视角轻微晃动底噪。

### 阶段 3：稳态响应测定与大屏 (Steady Measurement)
- **挡位选择器**：
  - ⚡ **快速摸底（9点）**：约 15 秒出大致曲线；
  - 🎯 **标准测定（17点，推荐）**：约 35 秒，精细度最佳；
  - 🔬 **科研级高精（33点）**：约 70 秒，全采样；
- **采样区间策略**：
  - 提供开关：“**聚焦有效行程**（仅在内死区至外死区之间排布测点，省时高效）”或“**全行程采样**”。
- **高级参数（折叠面板 + 问号 Tooltip 说明）**：
  - Settle 稳定时间（等待相机转速加速平稳的时间，默认 300ms）；
  - Sample 采样时间（计算平均速度的时长，默认 700ms）；
  - 重复测试次数（默认 2 次取中位数）。
- **测量进行时全景大屏**：
  - 实时显示当前推力仪表面板、动态波形曲线、进度条、测点稳定性评分及剩余时间。

### 阶段 4：ECharts 曲线大屏与导出 (Analysis & Export)
- **ECharts 交互图表**：
  - X 轴：摇杆推量（0.0 ~ 1.0）；Y 轴：转速（px/s）；
  - 自动标注高亮线：内死区界限、外死区界限、过渡段斜率；
  - 曲线形态自动判定：显示判定结果（如：标准线性 Linear、渐进加速 Exponential、S型曲线 S-Curve）。
- **导出套件**：
  - 📊 **标准 CSV**：包含列头 `Input, Velocity_px_s, Normalized_Ratio, Stability`；
  - 💾 **游戏预设 JSON**：保存完整测试工况与测试点，随时支持导入重现；
  - 📋 **一键复制为 Excel 表格**：直接复制 TSV 格式数据到剪贴板，方便粘贴至 Excel 绘制对比图。

---

## 6. 清理与剔除清单

在本次重构中，彻底删除以下历史遗留代码与依赖：
1. **彻底移除 PySide6**：从 `pyproject.toml` 移除，删除整个 `src/gamecurveprobe/gui/` 目录；
2. **彻底移除旧版 IPC HTTP 服务**：删除 `src/gamecurveprobe/services/http_server.py`；
3. **彻底移除 360° 旋转标定**：删除 `src/gamecurveprobe/services/yaw360_calibration_runner.py`；
4. **清理动态响应 (Dynamic Run) 占位代码**：清理 `models.py` 与业务层中所有未使用的动态占位字段与未实现逻辑。

---

## 7. 验证与测试计划

1. **后端 API 单元测试**：
   - 使用 `fastapi.testclient.TestClient` 测试 `/api/windows`、`/api/session/config`、`/api/deadzone/*` 等接口的正确性与异常处理；
2. **抓屏与视觉模块测试**：
   - 测试 `wgc_backend.py` 与 `dxcam_backend.py` 的接口一致性与异常回退；
   - 测试 `roi_analyzer.py` 的质量评分算法；
3. **测量调度与取消安全测试**：
   - 验证在稳态测量中途发送 `cancel` 时，手柄是否保证立即调用 `neutral()`，避免摇杆卡死；
4. **前端构建验证**：
   - 执行 `npm run build`，确保 TypeScript 类型无报错、Tailwind v4 样式打包正常，产物成功供 FastAPI 托管。
