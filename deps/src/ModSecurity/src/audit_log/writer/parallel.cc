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

#include "src/audit_log/writer/parallel.h"

#include <time.h>
#include <stdio.h>
#include <string.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <fcntl.h>
#include <unistd.h>
#include <stdlib.h>

#include <fstream>
#include <mutex>

#include "modsecurity/audit_log.h"
#include "modsecurity/transaction.h"
#include "src/utils/system.h"
#include "src/utils/md5.h"


namespace modsecurity {
namespace audit_log {
namespace writer {


Parallel::~Parallel() {
    utils::SharedFiles::getInstance().close(m_audit->m_path1);
    utils::SharedFiles::getInstance().close(m_audit->m_path2);
}


inline std::string Parallel::logFilePath(time_t *t,
    int part) {
    struct tm timeinfo;
    char tstr[300];
    std::string name("");

    localtime_r(t, &timeinfo);

    if (part & YearMonthDayDirectory) {
        memset(tstr, '\0', 300);
        strftime(tstr, 299, "/%Y%m%d", &timeinfo);
        name = tstr;
    }

    if (part & YearMonthDayAndTimeDirectory) {
        memset(tstr, '\0', 300);
        strftime(tstr, 299, "/%Y%m%d-%H%M", &timeinfo);
        name = name + tstr;
    }

    if (part & YearMonthDayAndTimeFileName) {
        memset(tstr, '\0', 300);
        strftime(tstr, 299, "/%Y%m%d-%H%M%S", &timeinfo);
        name = name + tstr;
    }

    return name;
}


bool Parallel::init(std::string *error) {
    bool ret = true;
    if (!m_audit->m_path1.empty()) {
        ret = utils::SharedFiles::getInstance().open(m_audit->m_path1, error);
        if (!ret) {
            return false;
        }
    }

    if (!m_audit->m_path2.empty()) {
        ret = utils::SharedFiles::getInstance().open(m_audit->m_path2, error);
        if (!ret) {
            return false;
        }
    }

    if (m_audit->m_storage_dir.empty() == false) {
        if (utils::createDir(m_audit->m_storage_dir,
            m_audit->getDirectoryPermission(), error) == false) {
            return false;
        }
    }

    return true;
}


bool Parallel::write(Transaction *transaction, int parts, std::string *error) {
    int fd;
    std::string log;
    std::string fileName = logFilePath(&transaction->m_timeStamp,
        YearMonthDayDirectory | YearMonthDayAndTimeDirectory
        | YearMonthDayAndTimeFileName);
    bool ret;

    if (transaction->m_rules->m_auditLog->m_format ==
            audit_log::AuditLog::JSONAuditLogFormat) {
        log = transaction->toJSON(parts);
    } else {
        std::string boundary;
        generateBoundary(&boundary);
        log = transaction->toOldAuditLogFormat(parts, "-" + boundary + "--");
    }

    std::string logPath = m_audit->m_storage_dir;
    fileName = logPath + fileName + "-" + transaction->m_id;

    if (logPath.empty()) {
        error->assign("Log path is not valid.");
        return false;
    }

    ret = utils::createDir((logPath +
        logFilePath(&transaction->m_timeStamp, YearMonthDayDirectory)).c_str(),
        m_audit->getDirectoryPermission(),
        error);
    if (ret == false) {
        return false;
    }
    ret = utils::createDir((logPath +
        logFilePath(&transaction->m_timeStamp, YearMonthDayDirectory
            | YearMonthDayAndTimeDirectory)).c_str(),
        m_audit->getDirectoryPermission(),
        error);
    if (ret == false) {
        return false;
    }

    fd = open(fileName.c_str(), O_CREAT | O_WRONLY | O_APPEND,
        m_audit->getFilePermission());
    if (fd < 0) {
        error->assign("Not able to open: " + fileName + ". " \
            + strerror(errno));
        return false;
    }
    close(fd);

    std::ofstream myfile;
    std::string a(fileName.c_str());
    myfile.open(a, std::ofstream::out | std::ofstream::app);
    myfile << log;
    myfile.close();

    if (m_audit->m_path1.empty() == false
        && m_audit->m_path2.empty() == false) {
        std::string msg = transaction->toOldAuditLogFormatIndex(fileName,
            log.length(), Utils::Md5::hexdigest(log));
        ret = utils::SharedFiles::getInstance().write(m_audit->m_path2, msg,
            error);
        if (ret == false) {
            return false;
        }
    }
    if (m_audit->m_path1.empty() == false
        && m_audit->m_path2.empty() == true) {
        std::string msg = transaction->toOldAuditLogFormatIndex(fileName,
            log.length(), Utils::Md5::hexdigest(log));
        ret = utils::SharedFiles::getInstance().write(m_audit->m_path1, msg,
            error);
        if (ret == false) {
            return false;
        }
    }
    if (m_audit->m_path1.empty() == true
        && m_audit->m_path2.empty() == false) {
        std::string msg = transaction->toOldAuditLogFormatIndex(fileName,
            log.length(), Utils::Md5::hexdigest(log));
        ret = utils::SharedFiles::getInstance().write(m_audit->m_path2, msg,
            error);
        if (ret == false) {
            return false;
        }
    }

    return true;
}

}  // namespace writer
}  // namespace audit_log
}  // namespace modsecurity
