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

#include "trim.h"

#include <algorithm>


namespace modsecurity::actions::transformations {


bool Trim::ltrim(std::string &s) {
    auto it = std::find_if(s.begin(), s.end(), [](unsigned char c) {
            return !std::isspace(c);
        });

    const bool changed = it != s.begin();

    s.erase(s.begin(), it);

    return changed;
}


bool Trim::rtrim(std::string &s) {
    auto it = std::find_if(s.rbegin(), s.rend(), [](unsigned char c) {
            return !std::isspace(c);
        }).base();

    const bool changed = it != s.end();

    s.erase(it, s.end());

    return changed;
}


bool Trim::trim(std::string &s) {
    bool changed = false;
    changed |= rtrim(s);
    changed |= ltrim(s);
    return changed;
}


bool Trim::transform(std::string &value, const Transaction *trans) const {
    return trim(value);
}


}  // namespace modsecurity::actions::transformations
