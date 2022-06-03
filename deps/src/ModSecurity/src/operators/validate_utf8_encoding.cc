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

#include "src/operators/validate_utf8_encoding.h"

#include <string>

#include "src/operators/operator.h"

namespace modsecurity {
namespace operators {

int ValidateUtf8Encoding::detect_utf8_character(
    const unsigned char *p_read, unsigned int length) {
    int unicode_len = 0;
    unsigned int d = 0;
    unsigned char c;

    if (p_read == NULL) {
        return UNICODE_ERROR_DECODING_ERROR;
    }
    c = *p_read;

    /* If first byte begins with binary 0 it is single byte encoding */
    if ((c & 0x80) == 0) {
        /* single byte unicode (7 bit ASCII equivilent) has no validation */
        return 1;
    } else if ((c & 0xE0) == 0xC0) {
        /* If first byte begins with binary 110 it is two byte encoding*/
        /* check we have at least two bytes */
        if (length < 2) {
            unicode_len = UNICODE_ERROR_CHARACTERS_MISSING;
        } else if (((*(p_read + 1)) & 0xC0) != 0x80) {
            /* check second byte starts with binary 10 */
            unicode_len = UNICODE_ERROR_INVALID_ENCODING;
        } else {
            unicode_len = 2;
            /* compute character number */
            d = ((c & 0x1F) << 6) | (*(p_read + 1) & 0x3F);
        }
    } else if ((c & 0xF0) == 0xE0) {
        /* If first byte begins with binary 1110 it is three byte encoding */
        /* check we have at least three bytes */
        if (length < 3) {
            unicode_len = UNICODE_ERROR_CHARACTERS_MISSING;
        } else if (((*(p_read + 1)) & 0xC0) != 0x80) {
            /* check second byte starts with binary 10 */
            unicode_len = UNICODE_ERROR_INVALID_ENCODING;
        } else if (((*(p_read + 2)) & 0xC0) != 0x80) {
            /* check third byte starts with binary 10 */
            unicode_len = UNICODE_ERROR_INVALID_ENCODING;
        } else {
            unicode_len = 3;
            /* compute character number */
            d = ((c & 0x0F) << 12) | ((*(p_read + 1) & 0x3F) << 6)
                | (*(p_read + 2) & 0x3F);
        }
    } else if ((c & 0xF8) == 0xF0) {
        /* If first byte begins with binary 11110 it is four byte encoding */
        /* restrict characters to UTF-8 range (U+0000 - U+10FFFF)*/
        if (c >= 0xF5) {
            return UNICODE_ERROR_RESTRICTED_CHARACTER;
        }
        /* check we have at least four bytes */
        if (length < 4) {
            unicode_len = UNICODE_ERROR_CHARACTERS_MISSING;
        } else if (((*(p_read + 1)) & 0xC0) != 0x80) {
            unicode_len = UNICODE_ERROR_INVALID_ENCODING;
        } else if (((*(p_read + 2)) & 0xC0) != 0x80) {
            unicode_len = UNICODE_ERROR_INVALID_ENCODING;
        } else if (((*(p_read + 3)) & 0xC0) != 0x80) {
            unicode_len = UNICODE_ERROR_INVALID_ENCODING;
        } else {
            unicode_len = 4;
            /* compute character number */
            d = ((c & 0x07) << 18) | ((*(p_read + 1) & 0x3F) << 12)
                | ((*(p_read + 2) & 0x3F) << 6) | (*(p_read + 3) & 0x3F);
        }
    } else {
        /* any other first byte is invalid (RFC 3629) */
        return UNICODE_ERROR_INVALID_ENCODING;
    }

    /* invalid UTF-8 character number range (RFC 3629) */
    if ((d >= 0xD800) && (d <= 0xDFFF)) {
        return UNICODE_ERROR_RESTRICTED_CHARACTER;
    }

    /* check for overlong */
    if ((unicode_len == 4) && (d < 0x010000)) {
        /* four byte could be represented with less bytes */
        return UNICODE_ERROR_OVERLONG_CHARACTER;
    } else if ((unicode_len == 3) && (d < 0x0800)) {
        /* three byte could be represented with less bytes */
        return UNICODE_ERROR_OVERLONG_CHARACTER;
    } else if ((unicode_len == 2) && (d < 0x80)) {
        /* two byte could be represented with less bytes */
        return UNICODE_ERROR_OVERLONG_CHARACTER;
    }

    return unicode_len;
}

bool ValidateUtf8Encoding::evaluate(Transaction *transaction, Rule *rule,
    const std::string &str, std::shared_ptr<RuleMessage> ruleMessage) {
    unsigned int i, bytes_left;

    const char *str_c = str.c_str();
    bytes_left = str.size();

    for (i = 0; i < str.size();) {
        int rc = detect_utf8_character((unsigned char *)&str_c[i], bytes_left);

        switch (rc) {
            case UNICODE_ERROR_CHARACTERS_MISSING :
                if (transaction) {
                    ms_dbg_a(transaction, 8, "Invalid UTF-8 encoding: "
                        "not enough bytes in character "
                        "at " + str + ". [offset \"" +
                        std::to_string(i) + "\"]");
                }
                return true;
                break;
            case UNICODE_ERROR_INVALID_ENCODING :
                if (transaction) {
                    ms_dbg_a(transaction, 8, "Invalid UTF-8 encoding: "
                        "invalid byte value in character "
                        "at " + str + ". [offset \"" +
                        std::to_string(i) + "\"]");
                    logOffset(ruleMessage, i, str.size());
                }
                return true;
                break;
            case UNICODE_ERROR_OVERLONG_CHARACTER :
                if (transaction) {
                    ms_dbg_a(transaction, 8, "Invalid UTF-8 encoding: "
                        "overlong character detected "
                        "at " + str + ". [offset \"" +
                        std::to_string(i) + "\"]");
                    logOffset(ruleMessage, i, str.size());
                }
                return true;
                break;
            case UNICODE_ERROR_RESTRICTED_CHARACTER :
                if (transaction) {
                    ms_dbg_a(transaction, 8, "Invalid UTF-8 encoding: "
                        "use of restricted character "
                        "at " + str + ". [offset \"" +
                        std::to_string(i) + "\"]");
                    logOffset(ruleMessage, i, str.size());
                }
                return true;
                break;
            case UNICODE_ERROR_DECODING_ERROR :
                if (transaction) {
                    ms_dbg_a(transaction, 8, "Error validating UTF-8 decoding "
                        "at " + str + ". [offset \"" +
                        std::to_string(i) + "\"]");
                    logOffset(ruleMessage, i, str.size());
                }
                return true;
                break;
        }

        if (rc <= 0) {
            if (transaction) {
                ms_dbg_a(transaction, 8, "Internal error during UTF-8 validation "
                    "at " + str + ". [offset \"" +
                    std::to_string(i) + "\"]");
                logOffset(ruleMessage, i, str.size());
            }
            return true;
        }

        i += rc;
        bytes_left -= rc;
    }

    return false;
}


}  // namespace operators
}  // namespace modsecurity
