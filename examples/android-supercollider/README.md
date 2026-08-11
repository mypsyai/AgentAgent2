# PSYAI Android SuperCollider Backend

A production-ready Android audio backend that embeds SuperCollider synthesis into a C++/Kotlin application via JNI.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Kotlin UI Layer                       │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐  │
│  │  SCEngine   │  │   SCDsl     │  │ SynthDefBuilder │  │
│  │  (Wrapper)  │  │   (DSL)     │  │   (Generator)   │  │
│  └──────┬──────┘  └──────┬──────┘  └────────┬────────┘  │
└─────────┼────────────────┼──────────────────┼───────────┘
          │                │                  │
          ▼                ▼                  ▼
┌─────────────────────────────────────────────────────────┐
│                    JNI Bridge                            │
│  ┌──────────────────────────────────────────────────┐   │
│  │  sc_jni.cpp - Handle management, type conversion │   │
│  └──────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────────┐
│                  C++ Audio Backend                       │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐  │
│  │  SCEngine   │  │ OSCMessage  │  │ LockFreeQueue   │  │
│  │  (Core)     │  │  (Builder)  │  │   (RT-safe)     │  │
│  └──────┬──────┘  └─────────────┘  └─────────────────┘  │
│         │                                                │
│         ▼                                                │
│  ┌─────────────────────────────────────────────────┐    │
│  │              Oboe Audio Stream                   │    │
│  │     (Low-latency, exclusive mode, auto-restart)  │    │
│  └─────────────────────────────────────────────────┘    │
│         │                                                │
│         ▼                                                │
│  ┌─────────────────────────────────────────────────┐    │
│  │              SuperCollider World                 │    │
│  │     (scsynth embedded, UGen processing)          │    │
│  └─────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────┘
```

## Features

- **Lock-free command queue** for RT-safe synth control
- **Oboe integration** with exclusive mode and auto-restart
- **Kotlin DSL** for expressive synth programming
- **StateFlow metering** for reactive UI updates
- **Lifecycle-aware** engine management
- **SynthDef builder** for common synthesis patterns

## Usage

### Basic Usage

```kotlin
val sc = SCEngine(context)
lifecycle.addObserver(sc)

sc.start()

// Create a synth
val synth = sc.synth("sine") {
    set("freq", 440f)
    set("amp", 0.5f)
}

// Modify in real-time
synth.set("freq", 880f)

// Release
synth.free()
```

### Using the DSL

```kotlin
// Play with DSL
val synth = sc.play("sawFilter") {
    "freq" to 220
    "cutoff" to 1500
    "res" to 0.7
    ampDb(-6f)
    pan(-0.3f)
    gate(true)
}

// Play a note with auto-release
scope.launch {
    sc.note("sine", durationMs = 500) {
        freq(60)  // MIDI note
        "amp" to 0.5
    }
}

// Play a sequence
scope.launch {
    sc.sequence("sine", listOf(
        60 to 200L,
        62 to 200L,
        64 to 200L,
        65 to 400L
    ))
}
```

### Control Buses

```kotlin
// Set a control bus (accessible to all synths)
sc.setControlBus(0, 0.5f)

// Read back
val value = sc.getControlBus(0)
```

### Metering

```kotlin
@Composable
fun MeterDisplay(engine: SCEngine) {
    val peakL by engine.peakL.collectAsState()
    val peakR by engine.peakR.collectAsState()
    
    // Use peakL, peakR for visualization
}
```

## Project Structure

```
app/src/main/
├── cpp/
│   ├── CMakeLists.txt      # Build configuration
│   ├── SCEngine.h          # Core engine (header-only)
│   └── sc_jni.cpp          # JNI bridge
├── kotlin/cloud/psyai/sc/
│   ├── SCEngine.kt         # Kotlin wrapper
│   ├── SCDsl.kt            # DSL extensions
│   ├── SynthDefBuilder.kt  # SynthDef generator
│   └── MainActivity.kt     # Demo UI
└── AndroidManifest.xml
```

## Building

### Prerequisites

- Android Studio Hedgehog or newer
- NDK 25+ (installed via SDK Manager)
- CMake 3.22+ (installed via SDK Manager)

### Build Steps

```bash
# Clone and open in Android Studio
cd examples/android-supercollider
./gradlew assembleDebug

# Or build from command line
./gradlew installDebug
```

### SuperCollider Integration

For full SuperCollider support, you need to:

1. Build scsynth for Android (arm64-v8a, x86_64)
2. Place libraries in `app/src/main/jniLibs/{abi}/`
3. Update CMakeLists.txt to link against libscsynth.so
4. Pre-compile SynthDefs and include in assets

See [SuperCollider Android build instructions](https://github.com/supercollider/supercollider/wiki/Building-for-Android)

## Real-Time Safety

The engine maintains strict RT-safety in the audio callback:

- **No allocations** in audio thread
- **No locks** - uses lock-free queue for commands
- **No syscalls** - all I/O happens on command thread
- **Atomic operations** for parameter updates

## Performance Tips

1. **Pre-allocate synths** for polyphonic instruments
2. **Use control buses** for global parameters
3. **Batch parameter updates** with `setControls()`
4. **Minimize JNI crossings** in tight loops

## License

MIT License - See LICENSE file
