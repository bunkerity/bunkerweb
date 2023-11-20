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

#include "src/actions/transformations/remove_comments_char.h"

#include <string>

#include "modsecurity/transaction.h"
#include "src/actions/transformations/transformation.h"


namespace modsecurity {
namespace actions {
namespace transformations {

RemoveCommentsChar::RemoveCommentsChar(const std::string &action) 
    : Transformation(action) {
    this->action_kind = 1;
}

std::string RemoveCommentsChar::evaluate(const std::string &val,
    Transaction *transaction) {
    size_t i = 0;
    std::string transformed_value;
    transformed_value.reserve(val.size());

    while (i < val.size()) {
        if (val.at(i) == '/'
            && (i+1 < val.size()) && val.at(i+1) == '*') {
            i += 2;
        } else if (val.at(i) == '*'
            && (i+1 < val.size()) && val.at(i+1) == '/') {
            i += 2;
        } else if (val.at(i) == '<'
            && (i+1 < val.size())
            && val.at(i+1) == '!'
            && (i+2 < val.size())
            && val.at(i+2) == '-'
            && (i+3 < val.size())
            && val.at(i+3) == '-') {
            i += 4;
        } else if (val.at(i) == '-'
            && (i+1 < val.size()) && val.at(i+1) == '-'
            && (i+2 < val.size()) && val.at(i+2) == '>') {
            i += 3;
        } else if (val.at(i) == '-'
            && (i+1 < val.size()) && val.at(i+1) == '-') {
            i += 2;
        } else if (val.at(i) == '#') {
            i += 1;
        } else {
            transformed_value += val.at(i);
            i++;
        }
    }
    return transformed_value;
}

}  // namespace transformations
}  // namespace actions
}  // namespace modsecurity

