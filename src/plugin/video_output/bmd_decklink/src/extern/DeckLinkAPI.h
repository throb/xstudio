#pragma once

#if defined(__APPLE__)
#include "mac/DeckLinkAPI.h"
// macOS MacTypes.h defines 'nil' as nullptr, which conflicts with
// CAF's caf::uuid::nil() method. Undefine it after including DeckLink SDK.
#undef nil
#endif

#if defined(_WIN32)
#include <Unknwn.h>
#include "win/DeckLinkAPI.h"
#endif

#if defined(__linux__)
#include "linux/DeckLinkAPI.h"
#endif