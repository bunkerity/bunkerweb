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

#include "src/variables/remote_user.h"

#include <time.h>
#include <stdio.h>
#include <string.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <fcntl.h>

#include <iostream>
#include <string>
#include <vector>
#include <list>
#include <utility>
#include <memory>

#include "modsecurity/transaction.h"
#include "src/utils/base64.h"

namespace modsecurity {
namespace variables {


void RemoteUser::evaluate(Transaction *transaction,
    Rule *rule,
    std::vector<const VariableValue *> *l) {
    size_t pos;
    std::string base64;
    VariableValue *var;
    std::string header;

    std::vector<const VariableValue *> *l2 = \
	new std::vector<const VariableValue *>();
    transaction->m_variableRequestHeaders.resolve("authorization", l2);

    if (l2->size() < 1) {
        goto clear;
    }

    header = std::string(l2->at(0)->getValue());

    if (header.compare(0, 6, "Basic ") == 0) {
        base64 = std::string(header, 6, header.length());
    }

    base64 = Utils::Base64::decode(base64);

    pos = base64.find(":");
    if (pos == std::string::npos) {
        goto clear;
    }
    transaction->m_variableRemoteUser.assign(std::string(base64, 0, pos));

    var = new VariableValue(&l2->at(0)->getKeyWithCollection(),
        &transaction->m_variableRemoteUser);

    for (auto &i : l2->at(0)->getOrigin()) {
        std::unique_ptr<VariableOrigin> origin(new VariableOrigin());
        origin->m_offset = i->m_offset;
        origin->m_length = i->m_length;
        var->addOrigin(std::move(origin));
    }
    l->push_back(var);

clear:
    for (auto &a : *l2) {
        delete a;
    }
    l2->clear();
    delete l2;
}


}  // namespace variables
}  // namespace modsecurity
