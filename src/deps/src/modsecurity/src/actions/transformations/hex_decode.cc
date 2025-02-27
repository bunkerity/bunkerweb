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

#include "hex_decode.h"

#include "src/utils/string.h"


namespace modsecurity::actions::transformations {


static inline int inplace(std::string &value) {
    if (value.empty()) return false;

    const auto len = value.length();
    auto d = reinterpret_cast<unsigned char *>(value.data());
    const auto *data = d;

    for (int i = 0; i <= len - 2; i += 2) {
        *d++ = utils::string::x2c(&data[i]);
    }

    *d = '\0';

    value.resize(d - data);
    return true;
}


bool HexDecode::transform(std::string &value, const Transaction *trans) const {
    return inplace(value);
}


}  // namespace modsecurity::actions::transformations
