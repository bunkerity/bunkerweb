/*
 * ModSecurity, http://www.modsecurity.org/
 * Copyright (c) 2022 Trustwave Holdings, Inc. (http://www.trustwave.com/)
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

#include "src/actions/ctl/audit_engine.h"

#include <string>

#include "modsecurity/rules_set_properties.h"
#include "modsecurity/rules_set.h"
#include "modsecurity/transaction.h"

namespace modsecurity {
namespace actions {
namespace ctl {


bool AuditEngine::init(std::string *error) {

    std::string what(m_parser_payload, 12, m_parser_payload.size() - 12);

    if (what == "on") {
        m_auditEngine = audit_log::AuditLog::AuditLogStatus::OnAuditLogStatus;
    } else if (what == "off") {
        m_auditEngine = audit_log::AuditLog::AuditLogStatus::OffAuditLogStatus;
    } else if (what == "relevantonly") {
        m_auditEngine = audit_log::AuditLog::AuditLogStatus::RelevantOnlyAuditLogStatus;
    } else {
        error->assign("Internal error. Expected: On, Off or RelevantOnly; " \
            "got: " + m_parser_payload);
        return false;
    }

    return true;
}

bool AuditEngine::evaluate(RuleWithActions *rule, Transaction *transaction) {
    std::stringstream a;
    a << "Setting SecAuditEngine to ";
    a << std::to_string(m_auditEngine);
    a << " as requested by a ctl:auditEngine action";

    ms_dbg_a(transaction, 8, a.str());

    transaction->m_ctlAuditEngine = m_auditEngine;
    return true;
}


}  // namespace ctl
}  // namespace actions
}  // namespace modsecurity
