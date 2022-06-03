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

#include "src/actions/transformations/css_decode.h"

#include <string.h>

#include <iostream>
#include <string>
#include <algorithm>
#include <functional>
#include <cctype>
#include <locale>

#include "modsecurity/transaction.h"
#include "src/actions/transformations/transformation.h"
#include "src/utils/string.h"


namespace modsecurity {
namespace actions {
namespace transformations {


std::string CssDecode::evaluate(std::string value,
    Transaction *transaction) {

    char *tmp = reinterpret_cast<char *>(
        malloc(sizeof(char) * value.size() + 1));
    memcpy(tmp, value.c_str(), value.size() + 1);
    tmp[value.size()] = '\0';

    CssDecode::css_decode_inplace(reinterpret_cast<unsigned char *>(tmp),
        value.size());

    std::string ret(tmp, 0, value.size());
    free(tmp);
    return ret;
}


/**
 * Decode a string that contains CSS-escaped characters.
 *
 * References:
 *     http://www.w3.org/TR/REC-CSS2/syndata.html#q4
 *     http://www.unicode.org/roadmaps/
 */
int CssDecode::css_decode_inplace(unsigned char *input, int64_t input_len) {
    unsigned char *d = (unsigned char *)input;
    int64_t i, j, count;

    if (input == NULL) {
        return -1;
    }

    i = count = 0;
    while (i < input_len) {
        /* Is the character a backslash? */
        if (input[i] == '\\') {
            /* Is there at least one more byte? */
            if (i + 1 < input_len) {
                i++; /* We are not going to need the backslash. */

                /* Check for 1-6 hex characters following the backslash */
                j = 0;
                while ((j < 6)
                        && (i + j < input_len)
                        && (VALID_HEX(input[i + j]))) {
                    j++;
                }

                if (j > 0) {
                    /* We have at least one valid hexadecimal character. */
                    int fullcheck = 0;

                    /* For now just use the last two bytes. */
                    switch (j) {
                        /* Number of hex characters */
                        case 1:
                            *d++ = utils::string::xsingle2c(&input[i]);
                            break;

                        case 2:
                        case 3:
                            /* Use the last two from the end. */
                            *d++ = utils::string::x2c(&input[i + j - 2]);
                            break;

                        case 4:
                            /* Use the last two from the end, but request
                             * a full width check.
                             */
                            *d = utils::string::x2c(&input[i + j - 2]);
                            fullcheck = 1;
                            break;

                        case 5:
                            /* Use the last two from the end, but request
                             * a full width check if the number is greater
                             * or equal to 0xFFFF.
                             */
                            *d = utils::string::x2c(&input[i + j - 2]);
                            /* Do full check if first byte is 0 */
                            if (input[i] == '0') {
                                fullcheck = 1;
                            } else {
                                d++;
                            }
                            break;

                        case 6:
                            /* Use the last two from the end, but request
                             * a full width check if the number is greater
                             * or equal to 0xFFFF.
                             */
                            *d = utils::string::x2c(&input[i + j - 2]);

                            /* Do full check if first/second bytes are 0 */
                            if ((input[i] == '0')
                                    && (input[i + 1] == '0')) {
                                fullcheck = 1;
                            } else {
                                d++;
                            }
                            break;
                    }

                    /* Full width ASCII (0xff01 - 0xff5e) needs 0x20 added */
                    if (fullcheck) {
                        if ((*d > 0x00) && (*d < 0x5f)
                                && ((input[i + j - 3] == 'f') ||
                                    (input[i + j - 3] == 'F'))
                                && ((input[i + j - 4] == 'f') ||
                                    (input[i + j - 4] == 'F'))) {
                            (*d) += 0x20;
                        }

                        d++;
                    }

                    /* We must ignore a single whitespace after a hex escape */
                    if ((i + j < input_len) && isspace(input[i + j])) {
                        j++;
                    }

                    /* Move over. */
                    count++;
                    i += j;
                } else if (input[i] == '\n') {
                /* No hexadecimal digits after backslash */
                    /* A newline character following backslash is ignored. */
                    i++;
                } else {
                /* The character after backslash is not a hexadecimal digit,
                 * nor a newline. */
                    /* Use one character after backslash as is. */
                    *d++ = input[i++];
                    count++;
                }
            } else {
            /* No characters after backslash. */
                /* Do not include backslash in output
                 *(continuation to nothing) */
                i++;
            }
        } else {
        /* Character is not a backslash. */
            /* Copy one normal character to output. */
            *d++ = input[i++];
            count++;
        }
    }

    /* Terminate output string. */
    *d = '\0';

    return count;
}


}  // namespace transformations
}  // namespace actions
}  // namespace modsecurity
