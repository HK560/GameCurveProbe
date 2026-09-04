# README, Manual EXE Packaging, and ViGEmBus Detection Design

## Scope

This change delivers three related release-readiness improvements:

1. Make `README.md` English, add `README.zh-CN.md`, link the two versions, and remove emoji from both.
2. Add a manually triggered GitHub Actions workflow that builds and uploads `GameCurveProbe.exe`.
3. Warn users when ViGEmBus is unavailable, link to the official download releases, and allow the warning to be permanently dismissed in that browser.

## README Structure

`README.md` becomes the canonical English project page. `README.zh-CN.md` preserves the equivalent Chinese content. Each file includes a plain-text language selector linking to the other version. Commands, requirements, links, and feature coverage remain equivalent, and neither file contains emoji.

## Manual Windows Packaging

Create `.github/workflows/build-exe.yml` with `workflow_dispatch` as its only trigger. The job runs on `windows-latest`, checks out the repository, installs the required Python, uv, and Node.js versions, then invokes `scripts/build-exe.ps1` as the single source of build logic. The script continues to run frontend checks, Python tests, PyInstaller, and the executable smoke test.

After a successful build, the workflow uploads `dist/GameCurveProbe.exe` as a downloadable artifact. Failed validation or packaging prevents artifact upload.

## ViGEmBus Warning

The existing `/api/health` response already exposes `controller_ready`, derived from the virtual-controller backend's ability to load and connect through vgamepad/ViGEmBus. The frontend reuses this status instead of adding a second driver-detection mechanism.

After the initial health check, the application displays a dedicated modal when `controller_ready` is false and the user has not suppressed the warning. The modal:

- explains that ViGEmBus is required for virtual gamepad output;
- links to `https://github.com/nefarius/ViGEmBus/releases` in a new tab;
- provides a "Do not remind me again" checkbox;
- stores suppression in `localStorage` only when the user confirms dismissal.

The modal is bilingual through the existing i18n service. If the first-run tutorial is also pending, the tutorial starts only after the warning closes so the overlays do not conflict. Backend connection failures do not produce a false driver warning because the modal is evaluated only after a successful health response.

## Testing

- Static workflow tests assert that the workflow is manual-only, runs on Windows, invokes the existing build script, and uploads the EXE artifact.
- README tests assert the English and Chinese language links and absence of emoji.
- Frontend unit tests cover the suppression-storage helper and the warning decision for available, unavailable, dismissed, and failed-health states.
- Existing frontend and Python suites plus the production frontend build remain required verification gates.

## Non-Goals

- Automatic builds on push, pull request, tag, or release.
- GitHub Environment approval gates or code signing.
- Bundling or automatically installing ViGEmBus.
- Server-side persistence of the dismissal preference.
