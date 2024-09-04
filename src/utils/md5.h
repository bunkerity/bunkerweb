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

#ifndef SRC_UTILS_MD5_H_
#define SRC_UTILS_MD5_H_

#include "src/utils/sha1.h"
#include "mbedtls/md5.h"
#include <string>

namespace modsecurity::Utils {


class Md5 : public DigestImpl<&mbedtls_md5, 16> {
};


}  // namespace modsecurity::Utils

#endif  // SRC_UTILS_MD5_H_