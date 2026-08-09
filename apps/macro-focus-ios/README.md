# Macro Focus — iPhone 6 near-subject camera

A tiny native iPhone camera app with one job: make nearby small subjects easier to focus on.

## What it does

- Uses the rear wide camera at full photo resolution.
- Requests AVFoundation's **near autofocus range restriction** when the camera supports it.
- Uses continuous autofocus and a center-weighted focus point by default.
- Tap anywhere to move the focus/exposure target to a tiny subject.
- **HUNT** instantly returns the focus target to the center and re-engages near-biased autofocus.
- Shows `SEARCHING`, `SETTLING`, and `SHARP` states based on the camera's real focus activity and lens stability.
- Displays a live near-focus percentage derived from the hardware lens position.
- Saves full-resolution stills to Photos.
- Full-screen, minimal UI intended for an iPhone 6-sized display.

## Important physical limit

This app can bias and control the iPhone's real autofocus system, but software cannot move the lens closer than the camera hardware allows. If the subject is inside the physical minimum focus distance, back the phone away slightly until `SHARP` appears. A clip-on macro lens can extend what the app can photograph, and the same near-focus behavior still helps.

## Build

This is a native iOS project rather than a GitHub Pages web app because browser camera APIs do not expose the same reliable near-focus hardware controls.

The project targets **iOS 12.0+** for iPhone 6 compatibility.

1. On a Mac, install Xcode and XcodeGen.
2. From this folder, run `xcodegen generate`.
3. Open `MacroFocus.xcodeproj` in Xcode.
4. Select your Apple development team under Signing & Capabilities.
5. Connect the iPhone and Run.

## Files

- `MacroFocus/AppDelegate.swift` — app entry point.
- `MacroFocus/MacroFocusViewController.swift` — camera, autofocus, capture, and UI.
- `MacroFocus/Info.plist` — camera/photo permissions and app metadata.
- `project.yml` — reproducible Xcode project definition.
