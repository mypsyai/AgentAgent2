/**
 * PSYAI NEON SIMD Snippets for ARM64 Android Audio
 * 
 * Include with: #include "simd_neon.h"
 * Compile with: -march=armv8-a+simd
 */

#pragma once
#include <arm_neon.h>
#include <cstdint>
#include <cmath>

namespace psyai::simd {

// ============================================================================
// BASIC OPERATIONS
// ============================================================================

/** Apply gain to buffer in-place */
inline void gain(float* __restrict data, int n, float g) {
    float32x4_t vg = vdupq_n_f32(g);
    int i = 0;
    for (; i <= n - 16; i += 16) {
        vst1q_f32(data + i,      vmulq_f32(vld1q_f32(data + i),      vg));
        vst1q_f32(data + i + 4,  vmulq_f32(vld1q_f32(data + i + 4),  vg));
        vst1q_f32(data + i + 8,  vmulq_f32(vld1q_f32(data + i + 8),  vg));
        vst1q_f32(data + i + 12, vmulq_f32(vld1q_f32(data + i + 12), vg));
    }
    for (; i <= n - 4; i += 4) {
        vst1q_f32(data + i, vmulq_f32(vld1q_f32(data + i), vg));
    }
    for (; i < n; ++i) data[i] *= g;
}

/** Mix src into dst: dst += src * gain */
inline void mixAdd(float* __restrict dst, const float* __restrict src, int n, float g) {
    float32x4_t vg = vdupq_n_f32(g);
    int i = 0;
    for (; i <= n - 4; i += 4) {
        float32x4_t d = vld1q_f32(dst + i);
        float32x4_t s = vld1q_f32(src + i);
        vst1q_f32(dst + i, vmlaq_f32(d, s, vg));
    }
    for (; i < n; ++i) dst[i] += src[i] * g;
}

/** Copy with gain: dst = src * gain */
inline void copyGain(float* __restrict dst, const float* __restrict src, int n, float g) {
    float32x4_t vg = vdupq_n_f32(g);
    int i = 0;
    for (; i <= n - 4; i += 4) {
        vst1q_f32(dst + i, vmulq_f32(vld1q_f32(src + i), vg));
    }
    for (; i < n; ++i) dst[i] = src[i] * g;
}

/** Clear buffer to zero */
inline void clear(float* data, int n) {
    float32x4_t zero = vdupq_n_f32(0.0f);
    int i = 0;
    for (; i <= n - 16; i += 16) {
        vst1q_f32(data + i,      zero);
        vst1q_f32(data + i + 4,  zero);
        vst1q_f32(data + i + 8,  zero);
        vst1q_f32(data + i + 12, zero);
    }
    for (; i <= n - 4; i += 4) vst1q_f32(data + i, zero);
    for (; i < n; ++i) data[i] = 0.0f;
}

// ============================================================================
// STEREO OPERATIONS
// ============================================================================

/** Interleave L/R mono to stereo LRLRLR */
inline void interleave(const float* __restrict L, const float* __restrict R,
                       float* __restrict stereo, int frames) {
    int i = 0;
    for (; i <= frames - 4; i += 4) {
        float32x4_t left = vld1q_f32(L + i);
        float32x4_t right = vld1q_f32(R + i);
        float32x4x2_t zipped = vzipq_f32(left, right);
        vst1q_f32(stereo + i * 2,     zipped.val[0]);
        vst1q_f32(stereo + i * 2 + 4, zipped.val[1]);
    }
    for (; i < frames; ++i) {
        stereo[i * 2]     = L[i];
        stereo[i * 2 + 1] = R[i];
    }
}

/** Deinterleave stereo LRLRLR to L/R mono */
inline void deinterleave(const float* __restrict stereo,
                         float* __restrict L, float* __restrict R, int frames) {
    int i = 0;
    for (; i <= frames - 4; i += 4) {
        float32x4x2_t loaded = vld2q_f32(stereo + i * 2);
        vst1q_f32(L + i, loaded.val[0]);
        vst1q_f32(R + i, loaded.val[1]);
    }
    for (; i < frames; ++i) {
        L[i] = stereo[i * 2];
        R[i] = stereo[i * 2 + 1];
    }
}

/** Pan mono to stereo: L = in * (1-pan), R = in * pan, pan in [0,1] */
inline void pan(const float* __restrict in, float* __restrict L, float* __restrict R,
                int n, float pan) {
    float32x4_t vL = vdupq_n_f32(1.0f - pan);
    float32x4_t vR = vdupq_n_f32(pan);
    int i = 0;
    for (; i <= n - 4; i += 4) {
        float32x4_t s = vld1q_f32(in + i);
        vst1q_f32(L + i, vmulq_f32(s, vL));
        vst1q_f32(R + i, vmulq_f32(s, vR));
    }
    for (; i < n; ++i) {
        L[i] = in[i] * (1.0f - pan);
        R[i] = in[i] * pan;
    }
}

// ============================================================================
// WAVESHAPING / SATURATION
// ============================================================================

/** Fast tanh approximation (Pade) */
inline float32x4_t tanh_fast(float32x4_t x) {
    float32x4_t x2 = vmulq_f32(x, x);
    float32x4_t num = vaddq_f32(vdupq_n_f32(27.0f), x2);
    float32x4_t den = vmlaq_f32(vdupq_n_f32(27.0f), x2, vdupq_n_f32(9.0f));
    return vmulq_f32(x, vdivq_f32(num, den));
}

/** Soft clip (attempt: softclip(x) = x / (1 + |x|)) */
inline float32x4_t softclip(float32x4_t x) {
    float32x4_t absx = vabsq_f32(x);
    float32x4_t denom = vaddq_f32(vdupq_n_f32(1.0f), absx);
    return vdivq_f32(x, denom);
}

/** Hard clip to [-1, 1] */
inline float32x4_t hardclip(float32x4_t x) {
    return vmaxq_f32(vdupq_n_f32(-1.0f), vminq_f32(vdupq_n_f32(1.0f), x));
}

/** Apply saturation in-place */
inline void saturate(float* data, int n, float drive) {
    float32x4_t vd = vdupq_n_f32(drive);
    int i = 0;
    for (; i <= n - 4; i += 4) {
        float32x4_t x = vmulq_f32(vld1q_f32(data + i), vd);
        vst1q_f32(data + i, tanh_fast(x));
    }
    for (; i < n; ++i) {
        float x = data[i] * drive;
        data[i] = x / (1.0f + std::abs(x));  // scalar fallback
    }
}

// ============================================================================
// FILTERS
// ============================================================================

/** Biquad coefficients */
struct BiquadCoeffs {
    float b0, b1, b2, a1, a2;  // a0 normalized to 1
};

/** Biquad state */
struct BiquadState {
    float z1 = 0, z2 = 0;
};

/** Process biquad filter (Direct Form II Transposed) */
inline void biquad(float* __restrict io, int n, const BiquadCoeffs& c, BiquadState& s) {
    float z1 = s.z1, z2 = s.z2;
    for (int i = 0; i < n; ++i) {
        float x = io[i];
        float y = c.b0 * x + z1;
        z1 = c.b1 * x - c.a1 * y + z2;
        z2 = c.b2 * x - c.a2 * y;
        io[i] = y;
    }
    s.z1 = z1;
    s.z2 = z2;
}

/** Calculate lowpass coefficients */
inline BiquadCoeffs lowpass(float freq, float q, float sampleRate) {
    float w0 = 2.0f * 3.14159265f * freq / sampleRate;
    float cosw0 = std::cos(w0);
    float sinw0 = std::sin(w0);
    float alpha = sinw0 / (2.0f * q);
    
    float a0 = 1.0f + alpha;
    return {
        .b0 = ((1.0f - cosw0) / 2.0f) / a0,
        .b1 = (1.0f - cosw0) / a0,
        .b2 = ((1.0f - cosw0) / 2.0f) / a0,
        .a1 = (-2.0f * cosw0) / a0,
        .a2 = (1.0f - alpha) / a0
    };
}

/** Calculate highpass coefficients */
inline BiquadCoeffs highpass(float freq, float q, float sampleRate) {
    float w0 = 2.0f * 3.14159265f * freq / sampleRate;
    float cosw0 = std::cos(w0);
    float sinw0 = std::sin(w0);
    float alpha = sinw0 / (2.0f * q);
    
    float a0 = 1.0f + alpha;
    return {
        .b0 = ((1.0f + cosw0) / 2.0f) / a0,
        .b1 = (-(1.0f + cosw0)) / a0,
        .b2 = ((1.0f + cosw0) / 2.0f) / a0,
        .a1 = (-2.0f * cosw0) / a0,
        .a2 = (1.0f - alpha) / a0
    };
}

// ============================================================================
// DELAY / REVERB UTILITIES
// ============================================================================

/** Fractional delay read with linear interpolation */
inline float delayRead(const float* buffer, int bufSize, int writePos, float delaySamples) {
    float readPos = static_cast<float>(writePos) - delaySamples;
    while (readPos < 0) readPos += bufSize;
    
    int i0 = static_cast<int>(readPos);
    int i1 = (i0 + 1) % bufSize;
    float frac = readPos - std::floor(readPos);
    
    return buffer[i0] * (1.0f - frac) + buffer[i1] * frac;
}

/** Allpass filter for reverb diffusion */
struct Allpass {
    float* buffer;
    int size;
    int writePos = 0;
    float feedback;
    
    float process(float in) {
        float delayed = buffer[writePos];
        float out = delayed - feedback * in;
        buffer[writePos] = in + feedback * delayed;
        writePos = (writePos + 1) % size;
        return out;
    }
};

// ============================================================================
// ENVELOPE / DYNAMICS
// ============================================================================

/** Peak envelope follower */
struct EnvelopeFollower {
    float attack;   // coefficient (e.g., exp(-1/(sr*0.001)))
    float release;  // coefficient (e.g., exp(-1/(sr*0.100)))
    float envelope = 0;
    
    float process(float in) {
        float abs_in = std::abs(in);
        if (abs_in > envelope) {
            envelope = attack * envelope + (1.0f - attack) * abs_in;
        } else {
            envelope = release * envelope + (1.0f - release) * abs_in;
        }
        return envelope;
    }
};

/** Calculate attack/release coefficient from time */
inline float envCoeff(float timeMs, float sampleRate) {
    return std::exp(-1.0f / (sampleRate * timeMs * 0.001f));
}

// ============================================================================
// OSCILLATORS
// ============================================================================

/** Phase increment for given frequency */
inline float phaseInc(float freq, float sampleRate) {
    return freq / sampleRate;
}

/** Polyblep residual for anti-aliased waveforms */
inline float polyblep(float t, float dt) {
    if (t < dt) {
        t /= dt;
        return t + t - t * t - 1.0f;
    } else if (t > 1.0f - dt) {
        t = (t - 1.0f) / dt;
        return t * t + t + t + 1.0f;
    }
    return 0.0f;
}

/** Anti-aliased sawtooth */
inline float sawPolyblep(float phase, float phaseInc) {
    float saw = 2.0f * phase - 1.0f;
    return saw - polyblep(phase, phaseInc);
}

/** Anti-aliased square */
inline float squarePolyblep(float phase, float phaseInc, float pw = 0.5f) {
    float sq = (phase < pw) ? 1.0f : -1.0f;
    sq -= polyblep(phase, phaseInc);
    sq += polyblep(std::fmod(phase + 1.0f - pw, 1.0f), phaseInc);
    return sq;
}

}  // namespace psyai::simd
