#pragma once
#include <string>
#ifdef __APPLE__
  #include <CoreFoundation/CoreFoundation.h>
  inline std::string decklink_string_to_std(CFStringRef cfstr) {
      if (!cfstr) return "";
      char buf[512];
      if (CFStringGetCString(cfstr, buf, sizeof(buf), kCFStringEncodingUTF8))
          return std::string(buf);
      return "";
  }
  inline void decklink_free_string(CFStringRef cfstr) { if (cfstr) CFRelease(cfstr); }
  #define DECKLINK_STR CFStringRef
#else
  inline std::string decklink_string_to_std(const char* str) { return str ? str : ""; }
  inline void decklink_free_string(const char*) { /* Linux SDK manages string lifetime */ }
  #define DECKLINK_STR const char*
#endif
