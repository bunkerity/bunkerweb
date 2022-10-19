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

#include "src/actions/transformations/remove_whitespace.h"

#include <iostream>
#include <string>
#include <algorithm>
#include <functional>
#include <cctype>
#include <locale>

#include "modsecurity/transaction.h"
#include "src/actions/transformations/transformation.h"

#define NBSP 160    // non breaking space char

namespace modsecurity {
namespace actions {
namespace transformations {

RemoveWhitespace::RemoveWhitespace(std::string action)
    : Transformation(action) {
    this->action_kind = 1;
}

std::string RemoveWhitespace::evaluate(std::string value,
    Transaction *transaction) {

    int64_t i = 0;

    // loop through all the chars
    while (i < value.size()) {
        // remove whitespaces and non breaking spaces (NBSP)
        if (isspace(value[i]) || (value[i] == NBSP)) {
            value.erase(i, 1);
        } else {
          /* if the space is not a whitespace char, increment counter
           counter should not be incremented if a character is erased because
           the index erased will be replaced by the following character */
          i++;
        }
    }

    return value;
}

}  // namespace transformations
}  // namespace actions
}  // namespace modsecurity

