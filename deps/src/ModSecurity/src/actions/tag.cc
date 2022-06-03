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

#include "src/actions/tag.h"

#include <iostream>
#include <string>
#include <memory>

#include "modsecurity/actions/action.h"
#include "modsecurity/transaction.h"
#include "modsecurity/rule.h"
#include "modsecurity/rule_message.h"

/**
 * Description: Assigns a tag (category) to a rule or a chain.
 *
 * Action Group: Meta-data
 *
 * Example:
 *
 * SecRule REQUEST_FILENAME|ARGS_NAMES|ARGS|XML:/* "\bgetparentfolder\b" \
 *         "phase:2,rev:'2.1.3',capture,t:none,t:htmlEntityDecode,t:compressWhiteSpace,t:lowercase,ctl:auditLogParts=+E,block,msg:'Cross-site Scripting (XSS) Attack',id:'958016',tag:'WEB_ATTACK/XSS',tag:'WASCTC/WASC-8',tag:'WASCTC/WASC-22',tag:'OWASP_TOP_10/A2',tag:'OWASP_AppSensor/IE1',tag:'PCI/6.5.1',logdata:'% \
 *         {TX.0}',severity:'2',setvar:'tx.msg=%{rule.msg}',setvar:tx.xss_score=+%{tx.critical_anomaly_score},setvar:tx.anomaly_score=+%{tx.critical_anomaly_score},setvar:tx.%{rule.id}-WEB_ATTACK/XSS-%{matched_var_name}=%{tx.0}"
 *
 *
 * The tag information appears along with other rule metadata. The
 * purpose of the tagging mechanism to allow easy automated categorization
 * of events. Multiple tags can be specified on the same rule. Use forward
 * slashes to create a hierarchy of categories (as in the example). Since
 * ModSecurity 2.6.0 tag supports macro expansion.
 *
 *
 */


namespace modsecurity {
namespace actions {


std::string Tag::getName(Transaction *transaction) {
    std::string tag(m_string->evaluate(transaction));
    return tag;
}


bool Tag::evaluate(Rule *rule, Transaction *transaction,
    std::shared_ptr<RuleMessage> rm) {
    std::string tag = getName(transaction);
    ms_dbg_a(transaction, 9, "Rule tag: " + tag);

    rm->m_tags.push_back(tag);

    return true;
}


}  // namespace actions
}  // namespace modsecurity
