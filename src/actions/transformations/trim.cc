/*
 * ModSecurity, http://www.modsecurity.org/
 * Copyright (c) 2015 - 2021 Trustwave Holdings, Inc. (http://www.trustwave.com/)
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

#include "src/actions/transformations/trim.h"

#include <iostream>
#include <string>
#include <algorithm>
#include <functional>
#include <cctype>
#include <locale>

#include "modsecurity/transaction.h"
#include "src/actions/transformations/transformation.h"
#include "modsecurity/actions/action.h"

namespace modsecurity {
namespace actions {
namespace transformations {


std::string *Trim::ltrim(std::string *s) {
    s->erase(
        s->begin(),
        std::find_if(s->begin(), s->end(), [](unsigned char c) {
            return !std::isspace(c);
        })
    );

    return s;
}


std::string *Trim::rtrim(std::string *s) {
    s->erase(
        std::find_if(s->rbegin(), s->rend(), [](unsigned char c) {
            return !std::isspace(c);
        }).base(),
        s->end()
    );

    return s;
}


std::string *Trim::trim(std::string *s) {
    return ltrim(rtrim(s));
}


Trim::Trim(const std::string &action) 
    : Transformation(action) {
    this->action_kind = 1;
}


std::string
Trim::evaluate(const std::string &val,
    Transaction *transaction) {
    std::string value(val);
    return *this->trim(&value);
}


}  // namespace transformations
}  // namespace actions
}  // namespace modsecurity
