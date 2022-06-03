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

#include <unistd.h>
#include <stdio.h>
#include <string.h>


#include <modsecurity/modsecurity.h>
#include <modsecurity/rules.h>
#include <modsecurity/rule_message.h>


#include <string>
#include <memory>



char request_uri[] = "/test.pl?param1=test&para2=test2";

char request_body_first[] = "" \
    "<?xml version=\"1.0\" encoding=\"utf-8\"?>\n\r" \
    "<soap:Envelope xmlns:xsi=\"http://www.w3.org/2001/XMLSchema-instance\" " \
    "xmlns:xsd=\"http://www.w3.org/2001/XMLSchema\" ";
char request_body_second[] = "" \
    "xmlns:soap=\"http://schemas.xmlsoap.org/soap/envelope/\">\n\r" \
    "  <soap:Body>\n\r" \
    "  <EnlightenResponse xmlns=\"http://clearforest.com/\">\n\r" \
    "  <EnlightenResult>string</EnlightenResult>\n\r";
char request_body_third[] = "" \
    "  </EnlightenResponse>\n\r" \
    "  </soap:Body>\n\r" \
    "</soap:Envelope>\n\r";


char response_body_first[] = "" \
    "<?xml version=\"1.0\" encoding=\"utf-8\"?>\n\r" \
    "<soap:Envelope xmlns:xsi=\"http://www.w3.org/2001/XMLSchema-instance\" " \
    "xmlns:xsd=\"http://www.w3.org/2001/XMLSchema\" ";
char response_body_second[] = "" \
    "xmlns:soap=\"http://schemas.xmlsoap.org/soap/envelope/\">\n\r" \
    "  <soap:Body>\n\r" \
    "  <EnlightenResponse xmlns=\"http://clearforest.com/\">\n\r" \
    "  <EnlightenResult>string</EnlightenResult>\n\r";
char response_body_third[] = "" \
    "  </EnlightenResponse>\n\r" \
    "  </soap:Body>\n\r" \
    "</soap:Envelope>\n\r";

char ip[] = "200.249.12.31";

static void logCb(void *data, const void *ruleMessagev) {
    if (ruleMessagev == NULL) {
        std::cout << "I've got a call but the message was null ;(";
        std::cout << std::endl;
        return;
    }

    const modsecurity::RuleMessage *ruleMessage = \
        reinterpret_cast<const modsecurity::RuleMessage *>(ruleMessagev);

    std::cout << "Rule Id: " << std::to_string(ruleMessage->m_ruleId);
    std::cout << " phase: " << std::to_string(ruleMessage->m_phase);
    std::cout << std::endl;
    if (ruleMessage->m_isDisruptive) {
        std::cout << " * Disruptive action: ";
        std::cout << modsecurity::RuleMessage::log(ruleMessage);
        std::cout << std::endl;
        std::cout << " ** %d is meant to be informed by the webserver.";
        std::cout << std::endl;
    } else {
        std::cout << " * Match, but no disruptive action: ";
        std::cout << modsecurity::RuleMessage::log(ruleMessage);
        std::cout << std::endl;
    }
}

int process_intervention(modsecurity::Transaction *transaction) {
    modsecurity::ModSecurityIntervention intervention;
    intervention.status = 200;
    intervention.url = NULL;
    intervention.log = NULL;
    intervention.disruptive = 0;

    if (msc_intervention(transaction, &intervention) == 0) {
        return 0;
    }

    if (intervention.log == NULL) {
        intervention.log = strdup("(no log message was specified)");
    }

    std::cout << "Log: " << intervention.log << std::endl;
    free(intervention.log);
    intervention.log = NULL;

    if (intervention.url != NULL) {
        std::cout << "Intervention, redirect to: " << intervention.url;
        std::cout << " with status code: " << intervention.status << std::endl;
        free(intervention.url);
        intervention.url = NULL;
        return intervention.status;
    }

    if (intervention.status != 200) {
        std::cout << "Intervention, returning code: " << intervention.status;
        std::cout << std::endl;
        return intervention.status;
    }

    return 0;
}

int main(int argc, char **argv) {
    modsecurity::ModSecurity *modsec;
    modsecurity::Rules *rules;
    modsecurity::ModSecurityIntervention it;

    if (argc < 2) {
        std::cout << "Use " << *argv << " test-case-file.conf";
        std::cout << std::endl << std::endl;
        return -1;
    }
    *(argv++);

    std::string rules_arg(*argv);

    /**
     * ModSecurity initial setup
     *
     */
    modsec = new modsecurity::ModSecurity();
    modsec->setConnectorInformation("ModSecurity-test v0.0.1-alpha" \
        " (ModSecurity test)");
    modsec->setServerLogCb(logCb, modsecurity::RuleMessageLogProperty
        | modsecurity::IncludeFullHighlightLogProperty);

    /**
     * loading the rules....
     *
     */
    rules = new modsecurity::Rules();
    if (rules->loadFromUri(rules_arg.c_str()) < 0) {
        std::cout << "Problems loading the rules..." << std::endl;
        std::cout << rules->m_parserError.str() << std::endl;
        return -1;
    }


    /**
     * We are going to have a transaction
     *
     */
    modsecurity::Transaction *modsecTransaction = \
        new modsecurity::Transaction(modsec, rules, NULL);
    process_intervention(modsecTransaction);

    /**
     * Initial connection setup
     *
     */
    modsecTransaction->processConnection(ip, 12345, "127.0.0.1", 80);
    process_intervention(modsecTransaction);

    /**
     * Finally we've got the URI
     *
     */
    modsecTransaction->processURI(request_uri, "GET", "1.1");
    process_intervention(modsecTransaction);

    /**
     * Lets add our request headers.
     *
     */
    modsecTransaction->addRequestHeader("Host",
        "net.tutsplus.com");
    process_intervention(modsecTransaction);

    /**
     * No other reuqest header to add, let process it.
     *
     */
    modsecTransaction->processRequestHeaders();
    process_intervention(modsecTransaction);

    /**
     * There is a request body to be informed...
     *
     */
    modsecTransaction->appendRequestBody(
        (const unsigned char*)request_body_first,
        strlen((const char*)request_body_first));
    process_intervention(modsecTransaction);

    modsecTransaction->appendRequestBody(
        (const unsigned char*)request_body_second,
        strlen((const char*)request_body_second));
    process_intervention(modsecTransaction);

    modsecTransaction->appendRequestBody(
        (const unsigned char*)request_body_third,
        strlen((const char*)request_body_third));
    process_intervention(modsecTransaction);

    /**
     * Request body is there ;) lets process it.
     *
     */
    modsecTransaction->processRequestBody();
    process_intervention(modsecTransaction);

    /**
     * The webserver is giving back the response headers.
     */
    modsecTransaction->addResponseHeader("HTTP/1.1",
        "200 OK");
    process_intervention(modsecTransaction);

    /**
     * The response headers are filled in, lets process.
     *
     */
    modsecTransaction->processResponseHeaders(200, "HTTP 1.2");
    process_intervention(modsecTransaction);

    /**
     * It is time to let modsec aware of the response body
     *
     */
    modsecTransaction->appendResponseBody(
        (const unsigned char*)response_body_first,
        strlen((const char*)response_body_first));
    process_intervention(modsecTransaction);

    modsecTransaction->appendResponseBody(
        (const unsigned char*)response_body_second,
        strlen((const char*)response_body_second));
    process_intervention(modsecTransaction);

    modsecTransaction->appendResponseBody(
        (const unsigned char*)response_body_third,
        strlen((const char*)response_body_third));
    process_intervention(modsecTransaction);

    /**
     * Finally, lets have the response body processed.
     *
     */
    modsecTransaction->processResponseBody();
    process_intervention(modsecTransaction);

    /**
     * Keeping track of everything: saving the logs.
     *
     */
    modsecTransaction->processLogging();
    process_intervention(modsecTransaction);


    /**
     * cleanup.
     */
    delete modsecTransaction;
    delete rules;
    delete modsec;
}
