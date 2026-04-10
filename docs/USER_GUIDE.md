# GameCurveProbe User Guide

## 1. What the Tool Can Do Right Now

The current version is best suited for these tasks:

- Select a game window and preview its image in real time
- Manually draw an ROI area for tracking
- Observe the real-time horizontal and vertical pixel speed of the ROI
- Run an actual steady scan and export the current session results
- Control the basic workflow from an external process through local HTTP IPC

What the current version cannot do yet:

- Automatically detect the best tracking region

So the most accurate description of the current state is that "real steady measurement + ROI tracking + session framework" is already usable, while dynamic response, more axis coverage, and more complete calibration are still in progress.

## 2. How to Run It

### 2.1 Install Dependencies

Run this in the project root:

```powershell
uv sync --extra capture --extra controller
```

If you want to enable the controller backend, install the Windows `ViGEmBus` driver first and make sure your environment includes the `vgamepad` dependency.

If the default `uv` cache directory is not writable, you can use:

```powershell
$env:UV_CACHE_DIR='d:\Github\GameCurveProbe\.uv-cache'
uv sync --extra capture --extra controller
```

### 2.2 Launch the GUI

```powershell
uv run gamecurveprobe
```

### 2.3 Launch IPC-Only Mode

```powershell
uv run gamecurveprobe --ipc-only
```

Default listen address:

```text
http://127.0.0.1:48231
```

## 3. How to Run a Measurement

### 3.1 Prepare the Game Environment

To make ROI tracking more stable, it is recommended to:

- Use windowed or borderless mode
- Keep the target window on the primary monitor
- Disable strong motion blur if possible
- Disable camera smoothing, aim assist, and extra frame interpolation if possible
- Choose a static scene with strong texture contrast
- Keep the character position and camera height as consistent as possible during testing

### 3.2 Select the Target Window

After launching the program, use the `Environment` section on the left:

1. Select the game window from the `Target window` dropdown.
2. If the window list is outdated, click `Refresh Windows`.
3. After selection, `Capture status` should show that the tool is attached to that window.

If you see an invalid window size warning, common causes include:

- The game is minimized
- The game is not on the primary monitor
- The current window coordinates extend outside the primary monitor bounds

### 3.3 Watch the Live Preview

The `Preview & ROI` section on the right shows the live image.

If you see a blank placeholder instead of the image, check:

- Whether the target window is still visible
- Whether it has been minimized
- Whether it is covered by another window or moved to a different display

### 3.4 Draw the ROI

Use the left mouse button to drag a high-contrast, easy-to-track region in the live preview.

Recommended ROI characteristics:

- Clear edges or visible texture
- Avoid selecting a flat sky or plain wall
- Do not make it too small; at least 80x80 pixels is recommended
- Prefer a region near the center of the screen that is not blocked by UI
- Avoid health bars, flashing crosshairs, dynamic UI, and subtitles

After the ROI is selected:

- The preview will show the ROI rectangle
- The `Motion` section will start showing `vx / vy / pts / conf`

Field meanings:

- `vx`
  Horizontal pixel speed of the ROI, in `px/s`
- `vy`
  Vertical pixel speed of the ROI, in `px/s`
- `pts`
  Number of feature points that are currently being tracked stably
- `conf`
  Current estimation confidence; values closer to `1.0` are more stable

### 3.5 Read the Measurement Result

In the current version, the `Motion` readout in the live preview is the closest thing to the actual measurement result.

You can think of it like this:

- If you rotate the in-game camera manually, `vx` and `vy` reflect the movement speed of the ROI in the image
- Once a virtual controller backend is fully integrated, the tool will sample the speed at a fixed input value and then generate a real input curve

The `Curve Preview` section shows a recommended half-axis curve that better matches controller driver editors:

- The horizontal axis is fixed to input percentage `0..100`
- The vertical axis is fixed to output percentage `0..100`
- The previewed curve shape is designed to map more directly to stick curve settings in a controller driver

### 3.6 Use the Current Action Buttons

Current button behavior:

- `Calibrate Yaw 360`
  Disabled by default in the public test build. The button is grayed out and does not start the calibration flow.
- `Run Steady`
  Runs the real steady scan in the background. It is currently optimized for a single-monitor borderless window setup. Each point reports quality labels and per-point diagnostics, and points with low stability are automatically retried once.
- `Run Dynamic`
  Disabled by default in the public test build. The button is grayed out and does not start the dynamic flow.
- `Cancel`
  Cancels the current session state.
- `Clear ROI`
  Clears the current ROI and resets the live motion estimation.
- `Export CSV`
  Exports the current session results.

The tool also supports 3 global hotkeys that work even when the window is minimized:

- `F8`
  Start `Run Steady`
- `F9`
  Cancel the current session
- `F10`
  Export the current results

When a measurement starts, finishes, fails, is canceled, or exports successfully, the program updates the GUI state and sends a system notification.

## 4. How to Configure Parameters

The parameters in the `Probe Parameters` panel on the left work as follows.

### 4.1 Capture FPS

This is the requested target sampling rate for the steady capture pipeline, and it also affects the GUI preview refresh rate.

Recommendations:

- `60` for normal debugging
- `120` if you want smoother real-time observation
- `30` or `60` first if the machine is under heavy load

Notes:

- The steady workflow passes this value to the `dxcam` monitor capture backend
- The GUI preview still applies its own refresh limit suitable for live rendering

### 4.2 Points / half-axis

This controls how many input points are scanned per half axis.

In the current version it affects two things:

- The number of raw measurement points on the positive `x` axis
- The density of the exported controller-driver half-axis curve

Recommendations:

- Quick preview: `9`
- Standard test: `17`
- High-density test: `33` or more

### 4.3 Settle (ms)

This is how long the tool waits after switching to a new input point before treating the system as stable.

In future real measurements, it affects:

- Whether the tool avoids the initial acceleration segment
- Whether the tool samples only the steady-state speed

Recommendations:

- Fast games: `200-300`
- Games with obvious camera smoothing: `400-800`

### 4.4 Steady Sample (ms)

This is the actual sampling duration used by `Run Steady` after each point has stabilized.

Recommendations:

- Rough test: `300-500`
- Standard test: `700-1000`
- High-stability requirement: `1000+`

### 4.5 Yaw360 Timeout (ms)

This is a reserved parameter for `Calibrate Yaw 360`. In the current public test build that button is disabled by default, so this parameter does not participate in actual execution yet.

Recommendations:

- Quick validation at high sensitivity: `2000-3000`
- Standard test: `4000-6000`
- Low sensitivity or slow-camera games: `6000+`

### 4.6 Repeats

This is the number of repeated samples for each point.

Recommendations:

- Quick test: `1`
- Standard test: `2`
- To compare variance: `3-5`

### 4.7 Inner deadzone

This marks the inner deadzone position.

In the current version it directly affects the starting input value of the default measurement points and also changes the preview curve shape. In the future it will also be used to:

- Display the estimated deadzone
- Help analyze the beginning segment of the input curve

### 4.8 Outer saturation

This marks the outer saturation position.

In the current version it directly affects the ending input value of the default measurement points and also changes the preview curve shape. In the future it will also be used to:

- Show when the curve enters saturation
- Help analyze whether the game compresses the outer input range

### 4.9 Enable dynamic response run

This indicates whether dynamic response testing will be enabled in the future.

In the current public test build, this option remains disabled and is reserved for future work.

### 4.10 Live preview during tests

This controls whether the live preview image and live motion data continue to update in the GUI while `Run Steady` or `Calibrate Idle Noise` is running. Once `Calibrate Yaw 360` is reopened, it will follow the same rule.

Default value: off.

Recommendations:

- Keep it off if you want to reduce measurement interference and lower GUI overhead
- Turn it on manually if you want to keep watching the image during the test

When it is off:

- The live image on the right pauses during measurement execution
- Real-time `vx / vy / pts / conf` updates also pause
- Live preview resumes automatically after the task finishes, fails, or is canceled

## 5. How to Export Results

After clicking `Export CSV`, the program exports four files:

- `raw_samples.csv`
- `curve_summary.csv`
- `session_meta.json`
- `controller_meta_curve.cmcurves.json`

In the current version:

- `raw_samples.csv`
  Records the raw measurement points on the positive `x` axis for the current session. In the public test build these mainly come from `Run Steady`, and each row also includes `measurement_kind` so you can distinguish the source.
- `curve_summary.csv`
  Records the recommended positive half-axis curve points for a controller driver, using `0..100 -> 0..100` coordinates, and also preserves `measurement_kind`.
- `session_meta.json`
  Stores the current configuration, status, raw results, and converted driver-curve results. `y_curve` is currently an empty list. The result object also records `measurement_kind`, `summary`, and `metadata`, where `metadata` includes `capture_fps_requested`, `retry_used_points`, and per-point `point_diagnostics`.
- `controller_meta_curve.cmcurves.json`
  Exports an additional `curve_transfer` package compatible with the JSON import format used by the ControllerMeta curve tool. By default, the recommended positive half-axis curve from `x_curve` is converted into a `polyline` that can be imported directly into the target tool.

## 6. How to Control It Through IPC

### 6.1 Check Service Health

```powershell
Invoke-RestMethod -Uri 'http://127.0.0.1:48231/health'
```

### 6.2 List Windows

```powershell
Invoke-RestMethod -Uri 'http://127.0.0.1:48231/windows'
```

### 6.3 Create a Session

```powershell
$session = Invoke-RestMethod `
  -Uri 'http://127.0.0.1:48231/session' `
  -Method Post `
  -ContentType 'application/json' `
  -Body '{"capture_fps":120,"point_count_per_half_axis":17}'
```

### 6.4 Update the ROI

```powershell
Invoke-RestMethod `
  -Uri ("http://127.0.0.1:48231/session/{0}/roi" -f $session.status.session_id) `
  -Method Post `
  -ContentType 'application/json' `
  -Body '{"x":200,"y":180,"width":240,"height":160}'
```

### 6.5 Run the Steady Workflow

```powershell
Invoke-RestMethod `
  -Uri ("http://127.0.0.1:48231/session/{0}/run/steady" -f $session.status.session_id) `
  -Method Post `
  -ContentType 'application/json' `
  -Body '{}'
```

### 6.6 Export Results

```powershell
Invoke-RestMethod `
  -Uri ("http://127.0.0.1:48231/session/{0}/export" -f $session.status.session_id) `
  -Method Post `
  -ContentType 'application/json' `
  -Body (@{ output_dir = '.\\gcp-export' } | ConvertTo-Json)
```

Notes:

- `POST /session/{id}/calibrate/yaw360`
  Returns `409` in the current public test build, which means the feature is not open yet.
- `POST /session/{id}/run/dynamic`
  Returns `409` in the current public test build, which means the feature is not open yet.

## 7. Recommendations During Testing

If you want future measurements to be as reliable as possible, it helps to build these habits early:

- Keep the game sensitivity fixed before the test and do not change it halfway through
- Use a separate test configuration and export directory for each game
- Prefer ROI regions with clear horizontal texture when observing `X / yaw`
- Repeat the same setup 2 to 3 times and compare result variance
- Avoid interference from character movement, recoil, camera shake, and similar effects

## 8. Current Known Limitations

- Steady capture is currently optimized only for single-monitor borderless-window scenarios
- Some protected windows or exclusive fullscreen windows may not be capturable
- `Run Dynamic` is disabled by default in the current public test build
- Steady measurement currently covers only the positive half of the `x` axis, not negative `x` or the `y` axis
- `Calibrate Yaw 360` is disabled by default in the current public test build

## 9. What Comes Next

The most important next implementation directions are:

1. Integrate the real virtual-controller backend
2. Continue improving the stability of background measurement, hotkeys, and system notifications
3. Continue improving steady `x`-axis measurement quality and export quality
4. Add real dynamic response testing and more accurate export fields
