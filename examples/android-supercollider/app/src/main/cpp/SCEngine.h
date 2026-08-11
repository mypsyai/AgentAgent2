/**
 * PSYAI SuperCollider Android Backend
 * 
 * Embeds scsynth (SuperCollider synthesis server) into Android,
 * bridged to Kotlin via JNI for real-time audio synthesis.
 * 
 * Architecture:
 *   Kotlin UI <-> JNI Bridge <-> SCEngine <-> scsynth <-> Oboe Output
 */

#pragma once

#include <oboe/Oboe.h>
#include <atomic>
#include <memory>
#include <string>
#include <vector>
#include <queue>
#include <mutex>
#include <thread>
#include <functional>

// Forward declarations for SuperCollider types
struct World;
struct WorldOptions;

namespace psyai::sc {

// ============================================================================
// OSC Message Builder (lock-free, RT-safe)
// ============================================================================

class OSCMessage {
public:
    OSCMessage(const char* address) {
        // OSC address pattern
        writeString(address);
        // Type tag placeholder position
        typeTagPos_ = buffer_.size();
        buffer_.push_back(',');
    }
    
    OSCMessage& addInt(int32_t value) {
        typeTags_ += 'i';
        writeInt32(value);
        return *this;
    }
    
    OSCMessage& addFloat(float value) {
        typeTags_ += 'f';
        writeFloat(value);
        return *this;
    }
    
    OSCMessage& addString(const char* value) {
        typeTags_ += 's';
        writeString(value);
        return *this;
    }
    
    const uint8_t* data() const { return buffer_.data(); }
    size_t size() const { return buffer_.size(); }
    
    std::vector<uint8_t> build() {
        // Insert type tags at the saved position
        std::vector<uint8_t> result;
        result.insert(result.end(), buffer_.begin(), buffer_.begin() + typeTagPos_);
        
        // Write type tag string (,ifs...\0 padded to 4 bytes)
        std::string tags = "," + typeTags_;
        for (char c : tags) result.push_back(c);
        result.push_back('\0');
        while (result.size() % 4 != 0) result.push_back('\0');
        
        // Append argument data
        result.insert(result.end(), argData_.begin(), argData_.end());
        return result;
    }

private:
    std::vector<uint8_t> buffer_;
    std::vector<uint8_t> argData_;
    std::string typeTags_;
    size_t typeTagPos_ = 0;
    
    void writeString(const char* s) {
        while (*s) buffer_.push_back(*s++);
        buffer_.push_back('\0');
        while (buffer_.size() % 4 != 0) buffer_.push_back('\0');
    }
    
    void writeInt32(int32_t v) {
        // Big-endian
        argData_.push_back((v >> 24) & 0xFF);
        argData_.push_back((v >> 16) & 0xFF);
        argData_.push_back((v >> 8) & 0xFF);
        argData_.push_back(v & 0xFF);
    }
    
    void writeFloat(float v) {
        union { float f; int32_t i; } u;
        u.f = v;
        writeInt32(u.i);
    }
};

// ============================================================================
// Lock-Free Command Queue (for RT-safe communication)
// ============================================================================

template<typename T, size_t Capacity = 256>
class LockFreeQueue {
public:
    bool push(const T& item) {
        size_t head = head_.load(std::memory_order_relaxed);
        size_t next = (head + 1) % Capacity;
        if (next == tail_.load(std::memory_order_acquire)) {
            return false; // Full
        }
        buffer_[head] = item;
        head_.store(next, std::memory_order_release);
        return true;
    }
    
    bool pop(T& item) {
        size_t tail = tail_.load(std::memory_order_relaxed);
        if (tail == head_.load(std::memory_order_acquire)) {
            return false; // Empty
        }
        item = buffer_[tail];
        tail_.store((tail + 1) % Capacity, std::memory_order_release);
        return true;
    }
    
    bool empty() const {
        return head_.load(std::memory_order_acquire) == 
               tail_.load(std::memory_order_acquire);
    }

private:
    std::array<T, Capacity> buffer_;
    std::atomic<size_t> head_{0};
    std::atomic<size_t> tail_{0};
};

// ============================================================================
// SC Command Types
// ============================================================================

enum class SCCommandType {
    CreateSynth,
    FreeSynth,
    SetControl,
    LoadSynthDef,
    FreeAll,
    SetBus,
    Quit
};

struct SCCommand {
    SCCommandType type;
    int32_t nodeId;
    int32_t busIndex;
    float value;
    char defName[64];
    char controlName[32];
};

// ============================================================================
// SuperCollider Engine
// ============================================================================

class SCEngine : public oboe::AudioStreamCallback {
public:
    SCEngine();
    ~SCEngine();
    
    // Lifecycle
    bool initialize(const std::string& synthDefPath, int sampleRate = 48000);
    void shutdown();
    bool isRunning() const { return running_.load(std::memory_order_acquire); }
    
    // Synth control (thread-safe, queued for RT processing)
    int32_t createSynth(const char* defName, int32_t targetId = 0);
    void freeSynth(int32_t nodeId);
    void setControl(int32_t nodeId, const char* name, float value);
    void setControl(int32_t nodeId, int32_t index, float value);
    void freeAll();
    
    // Bus control
    void setControlBus(int32_t busIndex, float value);
    float getControlBus(int32_t busIndex) const;
    
    // Load SynthDef at runtime
    void loadSynthDef(const char* path);
    
    // Audio metering
    float getPeakL() const { return peakL_.load(std::memory_order_relaxed); }
    float getPeakR() const { return peakR_.load(std::memory_order_relaxed); }
    
    // Oboe callback
    oboe::DataCallbackResult onAudioReady(
        oboe::AudioStream* stream,
        void* audioData,
        int32_t numFrames) override;

private:
    // SuperCollider world
    World* world_ = nullptr;
    std::unique_ptr<WorldOptions> options_;
    
    // Audio stream
    std::shared_ptr<oboe::AudioStream> stream_;
    int32_t sampleRate_ = 48000;
    int32_t blockSize_ = 64;
    
    // State
    std::atomic<bool> running_{false};
    std::atomic<int32_t> nextNodeId_{1000};
    
    // RT-safe command queue
    LockFreeQueue<SCCommand> commandQueue_;
    
    // Control buses (accessible from both threads)
    static constexpr int kNumControlBuses = 128;
    std::array<std::atomic<float>, kNumControlBuses> controlBuses_{};
    
    // Metering
    std::atomic<float> peakL_{0.0f};
    std::atomic<float> peakR_{0.0f};
    
    // Internal
    void processCommands();
    void sendOSC(const OSCMessage& msg);
    bool createWorld(int sampleRate);
    void destroyWorld();
};

// ============================================================================
// Implementation
// ============================================================================

SCEngine::SCEngine() {
    for (auto& bus : controlBuses_) {
        bus.store(0.0f, std::memory_order_relaxed);
    }
}

SCEngine::~SCEngine() {
    shutdown();
}

bool SCEngine::initialize(const std::string& synthDefPath, int sampleRate) {
    if (running_.load()) return false;
    
    sampleRate_ = sampleRate;
    
    // Create SC world
    if (!createWorld(sampleRate)) {
        return false;
    }
    
    // Create Oboe output stream
    oboe::AudioStreamBuilder builder;
    builder.setDirection(oboe::Direction::Output)
           .setPerformanceMode(oboe::PerformanceMode::LowLatency)
           .setSharingMode(oboe::SharingMode::Exclusive)
           .setFormat(oboe::AudioFormat::Float)
           .setChannelCount(2)
           .setSampleRate(sampleRate_)
           .setFramesPerBuffer(blockSize_ * 2)
           .setCallback(this);
    
    oboe::Result result = builder.openStream(stream_);
    if (result != oboe::Result::OK) {
        destroyWorld();
        return false;
    }
    
    // Load SynthDefs from path
    if (!synthDefPath.empty()) {
        loadSynthDef(synthDefPath.c_str());
    }
    
    // Start audio
    result = stream_->requestStart();
    if (result != oboe::Result::OK) {
        stream_->close();
        stream_.reset();
        destroyWorld();
        return false;
    }
    
    running_.store(true, std::memory_order_release);
    return true;
}

void SCEngine::shutdown() {
    running_.store(false, std::memory_order_release);
    
    if (stream_) {
        stream_->stop();
        stream_->close();
        stream_.reset();
    }
    
    destroyWorld();
}

int32_t SCEngine::createSynth(const char* defName, int32_t targetId) {
    int32_t nodeId = nextNodeId_.fetch_add(1, std::memory_order_relaxed);
    
    SCCommand cmd{};
    cmd.type = SCCommandType::CreateSynth;
    cmd.nodeId = nodeId;
    std::strncpy(cmd.defName, defName, sizeof(cmd.defName) - 1);
    commandQueue_.push(cmd);
    
    return nodeId;
}

void SCEngine::freeSynth(int32_t nodeId) {
    SCCommand cmd{};
    cmd.type = SCCommandType::FreeSynth;
    cmd.nodeId = nodeId;
    commandQueue_.push(cmd);
}

void SCEngine::setControl(int32_t nodeId, const char* name, float value) {
    SCCommand cmd{};
    cmd.type = SCCommandType::SetControl;
    cmd.nodeId = nodeId;
    cmd.value = value;
    std::strncpy(cmd.controlName, name, sizeof(cmd.controlName) - 1);
    commandQueue_.push(cmd);
}

void SCEngine::setControl(int32_t nodeId, int32_t index, float value) {
    // Use index as control name (SC accepts numeric indices)
    char buf[16];
    snprintf(buf, sizeof(buf), "%d", index);
    setControl(nodeId, buf, value);
}

void SCEngine::freeAll() {
    SCCommand cmd{};
    cmd.type = SCCommandType::FreeAll;
    commandQueue_.push(cmd);
}

void SCEngine::setControlBus(int32_t busIndex, float value) {
    if (busIndex >= 0 && busIndex < kNumControlBuses) {
        controlBuses_[busIndex].store(value, std::memory_order_relaxed);
        
        SCCommand cmd{};
        cmd.type = SCCommandType::SetBus;
        cmd.busIndex = busIndex;
        cmd.value = value;
        commandQueue_.push(cmd);
    }
}

float SCEngine::getControlBus(int32_t busIndex) const {
    if (busIndex >= 0 && busIndex < kNumControlBuses) {
        return controlBuses_[busIndex].load(std::memory_order_relaxed);
    }
    return 0.0f;
}

void SCEngine::loadSynthDef(const char* path) {
    SCCommand cmd{};
    cmd.type = SCCommandType::LoadSynthDef;
    std::strncpy(cmd.defName, path, sizeof(cmd.defName) - 1);
    commandQueue_.push(cmd);
}

oboe::DataCallbackResult SCEngine::onAudioReady(
    oboe::AudioStream* stream,
    void* audioData,
    int32_t numFrames) {
    
    if (!running_.load(std::memory_order_acquire) || !world_) {
        std::memset(audioData, 0, numFrames * 2 * sizeof(float));
        return oboe::DataCallbackResult::Continue;
    }
    
    auto* output = static_cast<float*>(audioData);
    
    // Process any pending commands
    processCommands();
    
    // Run SuperCollider world
    // This is a placeholder - actual SC integration would call:
    // World_Run(world_, numFrames);
    // Then copy from world's output buses to our buffer
    
    // For now, generate test tone
    static float phase = 0.0f;
    float freq = 440.0f;
    float phaseInc = freq / sampleRate_;
    
    float peakL = 0.0f, peakR = 0.0f;
    
    for (int32_t i = 0; i < numFrames; ++i) {
        float sample = std::sin(phase * 2.0f * 3.14159265f) * 0.3f;
        phase += phaseInc;
        if (phase >= 1.0f) phase -= 1.0f;
        
        output[i * 2] = sample;      // Left
        output[i * 2 + 1] = sample;  // Right
        
        peakL = std::max(peakL, std::abs(sample));
        peakR = std::max(peakR, std::abs(sample));
    }
    
    peakL_.store(peakL, std::memory_order_relaxed);
    peakR_.store(peakR, std::memory_order_relaxed);
    
    return oboe::DataCallbackResult::Continue;
}

void SCEngine::processCommands() {
    SCCommand cmd;
    while (commandQueue_.pop(cmd)) {
        switch (cmd.type) {
            case SCCommandType::CreateSynth: {
                // /s_new defName nodeId addAction targetId
                OSCMessage msg("/s_new");
                msg.addString(cmd.defName)
                   .addInt(cmd.nodeId)
                   .addInt(0)  // addToHead
                   .addInt(0); // default group
                sendOSC(msg);
                break;
            }
            case SCCommandType::FreeSynth: {
                // /n_free nodeId
                OSCMessage msg("/n_free");
                msg.addInt(cmd.nodeId);
                sendOSC(msg);
                break;
            }
            case SCCommandType::SetControl: {
                // /n_set nodeId controlName value
                OSCMessage msg("/n_set");
                msg.addInt(cmd.nodeId)
                   .addString(cmd.controlName)
                   .addFloat(cmd.value);
                sendOSC(msg);
                break;
            }
            case SCCommandType::LoadSynthDef: {
                // /d_load path
                OSCMessage msg("/d_load");
                msg.addString(cmd.defName);
                sendOSC(msg);
                break;
            }
            case SCCommandType::FreeAll: {
                // /g_freeAll 0
                OSCMessage msg("/g_freeAll");
                msg.addInt(0);
                sendOSC(msg);
                break;
            }
            case SCCommandType::SetBus: {
                // /c_set busIndex value
                OSCMessage msg("/c_set");
                msg.addInt(cmd.busIndex)
                   .addFloat(cmd.value);
                sendOSC(msg);
                break;
            }
            default:
                break;
        }
    }
}

void SCEngine::sendOSC(const OSCMessage& msg) {
    // In actual implementation, this would send to scsynth's OSC receiver
    // For embedded scsynth, you'd use World_SendPacket or similar
    (void)msg;
}

bool SCEngine::createWorld(int sampleRate) {
    // Placeholder - actual implementation would:
    // 1. Set up WorldOptions
    // 2. Call World_New(&options)
    // 3. Set up audio I/O callbacks
    
    // For now, just mark as created
    world_ = reinterpret_cast<World*>(1); // Placeholder
    return true;
}

void SCEngine::destroyWorld() {
    if (world_) {
        // World_Cleanup(world_);
        // World_Free(world_);
        world_ = nullptr;
    }
}

}  // namespace psyai::sc
