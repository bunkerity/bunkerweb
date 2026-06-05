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

#ifdef WITH_LIBXML2
#include <libxml/xmlschemas.h>
#include <libxml/xpath.h>
#include <libxml/SAX2.h>
#endif

#include <string>
#include <iostream>

#include "modsecurity/transaction.h"
#include "modsecurity/rules_set.h"

#ifndef SRC_REQUEST_BODY_PROCESSOR_XML_H_
#define SRC_REQUEST_BODY_PROCESSOR_XML_H_


namespace modsecurity {
namespace RequestBodyProcessor {

#ifdef WITH_LIBXML2

/*
* NodeData for parsing XML into args
*/
class NodeData {
    public:
        explicit NodeData();
        ~NodeData();

        bool has_child;
};

/*
* XMLNodes for parsing XML into args
*/
class XMLNodes {
    public:
        std::vector<std::shared_ptr<NodeData>> nodes;
        unsigned long int node_depth;
        std::string       currpath;
        std::string       currval;
        bool              currval_is_set;
        Transaction      *m_transaction;
        // need to store context - this is the same as in xml_data
        // need to stop parsing if the number of arguments reached the limit
        xmlParserCtxtPtr  parsing_ctx_arg;

        explicit XMLNodes (Transaction *);
        ~XMLNodes();
};

struct xml_data {
    std::unique_ptr<xmlSAXHandler> sax_handler;
    xmlParserCtxtPtr parsing_ctx;
    xmlDocPtr doc;

    unsigned int well_formed;

    /* error reporting and XML array flag */
    std::string               xml_error;

    /* additional parser context for arguments */
    xmlParserCtxtPtr          parsing_ctx_arg;

    /* parser state for SAX parser */
    std::unique_ptr<XMLNodes> xml_parser_state;
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

    xml_data m_data;

 private:
    Transaction *m_transaction;
    std::string m_header;
};

#endif

}  // namespace RequestBodyProcessor
}  // namespace modsecurity

#endif  // SRC_REQUEST_BODY_PROCESSOR_XML_H_
