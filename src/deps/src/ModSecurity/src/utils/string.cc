/*
 * ModSecurity, http://www.modsecurity.org/
 * Copyright (c) 2015 - 2021 Trustwave Holdings, Inc. (http://www.trustwave.com/)
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

#include <stdio.h>
#include <stdlib.h>
#include <stddef.h>
#include <string.h>
#ifdef __OpenBSD__
#include <glob.h>
#else
#include <wordexp.h>
#endif
#include <stdint.h>
#include <inttypes.h>

#include <algorithm>
#include <random>
#include <memory>
#include <functional>
#include <string>
#include <iostream>
#include <sstream>
#include <cstring>

#if defined _MSC_VER
#include <direct.h>
#elif defined __GNUC__
#include <sys/types.h>
#include <sys/stat.h>
#endif

#include "modsecurity/modsecurity.h"

#include "src/utils/string.h"


namespace modsecurity {
namespace utils {
namespace string {


std::string parserSanitizer(std::string a) {
    a = removeWhiteSpacesIfNeeded(a);
    a = removeBracketsIfNeeded(a);
    return a;
}


std::string removeWhiteSpacesIfNeeded(std::string a) {
    while (a.size() > 1 && a.at(0) == ' ') {
        a.erase(0, 1);
    }
    while (a.size() > 1 && a.at(a.length()-1) == ' ') {
        a.pop_back();
    }
    return a;
}


std::string ascTime(time_t *t) {
    std::string ts = std::ctime(t);
    ts.pop_back();
    return ts;
}


std::string dash_if_empty(const std::string *str) {
    if (str == NULL || str->empty()) {
        return "-";
    }

    return *str;
}


std::string dash_if_empty(const char *str) {
    if (str == NULL || strlen(str) == 0) {
        return "-";
    }

    return std::string(str);
}


std::string limitTo(int amount, const std::string &str) {
    std::string ret;

    if (str.length() > amount) {
        ret.assign(str, 0, amount);
        ret = ret + " (" + std::to_string(str.length() - amount) + " " \
            "characters omitted)";
        return ret;
    }

    return str;
}


std::string removeBracketsIfNeeded(std::string a) {
    if (a.length() > 1 && a.at(0) == '"' && a.at(a.length()-1) == '"') {
        a.pop_back();
        a.erase(0, 1);
    }
    if (a.length() > 1 && a.at(0) == '\'' && a.at(a.length()-1) == '\'') {
        a.pop_back();
        a.erase(0, 1);
    }
    return a;
}


std::string string_to_hex(const std::string& input) {
    static const char* const lut = "0123456789ABCDEF";
    size_t len = input.length();

    std::string output;
    output.reserve(2 * len);
    for (size_t i = 0; i < len; ++i) {
        const unsigned char c = input[i];
        output.push_back(lut[c >> 4]);
        output.push_back(lut[c & 15]);
    }
    return output;
}

std::string toHexIfNeeded(const std::string &str, bool escape_spec) {
    // escape_spec: escape special chars or not
    // spec chars: '"' (quotation mark, ascii 34), '\' (backslash, ascii 92)
    std::stringstream res;

    for (int i = 0; i < str.size(); i++) {
        int c = (unsigned char)str.at(i);
        if (c < 32 || c > 126 || (escape_spec == true && (c == 34 || c == 92))) {
            res << "\\x" << std::setw(2) << std::setfill('0') << std::hex << c;
        } else {
            res << str.at(i);
        }
    }

    return res.str();
}


std::string tolower(std::string str) {
    std::string value;
    value.resize(str.length());

    std::transform(str.begin(),
            str.end(),
            value.begin(),
            ::tolower);

    return value;
}


std::string toupper(std::string str) {
    std::string value;
    value.resize(str.length());

    std::transform(str.begin(),
            str.end(),
            value.begin(),
            ::toupper);

    return value;
}


std::vector<std::string> ssplit(std::string str, char delimiter) {
    std::vector<std::string> internal;
    std::stringstream ss(str);  // Turn the string into a stream.
    std::string tok;

    while (getline(ss, tok, delimiter)) {
        internal.push_back(tok);
    }

    return internal;
}


std::pair<std::string, std::string> ssplit_pair(const std::string& str, char delimiter) {
    std::stringstream ss(str);  // Turn the string into a stream.
    std::string key;
    std::string value;

    getline(ss, key, delimiter);
    if (key.length() < str.length()) {
        value = str.substr(key.length()+1);
    }

    return std::make_pair(key, value);
}


std::vector<std::string> split(std::string str, char delimiter) {
    std::vector<std::string> internal = ssplit(str, delimiter);

    if (internal.size() == 0) {
        internal.push_back(str);
    }

    return internal;
}


void chomp(std::string *str) {
    std::string::size_type pos = str->find_last_not_of("\n\r");
    if (pos != std::string::npos) {
        str->erase(pos+1, str->length()-pos-1);
    }
}


unsigned char x2c(unsigned char *what) {
    unsigned char digit;

    digit = (what[0] >= 'A' ? ((what[0] & 0xdf) - 'A') + 10 : (what[0] - '0'));
    digit *= 16;
    digit += (what[1] >= 'A' ? ((what[1] & 0xdf) - 'A') + 10 : (what[1] - '0'));

    return digit;
}


/**
 * Converts a single hexadecimal digit into a decimal value.
 */
unsigned char xsingle2c(unsigned char *what) {
    unsigned char digit;

    digit = (what[0] >= 'A' ? ((what[0] & 0xdf) - 'A') + 10 : (what[0] - '0'));

    return digit;
}


unsigned char *c2x(unsigned what, unsigned char *where) {
    static const char c2x_table[] = "0123456789abcdef";

    what = what & 0xff;
    *where++ = c2x_table[what >> 4];
    *where++ = c2x_table[what & 0x0f];

    return where;
}


void replaceAll(std::string *str, const std::string& from,
    const std::string& to) {
    size_t start_pos = 0;
    while ((start_pos = str->find(from, start_pos)) != std::string::npos) {
        str->replace(start_pos, from.length(), to);
        start_pos += to.length();
    }
}

}  // namespace string
}  // namespace utils
}  // namespace modsecurity
