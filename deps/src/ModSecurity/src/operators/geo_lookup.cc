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

#include "src/operators/geo_lookup.h"

#if WITH_MAXMIND
#include <maxminddb.h>
#endif

#if WITH_GEOIP
#include <GeoIPCity.h>
#endif

#include <string>
#include <functional>

#include "src/operators/operator.h"
#include "src/utils/geo_lookup.h"


namespace modsecurity {
namespace operators {

bool GeoLookup::debug(Transaction *transaction, int x, std::string a) {
    ms_dbg_a(transaction, x, a);
    return true;
}


bool GeoLookup::evaluate(Transaction *trans, const std::string &exp) {
    using std::placeholders::_1;
    using std::placeholders::_2;
    bool ret = true;

    if (trans) {
        ret = Utils::GeoLookup::getInstance().lookup(exp, trans,
            std::bind(&GeoLookup::debug, this, trans, _1, _2));
    } else {
        ret = Utils::GeoLookup::getInstance().lookup(exp, NULL,
            nullptr);
    }

    return ret;
}


}  // namespace operators
}  // namespace modsecurity
