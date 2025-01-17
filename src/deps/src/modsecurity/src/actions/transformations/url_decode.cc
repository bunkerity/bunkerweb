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

#include "url_decode.h"

#include "src/utils/decode.h"


namespace modsecurity::actions::transformations {


bool UrlDecode::transform(std::string &value, const Transaction *trans) const {
    int invalid_count;
    return utils::urldecode_nonstrict_inplace(value, invalid_count);
}


}  // namespace modsecurity::actions::transformations
