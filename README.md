# GameCurveProbe

GameCurveProbe is a Windows-focused game controller input curve probing tool. Its goal is to measure the relationship between right-stick input values and in-game camera movement or turn speed.

For more detailed instructions, see:

- [User Guide](docs/USER_GUIDE.md)

## Requirements

- Windows 10/11
- `uv`
- `ViGEmBus` must be installed, along with an environment that includes the `vgamepad` dependency
- The target game is recommended to run in windowed or borderless mode

## Installation and Running

Sync dependencies for the first time:

```powershell
uv sync --extra capture --extra controller
```

Launch the desktop UI:

```powershell
uv run gamecurveprobe
```

Start only the local IPC service:

```powershell
uv run gamecurveprobe --ipc-only
```

Specify the IPC port:

```powershell
uv run gamecurveprobe --port 49200
```

If the current environment does not have write access to the default `uv` cache directory, you can place the cache inside the repository:

```powershell
$env:UV_CACHE_DIR='d:\Github\GameCurveProbe\.uv-cache'
uv sync --extra capture --extra controller
uv run gamecurveprobe
```
