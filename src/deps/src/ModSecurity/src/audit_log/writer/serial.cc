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

#include "src/audit_log/writer/serial.h"

#include "modsecurity/audit_log.h"

namespace modsecurity {
namespace audit_log {
namespace writer {
// static std::mutex serialLoggingMutex;


Serial::~Serial() {
    utils::SharedFiles::getInstance().close(m_audit->m_path1);
}


bool Serial::init(std::string *error) {
    return utils::SharedFiles::getInstance().open(m_audit->m_path1, error);
}


bool Serial::write(Transaction *transaction, int parts, std::string *error) {
    std::string msg;

    if (transaction->m_rules->m_auditLog->m_format ==
            audit_log::AuditLog::JSONAuditLogFormat) {
        msg = transaction->toJSON(parts);
    } else {
        std::string boundary;
        generateBoundary(&boundary);
        msg = transaction->toOldAuditLogFormat(parts, "-" + boundary + "--");
    }

    return utils::SharedFiles::getInstance().write(m_audit->m_path1, msg,
        error);
}

}  // namespace writer
}  // namespace audit_log
}  // namespace modsecurity
