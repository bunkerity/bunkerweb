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

#include "src/utils/decode.h"
#include "modsecurity/modsecurity.h"
#include "src/utils/string.h"

using namespace modsecurity::utils::string;

namespace modsecurity::utils {


bool urldecode_nonstrict_inplace(std::string &val,
    int &invalid_count) {
    unsigned char *d = (unsigned char *)val.data();
    unsigned char *s = d;
    const unsigned char *e = s + val.size();

    invalid_count = 0;
    bool changed = false;

    while (s != e) {
        if (*s == '%') {
            /* Character is a percent sign. */

            /* Are there enough bytes available? */
            if (s + 2 < e) {
                const auto c1 = *(s + 1);
                const auto c2 = *(s + 2);
                if (VALID_HEX(c1) && VALID_HEX(c2)) {
                    const auto uni = string::x2c(s + 1);

                    *d++ = uni;
                    s += 3;
                    changed = true;
                } else {
                    /* Not a valid encoding, skip this % */
                    *d++ = *s++;
                    invalid_count++;
                }
            } else {
                /* Not enough bytes available, copy the raw bytes. */
                *d++ = *s++;
                invalid_count++;
            }
        } else {
            /* Character is not a percent sign. */
            if (*s == '+') {
                *d++ = ' ';
                changed = true;
            } else {
                *d++ = *s;
            }
            s++;
        }
    }

    if (changed)
        val.resize((char*) d - val.c_str());

    return changed;
}


std::string uri_decode(const std::string & sSrc) {
    // Note from RFC1630: "Sequences which start with a percent
    // sign but are not followed by two hexadecimal characters
    // (0-9, A-F) are reserved for future extension"

    const unsigned char * pSrc = (const unsigned char *)sSrc.c_str();
    const int SRC_LEN = sSrc.length();
    const unsigned char * const SRC_END = pSrc + SRC_LEN;
    // last decodable '%'
    const unsigned char * const SRC_LAST_DEC = SRC_END - 2;

    char * const pStart = new char[SRC_LEN];
    char * pEnd = pStart;

    while (pSrc < SRC_LAST_DEC) {
        if (*pSrc == '%') {
            char dec1, dec2;
            if ((char)-1 != (dec1 = string::HEX2DEC[*(pSrc + 1)])
                && (char)-1 != (dec2 = string::HEX2DEC[*(pSrc + 2)])) {
                *pEnd++ = (dec1 << 4) + dec2;
                pSrc += 3;
                continue;
            }
        }
        *pEnd++ = *pSrc++;
    }

    // the last 2- chars
    while (pSrc < SRC_END) {
        *pEnd++ = *pSrc++;
    }

    std::string sResult(pStart, pEnd);
    delete [] pStart;
    return sResult;
}


}  // namespace modsecurity::utils
