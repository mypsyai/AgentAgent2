/**
 * PSYAI SuperCollider Kotlin Wrapper
 * 
 * High-level Kotlin API for the SuperCollider synthesis engine.
 * Lifecycle-aware, coroutine-friendly, with StateFlow for reactive UI.
 */
package cloud.psyai.sc

import android.content.Context
import androidx.lifecycle.DefaultLifecycleObserver
import androidx.lifecycle.LifecycleOwner
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import java.io.Closeable
import java.io.File

/**
 * Represents a running synth node in SuperCollider.
 */
data class Synth(
    val nodeId: Int,
    val defName: String,
    private val engine: SCEngine
) {
    /** Set a control parameter by name */
    fun set(name: String, value: Float) {
        engine.setControl(nodeId, name, value)
    }
    
    /** Set a control parameter by index */
    fun set(index: Int, value: Float) {
        engine.setControl(nodeId, index, value)
    }
    
    /** Set multiple controls at once */
    fun set(vararg pairs: Pair<String, Float>) {
        pairs.forEach { (name, value) -> set(name, value) }
    }
    
    /** Free this synth */
    fun free() {
        engine.freeSynth(nodeId)
    }
}

/**
 * SuperCollider synthesis engine for Android.
 * 
 * Usage:
 * ```kotlin
 * val sc = SCEngine(context)
 * lifecycle.addObserver(sc)
 * 
 * sc.start()
 * val synth = sc.synth("sine") {
 *     set("freq", 440f)
 *     set("amp", 0.5f)
 * }
 * 
 * // Later...
 * synth.set("freq", 880f)
 * synth.free()
 * 
 * sc.close()
 * ```
 */
class SCEngine(
    private val context: Context,
    private val sampleRate: Int = 48000
) : Closeable, DefaultLifecycleObserver {

    private var nativeHandle: Long = 0L
    private val scope = CoroutineScope(Dispatchers.Default + Job())
    private var meterJob: Job? = null
    
    // State
    private val _isRunning = MutableStateFlow(false)
    val isRunning: StateFlow<Boolean> = _isRunning.asStateFlow()
    
    // Metering (updated ~60fps)
    private val _peakL = MutableStateFlow(0f)
    private val _peakR = MutableStateFlow(0f)
    val peakL: StateFlow<Float> = _peakL.asStateFlow()
    val peakR: StateFlow<Float> = _peakR.asStateFlow()
    
    // SynthDef directory
    private val synthDefDir: File by lazy {
        File(context.filesDir, "synthdefs").apply { mkdirs() }
    }

    init {
        nativeHandle = nativeCreate()
        if (nativeHandle == 0L) {
            throw IllegalStateException("Failed to create native SCEngine")
        }
    }

    // ========================================================================
    // Lifecycle
    // ========================================================================

    /**
     * Start the audio engine.
     * 
     * @param synthDefPath Optional path to SynthDef directory
     * @return true if started successfully
     */
    fun start(synthDefPath: String? = null): Boolean {
        if (nativeHandle == 0L) return false
        
        val path = synthDefPath ?: synthDefDir.absolutePath
        val success = nativeInitialize(nativeHandle, path, sampleRate)
        
        if (success) {
            _isRunning.value = true
            startMeterUpdates()
        }
        
        return success
    }

    /**
     * Stop the audio engine.
     */
    fun stop() {
        meterJob?.cancel()
        meterJob = null
        
        if (nativeHandle != 0L) {
            nativeShutdown(nativeHandle)
            _isRunning.value = false
        }
    }

    override fun onResume(owner: LifecycleOwner) {
        if (!_isRunning.value) {
            start()
        }
    }

    override fun onPause(owner: LifecycleOwner) {
        stop()
    }

    override fun close() {
        stop()
        if (nativeHandle != 0L) {
            nativeDestroy(nativeHandle)
            nativeHandle = 0L
        }
    }

    // ========================================================================
    // Synth Creation
    // ========================================================================

    /**
     * Create a new synth instance.
     * 
     * @param defName Name of the SynthDef
     * @param targetId Optional target node ID
     * @param init Optional initialization block
     * @return The created Synth
     */
    fun synth(
        defName: String,
        targetId: Int = 0,
        init: Synth.() -> Unit = {}
    ): Synth {
        require(nativeHandle != 0L) { "Engine not initialized" }
        
        val nodeId = nativeCreateSynth(nativeHandle, defName, targetId)
        return Synth(nodeId, defName, this).apply(init)
    }

    /**
     * Free a synth by node ID.
     */
    fun freeSynth(nodeId: Int) {
        if (nativeHandle != 0L) {
            nativeFreeSynth(nativeHandle, nodeId)
        }
    }

    /**
     * Free all running synths.
     */
    fun freeAll() {
        if (nativeHandle != 0L) {
            nativeFreeAll(nativeHandle)
        }
    }

    // ========================================================================
    // Control
    // ========================================================================

    /**
     * Set a control parameter on a synth.
     */
    fun setControl(nodeId: Int, name: String, value: Float) {
        if (nativeHandle != 0L) {
            nativeSetControl(nativeHandle, nodeId, name, value)
        }
    }

    /**
     * Set a control parameter by index.
     */
    fun setControl(nodeId: Int, index: Int, value: Float) {
        if (nativeHandle != 0L) {
            nativeSetControlByIndex(nativeHandle, nodeId, index, value)
        }
    }

    /**
     * Set multiple controls at once (more efficient).
     */
    fun setControls(nodeId: Int, controls: Map<Int, Float>) {
        if (nativeHandle != 0L && controls.isNotEmpty()) {
            val indices = controls.keys.toIntArray()
            val values = controls.values.toFloatArray()
            nativeSetControls(nativeHandle, nodeId, indices, values)
        }
    }

    // ========================================================================
    // Control Buses
    // ========================================================================

    /**
     * Set a control bus value.
     */
    fun setControlBus(index: Int, value: Float) {
        if (nativeHandle != 0L) {
            nativeSetControlBus(nativeHandle, index, value)
        }
    }

    /**
     * Get a control bus value.
     */
    fun getControlBus(index: Int): Float {
        return if (nativeHandle != 0L) {
            nativeGetControlBus(nativeHandle, index)
        } else 0f
    }

    // ========================================================================
    // SynthDef Management
    // ========================================================================

    /**
     * Load a SynthDef from a file.
     */
    fun loadSynthDef(path: String) {
        if (nativeHandle != 0L) {
            nativeLoadSynthDef(nativeHandle, path)
        }
    }

    /**
     * Load a SynthDef from assets.
     */
    fun loadSynthDefFromAssets(assetName: String) {
        val destFile = File(synthDefDir, assetName)
        if (!destFile.exists()) {
            context.assets.open("synthdefs/$assetName").use { input ->
                destFile.outputStream().use { output ->
                    input.copyTo(output)
                }
            }
        }
        loadSynthDef(destFile.absolutePath)
    }

    // ========================================================================
    // Metering
    // ========================================================================

    private fun startMeterUpdates() {
        meterJob = scope.launch {
            while (isActive && _isRunning.value) {
                if (nativeHandle != 0L) {
                    val peaks = nativeGetPeaks(nativeHandle)
                    _peakL.value = peaks[0]
                    _peakR.value = peaks[1]
                }
                delay(16) // ~60fps
            }
        }
    }

    // ========================================================================
    // Native Methods
    // ========================================================================

    private external fun nativeCreate(): Long
    private external fun nativeDestroy(handle: Long)
    private external fun nativeInitialize(handle: Long, synthDefPath: String, sampleRate: Int): Boolean
    private external fun nativeShutdown(handle: Long)
    private external fun nativeIsRunning(handle: Long): Boolean
    
    private external fun nativeCreateSynth(handle: Long, defName: String, targetId: Int): Int
    private external fun nativeFreeSynth(handle: Long, nodeId: Int)
    private external fun nativeFreeAll(handle: Long)
    
    private external fun nativeSetControl(handle: Long, nodeId: Int, controlName: String, value: Float)
    private external fun nativeSetControlByIndex(handle: Long, nodeId: Int, controlIndex: Int, value: Float)
    private external fun nativeSetControls(handle: Long, nodeId: Int, indices: IntArray, values: FloatArray)
    
    private external fun nativeSetControlBus(handle: Long, busIndex: Int, value: Float)
    private external fun nativeGetControlBus(handle: Long, busIndex: Int): Float
    
    private external fun nativeLoadSynthDef(handle: Long, path: String)
    
    private external fun nativeGetPeakL(handle: Long): Float
    private external fun nativeGetPeakR(handle: Long): Float
    private external fun nativeGetPeaks(handle: Long): FloatArray

    companion object {
        init {
            System.loadLibrary("psyai_sc")
        }
    }
}
