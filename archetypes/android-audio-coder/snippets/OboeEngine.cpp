/**
 * PSYAI Oboe Audio Engine Template
 * 
 * Production-ready Oboe setup with:
 * - Low-latency exclusive mode
 * - Automatic stream restart on disconnect
 * - Performance mode selection
 * - Format negotiation
 */

#pragma once

#include <oboe/Oboe.h>
#include <android/log.h>
#include <atomic>
#include <memory>
#include <functional>

#define LOG_TAG "OboeEngine"
#define LOGD(...) __android_log_print(ANDROID_LOG_DEBUG, LOG_TAG, __VA_ARGS__)
#define LOGE(...) __android_log_print(ANDROID_LOG_ERROR, LOG_TAG, __VA_ARGS__)

namespace psyai::audio {

/**
 * DSP callback interface - implement your processing here.
 */
class DSPCallback {
public:
    virtual ~DSPCallback() = default;
    
    /**
     * Process audio in real-time.
     * 
     * @param inputData Input samples (nullptr if output-only)
     * @param outputData Output buffer to fill
     * @param numFrames Number of frames to process
     * @param numChannels Number of channels
     * @return true to continue, false to stop
     */
    virtual bool process(const float* inputData, float* outputData,
                        int32_t numFrames, int32_t numChannels) = 0;
    
    /**
     * Called when stream properties are known.
     */
    virtual void prepare(int32_t sampleRate, int32_t framesPerBuffer,
                        int32_t numChannels) {}
};

/**
 * Oboe-based audio engine with automatic error recovery.
 */
class OboeEngine : public oboe::AudioStreamCallback,
                   public oboe::AudioStreamErrorCallback {
public:
    OboeEngine() = default;
    ~OboeEngine() override { stop(); }
    
    // Non-copyable
    OboeEngine(const OboeEngine&) = delete;
    OboeEngine& operator=(const OboeEngine&) = delete;

    /**
     * Set the DSP callback (call before start).
     */
    void setCallback(std::shared_ptr<DSPCallback> callback) {
        dspCallback_ = std::move(callback);
    }

    /**
     * Start the audio stream.
     * 
     * @param requestedSampleRate 0 = use device native
     * @param requestedChannels 0 = use device native
     * @param inputEnabled true for full-duplex
     * @return true on success
     */
    bool start(int32_t requestedSampleRate = 0,
               int32_t requestedChannels = 2,
               bool inputEnabled = false) {
        
        std::lock_guard<std::mutex> lock(streamLock_);
        
        if (outputStream_) {
            LOGE("Stream already running");
            return false;
        }
        
        inputEnabled_ = inputEnabled;
        
        // Build output stream
        oboe::AudioStreamBuilder builder;
        builder.setDirection(oboe::Direction::Output)
               .setPerformanceMode(oboe::PerformanceMode::LowLatency)
               .setSharingMode(oboe::SharingMode::Exclusive)
               .setFormat(oboe::AudioFormat::Float)
               .setFormatConversionAllowed(true)
               .setChannelConversionAllowed(true)
               .setSampleRateConversionQuality(oboe::SampleRateConversionQuality::Medium)
               .setCallback(this)
               .setErrorCallback(this);
        
        if (requestedSampleRate > 0) {
            builder.setSampleRate(requestedSampleRate);
        }
        if (requestedChannels > 0) {
            builder.setChannelCount(requestedChannels);
        }
        
        oboe::Result result = builder.openStream(outputStream_);
        if (result != oboe::Result::OK) {
            LOGE("Failed to open output stream: %s", oboe::convertToText(result));
            return false;
        }
        
        LOGD("Output stream opened: %d Hz, %d channels, %d frames/buffer",
             outputStream_->getSampleRate(),
             outputStream_->getChannelCount(),
             outputStream_->getFramesPerBurst());
        
        // Build input stream if requested
        if (inputEnabled_) {
            oboe::AudioStreamBuilder inputBuilder;
            inputBuilder.setDirection(oboe::Direction::Input)
                       .setPerformanceMode(oboe::PerformanceMode::LowLatency)
                       .setSharingMode(oboe::SharingMode::Exclusive)
                       .setFormat(oboe::AudioFormat::Float)
                       .setSampleRate(outputStream_->getSampleRate())
                       .setChannelCount(outputStream_->getChannelCount())
                       .setFramesPerBuffer(outputStream_->getFramesPerBurst());
            
            result = inputBuilder.openStream(inputStream_);
            if (result != oboe::Result::OK) {
                LOGE("Failed to open input stream: %s", oboe::convertToText(result));
                outputStream_->close();
                outputStream_.reset();
                return false;
            }
            
            LOGD("Input stream opened: %d Hz, %d channels",
                 inputStream_->getSampleRate(),
                 inputStream_->getChannelCount());
        }
        
        // Notify callback of stream properties
        if (dspCallback_) {
            dspCallback_->prepare(
                outputStream_->getSampleRate(),
                outputStream_->getFramesPerBurst(),
                outputStream_->getChannelCount()
            );
        }
        
        // Start streams
        if (inputStream_) {
            result = inputStream_->requestStart();
            if (result != oboe::Result::OK) {
                LOGE("Failed to start input stream");
            }
        }
        
        result = outputStream_->requestStart();
        if (result != oboe::Result::OK) {
            LOGE("Failed to start output stream: %s", oboe::convertToText(result));
            cleanup();
            return false;
        }
        
        running_.store(true, std::memory_order_release);
        LOGD("Audio streams started");
        return true;
    }

    /**
     * Stop the audio stream.
     */
    void stop() {
        std::lock_guard<std::mutex> lock(streamLock_);
        running_.store(false, std::memory_order_release);
        cleanup();
    }

    /**
     * Check if running.
     */
    bool isRunning() const {
        return running_.load(std::memory_order_acquire);
    }

    /**
     * Get actual sample rate (after stream opened).
     */
    int32_t getSampleRate() const {
        return outputStream_ ? outputStream_->getSampleRate() : 0;
    }

    /**
     * Get actual latency in frames.
     */
    int32_t getLatencyFrames() const {
        return outputStream_ ? outputStream_->getFramesPerBurst() * 2 : 0;
    }

    // ========================================================================
    // Oboe Callbacks
    // ========================================================================

    oboe::DataCallbackResult onAudioReady(
        oboe::AudioStream* stream,
        void* audioData,
        int32_t numFrames) override {
        
        if (!running_.load(std::memory_order_acquire)) {
            return oboe::DataCallbackResult::Stop;
        }
        
        auto* output = static_cast<float*>(audioData);
        const float* input = nullptr;
        
        // Read from input stream if available
        if (inputStream_) {
            inputBuffer_.resize(numFrames * inputStream_->getChannelCount());
            auto readResult = inputStream_->read(
                inputBuffer_.data(),
                numFrames,
                0  // Non-blocking
            );
            if (readResult.value() > 0) {
                input = inputBuffer_.data();
            }
        }
        
        // Process audio
        if (dspCallback_) {
            bool continueProcessing = dspCallback_->process(
                input, output, numFrames, stream->getChannelCount()
            );
            if (!continueProcessing) {
                return oboe::DataCallbackResult::Stop;
            }
        } else {
            // No callback - output silence
            std::memset(output, 0, numFrames * stream->getChannelCount() * sizeof(float));
        }
        
        return oboe::DataCallbackResult::Continue;
    }

    void onErrorBeforeClose(oboe::AudioStream* stream, oboe::Result error) override {
        LOGE("Stream error before close: %s", oboe::convertToText(error));
    }

    void onErrorAfterClose(oboe::AudioStream* stream, oboe::Result error) override {
        LOGE("Stream error after close: %s", oboe::convertToText(error));
        
        // Attempt restart on disconnect
        if (error == oboe::Result::ErrorDisconnected) {
            LOGD("Attempting stream restart...");
            std::thread([this]() {
                std::this_thread::sleep_for(std::chrono::milliseconds(100));
                if (running_.load()) {
                    stop();
                    start();
                }
            }).detach();
        }
    }

private:
    std::shared_ptr<oboe::AudioStream> outputStream_;
    std::shared_ptr<oboe::AudioStream> inputStream_;
    std::shared_ptr<DSPCallback> dspCallback_;
    std::vector<float> inputBuffer_;
    
    std::mutex streamLock_;
    std::atomic<bool> running_{false};
    bool inputEnabled_ = false;
    
    void cleanup() {
        if (inputStream_) {
            inputStream_->stop();
            inputStream_->close();
            inputStream_.reset();
        }
        if (outputStream_) {
            outputStream_->stop();
            outputStream_->close();
            outputStream_.reset();
        }
    }
};

// ============================================================================
// Example DSP Implementation
// ============================================================================

/**
 * Example: Simple gain processor with metering.
 */
class GainProcessor : public DSPCallback {
public:
    void setGain(float g) { gain_.store(g, std::memory_order_relaxed); }
    float getGain() const { return gain_.load(std::memory_order_relaxed); }
    
    float getPeakL() const { return peakL_.load(std::memory_order_relaxed); }
    float getPeakR() const { return peakR_.load(std::memory_order_relaxed); }
    
    void prepare(int32_t sampleRate, int32_t framesPerBuffer,
                int32_t numChannels) override {
        sampleRate_ = sampleRate;
        numChannels_ = numChannels;
        LOGD("GainProcessor prepared: %d Hz, %d channels", sampleRate, numChannels);
    }
    
    bool process(const float* input, float* output,
                int32_t numFrames, int32_t numChannels) override {
        
        float g = gain_.load(std::memory_order_relaxed);
        float peakL = 0, peakR = 0;
        
        if (numChannels == 2) {
            // Stereo
            for (int32_t i = 0; i < numFrames; ++i) {
                float l = (input ? input[i * 2] : 0) * g;
                float r = (input ? input[i * 2 + 1] : 0) * g;
                output[i * 2] = l;
                output[i * 2 + 1] = r;
                peakL = std::max(peakL, std::abs(l));
                peakR = std::max(peakR, std::abs(r));
            }
        } else {
            // Mono
            for (int32_t i = 0; i < numFrames; ++i) {
                float s = (input ? input[i] : 0) * g;
                output[i] = s;
                peakL = std::max(peakL, std::abs(s));
            }
            peakR = peakL;
        }
        
        // Update meters (simple peak hold - decay on UI thread)
        peakL_.store(peakL, std::memory_order_relaxed);
        peakR_.store(peakR, std::memory_order_relaxed);
        
        return true;
    }

private:
    std::atomic<float> gain_{1.0f};
    std::atomic<float> peakL_{0.0f};
    std::atomic<float> peakR_{0.0f};
    int32_t sampleRate_ = 48000;
    int32_t numChannels_ = 2;
};

}  // namespace psyai::audio
