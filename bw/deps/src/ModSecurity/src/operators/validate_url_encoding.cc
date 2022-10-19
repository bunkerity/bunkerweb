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

#include "src/operators/validate_url_encoding.h"

#include <string>

#include "src/operators/operator.h"

namespace modsecurity {
namespace operators {


int ValidateUrlEncoding::validate_url_encoding(const char *input,
    uint64_t input_length, size_t *offset) {
    int i;
    *offset = 0;

    if ((input == NULL) || (input_length <= 0)) {
        return -1;
    }

    i = 0;
    while (i < input_length) {
        if (input[i] == '%') {
            if (i + 2 >= input_length) {
                *offset = i;
                /* Not enough bytes. */
                return -3;
            } else {
                /* Here we only decode a %xx combination if it is valid,
                 * leaving it as is otherwise.
                 */
                char c1 = input[i + 1];
                char c2 = input[i + 2];

                if ( (((c1 >= '0') && (c1 <= '9'))
                    || ((c1 >= 'a') && (c1 <= 'f'))
                    || ((c1 >= 'A') && (c1 <= 'F')))
                    && (((c2 >= '0') && (c2 <= '9'))
                    || ((c2 >= 'a') && (c2 <= 'f'))
                    || ((c2 >= 'A') && (c2 <= 'F'))) ) {
                    i += 3;
                } else {
                    /* Non-hexadecimal characters used in encoding. */
                    *offset = i;
                    return -2;
                }
            }
        } else {
            i++;
        }
    }

    return 1;
}


bool ValidateUrlEncoding::evaluate(Transaction *transaction, Rule *rule,
    const std::string &input, std::shared_ptr<RuleMessage> ruleMessage) {
    size_t offset = 0;
    bool res = false;

    if (input.empty() == true) {
        return res;
    }

    int rc = validate_url_encoding(input.c_str(), input.size(), &offset);
    switch (rc) {
        case 1 :
            /* Encoding is valid */
            if (transaction) {
                ms_dbg_a(transaction, 7, "Valid URL Encoding at '" +input + "'");
            }
            res = false;
            break;
        case -2 :
            if (transaction) {
                ms_dbg_a(transaction, 7, "Invalid URL Encoding: Non-hexadecimal "
                    "digits used at '" + input + "'");
                logOffset(ruleMessage, offset, input.size());
            }
            res = true; /* Invalid match. */
            break;
        case -3 :
            if (transaction) {
                ms_dbg_a(transaction, 7, "Invalid URL Encoding: Not enough " \
                "characters at the end of input at '" + input + "'");
                logOffset(ruleMessage, offset, input.size());
            }
            res = true; /* Invalid match. */
            break;
        case -1 :
        default :
            if (transaction) {
                ms_dbg_a(transaction, 7, "Invalid URL Encoding: Internal " \
                    "Error (rc = " + std::to_string(rc) + ") at '" +
                    input + "'");
                logOffset(ruleMessage, offset, input.size());
            }
            res = true;
            break;
    }

    return res;
}


}  // namespace operators
}  // namespace modsecurity
