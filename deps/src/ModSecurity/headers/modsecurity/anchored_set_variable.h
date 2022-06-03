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
#include <algorithm>
#include <memory>
#endif

#include "modsecurity/variable_value.h"

#ifndef HEADERS_MODSECURITY_ANCHORED_SET_VARIABLE_H_
#define HEADERS_MODSECURITY_ANCHORED_SET_VARIABLE_H_

#ifdef __cplusplus

namespace modsecurity {
class Transaction;
namespace Utils {
class Regex;
}
namespace variables {
class KeyExclusions;
}


struct MyEqual {
    bool operator()(const std::string& Left, const std::string& Right) const {
        return Left.size() == Right.size()
             && std::equal(Left.begin(), Left.end(), Right.begin(),
            [](char a, char b) {
            return tolower(a) == tolower(b);
        });
    }
};

struct MyHash{
    size_t operator()(const std::string& Keyval) const {
        // You might need a better hash function than this
        size_t h = 0;
        std::for_each(Keyval.begin(), Keyval.end(), [&](char c) {
            h += tolower(c);
        });
        return h;
    }
};


class AnchoredSetVariable : public std::unordered_multimap<std::string,
	VariableValue *, MyHash, MyEqual> {
 public:
    AnchoredSetVariable(Transaction *t, std::string name);
    ~AnchoredSetVariable();

    void unset();

    void set(const std::string &key, const std::string &value,
        size_t offset);

    void set(const std::string &key, const std::string &value,
        size_t offset, size_t len);

    void setCopy(std::string key, std::string value, size_t offset);

    void resolve(std::vector<const VariableValue *> *l);
    void resolve(std::vector<const VariableValue *> *l,
        variables::KeyExclusions &ke);

    void resolve(const std::string &key,
        std::vector<const VariableValue *> *l);

    void resolveRegularExpression(Utils::Regex *r,
        std::vector<const VariableValue *> *l);

    void resolveRegularExpression(Utils::Regex *r,
        std::vector<const VariableValue *> *l,
        variables::KeyExclusions &ke);

    std::unique_ptr<std::string> resolveFirst(const std::string &key);

    Transaction *m_transaction;
    std::string m_name;
};

}  // namespace modsecurity

#endif


#endif  // HEADERS_MODSECURITY_ANCHORED_SET_VARIABLE_H_

