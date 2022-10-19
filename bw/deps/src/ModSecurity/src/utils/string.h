/*
 * ModSecurity, http://www.modsecurity.org/
 * Copyright (c) 2015 Trustwave Holdings, Inc. (http://www.trustwave.com/)
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

#include <ctime>
#include <iostream>
#include <string>
#include <vector>

#ifndef SRC_UTILS_STRING_H_
#define SRC_UTILS_STRING_H_

#define VALID_HEX(X) (((X >= '0') && (X <= '9')) || \
    ((X >= 'a') && (X <= 'f')) || ((X >= 'A') && (X <= 'F')))
#define ISODIGIT(X) ((X >= '0') && (X <= '7'))
#define NBSP 160


namespace modsecurity {
namespace utils {
namespace string {

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


std::string ascTime(time_t *t);
std::string dash_if_empty(const char *str);
std::string dash_if_empty(const std::string *str);
std::string limitTo(int amount, const std::string &str);
std::string removeBracketsIfNeeded(std::string a);
std::string string_to_hex(const std::string& input);
std::string toHexIfNeeded(const std::string &str);
std::string tolower(std::string str);
std::string toupper(std::string str);
std::vector<std::string> ssplit(std::string str, char delimiter);
std::pair<std::string, std::string> ssplit_pair(const std::string& str, char delimiter);
std::vector<std::string> split(std::string str, char delimiter);
void chomp(std::string *str);
void replaceAll(std::string *str, const std::string& from,
    const std::string& to);
std::string removeWhiteSpacesIfNeeded(std::string a);
std::string parserSanitizer(std::string a);

unsigned char x2c(unsigned char *what);
unsigned char xsingle2c(unsigned char *what);
unsigned char *c2x(unsigned what, unsigned char *where);

}  // namespace string
}  // namespace utils
}  // namespace modsecurity

#endif  // SRC_UTILS_STRING_H_
