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

#ifndef SRC_OPERATORS_INSPECT_FILE_H_
#define SRC_OPERATORS_INSPECT_FILE_H_

#include <string>
#include <memory>
#include <utility>

#include "src/operators/operator.h"
#include "src/engine/lua.h"


namespace modsecurity {
namespace operators {

class InspectFile : public Operator {
 public:
    /** @ingroup ModSecurity_Operator */
    explicit InspectFile(std::unique_ptr<RunTimeString> param)
        : Operator("InspectFile", std::move(param)),
        m_file(""),
        m_isScript(false) { }

    bool init(const std::string &param, std::string *error) override;
    bool evaluate(Transaction *transaction, const std::string &str) override;
 private:
    std::string m_file;
    bool m_isScript;
    engine::Lua m_lua;
};

}  // namespace operators
}  // namespace modsecurity


#endif  // SRC_OPERATORS_INSPECT_FILE_H_
