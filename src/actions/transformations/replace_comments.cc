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

#include "replace_comments.h"


namespace modsecurity::actions::transformations {


static inline bool inplace(std::string &value) {
    auto input = reinterpret_cast<unsigned char*>(value.data());
    const auto input_len = value.length();
    bool changed = false, incomment = false;
    std::string::size_type i = 0, j = 0;

    while (i < input_len) {
        if (!incomment) {
            if ((input[i] == '/') && (i + 1 < input_len)
                && (input[i + 1] == '*')) {
                incomment = true;
                i += 2;
                changed = true;
            } else {
                input[j] = input[i];
                i++;
                j++;
            }
        } else {
            if ((input[i] == '*') && (i + 1 < input_len)
                && (input[i + 1] == '/')) {
                incomment = false;
                i += 2;
                input[j] = ' ';
                j++;
            } else {
                i++;
            }
        }
    }

    if (incomment) {
        input[j++] = ' ';
    }

    value.resize(j);
    return changed;
}


bool ReplaceComments::transform(std::string &value, const Transaction *trans) const {
    return inplace(value);
}


}  // namespace modsecurity::actions::transformations
