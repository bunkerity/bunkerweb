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

#include "src/operators/inspect_file.h"

#include <stdio.h>

#include <string>
#include <iostream>

#include "src/operators/operator.h"
#include "src/utils/system.h"

#ifdef WIN32
#include "src/compat/msvc.h"
#endif

namespace modsecurity {
namespace operators {

bool InspectFile::init(const std::string &param2, std::string *error) {
    std::ifstream *iss;
    std::string err;
    std::string err_lua;

    m_file = utils::find_resource(m_param, param2, &err);
    iss = new std::ifstream(m_file, std::ios::in);

    if (iss->is_open() == false) {
        error->assign("Failed to open file: " + m_param + ". " + err);
        delete iss;
        return false;
    }

    if (engine::Lua::isCompatible(m_file, &m_lua, &err_lua) == true) {
        m_isScript = true;
    }

    delete iss;
    return true;
}


bool InspectFile::evaluate(Transaction *transaction, const std::string &str) {
    if (m_isScript) {
        return m_lua.run(transaction, str);
    } else {
        FILE *in;
        char buff[512];
        std::stringstream s;
        std::string res;
        std::string openstr;

        openstr.append(m_param);
        openstr.append(" ");
        openstr.append(str);
        if (!(in = popen(openstr.c_str(), "r"))) {
            return false;
        }

        while (fgets(buff, sizeof(buff), in) != NULL) {
            s << buff;
        }

        pclose(in);

        res.append(s.str());
        if (res.size() > 1 && res[0] != '1') {
            return true; /* match */
        }

        /* no match */
        return false;
    }
}


}  // namespace operators
}  // namespace modsecurity
