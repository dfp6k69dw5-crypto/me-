# Physical Studio — Verification Protocol

This protocol exists to prevent “code changed” from being reported as “works.” A build is not considered verified until it passes the simulator and the manual device gate below.

## Status words

- **Prototype** — code exists, behavior is not yet verified.
- **Implemented** — feature is wired into the running app and automated checks pass where applicable.
- **Verified in simulator** — visual, interaction, physics, and audio simulator checks pass.
- **Verified on iPhone** — the user has confirmed the behavior on the target iPhone.
- Never use **fixed** or **works** for target-device behavior until the target-device gate has passed.

## Change discipline

1. Preserve a known-good commit before any risky change.
2. Change one subsystem at a time whenever possible: camera, scene interaction, physics, audio, or UI.
3. Do not mix a camera change with a UI/layout change in the same commit unless the change is inseparable.
4. After every change, run the simulator before sharing a test link.
5. A failed simulator check blocks the build. Fix it before asking the user to test.
6. If the same bug survives two attempted fixes, stop guessing. Research a proven implementation or reference before a third attempt.

## Simulator gate

Open `simulator.html` and run the full suite. The suite must test the deployed app, not a copied mockup.

### Boot and rendering
- App iframe loads without an uncaught error.
- WebGL canvas exists and has non-zero dimensions.
- A captured frame contains real visual variation (not a blank/solid canvas).
- Scene continues to render after interaction.

### Camera interaction
- Horizontal one-finger-style drag measurably changes the rendered frame.
- Vertical one-finger-style drag measurably changes the rendered frame.
- Repeated horizontal drags continue to change the scene rather than toggling between two orientations.
- Repeated vertical drags continue to change the scene.
- Zoom interaction changes the rendered frame without throwing.
- Camera movement must not cause NaN/blank rendering.

### UI interaction
- Palette buttons can be activated.
- Active tool state changes visibly.
- Inspector can be shown for a selectable object when the app exposes selection.
- UI remains inside the viewport at phone dimensions.
- No control may cover its own label/value.

### Physics
- A dynamic body changes position after excitation.
- Anchored bodies remain fixed.
- Spring endpoints continue to follow their bodies.
- Simulation does not produce NaN/Infinity after a stress interval.
- Reset returns to a finite stable state.

### Audio
- The actual `physics-worklet.js` is loaded into an AudioWorklet.
- A small test graph is sent to the worklet.
- Before excitation, measured output is near silence.
- After a `hit`, measurable non-zero RMS output appears.
- Output decays rather than remaining DC/full-scale.
- Left and right channels remain finite and below clipping threshold.

## Visual review gate

Automated pass is necessary but not sufficient. Before sending a build link:

1. Look at the simulator’s live app view at an iPhone-sized viewport.
2. Look at the captured “before” and “after” frames side by side.
3. Confirm that the intended object and controls are visually present and not overlapping.
4. Confirm the design still resembles the current reference direction: 3D workspace first, compact floating contextual inspectors, minimal permanent chrome.
5. If the simulator view looks ugly, crowded, clipped, or obviously wrong, do not send it merely because tests are green.

## Audio review gate

Before sharing a build that changes audio:

1. Run the worklet audio test.
2. Inspect the oscilloscope trace and RMS/peak readings.
3. Reject silence, DC offset, runaway full-scale output, NaN, or unstable sustained output.
4. If timbre is materially changed, report it as simulator-verified only; subjective sound quality still requires listening on a real device.

## Target iPhone gate

The simulator cannot perfectly reproduce iOS Safari, speaker response, touch hardware, or ChatGPT’s in-app browser. The final gate for touch feel and perceived sound is the actual iPhone.

When asking for device verification, name the exact behavior to test. Example: “Simulator passed horizontal and vertical orbit; please verify vertical orbit on iPhone.” Do not ask the user to retest unrelated features.

## Release checklist

A link may be presented as a verified candidate only when:

- [ ] Current source committed
- [ ] Simulator boot/render PASS
- [ ] Horizontal orbit PASS
- [ ] Vertical orbit PASS
- [ ] UI interaction PASS
- [ ] Physics stability PASS
- [ ] Audio worklet output PASS
- [ ] Visual review PASS
- [ ] No uncaught errors in simulator log
- [ ] Exact unverified target-device behaviors explicitly stated
