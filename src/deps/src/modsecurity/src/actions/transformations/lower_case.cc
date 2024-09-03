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


#include "lower_case.h"

#include <cctype>


namespace modsecurity::actions::transformations {


bool LowerCase::transform(std::string &value, const Transaction *trans) const {
    return convert(value, [](auto c) {
                    return std::tolower(c); });
}


}  // namespace modsecurity::actions::transformations
