# 游戏手柄响应曲线自动拟合估算与可视化设计规范

## 1. 目标与背景

在游戏手柄测定仪完成离散采样点的速度与推杆行程测试后，需自动逆向推导并估算游戏原生响应曲线的数学模型。
实际游戏中响应曲线一般呈现以下形态：
1. **纯线性曲线（Linear）**：全行程匀速上升 $y = kx$。
2. **凹曲线 / 幂函数曲线（Power / Classic Exponential）**：小推杆行程下灵敏度低便于微调瞄准，大推杆下速度迅速爬升（如 $y = x^\gamma, \gamma \approx 1.5 \sim 2.5$）。
3. **分段折线（Piecewise Linear）**：
   - **1 个拐点（2 段折线）**：主段平缓线性巡航，尾端达到设定阈值（如 90%~95%）后触发“转向额外加速（Outer Threshold Boost / Turning Extra Yaw）”，斜率暴增。
   - **2 个拐点（3 段折线）**：微调启动段、巡航段、额外加速段。
4. **贝塞尔曲线（Cubic Bézier）**：在精英手柄驱动或 Steam Input 自定义曲线中常用的平滑过渡曲线。

同时，实测离散点中因游戏偶发掉帧、ROI短期遮挡或测速波动可能存在离群噪点（Outliers），必须具备鲁棒过滤能力，忽略偏差过大的噪点，并自动评判出全局最佳拟合模型，在图表中叠加直观渲染。

---

## 2. 算法与数学模型设计

模块位于前端 `webui/src/services/curveFitting.ts`，纯 TypeScript 毫秒级求解。

### 2.1 数据预处理与死区归一化
设有效采样点为 $(x_i, v_i)$，其中 $x_i \in [x_{\text{inner}}, x_{\text{outer}}]$。
将输入映射到相对分析行程 $u_i \in [0, 1]$：
$$u_i = \frac{x_i - x_{\text{inner}}}{x_{\text{outer}} - x_{\text{inner}}}$$
速度归一化到 $w_i \in [0, 1]$：
$$w_i = \frac{v_i - v_{\min}}{v_{\max} - v_{\min}}$$

### 2.2 离群噪点剔除（Robust Filtering via MAD）
1. 计算相邻点差分及局部平滑残差：
   $$r_i = |w_i - \text{median\_filter}(w)_i|$$
2. 计算中位绝对偏差 $\text{MAD} = \text{median}(|r_i - \text{median}(r)|)$。
3. 判定阈值：若 $r_i > 2.5 \times \max(\text{MAD}, 0.02)$，则标记该采样点为 `is_outlier = true`。
4. 拟合计算时剔除或降权 `is_outlier` 点，图表渲染时保留该采样点并标记为已忽略。

### 2.3 候选拟合模型池（Model Pool）

所有拟合均在 $u \in [0, 1] \to \hat{w} \in [0, 1]$ 进行求解：

1. **线性模型（Linear）**
   - 模型函数：$\hat{w}(u) = k \cdot u + b$（强制通过或逼近 $(0,0)$ 与 $(1,1)$，最小二乘求解）。
   - 参数量 $k_{\text{param}} = 2$。

2. **幂函数/凹凸曲线（Power Curve）**
   - 模型函数：$\hat{w}(u) = u^\gamma$。
   - 优化区间：$\gamma \in [0.3, 3.5]$，采用黄金分割搜索最小化 $\sum (w_i - u_i^\gamma)^2$。
   - 参数量 $k_{\text{param}} = 1$。

3. **1 拐点折线（Piecewise Linear - 1 Breakpoint）**
   - 连续分段函数：
     $$\hat{w}(u) = \begin{cases} 
     k_1 \cdot u, & 0 \le u \le u_b \\ 
     k_1 \cdot u_b + k_2 \cdot (u - u_b), & u_b < u \le 1 
     \end{cases}$$
   - 约束：$\hat{w}(1) \approx 1$，$k_1 \ge 0, k_2 \ge 0$。
   - 求解：遍历有效采样点作为拐点 $u_b \in [0.15, 0.95]$，对前后两段进行加权最小二乘求解，寻找全局 MSE 最小的拐点 $u_b$。
   - 参数量 $k_{\text{param}} = 3$（拐点 $u_b$、斜率 $k_1$、斜率 $k_2$）。
   - 特征输出：加速阈值 $X_{\text{accel}}$、额外加速倍率 $\text{ratio} = k_2 / k_1$。

4. **2 拐点折线（Piecewise Linear - 2 Breakpoints）**
   - 连续三段函数，拐点 $0 < u_{b1} < u_{b2} < 1$。
   - 二维网格动态规划求解。
   - 参数量 $k_{\text{param}} = 5$。

5. **三次贝塞尔曲线（Cubic Bézier）**
   - 起点 $P_0=(0,0)$，终点 $P_3=(1,1)$，控制点 $P_1=(x_1, y_1), P_2=(x_2, y_2)$。
   - 约束：$0 \le x_1 \le x_2 \le 1$ 且 $0 \le y_1 \le y_2 \le 1$（保证单调性）。
   - 求解：参数空间快速网格搜索或 Nelder-Mead 迭代。
   - 参数量 $k_{\text{param}} = 4$。

### 2.4 模型自动优选准则（BIC 惩罚防过拟合）
对每个模型计算标准均方误差 $\text{MSE}$ 与贝叶斯信息准则（BIC）：
$$\text{BIC} = N \cdot \ln(\text{MSE} + 1e-8) + k_{\text{param}} \cdot \ln(N)$$
- 惩罚项 $k_{\text{param}} \cdot \ln(N)$ 能有效抵消分段折线和贝塞尔的高自由度优势。
- 只有当折线或贝塞尔带来的残差降幅显著超越参数惩罚（如末端额外加速导致残差断崖式下降）时，系统才会优选该模型，否则自动回归纯线性或幂函数模型。

---

## 3. 前端交互与可视化设计

### 3.1 拟合引擎封装 (`webui/src/services/curveFitting.ts`)
导出方法：
```typescript
export interface FitResult {
  modelType: 'linear' | 'power' | 'piecewise1' | 'piecewise2' | 'bezier'
  modelName: string
  confidence: number // 0.0 - 1.0
  nrmse: number
  r2: number
  bic: number
  parameters: Record<string, number | string>
  sampleOutliers: number[] // 离群点索引
  // 生成在原始输入区间 [inner, outer] 的 100 个平滑插值采样点，供 ECharts 绘制
  fittedCurvePoints: [number, number][]
  // 拐点物理输入坐标 (用于画 MarkLine)
  breakpoints?: number[]
}

export function fitBestCurve(points: MeasurementPoint[], innerDz: number, outerDz: number): {
  best: FitResult
  candidates: Record<string, FitResult>
}
```

### 3.2 图表呈现 (`CurveChart.vue`)
1. **平滑拟合曲线（Fitted Line）**：
   - 颜色：采用青蓝色高光实线（如 `#06b6d4` / `#0891b2`），线宽 2.5px，平滑过渡。
   - 图例增加“🎯 估算拟合曲线”。
2. **拐点标记（MarkLine）**：
   - 折线模型存在拐点时，在拐点推杆行程处绘制垂直辅助虚线，带标签：`⚡ 额外加速拐点: 94.0%`。
3. **离群点区分（Outlier Visual）**：
   - 被算法忽略的噪点，在 Tooltip 中展示状态“⚠️ 偏差过大已自动忽略”。

### 3.3 结果展示面板 (`AnalysisStep.vue`)
1. **自动诊断徽章与指标**：
   - 识别类型高亮标签（如 `折线 (1个拐点 / 边缘额外加速)`、`纯线性`、`下凹曲线 (Power: γ=1.75)` 等）。
   - 置信度指标（如 `98.5%`）。
2. **游戏核心配置反推数值**：
   - 折线模型展示：**额外加速触发点**、**基础巡航斜率**、**边缘加速倍率**。
   - 幂曲线展示：**响应系数 $\gamma$**。
3. **手动对比切换器（Model Selector）**：
   - 提供快捷单选组或下拉选项：`[⭐ 自动推荐: 1点折线] [线性] [幂函数] [1点折线] [2点折线] [贝塞尔]`。
   - 用户切换时，图表立即动态切换展示对应模型的拟合线。
4. **与死区滑块实时联动**：
   - 用户滑动调整死区时，`recalculatedPoints` 更新触发 `computed` 重新拟合，图表与参数毫秒级无缝刷新。

---

## 4. 单元测试与验证计划

1. **单元测试 (`webui/tests/curveFitting.test.ts`)**：
   - 测试纯线性点集：验证算法稳定输出 `linear`，BIC 优于分段。
   - 测试带尾端加速点集（用户提供的典型 Apex/Halo 场景，95% 处速度暴涨）：验证算法精准识别为 `piecewise1`，正确输出拐点约 94%~95%。
   - 测试下凹幂曲线点集（$y = x^2$）：验证算法精准输出 `power` 且 $\gamma \approx 2.0$。
   - 测试含离群噪点点集（中途插入单个毛刺点）：验证离群点被自动剔除，不拉偏拟合线。
2. **UI 与端到端测试**：
   - 在前端页面调整死区滑块，确认拟合曲线与拐点垂直线自适应重算。
   - 切换手动模型，确认图表曲线与参数卡片即时更新。
