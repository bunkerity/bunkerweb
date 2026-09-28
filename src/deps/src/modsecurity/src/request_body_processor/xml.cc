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

#include "src/request_body_processor/xml.h"

#include <list>
#include <iostream>
#include <string>


namespace modsecurity {
namespace RequestBodyProcessor {

#ifdef WITH_LIBXML2

/*
* NodeData for parsing XML into args
*/
NodeData::NodeData() {
    has_child = false;
}

NodeData::~NodeData() {};

/*
* XMLNodes for parsing XML into args
*/
XMLNodes::XMLNodes(Transaction *transaction) 
    : nodes{},
    node_depth(0),
    currpath(""),
    currval(""),
    currval_is_set(false),
    m_transaction(transaction)
    {}

XMLNodes::~XMLNodes() {};

/*
* SAX handler for parsing XML into args
*/
class MSCSAXHandler {
    public:
        void onStartElement(void * ctx, const xmlChar *localname) {

            std::string name = reinterpret_cast<const char*>(localname);

            XMLNodes* xml_data = static_cast<XMLNodes*>(ctx);
            xml_data->nodes.push_back(std::make_shared<NodeData>());
            xml_data->node_depth++;
            // FIXME - later if we want to check the depth of XML tree
            /* if (max_depth > 0 && max_depth > xml_data->node_depth) {
                std::cout << "Depth of XML tree reached the given maximum value " << xml_data->node_depth << std::endl;
                exit(1);
            } */
            // if it's not the first (root) item, then append a '.'
            // note, the condition should always be true because there is always a pseudo root element: 'xml'
            if (xml_data->nodes.size() > 1) {
                xml_data->currpath.append(".");
                xml_data->nodes[xml_data->nodes.size()-2]->has_child = true;
            }
            xml_data->currpath.append(name);
            // set the current value empty
            // this is necessary because if there is any text between the tags (new line, etc)
            // it will be added to the current value
            xml_data->currval = "";
            xml_data->currval_is_set = false;
        }

        void onEndElement(void * ctx, const xmlChar *localname) {
            std::string name = reinterpret_cast<const char*>(localname);
            XMLNodes* xml_data = static_cast<XMLNodes*>(ctx);
            const std::shared_ptr<NodeData>& nd = xml_data->nodes[xml_data->nodes.size()-1];
            if (nd->has_child == false) {
                // check the return value
                // if false, then stop parsing
                // this means the number of arguments reached the limit
                if (xml_data->m_transaction->addArgument("XML", xml_data->currpath, xml_data->currval, 0) == false) {
                    xmlStopParser(xml_data->parsing_ctx_arg);
                }
            }
            if (xml_data->currpath.length() > 0) {
                // set an offset to store whether this is the first item, in order to know whether to remove the '.'
                int offset = (xml_data->nodes.size() > 1) ? 1 : 0;
                xml_data->currpath.erase(xml_data->currpath.length() - (name.length()+offset));
            }
            xml_data->nodes.pop_back();
            xml_data->node_depth--;
            xml_data->currval = "";
            xml_data->currval_is_set = false;
        }

        void onCharacters(void *ctx, const xmlChar *ch, int len) {
            XMLNodes* xml_data = static_cast<XMLNodes*>(ctx);
            std::string content(reinterpret_cast<const char *>(ch), len);

            // libxml2 SAX parser will call this function multiple times
            // during the parsing of a single node, if the value has multibyte
            // characters, so we need to concatenate the values
            if (xml_data->currval_is_set == false) {
                xml_data->currval = content;
                xml_data->currval_is_set = true;
            } else {
                xml_data->currval += content;
            }
        }
};

extern "C" {
    void MSC_startElement(void *userData,
        const xmlChar *name,
        const xmlChar *prefix,
        const xmlChar *URI,
        int nb_namespaces,
        const xmlChar **namespaces,
        int nb_attributes,
        int nb_defaulted,
        const xmlChar **attributes) {

            MSCSAXHandler* handler = static_cast<MSCSAXHandler*>(userData);
            handler->onStartElement(userData, name);
    }

    void MSC_endElement(
        void *userData,
        const xmlChar *name,
        const xmlChar* prefix,
        const xmlChar* URI) {

            MSCSAXHandler* handler = static_cast<MSCSAXHandler*>(userData);
            handler->onEndElement(userData, name);
    }

    void MSC_xmlcharacters(void *userData, const xmlChar *ch, int len) {
        MSCSAXHandler* handler = static_cast<MSCSAXHandler*>(userData);
        handler->onCharacters(userData, ch, len);
    }
}

XML::XML(Transaction *transaction)
    : m_transaction(transaction) {
    m_data.doc = NULL;
    m_data.parsing_ctx = NULL;
    m_data.sax_handler = NULL;
    m_data.xml_error = "";
    m_data.parsing_ctx_arg = NULL;
    m_data.xml_parser_state = NULL;
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
    //xmlParserInputBufferCreateFilenameFunc entity;
    if (m_transaction->m_rules->m_secXMLExternalEntity
        == RulesSetProperties::TrueConfigBoolean) {
        /*entity = */xmlParserInputBufferCreateFilenameDefault(
            __xmlParserInputBufferCreateFilename);
    } else {
        /*entity = */xmlParserInputBufferCreateFilenameDefault(
            this->unloadExternalEntity);
    }
    if (m_transaction->m_secXMLParseXmlIntoArgs
        == RulesSetProperties::TrueConfigXMLParseXmlIntoArgs ||
        m_transaction->m_secXMLParseXmlIntoArgs
        == RulesSetProperties::OnlyArgsConfigXMLParseXmlIntoArgs) {
        ms_dbg_a(m_transaction, 9,
                "XML: SecParseXmlIntoArgs is set to " \
                + RulesSetProperties::configXMLParseXmlIntoArgsString(static_cast<RulesSetProperties::ConfigXMLParseXmlIntoArgs>(m_transaction->m_secXMLParseXmlIntoArgs)));
        m_data.sax_handler = std::make_unique<xmlSAXHandler>();
        memset(m_data.sax_handler.get(), 0, sizeof(xmlSAXHandler));

        m_data.sax_handler->initialized = XML_SAX2_MAGIC;
        m_data.sax_handler->startElementNs = &MSC_startElement;
        m_data.sax_handler->endElementNs = &MSC_endElement;
        m_data.sax_handler->characters = &MSC_xmlcharacters;

        // set the parser state struct
        m_data.xml_parser_state                  = std::make_unique<XMLNodes>(m_transaction);
        m_data.xml_parser_state->node_depth      = 0;
        m_data.xml_parser_state->currval         = "";
        // the XML will contain at least one node, which is the pseudo root node 'xml'
        m_data.xml_parser_state->currpath        = "xml.";
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
    if (m_data.parsing_ctx == NULL && m_data.parsing_ctx_arg == NULL) {
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

        if (m_transaction->m_secXMLParseXmlIntoArgs
            != RulesSetProperties::OnlyArgsConfigXMLParseXmlIntoArgs) {
            m_data.parsing_ctx = xmlCreatePushParserCtxt(NULL, NULL,
                buf, size, "body.xml");

            if (m_data.parsing_ctx == NULL) {
                ms_dbg_a(m_transaction, 4,
                    "XML: Failed to create parsing context.");
                error->assign("XML: Failed to create parsing context.");
                return false;
            }
            // disable parser errors being printed to stderr
            m_data.parsing_ctx->options |= XML_PARSE_NOWARNING | XML_PARSE_NOERROR;
        }

        if (m_transaction->m_secXMLParseXmlIntoArgs
            == RulesSetProperties::OnlyArgsConfigXMLParseXmlIntoArgs ||
            m_transaction->m_secXMLParseXmlIntoArgs
            == RulesSetProperties::TrueConfigXMLParseXmlIntoArgs) {
            m_data.parsing_ctx_arg = xmlCreatePushParserCtxt(
                m_data.sax_handler.get(),
                m_data.xml_parser_state.get(),
                buf,
                size,
                NULL);
            if (m_data.parsing_ctx_arg == NULL) {
                error->assign("XML: Failed to create parsing context for ARGS.");
                return false;
            }
            // disable parser errors being printed to stderr
            m_data.parsing_ctx_arg->options |= XML_PARSE_NOWARNING | XML_PARSE_NOERROR;
        }

        return true;
    }

    /* Not a first invocation. */
    if (m_data.parsing_ctx != NULL &&
        m_transaction->m_secXMLParseXmlIntoArgs
        != RulesSetProperties::OnlyArgsConfigXMLParseXmlIntoArgs) {
        xmlParseChunk(m_data.parsing_ctx, buf, size, 0);
        m_data.xml_parser_state->parsing_ctx_arg = m_data.parsing_ctx_arg;
        if (m_data.parsing_ctx->wellFormed != 1) {
            error->assign("XML: Failed to parse document.");
            ms_dbg_a(m_transaction, 4, "XML: Failed to parse document.");
            return false;
        }
    }

    if (m_data.parsing_ctx_arg != NULL &&
        (
            m_transaction->m_secXMLParseXmlIntoArgs
              == RulesSetProperties::OnlyArgsConfigXMLParseXmlIntoArgs
            ||
            m_transaction->m_secXMLParseXmlIntoArgs
              == RulesSetProperties::TrueConfigXMLParseXmlIntoArgs)
        ) {
        xmlParseChunk(m_data.parsing_ctx_arg, buf, size, 0);
        if (m_data.parsing_ctx_arg->wellFormed != 1) {
            error->assign("XML: Failed to parse document for ARGS.");
            ms_dbg_a(m_transaction, 4, "XML: Failed to parse document for ARGS.");
            return false;
        }
    }

    return true;
}


bool XML::complete(std::string *error) {
    /* Only if we have a context, meaning we've done some work. */
    if (m_data.parsing_ctx != NULL || m_data.parsing_ctx_arg != NULL) {
        if (m_data.parsing_ctx != NULL &&
            m_transaction->m_secXMLParseXmlIntoArgs
            != RulesSetProperties::OnlyArgsConfigXMLParseXmlIntoArgs) {
            /* This is how we signal the end of parsing to libxml. */
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
                error->assign("XML: Failed to parse document.");
                ms_dbg_a(m_transaction, 4, "XML: Failed to parse document.");
                return false;
            }
        }
        if (m_data.parsing_ctx_arg != NULL &&
            (
                m_transaction->m_secXMLParseXmlIntoArgs
                  == RulesSetProperties::OnlyArgsConfigXMLParseXmlIntoArgs
                  ||
                m_transaction->m_secXMLParseXmlIntoArgs
                  == RulesSetProperties::TrueConfigXMLParseXmlIntoArgs)
            ) {
            /* This is how we signale the end of parsing to libxml. */
            if (xmlParseChunk(m_data.parsing_ctx_arg, NULL, 0, 1) != 0) {
                if (m_data.xml_error != "") {
                    error->assign(m_data.xml_error);
                }
                else {
                    error->assign("XML: Failed to parse document for ARGS.");
                }
                xmlFreeParserCtxt(m_data.parsing_ctx_arg);
                m_data.parsing_ctx_arg = NULL;
                return false;
            }
            xmlFreeParserCtxt(m_data.parsing_ctx_arg);
            m_data.parsing_ctx_arg = NULL;
        }
    }

    return true;
}

#endif

}  // namespace RequestBodyProcessor
}  // namespace modsecurity
