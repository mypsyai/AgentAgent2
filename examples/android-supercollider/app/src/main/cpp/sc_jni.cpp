/**
 * PSYAI SuperCollider JNI Bridge
 * 
 * Maps Kotlin calls to SCEngine methods with proper handle management.
 */

#include <jni.h>
#include <android/log.h>
#include <string>
#include "SCEngine.h"

#define LOG_TAG "PSYAI_SC_JNI"
#define LOGD(...) __android_log_print(ANDROID_LOG_DEBUG, LOG_TAG, __VA_ARGS__)
#define LOGE(...) __android_log_print(ANDROID_LOG_ERROR, LOG_TAG, __VA_ARGS__)

using namespace psyai::sc;

// ============================================================================
// JNI Helpers
// ============================================================================

#define JNI_METHOD(ReturnType, ClassName, MethodName) \
    extern "C" JNIEXPORT ReturnType JNICALL \
    Java_cloud_psyai_sc_##ClassName##_##MethodName

#define GET_ENGINE(handle) reinterpret_cast<SCEngine*>(handle)
#define TO_HANDLE(ptr) reinterpret_cast<jlong>(ptr)

// Convert jstring to std::string
static std::string jstringToString(JNIEnv* env, jstring str) {
    if (str == nullptr) return "";
    const char* chars = env->GetStringUTFChars(str, nullptr);
    std::string result(chars);
    env->ReleaseStringUTFChars(str, chars);
    return result;
}

// ============================================================================
// SCEngine JNI Methods
// ============================================================================

JNI_METHOD(jlong, SCEngine, nativeCreate)(JNIEnv* env, jobject thiz) {
    LOGD("Creating SCEngine");
    auto* engine = new SCEngine();
    return TO_HANDLE(engine);
}

JNI_METHOD(void, SCEngine, nativeDestroy)(JNIEnv* env, jobject thiz, jlong handle) {
    LOGD("Destroying SCEngine");
    if (handle != 0) {
        delete GET_ENGINE(handle);
    }
}

JNI_METHOD(jboolean, SCEngine, nativeInitialize)(
    JNIEnv* env, jobject thiz, jlong handle,
    jstring synthDefPath, jint sampleRate) {
    
    if (handle == 0) return JNI_FALSE;
    
    std::string path = jstringToString(env, synthDefPath);
    LOGD("Initializing SCEngine: path=%s, sr=%d", path.c_str(), sampleRate);
    
    bool success = GET_ENGINE(handle)->initialize(path, sampleRate);
    return success ? JNI_TRUE : JNI_FALSE;
}

JNI_METHOD(void, SCEngine, nativeShutdown)(JNIEnv* env, jobject thiz, jlong handle) {
    LOGD("Shutting down SCEngine");
    if (handle != 0) {
        GET_ENGINE(handle)->shutdown();
    }
}

JNI_METHOD(jboolean, SCEngine, nativeIsRunning)(JNIEnv* env, jobject thiz, jlong handle) {
    if (handle == 0) return JNI_FALSE;
    return GET_ENGINE(handle)->isRunning() ? JNI_TRUE : JNI_FALSE;
}

// ============================================================================
// Synth Control
// ============================================================================

JNI_METHOD(jint, SCEngine, nativeCreateSynth)(
    JNIEnv* env, jobject thiz, jlong handle,
    jstring defName, jint targetId) {
    
    if (handle == 0) return -1;
    
    const char* name = env->GetStringUTFChars(defName, nullptr);
    int32_t nodeId = GET_ENGINE(handle)->createSynth(name, targetId);
    env->ReleaseStringUTFChars(defName, name);
    
    LOGD("Created synth: def=%s, nodeId=%d", name, nodeId);
    return nodeId;
}

JNI_METHOD(void, SCEngine, nativeFreeSynth)(
    JNIEnv* env, jobject thiz, jlong handle, jint nodeId) {
    
    if (handle != 0) {
        GET_ENGINE(handle)->freeSynth(nodeId);
        LOGD("Freed synth: nodeId=%d", nodeId);
    }
}

JNI_METHOD(void, SCEngine, nativeSetControl)(
    JNIEnv* env, jobject thiz, jlong handle,
    jint nodeId, jstring controlName, jfloat value) {
    
    if (handle == 0) return;
    
    const char* name = env->GetStringUTFChars(controlName, nullptr);
    GET_ENGINE(handle)->setControl(nodeId, name, value);
    env->ReleaseStringUTFChars(controlName, name);
}

JNI_METHOD(void, SCEngine, nativeSetControlByIndex)(
    JNIEnv* env, jobject thiz, jlong handle,
    jint nodeId, jint controlIndex, jfloat value) {
    
    if (handle != 0) {
        GET_ENGINE(handle)->setControl(nodeId, controlIndex, value);
    }
}

JNI_METHOD(void, SCEngine, nativeFreeAll)(JNIEnv* env, jobject thiz, jlong handle) {
    if (handle != 0) {
        GET_ENGINE(handle)->freeAll();
        LOGD("Freed all synths");
    }
}

// ============================================================================
// Bus Control
// ============================================================================

JNI_METHOD(void, SCEngine, nativeSetControlBus)(
    JNIEnv* env, jobject thiz, jlong handle,
    jint busIndex, jfloat value) {
    
    if (handle != 0) {
        GET_ENGINE(handle)->setControlBus(busIndex, value);
    }
}

JNI_METHOD(jfloat, SCEngine, nativeGetControlBus)(
    JNIEnv* env, jobject thiz, jlong handle, jint busIndex) {
    
    if (handle == 0) return 0.0f;
    return GET_ENGINE(handle)->getControlBus(busIndex);
}

// ============================================================================
// SynthDef Loading
// ============================================================================

JNI_METHOD(void, SCEngine, nativeLoadSynthDef)(
    JNIEnv* env, jobject thiz, jlong handle, jstring path) {
    
    if (handle == 0 || path == nullptr) return;
    
    const char* pathStr = env->GetStringUTFChars(path, nullptr);
    GET_ENGINE(handle)->loadSynthDef(pathStr);
    LOGD("Loading SynthDef: %s", pathStr);
    env->ReleaseStringUTFChars(path, pathStr);
}

// ============================================================================
// Metering
// ============================================================================

JNI_METHOD(jfloat, SCEngine, nativeGetPeakL)(JNIEnv* env, jobject thiz, jlong handle) {
    if (handle == 0) return 0.0f;
    return GET_ENGINE(handle)->getPeakL();
}

JNI_METHOD(jfloat, SCEngine, nativeGetPeakR)(JNIEnv* env, jobject thiz, jlong handle) {
    if (handle == 0) return 0.0f;
    return GET_ENGINE(handle)->getPeakR();
}

JNI_METHOD(jfloatArray, SCEngine, nativeGetPeaks)(JNIEnv* env, jobject thiz, jlong handle) {
    jfloatArray result = env->NewFloatArray(2);
    if (handle != 0) {
        float peaks[2] = {
            GET_ENGINE(handle)->getPeakL(),
            GET_ENGINE(handle)->getPeakR()
        };
        env->SetFloatArrayRegion(result, 0, 2, peaks);
    }
    return result;
}

// ============================================================================
// Batch Operations (for efficiency)
// ============================================================================

JNI_METHOD(void, SCEngine, nativeSetControls)(
    JNIEnv* env, jobject thiz, jlong handle,
    jint nodeId, jintArray indices, jfloatArray values) {
    
    if (handle == 0) return;
    
    jsize len = env->GetArrayLength(indices);
    jint* indexPtr = env->GetIntArrayElements(indices, nullptr);
    jfloat* valuePtr = env->GetFloatArrayElements(values, nullptr);
    
    auto* engine = GET_ENGINE(handle);
    for (jsize i = 0; i < len; ++i) {
        engine->setControl(nodeId, indexPtr[i], valuePtr[i]);
    }
    
    env->ReleaseIntArrayElements(indices, indexPtr, JNI_ABORT);
    env->ReleaseFloatArrayElements(values, valuePtr, JNI_ABORT);
}

// ============================================================================
// JNI Lifecycle
// ============================================================================

static JavaVM* g_jvm = nullptr;

jint JNI_OnLoad(JavaVM* vm, void* reserved) {
    g_jvm = vm;
    LOGD("PSYAI SuperCollider JNI loaded");
    return JNI_VERSION_1_6;
}

void JNI_OnUnload(JavaVM* vm, void* reserved) {
    LOGD("PSYAI SuperCollider JNI unloaded");
}
