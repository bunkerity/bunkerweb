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
#include <ctime>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <list>
#include <map>
#include <sstream>
#include <string>
#include <unordered_map>
#include <utility>
#include <vector>
#include <memory>
#endif

#include "modsecurity/variable_value.h"

#ifndef HEADERS_MODSECURITY_ANCHORED_VARIABLE_H_
#define HEADERS_MODSECURITY_ANCHORED_VARIABLE_H_

#ifdef __cplusplus


namespace modsecurity {
class Transaction;


class AnchoredVariable {
 public:
    AnchoredVariable(Transaction* t, std::string name);
    ~AnchoredVariable();

    void unset();
    void set(const std::string &a, size_t offset);
    void set(const std::string &a, size_t offset, size_t offsetLen);
    void append(const std::string &a, size_t offset,
        bool spaceSeparator = false);
    void append(const std::string &a, size_t offset,
        bool spaceSeparator, int size);

    void evaluate(std::vector<const VariableValue *> *l);
    std::string *  evaluate();
    std::unique_ptr<std::string> resolveFirst();

    Transaction *m_transaction;
    int m_offset;
    std::string m_name;
    std::string m_value;

 private:
    VariableValue *m_var;
};

}  // namespace modsecurity

#endif


#endif  // HEADERS_MODSECURITY_ANCHORED_VARIABLE_H_

