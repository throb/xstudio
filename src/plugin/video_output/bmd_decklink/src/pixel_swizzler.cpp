#include "pixel_swizzler.hpp"
#if defined(_MSC_VER)
#include <intrin.h>
#endif
#if defined(__SSE2__) || defined(_MSC_VER)
#include <emmintrin.h>
#endif
#if defined(__SSSE3__)
#include <tmmintrin.h>
#endif
#include "xstudio/utility/chrono.hpp"

using namespace xstudio::bm_decklink_plugin_1_0;
using namespace xstudio;

namespace {

inline uint32_t bswap32(const uint32_t value) {
#if defined(_MSC_VER)
    return _byteswap_ulong(value);
#elif defined(__GNUC__) || defined(__clang__)
    return __builtin_bswap32(value);
#else
    return ((value & 0x000000FFu) << 24) | ((value & 0x0000FF00u) << 8) |
           ((value & 0x00FF0000u) >> 8) | ((value & 0xFF000000u) >> 24);
#endif
}

} // namespace

void RGBA16_to_10bitRGB::doit() {

#if defined(__SSSE3__)

    std::cerr << ".";
    // SSSE3 byte-swap mask for 4x uint32_t via pshufb
    const __m128i bswap_mask = _mm_setr_epi8(
        3, 2, 1, 0,  7, 6, 5, 4,  11, 10, 9, 8,  15, 14, 13, 12);
    const __m128i zero = _mm_setzero_si128();

    const size_t quads = n / 4;
    size_t remaining = n - quads * 4;

    for (size_t q = 0; q < quads; q++) {
        // Load 4 RGBA16 pixels (2x 128-bit loads)
        __m128i px01 = _mm_loadu_si128((__m128i*)&_src[0]);   // [r0,g0,b0,a0, r1,g1,b1,a1]
        __m128i px23 = _mm_loadu_si128((__m128i*)&_src[8]);   // [r2,g2,b2,a2, r3,g3,b3,a3]

        // Shift all 16-bit elements right by 6 to get 10-bit values
        px01 = _mm_srli_epi16(px01, 6);
        px23 = _mm_srli_epi16(px23, 6);

        // Zero-extend 16-bit to 32-bit per pixel
        __m128i p0 = _mm_unpacklo_epi16(px01, zero);  // [r0, g0, b0, a0] as 32-bit
        __m128i p1 = _mm_unpackhi_epi16(px01, zero);  // [r1, g1, b1, a1] as 32-bit
        __m128i p2 = _mm_unpacklo_epi16(px23, zero);  // [r2, g2, b2, a2] as 32-bit
        __m128i p3 = _mm_unpackhi_epi16(px23, zero);  // [r3, g3, b3, a3] as 32-bit

        // 4x4 transpose to separate R, G, B channels across 4 pixels
        __m128i t0 = _mm_unpacklo_epi32(p0, p1);      // [r0, r1, g0, g1]
        __m128i t1 = _mm_unpackhi_epi32(p0, p1);      // [b0, b1, a0, a1]
        __m128i t2 = _mm_unpacklo_epi32(p2, p3);      // [r2, r3, g2, g3]
        __m128i t3 = _mm_unpackhi_epi32(p2, p3);      // [b2, b3, a2, a3]

        __m128i reds   = _mm_unpacklo_epi64(t0, t2);  // [r0, r1, r2, r3]
        __m128i greens = _mm_unpackhi_epi64(t0, t2);  // [g0, g1, g2, g3]
        __m128i blues  = _mm_unpacklo_epi64(t1, t3);  // [b0, b1, b2, b3]

        // Pack: result = blue | (green << 10) | (red << 20)
        __m128i result = _mm_or_si128(
            _mm_or_si128(_mm_slli_epi32(reds, 20), _mm_slli_epi32(greens, 10)),
            blues);

        // Vectorised byte swap with SSSE3 pshufb
        result = _mm_shuffle_epi8(result, bswap_mask);

        // Store 4 output pixels
        _mm_storeu_si128((__m128i*)_dst, result);

        _src += 16;
        _dst += 4;
    }

    // Scalar fallback for remaining pixels
    while (remaining--) {
        uint32_t red = *(_src++) >> 6;
        uint32_t green = *(_src++) >> 6;
        uint32_t blue = *(_src++) >> 6;
        _src++; // skip alpha
        uint32_t le = (blue) + (green << 10) + (red << 20);
        *(_dst++) = bswap32(le);
    }
#else
    while (n--) {
        uint32_t red = *(_src++) >> 6;
        uint32_t green = *(_src++) >> 6;
        uint32_t blue = *(_src++) >> 6;
        _src++; // skip alpha
        uint32_t le = (blue) + (green << 10) + (red << 20);
        *(_dst++) = bswap32(le);
    }
#endif

}

void RGBA16_to_10bitRGBX::doit() {

    while (n--) {             

        uint32_t red = *(_src++) >> 6;
        uint32_t green = *(_src++) >> 6;
        uint32_t blue = *(_src++) >> 6;

        // map to vid range (64-940) from full (0-1023)
        red = 64 + ((red*876) >> 10);
        green =  64 + ((green*876) >> 10);
        blue =  64 + ((blue*876) >> 10);

        _src++; // skip alpha
        uint32_t le = (blue << 2) + (green << 12) + (red << 22);   
        *(_dst++) = bswap32(le);
    }

}


void RGBA16_to_10bitRGBXLE::doit() {

    while (n--) {             

        uint32_t red = *(_src++) >> 6;
        uint32_t green = *(_src++) >> 6;
        uint32_t blue = *(_src++) >> 6;

        // map to vid range (64-940) from full (0-1023)
        red = 64 + ((red*876) >> 10);
        green =  64 + ((green*876) >> 10);
        blue =  64 + ((blue*876) >> 10);

        _src++; // skip alpha
        *(_dst++) = (blue << 2) + (green << 12) + (red << 22);   
    }

}

void RGBA16_to_10bitRGBLE::doit() {

    while (n--) {             

        uint32_t red = *(_src++) >> 6;
        uint32_t green = *(_src++) >> 6;
        uint32_t blue = *(_src++) >> 6;
        _src++; // skip alpha
        *(_dst++) = (blue) + (green << 10) + (red << 20);   
    }

}

void RGBA16_to_12bitRGBLE::doit() {

    int shift = 0;
    while (n>=4) {             

        // 4 channels worth of pixel data. truncated to 12 bits each
        uint16_t q = *(_src++) >> 4;
        uint16_t r = *(_src++) >> 4;
        uint16_t s = *(_src++) >> 4;
        _src++; // skip alpha
        uint16_t t = *(_src++) >> 4;

        *(_dst++) = q + ((r&15) << 12);
        *(_dst++) = (r >> 4) + ((s&255) << 8);
        *(_dst++) = (s >> 8) + (t << 4);

        q = *(_src++) >> 4;
        r = *(_src++) >> 4;
        _src++; // skip alpha
        s = *(_src++) >> 4;
        t = *(_src++) >> 4;

        *(_dst++) = q + ((r&15) << 12);
        *(_dst++) = (r >> 4) + ((s&255) << 8);
        *(_dst++) = (s >> 8) + (t << 4);

        q = *(_src++) >> 4;
        _src++; // skip alpha
        r = *(_src++) >> 4;
        s = *(_src++) >> 4;
        t = *(_src++) >> 4;

        *(_dst++) = q + ((r&15) << 12);
        *(_dst++) = (r >> 4) + ((s&255) << 8);
        *(_dst++) = (s >> 8) + (t << 4);

        _src++; // skip alpha
        n-=4;

    }

}

void RGBA16_to_12bitRGB::doit() {

    uint32_t * _mdst = (uint32_t *)_dst;
    size_t mn = (n*9)/8;

    while (n>=4) {             

        // 4 channels worth of pixel data. truncated to 12 bits each
        uint16_t q = *(_src++) >> 4;
        uint16_t r = *(_src++) >> 4;
        uint16_t s = *(_src++) >> 4;
        _src++; // skip alpha
        uint16_t t = *(_src++) >> 4;

        *(_dst++) = q + ((r&15) << 12);
        *(_dst++) = (r >> 4) + ((s&255) << 8);
        *(_dst++) = (s >> 8) + (t << 4);

        q = *(_src++) >> 4;
        r = *(_src++) >> 4;
        _src++; // skip alpha
        s = *(_src++) >> 4;
        t = *(_src++) >> 4;

        *(_dst++) = q + ((r&15) << 12);
        *(_dst++) = (r >> 4) + ((s&255) << 8);
        *(_dst++) = (s >> 8) + (t << 4);

        q = *(_src++) >> 4;
        _src++; // skip alpha
        r = *(_src++) >> 4;
        s = *(_src++) >> 4;
        t = *(_src++) >> 4;

        *(_dst++) = q + ((r&15) << 12);
        *(_dst++) = (r >> 4) + ((s&255) << 8);
        *(_dst++) = (s >> 8) + (t << 4);

        _src++; // skip alpha
        n-=4;

    }

    while (mn--) {
        *_mdst = bswap32(*_mdst);
        _mdst++;
    }

}

