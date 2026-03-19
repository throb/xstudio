if(NOT DEFINED APP_BUNDLE_DIR)
    message(FATAL_ERROR "APP_BUNDLE_DIR must be provided")
endif()

if(NOT DEFINED CODESIGN_IDENTITY OR CODESIGN_IDENTITY STREQUAL "")
    set(CODESIGN_IDENTITY "-")
endif()

if(NOT DEFINED CODESIGN_ENTITLEMENTS)
    set(CODESIGN_ENTITLEMENTS "")
endif()

if(NOT DEFINED CODESIGN_ENABLE_HARDENED_RUNTIME)
    set(CODESIGN_ENABLE_HARDENED_RUNTIME OFF)
endif()

if(POLICY CMP0009)
    cmake_policy(SET CMP0009 NEW)
endif()

get_filename_component(APP_BUNDLE_DIR "${APP_BUNDLE_DIR}" ABSOLUTE)
get_filename_component(BUILD_DIR "${APP_BUNDLE_DIR}" DIRECTORY)
string(REGEX REPLACE "([][+.*^$()\\\\|?])" "\\\\\\1" BUILD_DIR_REGEX "${BUILD_DIR}")

set(LEGACY_QML_PLUGIN_DIR "${APP_BUNDLE_DIR}/Contents/PlugIns/xstudio/qml")
if(EXISTS "${LEGACY_QML_PLUGIN_DIR}")
    file(REMOVE_RECURSE "${LEGACY_QML_PLUGIN_DIR}")
endif()

set(PYTHON_FRAMEWORK_HOME "${APP_BUNDLE_DIR}/Contents/Frameworks/lib/python3.12")
set(PYTHON_RESOURCE_HOME "${APP_BUNDLE_DIR}/Contents/Resources/python/lib/python3.12")
if(EXISTS "${PYTHON_FRAMEWORK_HOME}")
    file(MAKE_DIRECTORY "${APP_BUNDLE_DIR}/Contents/Resources/python/lib")
    if(EXISTS "${PYTHON_RESOURCE_HOME}")
        file(REMOVE_RECURSE "${PYTHON_RESOURCE_HOME}")
    endif()
    file(RENAME "${PYTHON_FRAMEWORK_HOME}" "${PYTHON_RESOURCE_HOME}")

    file(GLOB FRAMEWORK_LIB_REMAINDER LIST_DIRECTORIES TRUE "${APP_BUNDLE_DIR}/Contents/Frameworks/lib/*")
    if(NOT FRAMEWORK_LIB_REMAINDER)
        file(REMOVE_RECURSE "${APP_BUNDLE_DIR}/Contents/Frameworks/lib")
    endif()
endif()

function(run_checked)
    execute_process(
        COMMAND ${ARGV}
        RESULT_VARIABLE command_result
        OUTPUT_VARIABLE command_stdout
        ERROR_VARIABLE command_stderr
    )

    if(NOT command_result EQUAL 0)
        list(JOIN ARGV " " command_line)
        message(
            FATAL_ERROR
            "Command failed (${command_result}): ${command_line}\n"
            "stdout:\n${command_stdout}\n"
            "stderr:\n${command_stderr}"
        )
    endif()
endfunction()

function(scrub_rpaths target_file)
    execute_process(
        COMMAND otool -l "${target_file}"
        RESULT_VARIABLE otool_result
        OUTPUT_VARIABLE otool_output
        ERROR_VARIABLE otool_error
    )

    if(NOT otool_result EQUAL 0)
        return()
    endif()

    string(REGEX MATCHALL "path ([^\n]+) \\(offset [0-9]+\\)" rpath_matches "${otool_output}")

    foreach(rpath_match IN LISTS rpath_matches)
        string(REGEX REPLACE "^path ([^\n]+) \\(offset [0-9]+\\)$" "\\1" rpath "${rpath_match}")

        if(rpath MATCHES "^${BUILD_DIR_REGEX}(/|$)" OR rpath MATCHES "^/opt/homebrew(/|$)")
            run_checked(install_name_tool -delete_rpath "${rpath}" "${target_file}")
        endif()
    endforeach()
endfunction()

function(normalise_framework_id library_file)
    get_filename_component(library_name "${library_file}" NAME)
    run_checked(install_name_tool -id "@rpath/${library_name}" "${library_file}")
endfunction()

function(sign_code_file target_file)
    set(options USE_RUNTIME)
    set(one_value_args ENTITLEMENTS)
    cmake_parse_arguments(SIGN_CODE "${options}" "${one_value_args}" "" ${ARGN})

    set(sign_command codesign --force --sign "${CODESIGN_IDENTITY}")

    if(CODESIGN_IDENTITY STREQUAL "-")
        list(APPEND sign_command --timestamp=none)
    else()
        list(APPEND sign_command --timestamp)
    endif()

    if(
        SIGN_CODE_USE_RUNTIME
        AND CODESIGN_ENABLE_HARDENED_RUNTIME
        AND NOT CODESIGN_IDENTITY STREQUAL "-"
    )
        list(APPEND sign_command --options runtime)
    endif()

    if(SIGN_CODE_ENTITLEMENTS)
        if(NOT EXISTS "${SIGN_CODE_ENTITLEMENTS}")
            message(FATAL_ERROR "Entitlements file does not exist: ${SIGN_CODE_ENTITLEMENTS}")
        endif()
        list(APPEND sign_command --entitlements "${SIGN_CODE_ENTITLEMENTS}")
    endif()

    list(APPEND sign_command "${target_file}")
    run_checked(${sign_command})
endfunction()

file(GLOB_RECURSE FRAMEWORK_LIBRARIES
    LIST_DIRECTORIES FALSE
    "${APP_BUNDLE_DIR}/Contents/Frameworks/*.dylib"
)
foreach(library_file IN LISTS FRAMEWORK_LIBRARIES)
    normalise_framework_id("${library_file}")
endforeach()

file(GLOB_RECURSE MACHO_CANDIDATES
    LIST_DIRECTORIES FALSE
    "${APP_BUNDLE_DIR}/Contents/MacOS/*"
    "${APP_BUNDLE_DIR}/Contents/Frameworks/*"
    "${APP_BUNDLE_DIR}/Contents/PlugIns/*"
)
file(GLOB_RECURSE RESOURCE_CODE_CANDIDATES
    LIST_DIRECTORIES FALSE
    "${APP_BUNDLE_DIR}/Contents/Resources/*.dylib"
    "${APP_BUNDLE_DIR}/Contents/Resources/*.so"
)
list(APPEND MACHO_CANDIDATES ${RESOURCE_CODE_CANDIDATES})
list(REMOVE_DUPLICATES MACHO_CANDIDATES)

foreach(candidate IN LISTS MACHO_CANDIDATES)
    if(NOT IS_DIRECTORY "${candidate}")
        scrub_rpaths("${candidate}")
    endif()
endforeach()

file(GLOB FRAMEWORK_BUNDLES
    LIST_DIRECTORIES TRUE
    "${APP_BUNDLE_DIR}/Contents/Frameworks/*.framework"
)
foreach(framework_bundle IN LISTS FRAMEWORK_BUNDLES)
    sign_code_file("${framework_bundle}")
endforeach()

foreach(candidate IN LISTS MACHO_CANDIDATES)
    if(IS_DIRECTORY "${candidate}")
        continue()
    endif()

    if(candidate MATCHES "/Contents/MacOS/xstudio\\.bin$")
        continue()
    endif()

    if(candidate MATCHES "/\\.framework/")
        continue()
    endif()

    if(candidate MATCHES "/Contents/MacOS/")
        sign_code_file("${candidate}" USE_RUNTIME)
    elseif(candidate MATCHES "\\.(dylib|so)$")
        sign_code_file("${candidate}")
    endif()
endforeach()

sign_code_file(
    "${APP_BUNDLE_DIR}"
    USE_RUNTIME
    ENTITLEMENTS "${CODESIGN_ENTITLEMENTS}"
)
run_checked(codesign --verify -vv --strict --deep "${APP_BUNDLE_DIR}")
