/*
 * ModSecurity, http://www.modsecurity.org/
 * Copyright (c) 2025 OWASP ModSecurity Project
 *
 * You may not use this file except in compliance with
 * the License.  You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * If any of the files related to licensing are missing or if you have any
 * other questions related to licensing please contact OWASP.
 * directly using the email address modsecurity@owasp.org
 *
 */

#include <string>

#include "modsecurity/rules_set_properties.h"
#include "modsecurity/actions/action.h"
#include "modsecurity/transaction.h"


#ifndef SRC_ACTIONS_CTL_PARSE_XML_INTO_ARGS_H_
#define SRC_ACTIONS_CTL_PARSE_XML_INTO_ARGS_H_

namespace modsecurity {
namespace actions {
namespace ctl {


class ParseXmlIntoArgs : public Action {
 public:
    explicit ParseXmlIntoArgs(const std::string &action) 
        : Action(action),
        m_secXMLParseXmlIntoArgs(RulesSetProperties::PropertyNotSetConfigXMLParseXmlIntoArgs) { }

    bool init(std::string *error) override;
    bool evaluate(RuleWithActions *rule, Transaction *transaction) override;

    RulesSetProperties::ConfigXMLParseXmlIntoArgs m_secXMLParseXmlIntoArgs;
};


}  // namespace ctl
}  // namespace actions
}  // namespace modsecurity

#endif  // SRC_ACTIONS_CTL_PARSE_XML_INTO_ARGS_H_
