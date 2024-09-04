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

#include "compress_whitespace.h"


namespace modsecurity::actions::transformations {


bool CompressWhitespace::transform(std::string &value, const Transaction *trans) const {
    bool inWhiteSpace = false;

    auto d = value.data();

    for(const auto c : value) {
        if (isspace(c)) {
            if (inWhiteSpace) {
                continue;
            } else {
                inWhiteSpace = true;
                *d++ = ' ';
            }
        } else {
            inWhiteSpace = false;
            *d++ = c;
        }
    }

    const auto new_len = d - value.c_str();
    const auto changed = new_len != value.length();
    value.resize(new_len);
    return changed;
}


}  // namespace modsecurity::actions::transformations
