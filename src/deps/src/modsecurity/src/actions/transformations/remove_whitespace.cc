/*
 * ModSecurity, http://www.modsecurity.org/
 * Copyright (c) 2015 - 2023 Trustwave Holdings, Inc. (http://www.trustwave.com/)
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

#include <string>

#include "modsecurity/transaction.h"
#include "src/actions/transformations/transformation.h"


namespace modsecurity {
namespace actions {
namespace transformations {

RemoveWhitespace::RemoveWhitespace(const std::string &action) 
    : Transformation(action) {
    this->action_kind = 1;
}

std::string RemoveWhitespace::evaluate(const std::string &val,
    Transaction *transaction) {
    std::string transformed_value;
    transformed_value.reserve(val.size());

    size_t i = 0;
    const char nonBreakingSpaces = 0xa0;
    const char nonBreakingSpaces2 = 0xc2;

    // loop through all the chars
    while (i < val.size()) {
        // remove whitespaces and non breaking spaces (NBSP)
        if (std::isspace(static_cast<unsigned char>(val[i]))
            || (val[i] == nonBreakingSpaces)
            || val[i] == nonBreakingSpaces2) {
            // don't copy; continue on to next char in original val
        } else {
            transformed_value += val.at(i);
        }
        i++;
    }

    return transformed_value;
}

}  // namespace transformations
}  // namespace actions
}  // namespace modsecurity

