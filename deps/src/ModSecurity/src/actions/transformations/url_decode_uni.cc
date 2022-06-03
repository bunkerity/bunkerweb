/*
 * ModSecurity, http://www.modsecurity.org/
 * Copyright (c) 2015 Trustwave Holdings, Inc. (http://www.trustwave.com/)
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

#include "src/actions/transformations/url_decode_uni.h"

#include <string.h>

#include <iostream>
#include <string>
#include <algorithm>
#include <functional>
#include <cctype>
#include <locale>
#include <cstring>

#include "modsecurity/transaction.h"
#include "src/actions/transformations/transformation.h"
#include "src/utils/string.h"
#include "src/utils/system.h"
#include "modsecurity/rules.h"
#include "modsecurity/rules_properties.h"


namespace modsecurity {
namespace actions {
namespace transformations {


std::string UrlDecodeUni::evaluate(std::string value,
    Transaction *t) {
    std::string ret;
    unsigned char *input;

    input = reinterpret_cast<unsigned char *>
        (malloc(sizeof(char) * value.length()+1));

    if (input == NULL) {
        return "";
    }

    memcpy(input, value.c_str(), value.length()+1);

    size_t i = inplace(input, value.length(), t);

    ret.assign(reinterpret_cast<char *>(input), i);
    free(input);

    return ret;
}


/**
 *
 * IMP1 Assumes NUL-terminated
 */
int UrlDecodeUni::inplace(unsigned char *input, uint64_t input_len,
    Transaction *t) {
    unsigned char *d = input;
    int64_t i, count, fact, j, xv;
    int Code, hmap = -1;

    if (input == NULL) return -1;

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
                                Rules *r = t->m_rules;
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
                        count++;
                        i += 6;
                    } else {
                        /* Invalid data, skip %u. */
                        *d++ = input[i++];
                        *d++ = input[i++];
                        count += 2;
                    }
                } else {
                    /* Not enough bytes (4 data bytes), skip %u. */
                    *d++ = input[i++];
                    *d++ = input[i++];
                    count += 2;
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
                        count++;
                        i += 3;
                    } else {
                        /* Not a valid encoding, skip this % */
                        *d++ = input[i++];
                        count++;
                    }
                } else {
                    /* Not enough bytes available, skip this % */
                    *d++ = input[i++];
                    count++;
                }
            }
        } else {
            /* Character is not a percent sign. */
            if (input[i] == '+') {
                *d++ = ' ';
            } else {
                *d++ = input[i];
            }

            count++;
            i++;
        }
    }

    *d = '\0';

    return count;
}


}  // namespace transformations
}  // namespace actions
}  // namespace modsecurity
