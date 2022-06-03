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

#include "modsecurity/actions/action.h"
#include "src/engine/lua.h"

#ifndef SRC_ACTIONS_EXEC_H_
#define SRC_ACTIONS_EXEC_H_

class Transaction;

namespace modsecurity {
class Transaction;
namespace actions {


class Exec : public Action {
 public:
    explicit Exec(std::string action)
        : Action(action),
        m_script("") { }

    ~Exec() { }

    bool evaluate(Rule *rule, Transaction *transaction) override;
    bool init(std::string *error) override;

 private:
    std::string m_script;
    engine::Lua m_lua;
};


}  // namespace actions
}  // namespace modsecurity

#endif  // SRC_ACTIONS_EXEC_H_
