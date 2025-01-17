/*
 * ModSecurity, http://www.modsecurity.org/
 * Copyright (c) 2015 - 2023 Trustwave Holdings, Inc. (http://www.trustwave.com/)
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

#include "remove_comments_char.h"


namespace modsecurity::actions::transformations {


bool RemoveCommentsChar::transform(std::string &value, const Transaction *trans) const {
    char *d = value.data();
    const char *s = d;
    const char *e = s + value.size();

    while (s < e) {
        if (*s == '/'
            && (s+1 < e) && *(s+1) == '*') {
            s += 2;
        } else if (*s == '*'
            && (s+1 < e) && *(s+1) == '/') {
            s += 2;
        } else if (*s == '<'
            && (s+1 < e)
            && *(s+1) == '!'
            && (s+2 < e)
            && *(s+2) == '-'
            && (s+3 < e)
            && *(s+3) == '-') {
            s += 4;
        } else if (*s == '-'
            && (s+1 < e) && *(s+1) == '-'
            && (s+2 < e) && *(s+2) == '>') {
            s += 3;
        } else if (*s == '-'
            && (s+1 < e) && *(s+1) == '-') {
            s += 2;
        } else if (*s == '#') {
            s += 1;
        } else {
            *d++ = *s++;
        }
    }

    const auto changed = d != s;
    const auto new_len = d - value.c_str();
    value.resize(new_len);
    return changed;
}

}  // namespace modsecurity::actions::transformations

