
/*Simple helper class to wrap pixel cast/swizzle & bitshift ops.

Some of these will be very heavy on CPU side. A better approach would be
that the viewport glsl shader does some conversions at draw time - for
example packing 10 bit RGB into RGBA8 (unsigned byte) output when we need
RGB 10_10_10_2 for the SDI Output card.
*/
#include <cstddef>

namespace xstudio {
    namespace bm_decklink_plugin_1_0 {

class PixelSwizzler
{
    public:

        PixelSwizzler(const int n_threads=8) : n_threads_(n_threads) {}

        /*void cpy8bitRGBA_to_8bitYUV(
            void * _dst,
            void * _src,
            size_t num_pix);

        void cpy16bitRGBA_to_10bitYUV(
            void * _dst,
            void * _src,
            size_t num_pix);

        void cpy8bitRGBA_to_8BitARGB(
            void * _dst,
            void * _src,
            size_t num_pix);

        void cpy8bitRGBA_to_8BitBGRA(
            void * _dst,
            void * _src,
            size_t num_pix);*/

        void cpy16bitRGBA_to_10bitRGB(
            void * _dst,
            void * _src,
            size_t num_pix);

        void cpy16bitRGBA_to_10bitRGBX(
            void * _dst,
            void * _src,
            size_t num_pix
        );

        void cpy16bitRGBA_to_10bitRGBXLE(
            void * _dst,
            void * _src,
            size_t num_pix
        );        

        void cpy16bitRGBA_to_10bitRGBLE(
            void * _dst,
            void * _src,
            size_t num_pix);

        void cpy16bitRGBA_to_12bitRGB(void * _dst,
            void * _src,
            size_t num_pix);

        void cpy16bitRGBA_to_12bitRGBLE(void * _dst,
            void * _src,
            size_t num_pix);


        /*void cpy16bitRGBA_to_12bitRGB(
            void * _dst,
            void * _src,
            size_t num_pix);

        void cpy16bitRGBA_to_12bitRGBLE(
            void * _dst,
            void * _src,
            size_t num_pix);

        void cpy16bitRGBA_to_10bitRGBLE(
            void * _dst,
            void * _src,
            size_t num_pix);*/

    const int n_threads_;
};
}
}