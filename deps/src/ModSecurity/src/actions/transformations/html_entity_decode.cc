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

#include "src/actions/transformations/html_entity_decode.h"

#include <string.h>

#include <iostream>
#include <string>
#include <algorithm>
#include <functional>
#include <cctype>
#include <locale>

#include "modsecurity/transaction.h"
#include "src/actions/transformations/transformation.h"


namespace modsecurity {
namespace actions {
namespace transformations {


std::string HtmlEntityDecode::evaluate(std::string value,
    Transaction *transaction) {
    std::string ret;
    unsigned char *input;

    input = reinterpret_cast<unsigned char *>
        (malloc(sizeof(char) * value.length()+1));

    if (input == NULL) {
        return "";
    }

    memcpy(input, value.c_str(), value.length()+1);

    size_t i = inplace(input, value.length());

    ret.assign(reinterpret_cast<char *>(input), i);
    free(input);

    return ret;
}


int HtmlEntityDecode::inplace(unsigned char *input, uint64_t input_len) {
    unsigned char *d = input;
    int i, count;

    if ((input == NULL) || (input_len <= 0)) {
        return 0;
    }

    i = count = 0;
    while ((i < input_len) && (count < input_len)) {
        int z, copy = 1;

        /* Require an ampersand and at least one character to
         * start looking into the entity.
         */
        if ((input[i] == '&') && (i + 1 < input_len)) {
            int k, j = i + 1;

            if (input[j] == '#') {
                /* Numerical entity. */
                copy++;

                if (!(j + 1 < input_len)) {
                    goto HTML_ENT_OUT; /* Not enough bytes. */
                }
                j++;

                if ((input[j] == 'x') || (input[j] == 'X')) {
                    /* Hexadecimal entity. */
                    copy++;

                    if (!(j + 1 < input_len)) {
                        goto HTML_ENT_OUT; /* Not enough bytes. */
                    }
                    j++; /* j is the position of the first digit now. */

                    k = j;
                    while ((j < input_len) && (isxdigit(input[j]))) {
                        j++;
                    }
                    if (j > k) { /* Do we have at least one digit? */
                        /* Decode the entity. */
                        char *x;
                        x = reinterpret_cast<char *>(calloc(sizeof(char),
                            ((j - k) + 1)));
                        memcpy(x, (const char *)&input[k], j - k);
                        *d++ = (unsigned char)strtol(x, NULL, 16);
                        free(x);
                        count++;

                        /* Skip over the semicolon if it's there. */
                        if ((j < input_len) && (input[j] == ';')) {
                            i = j + 1;
                        } else {
                            i = j;
                        }
                        continue;
                    } else {
                        goto HTML_ENT_OUT;
                    }
                } else {
                    /* Decimal entity. */
                    k = j;
                    while ((j < input_len) && (isdigit(input[j]))) {
                        j++;
                    }
                    if (j > k) { /* Do we have at least one digit? */
                        /* Decode the entity. */
                        char *x;
                        x = reinterpret_cast<char *>(calloc(sizeof(char),
                            ((j - k) + 1)));
                        memcpy(x, (const char *)&input[k], j - k);
                        *d++ = (unsigned char)strtol(x, NULL, 10);
                        free(x);
                        count++;

                        /* Skip over the semicolon if it's there. */
                        if ((j < input_len) && (input[j] == ';')) {
                            i = j + 1;
                        } else {
                            i = j;
                        }
                        continue;
                    } else {
                        goto HTML_ENT_OUT;
                    }
                }
            } else {
                /* Text entity. */
                k = j;
                while ((j < input_len) && (isalnum(input[j]))) {
                    j++;
                }
                if (j > k) { /* Do we have at least one digit? */
                    char *x;
                    x = reinterpret_cast<char *>(calloc(sizeof(char),
                        ((j - k) + 1)));
                    memcpy(x, (const char *)&input[k], j - k);

                    /* Decode the entity. */
                    /* ENH What about others? */
                    if (strcasecmp(x, "quot") == 0) {
                        *d++ = '"';
                    } else if (strcasecmp(x, "amp") == 0) {
                        *d++ = '&';
                    } else if (strcasecmp(x, "lt") == 0) {
                        *d++ = '<';
                    } else if (strcasecmp(x, "gt") == 0) {
                        *d++ = '>';
                    } else if (strcasecmp(x, "nbsp") == 0) {
                        *d++ = NBSP;
                    } else {
                        /* We do no want to convert this entity,
                         * copy the raw data over. */
                        copy = j - k + 1;
                        free(x);
                        goto HTML_ENT_OUT;
                    }
                    free(x);

                    count++;

                    /* Skip over the semicolon if it's there. */
                    if ((j < input_len) && (input[j] == ';')) {
                        i = j + 1;
                    } else {
                        i = j;
                    }

                    continue;
                }
            }
        }

HTML_ENT_OUT:

        for (z = 0; ((z < copy) && (count < input_len)); z++) {
            *d++ = input[i++];
            count++;
        }
    }

    *d = '\0';

    return count;
}

}  // namespace transformations
}  // namespace actions
}  // namespace modsecurity
