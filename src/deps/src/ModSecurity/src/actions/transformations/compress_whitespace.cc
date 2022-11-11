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

#include "src/actions/transformations/compress_whitespace.h"

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

CompressWhitespace::CompressWhitespace(std::string action)
    : Transformation(action) {
    this->action_kind = 1;
}

std::string CompressWhitespace::evaluate(std::string value,
    Transaction *transaction) {

    std::string a;
    int inWhiteSpace = 0;
    int i = 0;

    while (i < value.size()) {
        if (isspace(value[i])) {
            if (inWhiteSpace) {
                i++;
                continue;
            } else {
                inWhiteSpace = 1;
                a.append(" ", 1);
            }
        } else {
            inWhiteSpace = 0;
            a.append(&value.at(i), 1);
        }
        i++;
    }

    return a;
}

}  // namespace transformations
}  // namespace actions
}  // namespace modsecurity
