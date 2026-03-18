#!/usr/bin/env bash
# xSTUDIO Build Script for macOS / Linux
# Usage: ./build.sh [command] [options]
#
# Commands:
#   configure   - Run CMake configure step only
#   build       - Build xstudio (runs configure if needed)
#   deploy      - Copy built binaries to portable/
#   all         - configure + build + deploy (default)
#   clean       - Remove build directory
#   clean-qml   - Delete QML autogen cache (required after QML changes)
#   setup       - Install prerequisites only (vcpkg, Qt6)
#
# Options:
#   --preset <name>   - CMake preset (default: auto-detected)
#   --config <type>   - Build type: Release|RelWithDebInfo|Debug (default: Release)
#   --target <name>   - Build target (default: xstudio)
#   --jobs <n>        - Parallel build jobs (default: $(nproc))
#   --no-deploy       - Skip deploy step in 'all' command

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# ---------- Defaults ----------
BUILD_DIR="build"
CONFIG="Release"
TARGET="xstudio"
JOBS=""
COMMAND="all"
PRESET=""
NO_DEPLOY=false
VCPKG_DIR="${SCRIPT_DIR}/../vcpkg"

# ---------- Colour output ----------
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

info()  { echo -e "${CYAN}[INFO]${NC}  $*"; }
ok()    { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
err()   { echo -e "${RED}[ERROR]${NC} $*" >&2; }

# ---------- Detect platform & preset ----------
detect_platform() {
    local os
    os="$(uname -s)"
    case "$os" in
        Darwin)
            local arch
            arch="$(uname -m)"
            if [[ "$arch" == "arm64" ]]; then
                echo "MacOSRelease"
            else
                echo "MacOSIntelRelease"
            fi
            ;;
        Linux)
            echo "LinuxRelease"
            ;;
        *)
            err "Unsupported platform: $os"
            exit 1
            ;;
    esac
}

resolve_preset() {
    if [[ -n "$PRESET" ]]; then
        echo "$PRESET"
        return
    fi

    local base
    base="$(detect_platform)"

    # Swap suffix based on CONFIG
    case "$CONFIG" in
        Release)         echo "$base" ;;
        RelWithDebInfo)  echo "${base%Release}RelWithDebInfo" ;;
        Debug)           echo "${base%Release}Debug" ;;
        *)               echo "$base" ;;
    esac
}

# ---------- Shared library extension ----------
lib_ext() {
    case "$(uname -s)" in
        Darwin) echo "dylib" ;;
        *)      echo "so" ;;
    esac
}

# ---------- Parse args ----------
parse_args() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            configure|build|deploy|all|clean|clean-qml|setup)
                COMMAND="$1" ;;
            --preset)   shift; PRESET="$1" ;;
            --config)   shift; CONFIG="$1" ;;
            --target)   shift; TARGET="$1" ;;
            --jobs)     shift; JOBS="$1" ;;
            --no-deploy) NO_DEPLOY=true ;;
            -h|--help)
                sed -n '2,/^$/s/^# \?//p' "$0"
                exit 0 ;;
            *)
                err "Unknown argument: $1"
                exit 1 ;;
        esac
        shift
    done

    # Default job count
    if [[ -z "$JOBS" ]]; then
        if command -v nproc &>/dev/null; then
            JOBS="$(nproc)"
        elif command -v sysctl &>/dev/null; then
            JOBS="$(sysctl -n hw.ncpu)"
        else
            JOBS=4
        fi
    fi
}

# ---------- Prerequisite checks ----------

# System packages required to build xstudio and its vcpkg dependencies.
# Each entry: "command|brew_pkg|apt_pkg|description"
REQUIRED_TOOLS=(
    "cmake|cmake|cmake|CMake build system"
    "make|make|build-essential|Make build tool"
    "nasm|nasm|nasm|Netwide Assembler (needed by aom/x264)"
    "pkg-config|pkg-config|pkg-config|Package config helper"
    "autoconf|autoconf|autoconf|Autoconf (needed by vcpkg ports)"
    "automake|automake|automake|Automake (needed by vcpkg ports)"
    "libtool|libtool|libtool-bin|Libtool (needed by vcpkg ports)"
)

check_tool() {
    local cmd="$1" brew_pkg="$2" apt_pkg="$3" desc="$4"
    if command -v "$cmd" &>/dev/null; then
        return 0
    fi
    MISSING_TOOLS+=("$cmd")
    MISSING_BREW+=("$brew_pkg")
    MISSING_APT+=("$apt_pkg")
    err "${desc} (${cmd}) not found"
    return 1
}

check_system_tools() {
    MISSING_TOOLS=()
    MISSING_BREW=()
    MISSING_APT=()

    for entry in "${REQUIRED_TOOLS[@]}"; do
        IFS='|' read -r cmd brew_pkg apt_pkg desc <<< "$entry"
        check_tool "$cmd" "$brew_pkg" "$apt_pkg" "$desc" || true
    done

    # Check for autoconf-archive (provides m4 macros, no binary to check)
    local ax_macro=""
    case "$(uname -s)" in
        Darwin)
            ax_macro="$(brew --prefix autoconf-archive 2>/dev/null)/share/autoconf-archive/m4/ax_c_float_words_bigendian.m4"
            if [[ ! -f "$ax_macro" ]]; then
                # Also check homebrew share directly
                ax_macro="/opt/homebrew/share/aclocal/ax_c_float_words_bigendian.m4"
            fi
            ;;
        Linux)
            ax_macro="/usr/share/aclocal/ax_c_float_words_bigendian.m4"
            ;;
    esac
    if [[ -n "$ax_macro" ]] && [[ ! -f "$ax_macro" ]]; then
        MISSING_TOOLS+=("autoconf-archive")
        MISSING_BREW+=("autoconf-archive")
        MISSING_APT+=("autoconf-archive")
        err "autoconf-archive not found (needed to build Python via vcpkg)"
    fi

    if [[ ${#MISSING_TOOLS[@]} -gt 0 ]]; then
        echo ""
        case "$(uname -s)" in
            Darwin)
                local brew_list
                brew_list="$(IFS=' '; echo "${MISSING_BREW[*]}")"
                info "Install missing tools with:"
                echo -e "  ${BOLD}brew install ${brew_list}${NC}"
                echo ""
                read -rp "Install now? [Y/n] " answer
                if [[ "${answer:-Y}" =~ ^[Yy]$ ]]; then
                    # shellcheck disable=SC2086
                    brew install $brew_list
                    ok "Tools installed"
                else
                    return 1
                fi
                ;;
            Linux)
                local apt_list
                apt_list="$(IFS=' '; echo "${MISSING_APT[*]}")"
                info "Install missing tools with:"
                echo -e "  ${BOLD}sudo apt install ${apt_list}${NC}"
                echo ""
                read -rp "Install now? [Y/n] " answer
                if [[ "${answer:-Y}" =~ ^[Yy]$ ]]; then
                    sudo apt-get install -y $apt_list
                    ok "Tools installed"
                else
                    return 1
                fi
                ;;
        esac
    fi
}

check_qt6() {
    local qt6_dir=""

    if [[ -n "${Qt6_DIR:-}" ]]; then
        qt6_dir="$Qt6_DIR"
    elif [[ -n "${CMAKE_PREFIX_PATH:-}" ]]; then
        qt6_dir="already-set-via-prefix-path"
    fi

    # Check common install locations
    if [[ -z "$qt6_dir" ]]; then
        local search_paths=()
        case "$(uname -s)" in
            Darwin)
                search_paths=(
                    "$(brew --prefix qt@6 2>/dev/null)/lib/cmake/Qt6"
                    "$(brew --prefix qt 2>/dev/null)/lib/cmake/Qt6"
                    "/opt/homebrew/opt/qt@6/lib/cmake/Qt6"
                    "/opt/homebrew/opt/qt/lib/cmake/Qt6"
                    "/usr/local/opt/qt@6/lib/cmake/Qt6"
                    "/usr/local/opt/qt/lib/cmake/Qt6"
                )
                ;;
            Linux)
                search_paths=(
                    "/usr/lib/x86_64-linux-gnu/cmake/Qt6"
                    "/usr/lib/cmake/Qt6"
                    "/opt/Qt/6.*/gcc_64/lib/cmake/Qt6"
                )
                ;;
        esac

        for p in "${search_paths[@]}"; do
            for expanded in $p; do
                if [[ -f "${expanded}/Qt6Config.cmake" ]]; then
                    qt6_dir="$expanded"
                    break 2
                fi
            done
        done
    fi

    if [[ -z "$qt6_dir" ]]; then
        echo ""
        case "$(uname -s)" in
            Darwin)
                err "Qt6 not found."
                info "Install with:"
                echo -e "  ${BOLD}brew install qt@6${NC}"
                echo ""
                read -rp "Install now? [Y/n] " answer
                if [[ "${answer:-Y}" =~ ^[Yy]$ ]]; then
                    brew install qt@6
                    # Re-detect after install
                    qt6_dir="$(brew --prefix qt@6 2>/dev/null || brew --prefix qt 2>/dev/null)/lib/cmake/Qt6"
                    if [[ ! -f "${qt6_dir}/Qt6Config.cmake" ]]; then
                        qt6_dir="$(brew --prefix qt 2>/dev/null)/lib/cmake/Qt6"
                    fi
                else
                    return 1
                fi
                ;;
            Linux)
                err "Qt6 not found."
                info "Install with:"
                echo -e "  ${BOLD}sudo apt install qt6-base-dev qt6-declarative-dev qt6-svg-dev${NC}"
                err "Or set Qt6_DIR to your Qt6 cmake directory"
                return 1
                ;;
        esac
    fi

    if [[ "$qt6_dir" == "already-set-via-prefix-path" ]]; then
        info "Qt6 discovery via CMAKE_PREFIX_PATH"
    else
        info "Qt6 found at ${qt6_dir}"
        export CMAKE_PREFIX_PATH="${qt6_dir}/../../..${CMAKE_PREFIX_PATH:+:$CMAKE_PREFIX_PATH}"
    fi
}

setup_vcpkg() {
    if [[ -f "${VCPKG_DIR}/vcpkg" ]] || [[ -f "${VCPKG_DIR}/vcpkg.exe" ]]; then
        info "vcpkg already installed at ${VCPKG_DIR}"
        return 0
    fi

    info "vcpkg not found at ${VCPKG_DIR} — cloning..."
    git clone https://github.com/microsoft/vcpkg.git "$VCPKG_DIR"

    info "Bootstrapping vcpkg..."
    "$VCPKG_DIR/bootstrap-vcpkg.sh" -disableMetrics

    ok "vcpkg ready"
}

check_prereqs() {
    local failed=false

    echo -e "\n${BOLD}Checking prerequisites...${NC}\n"

    check_system_tools || failed=true
    check_qt6          || failed=true

    if [[ ! -f "${VCPKG_DIR}/vcpkg" ]] && [[ ! -f "${VCPKG_DIR}/vcpkg.exe" ]]; then
        warn "vcpkg not found — will install automatically"
        setup_vcpkg
    else
        info "vcpkg found at ${VCPKG_DIR}"
    fi

    echo ""

    if [[ "$failed" == true ]]; then
        err "Missing prerequisites. Install them and try again."
        exit 1
    fi

    ok "All prerequisites satisfied"
    echo ""
}

# ---------- Commands ----------
do_configure() {
    check_prereqs

    # Ensure git submodules are initialized
    if git submodule status 2>/dev/null | grep -q '^-'; then
        info "Initializing git submodules..."
        git submodule update --init --recursive
        ok "Submodules ready"
    fi

    local preset
    preset="$(resolve_preset)"
    info "Configuring with preset: ${preset}"
    cmake --preset "$preset"
    ok "Configure complete"
}

do_build() {
    # Configure if build dir doesn't exist
    if [[ ! -d "$BUILD_DIR" ]]; then
        warn "Build directory not found, running configure first..."
        do_configure
    fi

    if [[ "$TARGET" == "xstudio" ]]; then
        # Build all targets to ensure resources (preferences, fonts, plugins) are copied
        info "Building all targets (${CONFIG}, ${JOBS} jobs)..."
        cmake --build "$BUILD_DIR" --config "$CONFIG" -j "$JOBS"
    else
        info "Building target '${TARGET}' (${CONFIG}, ${JOBS} jobs)..."
        cmake --build "$BUILD_DIR" --config "$CONFIG" --target "$TARGET" -j "$JOBS"
    fi
    ok "Build complete"
}

do_deploy() {
    local ext
    ext="$(lib_ext)"

    info "Deploying to portable/..."

    # Ensure destination dirs exist
    mkdir -p portable/bin
    mkdir -p portable/share/xstudio/plugin

    # --- Main executable ---
    local exe_src="$BUILD_DIR/bin/xstudio"
    if [[ -f "$exe_src" ]]; then
        cp -v "$exe_src" portable/bin/
    elif [[ -f "$BUILD_DIR/bin/$CONFIG/xstudio" ]]; then
        cp -v "$BUILD_DIR/bin/$CONFIG/xstudio" portable/bin/
    else
        warn "xstudio executable not found in build output"
    fi

    # --- Core libraries (non-plugin) → portable/bin/ ---
    local core_libs=(
        "src/colour_pipeline/src"
        "src/module/src"
    )
    for lib_path in "${core_libs[@]}"; do
        local full="$BUILD_DIR/$lib_path"
        if [[ -d "$full" ]]; then
            find "$full" -maxdepth 1 -name "*.${ext}" -exec cp -v {} portable/bin/ \;
        fi
    done

    # --- Plugin libraries → portable/share/xstudio/plugin/ ---
    info "Deploying plugins..."
    local plugin_count=0
    while IFS= read -r -d '' plugin_lib; do
        cp -v "$plugin_lib" portable/share/xstudio/plugin/
        ((plugin_count++))
    done < <(find "$BUILD_DIR/src/plugin" -name "*.${ext}" -not -path "*/test/*" -print0 2>/dev/null || true)

    ok "Deployed ${plugin_count} plugins"
    ok "Deploy complete"
}

do_clean() {
    info "Removing build directory..."
    rm -rf "$BUILD_DIR"
    ok "Clean complete"
}

do_clean_qml() {
    info "Cleaning QML autogen cache..."
    rm -rf "$BUILD_DIR/src/launch/xstudio/src/xstudio_autogen/"
    ok "QML cache cleaned. Rebuild required."
}

do_setup() {
    check_prereqs
    ok "Setup complete — ready to build. Run: ./build.sh"
}

# ---------- Main ----------
parse_args "$@"

case "$COMMAND" in
    configure)
        do_configure ;;
    build)
        do_build ;;
    deploy)
        do_deploy ;;
    all)
        do_configure
        do_build
        if [[ "$NO_DEPLOY" == false ]]; then
            do_deploy
        fi
        ;;
    clean)
        do_clean ;;
    clean-qml)
        do_clean_qml ;;
    setup)
        do_setup ;;
esac
