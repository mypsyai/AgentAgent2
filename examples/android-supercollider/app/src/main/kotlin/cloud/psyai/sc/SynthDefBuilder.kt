/**
 * PSYAI SuperCollider SynthDef Builder
 * 
 * Generate SynthDef files from Kotlin for common patterns.
 * These can be pre-compiled or loaded at runtime.
 */
package cloud.psyai.sc

import java.io.File

/**
 * Generates SuperCollider SynthDef source code.
 */
object SynthDefBuilder {

    /**
     * Simple sine oscillator with envelope.
     */
    fun sine(): String = """
        SynthDef(\sine, { |out=0, freq=440, amp=0.5, pan=0, gate=1|
            var sig, env;
            env = EnvGen.kr(Env.asr(0.01, 1, 0.1), gate, doneAction: 2);
            sig = SinOsc.ar(freq) * env * amp;
            sig = Pan2.ar(sig, pan);
            Out.ar(out, sig);
        }).writeDefFile;
    """.trimIndent()

    /**
     * Saw wave with filter.
     */
    fun sawFilter(): String = """
        SynthDef(\sawFilter, { |out=0, freq=440, amp=0.5, pan=0, gate=1, 
                                cutoff=2000, res=0.5|
            var sig, env, fenv;
            env = EnvGen.kr(Env.asr(0.01, 1, 0.2), gate, doneAction: 2);
            fenv = EnvGen.kr(Env.perc(0.01, 0.3), gate) * cutoff;
            sig = Saw.ar(freq);
            sig = RLPF.ar(sig, cutoff + fenv, res);
            sig = sig * env * amp;
            sig = Pan2.ar(sig, pan);
            Out.ar(out, sig);
        }).writeDefFile;
    """.trimIndent()

    /**
     * FM synthesis.
     */
    fun fm(): String = """
        SynthDef(\fm, { |out=0, freq=440, amp=0.5, pan=0, gate=1,
                        modRatio=2, modIndex=1|
            var sig, mod, env;
            env = EnvGen.kr(Env.asr(0.01, 1, 0.1), gate, doneAction: 2);
            mod = SinOsc.ar(freq * modRatio) * freq * modIndex;
            sig = SinOsc.ar(freq + mod) * env * amp;
            sig = Pan2.ar(sig, pan);
            Out.ar(out, sig);
        }).writeDefFile;
    """.trimIndent()

    /**
     * Granular synthesis.
     */
    fun granular(): String = """
        SynthDef(\granular, { |out=0, buf=0, amp=0.5, pan=0, gate=1,
                               rate=1, pos=0, grainSize=0.1, density=20|
            var sig, env, trig;
            env = EnvGen.kr(Env.asr(0.1, 1, 0.5), gate, doneAction: 2);
            trig = Dust.kr(density);
            sig = GrainBuf.ar(2, trig, grainSize, buf, rate, pos);
            sig = sig * env * amp;
            Out.ar(out, sig);
        }).writeDefFile;
    """.trimIndent()

    /**
     * Subtractive synth with multiple oscillators.
     */
    fun polysynth(): String = """
        SynthDef(\polysynth, { |out=0, freq=440, amp=0.5, pan=0, gate=1,
                                cutoff=4000, res=0.3, detune=0.01|
            var sig, env, fenv;
            env = EnvGen.kr(Env.adsr(0.01, 0.2, 0.7, 0.3), gate, doneAction: 2);
            fenv = EnvGen.kr(Env.perc(0.01, 0.5)) * cutoff * 0.5;
            sig = Mix.ar([
                Saw.ar(freq),
                Saw.ar(freq * (1 + detune)),
                Saw.ar(freq * (1 - detune)),
                Pulse.ar(freq * 0.5, 0.5) * 0.5
            ]) * 0.25;
            sig = RLPF.ar(sig, cutoff + fenv, res);
            sig = sig * env * amp;
            sig = Pan2.ar(sig, pan);
            Out.ar(out, sig);
        }).writeDefFile;
    """.trimIndent()

    /**
     * Drum kick.
     */
    fun kick(): String = """
        SynthDef(\kick, { |out=0, amp=0.5, pan=0|
            var sig, env, fenv;
            env = EnvGen.kr(Env.perc(0.001, 0.3), doneAction: 2);
            fenv = EnvGen.kr(Env.perc(0.001, 0.1)) * 200;
            sig = SinOsc.ar(50 + fenv) * env;
            sig = sig + (WhiteNoise.ar * EnvGen.kr(Env.perc(0.001, 0.02)) * 0.3);
            sig = sig.tanh * amp;
            sig = Pan2.ar(sig, pan);
            Out.ar(out, sig);
        }).writeDefFile;
    """.trimIndent()

    /**
     * Drum snare.
     */
    fun snare(): String = """
        SynthDef(\snare, { |out=0, amp=0.5, pan=0|
            var sig, env, noise;
            env = EnvGen.kr(Env.perc(0.001, 0.2), doneAction: 2);
            noise = WhiteNoise.ar * EnvGen.kr(Env.perc(0.001, 0.15));
            sig = SinOsc.ar(180) * EnvGen.kr(Env.perc(0.001, 0.05));
            sig = (sig + noise) * env * amp;
            sig = Pan2.ar(sig, pan);
            Out.ar(out, sig);
        }).writeDefFile;
    """.trimIndent()

    /**
     * Drum hi-hat.
     */
    fun hihat(): String = """
        SynthDef(\hihat, { |out=0, amp=0.3, pan=0, decay=0.1|
            var sig, env;
            env = EnvGen.kr(Env.perc(0.001, decay), doneAction: 2);
            sig = HPF.ar(WhiteNoise.ar, 8000) * env * amp;
            sig = Pan2.ar(sig, pan);
            Out.ar(out, sig);
        }).writeDefFile;
    """.trimIndent()

    /**
     * Reverb effect.
     */
    fun reverb(): String = """
        SynthDef(\reverb, { |out=0, in=0, mix=0.3, room=0.7, damp=0.5|
            var sig, wet;
            sig = In.ar(in, 2);
            wet = FreeVerb2.ar(sig[0], sig[1], mix, room, damp);
            Out.ar(out, wet);
        }).writeDefFile;
    """.trimIndent()

    /**
     * Delay effect.
     */
    fun delay(): String = """
        SynthDef(\delay, { |out=0, in=0, delayTime=0.3, feedback=0.5, mix=0.3|
            var sig, delayed;
            sig = In.ar(in, 2);
            delayed = sig + LocalIn.ar(2);
            delayed = DelayC.ar(delayed, 2, delayTime);
            LocalOut.ar(delayed * feedback);
            Out.ar(out, (sig * (1 - mix)) + (delayed * mix));
        }).writeDefFile;
    """.trimIndent()

    /**
     * Generate all built-in SynthDefs to a directory.
     */
    fun generateAll(dir: File) {
        dir.mkdirs()
        
        val defs = mapOf(
            "sine" to sine(),
            "sawFilter" to sawFilter(),
            "fm" to fm(),
            "granular" to granular(),
            "polysynth" to polysynth(),
            "kick" to kick(),
            "snare" to snare(),
            "hihat" to hihat(),
            "reverb" to reverb(),
            "delay" to delay()
        )
        
        // Write as .scd files (SuperCollider source)
        for ((name, code) in defs) {
            File(dir, "$name.scd").writeText(code)
        }
    }
}
