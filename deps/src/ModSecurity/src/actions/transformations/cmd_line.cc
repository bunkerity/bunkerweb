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

#include "src/actions/transformations/cmd_line.h"

#include <iostream>
#include <string>
#include <algorithm>
#include <functional>
#include <cctype>
#include <locale>

#include "modsecurity/transaction.h"
#include "src/actions/transformations/transformation.h"


namespace modsecurity {
namespace actions {
namespace transformations {


std::string CmdLine::evaluate(std::string value,
    Transaction *transaction) {
    std::string ret;
    int space = 0;

    for (auto& a : value) {
        switch (a) {
            /* remove some characters */
            case '"':
            case '\'':
            case '\\':
            case '^':
                break;

            /* replace some characters to space (only one) */
            case ' ':
            case ',':
            case ';':
            case '\t':
            case '\r':
            case '\n':
                if (space == 0) {
                    ret.append(" ");
                    space++;
                }
                break;

            /* remove space before / or ( */
            case '/':
            case '(':
                if (space) {
                    ret.pop_back();
                }
                space = 0;
                ret.append(&a, 1);
                break;

            /* copy normal characters */
            default :
                char b = std::tolower(a);
                ret.append(&b, 1);
                space = 0;
                break;
        }
    }

    return ret;
}


}  // namespace transformations
}  // namespace actions
}  // namespace modsecurity

