/*
 * ModSecurity, http://www.modsecurity.org/
 * Copyright (c) 2023 Trustwave Holdings, Inc. (http://www.trustwave.com/)
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

#include "src/actions/expire_var.h"

#include <string>

#include "modsecurity/rules_set.h"
#include "modsecurity/transaction.h"
#include "modsecurity/rule.h"
#include "src/utils/string.h"
#include "src/variables/global.h"
#include "src/variables/ip.h"
#include "src/variables/resource.h"
#include "src/variables/session.h"
#include "src/variables/user.h"
#include "src/variables/variable.h"

namespace modsecurity {
namespace actions {


bool ExpireVar::init(std::string *error) {
    return true;
}


bool ExpireVar::evaluate(RuleWithActions *rule, Transaction *t) {

    std::string expireExpressionExpanded(m_string->evaluate(t));

    std::string fully_qualified_var;
    int expirySeconds = 0;
    size_t posEquals = expireExpressionExpanded.find("=");
    if (posEquals == std::string::npos) {
        fully_qualified_var = expireExpressionExpanded;
    } else {
        fully_qualified_var = expireExpressionExpanded.substr(0, posEquals);
	std::string expiry = expireExpressionExpanded.substr(posEquals+1);
	if (expiry.find_first_not_of("0123456789") == std::string::npos) {
            expirySeconds = atoi(expiry.c_str());
	} else {
            ms_dbg_a(t, 5, "Non-numeric expiry seconds found in expirevar expression.");
            return true;
	}
    }

    size_t posDot = fully_qualified_var.find(".");
    if (posDot == std::string::npos) {
        ms_dbg_a(t, 5, "No collection found in expirevar expression.");
	return true;
    }

    std::string collection = fully_qualified_var.substr(0, posDot);
    std::string variable_name = fully_qualified_var.substr(posDot+1);
    std::unique_ptr<RunTimeString> runTimeString(new RunTimeString());
    runTimeString->appendText(fully_qualified_var);

    if (collection == "ip") {
        std::unique_ptr<modsecurity::variables::Ip_DynamicElement> ip_dynamicElement(new modsecurity::variables::Ip_DynamicElement(std::move(runTimeString)));
        ip_dynamicElement->setExpiry(t, variable_name, expirySeconds);
    } else if (collection == "global") {
        std::unique_ptr<modsecurity::variables::Global_DynamicElement> global_dynamicElement(new modsecurity::variables::Global_DynamicElement(std::move(runTimeString)));
        global_dynamicElement->setExpiry(t, variable_name, expirySeconds);
    } else if (collection == "resource") {
        std::unique_ptr<modsecurity::variables::Resource_DynamicElement> resource_dynamicElement(new modsecurity::variables::Resource_DynamicElement(std::move(runTimeString)));
        resource_dynamicElement->setExpiry(t, variable_name, expirySeconds);
    } else if (collection == "session") {
        std::unique_ptr<modsecurity::variables::Session_DynamicElement> session_dynamicElement(new modsecurity::variables::Session_DynamicElement(std::move(runTimeString)));
        session_dynamicElement->setExpiry(t, variable_name, expirySeconds);
    } else if (collection == "user") {
        std::unique_ptr<modsecurity::variables::User_DynamicElement> user_dynamicElement(new modsecurity::variables::User_DynamicElement(std::move(runTimeString)));
        user_dynamicElement->setExpiry(t, variable_name, expirySeconds);
    } else {
        ms_dbg_a(t, 5, "Invalid collection found in expirevar expression: collection must be `ip', `global', `resource', `user' or `session'");
    }
    ms_dbg_a(t, 9, "Setting variable `" + variable_name + "' to expire in " + std::to_string(expirySeconds) + " seconds.");

    return true;
}

}  // namespace actions
}  // namespace modsecurity
