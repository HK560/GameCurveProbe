# GameCurveProbe 用户手册

## 1. 工具当前能做什么

当前版本最适合做这几件事：

- 选择一个游戏窗口并实时预览画面
- 手动框选一个用于追踪的 ROI 区域
- 观察 ROI 的实时水平/垂直像素速度
- 运行真实 steady 扫描并导出当前会话结果
- 通过本地 HTTP IPC 从外部进程控制基础流程

当前版本还不能做的事：

- 自动识别最佳追踪区域

所以当前版本更准确地说，是“steady 真实测量 + ROI 追踪 + 会话框架”已经可用，但动态响应、更多轴向和更完整校准还在继续实现。

## 2. 如何运行

### 2.1 安装依赖

在项目根目录执行：

```powershell
uv sync --extra capture --extra controller
```

如果要启用手柄控制后端，请先安装 Windows 的 `ViGEmBus` 驱动，并确保环境里会安装到 `vgamepad` 依赖。

如果 `uv` 默认缓存目录不可写，可以改为：

```powershell
$env:UV_CACHE_DIR='d:\Github\GameCurveProbe\.uv-cache'
uv sync --extra capture --extra controller
```

### 2.2 启动 GUI

```powershell
uv run gamecurveprobe
```

### 2.3 启动 IPC-only 模式

```powershell
uv run gamecurveprobe --ipc-only
```

默认监听地址：

```text
http://127.0.0.1:48231
```

## 3. 如何做一次检测

### 3.1 准备游戏环境

为了让 ROI 追踪更稳定，建议：

- 使用窗口化或无边框模式
- 保持目标窗口在主显示器上
- 尽量关闭强动态模糊
- 尽量关闭镜头平滑、辅助瞄准、额外插帧
- 选择有明显对比纹理的静态场景
- 测试过程中尽量保持人物位置和视角高度不变

### 3.2 选择目标窗口

启动程序后，在左侧 `Environment` 区域：

1. 在 `Target window` 下拉框选择游戏窗口。
2. 如果窗口列表没有更新，点击 `Refresh Windows`。
3. 选中后，`Capture status` 应显示已附加到该窗口。

如果提示窗口尺寸无效，常见原因有：

- 游戏最小化了
- 游戏不在主显示器
- 当前窗口坐标超出主显示器边界

### 3.3 观察实时预览

右侧 `Preview & ROI` 区域会显示实时画面。

如果看到的是空白提示而不是画面，先检查：

- 目标窗口是否仍然可见
- 是否被最小化
- 是否被遮挡或移动到了其他显示器

### 3.4 框选 ROI

在实时画面上用鼠标左键拖拽，框选一块高对比、容易追踪的区域。

建议 ROI 满足这些条件：

- 有明显边缘或纹理
- 不要只框一块纯色天空/墙面
- 不要太小，建议至少 80x80 像素以上
- 尽量选靠近屏幕中央但不被 UI 遮挡的区域
- 避开血条、准星闪烁、动态 UI、字幕

框选完成后：

- 预览画面会显示 ROI 矩形框
- `Motion` 区域会开始显示 `vx / vy / pts / conf`

字段含义：

- `vx`
  ROI 水平像素速度，单位 `px/s`
- `vy`
  ROI 垂直像素速度，单位 `px/s`
- `pts`
  当前被稳定跟踪的特征点数量
- `conf`
  当前估计置信度，越接近 `1.0` 越稳定

### 3.5 读取检测结果

当前版本里，实时预览区的 `Motion` 是最接近真实检测值的部分。

你可以这样理解它：

- 如果你手动转动游戏镜头，`vx` 和 `vy` 会反映画面中 ROI 的移动速度
- 如果未来虚拟手柄接入后，工具就会把“某个固定输入值下的速度”采样下来，进而生成真正的输入曲线

`Curve Preview` 区域显示的是更贴近手柄驱动编辑器的推荐半轴曲线：

- 横轴固定为输入百分比 `0..100`
- 纵轴固定为输出百分比 `0..100`
- 预览里的曲线形状更适合直接对照驱动里的摇杆曲线设置

### 3.6 运行当前动作按钮

当前按钮行为如下：

- `Calibrate Yaw 360`
  当前对外测试版默认禁用，按钮置灰，不会启动标定流程
- `Run Steady`
  当前会在后台执行真实的稳态扫描流程，优先针对单显示器无边框窗口；每个点会输出质量标签、逐点诊断信息，并在低稳定度时自动重测一次
- `Run Dynamic`
  当前对外测试版默认禁用，按钮置灰，不会启动动态流程
- `Cancel`
  取消当前会话状态
- `Clear ROI`
  清除当前 ROI，并重置实时运动估计
- `Export CSV`
  导出当前会话结果

当前还支持 3 个全局快捷键，即使窗口缩小后也能触发：

- `F8`
  启动 `Run Steady`
- `F9`
  取消当前会话
- `F10`
  导出当前结果

检测开始、完成、失败、取消和导出成功时，程序会同时更新 GUI 状态，并发送系统通知。

## 4. 如何设置参数

左侧 `Probe Parameters` 面板中的参数作用如下。

### 4.1 Capture FPS

表示 steady 采集链路请求的目标采样率，同时也会影响 GUI 预览刷新频率。

建议：

- 普通调试可用 `60`
- 追求更平滑的实时观察可用 `120`
- 如果机器压力较大，先降到 `30` 或 `60`

注意：

- steady 会把这个值传给 `dxcam` 显示器采集后端
- GUI 预览内部仍会限制到适合实时刷新的频率

### 4.2 Points / half-axis

表示每个半轴预计扫描多少个输入点。

当前版本里它会影响两部分：

- 原始 `x` 轴正方向测量点数量
- 最终导出的单半轴驱动曲线密度

建议：

- 快速预览：`9`
- 常规测试：`17`
- 高密度测试：`33` 或更高

### 4.3 Settle (ms)

表示切换到一个输入点之后，等待系统稳定的时间。

未来真实测量时，它会影响：

- 是否避开起始加速段
- 是否只测稳态速度

建议：

- 快速游戏：`200-300`
- 有明显镜头平滑的游戏：`400-800`

### 4.4 Steady Sample (ms)

表示 `Run Steady` 在每个点稳定后实际采样的时长。

建议：

- 粗略测试：`300-500`
- 常规测试：`700-1000`
- 高稳定要求：`1000+`

### 4.5 Yaw360 Timeout (ms)

表示 `Calibrate Yaw 360` 的预留参数。当前对外测试版里该按钮默认禁用，所以这个参数暂时不会参与实际执行。

建议：

- 高灵敏度快速验证：`2000-3000`
- 常规测试：`4000-6000`
- 低灵敏度或慢镜头游戏：`6000+`

### 4.6 Repeats

表示每个点重复采样次数。

建议：

- 快速测试：`1`
- 常规测试：`2`
- 需要对比波动：`3-5`

### 4.7 Inner deadzone

用于标记内部死区位置。

当前版本里它会直接影响默认测量点的起始输入值，同时也会影响预览曲线形状；未来还会用于：

- 显示估计死区
- 辅助分析输入曲线起始段

### 4.8 Outer saturation

用于标记外部饱和值位置。

当前版本里它会直接影响默认测量点的终止输入值，同时也会影响预览曲线形状；未来还会用于：

- 显示曲线什么时候进入饱和
- 辅助判断游戏是否对外圈做了压缩

### 4.9 Enable dynamic response run

表示未来是否启用动态响应测试。

当前对外测试版中该项会保持禁用，仅作为后续功能预留。

### 4.10 Live preview during tests

表示在执行 `Run Steady`、`Calibrate Idle Noise` 时，是否继续把实时预览画面和实时 motion 数据推送到 GUI。等 `Calibrate Yaw 360` 重新开放后，它也会遵循同一规则。

默认值：关闭。

建议：

- 想减少测量干扰、降低 GUI 额外开销：保持关闭
- 想在测试过程中继续观察画面变化：手动开启

关闭时：

- 测量执行期间右侧实时画面会暂停
- 实时 `vx / vy / pts / conf` 也会暂停更新
- 任务结束、失败或取消后会自动恢复实时预览

## 5. 如何导出结果

点击 `Export CSV` 后，程序会导出四个文件：

- `raw_samples.csv`
- `curve_summary.csv`
- `session_meta.json`
- `controller_meta_curve.cmcurves.json`

当前版本里：

- `raw_samples.csv`
  记录当前会话中的 `x` 轴正方向原始测量点。对外测试版里主要来自 `Run Steady`；每一行还会带上 `measurement_kind`，用于区分来源
- `curve_summary.csv`
  记录推荐录入手柄驱动的 `x` 轴正半轴曲线点，坐标语义为 `0..100 -> 0..100`，并同样保留 `measurement_kind`
- `session_meta.json`
  保存当前配置、状态、原始结果，以及转换后的驱动曲线结果；`y_curve` 当前保持空列表。结果对象里会额外记录 `measurement_kind`、`summary`、`metadata`，其中 `metadata` 会包含 `capture_fps_requested`、`retry_used_points` 和逐点 `point_diagnostics`
- `controller_meta_curve.cmcurves.json`
  额外导出一个兼容 ControllerMeta 曲线工具 JSON 导入格式的 `curve_transfer` 包；当前默认把 `x_curve` 的正半轴推荐曲线转换为 `polyline`，可直接用于目标工具导入

## 6. 如何通过 IPC 控制

### 6.1 查看服务状态

```powershell
Invoke-RestMethod -Uri 'http://127.0.0.1:48231/health'
```

### 6.2 列出窗口

```powershell
Invoke-RestMethod -Uri 'http://127.0.0.1:48231/windows'
```

### 6.3 创建会话

```powershell
$session = Invoke-RestMethod `
  -Uri 'http://127.0.0.1:48231/session' `
  -Method Post `
  -ContentType 'application/json' `
  -Body '{"capture_fps":120,"point_count_per_half_axis":17}'
```

### 6.4 更新 ROI

```powershell
Invoke-RestMethod `
  -Uri ("http://127.0.0.1:48231/session/{0}/roi" -f $session.status.session_id) `
  -Method Post `
  -ContentType 'application/json' `
  -Body '{"x":200,"y":180,"width":240,"height":160}'
```

### 6.5 运行稳态流程

```powershell
Invoke-RestMethod `
  -Uri ("http://127.0.0.1:48231/session/{0}/run/steady" -f $session.status.session_id) `
  -Method Post `
  -ContentType 'application/json' `
  -Body '{}'
```

### 6.6 导出结果

```powershell
Invoke-RestMethod `
  -Uri ("http://127.0.0.1:48231/session/{0}/export" -f $session.status.session_id) `
  -Method Post `
  -ContentType 'application/json' `
  -Body (@{ output_dir = '.\\gcp-export' } | ConvertTo-Json)
```

说明：

- `POST /session/{id}/calibrate/yaw360`
  当前对外测试版会返回 `409`，表示该功能暂未开放
- `POST /session/{id}/run/dynamic`
  当前对外测试版会返回 `409`，表示该功能暂未开放

## 7. 检测时的建议

如果你想尽量让未来测得的曲线更靠谱，建议从一开始就养成这些操作习惯：

- 测试前固定游戏灵敏度，不中途修改
- 每个游戏建立单独的测试配置和导出目录
- 优先选横向纹理明显的 ROI 来看 `X / yaw`
- 同一组设置重复做 2 到 3 次，观察结果波动
- 避免角色位移、后坐力、镜头晃动等干扰

## 8. 当前已知限制

- steady 目前只优先支持单显示器无边框窗口采集
- 某些受保护窗口、独占全屏窗口可能无法正常抓取
- 当前对外测试版中 `Run Dynamic` 默认禁用
- 当前稳态检测只覆盖 `x` 轴正半轴，不覆盖 `x` 负方向或 `y` 轴
- 当前对外测试版中 `Calibrate Yaw 360` 默认禁用

## 9. 下一阶段会补什么

接下来最关键的实现方向是：

1. 接入真实虚拟手柄后端
2. 继续完善后台检测、热键与系统通知的稳定性
3. 继续提升 `x` 轴稳态测量和导出结果质量
4. 增加真实动态响应测试和更准确的导出字段
