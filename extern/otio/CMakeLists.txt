set(OTIO_DEPENDENCIES_INSTALL OFF)
set(OTIO_INSTALL_COMMANDLINE_TOOLS OFF)
set(OTIO_FIND_IMATH ON)
set(OTIO_PYTHON_INSTALL_DIR python)

if (APPLE)
    #install directly into VCPKG pythin installation. This gets copied into xSTUDIO.app installation
    set(CMAKE_INSTALL_PREFIX "${VCPKG_INSTALLED_DIR}/${VCPKG_TARGET_TRIPLET}/lib/${PYTHONVP}/site-packages")
else()
    set(CMAKE_INSTALL_PREFIX "bin/python")
endif()

# Build options
if (WIN32)
    set(OTIO_SHARED_LIBS OFF)
else()
    set(OTIO_SHARED_LIBS ON)
endif()

find_package(Python COMPONENTS Interpreter Development)
find_package(pybind11 CONFIG)

# When pybind11 is provided by vcpkg, skip OTIO's bundled copy to prevent
# duplicate target errors (pybind11::pybind11_headers, etc.)
if(pybind11_FOUND)
    set(OTIO_PYTHON_INSTALL OFF)
    set(OTIO_INSTALL_PYTHON_MODULES OFF)
else()
    set(OTIO_PYTHON_INSTALL ON)
    set(OTIO_INSTALL_PYTHON_MODULES ON)
    set(OTIO_AUTOMATIC_SUBMODULES ON)
endif()

add_subdirectory("OpenTimelineIO")