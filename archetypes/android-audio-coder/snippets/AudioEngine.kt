/**
 * PSYAI Kotlin Audio Engine Wrapper
 * 
 * Lifecycle-aware wrapper around native C++ audio engine.
 * Uses AutoCloseable for deterministic cleanup.
 */
package cloud.psyai.audio

import android.content.Context
import android.media.AudioManager
import androidx.lifecycle.DefaultLifecycleObserver
import androidx.lifecycle.LifecycleOwner
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import java.io.Closeable
import java.nio.ByteBuffer
import java.nio.ByteOrder

/**
 * Callback interface for meter updates from native code.
 */
interface AudioMeterCallback {
    fun onMeterUpdate(left: Float, right: Float)
}

/**
 * Main audio engine wrapper.
 * 
 * Usage:
 * ```kotlin
 * val engine = AudioEngine(context)
 * lifecycle.addObserver(engine)  // Auto start/stop
 * engine.gain = 0.8f
 * engine.start()
 * // ...
 * engine.close()
 * ```
 */
class AudioEngine(
    context: Context
) : Closeable, DefaultLifecycleObserver, AudioMeterCallback {

    private var nativeHandle: Long = 0L
    private val audioManager = context.getSystemService(Context.AUDIO_SERVICE) as AudioManager
    
    // Observable state
    private val _isRunning = MutableStateFlow(false)
    val isRunning: StateFlow<Boolean> = _isRunning.asStateFlow()
    
    private val _meterLeft = MutableStateFlow(0f)
    private val _meterRight = MutableStateFlow(0f)
    val meterLeft: StateFlow<Float> = _meterLeft.asStateFlow()
    val meterRight: StateFlow<Float> = _meterRight.asStateFlow()

    init {
        nativeHandle = nativeCreate()
        if (nativeHandle == 0L) {
            throw IllegalStateException("Failed to create native AudioEngine")
        }
        nativeSetCallback(nativeHandle, this)
    }

    // ========================================================================
    // PUBLIC API
    // ========================================================================

    /** Master gain [0.0, 2.0] */
    var gain: Float
        get() = if (nativeHandle != 0L) nativeGetGain(nativeHandle) else 0f
        set(value) {
            if (nativeHandle != 0L) {
                nativeSetGain(nativeHandle, value.coerceIn(0f, 2f))
            }
        }

    /** Get/set parameter by index */
    fun getParameter(index: Int): Float {
        return if (nativeHandle != 0L) nativeGetParameter(nativeHandle, index) else 0f
    }

    fun setParameter(index: Int, value: Float) {
        if (nativeHandle != 0L) {
            nativeSetParameter(nativeHandle, index, value)
        }
    }

    /** Start audio processing */
    fun start(): Boolean {
        if (nativeHandle == 0L) return false
        requestAudioFocus()
        val success = nativeStart(nativeHandle)
        _isRunning.value = success
        return success
    }

    /** Stop audio processing */
    fun stop() {
        if (nativeHandle != 0L) {
            nativeStop(nativeHandle)
            _isRunning.value = false
        }
        abandonAudioFocus()
    }

    /** Load audio file */
    fun loadFile(path: String) {
        if (nativeHandle != 0L) {
            nativeLoadFile(nativeHandle, path)
        }
    }

    /**
     * Process audio buffers externally (for render-on-demand scenarios).
     * 
     * @param input Input samples (mono or interleaved stereo)
     * @param output Output buffer (same size as input)
     * @param frames Number of frames to process
     */
    fun process(input: FloatArray, output: FloatArray, frames: Int) {
        require(input.size >= frames) { "Input buffer too small" }
        require(output.size >= frames) { "Output buffer too small" }
        if (nativeHandle != 0L) {
            nativeProcess(nativeHandle, input, output, frames)
        }
    }

    /**
     * Process using direct ByteBuffers (zero-copy for large buffers).
     */
    fun processDirect(input: ByteBuffer, output: ByteBuffer, frames: Int) {
        require(input.isDirect) { "Input must be a direct buffer" }
        require(output.isDirect) { "Output must be a direct buffer" }
        if (nativeHandle != 0L) {
            nativeProcessDirect(nativeHandle, input, output, frames)
        }
    }

    // ========================================================================
    // LIFECYCLE
    // ========================================================================

    override fun onResume(owner: LifecycleOwner) {
        start()
    }

    override fun onPause(owner: LifecycleOwner) {
        stop()
    }

    override fun close() {
        stop()
        if (nativeHandle != 0L) {
            nativeSetCallback(nativeHandle, null)
            nativeDestroy(nativeHandle)
            nativeHandle = 0L
        }
    }

    // ========================================================================
    // METER CALLBACK (called from native on audio thread)
    // ========================================================================

    override fun onMeterUpdate(left: Float, right: Float) {
        _meterLeft.value = left
        _meterRight.value = right
    }

    // ========================================================================
    // AUDIO FOCUS
    // ========================================================================

    private var focusRequest: android.media.AudioFocusRequest? = null

    private fun requestAudioFocus() {
        if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.O) {
            focusRequest = android.media.AudioFocusRequest.Builder(
                AudioManager.AUDIOFOCUS_GAIN
            ).apply {
                setAudioAttributes(
                    android.media.AudioAttributes.Builder()
                        .setUsage(android.media.AudioAttributes.USAGE_MEDIA)
                        .setContentType(android.media.AudioAttributes.CONTENT_TYPE_MUSIC)
                        .build()
                )
                setOnAudioFocusChangeListener { focusChange ->
                    when (focusChange) {
                        AudioManager.AUDIOFOCUS_LOSS -> stop()
                        AudioManager.AUDIOFOCUS_LOSS_TRANSIENT -> gain *= 0.3f
                        AudioManager.AUDIOFOCUS_GAIN -> gain = 1.0f
                    }
                }
            }.build()
            audioManager.requestAudioFocus(focusRequest!!)
        }
    }

    private fun abandonAudioFocus() {
        if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.O) {
            focusRequest?.let { audioManager.abandonAudioFocusRequest(it) }
        }
    }

    // ========================================================================
    // NATIVE METHODS
    // ========================================================================

    private external fun nativeCreate(): Long
    private external fun nativeDestroy(handle: Long)
    private external fun nativeStart(handle: Long): Boolean
    private external fun nativeStop(handle: Long)
    
    private external fun nativeSetGain(handle: Long, gain: Float)
    private external fun nativeGetGain(handle: Long): Float
    
    private external fun nativeSetParameter(handle: Long, index: Int, value: Float)
    private external fun nativeGetParameter(handle: Long, index: Int): Float
    
    private external fun nativeProcess(
        handle: Long, input: FloatArray, output: FloatArray, frames: Int
    )
    private external fun nativeProcessDirect(
        handle: Long, input: ByteBuffer, output: ByteBuffer, frames: Int
    )
    
    private external fun nativeLoadFile(handle: Long, path: String)
    private external fun nativeSetCallback(handle: Long, callback: AudioMeterCallback?)

    companion object {
        init {
            System.loadLibrary("psyai_audio")
        }

        /** Create a direct float buffer for zero-copy processing */
        fun createDirectFloatBuffer(frames: Int, channels: Int = 2): ByteBuffer {
            return ByteBuffer.allocateDirect(frames * channels * 4)
                .order(ByteOrder.nativeOrder())
        }
    }
}
