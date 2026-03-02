// SPDX-License-Identifier: Apache-2.0
#ifdef __APPLE__
#include <OpenGL/gl.h>
#else
#undef WIN32_LEAN_AND_MEAN
#include <GL/glew.h>
#include <GL/gl.h>
#endif

#include <filesystem>

#include <caf/actor_registry.hpp>

#include "decklink_audio_device.hpp"
#include "decklink_plugin.hpp"
#include "decklink_output.hpp"

#include "xstudio/utility/helpers.hpp"
#include "xstudio/utility/logging.hpp"

#include <ImfRgbaFile.h>
#include <vector>

#ifdef __linux__
#include <dlfcn.h>
#define kDeckLinkAPI_Name "libDeckLinkAPI.so"
#endif

#ifdef _WIN32
#include <windows.h>
#endif

using namespace xstudio;
using namespace xstudio::ui;
using namespace xstudio::bm_decklink_plugin_1_0;

namespace {
    static std::map<std::string, BMDPixelFormat> bmd_pixel_formats(
        {
            {"8 bit YUV", bmdFormat8BitYUV},
            {"10 bit YUV", bmdFormat10BitYUV},
            {"8 bit ARGB", bmdFormat8BitARGB},
            {"8 bit BGRA", bmdFormat8BitBGRA},
            {"10 bit RGB", bmdFormat10BitRGB},
            {"12 bit RGB", bmdFormat12BitRGB},
            {"12 bit RGB-LE", bmdFormat12BitRGBLE},
            {"10 bit RGB Video Range", bmdFormat10BitRGBX},
            {"10 bit RGB-LE Video Range", bmdFormat10BitRGBXLE}
        });

static const std::string version1_ui_qml(R"(
import QtQuick 2.12
import BlackmagicSDI 1.0
DecklinkSettingsDialog {
}
)");
}

BMDecklinkPlugin::BMDecklinkPlugin(
    caf::actor_config &cfg, const utility::JsonStore &init_settings)
    : ui::viewport::VideoOutputPlugin(cfg, init_settings, "BMDecklinkPlugin")
{

    // here we try to open the decklink driver libs. If they are not installed
    // on the system abort construction of the plugin (caught by plugin manager)
#ifdef __APPLE__
    CFURLRef bundleURL = CFURLCreateWithFileSystemPath(kCFAllocatorDefault,
        CFSTR("/Library/Frameworks/DeckLinkAPI.framework"), kCFURLPOSIXPathStyle, true);
    bool drivers_found = false;
    if (bundleURL) {
        CFBundleRef bundle = CFBundleCreate(kCFAllocatorDefault, bundleURL);
        drivers_found = (bundle != NULL);
        if (bundle) CFRelease(bundle);
        CFRelease(bundleURL);
    }
    if (!drivers_found)
#endif
#ifdef __linux__    
	if (!dlopen(kDeckLinkAPI_Name, RTLD_NOW|RTLD_GLOBAL))
#endif
#ifdef _WIN32
    {
        HMODULE hModule = LoadLibraryA("DeckLinkAPI.dll");
        if (!hModule) {
            spdlog::error("Failed to load DeckLinkAPI.dll");
        }
    }
#endif
	{
		send_exit(this, caf::exit_reason::user_shutdown);
      	spdlog::info("Blackmagic Decklink SDI output disabled: drivers not found.");
        return;
	}

    // add attributes used for configuring the SDI output
    pixel_formats_ = add_string_choice_attribute("Pixel Format", "Pix Fmt", "10 bit YUV", utility::map_key_to_vec(bmd_pixel_formats));
    pixel_formats_->expose_in_ui_attrs_group("Decklink Settings");
    pixel_formats_->set_preference_path("/plugin/decklink/pixel_format");

    sdi_output_is_running_ = add_boolean_attribute("Enabled", "Enabled", false);
    sdi_output_is_running_->expose_in_ui_attrs_group("Decklink Settings");

    status_message_ = add_string_attribute("Status", "Status", "Not Started");
    status_message_->expose_in_ui_attrs_group("Decklink Settings");

    is_in_error_ = add_boolean_attribute("In Error", "In Error", false);
    is_in_error_->expose_in_ui_attrs_group("Decklink Settings");

    track_main_viewport_ = add_boolean_attribute("Track Viewport", "Track Viewport", false);
    track_main_viewport_->expose_in_ui_attrs_group("Decklink Settings");

    resolutions_ = add_string_choice_attribute(
            "Output Resolution",
            "Out. Res.");

    resolutions_->expose_in_ui_attrs_group("Decklink Settings");
    resolutions_->set_preference_path("/plugin/decklink/output_resolution");

    frame_rates_ = add_string_choice_attribute(
        "Refresh Rate",
        "Hz");
    frame_rates_->expose_in_ui_attrs_group("Decklink Settings");
    frame_rates_->set_preference_path("/plugin/decklink/output_frame_rate");

    start_stop_ =
        add_boolean_attribute("Start Stop", "Start Stop", false);
    start_stop_->expose_in_ui_attrs_group("Decklink Settings");

    auto_start_ = add_boolean_attribute("Auto Start", "Auto Start", false);
    auto_start_->set_preference_path("/plugin/decklink/auto_start_sdi");

    samples_water_level_ = add_integer_attribute("Audio Samples Water Level", "Audio Samples Water Level", 4096);
    samples_water_level_->set_preference_path("/plugin/decklink/audio_samps_water_level");

    video_pipeline_delay_milliseconds_= add_integer_attribute("Video Sync Delay", "Video Sync Delay", 0);
    video_pipeline_delay_milliseconds_->set_preference_path("/plugin/decklink/video_sync_delay");
    video_pipeline_delay_milliseconds_->expose_in_ui_attrs_group("Decklink Settings");

    audio_sync_delay_milliseconds_= add_integer_attribute("Audio Sync Delay", "Audio Sync Delay", 0);
    audio_sync_delay_milliseconds_->set_preference_path("/plugin/decklink/audio_sync_delay");
    audio_sync_delay_milliseconds_->expose_in_ui_attrs_group("Decklink Settings");

    disable_pc_audio_when_running_ = add_boolean_attribute("Auto Disable PC Audio", "Auto Disable PC Audio", false);
    disable_pc_audio_when_running_->set_preference_path("/plugin/decklink/disable_pc_audio_when_sdi_is_running");
    disable_pc_audio_when_running_->expose_in_ui_attrs_group("Decklink Settings");

    VideoOutputPlugin::finalise();
}

// This method is called when a new image buffer is ready to be displayed
void BMDecklinkPlugin::incoming_video_frame_callback(media_reader::ImageBufPtr incoming) {
    dcl_output_->incoming_frame(incoming);
}

void BMDecklinkPlugin::exit_cleanup() {
    // the dcl_output_ has caf::actor handles pointing to this (BMDecklinkPlugin)
    // instance. The BMDecklinkPlugin will therefore never get deleted due to
    // circular dependency so we use the on_exit
    delete dcl_output_;
}

void BMDecklinkPlugin::receive_status_callback(const utility::JsonStore & status_data) {

    if (status_data.contains("status_message") && status_data["status_message"].is_string()) {
        status_message_->set_value(status_data["status_message"].get<std::string>());
    }
    if (status_data.contains("sdi_output_is_active") && status_data["sdi_output_is_active"].is_boolean()) {
        sdi_output_is_running_->set_value(status_data["sdi_output_is_active"].get<bool>());
    }
    if (status_data.contains("error_state") && status_data["error_state"].is_boolean()) {
        is_in_error_->set_value(status_data["error_state"].get<bool>());
    }

}

void BMDecklinkPlugin::attribute_changed(const utility::Uuid &attribute_uuid, const int role)
{

    if (dcl_output_) {

        if (resolutions_ && attribute_uuid == resolutions_->uuid() && role == module::Attribute::Value) {

            std::cerr << "frame_rates_->value() " << frame_rates_->value() << "\n";

            const auto rates = dcl_output_->get_available_refresh_rates(resolutions_->value());
            frame_rates_->set_role_data(module::Attribute::StringChoices, rates);

            // pick a sensible refresh rate, if the current rate isn't available for new resolution
            auto i = std::find(rates.begin(), rates.end(), frame_rates_->value()); // prefer current rate
            if (i == rates.end()) {
                i = std::find(rates.begin(), rates.end(), "24.0"); // otherwise prefer 24.0
                if (i == rates.end()) {
                    i = std::find(rates.begin(), rates.end(), "60.0"); // use 60.0 otherwise
                    if (i == rates.end()) {
                        i = rates.begin();
                    }
                }
            }
            if (i != rates.end()) {
                frame_rates_->set_value(*i);
            }

        } else if (attribute_uuid == start_stop_->uuid()) {

            dcl_output_->StartStop();

        }

        if (attribute_uuid == pixel_formats_->uuid() || attribute_uuid == resolutions_->uuid() || attribute_uuid == frame_rates_->uuid()) {

            try {

                if (bmd_pixel_formats.find(pixel_formats_->value()) == bmd_pixel_formats.end()) {
                    throw std::runtime_error(fmt::format("Invalid pixel format: {}", pixel_formats_->value()));
                }

                const BMDPixelFormat pix_fmt = bmd_pixel_formats[pixel_formats_->value()];


                dcl_output_->set_display_mode(
                    resolutions_->value(),
                    frame_rates_->value(),
                    pix_fmt);

            } catch (std::exception & e) {

                status_message_->set_value(e.what());
                is_in_error_->set_value(true);

            }

        } else if (attribute_uuid == track_main_viewport_->uuid()) {

            /*if (track_main_viewport_->value()) {
                send(main_viewport_, ui::viewport::other_viewport_atom_v, offscreen_viewport_, caf::actor());
            } else {
                send(main_viewport_, module::link_module_atom_v, offscreen_viewport_, false);
            }*/
            if (track_main_viewport_->value()) {
                sync_geometry_to_main_viewport(true);

            } else {
                sync_geometry_to_main_viewport(false);
            }

        } else if (attribute_uuid == samples_water_level_->uuid()) {
            dcl_output_->set_audio_samples_water_level(samples_water_level_->value());
        } else if (attribute_uuid == audio_sync_delay_milliseconds_->uuid()) {
            dcl_output_->set_audio_sync_delay_milliseconds(audio_sync_delay_milliseconds_->value());
        } else if (attribute_uuid == video_pipeline_delay_milliseconds_->uuid()) {
            video_delay_milliseconds(video_pipeline_delay_milliseconds_->value());
        } else if (attribute_uuid == disable_pc_audio_when_running_->uuid()) {
            set_pc_audio_muting();
        } else if (attribute_uuid == sdi_output_is_running_->uuid()) {
            set_pc_audio_muting();
        }

    }
    StandardPlugin::attribute_changed(attribute_uuid, role);

}

audio::AudioOutputDevice * BMDecklinkPlugin::make_audio_output_device(const utility::JsonStore &prefs) {
    return static_cast<audio::AudioOutputDevice *>(new DecklinkAudioOutputDevice(prefs, dcl_output_));
}

void BMDecklinkPlugin::initialise() {

    try {

        dcl_output_ = new DecklinkOutput(this);

        resolutions_->set_role_data(module::Attribute::StringChoices, dcl_output_->output_resolution_names());

        dcl_output_->set_audio_samples_water_level(samples_water_level_->value());
        dcl_output_->set_audio_sync_delay_milliseconds(audio_sync_delay_milliseconds_->value());

        spdlog::info("Decklink Card Initialised");

        // We register the UI here
        register_viewport_dockable_widget(
            "SDI Output Controls",
            "qrc:/bmd_icons/sdi-logo.svg",   // icon for the button to activate the tool
            "Show/Hide SDI Output Controls", // tooltip for the button,
            10.0f,                           // button position in the buttons bar
            true,
            // qml code to create the left/right dockable widget
            R"(
                import QtQuick
                import BlackmagicSDI 1.0
                DecklinkSettingsVerticalWidget {
                }
                )",
            // qml code to create the top/bottom dockable widget
            R"(
                import QtQuick
                import BlackmagicSDI 1.0
                DecklinkSettingsHorizontalWidget {
                }
                )");

        // now we are set-up we can kick ourselves to fill in the refresh rate list etc.
        attribute_changed(resolutions_->uuid(), module::Attribute::Value);

        if (auto_start_->value()) {
            // start output immediately if auto_start_ is enabled (via prefs)
            dcl_output_->StartStop();
        }

        sync_geometry_to_main_viewport(false);

        video_delay_milliseconds(video_pipeline_delay_milliseconds_->value());

        // tell our viewport what sort of display we are. This info is used by
        // the colour management system to try and pick an appropriate display
        // transform
        display_info(
            "SDI Video Output",
            "Decklink",
            "Blackmagic Design",
            "");

    } catch (std::exception & e) {
        spdlog::critical("{} {}", __PRETTY_FUNCTION__, e.what());
    }

}

void BMDecklinkPlugin::set_pc_audio_muting() {

    // we can get access to the
    auto pc_audio_output_actor =
        system().registry().template get<caf::actor>(pc_audio_output_registry);

    if (pc_audio_output_actor) {
        const bool mute = disable_pc_audio_when_running_->value() && sdi_output_is_running_->value();
        anon_send(pc_audio_output_actor, audio::set_override_volume_atom_v, mute ? 0.0f : -1.0f);
    }

}

BMDecklinkPlugin::~BMDecklinkPlugin() {
}

XSTUDIO_PLUGIN_DECLARE_BEGIN()

XSTUDIO_REGISTER_PLUGIN(
    BMDecklinkPlugin,
    BMDecklinkPlugin::PLUGIN_UUID,
    BlackMagic Decklink Viewport,
    plugin_manager::PluginFlags::PF_VIDEO_OUTPUT,
    false,
    Ted Waine,
    BlackMagic Decklink SDI Output Plugin,
    1.0.0)

XSTUDIO_PLUGIN_DECLARE_END()

/*extern "C" {
__attribute__((visibility("default")))
plugin_manager::PluginFactoryCollection *plugin_factory_collection_ptr() {
    return new plugin_manager::PluginFactoryCollection(
        std::vector<std::shared_ptr<plugin_manager::PluginFactory>>(
            {std::make_shared<plugin_manager::PluginFactoryTemplate<BMDecklinkPlugin>>(
                BMDecklinkPlugin::PLUGIN_UUID,
                "BlackMagic Decklink Viewport",
                plugin_manager::PluginFlags::PF_VIDEO_OUTPUT,
                false, // not 'resident' .. the StudioUI class instances the viewport plugins
                "Ted Waine",
                "BlackMagic Decklink SDI Output Plugin")}));
}
}*/