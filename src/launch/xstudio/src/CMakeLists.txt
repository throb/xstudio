project(xstudio VERSION ${XSTUDIO_GLOBAL_VERSION} LANGUAGES CXX)

find_package(OpenGL REQUIRED)
find_package(GLEW REQUIRED)
find_package(Qt6 COMPONENTS Core Quick Gui Widgets OpenGL OpenGLWidgets Svg REQUIRED)
find_package(OpenSSL)
find_package(ZLIB)
find_package(fmt REQUIRED)

if(WIN32)
set(SOURCES
	xstudio.cpp
	xstudio_win_resource.rc
	../../../../ui/qml/xstudio/qml.qrc
	)
else()
set(SOURCES
	xstudio.cpp
	../../../../ui/qml/xstudio/qml.qrc
	)
endif()
if(WIN32)
    # Add the /bigobj option for xstudio.cpp
    set_source_files_properties(xstudio.cpp PROPERTIES COMPILE_FLAGS "/bigobj")
endif()

set(CMAKE_AUTOUIC ON)
set(CMAKE_AUTOMOC ON)
set(CMAKE_AUTORCC ON)

add_executable(${PROJECT_NAME} ${SOURCES})

configure_file(.clang-tidy .clang-tidy)

if(WIN32)
	configure_file(xstudio.bat.in xstudio.bat)
else()
	configure_file(xstudio.sh.in xstudio.sh @ONLY)
endif()

default_options_local(${PROJECT_NAME})

target_link_libraries(${PROJECT_NAME}
	PRIVATE
		xstudio::caf_utility
		xstudio::global
		xstudio::ui::model_data
		xstudio::ui::opengl::viewport
		xstudio::ui::qml::bookmark
		xstudio::ui::qml::conform
		xstudio::ui::qml::embedded_python
		xstudio::ui::qml::global_store
		xstudio::ui::qml::helper
		xstudio::ui::qml::log
		xstudio::ui::qml::session
		xstudio::ui::qml::studio
		xstudio::ui::qml::viewport
		xstudio::ui::qt::viewport_widget
		xstudio::ui::viewport
		xstudio::media
		xstudio::media_reader
		xstudio::utility
		fmt::fmt
	PUBLIC
		fmt::fmt
		spdlog::spdlog
		CAF::core
		CAF::io
		$<$<BOOL:${NVIDIA_HACK}>:GLdispatch>
		# quickfuture
		OTIO::opentime
		OTIO::opentimelineio
		Qt6::Core
		Qt6::Gui
		Qt6::Quick
		Qt6::OpenGLWidgets
		Qt6::Widgets
		Qt6::Svg
		OpenSSL::SSL
		ZLIB::ZLIB
)

if(WIN32)
    target_link_libraries(${PROJECT_NAME} PRIVATE dbghelp)
elseif(NOT APPLE)
	target_link_libraries(${PROJECT_NAME} PUBLIC uuid)
endif()

if(WIN32)

	set_target_properties(${PROJECT_NAME}
		PROPERTIES
		RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin"
		OUTPUT_NAME "${PROJECT_NAME}"
		VS_DEBUGGER_ENVIRONMENT XSTUDIO_ROOT=${CMAKE_BINARY_DIR}/bin/$<$<CONFIG:Debug>:Debug>$<$<CONFIG:Release>:Release>
		LINK_DEPENDS_NO_SHARED true
	)

	install(TARGETS ${PROJECT_NAME}
        RUNTIME DESTINATION bin)

	install(PROGRAMS
	  ${CMAKE_CURRENT_BINARY_DIR}/xstudio.bat
	  DESTINATION bin
	  RENAME xstudio)

	# install FFMPEG and all dependencies into target bin folder
	file(GLOB FFMPEG_COMPONENTS ${VCPKG_INSTALLED_DIR}/${VCPKG_TARGET_TRIPLET}/tools/ffmpeg/*)
	install(FILES ${FFMPEG_COMPONENTS} DESTINATION bin)

    get_target_property(_qmake_executable Qt6::qmake IMPORTED_LOCATION)
    get_filename_component(_qt_bin_dir "${_qmake_executable}" DIRECTORY)
    find_program(windeployqt_exe windeployqt HINTS "${_qt_bin_dir}")
        configure_file(windeploy.cmake.in ${CMAKE_CURRENT_BINARY_DIR}/windeploy.cmake @ONLY)
    install(SCRIPT ${CMAKE_CURRENT_BINARY_DIR}/windeploy.cmake)

elseif(APPLE)

    set(XSTUDIO_MACOS_CODESIGN_IDENTITY
        "-"
        CACHE STRING
        "Signing identity for xSTUDIO.app. Use '-' for ad-hoc local signing or a 'Developer ID Application: ...' identity for release builds."
    )
    set(XSTUDIO_MACOS_CODESIGN_ENTITLEMENTS
        ""
        CACHE FILEPATH
        "Optional entitlements plist to apply when signing release macOS app bundles."
    )
    set(XSTUDIO_MACOS_ENABLE_HARDENED_RUNTIME
        ON
        CACHE BOOL
        "Enable hardened runtime when signing xSTUDIO.app with a non ad-hoc identity."
    )
    set(XSTUDIO_MACOS_NOTARY_KEYCHAIN_PROFILE
        ""
        CACHE STRING
        "Keychain profile name for 'xcrun notarytool submit'. Leave empty to use API key environment variables instead."
    )
    set(XSTUDIO_MACOS_NOTARY_KEYCHAIN
        ""
        CACHE FILEPATH
        "Optional keychain path used with XSTUDIO_MACOS_NOTARY_KEYCHAIN_PROFILE."
    )
    set(XSTUDIO_MACOS_NOTARY_TIMEOUT
        "15m"
        CACHE STRING
        "Timeout passed to 'xcrun notarytool submit --wait --timeout'."
    )
    set(XSTUDIO_MACOS_RELEASE_ARCHIVE
        "${CMAKE_BINARY_DIR}/xSTUDIO-${PROJECT_VERSION}-macOS.zip"
        CACHE FILEPATH
        "Zip archive path produced by the xstudio_macos_zip target."
    )
    set(XSTUDIO_MACOS_NOTARIZED_ARCHIVE
        "${CMAKE_BINARY_DIR}/xSTUDIO-${PROJECT_VERSION}-macOS-notarized.zip"
        CACHE FILEPATH
        "Zip archive path produced by the xstudio_macos_notarize target after stapling the app bundle."
    )

    set(XSTUDIO_MACOS_CODESIGN_ENTITLEMENTS_ABS "${XSTUDIO_MACOS_CODESIGN_ENTITLEMENTS}")
    if(XSTUDIO_MACOS_CODESIGN_ENTITLEMENTS_ABS)
        get_filename_component(
            XSTUDIO_MACOS_CODESIGN_ENTITLEMENTS_ABS
            "${XSTUDIO_MACOS_CODESIGN_ENTITLEMENTS_ABS}"
            ABSOLUTE
            BASE_DIR "${CMAKE_SOURCE_DIR}"
        )
    endif()

    set(XSTUDIO_MACOS_NOTARY_KEYCHAIN_ABS "${XSTUDIO_MACOS_NOTARY_KEYCHAIN}")
    if(XSTUDIO_MACOS_NOTARY_KEYCHAIN_ABS)
        get_filename_component(
            XSTUDIO_MACOS_NOTARY_KEYCHAIN_ABS
            "${XSTUDIO_MACOS_NOTARY_KEYCHAIN_ABS}"
            ABSOLUTE
            BASE_DIR "${CMAKE_SOURCE_DIR}"
        )
    endif()

	set_target_properties(${PROJECT_NAME}
		PROPERTIES
		RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/xSTUDIO.app/Contents/MacOS"
		OUTPUT_NAME "${PROJECT_NAME}.bin"
		LINK_DEPENDS_NO_SHARED true
	)

	add_custom_command(TARGET ${PROJECT_NAME} POST_BUILD
        COMMAND ${CMAKE_COMMAND} -E make_directory "${CMAKE_BINARY_DIR}/xSTUDIO.app/Contents/Resources")

	add_custom_command(TARGET ${PROJECT_NAME} POST_BUILD
        COMMAND ${CMAKE_COMMAND} -E copy
        ${CMAKE_CURRENT_SOURCE_DIR}/Info.plist "${CMAKE_BINARY_DIR}/xSTUDIO.app/Contents/")

	add_custom_command(TARGET ${PROJECT_NAME} POST_BUILD
        COMMAND ${CMAKE_COMMAND} -E copy
        ${CMAKE_CURRENT_SOURCE_DIR}/xstudio_app.ico "${CMAKE_BINARY_DIR}/xSTUDIO.app/Contents/Resources/")

	# install FFMPEG into the app bundle
	find_program(FFMPEG_APP ffmpeg HINTS "${VCPKG_INSTALLED_DIR}/${VCPKG_TARGET_TRIPLET}/tools/ffmpeg")
	add_custom_command(TARGET ${PROJECT_NAME} POST_BUILD
        COMMAND ${CMAKE_COMMAND} -E copy
        ${FFMPEG_APP} "${CMAKE_BINARY_DIR}/xSTUDIO.app/Contents/MacOS/ffmpeg")

    get_target_property(_qmake_executable Qt6::qmake IMPORTED_LOCATION)
    get_filename_component(_qt_bin_dir "${_qmake_executable}" DIRECTORY)
    find_program(macdeployqt_exe macdeployqt HINTS "${_qt_bin_dir}")
    if(NOT macdeployqt_exe)
        message(FATAL_ERROR "macdeployqt not found in ${_qt_bin_dir}")
    endif()
    configure_file(macdeploy.cmake.in ${CMAKE_CURRENT_BINARY_DIR}/macdeploy.cmake @ONLY)
    configure_file(
        package_macos_bundle.cmake.in
        ${CMAKE_CURRENT_BINARY_DIR}/package_macos_bundle.cmake
        @ONLY
    )
    configure_file(
        notarize_macos_bundle.cmake.in
        ${CMAKE_CURRENT_BINARY_DIR}/notarize_macos_bundle.cmake
        @ONLY
    )

    add_custom_command(TARGET ${PROJECT_NAME} POST_BUILD
        COMMAND ${CMAKE_COMMAND} -P ${CMAKE_CURRENT_BINARY_DIR}/macdeploy.cmake
    )

    add_custom_target(xstudio_macos_refresh_bundle
        COMMAND ${CMAKE_COMMAND} -P ${CMAKE_CURRENT_BINARY_DIR}/macdeploy.cmake
        DEPENDS ${PROJECT_NAME}
        COMMENT "Refreshing xSTUDIO.app with macdeployqt and bundle fixups"
    )

    add_custom_target(xstudio_macos_zip
        COMMAND ${CMAKE_COMMAND} -P ${CMAKE_CURRENT_BINARY_DIR}/package_macos_bundle.cmake
        DEPENDS xstudio_macos_refresh_bundle
        COMMENT "Packaging xSTUDIO.app into a macOS zip archive"
    )

    add_custom_target(xstudio_macos_notarize
        COMMAND ${CMAKE_COMMAND} -P ${CMAKE_CURRENT_BINARY_DIR}/notarize_macos_bundle.cmake
        DEPENDS xstudio_macos_zip
        COMMENT "Submitting xSTUDIO.app for notarization and stapling the result"
    )

    add_custom_target(xstudio_macos_release
        DEPENDS xstudio_macos_notarize
    )

    install(SCRIPT ${CMAKE_CURRENT_BINARY_DIR}/macdeploy.cmake)

else()

	set_target_properties(${PROJECT_NAME}
		PROPERTIES
		RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin"
		OUTPUT_NAME "${PROJECT_NAME}.bin"
		LINK_DEPENDS_NO_SHARED true
	)

	install(TARGETS ${PROJECT_NAME}
      RUNTIME DESTINATION bin)

	install(PROGRAMS
	  ${CMAKE_CURRENT_BINARY_DIR}/xstudio.sh
	  DESTINATION bin
	  RENAME xstudio)

	install(PROGRAMS
	  ${CMAKE_CURRENT_SOURCE_DIR}/xstudio_desktop_integration.sh
	  DESTINATION bin
	  RENAME xstudio_desktop_integration)

endif()
