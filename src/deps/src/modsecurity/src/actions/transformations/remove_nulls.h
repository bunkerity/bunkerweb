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

#ifndef SRC_ACTIONS_TRANSFORMATIONS_REMOVE_NULLS_H_
#define SRC_ACTIONS_TRANSFORMATIONS_REMOVE_NULLS_H_

#include "transformation.h"

#include <algorithm>

namespace modsecurity::actions::transformations {

class RemoveNulls : public Transformation {
 public:
    using Transformation::Transformation;

    bool transform(std::string &value, const Transaction *trans) const override;

    template<typename Pred>
    static bool remove_if(std::string &val, Pred pred) {
        const auto old_size = val.size();

        val.erase(
            std::remove_if(
                val.begin(), val.end(), pred),
            val.end());

        return val.size() != old_size;
    }
};

}  // namespace modsecurity::actions::transformations

#endif  // SRC_ACTIONS_TRANSFORMATIONS_REMOVE_NULLS_H_
