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

#include "src/variables/rule.h"


namespace modsecurity {
namespace variables {


const std::string Rule_DictElement::m_rule("RULE");
const std::string Rule_DictElement::m_rule_id("id");
const std::string Rule_DictElement::m_rule_rev("rev");
const std::string Rule_DictElement::m_rule_severity("severity");
const std::string Rule_DictElement::m_rule_logdata("logdata");
const std::string Rule_DictElement::m_rule_msg("msg");


}  // namespace variables
}  // namespace modsecurity
