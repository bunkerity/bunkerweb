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

#include "src/actions/transformations/base64_decode_ext.h"

#include <iostream>
#include <string>
#include <algorithm>
#include <functional>
#include <cctype>
#include <locale>

#include "modsecurity/transaction.h"
#include "src/actions/transformations/transformation.h"
#include "src/utils/base64.h"


namespace modsecurity {
namespace actions {
namespace transformations {


std::string Base64DecodeExt::evaluate(std::string value,
    Transaction *transaction) {
    std::string ret = Utils::Base64::decode_forgiven(value);

    return ret;
}


}  // namespace transformations
}  // namespace actions
}  // namespace modsecurity
