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

#include "src/actions/transformations/remove_comments.h"

#include <iostream>
#include <string>
#include <algorithm>
#include <functional>
#include <cctype>
#include <locale>
#include <cstring>

#include "modsecurity/transaction.h"
#include "src/actions/transformations/transformation.h"


namespace modsecurity {
namespace actions {
namespace transformations {


std::string RemoveComments::evaluate(std::string value,
    Transaction *transaction) {
    std::string ret;
    unsigned char *input;

    input = reinterpret_cast<unsigned char *>
        (malloc(sizeof(char) * value.length()+1));

    if (input == NULL) {
        return "";
    }

    memcpy(input, value.c_str(), value.length()+1);

    uint64_t input_len = value.size();
    uint64_t i, j, incomment;

    i = j = incomment = 0;
    while (i < input_len) {
        if (incomment == 0) {
            if ((input[i] == '/') && (i + 1 < input_len)
                && (input[i + 1] == '*')) {
                incomment = 1;
                i += 2;
            } else if ((input[i] == '<') && (i + 1 < input_len)
                && (input[i + 1] == '!') && (i + 2 < input_len)
                && (input[i+2] == '-') && (i + 3 < input_len)
                && (input[i + 3] == '-') && (incomment == 0)) {
                incomment = 1;
                i += 4;
            } else if ((input[i] == '-') && (i + 1 < input_len)
                && (input[i + 1] == '-') && (incomment == 0)) {
                input[i] = ' ';
                break;
            } else if (input[i] == '#' && (incomment == 0)) {
                input[i] = ' ';
                break;
            } else {
                input[j] = input[i];
                i++;
                j++;
            }
        } else {
            if ((input[i] == '*') && (i + 1 < input_len)
                && (input[i + 1] == '/')) {
                incomment = 0;
                i += 2;
                input[j] = input[i];
                i++;
                j++;
            } else if ((input[i] == '-') && (i + 1 < input_len)
                && (input[i + 1] == '-') && (i + 2 < input_len)
                && (input[i+2] == '>'))   {
                incomment = 0;
                i += 3;
                input[j] = input[i];
                i++;
                j++;
            } else {
                i++;
            }
        }
    }

    if (incomment) {
        input[j++] = ' ';
    }

    ret.assign(reinterpret_cast<char *>(input), j);
    free(input);

    return ret;
}


}  // namespace transformations
}  // namespace actions
}  // namespace modsecurity
