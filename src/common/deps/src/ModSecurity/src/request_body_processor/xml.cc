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

#include "src/request_body_processor/xml.h"

#include <list>
#include <iostream>
#include <string>


namespace modsecurity {
namespace RequestBodyProcessor {

#ifdef WITH_LIBXML2

XML::XML(Transaction *transaction)
    : m_transaction(transaction) {
    m_data.doc = NULL;
    m_data.parsing_ctx = NULL;
    m_data.sax_handler = NULL;
}


XML::~XML() {
    if (m_data.parsing_ctx != NULL) {
        xmlFreeParserCtxt(m_data.parsing_ctx);
        m_data.parsing_ctx = NULL;
    }
    if (m_data.doc != NULL) {
        xmlFreeDoc(m_data.doc);
        m_data.doc = NULL;
    }
}


bool XML::init() {
    xmlParserInputBufferCreateFilenameFunc entity;
    if (m_transaction->m_rules->m_secXMLExternalEntity
        == RulesProperties::TrueConfigBoolean) {
        entity = xmlParserInputBufferCreateFilenameDefault(
            __xmlParserInputBufferCreateFilename);
    } else {
        entity = xmlParserInputBufferCreateFilenameDefault(
            this->unloadExternalEntity);
    }

    return true;
}


xmlParserInputBufferPtr XML::unloadExternalEntity(const char *URI,
    xmlCharEncoding enc) {
    return NULL;
}


bool XML::processChunk(const char *buf, unsigned int size,
    std::string *error) {
    /* We want to initialise our parsing context here, to
     * enable us to pass it the first chunk of data so that
     * it can attempt to auto-detect the encoding.
     */
    if (m_data.parsing_ctx == NULL) {
        /* First invocation. */

        ms_dbg_a(m_transaction, 4, "XML: Initialising parser.");

        /* NOTE When Sax interface is used libxml will not
         *      create the document object, but we need it.

        msr->xml->sax_handler = (xmlSAXHandler *)apr_pcalloc(msr->mp,
            sizeof(xmlSAXHandler));
        if (msr->xml->sax_handler == NULL) return -1;
        msr->xml->sax_handler->error = xml_receive_sax_error;
        msr->xml->sax_handler->warning = xml_receive_sax_error;
        msr->xml->parsing_ctx = xmlCreatePushParserCtxt(msr->xml->sax_handler,
            msr, buf, size, "body.xml");

        */

        m_data.parsing_ctx = xmlCreatePushParserCtxt(NULL, NULL,
            buf, size, "body.xml");

        if (m_data.parsing_ctx == NULL) {
            ms_dbg_a(m_transaction, 4,
                "XML: Failed to create parsing context.");
            error->assign("XML: Failed to create parsing context.");
            return false;
        }

        xmlSetGenericErrorFunc(m_data.parsing_ctx, null_error);

        return true;
    }

    /* Not a first invocation. */
    xmlParseChunk(m_data.parsing_ctx, buf, size, 0);
    if (m_data.parsing_ctx->wellFormed != 1) {
        error->assign("XML: Failed to create parsing context.");
        ms_dbg_a(m_transaction, 4, "XML: Failed parsing document.");
        return false;
    }

    return true;
}


bool XML::complete(std::string *error) {
    /* Only if we have a context, meaning we've done some work. */
    if (m_data.parsing_ctx != NULL) {
        /* This is how we signalise the end of parsing to libxml. */
        xmlParseChunk(m_data.parsing_ctx, NULL, 0, 1);

        /* Preserve the results for our reference. */
        m_data.well_formed = m_data.parsing_ctx->wellFormed;
        m_data.doc = m_data.parsing_ctx->myDoc;

        /* Clean up everything else. */
        xmlFreeParserCtxt(m_data.parsing_ctx);
        m_data.parsing_ctx = NULL;
        ms_dbg_a(m_transaction, 4, "XML: Parsing complete (well_formed " \
            + std::to_string(m_data.well_formed) + ").");

        if (m_data.well_formed != 1) {
            error->assign("XML: Failed parsing document.");
            ms_dbg_a(m_transaction, 4, "XML: Failed parsing document.");
            return false;
        }
    }

    return true;
}

#endif

}  // namespace RequestBodyProcessor
}  // namespace modsecurity
