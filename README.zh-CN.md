# GameCurveProbe 2.0

[English](README.md) | 中文

GameCurveProbe 是专为 Windows 平台打造的游戏手柄输入响应曲线测定与调优工具。通过 Windows 现代图形捕获（WGC）和计算机视觉光流追踪技术，全自动测定右摇杆推杆行程与游戏视口旋转角速度之间的非线性响应关系，帮助玩家与外设开发者精准掌握游戏死区、加速模式（线性、指数加速、S 型曲线）并导出标准化配置。

---

## 核心特性

- **现代 WebUI 交互**：基于 Vue 3、TypeScript、Tailwind CSS 与 ECharts 构建的向导式可视化界面，启动时自动唤起默认浏览器。
- **WGC 现代图形捕获**：优先采用 Windows.Graphics.Capture API 硬件级抓图，避免黑屏与低帧率，兼顾 DXGI Desktop Duplication 自动回退。
- **双死区精确标定**：支持内死区（起始响应阈值）与外死区（满速饱和阈值）实时输出微调探测与一键设定。
- **智能选区与特征质检**：基于 Sobel 梯度、角点检测与横向光流纹理熵的 0~100 分实时 ROI 质检评分，避免平坦天空或无纹理区域失稳。
- **自动化稳态测定与模型拟合**：全自动步进采样，自动重试失稳采样点；基于 NRMSE 智能分类线性（Linear）、指数加速（Exponential）及 S 型曲线（Logistic S-Curve）。
- **标准化报表导出**：支持一键导出包含完备采样点与分类参数的标准化 JSON 报告及 RFC 4180 CSV 格式。

---

## 快速上手

### 环境要求

- **操作系统**：Windows 10 (1903+) / Windows 11
- **Python 环境**：Python 3.13+ 与 [uv](https://github.com/astral-sh/uv) 包管理器
- **虚拟手柄驱动**：Windows [ViGEmBus](https://github.com/nefarius/ViGEmBus/releases) 驱动（手柄模拟必须）

### 安装依赖与运行

1. 同步 Python 依赖环境：

```powershell
uv sync --extra capture --extra controller
```

2. 启动 GameCurveProbe 2.0 服务（自动打开浏览器）：

```powershell
uv run gamecurveprobe
```

3. 可选启动参数：

```powershell
# 指定端口与监听地址
uv run gamecurveprobe --port 8765 --host 127.0.0.1

# 后台运行不自动打开浏览器
uv run gamecurveprobe --no-browser
```

---

## 4 步向导流程

1. **步骤 1：窗口与抓图配置**
   - 从下拉列表中选择运行中的游戏窗口。
   - 选择抓图引擎（推荐 Auto）与目标帧率（60 / 120 / 240 FPS）。
   - 在实时画面中左键拖拽圈选高对比度特征区域，实时查看 ROI 质检评分与优化建议。
2. **步骤 2：手柄死区标定**
   - 激活输出探测器，以 0.001 / 0.005 / 0.01 精度微调右摇杆输出。
   - 观察画面微动点，一键设定内死区与外死区。
   - 一键测定画面静止噪底，滤除环境晃动噪声。
3. **步骤 3：全自动曲线测定**
   - 选择测定模式（全范围 / 仅外死区 / 仅死区段）与采样点密度（9 / 17 / 33 点）。
   - 点击“开始稳态测定”，系统自动输出并等待角速度平稳，实时查看进度与各点稳定性。
4. **步骤 4：拟合分析与报告导出**
   - 可视化查看双 Y 轴角速度与归一化响应曲线图表。
   - 查看曲线数学模型拟合结果（线性度、幂律指数、置信度等）。
   - 一键导出为 JSON 报告或 CSV 数据表，或导入已有数据复测。

---

## 前端开发与打包构建

### 本地 WebUI 独立调试

```powershell
cd webui
npm install
npm run dev
```

### 构建前端静态包

```powershell
cd webui
npm run build
```

编译产物输出至 `webui/dist`。应用启动时可用以下脚本自动构建、同步并启动：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start-app.ps1
```

可追加 `--no-browser` 或其他应用启动参数。

### 打包 Python Wheel

```powershell
uv build
```

### 构建独立 Windows EXE 单文件

在 GitHub 仓库的 Actions 页面选择 **Build Windows EXE**，点击 **Run workflow** 即可手动构建并下载 `GameCurveProbe-windows` artifact。也可在本地运行：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build-exe.ps1
```

本地产物输出至 `dist\GameCurveProbe.exe`。
