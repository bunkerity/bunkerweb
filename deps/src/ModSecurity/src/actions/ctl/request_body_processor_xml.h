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
#include "modsecurity/transaction.h"

#ifndef SRC_ACTIONS_CTL_REQUEST_BODY_PROCESSOR_XML_H_
#define SRC_ACTIONS_CTL_REQUEST_BODY_PROCESSOR_XML_H_

namespace modsecurity {
namespace actions {
namespace ctl {


class RequestBodyProcessorXML : public Action {
 public:
    explicit RequestBodyProcessorXML(std::string action)
        : Action(action, RunTimeOnlyIfMatchKind) { }

    bool evaluate(Rule *rule, Transaction *transaction) override;
};


}  // namespace ctl
}  // namespace actions
}  // namespace modsecurity

#endif  // SRC_ACTIONS_CTL_REQUEST_BODY_PROCESSOR_XML_H_
