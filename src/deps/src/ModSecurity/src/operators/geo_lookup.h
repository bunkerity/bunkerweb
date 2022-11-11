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

#ifndef SRC_OPERATORS_GEO_LOOKUP_H_
#define SRC_OPERATORS_GEO_LOOKUP_H_

#include <string>

#include "src/operators/operator.h"


namespace modsecurity {
namespace operators {

class GeoLookup : public Operator {
 public:
    /** @ingroup ModSecurity_Operator */
    GeoLookup()
        : Operator("GeoLookup") { }
    bool evaluate(Transaction *transaction, const std::string &exp) override;

 protected:
    bool debug(Transaction *transaction, int x, std::string a);
};

}  // namespace operators
}  // namespace modsecurity


#endif  // SRC_OPERATORS_GEO_LOOKUP_H_
