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

#ifdef WITH_LIBXML2
#include <libxml/xmlschemas.h>
#include <libxml/xpath.h>
#endif

#include <string>
#include <iostream>

#include "modsecurity/transaction.h"
#include "modsecurity/rules.h"

#ifndef SRC_REQUEST_BODY_PROCESSOR_XML_H_
#define SRC_REQUEST_BODY_PROCESSOR_XML_H_


namespace modsecurity {
namespace RequestBodyProcessor {

#ifdef WITH_LIBXML2

struct xml_data {
    xmlSAXHandler *sax_handler;
    xmlParserCtxtPtr parsing_ctx;
    xmlDocPtr doc;

    unsigned int well_formed;
};

typedef struct xml_data xml_data;

class XML {
 public:
    explicit XML(Transaction *transaction);
    ~XML();
    bool init();
    bool processChunk(const char *buf, unsigned int size, std::string *err);
    bool complete(std::string *err);
    static xmlParserInputBufferPtr unloadExternalEntity(const char *URI,
        xmlCharEncoding enc);

    static void null_error(void *ctx, const char *msg, ...) {
    }


    xml_data m_data;

 private:
    Transaction *m_transaction;
    std::string m_header;
};

#endif

}  // namespace RequestBodyProcessor
}  // namespace modsecurity

#endif  // SRC_REQUEST_BODY_PROCESSOR_XML_H_
