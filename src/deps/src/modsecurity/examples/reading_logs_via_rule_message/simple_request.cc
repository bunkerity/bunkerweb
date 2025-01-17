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

#include <stdio.h>
#include <string.h>

#include <modsecurity/modsecurity.h>
#include <modsecurity/rules_set.h>
#include "examples/reading_logs_via_rule_message/reading_logs_via_rule_message.h"



int main(int argc, char **argv) {
    if (argc < 2) {
        std::cout << "Use " << *argv << " test-case-file.conf";
        std::cout << std::endl << std::endl;
        return -1;
    }

    char *rule = *(++argv);
    std::string rules(rule);
    ReadingLogsViaRuleMessage rlvrm(request_header, request_uri, request_body,
        response_headers, response_body, ip, rules);
    rlvrm.process();

    return 0;
}
