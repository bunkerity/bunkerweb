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

#include <string>

#ifndef SRC_AUDIT_LOG_WRITER_PARALLEL_H_
#define SRC_AUDIT_LOG_WRITER_PARALLEL_H_

#include "src/audit_log/writer/writer.h"
#include "modsecurity/transaction.h"
#include "modsecurity/audit_log.h"
#include "src/utils/shared_files.h"
#include "modsecurity/rules.h"

#ifdef __cplusplus

namespace modsecurity {
namespace audit_log {
namespace writer {

/** @ingroup ModSecurity_CPP_API */
class Parallel : public Writer {
 public:
    explicit Parallel(AuditLog *audit)
        : audit_log::writer::Writer(audit) { }

    ~Parallel() override;
    bool init(std::string *error) override;
    bool write(Transaction *transaction, int parts,
        std::string *error) override;


    /**
     *
     * Audit log file is saved into a directory structure. This directory
     * structure is based on the timestamp of the transaction creation, at
     * the exact moment that ModSecurity be aware of a particular
     * request/transaction.
     * The expect fromat is:
     *
     * [...]/YearMonthDay/YearMonthDayAndTime/YearMonthDayAndTime-RequestId
     *
     * Example:
     *
     * /20150710/20150710-1353/20150710-135353-143654723362.584244
     *
     * This enumeration describes the subpaths of this structure.
     *
     */
    enum AuditLogFilePath {
     YearMonthDayDirectory = 2,
     YearMonthDayAndTimeDirectory = 4,
     YearMonthDayAndTimeFileName = 8,
    };

    inline std::string logFilePath(time_t *t, int part);
};

}  // namespace writer
}  // namespace audit_log
}  // namespace modsecurity
#endif

#endif  // SRC_AUDIT_LOG_WRITER_PARALLEL_H_
