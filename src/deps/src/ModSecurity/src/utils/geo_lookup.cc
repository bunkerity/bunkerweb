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

#include <sys/socket.h>
#include <sys/types.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <string>

#include <fstream>
#include <iostream>

#include "src/utils/geo_lookup.h"
#if WITH_MAXMIND
#include <maxminddb.h>
#elif WITH_GEOIP
#include <GeoIPCity.h>
#endif

namespace modsecurity {
namespace Utils {


GeoLookup::~GeoLookup() {
    cleanUp();
}


void GeoLookup::cleanUp() {
#ifdef WITH_MAXMIND
    if (m_version == VERSION_MAXMIND) {
        MMDB_close(&mmdb);
    }
#endif
#ifdef WITH_GEOIP
    if (m_version == VERSION_GEOIP && m_gi != NULL) {
        GeoIP_delete(m_gi);
        m_gi = NULL;
    }
#endif
    m_version = NOT_LOADED;
}


bool GeoLookup::setDataBase(const std::string& filePath,
    std::string *err) {
    std::string intMax;
    std::string intGeo;

#ifdef WITH_MAXMIND
    int status = MMDB_open(filePath.c_str(), MMDB_MODE_MMAP, &mmdb);
    if (status != MMDB_SUCCESS) {
        intMax.assign("libMaxMind: Can't open: " + std::string(MMDB_strerror(status)) + ".");
    } else {
        m_version = VERSION_MAXMIND;
    }
#endif

#ifdef WITH_GEOIP
    if (m_version == NOT_LOADED) {
        m_gi = GeoIP_open(filePath.c_str(), GEOIP_INDEX_CACHE);
        if (m_gi == NULL) {
            intGeo.append("GeoIP: Can't open: " + filePath + ".");
        } else {
            m_version = VERSION_GEOIP;
        }
    }
#endif

    if (m_version == NOT_LOADED) {
        err->assign("Can't open:  " + filePath + ". ");
        err->append("Support enabled for:");
#ifdef WITH_MAXMIND
        err->append(" libMaxMind");
#endif

#ifdef WITH_GEOIP
        err->append(" GeoIP");
#endif
        err->append(".");

        if (intMax.size() > 0) {
            err->append(" " + intMax);

        }
        if (intGeo.size() > 0) {
            err->append(" " + intGeo);
        }
        return false;
    }

    return true;
}


bool GeoLookup::lookup(const std::string& target, Transaction *trans,
    std::function<bool(int, std::string)> debug) {

    if (m_version == NOT_LOADED) {
        if (debug) {
            debug(4, "Database is not open. " \
                "Use: SecGeoLookupDb directive.");
        }
        return false;
    }

#ifdef WITH_MAXMIND
    if (m_version == VERSION_MAXMIND) {
        int gai_error, mmdb_error;
        MMDB_lookup_result_s r;
        int status;

        r = MMDB_lookup_string(&mmdb, target.c_str(), &gai_error, &mmdb_error);

        if (gai_error) {
            if (debug) {
                debug(4, "MaxMind: Error from getaddrinfo for: " +
                    target + ". " + gai_strerror(gai_error));
            }
            return false;
        }

        if (mmdb_error != MMDB_SUCCESS) {
            if (debug) {
                debug(4, "MaxMind: Got an error from libmaxminddb: " +
                    std::string(MMDB_strerror(mmdb_error)));
            }
            return false;
        }

        if (!r.found_entry) {
            return false;
        } else {
            MMDB_entry_data_s entry_data;

            status = MMDB_get_value(&r.entry, &entry_data,
                "country", "iso_code", NULL);
            if (status == MMDB_SUCCESS && entry_data.has_data) {
                trans->m_variableGeo.set("COUNTRY_CODE",
                    std::string(entry_data.utf8_string,
                        entry_data.data_size), 0);
            }

            status = MMDB_get_value(&r.entry, &entry_data,
                "country", "names", "en", NULL);
            if (status == MMDB_SUCCESS && entry_data.has_data) {
                trans->m_variableGeo.set("COUNTRY_NAME",
                    std::string(entry_data.utf8_string,
                        entry_data.data_size), 0);
            }

            status = MMDB_get_value(&r.entry, &entry_data,
                "continent", "names", "en", NULL);
            if (status == MMDB_SUCCESS && entry_data.has_data) {
                trans->m_variableGeo.set("COUNTRY_CONTINENT",
                    std::string(entry_data.utf8_string,
                        entry_data.data_size), 0);
            }

            status = MMDB_get_value(&r.entry, &entry_data,
                "city", "names", "en", NULL);
            if (status == MMDB_SUCCESS && entry_data.has_data) {
                trans->m_variableGeo.set("CITY",
                    std::string(entry_data.utf8_string,
                        entry_data.data_size), 0);
            }

            status = MMDB_get_value(&r.entry, &entry_data,
                "postal", "code", NULL);
            if (status == MMDB_SUCCESS && entry_data.has_data) {
                trans->m_variableGeo.set("POSTAL_CODE",
                    std::string(entry_data.utf8_string,
                        entry_data.data_size), 0);
            }

            status = MMDB_get_value(&r.entry, &entry_data,
                "location", "latitude", NULL);
            if (status == MMDB_SUCCESS && entry_data.has_data) {
                trans->m_variableGeo.set("LATITUDE",
                    std::to_string(entry_data.double_value), 0);
            }

            status = MMDB_get_value(&r.entry, &entry_data,
                "location", "longitude", NULL);
            if (status == MMDB_SUCCESS && entry_data.has_data) {
                trans->m_variableGeo.set("LONGITUDE",
                    std::to_string(entry_data.double_value), 0);
            }

            /*
            status = MMDB_get_value(&r.entry, &entry_data,
                NULL);
            if (status == MMDB_SUCCESS && entry_data.has_data) {
                trans->m_variableGeo.set("COUNTRY_CODE3",
                    std::string(entry_data.utf8_string), 0);
            }

            status = MMDB_get_value(&r.entry, &entry_data,
                NULL);
            if (status == MMDB_SUCCESS && entry_data.has_data) {
                trans->m_variableGeo.set("REGION",
                    std::string(entry_data.utf8_string), 0);
            }

            status = MMDB_get_value(&r.entry, &entry_data,
                NULL);
            if (status == MMDB_SUCCESS && entry_data.has_data) {
                trans->m_variableGeo.set("DMA_CODE",
                    std::string(entry_data.utf8_string), 0);
            }

            status = MMDB_get_value(&r.entry, &entry_data,
                NULL);
            if (status == MMDB_SUCCESS && entry_data.has_data) {
                trans->m_variableGeo.set("AREA_CODE",
                    std::string(entry_data.utf8_string), 0);
            }
            */
        }
    }
#endif

#ifdef WITH_GEOIP
    if (m_version == VERSION_GEOIP) {
        GeoIPRecord *gir;
        gir = GeoIP_record_by_name(m_gi, target.c_str());
        if (gir == NULL) {
            return false;
        }

        if (trans) {
            if (gir->country_code) {
                trans->m_variableGeo.set("COUNTRY_CODE",
                    std::string(gir->country_code), 0);
            }
            if (gir->country_code3) {
                trans->m_variableGeo.set("COUNTRY_CODE3",
                    std::string(gir->country_code3), 0);
            }
            if (gir->country_name) {
                trans->m_variableGeo.set("COUNTRY_NAME",
                    std::string(gir->country_name), 0);
            }
            if (gir->continent_code) {
                trans->m_variableGeo.set("COUNTRY_CONTINENT",
                    std::string(gir->continent_code), 0);
            }
            if (gir->country_code && gir->region) {
                trans->m_variableGeo.set("REGION",
                    std::string(GeoIP_region_name_by_code(gir->country_code,
                        gir->region)), 0);
            }
            if (gir->city) {
                trans->m_variableGeo.set("CITY", std::string(gir->city), 0);
            }
            if (gir->postal_code) {
                trans->m_variableGeo.set("POSTAL_CODE",
                    std::string(gir->postal_code), 0);
            }
            if (gir->latitude) {
                trans->m_variableGeo.set("LATITUDE",
                    std::to_string(gir->latitude), 0);
            }
            if (gir->longitude) {
                trans->m_variableGeo.set("LONGITUDE",
                    std::to_string(gir->longitude), 0);
            }
            if (gir->metro_code) {
                trans->m_variableGeo.set("DMA_CODE",
                    std::to_string(gir->metro_code), 0);
            }
            if (gir->area_code) {
                trans->m_variableGeo.set("AREA_CODE",
                    std::to_string(gir->area_code), 0);
            }
        }

        GeoIPRecord_delete(gir);
    }
#endif

    return true;
}



}  // namespace Utils
}  // namespace modsecurity

