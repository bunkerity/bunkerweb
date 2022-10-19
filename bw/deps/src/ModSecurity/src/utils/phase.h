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

#include <ctime>
#include <iostream>
#include <string>
#include <vector>

#ifndef SRC_UTILS_PHASE_H_
#define SRC_UTILS_PHASE_H_

#include "modsecurity/modsecurity.h"

namespace modsecurity {
namespace utils {

std::string phase_name(int x) {
    switch (x) {
        case modsecurity::Phases::ConnectionPhase:
            return "Connection Phase";
            break;
        case modsecurity::Phases::UriPhase:
            return "URI Phase";
            break;
        case modsecurity::Phases::RequestHeadersPhase:
            return "Request Headers";
            break;
        case modsecurity::Phases::RequestBodyPhase:
            return "Request Body";
            break;
        case modsecurity::Phases::ResponseHeadersPhase:
            return "Response Headers";
            break;
        case modsecurity::Phases::ResponseBodyPhase:
            return "Reponse Body";
            break;
        case modsecurity::Phases::LoggingPhase:
            return "Logging";
            break;
    }
    return "Phase '" + std::to_string(x) + "' is not known.";
}

}  // namespace utils
}  // namespace modsecurity

#endif  // SRC_UTILS_PHASE_H_
