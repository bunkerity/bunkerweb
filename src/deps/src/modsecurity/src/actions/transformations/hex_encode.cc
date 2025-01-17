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

#include "hex_encode.h"

#include "modsecurity/rule_with_actions.h"


namespace modsecurity::actions::transformations {


bool HexEncode::transform(std::string &value, const Transaction *trans) const {
    if (value.empty()) return false;

    std::stringstream result;
    for (const auto c : value) {
        unsigned int ii = (unsigned char)c;
        result << std::setw(2) << std::setfill('0') << std::hex << ii;
    }

    value = result.str();
    return true;
}

}  // namespace modsecurity::actions::transformations
