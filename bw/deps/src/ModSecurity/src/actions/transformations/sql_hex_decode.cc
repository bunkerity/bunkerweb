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

#include "src/actions/transformations/sql_hex_decode.h"

#include <iostream>
#include <string>
#include <algorithm>
#include <functional>
#include <cctype>
#include <locale>
#include <cstring>

#include "modsecurity/transaction.h"
#include "src/actions/transformations/transformation.h"
#include "src/utils/string.h"


namespace modsecurity {
namespace actions {
namespace transformations {

#ifndef VALID_HEX
#define VALID_HEX(X) (((X >= '0') && (X <= '9')) \
    || ((X >= 'a') && (X <= 'f')) \
    || ((X >= 'A') && (X <= 'F')))
#endif
#ifndef ISODIGIT
#define ISODIGIT(X) ((X >= '0') && (X <= '7'))
#endif

std::string SqlHexDecode::evaluate(std::string value,
    Transaction *transaction) {
    std::string ret;
    unsigned char *input;
    int size = 0;

    input = reinterpret_cast<unsigned char *>
        (malloc(sizeof(char) * value.length()+1));

    if (input == NULL) {
        return "";
    }

    memcpy(input, value.c_str(), value.length()+1);

    size = inplace(input, value.length());

    ret.assign(reinterpret_cast<char *>(input), size);
    free(input);

    return ret;
}


int SqlHexDecode::inplace(unsigned char *data, int len) {
    unsigned char *d, *begin = data;
    int count = 0;

    if ((data == NULL) || (len == 0)) {
        return 0;
    }

    for (d = data; (++count < len) && *data; *d++ = *data++) {
        if (*data != '0') {
            continue;
        }
        ++data;
        ++count;
        if (mytolower(*data) != 'x') {
            data--;
            count--;
            continue;
        }

        data++;
        ++count;

        // Do we need to keep "0x" if no hexa after?
        if (!VALID_HEX(data[0]) || !VALID_HEX(data[1])) {
            data -= 2;
            count -= 2;
            continue;
        }

        while (VALID_HEX(data[0]) && VALID_HEX(data[1])) {
            *d++ = utils::string::x2c(data);
            data += 2;
            count += 2;
        }
    }

    *d = '\0';
    return strlen(reinterpret_cast<char *>(begin));
}



}  // namespace transformations
}  // namespace actions
}  // namespace modsecurity
