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

#include "sql_hex_decode.h"

#include <cstring>

#include "src/utils/string.h"

using namespace modsecurity::utils::string;

namespace modsecurity::actions::transformations {


static inline int mytolower(int ch) {
    if (ch >= 'A' && ch <= 'Z')
        return ('a' + ch - 'A');
    else
        return ch;
}

static inline bool inplace(std::string &value) {
    if (value.empty()) {
        return false;
    }

    auto d = reinterpret_cast<unsigned char*>(value.data());
    const unsigned char *data = d;
    const auto end = data + value.size();

    bool changed = false;

    while (data < end) {
        if (data + 3 < end
            && *data == '0'
            && mytolower(*(data + 1)) == 'x'
            && VALID_HEX(*(data + 2)) && VALID_HEX(*(data + 3))) {
            data += 2;  // skip '0x'
            do {
                *d++ = utils::string::x2c(data);
                data += 2;
            } while ((data + 1 < end) && VALID_HEX(*data) && VALID_HEX(*(data + 1)));
            changed = true;
        }
        else {
            *d++ = *data++;
        }
    }

    *d = '\0';

    value.resize(d - reinterpret_cast<const unsigned char*>(value.c_str()));
    return changed;
}


bool SqlHexDecode::transform(std::string &value, const Transaction *trans) const {
    return inplace(value);
}


}  // namespace modsecurity::actions::transformations
