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

#include <iostream>
#include <fstream>
#include <string>
#include <functional>

#if WITH_MAXMIND
#include <maxminddb.h>
#endif
#if WITH_GEOIP
#include <GeoIPCity.h>
#endif

#ifndef SRC_UTILS_GEO_LOOKUP_H_
#define SRC_UTILS_GEO_LOOKUP_H_

#include "modsecurity/transaction.h"

namespace modsecurity {
namespace Utils {

enum GeoLookupVersion {
    NOT_LOADED,
    VERSION_MAXMIND,
    VERSION_GEOIP,
};

class GeoLookup {
 public:
    static GeoLookup& getInstance() {
        static GeoLookup instance;
        return instance;
    }

    bool setDataBase(const std::string& filePath, std::string *err);
    void cleanUp();

    bool lookup(const std::string& target, Transaction *t,
        std::function<bool(int, std::string)> callback);

 private:
    GeoLookup() :
#if WITH_GEOIP
        m_gi(NULL),
#endif
        m_version(NOT_LOADED) { }
    ~GeoLookup();
    GeoLookup(GeoLookup const&);
    void operator=(GeoLookup const&);

    GeoLookupVersion m_version;
#if WITH_MAXMIND
    MMDB_s mmdb;
#endif
#if WITH_GEOIP
    GeoIP *m_gi;
#endif

};


}  // namespace Utils
}  // namespace modsecurity

#endif  // SRC_UTILS_GEO_LOOKUP_H_
