/**
 * PSYAI SuperCollider DSL for Kotlin
 * 
 * Provides a fluent DSL for creating and controlling synths.
 */
package cloud.psyai.sc

import kotlinx.coroutines.delay

/**
 * DSL scope for synth parameter configuration.
 */
class SynthScope(private val synth: Synth) {
    /** Set parameter by name */
    infix fun String.to(value: Float) {
        synth.set(this, value)
    }
    
    /** Set parameter by name (number) */
    infix fun String.to(value: Number) {
        synth.set(this, value.toFloat())
    }
    
    /** Set frequency from MIDI note */
    fun freq(midiNote: Int) {
        synth.set("freq", midiToFreq(midiNote))
    }
    
    /** Set frequency from MIDI note with detune */
    fun freq(midiNote: Int, detuneCents: Float) {
        val freq = midiToFreq(midiNote) * Math.pow(2.0, detuneCents / 1200.0).toFloat()
        synth.set("freq", freq)
    }
    
    /** Trigger envelope gate on */
    fun gate(on: Boolean = true) {
        synth.set("gate", if (on) 1f else 0f)
    }
    
    /** Set amplitude in dB */
    fun ampDb(db: Float) {
        synth.set("amp", dbToAmp(db))
    }
    
    /** Set pan position (-1 to 1) */
    fun pan(value: Float) {
        synth.set("pan", value.coerceIn(-1f, 1f))
    }
}

/**
 * Extension to create synth with DSL.
 */
inline fun SCEngine.play(
    defName: String,
    crossinline block: SynthScope.() -> Unit
): Synth {
    return synth(defName) {
        SynthScope(this).block()
    }
}

/**
 * Create a note that auto-releases after a duration.
 */
suspend fun SCEngine.note(
    defName: String,
    durationMs: Long,
    block: SynthScope.() -> Unit
): Synth {
    val synth = play(defName, block)
    delay(durationMs)
    synth.set("gate", 0f)
    return synth
}

/**
 * Play a sequence of notes.
 */
suspend fun SCEngine.sequence(
    defName: String,
    notes: List<Pair<Int, Long>>,  // (midiNote, durationMs)
    amp: Float = 0.5f
) {
    for ((note, duration) in notes) {
        val synth = play(defName) {
            freq(note)
            "amp" to amp
            gate(true)
        }
        delay(duration)
        synth.set("gate", 0f)
        delay(50) // Release time
        synth.free()
    }
}

// ============================================================================
// Utility Functions
// ============================================================================

/** Convert MIDI note number to frequency */
fun midiToFreq(note: Int): Float {
    return 440f * Math.pow(2.0, (note - 69) / 12.0).toFloat()
}

/** Convert frequency to MIDI note number */
fun freqToMidi(freq: Float): Int {
    return (69 + 12 * Math.log(freq / 440.0) / Math.log(2.0)).toInt()
}

/** Convert decibels to amplitude */
fun dbToAmp(db: Float): Float {
    return Math.pow(10.0, db / 20.0).toFloat()
}

/** Convert amplitude to decibels */
fun ampToDb(amp: Float): Float {
    return (20 * Math.log10(amp.coerceAtLeast(0.0001f).toDouble())).toFloat()
}

/** Linear interpolation */
fun lerp(a: Float, b: Float, t: Float): Float {
    return a + (b - a) * t
}

/** Exponential interpolation (for frequency, etc.) */
fun expLerp(a: Float, b: Float, t: Float): Float {
    return a * Math.pow((b / a).toDouble(), t.toDouble()).toFloat()
}
