# GameCurveProbe

GameCurveProbe 是一个面向 Windows 的游戏手柄输入曲线探测工具，目标是测量“右摇杆输入值”和“游戏内镜头移动速度/转向速度”之间的关系。

当前版本已经具备这些基础能力：

- PySide6 图形界面
- 本地 HTTP IPC 控制接口
- Windows 窗口枚举
- 基于 `dxcam` 的实时窗口/显示器画面采集
- 手动框选 ROI
- 基于光流的 ROI 运动速度估计
- `Run Steady` 的后台稳态扫描流程
- steady 点位质量诊断与自动一次重测
- 全局快捷键控制开始 / 取消 / 导出（`F8` / `F9` / `F10`）
- 面向手柄驱动的 `0..100 -> 0..100` 曲线预览
- 会话结果导出为 CSV / JSON

当前版本仍有这些限制：

- 对外测试版中，`Run Dynamic` 按钮和 IPC 接口默认禁用
- 对外测试版中，`Calibrate Yaw 360` 按钮和 IPC 接口默认禁用
- steady 当前优先支持单显示器上的无边框窗口
- 当前稳态检测和导出只覆盖 `x` 轴正半轴

更详细的使用说明见：

- [用户手册](docs/USER_GUIDE.md)

## 环境要求

- Windows 10/11
- `uv`
- 如果要使用手柄控制后端，需要安装 `ViGEmBus`，并同步带有 `vgamepad` 的依赖环境
- 建议使用独立显卡或支持 Desktop Duplication 的显卡驱动
- 建议目标游戏运行在窗口化或无边框模式

## 安装与运行

首次同步依赖：

```powershell
uv sync --extra capture --extra controller
```

启动桌面界面：

```powershell
uv run gamecurveprobe
```

只启动本地 IPC 服务：

```powershell
uv run gamecurveprobe --ipc-only
```

指定 IPC 端口：

```powershell
uv run gamecurveprobe --port 49200
```

如果当前环境对 `uv` 默认缓存目录没有写权限，可以在仓库内指定缓存目录：

```powershell
$env:UV_CACHE_DIR='d:\Github\GameCurveProbe\.uv-cache'
uv sync --extra capture --extra controller
uv run gamecurveprobe
```

## 项目结构

- `src/gamecurveprobe/app.py`
  应用入口，负责启动 GUI 和 IPC 服务。
- `src/gamecurveprobe/gui/`
  图形界面，包括曲线预览和实时画面预览。
- `src/gamecurveprobe/backends/capture/`
  采集后端，GUI 预览继续使用窗口截图，steady 运行使用 `dxcam` 显示器采集。
- `src/gamecurveprobe/services/`
  会话管理、窗口管理、HTTP IPC。
- `src/gamecurveprobe/vision/`
  ROI 运动估计逻辑。

## 当前 IPC 端点

- `GET /health`
- `GET /windows`
- `POST /session`
- `POST /session/{id}/roi`
- `POST /session/{id}/calibrate/yaw360`
  当前对外测试版会返回 `409`，表示功能暂未开放。
- `POST /session/{id}/run/steady`
- `POST /session/{id}/run/dynamic`
  当前对外测试版会返回 `409`，表示功能暂未开放。
- `POST /session/{id}/cancel`
- `POST /session/{id}/export`
- `GET /session/{id}/status`
- `GET /session/{id}/result`

## 开发说明

检查代码是否能正常编译：

```powershell
uv run python -m compileall src
```

当前阶段推荐的开发顺序：

1. 解除对外测试版中的 `Calibrate Yaw 360` 禁用并补齐发布质量验证。
2. 解除对外测试版中的 `Run Dynamic` 禁用并补齐真实动态响应测试。
3. 继续完善稳态测量的精度、异常处理和热键/通知兼容性。
4. 再扩展绝对角速度标定、批量导出和更强的分析格式。
