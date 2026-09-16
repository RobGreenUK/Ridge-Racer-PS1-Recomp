import SwiftUI
import AppKit

struct Settings: Codable, Equatable {
    var aspect = "4:3"
    var width = 1280
    var scale = 2
    var fullscreen = 0
    var filtering = "nearest"
    var antialiasing = true
    var perspective = false
    var vsync = "on"
    var blending = false
    var target = 0
    var lowLatency = true
    var rewind = false
    var nativeScene = false
    var nativeFullCourse = true
    var nativeCarDistance = 0
    var frameGraph = false
    var nativeFps = 60
    var nativeWidth = 960
    var nativeHeight = 720
}

@MainActor final class ServiceModel: ObservableObject {
    @Published var settings = Settings()
    @Published var running = false
    @Published var message = ""
    @Published var error = ""
    let root: URL
    private var process: Process?
    init() {
        // The runtime stages game.toml beside the app. It is not sufficient
        // to identify the source project; require the actual bridge as well.
        func isProject(_ location: URL) -> Bool {
            ["game.toml", "launcher/settings.py", "CMakeLists.txt"].allSatisfy {
                FileManager.default.fileExists(atPath: location.appendingPathComponent($0).path)
            }
        }
        var location = (Bundle.main.executableURL ?? URL(fileURLWithPath: CommandLine.arguments[0]))
            .resolvingSymlinksInPath().deletingLastPathComponent()
        if let override = ProcessInfo.processInfo.environment["RIDGE_PROJECT_ROOT"] {
            location = URL(fileURLWithPath: override).standardizedFileURL
        } else {
            while !isProject(location) && location.path != "/" {
                location.deleteLastPathComponent()
            }
        }
        root = location
        guard isProject(location) else {
            error = "Cannot find the Ridge Racer project. Keep this app in its build-macos folder, or set RIDGE_PROJECT_ROOT to the folder containing launcher/settings.py and game.toml."
            return
        }
        reload()
        if CommandLine.arguments.contains("--preview-native") { settings.nativeScene = true }
    }
    func helper(_ action: String) -> Process {
        let task = Process()
        let bundledPython = root.appendingPathComponent("runtime/python/bin/python3.13")
        if FileManager.default.fileExists(atPath: bundledPython.path) {
            task.executableURL = bundledPython
            var environment = ProcessInfo.processInfo.environment
            environment["PYTHONHOME"] = root.appendingPathComponent("runtime/python").path
            environment["PYTHONNOUSERSITE"] = "1"
            task.environment = environment
        } else {
            task.executableURL = URL(fileURLWithPath: "/opt/homebrew/bin/python3.13")
        }
        task.arguments = [root.appendingPathComponent("launcher/settings.py").path, action, "--root", root.path]
        task.currentDirectoryURL = root
        return task
    }
    func execute(_ action: String, input: Data? = nil) throws -> Data {
        let task = helper(action)
        let output = Pipe(), errors = Pipe(), stdin = Pipe()
        task.standardOutput = output; task.standardError = errors; task.standardInput = stdin
        try task.run()
        if let input { stdin.fileHandleForWriting.write(input) }
        try? stdin.fileHandleForWriting.close()
        let data = output.fileHandleForReading.readDataToEndOfFile()
        let failure = errors.fileHandleForReading.readDataToEndOfFile()
        task.waitUntilExit()
        guard task.terminationStatus == 0 else {
            throw NSError(domain: "ServiceMenu", code: Int(task.terminationStatus), userInfo: [NSLocalizedDescriptionKey: String(decoding: failure, as: UTF8.self)])
        }
        return data
    }
    func reload() {
        do { settings = try JSONDecoder().decode(Settings.self, from: execute("read")) }
        catch { self.error = error.localizedDescription }
    }
    @discardableResult func save() -> Bool {
        do {
            _ = try execute("save", input: JSONEncoder().encode(settings))
            message = "Settings saved for your next launch."
            return true
        } catch { self.error = error.localizedDescription; return false }
    }
    func launch(advanced: Bool = false) {
        guard save() else { return }
        let task = helper(advanced ? "advanced" : "launch")
        let errors = Pipe()
        task.standardError = errors
        task.standardOutput = FileHandle.nullDevice
        task.terminationHandler = { [weak self] task in
            let text = String(decoding: errors.fileHandleForReading.readDataToEndOfFile(), as: UTF8.self)
            Task { @MainActor in
                guard let self else { return }
                self.running = false
                self.process = nil
                if task.terminationStatus != 0 { self.error = text }
                self.reload()
                self.message = "Game closed. Settings are ready for the next launch."
                NSApp.activate(ignoringOtherApps: true)
            }
        }
        do {
            try task.run(); process = task; running = true
            message = "Game running. Close its window to return to the service menu."
        } catch { self.error = error.localizedDescription }
    }
}

struct ServiceView: View {
    @StateObject var model = ServiceModel()
    @State private var tab = CommandLine.arguments.contains("--preview-image") ? "Image" : (CommandLine.arguments.contains("--preview-native") ? "Motion" : "Display")
    @State private var nativeWidthInput = ""
    let red = Color(red: 0.94, green: 0.24, blue: 0.20)
    var body: some View {
        VStack(spacing: 0) {
            HStack(alignment: .top) {
                VStack(alignment: .leading, spacing: 5) {
                    Text("RIDGE RACER").font(.system(size: 34, weight: .black, design: .rounded)).italic()
                    Text("SERVICE MENU   /   USA · SCUS-94300").font(.system(size: 11, weight: .semibold, design: .monospaced)).tracking(1.7).foregroundStyle(.secondary)
                }
                Spacer()
                Label("APPLE SILICON", systemImage: "desktopcomputer").font(.system(size: 10, weight: .bold)).padding(9).background(.white.opacity(0.07), in: Capsule())
            }.padding(28)
            Rectangle().fill(red).frame(height: 3)
            HStack(spacing: 0) {
                VStack(alignment: .leading, spacing: 9) {
                    ForEach(["Display", "Image", "Motion", "Controls"], id: \.self) { name in
                        Button { tab = name } label: {
                            HStack { Image(systemName: icon(name)).frame(width: 20); Text(name); Spacer() }
                                .padding(12).background(tab == name ? red.opacity(0.22) : .clear, in: RoundedRectangle(cornerRadius: 8))
                        }.buttonStyle(.plain).foregroundStyle(tab == name ? .white : .secondary)
                    }
                    Spacer()
                    Text("ORIGINAL TIMING\n59.94 Hz guest clock").font(.system(size: 10, design: .monospaced)).foregroundStyle(.secondary).lineSpacing(4)
                    Text("Presentation settings never overclock the game.").font(.caption).foregroundStyle(.secondary).fixedSize(horizontal: false, vertical: true)
                }.padding(18).frame(width: 190).background(.black.opacity(0.16))
                ScrollView {
                    VStack(alignment: .leading, spacing: 20) {
                        Text(tab).font(.title2.bold())
                        Group {
                            switch tab {
                            case "Display": display
                            case "Image": image
                            case "Motion": motion
                            default: controls
                            }
                        }.disabled(model.running)
                    }.padding(26).frame(maxWidth: .infinity, alignment: .leading)
                }
            }
            Divider()
            HStack {
                VStack(alignment: .leading, spacing: 3) {
                    Text(model.running ? "ON TRACK" : "READY TO RACE").font(.system(size: 10, weight: .bold, design: .monospaced)).foregroundStyle(red)
                    Text(model.message.isEmpty ? "Choose your settings, then start your engine." : model.message).font(.caption).foregroundStyle(.secondary)
                }
                Spacer()
                Button("Save") { model.save() }.disabled(model.running)
                Button(model.running ? "Running…" : "Launch game  →") { model.launch() }
                    .buttonStyle(.borderedProminent).tint(red).disabled(model.running).keyboardShortcut(.defaultAction)
            }.padding(22)
        }.onChange(of: model.settings.aspect) { _ in alignNativeResolution() }
            .onChange(of: model.settings.nativeScene) { _ in alignNativeResolution() }
            .frame(minWidth: 820, idealWidth: 860, minHeight: 650, idealHeight: 690)
            .background(Color(red: 0.075, green: 0.085, blue: 0.105)).preferredColorScheme(.dark)
            .alert("Unable to complete action", isPresented: Binding(get: { !model.error.isEmpty }, set: { if !$0 { model.error = "" } })) {
                Button("OK") { model.error = "" }
            } message: { Text(model.error) }
    }
    func icon(_ s: String) -> String {
        ["Display":"display", "Image":"slider.horizontal.3", "Motion":"speedometer", "Controls":"gamecontroller"][s]!
    }
    func note(_ text: String) -> some View { Text(text).font(.callout).foregroundStyle(.secondary).fixedSize(horizontal: false, vertical: true) }
    func alignNativeResolution() {
        guard model.settings.nativeScene else { return }
        if model.settings.aspect == "adaptive" { model.settings.aspect = "16:9" }
        let a = model.settings.aspect == "4:3" ? 4 : 16
        let b = model.settings.aspect == "4:3" ? 3 : 9
        let units = max((240+b-1)/b, min(min(7680/a,4320/b),Int((Double(model.settings.nativeHeight)/Double(b)).rounded())))
        model.settings.nativeWidth = units*a; model.settings.nativeHeight = units*b
    }
    func applyNativeWidth() {
        guard let value = Int(nativeWidthInput) else {
            model.error = "Enter a whole-number rendering width."; return
        }
        let a = model.settings.aspect == "4:3" ? 4 : 16
        let b = model.settings.aspect == "4:3" ? 3 : 9
        let units = max((240+b-1)/b,min(min(7680/a,4320/b),Int((Double(value)/Double(a)).rounded())))
        model.settings.nativeWidth = units*a; model.settings.nativeHeight = units*b
        nativeWidthInput = String(model.settings.nativeWidth)
    }
    var nativeResolution: some View {
        let a = model.settings.aspect == "4:3" ? 4 : 16
        let b = model.settings.aspect == "4:3" ? 3 : 9
        let presets = a == 4 ? [640,800,960,1024,1280,1440,1600,1920,2560,2880,3840,5760] : [640,960,1280,1600,1920,2560,3200,3840,5120,7680]
        let widths = Array(Set(presets + [model.settings.nativeWidth])).sorted()
        let selection = Binding<Int>(get: { model.settings.nativeWidth }, set: { value in
            model.settings.nativeWidth = value; model.settings.nativeHeight = value/a*b
        })
        return VStack(alignment: .leading, spacing: 14) {
            Picker("Render resolution", selection: selection) {
                ForEach(widths, id: \.self) { width in Text("\(width) × \(width/a*b)").tag(width) }
            }
            HStack {
                Text("Custom width")
                Spacer()
                TextField("Pixels", text: $nativeWidthInput)
                    .frame(width: 100).textFieldStyle(.roundedBorder).onSubmit { applyNativeWidth() }
                Button("Apply") { applyNativeWidth() }
                Text("× \(model.settings.nativeHeight)")
            }
            note("Only \(model.settings.aspect) resolutions are available. Apply a custom width to calculate a matching height. These are actual rendering pixels.")
        }.onAppear { nativeWidthInput = String(model.settings.nativeWidth) }
            .onChange(of: model.settings.nativeWidth) { value in nativeWidthInput = String(value) }
    }
    var display: some View {
        VStack(alignment: .leading, spacing: 18) {

            Picker("Aspect ratio", selection: $model.settings.aspect) {
                Text("Original · 4:3").tag("4:3")
                Text("Widescreen · 16:9 (experimental)").tag("16:9")
                if !model.settings.nativeScene { Text("Adaptive · window shape").tag("adaptive") }
            }
            if model.settings.nativeScene {
                nativeResolution
                Toggle("Full course visibility", isOn: $model.settings.nativeFullCourse)
                Picker("CPU car draw distance", selection: $model.settings.nativeCarDistance) {
                    Text("All cars · unlimited").tag(0)
                    Text("1× · original").tag(1)
                    Text("2×").tag(2)
                    Text("3×").tag(3)
                    Text("4× · extended").tag(4)
                    Text("5×").tag(5)
                }
                note("VSync also applies to native rendering and limits presentation to the display refresh rate. Frame timings are recorded locally during native play. Press P (or F8) when you spot a bug to save a screenshot and replayable scene snapshot.")
                note("Full course removes scenery distance limits. All cars removes car distance limits. Buildings still hide objects behind them. Saved for the next launch.")
            } else {
            note("Widescreen reveals more of the 3D view. Menus retain their original proportions. Side visibility and HUD placement are still being tested.")
            HStack {
                Text("Window width")
                Spacer()
                TextField("640–3840", value: $model.settings.width, format: .number.grouping(.never)).frame(width: 90).textFieldStyle(.roundedBorder)
                Text("points").foregroundStyle(.secondary)
            }
            note("Height follows the selected aspect ratio. macOS Retina scaling determines the window’s physical pixel size; internal rendering resolution is separate.")
            Picker("Internal resolution", selection: $model.settings.scale) {
                Text("1× · original detail").tag(1)
                Text("2× · balanced").tag(2)
                Text("3× · high").tag(3)
                Text("4× · maximum").tag(4)
            }
            note("At 4:3, the game’s 320 × 240 buffer becomes \(320 * model.settings.scale) × \(240 * model.settings.scale). Widescreen adds horizontal detail. Higher scales cost more GPU time.")
            }
            Picker("Window mode", selection: $model.settings.fullscreen) {
                Text("Windowed").tag(0); Text("Borderless fullscreen").tag(1); Text("Exclusive fullscreen").tag(2)
            }
            if !model.settings.nativeScene {
            Divider()
            HStack {
                Text("Quick preset").foregroundStyle(.secondary)
                Button("Original") { model.settings = Settings(); model.settings.scale = 1; model.settings.antialiasing = false }
                Button("Crisp 2×") { model.settings.scale = 2; model.settings.filtering = "nearest"; model.settings.antialiasing = true }
            }
            }
        }
    }
    var image: some View {
        VStack(alignment: .leading, spacing: 18) {
            if !model.settings.nativeScene {
                Picker("Texture filtering", selection: $model.settings.filtering) {
                    Text("Nearest · sharp texels").tag("nearest"); Text("Bilinear · softer textures").tag("bilinear")
                }
                Toggle("Antialiasing", isOn: $model.settings.antialiasing)
            }
            Toggle("Perspective-correct textures", isOn: $model.settings.perspective)
            if model.settings.nativeScene {
                note("On: textures stay stable as surfaces recede into the distance. Off: affine texture mapping recreates the PlayStation’s texture warping. Applies when you launch the game.")
            } else {
                note("Reduces texture warping where the original renderer can identify projected 3D polygons. Coverage varies by scene.")
            }
        }
    }
    var motion: some View {
        VStack(alignment: .leading, spacing: 18) {
            Toggle("Native scene rendering (experimental)", isOn: $model.settings.nativeScene)
            note("Draws fresh geometry frames from the original camera and car motion, including the track, skyline and cars. Physics, race timers and audio retain their original timing.")
            if model.settings.nativeScene {
                HStack {
                    Text("Frames per second")
                    Spacer()
                    TextField("0 = display", value: $model.settings.nativeFps, format: .number.grouping(.never)).frame(width: 85).textFieldStyle(.roundedBorder)
                }
                HStack {
                    Text("Quick target")
                    Button("Display") { model.settings.nativeFps = 0 }
                    ForEach([60, 120, 144], id: \.self) { value in
                        Button("\(value) fps") { model.settings.nativeFps = value }
                    }
                }
                Toggle("Developer frame-time graph (G)", isOn: $model.settings.frameGraph)
                note("Display matches your monitor’s refresh rate. G toggles the five-second graph while playing; P captures it with the scene.")
                note("Aspect ratio and matching render resolutions are configured together in Display.")
                note("Menus and the original HUD appear in the native view. The original game also runs in a companion window for audio and simulation. Lighting, some effects and draw ordering are still being refined. Close either window to end the session.")
                note("Enter → Start · Arrows → Steer · X / Space → Accelerate · Z → Brake. Click the native view to use its keyboard controls. Your display must support the selected refresh rate to show every frame.")
            } else {
                Toggle("Legacy temporal blending", isOn: $model.settings.blending)
                Picker("Blending target", selection: $model.settings.target) {
                    Text("Display refresh").tag(0)
                    ForEach([60,90,120,144,165,240], id: \.self) { value in Text("\(value) presents / second").tag(value) }
                }.disabled(!model.settings.blending)
                note("Blending mixes adjacent images and can cause ghosting. Select native scene rendering above for new geometry frames.")
            }
            Picker("VSync", selection: $model.settings.vsync) {
                Text("On").tag("on"); Text("Off").tag("off"); Text("Adaptive").tag("adaptive")
            }.disabled(model.settings.blending && !model.settings.nativeScene)
            Toggle("Low-latency controller sampling", isOn: $model.settings.lowLatency)
            note("Refreshes original-runtime controller and keyboard input after its pacing wait. Native-window keyboard input already uses the latest sample at the game’s pad read. This does not change the physics tick rate.")
            if model.settings.blending && !model.settings.nativeScene { note("Temporal blending controls presentation pacing and overrides VSync while enabled.") }

        }
    }
    var controls: some View {
        VStack(alignment: .leading, spacing: 18) {
            Text("Keyboard & gamepad").font(.headline)
            note("Return → Start     Arrows → Steer\nX → Accelerate     Z → Brake\nA → Triangle     S → Circle")
            Toggle("Enable rewind (uses additional memory)", isOn: $model.settings.rewind)
            note("When enabled, use F8 to rewind. In the native window, P or F8 saves a bug capture. Rewind requires focus on the original companion window. Save states, hotkeys, audio, controller bindings and mod management are available in the advanced launcher.")
            Button("Open advanced settings…") { model.launch(advanced: true) }.buttonStyle(.bordered)
            note("Opens PSXRecomp’s full launcher. Settings changed there are reloaded here when it closes. Close the game before changing its configuration.")
            Divider()
            Button("Show settings file") { NSWorkspace.shared.activateFileViewerSelecting([model.root.appendingPathComponent("build-macos/settings.toml")]) }
        }
    }
}

@main struct RidgeServiceApp: App {
    init() {
        // Exercise the same project discovery and Python bridge as a real
        // launch, without opening a window or modifying player preferences.
        if CommandLine.arguments.contains("--check-settings") {
            let model = ServiceModel()
            guard model.error.isEmpty else {
                FileHandle.standardError.write(Data((model.error + "\n").utf8))
                exit(1)
            }
            print(model.root.path)
            if let data = try? JSONEncoder().encode(model.settings) {
                print(String(decoding: data, as: UTF8.self))
            }
            exit(0)
        }
        // Render our own SwiftUI view for layout QA without screen capture.
        if let index = CommandLine.arguments.firstIndex(of: "--render-preview"), CommandLine.arguments.count > index + 1 {
            let view = NSHostingView(rootView: ServiceView().environment(\.colorScheme, .dark).frame(width: 860, height: 690))
            view.frame = NSRect(x: 0, y: 0, width: 860, height: 690)
            view.appearance = NSAppearance(named: .darkAqua)
            view.layoutSubtreeIfNeeded()
            if let rep = view.bitmapImageRepForCachingDisplay(in: view.bounds) {
                view.cacheDisplay(in: view.bounds, to: rep)
                if let png = rep.representation(using: .png, properties: [:]) {
                    try? png.write(to: URL(fileURLWithPath: CommandLine.arguments[index + 1]))
                }
            }
            exit(0)
        }
    }
    var body: some Scene {
        Window("Ridge Racer · Service Menu", id: "service") { ServiceView() }
            .windowResizability(.contentMinSize)
            .defaultSize(width: 860, height: 690)
    }
}
