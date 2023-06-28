/*
 * ModSecurity, http://www.modsecurity.org/
 * Copyright (c) 2015 - 2021 Trustwave Holdings, Inc. (http://www.trustwave.com/)
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
#include <stack>
#include <vector>
#include <string>
#include <list>
#include <memory>
#include <utility>
#endif

#ifndef HEADERS_MODSECURITY_RULE_H_
#define HEADERS_MODSECURITY_RULE_H_

#include "modsecurity/transaction.h"
#include "modsecurity/modsecurity.h"
#include "modsecurity/variable_value.h"

#ifdef __cplusplus

namespace modsecurity {
namespace variables {
class Variable;
class Variables;
}
namespace actions {
class Action;
class Severity;
class LogData;
class Msg;
class Rev;
class SetVar;
class Tag;
namespace transformations {
class Transformation;
}
}
namespace operators {
class Operator;
}

using TransformationResult = std::pair<std::shared_ptr<std::string>,
    std::shared_ptr<std::string>>;
using TransformationResults = std::list<TransformationResult>;

using Transformation = actions::transformations::Transformation;
using Transformations = std::vector<Transformation *>;

using Actions = std::vector<actions::Action *>;

using Tags = std::vector<actions::Tag *>;
using SetVars = std::vector<actions::SetVar *>;
using MatchActions = std::vector<actions::Action *>;

class Rule {
 public:
    Rule(std::unique_ptr<std::string> fileName, int lineNumber)
        : m_fileName(std::make_shared<std::string>(*fileName)),
        m_lineNumber(lineNumber),
        m_phase(modsecurity::Phases::RequestHeadersPhase) {
        }

    Rule(const Rule &other) :
        m_fileName(other.m_fileName),
        m_lineNumber(other.m_lineNumber),
        m_phase(other.m_phase)
    { }

    Rule &operator=(const Rule& other) {
        m_fileName = other.m_fileName;
        m_lineNumber = other.m_lineNumber;
        m_phase = other.m_phase;
        return *this;
    }

    virtual ~Rule() {}

    virtual bool evaluate(Transaction *transaction) = 0;

    virtual bool evaluate(Transaction *transaction,
        std::shared_ptr<RuleMessage> rm) = 0;

    std::shared_ptr<std::string> getFileName() const {
        return m_fileName;
    }

    int getLineNumber() const {
        return m_lineNumber;
    }

    int getPhase() const { return m_phase; }
    void setPhase(int phase) { m_phase = phase; }

    virtual std::string getReference() {
        if (m_fileName) {
            return *m_fileName + ":" + std::to_string(m_lineNumber);
        }
        return "<<no file>>:" + std::to_string(m_lineNumber);
    }


    virtual bool isMarker() { return false; }

 private:
    std::shared_ptr<std::string> m_fileName;
    int m_lineNumber;
    // FIXME: phase may not be neede to SecMarker.
    int m_phase;
};


}  // namespace modsecurity
#endif


#endif  // HEADERS_MODSECURITY_RULE_H_
