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

#include "remove_comments.h"


namespace modsecurity::actions::transformations {


static inline int inplace(std::string &value) {
    auto input = reinterpret_cast<unsigned char*>(value.data());
    const auto input_len = value.length();
    bool changed = false, incomment = false;
    std::string::size_type i = 0, j = 0;

    while (i < input_len) {
        if (!incomment) {
            if ((input[i] == '/') && (i + 1 < input_len)
                && (input[i + 1] == '*')) {
                incomment = true;
                changed = true;
                i += 2;
            } else if ((input[i] == '<') && (i + 1 < input_len)
                && (input[i + 1] == '!') && (i + 2 < input_len)
                && (input[i+2] == '-') && (i + 3 < input_len)
                && (input[i + 3] == '-')) {
                incomment = true;
                changed = true;
                i += 4;
            } else if ((input[i] == '-') && (i + 1 < input_len)
                && (input[i + 1] == '-')) {
                input[i] = ' ';
                changed = true;
                break;
            } else if (input[i] == '#') {
                input[i] = ' ';
                changed = true;
                break;
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
                input[j] = input[i];
                i++;
                j++;
            } else if ((input[i] == '-') && (i + 1 < input_len)
                && (input[i + 1] == '-') && (i + 2 < input_len)
                && (input[i+2] == '>'))   {
                incomment = false;
                i += 3;
                input[j] = input[i];
                i++;
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


bool RemoveComments::transform(std::string &value, const Transaction *trans) const {
    return inplace(value);
}


}  // namespace modsecurity::actions::transformations
