/*
 * ModSecurity, http://www.modsecurity.org/
 * Copyright (c) 2025 OWASP ModSecurity project
 *
 * You may not use this file except in compliance with
 * the License.  You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * If any of the files related to licensing are missing or if you have any
 * other questions related to licensing please contact OWASP.
 * directly using the email address modsecurity@owasp.org.
 *
 */

#include "src/actions/ctl/parse_xml_into_args.h"

#include <iostream>
#include <string>

#include "modsecurity/rules_set_properties.h"
#include "modsecurity/rules_set.h"
#include "modsecurity/transaction.h"

namespace modsecurity {
namespace actions {
namespace ctl {


bool ParseXmlIntoArgs::init(std::string *error) {
    std::string what(m_parser_payload, 17, m_parser_payload.size() - 17);

    if (what == "on") {
        m_secXMLParseXmlIntoArgs = RulesSetProperties::TrueConfigXMLParseXmlIntoArgs;
    } else if (what == "off") {
        m_secXMLParseXmlIntoArgs = RulesSetProperties::FalseConfigXMLParseXmlIntoArgs;
    } else if (what == "onlyargs") {
        m_secXMLParseXmlIntoArgs = RulesSetProperties::OnlyArgsConfigXMLParseXmlIntoArgs;
    } else {
        error->assign("Internal error. Expected: On, Off or OnlyArgs; " \
            "got: " + m_parser_payload);
        return false;
    }

    return true;
}

bool ParseXmlIntoArgs::evaluate(RuleWithActions *rule, Transaction *transaction) {
    std::stringstream a;
    a << "Setting SecParseXmlIntoArgs to ";
    a << modsecurity::RulesSetProperties::configXMLParseXmlIntoArgsString(m_secXMLParseXmlIntoArgs);
    a << " as requested by a ctl:parseXmlIntoArgs action";

    ms_dbg_a(transaction, 8, a.str());

    transaction->m_secXMLParseXmlIntoArgs = m_secXMLParseXmlIntoArgs;
    return true;
}


}  // namespace ctl
}  // namespace actions
}  // namespace modsecurity
