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

#include <iostream>
#include <string>
#include <vector>
#include <list>
#include <utility>

#ifndef SRC_VARIABLES_MATCHED_VAR_NAME_H_
#define SRC_VARIABLES_MATCHED_VAR_NAME_H_

#include "src/variables/variable.h"

namespace modsecurity {

class Transaction;
namespace variables {


DEFINE_VARIABLE(MatchedVarName, MATCHED_VAR_NAME, m_variableMatchedVarName)


}  // namespace variables
}  // namespace modsecurity

#endif  // SRC_VARIABLES_MATCHED_VAR_NAME_H_
