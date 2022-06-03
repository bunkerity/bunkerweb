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

#ifndef SRC_AUDIT_LOG_WRITER_WRITER_H_
#define SRC_AUDIT_LOG_WRITER_WRITER_H_


#include <stdio.h>
#include <sys/ipc.h>
#include <sys/shm.h>
#include <sys/types.h>

#include <iostream>
#include <string>
#include <map>
#include <cstring>


#include "modsecurity/transaction.h"
#include "modsecurity/audit_log.h"

#define SERIAL_AUDIT_LOG_BOUNDARY_LENGTH 8

namespace modsecurity {
namespace audit_log {
namespace writer {


/** @ingroup ModSecurity_CPP_API */
class Writer {
 public:
    explicit Writer(AuditLog *audit)
        : m_audit(audit),
        m_refereceCount(1) { }

    virtual ~Writer() { }

    virtual bool init(std::string *error) = 0;
    virtual bool write(Transaction *transaction, int parts,
        std::string *error) = 0;

    void generateBoundary(std::string *boundary);

    void refCountIncrease() {
        m_refereceCount++;
    }


    bool refCountDecreaseAndCheck() {
        m_refereceCount--;
        if (m_refereceCount == 0) {
            delete this;
            return true;
        }
        return false;
    }

 protected:
    AuditLog *m_audit;
    int m_refereceCount;
};


}  // namespace writer
}  // namespace audit_log
}  // namespace modsecurity

#endif  // SRC_AUDIT_LOG_WRITER_WRITER_H_
