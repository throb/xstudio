if(NOT DEFINED APP_BUNDLE_DIR)
    message(FATAL_ERROR "APP_BUNDLE_DIR must be provided")
endif()

get_filename_component(APP_BUNDLE_DIR "${APP_BUNDLE_DIR}" ABSOLUTE)
get_filename_component(BUILD_DIR "${APP_BUNDLE_DIR}" DIRECTORY)
string(REGEX REPLACE "([][+.*^$()\\\\|?])" "\\\\\\1" BUILD_DIR_REGEX "${BUILD_DIR}")

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
    run_checked(codesign --force --sign - --timestamp=none "${target_file}")
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
    run_checked(codesign --force --sign - --timestamp=none "${framework_bundle}")
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

    if(candidate MATCHES "\\.(dylib|so)$" OR candidate MATCHES "/Contents/MacOS/")
        sign_code_file("${candidate}")
    endif()
endforeach()

execute_process(
    COMMAND codesign --force --sign - --deep --timestamp=none --ignore-resources "${APP_BUNDLE_DIR}"
    RESULT_VARIABLE app_codesign_result
    OUTPUT_VARIABLE app_codesign_stdout
    ERROR_VARIABLE app_codesign_stderr
)

execute_process(
    COMMAND codesign -vv --deep --ignore-resources "${APP_BUNDLE_DIR}"
    RESULT_VARIABLE app_verify_result
    OUTPUT_VARIABLE app_verify_stdout
    ERROR_VARIABLE app_verify_stderr
)

if(NOT app_verify_result EQUAL 0)
    message(
        FATAL_ERROR
        "Bundle code signing verification failed.\n"
        "codesign stdout:\n${app_codesign_stdout}\n"
        "codesign stderr:\n${app_codesign_stderr}\n"
        "verify stdout:\n${app_verify_stdout}\n"
        "verify stderr:\n${app_verify_stderr}"
    )
endif()

if(NOT app_codesign_result EQUAL 0)
    message(
        STATUS
        "codesign returned ${app_codesign_result}; continuing because "
        "--ignore-resources verification succeeded."
    )
endif()
