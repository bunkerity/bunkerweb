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

#include "url_encode.h"

#include "src/utils/string.h"

namespace modsecurity::actions::transformations {


static inline bool url_enc(std::string &value) {
    const auto len = value.size() * 3 + 1;
    std::string ret(len, {});

    bool changed = false;

    /* ENH Only encode the characters that really need to be encoded. */

    char *d = ret.data();
    for (const auto c : value) {
        if (c == ' ') {
            *d++ = '+';
            changed = true;
        } else {
            if ( (c == 42) || ((c >= 48) && (c <= 57))
                || ((c >= 65) && (c <= 90))
                || ((c >= 97) && (c <= 122))) {
                *d++ = c;
            }
            else
            {
                *d++ = '%';
                d = (char *)utils::string::c2x(c, (unsigned char *)d);
                changed = true;
            }
        }
    }

    ret.resize(d - ret.c_str());
    std::swap(value, ret);
    return changed;
}


bool UrlEncode::transform(std::string &value, const Transaction *trans) const {
    return url_enc(value);
}


}  // namespace modsecurity::actions::transformations
