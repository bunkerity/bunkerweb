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

#include "src/actions/transformations/utf8_to_unicode.h"

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


namespace modsecurity {
namespace actions {
namespace transformations {


std::string Utf8ToUnicode::evaluate(std::string value,
    Transaction *transaction) {
    std::string ret;
    unsigned char *input;
    int changed = 0;
    char *out;

    input = reinterpret_cast<unsigned char *>
        (malloc(sizeof(char) * value.length()+1));

    if (input == NULL) {
        return "";
    }

    memcpy(input, value.c_str(), value.length()+1);

    out = inplace(input, value.size() + 1, &changed);
    free(input);
    if (out != NULL) {
        ret.assign(reinterpret_cast<char *>(out),
            strlen(reinterpret_cast<char *>(out)));
        free(out);
    }

    return ret;
}


char *Utf8ToUnicode::inplace(unsigned char *input,
    uint64_t input_len, int *changed) {
    int length = 0;
    unsigned int count = 0;
    char *data;
    char *data_orig;
    unsigned int i, len, j;
    unsigned int bytes_left = input_len;
    unsigned char unicode[8];
    *changed = 0;

    /* RFC3629 states that UTF-8 are encoded using sequences of 1 to 4 octets. */
    /* Max size per character should fit in 4 bytes */
    len = input_len * 4 + 1;
    data = reinterpret_cast<char *>(malloc(sizeof(char) * len));
    if (data == NULL) {
        return NULL;
    }
    data_orig = data;

    if (input == NULL) {
        free(data);
        return NULL;
    }

    for (i = 0; i < bytes_left;)  {
        int unicode_len = 0;
        unsigned int d = 0;
        unsigned char c;
        unsigned char *utf = (unsigned char *)&input[i];

        c = *utf;

        /* If first byte begins with binary 0 it is single byte encoding */
        if ((c & 0x80) == 0) {
            /* single byte unicode (7 bit ASCII equivilent) has no validation */
            count++;
            if (count <= len) {
                if (c == 0 && input_len > i + 1) {
                    unsigned char z[2];
                    z[0] = *utf;
                    z[1] = *(utf + 1);
                    *data = utils::string::x2c((unsigned char*) &z);
                } else {
                    *data++ = c;
                }
            }
        } else if ((c & 0xE0) == 0xC0) {
            /* If first byte begins with binary 110 it is two byte encoding*/
            /* check we have at least two bytes */
            if (bytes_left < 2) {
                /* check second byte starts with binary 10 */
                unicode_len = UNICODE_ERROR_CHARACTERS_MISSING;
            } else if (((*(utf + 1)) & 0xC0) != 0x80) {
                unicode_len = UNICODE_ERROR_INVALID_ENCODING;
            } else {
                unicode_len = 2;
                count+=6;
                if (count <= len) {
                    /* compute character number */
                    d = ((c & 0x1F) << 6) | (*(utf + 1) & 0x3F);
                    *data++ = '%';
                    *data++ = 'u';
                    snprintf(reinterpret_cast<char *>(unicode),
                             sizeof(reinterpret_cast<char *>(unicode)),
                             "%x", d);
                    length = strlen(reinterpret_cast<char *>(unicode));

                    switch (length) {
                        case 1:
                            *data++ = '0';
                            *data++ = '0';
                            *data++ = '0';
                            break;
                        case 2:
                            *data++ = '0';
                            *data++ = '0';
                            break;
                        case 3:
                            *data++ = '0';
                            break;
                        case 4:
                        case 5:
                            break;
                    }

                    for (j = 0; j < length; j++) {
                        *data++ = unicode[j];
                    }

                    *changed = 1;
                }
            }
        } else if ((c & 0xF0) == 0xE0) {
        /* If first byte begins with binary 1110 it is three byte encoding */
            /* check we have at least three bytes */
            if (bytes_left < 3) {
                /* check second byte starts with binary 10 */
                unicode_len = UNICODE_ERROR_CHARACTERS_MISSING;
            } else if (((*(utf + 1)) & 0xC0) != 0x80) {
                /* check third byte starts with binary 10 */
                unicode_len = UNICODE_ERROR_INVALID_ENCODING;
            } else if (((*(utf + 2)) & 0xC0) != 0x80) {
                unicode_len = UNICODE_ERROR_INVALID_ENCODING;
            } else {
                unicode_len = 3;
                count+=6;
                if (count <= len) {
                    /* compute character number */
                    d = ((c & 0x0F) << 12)
                        | ((*(utf + 1) & 0x3F) << 6)
                        | (*(utf + 2) & 0x3F);
                    *data++ = '%';
                    *data++ = 'u';
                    snprintf(reinterpret_cast<char *>(unicode),
                             sizeof(reinterpret_cast<char *>(unicode)),
                             "%x", d);
                    length = strlen(reinterpret_cast<char *>(unicode));

                    switch (length)  {
                        case 1:
                            *data++ = '0';
                            *data++ = '0';
                            *data++ = '0';
                            break;
                        case 2:
                            *data++ = '0';
                            *data++ = '0';
                            break;
                        case 3:
                            *data++ = '0';
                            break;
                        case 4:
                        case 5:
                            break;
                    }

                    for (j = 0; j < length; j++) {
                        *data++ = unicode[j];
                    }

                    *changed = 1;
                }
            }
        } else if ((c & 0xF8) == 0xF0) {
            /* If first byte begins with binary 11110 it
             * is four byte encoding
             */
            /* restrict characters to UTF-8 range (U+0000 - U+10FFFF) */
            if (c >= 0xF5) {
                *data++ = c;
            }
            /* check we have at least four bytes */
            if (bytes_left < 4) {
                /* check second byte starts with binary 10 */
                unicode_len = UNICODE_ERROR_CHARACTERS_MISSING;
            } else if (((*(utf + 1)) & 0xC0) != 0x80) {
                /* check third byte starts with binary 10 */
                unicode_len = UNICODE_ERROR_INVALID_ENCODING;
            } else if (((*(utf + 2)) & 0xC0) != 0x80) {
                /* check forth byte starts with binary 10 */
                unicode_len = UNICODE_ERROR_INVALID_ENCODING;
            } else if (((*(utf + 3)) & 0xC0) != 0x80) {
                unicode_len = UNICODE_ERROR_INVALID_ENCODING;
            } else {
                unicode_len = 4;
                count+=7;
                if (count <= len) {
                    /* compute character number */
                    d = ((c & 0x07) << 18)
                        | ((*(utf + 1) & 0x3F) << 12)
                        | ((*(utf + 2) & 0x3F) << 6)
                        | (*(utf + 3) & 0x3F);
                    *data++ = '%';
                    *data++ = 'u';
                    snprintf(reinterpret_cast<char *>(unicode),
                             sizeof(reinterpret_cast<char *>(unicode)),
                             "%x", d);
                    length = strlen(reinterpret_cast<char *>(unicode));

                    switch (length)  {
                        case 1:
                            *data++ = '0';
                            *data++ = '0';
                            *data++ = '0';
                            break;
                        case 2:
                            *data++ = '0';
                            *data++ = '0';
                            break;
                        case 3:
                            *data++ = '0';
                            break;
                        case 4:
                        case 5:
                            break;
                    }

                    for (j = 0; j < length; j++) {
                        *data++ = unicode[j];
                    }

                    *changed = 1;
                }
            }
        } else {
            /* any other first byte is invalid (RFC 3629) */
            count++;
            if (count <= len)
                *data++ = c;
        }

        /* invalid UTF-8 character number range (RFC 3629) */
        if ((d >= 0xD800) && (d <= 0xDFFF)) {
            count++;
            if (count <= len)
                *data++ = c;
        }

        /* check for overlong */
        if ((unicode_len == 4) && (d < 0x010000)) {
            /* four byte could be represented with less bytes */
            count++;
            if (count <= len)
                *data++ = c;
        } else if ((unicode_len == 3) && (d < 0x0800)) {
            /* three byte could be represented with less bytes */
            count++;
            if (count <= len)
                *data++ = c;
        } else if ((unicode_len == 2) && (d < 0x80)) {
            /* two byte could be represented with less bytes */
            count++;
            if (count <= len)
                *data++ = c;
        }

        if (unicode_len > 0) {
            i += unicode_len;
        } else {
            i++;
        }
    }

    *data ='\0';

    return data_orig;
}


}  // namespace transformations
}  // namespace actions
}  // namespace modsecurity
