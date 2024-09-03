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

#include "url_decode_uni.h"

#include "modsecurity/rules_set.h"
#include "src/utils/string.h"

using namespace modsecurity::utils::string;

namespace modsecurity::actions::transformations {


/**
 *
 * IMP1 Assumes NUL-terminated
 */
static inline bool inplace(std::string &value,
    const Transaction *t) {
    bool changed = false;
    auto d = reinterpret_cast<unsigned char*>(value.data());
    const unsigned char *input = d;
    const auto input_len = value.length();

    std::string::size_type i, count, fact, j, xv;
    int Code, hmap = -1;

    i = count = 0;
    while (i < input_len) {
        if (input[i] == '%') {
            if ((i + 1 < input_len) &&
                ((input[i + 1] == 'u') || (input[i + 1] == 'U'))) {
            /* Character is a percent sign. */
                /* IIS-specific %u encoding. */
                if (i + 5 < input_len) {
                    /* We have at least 4 data bytes. */
                    if ((VALID_HEX(input[i + 2])) &&
                        (VALID_HEX(input[i + 3])) &&
                        (VALID_HEX(input[i + 4])) &&
                        (VALID_HEX(input[i + 5]))) {
                        Code = 0;
                        fact = 1;

                        if (t
                            && t->m_rules->m_unicodeMapTable.m_set == true
                            && t->m_rules->m_unicodeMapTable.m_unicodeMapTable != NULL
                            && t->m_rules->m_unicodeMapTable.m_unicodeCodePage > 0)  {
                            for (j = 5; j >= 2; j--) {
                                if (isxdigit((input[i+j]))) {
                                    if (input[i+j] >= 97) {
                                        xv = (input[i+j] - 97) + 10;
                                    } else if (input[i+j] >= 65)  {
                                        xv = (input[i+j] - 65) + 10;
                                    } else {
                                        xv = (input[i+j]) - 48;
                                    }
                                    Code += (xv * fact);
                                    fact *= 16;
                                }
                            }

                            if (Code >= 0 && Code <= 65535)  {
                                RulesSet *r = t->m_rules;
                                hmap = r->m_unicodeMapTable.m_unicodeMapTable->at(Code);
                            }
                        }

                        if (hmap != -1)  {
                            *d = hmap;
                        } else {
                            /* We first make use of the lower byte here,
                             * ignoring the higher byte. */
                            *d = utils::string::x2c(&input[i + 4]);

                            /* Full width ASCII (ff01 - ff5e)
                             * needs 0x20 added */
                            if ((*d > 0x00) && (*d < 0x5f)
                                    && ((input[i + 2] == 'f')
                                    || (input[i + 2] == 'F'))
                                    && ((input[i + 3] == 'f')
                                    || (input[i + 3] == 'F'))) {
                                (*d) += 0x20;
                            }
                        }
                        d++;
                        i += 6;
                        changed = true;
                    } else {
                        /* Invalid data, skip %u. */
                        *d++ = input[i++];
                        *d++ = input[i++];
                    }
                } else {
                    /* Not enough bytes (4 data bytes), skip %u. */
                    *d++ = input[i++];
                    *d++ = input[i++];
                }
            } else {
                /* Standard URL encoding. */
                /* Are there enough bytes available? */
                if (i + 2 < input_len) {
                    /* Yes. */

                    /* Decode a %xx combo only if it is valid.
                     */
                    char c1 = input[i + 1];
                    char c2 = input[i + 2];

                    if (VALID_HEX(c1) && VALID_HEX(c2)) {
                        *d++ = utils::string::x2c(&input[i + 1]);
                        i += 3;
                        changed = true;
                    } else {
                        /* Not a valid encoding, skip this % */
                        *d++ = input[i++];
                        count++;
                    }
                } else {
                    /* Not enough bytes available, skip this % */
                    *d++ = input[i++];
                }
            }
        } else {
            /* Character is not a percent sign. */
            if (input[i] == '+') {
                *d++ = ' ';
                changed = true;
            } else {
                *d++ = input[i];
            }

            i++;
        }
    }

    *d = '\0';

    value.resize(d - input);
    return changed;
}



bool UrlDecodeUni::transform(std::string &value, const Transaction *trans) const {
    return inplace(value, trans);
}


}  // namespace modsecurity::actions::transformations
