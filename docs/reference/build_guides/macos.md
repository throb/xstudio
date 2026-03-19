## MacOS (Intel/ARM)

To build xSTUDIO on MacOS you must download and install some build dependencies. Once these are in place xSTUDIO can be built with just two commands. Please read these notes carefully, particulary if you are not experienced in software development.

### Download Apple XCode

From the App store, locate and download XCode. Note that it is a large package and may take some time to download. Once downloaded, launch XCode and agree to the license terms & conditions.

### Install 'homebrew' package manager

Some of xSTUDIO's dependencies require 'homebrew', the MacOS open source software package manager. The homepage is [here](https://brew.sh) but you can simply run this command in a terminal 

    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

We require 5 packages to be installed to proceed. Run these commands in a terminal:

    brew install cmake
    brew install pkg-config
    brew install nasm
    brew install autoconf
    brew install autoconf-archive

### Download and install Qt 6.5.3 SDK

Follow [these instructions](downloading_qt.md)

### Download the VCPKG repo

To build xSTUDIO we need a number of other open source software packages. We use the VCPKG package manager to do this. All that we need to do is download the repo and run the bootstrap script before we build xstudio.

    git clone https://github.com/microsoft/vcpkg.git
    ./vcpkg/bootstrap-vcpkg.sh

### Download the xSTUDIO repo

Download from github in the usual manner. Enter the root folder of the repo and ensure you are building from the correct branch. Example terminal commands might be as follows, to build from the develop branch:

    git clone https://github.com/AcademySoftwareFoundation/xstudio.git
    cd xstudio
    git checkout develop

You must run these commands to add the OpenTimelineIO submodule to the tree and apply a small patch

    git submodule init
    git submodule update
    git apply cmake/otio_patch.diff

### Modify the CMakePresets.json file

Open the CMakePresets.json file (which is in the root of the xstudio repo) in a text editor. You must look for the entry "Qt6_DIR" and modify the value that follows it to point to your installation of the Qt SDK. Specifically, you need to point to a directory named 'Qt6' which is in a directory named 'cmake', which is in a directory named 'lib'. For example, on MacOS where user Mary Jane downloaded Qt into her home folder the entry should look like this:

    "Qt6_DIR": "/Users/maryjane/Qt/6.5.3/macos/lib/cmake/Qt6",

### Build xSTUDIO

Run the appropriate command for your platform (whether you have an older Intel or a newer Apple Silicon machine) to set-up for building. Note that this cmake command ***may take several hours to complete***. This is because xSTUDIO's dependencies (particularly ffmpeg) take a long time to download and build from the source code, which is what VCPKG is doing.

**Apple Silicon (ARM) Machines:**
    
    cmake -B build --preset MacOSRelease

**Intel Machines:**

    cmake -B build --preset MacOSIntelRelease

When this has finished, you can build xSTUDIO with this command.

    cmake --build build --parallel 16 --target install

If the build is successful, you should have an application bundle in the 'build' folder called 'xSTUDIO.app'. This can be drag & dropped into your applications folder, desktop and dock as for any other application.

### App bundle notes

- Normal macOS builds now run `macdeployqt` as part of the xSTUDIO target build and refresh `build/xSTUDIO.app` in place.
- The post-build bundle fixup removes build-tree and `/opt/homebrew` rpaths from the app and plugin dylibs, so local builds no longer require manual `install_name_tool` edits before launch.
- Local development builds can be launched either with `open build/xSTUDIO.app` or by running `build/xSTUDIO.app/Contents/MacOS/xstudio.bin` directly.
- The filesystem browser prefers the bundled `Contents/MacOS/ffmpeg` binary when it is present in the app bundle.
- Local development builds now pass standard `codesign --verify -vv --strict --deep build/xSTUDIO.app` verification after the normal build completes.
- Release signing/notarization is now available as an explicit build target so normal development builds stay simple.

### Release signing and notarization

To produce a distributable macOS zip archive signed with a `Developer ID Application` certificate, configure the build with the signing identity before you build:

    cmake -B build --preset MacOSRelease \
      -DXSTUDIO_MACOS_CODESIGN_IDENTITY="Developer ID Application: Example Company (TEAMID)"

Optional release variables:

- `XSTUDIO_MACOS_CODESIGN_ENTITLEMENTS` points to an entitlements plist if the shipped app needs one.
- `XSTUDIO_MACOS_ENABLE_HARDENED_RUNTIME` defaults to `ON` for release signing.
- `XSTUDIO_MACOS_RELEASE_ARCHIVE` overrides the unsigned zip path produced by `xstudio_macos_zip`.
- `XSTUDIO_MACOS_NOTARIZED_ARCHIVE` overrides the stapled zip path produced by `xstudio_macos_notarize`.

The release helper targets are:

- `xstudio_macos_refresh_bundle` reruns `macdeployqt` and bundle fixups on `build/xSTUDIO.app`.
- `xstudio_macos_zip` refreshes the bundle and creates a distributable zip archive.
- `xstudio_macos_notarize` submits the zip to Apple, staples the returned ticket to `build/xSTUDIO.app`, validates it, and writes a stapled zip archive.
- `xstudio_macos_release` is a convenience alias for `xstudio_macos_notarize`.

Example commands:

    cmake --build build --parallel 16 --target xstudio_macos_zip
    cmake --build build --parallel 16 --target xstudio_macos_release

For notarization you must configure one authentication method:

1. Store credentials in the keychain and set `XSTUDIO_MACOS_NOTARY_KEYCHAIN_PROFILE`:

       xcrun notarytool store-credentials xstudio-notary \
         --apple-id "developer@example.com" \
         --team-id "TEAMID" \
         --password "app-specific-password"

       cmake -B build --preset MacOSRelease \
         -DXSTUDIO_MACOS_CODESIGN_IDENTITY="Developer ID Application: Example Company (TEAMID)" \
         -DXSTUDIO_MACOS_NOTARY_KEYCHAIN_PROFILE=xstudio-notary

2. Or export App Store Connect API key environment variables before running `xstudio_macos_notarize`:

       export XSTUDIO_MACOS_NOTARY_API_KEY=/path/to/AuthKey_ABC123XYZ.p8
       export XSTUDIO_MACOS_NOTARY_KEY_ID=ABC123XYZ
       export XSTUDIO_MACOS_NOTARY_ISSUER=01234567-89ab-cdef-0123-456789abcdef

The notarization target saves the raw `notarytool` JSON response to `build/xstudio-notarytool-submit.json`.
