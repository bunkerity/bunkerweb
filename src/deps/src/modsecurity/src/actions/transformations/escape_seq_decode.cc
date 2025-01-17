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

#include "escape_seq_decode.h"

#include "src/utils/string.h"

using namespace modsecurity::utils::string;

namespace modsecurity::actions::transformations {


static inline int ansi_c_sequences_decode_inplace(std::string &value) {
    auto d = reinterpret_cast<unsigned char *>(value.data());
    const unsigned char* input = d;
    const auto input_len = value.length();

    bool changed = false;
    std::string::size_type i = 0;
    while (i < input_len) {
        if ((input[i] == '\\') && (i + 1 < input_len)) {
            int c = -1;

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
                case '\\' :
                    c = '\\';
                    break;
                case '?' :
                    c = '?';
                    break;
                case '\'' :
                    c = '\'';
                    break;
                case '"' :
                    c = '"';
                    break;
            }

            if (c != -1) i += 2;

            /* Hexadecimal or octal? */
            if (c == -1) {
                if ((input[i + 1] == 'x') || (input[i + 1] == 'X')) {
                    /* Hexadecimal. */
                    if ((i + 3 < input_len) && (isxdigit(input[i + 2]))
                        && (isxdigit(input[i + 3]))) {
                        /* Two digits. */
                        c = utils::string::x2c(&input[i + 2]);
                        i += 4;
                    } else {
                        /* Invalid encoding, do nothing. */
                    }
                } else {
                    if (ISODIGIT(input[i + 1])) { /* Octal. */
                        char buf[4];
                        int j = 0;

                        while ((i + 1 + j < input_len) && (j < 3)) {
                            buf[j] = input[i + 1 + j];
                            j++;
                            if (!ISODIGIT(input[i + 1 + j])) break;
                        }
                        buf[j] = '\0';

                        if (j > 0) {
                            c = strtol(buf, NULL, 8);
                            i += 1 + j;
                        }
                    }
                }
            }

            if (c == -1) {
                /* Didn't recognise encoding, copy raw bytes. */
                *d++ = input[i + 1];
                i += 2;
            } else {
                /* Converted the encoding. */
                *d++ = c;
            }

            changed = true;
        } else {
            /* Input character not a backslash, copy it. */
            *d++ = input[i++];
        }
    }

    *d = '\0';

    value.resize(d - input);
    return changed;
}


bool EscapeSeqDecode::transform(std::string &value, const Transaction *trans) const {
    return ansi_c_sequences_decode_inplace(value);
}


}  // namespace modsecurity::actions::transformations
