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

#include "js_decode.h"

#include "src/utils/string.h"

using namespace modsecurity::utils::string;

namespace modsecurity::actions::transformations {


static inline int inplace(std::string &value) {
    auto d = reinterpret_cast<unsigned char*>(value.data());
    const unsigned char *input = d;
    const auto input_len = value.length();

    bool changed = false;
    std::string::size_type i = 0;
    while (i < input_len) {
        if (input[i] == '\\') {
            /* Character is an escape. */

            if ((i + 5 < input_len) && (input[i + 1] == 'u')
                && (VALID_HEX(input[i + 2])) && (VALID_HEX(input[i + 3]))
                && (VALID_HEX(input[i + 4])) && (VALID_HEX(input[i + 5]))) {
                /* \uHHHH */

                /* Use only the lower byte. */
                *d = utils::string::x2c(&input[i + 4]);

                /* Full width ASCII (ff01 - ff5e) needs 0x20 added */
                if ((*d > 0x00) && (*d < 0x5f)
                    && ((input[i + 2] == 'f') || (input[i + 2] == 'F'))
                    && ((input[i + 3] == 'f') || (input[i + 3] == 'F'))) {
                    (*d) += 0x20;
                }

                d++;
                i += 6;
                changed = true;
            } else if ((i + 3 < input_len) && (input[i + 1] == 'x')
                    && VALID_HEX(input[i + 2]) && VALID_HEX(input[i + 3])) {
                /* \xHH */
                *d++ = utils::string::x2c(&input[i + 2]);
                i += 4;
                changed = true;
            } else if ((i + 1 < input_len) && ISODIGIT(input[i + 1])) {
                /* \OOO (only one byte, \000 - \377) */
                char buf[4];
                int j = 0;

                while ((i + 1 + j < input_len) && (j < 3)) {
                    buf[j] = input[i + 1 + j];
                    j++;
                    if (!ISODIGIT(input[i + 1 + j])) break;
                }
                buf[j] = '\0';

                if (j > 0) {
                    /* Do not use 3 characters if we will be > 1 byte */
                    if ((j == 3) && (buf[0] > '3')) {
                        j = 2;
                        buf[j] = '\0';
                    }
                    *d++ = (unsigned char)strtol(buf, NULL, 8);
                    i += 1 + j;
                    changed = true;
                }
            } else if (i + 1 < input_len) {
                /* \C */
                unsigned char c = input[i + 1];
                switch (input[i + 1]) {
                    case 'a' :
                        c = '\a';
                        break;
                    case 'b' :
                        c = '\b';
                        break;
                    case 'f' :
                        c = '\f';
                        break;
                    case 'n' :
                        c = '\n';
                        break;
                    case 'r' :
                        c = '\r';
                        break;
                    case 't' :
                        c = '\t';
                        break;
                    case 'v' :
                        c = '\v';
                        break;
                        /* The remaining (\?,\\,\',\") are just a removal
                         * of the escape char which is default.
                         */
                }

                *d++ = c;
                i += 2;
                changed = true;
            } else {
                /* Not enough bytes */
                while (i < input_len) {
                    *d++ = input[i++];
                }
            }
        } else {
            *d++ = input[i++];
        }
    }

    *d = '\0';

    value.resize(d - input);
    return changed;
}


bool JsDecode::transform(std::string &value, const Transaction *trans) const {
    return inplace(value);
}


}  // namespace modsecurity::actions::transformations
