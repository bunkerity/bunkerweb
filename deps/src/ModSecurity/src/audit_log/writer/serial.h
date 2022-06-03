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

#ifdef __cplusplus
#include <iostream>
#include <fstream>
#include <string>
#endif

#ifndef SRC_AUDIT_LOG_WRITER_SERIAL_H_
#define SRC_AUDIT_LOG_WRITER_SERIAL_H_

#include "src/audit_log/writer/writer.h"
#include "src/utils/shared_files.h"
#include "modsecurity/transaction.h"
#include "modsecurity/audit_log.h"
#include "modsecurity/rules.h"

#ifdef __cplusplus

namespace modsecurity {
namespace audit_log {
namespace writer {


/** @ingroup ModSecurity_CPP_API */
class Serial : public Writer {
 public:
    explicit Serial(audit_log::AuditLog *audit)
        : audit_log::writer::Writer(audit) { }

    ~Serial() override;


    bool init(std::string *error) override;
    bool write(Transaction *transaction, int parts,
        std::string *error) override;
};

}  // namespace writer
}  // namespace audit_log
}  // namespace modsecurity
#endif

#endif  // SRC_AUDIT_LOG_WRITER_SERIAL_H_
