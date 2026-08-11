/**
 * PSYAI JNI Bridge Template for Android Audio
 * 
 * Pattern: Each native method maps to a C++ object method via handle cast.
 * The Kotlin side holds a `Long` handle representing the native pointer.
 */

#include <jni.h>
#include <android/log.h>
#include <memory>
#include <string>

// Replace with your actual audio engine header
// #include "AudioEngine.h"

#define LOG_TAG "PSYAI_JNI"
#define LOGD(...) __android_log_print(ANDROID_LOG_DEBUG, LOG_TAG, __VA_ARGS__)
#define LOGE(...) __android_log_print(ANDROID_LOG_ERROR, LOG_TAG, __VA_ARGS__)

// ============================================================================
// HELPER MACROS
// ============================================================================

#define JNI_FUNC(ReturnType, ClassName, MethodName) \
    extern "C" JNIEXPORT ReturnType JNICALL \
    Java_cloud_psyai_audio_##ClassName##_##MethodName

#define GET_ENGINE(handle) reinterpret_cast<AudioEngine*>(handle)
#define TO_HANDLE(ptr) reinterpret_cast<jlong>(ptr)

// ============================================================================
// EXAMPLE AUDIO ENGINE (replace with your implementation)
// ============================================================================

class AudioEngine {
public:
    AudioEngine() { LOGD("AudioEngine created"); }
    ~AudioEngine() { LOGD("AudioEngine destroyed"); }
    
    bool start() { /* Start Oboe stream */ return true; }
    void stop() { /* Stop Oboe stream */ }
    
    void setGain(float g) { gain_.store(g, std::memory_order_relaxed); }
    float getGain() const { return gain_.load(std::memory_order_relaxed); }
    
    void setParameter(int index, float value) {
        if (index >= 0 && index < 16) {
            params_[index].store(value, std::memory_order_relaxed);
        }
    }
    
    float getParameter(int index) const {
        if (index >= 0 && index < 16) {
            return params_[index].load(std::memory_order_relaxed);
        }
        return 0.0f;
    }
    
    // Called from Kotlin with audio buffers
    void processExternal(const float* input, float* output, int frames) {
        float g = gain_.load(std::memory_order_relaxed);
        for (int i = 0; i < frames; ++i) {
            output[i] = input[i] * g;
        }
    }

private:
    std::atomic<float> gain_{1.0f};
    std::atomic<float> params_[16]{};
};

// ============================================================================
// JNI LIFECYCLE METHODS
// ============================================================================

JNI_FUNC(jlong, AudioEngine, nativeCreate)(JNIEnv* env, jobject thiz) {
    try {
        auto* engine = new AudioEngine();
        return TO_HANDLE(engine);
    } catch (const std::exception& e) {
        LOGE("nativeCreate failed: %s", e.what());
        return 0;
    }
}

JNI_FUNC(void, AudioEngine, nativeDestroy)(JNIEnv* env, jobject thiz, jlong handle) {
    if (handle != 0) {
        delete GET_ENGINE(handle);
    }
}

JNI_FUNC(jboolean, AudioEngine, nativeStart)(JNIEnv* env, jobject thiz, jlong handle) {
    if (handle == 0) return JNI_FALSE;
    return GET_ENGINE(handle)->start() ? JNI_TRUE : JNI_FALSE;
}

JNI_FUNC(void, AudioEngine, nativeStop)(JNIEnv* env, jobject thiz, jlong handle) {
    if (handle != 0) {
        GET_ENGINE(handle)->stop();
    }
}

// ============================================================================
// PARAMETER METHODS
// ============================================================================

JNI_FUNC(void, AudioEngine, nativeSetGain)(JNIEnv* env, jobject thiz, jlong handle, jfloat gain) {
    if (handle != 0) {
        GET_ENGINE(handle)->setGain(gain);
    }
}

JNI_FUNC(jfloat, AudioEngine, nativeGetGain)(JNIEnv* env, jobject thiz, jlong handle) {
    if (handle == 0) return 0.0f;
    return GET_ENGINE(handle)->getGain();
}

JNI_FUNC(void, AudioEngine, nativeSetParameter)(
    JNIEnv* env, jobject thiz, jlong handle, jint index, jfloat value) {
    if (handle != 0) {
        GET_ENGINE(handle)->setParameter(index, value);
    }
}

JNI_FUNC(jfloat, AudioEngine, nativeGetParameter)(
    JNIEnv* env, jobject thiz, jlong handle, jint index) {
    if (handle == 0) return 0.0f;
    return GET_ENGINE(handle)->getParameter(index);
}

// ============================================================================
// BUFFER PROCESSING (for external/render-on-demand scenarios)
// ============================================================================

JNI_FUNC(void, AudioEngine, nativeProcess)(
    JNIEnv* env, jobject thiz, jlong handle,
    jfloatArray inputArray, jfloatArray outputArray, jint frames) {
    
    if (handle == 0) return;
    
    // Pin arrays (critical for performance - no copy)
    jfloat* input = env->GetFloatArrayElements(inputArray, nullptr);
    jfloat* output = env->GetFloatArrayElements(outputArray, nullptr);
    
    if (input && output) {
        GET_ENGINE(handle)->processExternal(input, output, frames);
    }
    
    // Release arrays (0 = copy back if needed, JNI_ABORT = don't copy input back)
    env->ReleaseFloatArrayElements(inputArray, input, JNI_ABORT);
    env->ReleaseFloatArrayElements(outputArray, output, 0);
}

// ============================================================================
// STRING HANDLING EXAMPLE
// ============================================================================

JNI_FUNC(void, AudioEngine, nativeLoadFile)(
    JNIEnv* env, jobject thiz, jlong handle, jstring pathStr) {
    
    if (handle == 0 || pathStr == nullptr) return;
    
    const char* path = env->GetStringUTFChars(pathStr, nullptr);
    if (path) {
        LOGD("Loading file: %s", path);
        // GET_ENGINE(handle)->loadFile(path);
        env->ReleaseStringUTFChars(pathStr, path);
    }
}

// ============================================================================
// DIRECT BUFFER ACCESS (Zero-Copy for large buffers)
// ============================================================================

JNI_FUNC(void, AudioEngine, nativeProcessDirect)(
    JNIEnv* env, jobject thiz, jlong handle,
    jobject inputBuffer, jobject outputBuffer, jint frames) {
    
    if (handle == 0) return;
    
    auto* input = static_cast<float*>(env->GetDirectBufferAddress(inputBuffer));
    auto* output = static_cast<float*>(env->GetDirectBufferAddress(outputBuffer));
    
    if (input && output) {
        GET_ENGINE(handle)->processExternal(input, output, frames);
    }
}

// ============================================================================
// CALLBACK REGISTRATION (for async notifications to Kotlin)
// ============================================================================

static JavaVM* g_jvm = nullptr;
static jobject g_callback = nullptr;
static jmethodID g_onMeterUpdate = nullptr;

JNI_FUNC(void, AudioEngine, nativeSetCallback)(
    JNIEnv* env, jobject thiz, jlong handle, jobject callback) {
    
    // Store JVM reference for callbacks from audio thread
    env->GetJavaVM(&g_jvm);
    
    // Release old callback
    if (g_callback) {
        env->DeleteGlobalRef(g_callback);
    }
    
    if (callback) {
        g_callback = env->NewGlobalRef(callback);
        jclass cls = env->GetObjectClass(callback);
        g_onMeterUpdate = env->GetMethodID(cls, "onMeterUpdate", "(FF)V");
    } else {
        g_callback = nullptr;
        g_onMeterUpdate = nullptr;
    }
}

// Call from audio thread (carefully!)
void notifyMeterUpdate(float left, float right) {
    if (!g_jvm || !g_callback || !g_onMeterUpdate) return;
    
    JNIEnv* env;
    bool attached = false;
    
    if (g_jvm->GetEnv(reinterpret_cast<void**>(&env), JNI_VERSION_1_6) != JNI_OK) {
        g_jvm->AttachCurrentThread(&env, nullptr);
        attached = true;
    }
    
    env->CallVoidMethod(g_callback, g_onMeterUpdate, left, right);
    
    if (attached) {
        g_jvm->DetachCurrentThread();
    }
}

// ============================================================================
// JNI_OnLoad (optional: cache classes/methods here)
// ============================================================================

jint JNI_OnLoad(JavaVM* vm, void* reserved) {
    g_jvm = vm;
    LOGD("PSYAI Audio JNI loaded");
    return JNI_VERSION_1_6;
}

void JNI_OnUnload(JavaVM* vm, void* reserved) {
    LOGD("PSYAI Audio JNI unloaded");
}
