# GameCurveProbe 2.0

English | [中文](README.zh-CN.md)

GameCurveProbe is a Windows tool for measuring and tuning gamepad input response curves. It uses Windows Graphics Capture (WGC) and computer-vision optical flow tracking to automatically measure the nonlinear relationship between right-stick travel and the angular velocity of the in-game viewport. This helps players and peripheral developers identify game deadzones and acceleration models, including linear, exponential, and S-curve responses, and export standardized configurations.

---

## Key Features

- **Modern Web UI**: A guided visual interface built with Vue 3, TypeScript, Tailwind CSS, and ECharts that opens automatically in the default browser.
- **Windows Graphics Capture**: Prioritizes the hardware-accelerated Windows.Graphics.Capture API to avoid black screens and low frame rates, with automatic fallback to DXGI Desktop Duplication.
- **Precise Dual-Deadzone Calibration**: Supports real-time output probing, fine adjustment, and one-click setting of the inner deadzone (initial response threshold) and outer deadzone (full-speed saturation threshold).
- **Smart ROI Selection and Quality Checks**: Provides a real-time ROI quality score from 0 to 100 based on Sobel gradients, corner detection, and horizontal optical-flow texture entropy, helping avoid unstable flat or textureless regions.
- **Automated Steady-State Measurement and Model Fitting**: Performs automated stepped sampling and retries unstable samples. Uses NRMSE to classify linear, exponential, and logistic S-curve responses.
- **Standardized Report Export**: Exports complete sample points and classification parameters as standardized JSON reports or RFC 4180 CSV files.

---

## Quick Start

### Requirements

- **Operating System**: Windows 10 (1903+) or Windows 11
- **Python**: Python 3.13+ and the [uv](https://github.com/astral-sh/uv) package manager
- **Virtual Gamepad Driver**: [ViGEmBus](https://github.com/nefarius/ViGEmBus/releases) for Windows (required for gamepad emulation)

### Install and Run

1. Sync the Python dependencies:

```powershell
uv sync --extra capture --extra controller
```

2. Start GameCurveProbe 2.0 (opens the browser automatically):

```powershell
uv run gamecurveprobe
```

3. Optional startup arguments:

```powershell
# Specify the port and bind address
uv run gamecurveprobe --port 8765 --host 127.0.0.1

# Run without opening the browser automatically
uv run gamecurveprobe --no-browser
```

---

## Four-Step Workflow

1. **Step 1: Window and Capture Configuration**
   - Select a running game window from the drop-down list.
   - Choose a capture engine (Auto recommended) and target frame rate (60, 120, or 240 FPS).
   - Drag over the live preview to select a high-contrast feature region, then review its real-time ROI quality score and recommendations.
2. **Step 2: Gamepad Deadzone Calibration**
   - Activate the output probe and fine-tune the right-stick output in increments of 0.001, 0.005, or 0.01.
   - Observe when the viewport begins to move and set the inner and outer deadzones with one click.
   - Measure the static scene noise floor and filter out environmental motion noise.
3. **Step 3: Automated Curve Measurement**
   - Select a measurement mode (full range, outer deadzone only, or deadzone segment only) and sample density (9, 17, or 33 points).
   - Select **Start Steady-State Measurement**. The application outputs each value automatically, waits for angular velocity to stabilize, and shows progress and stability for each point in real time.
4. **Step 4: Fit Analysis and Report Export**
   - View angular velocity and normalized response curves on an interactive dual-Y-axis chart.
   - Review the fitted mathematical curve model, including linearity, power-law exponent, and confidence.
   - Export a JSON report or CSV data table, or import existing data for comparison.

---

## Frontend Development and Packaging

### Run the Web UI Locally

```powershell
cd webui
npm install
npm run dev
```

### Build the Frontend

```powershell
cd webui
npm run build
```

Build output is written to `webui/dist`. Use the following script to build, synchronize, and start the application automatically:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start-app.ps1
```

You can append `--no-browser` or other application startup arguments.

### Build the Python Wheel

```powershell
uv build
```

### Build a Standalone Windows EXE

In the repository's GitHub Actions page, select **Build Windows EXE** and click **Run workflow**. After the build succeeds, download the `GameCurveProbe-windows` artifact. To build locally, run:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build-exe.ps1
```

The local output is written to `dist\GameCurveProbe.exe`.
