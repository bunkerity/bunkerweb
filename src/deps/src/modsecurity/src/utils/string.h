/*
 * ModSecurity, http://www.modsecurity.org/
 * Copyright (c) 2015 - 2023 Trustwave Holdings, Inc. (http://www.trustwave.com/)
 *
 * You may not use this file except in compliance with
 * the License.  You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * If any of the files related to licensing are missing or if you have any
 * other questions related to licensing please contact Trustwave Holdings, Inc.
 * directly using the email address security@modsecurity.org.
 *
 */

#ifndef SRC_UTILS_STRING_H_
#define SRC_UTILS_STRING_H_

#include <ctime>
#include <string>
#include <cstring>
#include <vector>
#include <algorithm>
#include <utility>
#include <sstream>
#include <iomanip>
#include <time.h>

#ifdef WIN32
#include "src/compat/msvc.h"
#endif

namespace modsecurity::utils::string {

template<typename CharT>
constexpr bool VALID_HEX(CharT X) {
    return ((X >= '0') && (X <= '9')) 
        || ((X >= 'a') && (X <= 'f'))
        || ((X >= 'A') && (X <= 'F'));
}

template<typename CharT>
constexpr bool ISODIGIT(CharT X) {
    return (X >= '0') && (X <= '7');
}

constexpr unsigned char NBSP = 160;

const char HEX2DEC[256] = {
    /*       0  1  2  3   4  5  6  7   8  9  A  B   C  D  E  F */
    /* 0 */ (char)-1, (char)-1, (char)-1, (char)-1,  (char)-1, (char)-1, (char)-1, (char)-1,  (char)-1, (char)-1, (char)-1, (char)-1,  (char)-1, (char)-1, (char)-1, (char)-1,
    /* 1 */ (char)-1, (char)-1, (char)-1, (char)-1,  (char)-1, (char)-1, (char)-1, (char)-1,  (char)-1, (char)-1, (char)-1, (char)-1,  (char)-1, (char)-1, (char)-1, (char)-1,
    /* 2 */ (char)-1, (char)-1, (char)-1, (char)-1,  (char)-1, (char)-1, (char)-1, (char)-1,  (char)-1, (char)-1, (char)-1, (char)-1,  (char)-1, (char)-1, (char)-1, (char)-1,
    /* 3 */  0,  1,  2,  3,   4,  5,  6,  7,   8,  9, (char)-1, (char)-1,  (char)-1, (char)-1, (char)-1, (char)-1,

    /* 4 */ (char)-1, 10, 11, 12,  13, 14, 15, (char)-1,  (char)-1, (char)-1, (char)-1, (char)-1,  (char)-1, (char)-1, (char)-1, (char)-1,
    /* 5 */ (char)-1, (char)-1, (char)-1, (char)-1,  (char)-1, (char)-1, (char)-1, (char)-1,  (char)-1, (char)-1, (char)-1, (char)-1,  (char)-1, (char)-1, (char)-1, (char)-1,
    /* 6 */ (char)-1, 10, 11, 12,  13, 14, 15, (char)-1,  (char)-1, (char)-1, (char)-1, (char)-1,  (char)-1, (char)-1, (char)-1, (char)-1,
    /* 7 */ (char)-1, (char)-1, (char)-1, (char)-1,  (char)-1, (char)-1, (char)-1, (char)-1,  (char)-1, (char)-1, (char)-1, (char)-1,  (char)-1, (char)-1, (char)-1, (char)-1,

    /* 8 */ (char)-1, (char)-1, (char)-1, (char)-1,  (char)-1, (char)-1, (char)-1, (char)-1,  (char)-1, (char)-1, (char)-1, (char)-1,  (char)-1, (char)-1, (char)-1, (char)-1,
    /* 9 */ (char)-1, (char)-1, (char)-1, (char)-1,  (char)-1, (char)-1, (char)-1, (char)-1,  (char)-1, (char)-1, (char)-1, (char)-1,  (char)-1, (char)-1, (char)-1, (char)-1,
    /* A */ (char)-1, (char)-1, (char)-1, (char)-1,  (char)-1, (char)-1, (char)-1, (char)-1,  (char)-1, (char)-1, (char)-1, (char)-1,  (char)-1, (char)-1, (char)-1, (char)-1,
    /* B */ (char)-1, (char)-1, (char)-1, (char)-1,  (char)-1, (char)-1, (char)-1, (char)-1,  (char)-1, (char)-1, (char)-1, (char)-1,  (char)-1, (char)-1, (char)-1, (char)-1,

    /* C */ (char)-1, (char)-1, (char)-1, (char)-1,  (char)-1, (char)-1, (char)-1, (char)-1,  (char)-1, (char)-1, (char)-1, (char)-1,  (char)-1, (char)-1, (char)-1, (char)-1,
    /* D */ (char)-1, (char)-1, (char)-1, (char)-1,  (char)-1, (char)-1, (char)-1, (char)-1,  (char)-1, (char)-1, (char)-1, (char)-1,  (char)-1, (char)-1, (char)-1, (char)-1,
    /* E */ (char)-1, (char)-1, (char)-1, (char)-1,  (char)-1, (char)-1, (char)-1, (char)-1,  (char)-1, (char)-1, (char)-1, (char)-1,  (char)-1, (char)-1, (char)-1, (char)-1,
    /* F */ (char)-1, (char)-1, (char)-1, (char)-1,  (char)-1, (char)-1, (char)-1, (char)-1,  (char)-1, (char)-1, (char)-1, (char)-1,  (char)-1, (char)-1, (char)-1, (char)-1
};


inline std::string ascTime(const time_t *t) {
    struct tm timeinfo;
    localtime_r(t, &timeinfo);
    char tstr[std::size("Www Mmm dd hh:mm:ss yyyy")];
    strftime(tstr, std::size(tstr), "%c", &timeinfo);
    return tstr;
}


inline std::string dash_if_empty(const std::string *str) {
    if (str == nullptr || str->empty()) {
        return "-";
    }

    return *str;
}


inline std::string limitTo(int amount, const std::string &str) {
    std::string ret;

    if (str.length() > amount) {
        ret.assign(str, 0, amount);
        ret = ret + " (" + std::to_string(str.length() - amount) + " " \
            "characters omitted)";
        return ret;
    }

    return str;
}


inline std::string toHexIfNeeded(const std::string &str, bool escape_spec = false) {
    // escape_spec: escape special chars or not
    // spec chars: '"' (quotation mark, ascii 34), '\' (backslash, ascii 92)
    std::stringstream res;

    for (const auto ch : str) {
        int c = (unsigned char)ch;
        if (c < 32 || c > 126 || (escape_spec == true && (c == 34 || c == 92))) {
            res << "\\x" << std::setw(2) << std::setfill('0') << std::hex << c;
        } else {
            res << ch;
        }
    }

    return res.str();
}


inline std::vector<std::string> ssplit(const std::string &str, char delimiter) {
    std::vector<std::string> internal;
    std::stringstream ss(str);  // Turn the string into a stream.
    std::string tok;

    while (getline(ss, tok, delimiter)) {
        internal.push_back(tok);
    }

    return internal;
}


inline std::pair<std::string, std::string> ssplit_pair(const std::string& str, char delimiter) {
    std::stringstream ss(str);  // Turn the string into a stream.
    std::string key;
    std::string value;

    getline(ss, key, delimiter);
    if (key.length() < str.length()) {
        value = str.substr(key.length()+1);
    }

    return std::make_pair(key, value);
}


inline std::vector<std::string> split(const std::string &str, char delimiter) {
    std::vector<std::string> internal = ssplit(str, delimiter);

    if (internal.empty()) {
        internal.push_back(str);
    }

    return internal;
}


inline void chomp(std::string &str) {
    std::string::size_type pos = str.find_last_not_of("\n\r");
    if (pos != std::string::npos) {
        str.erase(pos+1, str.length()-pos-1);
    }
}


inline void replaceAll(std::string &str, std::string_view from,
    std::string_view to) {
    size_t start_pos = 0;
    while ((start_pos = str.find(from, start_pos)) != std::string::npos) {
        str.replace(start_pos, from.length(), to);
        start_pos += to.length();
    }
}


inline std::string removeWhiteSpacesIfNeeded(std::string a) {
    while (a.size() > 1 && a.front() == ' ') {
        a.erase(0, 1);
    }
    while (a.size() > 1 && a.back() == ' ') {
        a.pop_back();
    }
    return a;
}


inline std::string removeBracketsIfNeeded(std::string a) {
    if (a.length() > 1 && a.front() == '"' && a.back() == '"') {
        a.pop_back();
        a.erase(0, 1);
    }
    if (a.length() > 1 && a.front() == '\'' && a.back() == '\'') {
        a.pop_back();
        a.erase(0, 1);
    }
    return a;
}


inline std::string parserSanitizer(std::string a) {
    a = removeWhiteSpacesIfNeeded(a);
    a = removeBracketsIfNeeded(a);
    return a;
}


/**
 * Converts a single hexadecimal digit into a decimal value.
 */
inline unsigned char xsingle2c(const unsigned char *what) {
    unsigned char digit;

    digit = (what[0] >= 'A' ? ((what[0] & 0xdf) - 'A') + 10 : (what[0] - '0'));

    return digit;
}


inline unsigned char x2c(const unsigned char *what) {
    unsigned char digit;

    digit = xsingle2c(what);
    digit *= 16;
    digit += xsingle2c(what+1);

    return digit;
}


inline unsigned char *c2x(unsigned what, unsigned char *where) {
    static const char c2x_table[] = "0123456789abcdef";

    what = what & 0xff;
    *where++ = c2x_table[what >> 4];
    *where++ = c2x_table[what & 0x0f];

    return where;
}


inline std::string string_to_hex(std::string_view input) {
    static const char* const lut = "0123456789abcdef";

    std::string a(input.size()*2, 0);
    char *d = a.data();

    for (const unsigned char c : input) {
        *d++ = lut[c >> 4];
        *d++ = lut[c & 15];
    }

    return a;
}


template<typename Operation>
inline std::string toCaseHelper(std::string str, Operation op) { // cppcheck-suppress syntaxError ; false positive
    std::transform(str.begin(),
            str.end(),
            str.begin(),
            op);

    return str;
}


inline std::string tolower(std::string str) { // cppcheck-suppress passedByValue ; copied value is used for in-place transformation
    return toCaseHelper(str, ::tolower);
}


inline std::string toupper(std::string str) { // cppcheck-suppress passedByValue ; copied value is used for in-place transformation
    return toCaseHelper(str, ::toupper);
}


}  // namespace modsecurity::utils::string

#endif  // SRC_UTILS_STRING_H_
