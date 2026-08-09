import UIKit
import AVFoundation
import Photos

final class MacroFocusViewController: UIViewController, AVCapturePhotoCaptureDelegate {
    private let session = AVCaptureSession()
    private let sessionQueue = DispatchQueue(label: "macrofocus.camera.session")
    private let photoOutput = AVCapturePhotoOutput()

    private var camera: AVCaptureDevice?
    private var previewLayer: AVCaptureVideoPreviewLayer!
    private var focusPollTimer: Timer?
    private var lastLensPosition: Float = -1
    private var stableFocusTicks = 0
    private var cameraAuthorized = false

    private let topShade = CAGradientLayer()
    private let bottomShade = CAGradientLayer()

    private let titleLabel: UILabel = {
        let label = UILabel()
        label.text = "MACRO"
        label.font = UIFont.systemFont(ofSize: 13, weight: .semibold)
        label.textColor = UIColor.white.withAlphaComponent(0.92)
        label.textAlignment = .center
        label.translatesAutoresizingMaskIntoConstraints = false
        return label
    }()

    private let statusLabel: UILabel = {
        let label = UILabel()
        label.text = "SEARCHING"
        label.font = UIFont.monospacedDigitSystemFont(ofSize: 11, weight: .medium)
        label.textColor = UIColor.white.withAlphaComponent(0.78)
        label.textAlignment = .center
        label.translatesAutoresizingMaskIntoConstraints = false
        return label
    }()

    private let distanceLabel: UILabel = {
        let label = UILabel()
        label.text = "NEAR FOCUS"
        label.font = UIFont.monospacedDigitSystemFont(ofSize: 9, weight: .regular)
        label.textColor = UIColor.white.withAlphaComponent(0.52)
        label.textAlignment = .center
        label.translatesAutoresizingMaskIntoConstraints = false
        return label
    }()

    private let reticleView = FocusReticleView()

    private let shutterButton: UIButton = {
        let button = UIButton(type: .custom)
        button.translatesAutoresizingMaskIntoConstraints = false
        button.backgroundColor = .clear
        button.layer.cornerRadius = 35
        button.layer.borderWidth = 3
        button.layer.borderColor = UIColor.white.cgColor
        button.accessibilityLabel = "Take photo"
        return button
    }()

    private let huntButton: UIButton = {
        let button = UIButton(type: .system)
        button.setTitle("HUNT", for: .normal)
        button.setTitleColor(.white, for: .normal)
        button.titleLabel?.font = UIFont.systemFont(ofSize: 11, weight: .semibold)
        button.backgroundColor = UIColor.black.withAlphaComponent(0.28)
        button.layer.cornerRadius = 18
        button.layer.borderWidth = 1
        button.layer.borderColor = UIColor.white.withAlphaComponent(0.18).cgColor
        button.translatesAutoresizingMaskIntoConstraints = false
        return button
    }()

    override func viewDidLoad() {
        super.viewDidLoad()
        view.backgroundColor = .black
        configurePreview()
        configureInterface()
        requestCameraAccessAndStart()
    }

    override func viewDidLayoutSubviews() {
        super.viewDidLayoutSubviews()
        previewLayer.frame = view.bounds
        topShade.frame = CGRect(x: 0, y: 0, width: view.bounds.width, height: 150)
        bottomShade.frame = CGRect(x: 0, y: max(0, view.bounds.height - 190), width: view.bounds.width, height: 190)
    }

    override var prefersStatusBarHidden: Bool { true }

    deinit {
        focusPollTimer?.invalidate()
        sessionQueue.async { [session] in
            if session.isRunning { session.stopRunning() }
        }
    }

    private func configurePreview() {
        previewLayer = AVCaptureVideoPreviewLayer(session: session)
        previewLayer.videoGravity = .resizeAspectFill
        view.layer.addSublayer(previewLayer)

        topShade.colors = [UIColor.black.withAlphaComponent(0.58).cgColor, UIColor.clear.cgColor]
        topShade.locations = [0, 1]
        view.layer.addSublayer(topShade)

        bottomShade.colors = [UIColor.clear.cgColor, UIColor.black.withAlphaComponent(0.68).cgColor]
        bottomShade.locations = [0, 1]
        view.layer.addSublayer(bottomShade)
    }

    private func configureInterface() {
        reticleView.translatesAutoresizingMaskIntoConstraints = false
        view.addSubview(reticleView)
        view.addSubview(titleLabel)
        view.addSubview(statusLabel)
        view.addSubview(distanceLabel)
        view.addSubview(shutterButton)
        view.addSubview(huntButton)

        NSLayoutConstraint.activate([
            titleLabel.topAnchor.constraint(equalTo: view.safeAreaLayoutGuide.topAnchor, constant: 12),
            titleLabel.centerXAnchor.constraint(equalTo: view.centerXAnchor),

            reticleView.centerXAnchor.constraint(equalTo: view.centerXAnchor),
            reticleView.centerYAnchor.constraint(equalTo: view.centerYAnchor, constant: -22),
            reticleView.widthAnchor.constraint(equalToConstant: 104),
            reticleView.heightAnchor.constraint(equalToConstant: 104),

            statusLabel.topAnchor.constraint(equalTo: reticleView.bottomAnchor, constant: 18),
            statusLabel.centerXAnchor.constraint(equalTo: view.centerXAnchor),
            distanceLabel.topAnchor.constraint(equalTo: statusLabel.bottomAnchor, constant: 5),
            distanceLabel.centerXAnchor.constraint(equalTo: view.centerXAnchor),

            shutterButton.widthAnchor.constraint(equalToConstant: 70),
            shutterButton.heightAnchor.constraint(equalToConstant: 70),
            shutterButton.centerXAnchor.constraint(equalTo: view.centerXAnchor),
            shutterButton.bottomAnchor.constraint(equalTo: view.safeAreaLayoutGuide.bottomAnchor, constant: -22),

            huntButton.centerYAnchor.constraint(equalTo: shutterButton.centerYAnchor),
            huntButton.trailingAnchor.constraint(equalTo: view.trailingAnchor, constant: -22),
            huntButton.widthAnchor.constraint(equalToConstant: 76),
            huntButton.heightAnchor.constraint(equalToConstant: 36)
        ])

        shutterButton.addTarget(self, action: #selector(capturePhoto), for: .touchUpInside)
        huntButton.addTarget(self, action: #selector(huntNearFocus), for: .touchUpInside)

        let tap = UITapGestureRecognizer(target: self, action: #selector(focusTapped(_:)))
        view.addGestureRecognizer(tap)
    }

    private func requestCameraAccessAndStart() {
        switch AVCaptureDevice.authorizationStatus(for: .video) {
        case .authorized:
            cameraAuthorized = true
            startCamera()
        case .notDetermined:
            AVCaptureDevice.requestAccess(for: .video) { [weak self] allowed in
                guard let self = self else { return }
                self.cameraAuthorized = allowed
                allowed ? self.startCamera() : self.showCameraDenied()
            }
        default:
            showCameraDenied()
        }
    }

    private func startCamera() {
        sessionQueue.async { [weak self] in
            guard let self = self else { return }

            self.session.beginConfiguration()
            self.session.sessionPreset = .photo

            guard let device = AVCaptureDevice.default(.builtInWideAngleCamera, for: .video, position: .back),
                  let input = try? AVCaptureDeviceInput(device: device),
                  self.session.canAddInput(input) else {
                self.session.commitConfiguration()
                DispatchQueue.main.async { self.showCameraUnavailable() }
                return
            }

            self.camera = device
            self.session.addInput(input)

            if self.session.canAddOutput(self.photoOutput) {
                self.session.addOutput(self.photoOutput)
                self.photoOutput.isHighResolutionCaptureEnabled = true
            }

            self.configureMacroAutofocus(device, point: CGPoint(x: 0.5, y: 0.5))
            self.session.commitConfiguration()
            self.session.startRunning()

            DispatchQueue.main.async {
                self.beginFocusPolling()
                self.animateSearching()
            }
        }
    }

    private func configureMacroAutofocus(_ device: AVCaptureDevice, point: CGPoint) {
        do {
            try device.lockForConfiguration()

            if device.isAutoFocusRangeRestrictionSupported {
                device.autoFocusRangeRestriction = .near
            }

            if device.isSmoothAutoFocusSupported {
                device.isSmoothAutoFocusEnabled = false
            }

            if device.isFocusPointOfInterestSupported {
                device.focusPointOfInterest = point
            }

            if device.isFocusModeSupported(.continuousAutoFocus) {
                device.focusMode = .continuousAutoFocus
            } else if device.isFocusModeSupported(.autoFocus) {
                device.focusMode = .autoFocus
            }

            if device.isExposurePointOfInterestSupported {
                device.exposurePointOfInterest = point
            }
            if device.isExposureModeSupported(.continuousAutoExposure) {
                device.exposureMode = .continuousAutoExposure
            }

            device.unlockForConfiguration()
        } catch {
            DispatchQueue.main.async { [weak self] in
                self?.statusLabel.text = "FOCUS ERROR"
            }
        }
    }

    @objc private func focusTapped(_ gesture: UITapGestureRecognizer) {
        guard gesture.state == .ended,
              let device = camera,
              session.isRunning else { return }

        let viewPoint = gesture.location(in: view)
        let devicePoint = previewLayer.captureDevicePointConverted(fromLayerPoint: viewPoint)
        configureMacroAutofocus(device, point: devicePoint)

        reticleView.center = viewPoint
        animateSearching()
    }

    @objc private func huntNearFocus() {
        guard let device = camera else { return }
        configureMacroAutofocus(device, point: CGPoint(x: 0.5, y: 0.5))

        UIView.animate(withDuration: 0.2, animations: {
            self.reticleView.center = CGPoint(x: self.view.bounds.midX, y: self.view.bounds.midY - 22)
        })
        animateSearching()
    }

    private func beginFocusPolling() {
        focusPollTimer?.invalidate()
        focusPollTimer = Timer.scheduledTimer(withTimeInterval: 0.10, repeats: true) { [weak self] _ in
            self?.refreshFocusState()
        }
    }

    private func refreshFocusState() {
        guard let device = camera else { return }

        if device.isAdjustingFocus {
            stableFocusTicks = 0
            statusLabel.text = "SEARCHING"
            reticleView.setLocked(false)
            return
        }

        let current = device.lensPosition
        let delta = abs(current - lastLensPosition)
        lastLensPosition = current

        if delta < 0.002 {
            stableFocusTicks += 1
        } else {
            stableFocusTicks = 0
        }

        if stableFocusTicks >= 3 {
            statusLabel.text = "SHARP"
            reticleView.setLocked(true)
        } else {
            statusLabel.text = "SETTLING"
        }

        let nearPercent = max(0, min(100, Int((1.0 - current) * 100.0)))
        distanceLabel.text = "NEAR \(nearPercent)%"
    }

    private func animateSearching() {
        statusLabel.text = "SEARCHING"
        stableFocusTicks = 0
        reticleView.beginSearchAnimation()
    }

    @objc private func capturePhoto() {
        guard cameraAuthorized, session.isRunning else { return }

        let settings = AVCapturePhotoSettings()
        settings.isHighResolutionPhotoEnabled = true

        shutterButton.isEnabled = false
        UIView.animate(withDuration: 0.08, animations: {
            self.shutterButton.transform = CGAffineTransform(scaleX: 0.86, y: 0.86)
        }) { _ in
            UIView.animate(withDuration: 0.12) {
                self.shutterButton.transform = .identity
            }
        }

        photoOutput.capturePhoto(with: settings, delegate: self)
    }

    func photoOutput(_ output: AVCapturePhotoOutput, didFinishProcessingPhoto photo: AVCapturePhoto, error: Error?) {
        defer { DispatchQueue.main.async { self.shutterButton.isEnabled = true } }
        guard error == nil, let data = photo.fileDataRepresentation() else { return }

        PHPhotoLibrary.requestAuthorization { status in
            guard status == .authorized else { return }
            PHPhotoLibrary.shared().performChanges({
                let request = PHAssetCreationRequest.forAsset()
                request.addResource(with: .photo, data: data, options: nil)
            }, completionHandler: nil)
        }
    }

    private func showCameraDenied() {
        DispatchQueue.main.async {
            self.statusLabel.text = "CAMERA ACCESS NEEDED"
            self.distanceLabel.text = "Settings → Privacy → Camera"
            self.reticleView.setLocked(false)
        }
    }

    private func showCameraUnavailable() {
        statusLabel.text = "CAMERA UNAVAILABLE"
        distanceLabel.text = "BACK CAMERA REQUIRED"
        reticleView.setLocked(false)
    }
}

private final class FocusReticleView: UIView {
    private let ring = CAShapeLayer()
    private let centerDot = CAShapeLayer()
    private var locked = false

    override init(frame: CGRect) {
        super.init(frame: frame)
        isUserInteractionEnabled = false
        backgroundColor = .clear
        layer.addSublayer(ring)
        layer.addSublayer(centerDot)
    }

    required init?(coder: NSCoder) {
        fatalError("init(coder:) has not been implemented")
    }

    override func layoutSubviews() {
        super.layoutSubviews()
        let inset: CGFloat = 9
        let rect = bounds.insetBy(dx: inset, dy: inset)

        ring.path = UIBezierPath(ovalIn: rect).cgPath
        ring.fillColor = UIColor.clear.cgColor
        ring.strokeColor = UIColor.white.withAlphaComponent(0.88).cgColor
        ring.lineWidth = 1.2
        ring.lineDashPattern = [3, 7]

        let dotRect = CGRect(x: bounds.midX - 2, y: bounds.midY - 2, width: 4, height: 4)
        centerDot.path = UIBezierPath(ovalIn: dotRect).cgPath
        centerDot.fillColor = UIColor.white.withAlphaComponent(0.92).cgColor
    }

    func beginSearchAnimation() {
        locked = false
        layer.removeAllAnimations()
        ring.strokeColor = UIColor.white.withAlphaComponent(0.82).cgColor

        transform = CGAffineTransform(scaleX: 1.20, y: 1.20)
        alpha = 0.65
        UIView.animate(
            withDuration: 0.72,
            delay: 0,
            options: [.curveEaseOut, .beginFromCurrentState],
            animations: {
                self.transform = .identity
                self.alpha = 1
            }
        )

        let rotation = CABasicAnimation(keyPath: "transform.rotation")
        rotation.fromValue = 0
        rotation.toValue = Double.pi * 2
        rotation.duration = 2.4
        rotation.repeatCount = .infinity
        ring.add(rotation, forKey: "searchRotation")
    }

    func setLocked(_ value: Bool) {
        guard value != locked else { return }
        locked = value

        if value {
            ring.removeAnimation(forKey: "searchRotation")
            ring.lineDashPattern = nil
            ring.strokeColor = UIColor.white.cgColor
            UIView.animate(withDuration: 0.12, animations: {
                self.transform = CGAffineTransform(scaleX: 0.94, y: 0.94)
            }) { _ in
                UIView.animate(withDuration: 0.18) { self.transform = .identity }
            }
        } else {
            ring.lineDashPattern = [3, 7]
            ring.strokeColor = UIColor.white.withAlphaComponent(0.82).cgColor
        }
    }
}
