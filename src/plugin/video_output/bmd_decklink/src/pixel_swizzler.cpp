#include "pixel_swizzler.hpp"
#include <memory>
#include <thread>
#include <vector>
#if defined(_MSC_VER)
#include <intrin.h>
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

void PixelSwizzler::cpy16bitRGBA_to_10bitRGB(
            void * _dst,
            void * _src,
            size_t num_pix) 
{

    // could SSE instructions be used here, or will compiler achieve that
    // for us?
    auto swizzle_chunk = [](uint32_t * _dst, uint16_t * _src, size_t n) {

        while (n--) {             

            uint32_t red = *(_src++) >> 6;
            uint32_t green = *(_src++) >> 6;
            uint32_t blue = *(_src++) >> 6;
            _src++; // skip alpha
            uint32_t le = (blue) + (green << 10) + (red << 20);   
            *(_dst++) = bswap32(le);
        }

    };

    // Note: my instinct tells me that spawning threads for
    // every copy operation (which might happen 60 times a second)
    // is not efficient but it seems that having a threadool doesn't
    // make any real difference, the overhead of thread creation
    // is tiny.
    std::vector<std::thread> memcpy_threads;
    size_t step = ((num_pix / n_threads_) / 4096) * 4096;

    uint32_t *dst = (uint32_t *)_dst;
    uint16_t *src = (uint16_t *)_src;

    for (int i = 0; i < n_threads_; ++i) {
        memcpy_threads.emplace_back(swizzle_chunk, dst, src, std::min(num_pix, step));
        dst += step;
        src += step*4;
        num_pix -= step;
    }

    // ensure any threads still running to copy data to this texture are done
    for (auto &t : memcpy_threads) {
        if (t.joinable())
            t.join();
    }
}

void PixelSwizzler::cpy16bitRGBA_to_10bitRGBX(
            void * _dst,
            void * _src,
            size_t num_pix) 
{

    // could SSE instructions be used here, or will compiler achieve that
    // for us?
    auto swizzle_chunk = [](uint32_t * _dst, uint16_t * _src, size_t n) {

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

    };

    //auto t0 = utility::clock::now();

    // Note: my instinct tells me that spawning threads for
    // every copy operation (which might happen 60 times a second)
    // is not efficient but it seems that having a threadool doesn't
    // make any real difference, the overhead of thread creation
    // is tiny.
    std::vector<std::thread> memcpy_threads;
    size_t step = ((num_pix / n_threads_) / 4096) * 4096;

    uint32_t *dst = (uint32_t *)_dst;
    uint16_t *src = (uint16_t *)_src;

    for (int i = 0; i < n_threads_; ++i) {
        memcpy_threads.emplace_back(swizzle_chunk, dst, src, std::min(num_pix, step));
        dst += step;
        src += step*4;
        num_pix -= step;
    }

    // ensure any threads still running to copy data to this texture are done
    for (auto &t : memcpy_threads) {
        if (t.joinable())
            t.join();
    }
    // std::cerr << std::chrono::duration_cast<std::chrono::microseconds>(utility::clock::now() - t0).count() << "\n";
}

void PixelSwizzler::cpy16bitRGBA_to_10bitRGBXLE(
            void * _dst,
            void * _src,
            size_t num_pix) 
{

    // could SSE instructions be used here, or will compiler achieve that
    // for us?
    auto swizzle_chunk = [](uint32_t * _dst, uint16_t * _src, size_t n) {

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

    };

    //auto t0 = utility::clock::now();

    // Note: my instinct tells me that spawning threads for
    // every copy operation (which might happen 60 times a second)
    // is not efficient but it seems that having a threadool doesn't
    // make any real difference, the overhead of thread creation
    // is tiny.
    std::vector<std::thread> memcpy_threads;
    size_t step = ((num_pix / n_threads_) / 4096) * 4096;

    uint32_t *dst = (uint32_t *)_dst;
    uint16_t *src = (uint16_t *)_src;

    for (int i = 0; i < n_threads_; ++i) {
        memcpy_threads.emplace_back(swizzle_chunk, dst, src, std::min(num_pix, step));
        dst += step;
        src += step*4;
        num_pix -= step;
    }

    // ensure any threads still running to copy data to this texture are done
    for (auto &t : memcpy_threads) {
        if (t.joinable())
            t.join();
    }
    // std::cerr << std::chrono::duration_cast<std::chrono::microseconds>(utility::clock::now() - t0).count() << "\n";
}


void PixelSwizzler::cpy16bitRGBA_to_10bitRGBLE(
            void * _dst,
            void * _src,
            size_t num_pix) 
{

    auto swizzle_chunk = [](uint32_t * _dst, uint16_t * _src, size_t n) {

        while (n--) {             

            uint32_t red = *(_src++) >> 6;
            uint32_t green = *(_src++) >> 6;
            uint32_t blue = *(_src++) >> 6;
            _src++; // skip alpha
            *(_dst++) = (blue) + (green << 10) + (red << 20);   
        }

    };

    // Note: my instinct tells me that spawning threads for
    // every copy operation (which might happen 60 times a second)
    // is not efficient but it seems that having a threadool doesn't
    // make any real difference, the overhead of thread creation
    // is tiny.
    std::vector<std::thread> memcpy_threads;
    size_t step = ((num_pix / n_threads_) / 4096) * 4096;

    uint32_t *dst = (uint32_t *)_dst;
    uint16_t *src = (uint16_t *)_src;

    for (int i = 0; i < n_threads_; ++i) {
        memcpy_threads.emplace_back(swizzle_chunk, dst, src, std::min(num_pix, step));
        dst += step;
        src += step*4;
        num_pix -= step;
    }

    // ensure any threads still running to copy data to this texture are done
    for (auto &t : memcpy_threads) {
        if (t.joinable())
            t.join();
    }
}

void PixelSwizzler::cpy16bitRGBA_to_12bitRGBLE(
            void * _dst,
            void * _src,
            size_t num_pix) 
{

    // again, SSE instructions could make this soooo much better unless
    // the compiler is being clever for us.
    auto swizzle_chunk = [](uint16_t * _dst, uint16_t * _src, size_t n) {

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

    };

    std::vector<std::thread> memcpy_threads;
    size_t step = ((num_pix / n_threads_) / 4128) * 4128;

    uint16_t *dst = (uint16_t *)_dst;
    uint16_t *src = (uint16_t *)_src;

    for (int i = 0; i < n_threads_; ++i) {
        memcpy_threads.emplace_back(swizzle_chunk, dst, src, std::min(num_pix, step));
        dst += (step*9)/4;
        src += step*4;
        num_pix -= step;
    }

    // ensure any threads still running to copy data to this texture are done
    for (auto &t : memcpy_threads) {
        if (t.joinable())
            t.join();
    }
}

void PixelSwizzler::cpy16bitRGBA_to_12bitRGB(
            void * _dst,
            void * _src,
            size_t num_pix) 
{

    // again, SSE instructions could make this soooo much better unless
    // the compiler is being clever for us.
    auto swizzle_chunk = [](uint16_t * _dst, uint16_t * _src, size_t n) {

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

    };

    std::vector<std::thread> memcpy_threads;
    size_t step = ((num_pix / n_threads_) / 4128) * 4128;

    uint16_t *dst = (uint16_t *)_dst;
    uint16_t *src = (uint16_t *)_src;

    for (int i = 0; i < n_threads_; ++i) {
        memcpy_threads.emplace_back(swizzle_chunk, dst, src, std::min(num_pix, step));
        dst += (step*9)/4;
        src += step*4;
        num_pix -= step;
    }

    // ensure any threads still running to copy data to this texture are done
    for (auto &t : memcpy_threads) {
        if (t.joinable())
            t.join();
    }
}

