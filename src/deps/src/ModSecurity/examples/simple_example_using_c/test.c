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


#include <stdio.h>
#include <stdlib.h>

#include "modsecurity/modsecurity.h"
#include "modsecurity/rules.h"


char main_rule_uri[] = "basic_rules.conf";

int main (int argc, char **argv)
{
    int ret;
    const char *error = NULL;
    ModSecurity *modsec;
    Transaction *transaction = NULL;
    Rules *rules;

    modsec = msc_init();

    msc_set_connector_info(modsec, "ModSecurity-test v0.0.1-alpha (Simple " \
        "example on how to use ModSecurity API");

    rules = msc_create_rules_set();

    ret = msc_rules_add_file(rules, main_rule_uri, &error);
    if (ret < 0) {
        fprintf(stderr, "Problems loading the rules --\n");
        fprintf(stderr, "%s\n", error);
        goto end;
    }
    msc_rules_dump(rules);

    ret = msc_rules_add_remote(rules, "test",
        "https://www.modsecurity.org/modsecurity-regression-test-secremoterules.txt",
        &error);
    if (ret < 0) {
        fprintf(stderr, "Problems loading the rules --\n");
        fprintf(stderr, "%s\n", error);
        goto end;
    }
    msc_rules_dump(rules);

    transaction = msc_new_transaction(modsec, rules, NULL);

    msc_process_connection(transaction, "127.0.0.1", 12345, "127.0.0.1", 80);
    msc_process_uri(transaction,
        "http://www.modsecurity.org/test?key1=value1&key2=value2&key3=value3",
        "GET", "1.1");
    msc_process_request_headers(transaction);
    msc_process_request_body(transaction);
    msc_process_response_headers(transaction, 200, "HTTP 1.3");
    msc_process_response_body(transaction);
    msc_process_logging(transaction);
end:
    msc_rules_cleanup(rules);
    msc_cleanup(modsec);

    return 0;
}


