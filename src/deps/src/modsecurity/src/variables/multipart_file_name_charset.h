/*
 * ModSecurity, http://www.modsecurity.org/
 * Copyright (c) 2026 OWASP Foundation.  All Rights Reserved.
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

#include <iostream>
#include <string>
#include <vector>
#include <list>
#include <utility>

#ifndef SRC_VARIABLES_MULTIPART_FILE_NAME_CHARSET_H_
#define SRC_VARIABLES_MULTIPART_FILE_NAME_CHARSET_H_

#include "src/variables/variable.h"

namespace modsecurity {

class Transaction;
namespace variables {


DEFINE_VARIABLE_DICT(MultiPartFileNameCharset, MULTIPART_FILENAME_CHARSET,
    m_variableMultipartFileNameCharset)


}  // namespace variables
}  // namespace modsecurity

#endif  // SRC_VARIABLES_MULTIPART_FILE_NAME_CHARSET_H_
