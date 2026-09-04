import type { Language } from './i18n'

export type TutorialAction =
  | 'show-poor-roi'
  | 'show-good-roi'
  | 'show-noise'
  | 'show-probe'
  | 'animate-measurement'
  | 'show-report'
  | 'show-summary'

export interface TutorialStepDefinition {
  id: string
  chapter: number
  page?: 1 | 2 | 3 | 4
  element?: string
  title: string
  description: string
  action?: TutorialAction
}

interface StepCopy {
  id: string
  chapter: number
  page?: 1 | 2 | 3 | 4
  target?: string
  zh: [string, string]
  en: [string, string]
  action?: TutorialAction
}

const catalog: StepCopy[] = [
  { id: 'welcome', chapter: 1, zh: ['欢迎使用 GameCurveProbe', '这是一段使用教程模拟演示，引导你如何使用本工具来测量游戏手柄摇杆曲线'], en: ['Welcome to GameCurveProbe', 'This is a tutorial simulation that guides you through using this tool to measure gamepad joystick response curves.'] },
  { id: 'workflow', chapter: 1, target: 'workflow-nav', zh: ['四步检测流程', '依次完成游戏窗口选择与 ROI绘制、死区设置、自动测定和报告分析。'], en: ['Four-Step Measurement Workflow', 'Sequentially complete game window selection and ROI drawing, deadzone configuration, automated measurement, and report analysis.'] },
  { id: 'prepare', chapter: 1, target: 'controller-status', zh: ['开始前的准备', '真实检测时请启动游戏并安装 ViGEmBus。检测期间让游戏保持前台聚焦，不要连接实体手柄。'], en: ['Pre-Measurement Preparation', 'For real measurements, please launch the game and install ViGEmBus. Keep the game focused in the foreground during measurement and do not connect physical controllers.'] },

  { id: 'window', chapter: 2, page: 1, target: 'window-selector', zh: ['选择目标窗口', '从正在运行的窗口中选择游戏。当前教程演示使用一个虚构窗口。'], en: ['Select Target Window', 'Select the game from currently running windows. This tutorial demo uses a simulated window.'] },
  { id: 'backend', chapter: 2, page: 1, target: 'capture-backend', zh: ['抓图引擎', 'Auto 会优先选择合适后端；WGC 支持窗口遮挡；DXCAM 是兼容模式，可能会捕获遮挡内容。'], en: ['Capture Backend', 'Auto prioritizes the most suitable backend; WGC supports window occlusion; DXCAM is a compatibility mode that may capture occluding content.'] },
  { id: 'fps', chapter: 2, page: 1, target: 'capture-fps', zh: ['目标帧率', '120 FPS 是精度与开销的推荐平衡。60 FPS 更省资源，240 FPS 适合高刷新且性能充足的环境。'], en: ['Target Frame Rate', '120 FPS is the recommended balance between precision and overhead. 60 FPS saves resources, while 240 FPS suits high-refresh-rate setups with ample performance.'] },
  { id: 'attach', chapter: 2, page: 1, target: 'capture-action', zh: ['开始抓图', '真实操作会绑定所选窗口并启动实时预览；这里只做实例，不启动抓图。'], en: ['Start Capture', 'In real operation, this binds the selected window and starts real-time preview; this is just a demo and will not start actual capture.'] },
  { id: 'status', chapter: 2, page: 1, target: 'capture-status', zh: ['确认捕获状态', '这里核对分辨率、帧率和后端。窗口最小化、关闭、黑屏或停止出帧时会显示针对性提示。'], en: ['Verify Capture Status', 'Check resolution, frame rate, and backend here. Specific hints are shown if the window is minimized, closed, black-screened, or stops producing frames.'] },

  { id: 'roi', chapter: 3, page: 1, target: 'roi-viewport', zh: ['框选 ROI', '使用鼠标左键框选纹理丰富且稳定的画面区域，避开准星、动态 UI、角色和粒子效果。尺寸变化后需要重新框选。'], en: ['Draw ROI', 'Use the left mouse button to select a stable, texture-rich screen region, avoiding crosshairs, dynamic UI, characters, and particle effects. Redraw if the window size changes.'] },
  { id: 'roi-poor', chapter: 3, page: 1, target: 'roi-quality', action: 'show-poor-roi', zh: ['低质量选区示例', '平坦区域缺少梯度和角点，光流容易丢失。低于继续阈值时应重新选择。'], en: ['Poor ROI Example', 'Flat regions lack gradients and corners, making optical flow prone to tracking loss. Reselect when quality is below the continuation threshold.'] },
  { id: 'roi-good', chapter: 3, page: 1, target: 'roi-quality', action: 'show-good-roi', zh: ['优秀选区示例', '总分综合梯度、角点、信息熵和追踪稳定性。建议选择 60 分以上且四项指标均衡的区域。'], en: ['Excellent ROI Example', 'The overall score combines gradient, corners, entropy, and tracking stability. It is recommended to choose a region scored 60+ with well-balanced metrics.'] },
  { id: 'roi-coordinates', chapter: 3, page: 1, target: 'roi-coordinates', zh: ['坐标与尺寸', 'X/Y 是原始捕获画面坐标，宽高决定追踪范围。过小不稳定，过大会增加计算量并混入动态内容。'], en: ['Coordinates and Dimensions', 'X/Y are coordinates in the native capture resolution; width/height define the tracking area. Regions too small are unstable, while regions too large increase computation and risk capturing dynamic content.'] },

  { id: 'deadzone', chapter: 4, page: 2, target: 'deadzone-overview', zh: ['内外死区', '内死区是开始产生视角运动的摇杆最小输入，外死区是达到最大速度的摇杆最大输入；两者之间是摇杆测量输出的有效行程。'], en: ['Inner & Outer Deadzones', 'The inner deadzone is the minimum stick input that starts camera motion; the outer deadzone is the maximum stick input where maximum speed is reached. The range between them is the effective travel for measurement output.'] },
  { id: 'noise', chapter: 4, page: 2, target: 'noise-test', action: 'show-noise', zh: ['测定画面噪底', '让摇杆回中且画面静止，采样 X/Y 背景运动作为噪声。后续测速会过滤这一噪底优化结果。'], en: ['Measure Scene Noise Floor', 'Keep the stick centered and the scene still to sample background X/Y motion as noise. Subsequent velocity measurements will filter out this noise floor to optimize results.'] },
  { id: 'probe', chapter: 4, page: 2, target: 'probe-toggle', action: 'show-probe', zh: ['实时输出测试', '实际测试时候会通过虚拟手柄输出当前值，可以切回游戏观察“刚开始转动”或“刚达到最大速度”，可以通过快捷键调整死区'], en: ['Live Output Probe', 'During real testing, the current value is output via the virtual controller. Switch back to the game to observe "just starts turning" or "just reaches maximum speed", and adjust deadzones using hotkeys.'] },
  { id: 'targets', chapter: 4, page: 2, target: 'probe-targets', zh: ['切换探测目标', '先微调内死区，再切换到外死区。小步长更精确，大步长更快；可配合设置中的增减快捷键。'], en: ['Switch Probe Target', 'Fine-tune the inner deadzone first, then switch to the outer deadzone. Smaller step sizes are more precise while larger ones are faster; they can be adjusted using hotkeys in Settings.'] },
  { id: 'range', chapter: 4, page: 2, target: 'deadzone-range', zh: ['有效范围与采样点', '滑块显示内外死区的两个阈值和实际采样点。中间部分即为测量时会输出的右摇杆X轴值'], en: ['Effective Range & Sample Points', 'The slider displays the inner/outer deadzone thresholds and actual sample points. The middle section represents the Right Stick X-axis values output during measurement.'] },

  { id: 'range-mode', chapter: 5, page: 3, target: 'measurement-range', zh: ['测定范围', '按目标选择设定的范围或全范围。'], en: ['Measurement Range', 'Select between the configured range or the full range based on your measurement goals.'] },
  { id: 'parameters', chapter: 5, page: 3, target: 'measurement-parameters', zh: ['采样参数', '采样点数决定曲线分辨率；稳定时间等待视角匀速；采样时间和重复次数提升抗抖能力。'], en: ['Sampling Parameters', 'Point count determines curve resolution; settle time waits for camera motion to stabilize; sample duration and repeat count improve jitter resistance.'] },
  { id: 'presets', chapter: 5, page: 3, target: 'measurement-parameters', zh: ['三类建议', '快速预览：9 点/快速；推荐均衡：17 点/标准；高精度：33 点/精确。'], en: ['Three Recommended Presets', 'Quick Preview: 9 points / Fast; Recommended Balanced: 17 points / Standard; High Precision: 33 points / Precise.'] },
  { id: 'start', chapter: 5, page: 3, target: 'measurement-start', zh: ['开始稳态测定', '点击后会倒计时并自动输出摇杆值并测量。F9 可在游戏中开始，F10 可安全取消，按键可在设置中更改。'], en: ['Start Steady-State Measurement', 'Clicking starts a countdown followed by automated stick output and measurement. Press F9 in-game to start, and F10 to safely cancel; keys can be modified in Settings.'] },
  { id: 'progress', chapter: 5, page: 3, target: 'measurement-progress', action: 'animate-measurement', zh: ['观察测定过程', '进度会经历稳定、采样、完成等阶段；不稳定点会自动复测。'], en: ['Monitor Measurement Progress', 'Progress transitions through settling, sampling, and completion stages; unstable sample points are automatically retested.'] },
  { id: 'logs', chapter: 5, page: 3, target: 'measurement-logs', zh: ['日志与诊断', '日志记录每个点、复测和异常原因。检测时保持游戏前台聚焦，不要连接实体手柄。'], en: ['Logs and Diagnostics', 'The log records each point, retry, and exception cause. Keep the game focused in the foreground during measurement and do not connect physical controllers.'] },

  { id: 'report', chapter: 6, page: 4, target: 'analysis-summary', action: 'show-report', zh: ['读取分析报告', '教程加载一份完整示例。这里先看模型类型、置信度和总体误差，再结合曲线判断。'], en: ['Read Analysis Report', 'The tutorial loads a complete sample report. Check the model type, confidence, and overall error first, then evaluate alongside the curve chart.'] },
  { id: 'models', chapter: 6, page: 4, target: 'analysis-model', zh: ['理解曲线模型', '线性响应均匀；幂律外段加速；分段曲线有明显速度区间；S 曲线两端柔和、中段稳定。'], en: ['Understand Curve Models', 'Linear response is uniform; power curves accelerate outward; piecewise curves have distinct velocity segments; S-curves are gentle at both ends and steady in the middle.'] },
  { id: 'metrics', chapter: 6, page: 4, target: 'analysis-model', zh: ['理解拟合指标', 'R² 越接近 1 越好，NRMSE 越低越好，置信度综合反映模型可靠性。参数如 gamma 描述曲线弯曲程度。'], en: ['Understand Fitting Metrics', 'R² closer to 1 is better; NRMSE lower is better; confidence comprehensively reflects model reliability. Parameters such as gamma describe the degree of curvature.'] },
  { id: 'chart', chapter: 6, page: 4, target: 'analysis-chart', zh: ['曲线、死区与异常点', '对照原始速度、归一化响应、拟合线和死区标记。孤立点常由帧抖动造成；连续异常则应重新检测。'], en: ['Curves, Deadzones & Outliers', 'Compare raw velocity, normalized response, fitted line, and deadzone markers. Isolated outliers are often caused by frame jitter; consecutive anomalies suggest re-running the test.'] },
  { id: 'recalculate', chapter: 6, page: 4, target: 'analysis-range', zh: ['重新解析有效范围', '调整内外截点可即时重算归一化和模型，用于验证边界判断；原始采样点不会被删除。'], en: ['Recalculate Effective Range', 'Adjusting inner/outer cutoffs instantly recalculates normalization and model fitting for verifying boundary decisions; original sample points will not be deleted.'] },
  { id: 'export', chapter: 6, page: 4, target: 'analysis-export', zh: ['导出 ControllerMeta 曲线数据', '导出的 JSON/CSV 是 ControllerMeta 曲线工具支持的格式。ControllerMeta 是需要另行下载安装的手柄检测工具，可前往 https://www.controllermeta.com/ 下载并用它继续编辑、转换曲线。教程不会打开或下载文件。'], en: ['Export ControllerMeta Curve Data', 'The exported JSON/CSV uses a format supported by the ControllerMeta curve tool. ControllerMeta is a separate gamepad testing tool that must be downloaded and installed from https://www.controllermeta.com/ before you can use it to continue editing or converting the curve. The tutorial does not open or download files.'] },

  { id: 'summary', chapter: 7, target: 'workflow-nav', action: 'show-summary', zh: ['准备开始真实检测', '检查游戏与驱动、选窗口、选高质量 ROI、测噪底、校准死区、确认参数，然后开始测定并解读报告。教程可在设置中重看。'], en: ['Ready to Start Real Measurement', 'Check game and driver, select window, choose high-quality ROI, measure noise floor, calibrate deadzones, confirm parameters, then start measurement and interpret the report. This tutorial can be replayed from Settings anytime.'] },
]

export const tutorialTargetNames = [...new Set(catalog.map(step => step.target).filter((target): target is string => Boolean(target)))]

export function createTutorialSteps(locale: Language): TutorialStepDefinition[] {
  return catalog.map(step => ({
    id: step.id,
    chapter: step.chapter,
    page: step.page,
    element: step.target ? ('[data-tour="' + step.target + '"]') : undefined,
    title: step[locale][0],
    description: step[locale][1],
    action: step.action,
  }))
}

