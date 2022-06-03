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

#include "modsecurity/rules_properties.h"

#include <string>

#include "src/utils/string.h"
#include "src/variables/variable.h"

namespace modsecurity {


void ConfigUnicodeMap::loadConfig(std::string f, double configCodePage,
    RulesProperties *driver, std::string *errg) {
    char *buf = NULL;
    char *hmap = NULL;
    char *p = NULL;
    char *savedptr = NULL;
    char *ucode = NULL;
    int code = 0;
    int found = 0;
    int length = 0;
    int Map = 0;
    int processing = 0;
    unsigned int codepage = 0;

    driver->m_unicodeMapTable.m_set = true;
    driver->m_unicodeMapTable.m_unicodeCodePage = configCodePage;

    driver->m_unicodeMapTable.m_unicodeMapTable.reset(new modsecurity::UnicodeMapHolder());

    /* Setting some unicode values - http://tools.ietf.org/html/rfc3490#section-3.1 */
    /* Set 0x3002 -> 0x2e */
    driver->m_unicodeMapTable.m_unicodeMapTable->change(0x3002, 0x2e);
    /* Set 0xFF61 -> 0x2e */
    driver->m_unicodeMapTable.m_unicodeMapTable->change(0xff61, 0x2e);
    /* Set 0xFF0E -> 0x2e */
    driver->m_unicodeMapTable.m_unicodeMapTable->change(0xff0e, 0x2e);
    /* Set 0x002E -> 0x2e */
    driver->m_unicodeMapTable.m_unicodeMapTable->change(0x002e, 0x2e);


    std::ifstream file_stream(f, std::ios::in | std::ios::binary);
    if (file_stream) {
        file_stream.seekg (0, file_stream.end);
        length = file_stream.tellg();
        file_stream.seekg (0, file_stream.beg);
    } else {
        std::stringstream ss;
        ss << "Failed to open the unicode map file from: " << f << " ";
        errg->assign(ss.str());
        return;
    }

    if (length <= 0) {
        std::stringstream ss;
        ss << "Failed to open the unicode map file from: " << f << " ";
        errg->assign(ss.str());
        return;
    }

    buf = new char[length+1];
    if (!buf) {
        std::stringstream ss;
        ss << "Failed to open the unicode map file from: " << f << " ";
        errg->assign(ss.str());
        return;
    }

    memset(buf, '\0', (sizeof(char)*(length+1)));

    file_stream.read(buf, length);
    file_stream.close();

    p = strtok_r(buf, CODEPAGE_SEPARATORS, &savedptr);

    while (p != NULL) {
        codepage = atol(p);

        if (codepage == configCodePage) {
            found = 1;
        }

        if (found == 1 && (strchr(p,':') != NULL))   {
            char *mapping = strdup(p);
            processing = 1;

            if (mapping != NULL) {
                ucode = strtok_r(mapping, ":", &hmap);
                sscanf(ucode, "%x", &code);
                sscanf(hmap, "%x", &Map);
                if (code >= 0 && code <= 65535)    {
                    driver->m_unicodeMapTable.m_unicodeMapTable->change(code, Map);
                }

                free(mapping);
                mapping = NULL;
            }
        }

        if (processing == 1 && (strchr(p,':') == NULL)) {
            break;
        }

        if (!savedptr) {
            break;
        }

        p = strtok_r(NULL, CODEPAGE_SEPARATORS, &savedptr);
    }

    delete[] buf;
}


}  // namespace modsecurity

