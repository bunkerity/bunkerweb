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

#include "cmd_line.h"


namespace modsecurity::actions::transformations {


bool CmdLine::transform(std::string &value, const Transaction *trans) const {
    char *d = value.data();
    bool space = false;

    for (const auto& a : value) {
        switch (a) {
            /* remove some characters */
            case '"':
            case '\'':
            case '\\':
            case '^':
                break;

            /* replace some characters to space (only one) */
            case ' ':
            case ',':
            case ';':
            case '\t':
            case '\r':
            case '\n':
                if (space == false) {
                    *d++ = ' ';
                    space = true;
                }
                break;

            /* remove space before / or ( */
            case '/':
            case '(':
                if (space) {
                    d--;
                }
                space = false;
                *d++ = a;
                break;

            /* copy normal characters */
            default :
                char b = std::tolower(a);
                *d++ = b;
                space = false;
                break;
        }
    }

    const auto new_len = d - value.c_str();
    const auto changed = new_len != value.length();
    value.resize(new_len);
    return changed;
}


}  // namespace modsecurity::actions::transformations

