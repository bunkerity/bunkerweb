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

#include "src/request_body_processor/multipart.h"

#include <time.h>
#include <stdio.h>
#include <string.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <fcntl.h>
#include <unistd.h>
#include <list>
#include <iostream>
#include <string>
#include <utility>

#include "modsecurity/collection/collections.h"
#include "modsecurity/rules.h"
#include "src/utils/string.h"


namespace modsecurity {
namespace RequestBodyProcessor {


Multipart::Multipart(std:: string header, Transaction *transaction)
    : m_reqbody_no_files_length(0),
    m_nfiles(0),
    m_boundary_count(0),
    m_buf{0},
    m_buf_contains_line(0),
    m_bufptr(NULL),
    m_bufleft(0),
    m_buf_offset(0),
    m_mpp(NULL),
    m_mpp_state(0),
    m_reserve{0},
    m_seen_data(0),
    m_is_complete(0),
    m_flag_error(0),
    m_flag_data_before(0),
    m_flag_data_after(0),
    m_flag_header_folding(0),
    m_flag_boundary_quoted(0),
    m_flag_lf_line(0),
    m_flag_crlf_line(0),
    m_flag_unmatched_boundary(0),
    m_flag_boundary_whitespace(0),
    m_flag_missing_semicolon(0),
    m_flag_invalid_quoting(0),
    m_flag_invalid_part(0),
    m_flag_invalid_header_folding(0),
    m_flag_file_limit_exceeded(0),
    m_header(header),
    m_transaction(transaction) { }


Multipart::~Multipart() {
    ms_dbg_a(m_transaction, 4,
        "Multipart: Cleanup started (keep files set to " \
        + RulesProperties::configBooleanString(
            m_transaction->m_rules->m_uploadKeepFiles) \
        + ")");

    if (m_transaction->m_rules->m_uploadKeepFiles
        != RulesProperties::TrueConfigBoolean) {
        for (MultipartPart *m : m_parts) {
            if (m->m_type == MULTIPART_FILE) {
                if (!m->m_tmp_file_name.empty()) {
                    /* make sure it is closed first */
                    if (m->m_tmp_file_fd > 0) {
                        close(m->m_tmp_file_fd);
                        m->m_tmp_file_fd = -1;
                    }
                    const int unlink_rc =
                        unlink(m->m_tmp_file_name.c_str());

                    if (unlink_rc < 0) {
                        ms_dbg_a(m_transaction, 1,
                            "Multipart: Failed to delete file (part) \"" \
                            + m->m_tmp_file_name + "\" because " \
                            + std::to_string(errno) +  "(" \
                            + strerror(errno) + ")");
                    } else {
                        ms_dbg_a(m_transaction, 4,
                            "Multipart: file deleted successfully (part) \"" \
                            + m->m_tmp_file_name + "\"");
                    }

                }
            }
        }
    }

    while (m_parts.empty() == false) {
        auto *a = m_parts.back();
        m_parts.pop_back();
        delete a;
    }

    if (m_mpp != NULL) {
        delete m_mpp;
        m_mpp = NULL;
    }
}


int Multipart::is_token_char(unsigned char c) {
    /* ENH Is the performance important at all? We could use a table instead. */

    /* CTLs not allowed */
    if ((c <= 32) || (c >= 127)) {
        return 0;
    }

    switch (c) {
        case '(' :
        case ')' :
        case '<' :
        case '>' :
        case '@' :
        case ',' :
        case ';' :
        case ':' :
        case '\\' :
        case '"' :
        case '/' :
        case '[' :
        case ']' :
        case '?' :
        case '=' :
            return 0;
    }

    return 1;
}


int Multipart::boundary_characters_valid(const char *boundary) {
    const unsigned char *p = (unsigned char *)boundary;
    unsigned char c;

    if (p == NULL) {
        return -1;
    }

    while ((c = *p) != '\0') {
        // Check against allowed list defined in RFC2046 page 22
        if (!(
            ('0' <= c && c <= '9')
            || ('A' <= c && c <= 'Z')
            || ('a' <= c && c <= 'z')
            || (c == ' ' && *(p + 1) != '\0') // space allowed, but not as last character
            || c == '\''
            || c == '('
            || c == ')'
            || c == '+'
            || c == '_'
            || c == ','
            || c == '-'
            || c == '.'
            || c == '/'
            || c == ':'
            || c == '='
            || c == '?'
            )) {
            return 0;
        }
        p++;
    }

    return 1;
}


void Multipart::validate_quotes(const char *data)  {
    int i, len;

    if (data == NULL)
        return;

    len = strlen(data);

    for (i = 0; i < len; i++)   {
        if (data[i] == '\'') {
            ms_dbg_a(m_transaction, 9,
                "Multipart: Invalid quoting detected: " \
                + std::string(data) + " length " \
                + std::to_string(len) + " bytes");
            m_flag_invalid_quoting = 1;
        }
    }
}


int Multipart::parse_content_disposition(const char *c_d_value, int offset) {
    const char *p = NULL;

    /* accept only what we understand */
    if (strncmp(c_d_value, "form-data", 9) != 0) {
        return -1;
    }

    /* see if there are any other parts to parse */

    p = c_d_value + 9;
    while ((*p == '\t') || (*p == ' ')) p++;
    if (*p == '\0') {
        return 1; /* this is OK */
    }

    if (*p != ';') {
        return -2;
    }
    p++;

    /* parse the appended parts */

    while (*p != '\0') {
        const char *start = NULL;
        std::string name;
        std::string value;

        /* go over the whitespace */
        while ((*p == '\t') || (*p == ' ')) {
            p++;
        }

        if (*p == '\0') {
            return -3;
        }

        start = p;
        while ((*p != '\0') && (*p != '=') && (*p != '\t') && (*p != ' ')) {
            p++;
        }

        if (*p == '\0') {
            return -4;
        }

        name = std::string(start, (p - start));

        while ((*p == '\t') || (*p == ' ')) {
            p++;
        }

        if (*p == '\0') {
            return -5;
        }

        if (*p != '=') {
            return -13;
        }

        p++;

        while ((*p == '\t') || (*p == ' ')) {
            p++;
        }

        if (*p == '\0') {
            return -6;
        }

        /* Accept both quotes as some backends will accept them, but
         * technically "'" is invalid and so flag_invalid_quoting is
         * set so the user can deal with it in the rules if they so wish.
         */

        if ((*p == '"') || (*p == '\'')) {
            /* quoted */
            char quote = *p;

            if (quote == '\'') {
                m_flag_invalid_quoting = 1;
            }

            p++;
            if (*p == '\0') {
                return -7;
            }

            while (*p != '\0') {
                if (*p == '\\') {
                    if (*(p + 1) == '\0') {
                        /* improper escaping */
                        return -8;
                    }
                    /* only quote and \ can be escaped */
                    if ((*(p + 1) == quote) || (*(p + 1) == '\\')) {
                        p++;
                    } else {
                        /* improper escaping */

                        /* We allow for now because IE sends
                         * improperly escaped content and there's
                         * nothing we can do about it.
                         *
                         * return -9;
                         */
                    }
                } else if (*p == quote) {
                    break;
                }

                value.append((p++), 1);
            }

            p++; /* go over the quote at the end */

        } else {
            /* not quoted */

            start = p;
            while ((*p != '\0') && (is_token_char(*p))) {
                p++;
            }
            value.assign(start, p - start);
        }

        /* evaluate part */
        if (name == "name") {
            validate_quotes(value.c_str());

            m_transaction->m_variableMultipartName.set(value, value,
                offset + ((p - c_d_value) - value.size()));

            if (!m_mpp->m_name.empty()) {
                ms_dbg_a(m_transaction, 4,
                    "Multipart: Warning: Duplicate Content-Disposition " \
                    "name: " + value + ". Previously: " + m_mpp->m_name + "");
                return -14;
            }
            m_mpp->m_name.assign(value);
            m_mpp->m_nameOffset = offset + ((p - c_d_value) - value.size());
            ms_dbg_a(m_transaction, 9,
                "Multipart: Content-Disposition name: " + value + ".");
        } else if (name == "filename") {
            validate_quotes(value.c_str());
            m_transaction->m_variableMultipartFileName.set(value, value, \
                offset + ((p - c_d_value) - value.size()));

            if (!m_mpp->m_filename.empty()) {
                ms_dbg_a(m_transaction, 4,
                    "Multipart: Warning: Duplicate Content-Disposition " \
                    "filename: " + value + ".");
                return -15;
            }
            m_mpp->m_filename.assign(value);
            m_mpp->m_filenameOffset = offset + ((p - c_d_value) - value.size());

            ms_dbg_a(m_transaction, 9,
                "Multipart: Content-Disposition filename: " \
                + value + ".");
        } else {
            return -11;
        }

        if (*p != '\0') {
            while ((*p == '\t') || (*p == ' ')) {
                p++;
            }

            /* the next character must be a zero or a semi-colon */
            if (*p == '\0') {
                return 1; /* this is OK */
            }
            if (*p != ';') {
                p--;
                if (*p == '\'' || *p == '\"') {
                    ms_dbg_a(m_transaction, 9,
                        "Multipart: Invalid quoting detected: " \
                        + std::string(p) + " length " \
                        + std::to_string(strlen(p)) + " bytes");
                    m_flag_invalid_quoting = 1;
                }
                p++;
                return -12;
            }
            p++; /* move over the semi-colon */
        }

        /* loop will stop when (*p == '\0') */
    }

    return 1;
}


int Multipart::tmp_file_name(std::string *filename) const {
    std::string path;
    struct tm timeinfo;
    char tstr[300];
    char *tmp;
    int fd;
    int mode;
    time_t tt = time(NULL);

    localtime_r(&tt, &timeinfo);

    path = m_transaction->m_rules->m_uploadDirectory.m_value;
    mode = m_transaction->m_rules->m_uploadFileMode.m_value;

    memset(tstr, '\0', 300);
    strftime(tstr, 299, "/%Y%m%d-%H%M%S", &timeinfo);
    path = path + tstr + "-" + m_transaction->m_id;
    path = path + "-file-XXXXXX";

    tmp = strdup(path.c_str());

    fd = mkstemp(tmp);
    filename->assign(tmp);
    free(tmp);
    if ((fd != -1) && (mode != 0)) {
        if (fchmod(fd, mode) == -1) {
            return -1;
        }
    }

    return fd;
}


int Multipart::process_part_data(std::string *error, size_t offset) {
    char *p = m_buf + (MULTIPART_BUF_SIZE - m_bufleft);
    char localreserve[2] = { '\0', '\0' }; /* initialized to quiet warning */
    int bytes_reserved = 0;

    /* Preserve some bytes for later. */
    if (((MULTIPART_BUF_SIZE - m_bufleft) >= 1) && (*(p - 1) == '\n')) {
        if (((MULTIPART_BUF_SIZE - m_bufleft) >= 2) && (*(p - 2) == '\r')) {
            /* Two bytes. */
            bytes_reserved = 2;
            localreserve[0] = *(p - 2);
            localreserve[1] = *(p - 1);
            m_bufleft += 2;
            *(p - 2) = 0;
        } else {
            /* Only one byte. */
            bytes_reserved = 1;
            localreserve[0] = *(p - 1);
            localreserve[1] = 0;
            m_bufleft += 1;
            *(p - 1) = 0;
        }
    }

    /* add data to the part we are building */
    if (m_mpp->m_type == MULTIPART_FILE) {
        bool extract = m_transaction->m_rules->m_uploadKeepFiles \
            == RulesProperties::TrueConfigBoolean \
            || m_transaction->m_rules->m_tmpSaveUploadedFiles \
            == RulesProperties::TrueConfigBoolean;

        /* remember where we started */
        if (m_mpp->m_length == 0) {
            m_mpp->m_offset = m_buf_offset;
        }

        /* check if the file limit has been reached */
        if (extract && m_transaction->m_rules->m_uploadFileLimit.m_value
            && (m_nfiles >=
                m_transaction->m_rules->m_uploadFileLimit.m_value)) {
            if (m_flag_file_limit_exceeded == 0) {
                ms_dbg_a(m_transaction, 1,
                    "Multipart: Upload file limit exceeded " \
                    + std::to_string(
                        m_transaction->m_rules->m_uploadFileLimit.m_value) \
                    + ". Use SecUploadFileLimit to change the limit.");
               error->assign("Multipart: Upload file limit exceeded " \
                + std::to_string(
                    m_transaction->m_rules->m_uploadFileLimit.m_value) \
                + ". Use SecUploadFileLimit to change the limit.");
                m_flag_file_limit_exceeded = 1;
            }
            extract = 0;
        }
        /* only store individual files on disk if we are going
         * to keep them or if we need to have them approved later
         */
        if (extract) {
            /* first create a temporary file if we don't have it already */
            if (m_mpp->m_tmp_file_fd == 0) {
                std::string path;
                m_mpp->m_tmp_file_fd = tmp_file_name(&path);

                /* construct temporary file name */
                m_mpp->m_tmp_file_name = path;

                /* do we have an opened file? */
                if (m_mpp->m_tmp_file_fd < 0) {
                    ms_dbg_a(m_transaction, 1,
                        "Multipart: Failed to create file: " \
                        + m_mpp->m_tmp_file_name);
                    error->assign("Multipart: Failed to create file: " \
                        + m_mpp->m_tmp_file_name);
                    return -1;
                }
                /* keep track of the files count */

                m_nfiles++;

                ms_dbg_a(m_transaction, 4,
                    "Multipart: Created temporary file " \
                    + std::to_string(m_nfiles) + " (mode o" + std::to_string(m_transaction->m_rules->m_uploadFileMode.m_value) + "): " \
                    + m_mpp->m_tmp_file_name);
            }

            /* write the reserve first */
            if (m_reserve[0] != 0) {
                if (write(m_mpp->m_tmp_file_fd, &m_reserve[1], m_reserve[0])
                    != m_reserve[0]) {
                    ms_dbg_a(m_transaction, 1,
                        "Multipart: writing to \"" \
                        + m_mpp->m_tmp_file_name + "\" failed");
                    error->assign("Multipart: writing to \"" \
                        + m_mpp->m_tmp_file_name + "\" failed");
                    return -1;
                }

                m_mpp->m_tmp_file_size.first += m_reserve[0];
                if (m_mpp->m_tmp_file_size.second == 0) {
                    m_mpp->m_tmp_file_size.second = offset \
                        - m_mpp->m_tmp_file_size.first;
                }
                m_mpp->m_length += m_reserve[0];
            }

            /* write data to the file */

            if (write(m_mpp->m_tmp_file_fd, m_buf,
                MULTIPART_BUF_SIZE - m_bufleft)
                != (MULTIPART_BUF_SIZE - m_bufleft)) {
                ms_dbg_a(m_transaction, 1,
                    "Multipart: writing to \"" \
                    + m_mpp->m_tmp_file_name + "\" failed");
                error->assign("Multipart: writing to \"" \
                    + m_mpp->m_tmp_file_name + "\" failed");
                return -1;
            }

            m_mpp->m_value.append(std::string(m_buf,
                    MULTIPART_BUF_SIZE - m_bufleft));
            m_mpp->m_valueOffset = offset - (MULTIPART_BUF_SIZE - m_bufleft);

            m_mpp->m_tmp_file_size.first += (MULTIPART_BUF_SIZE - m_bufleft);
            if (m_mpp->m_tmp_file_size.second == 0) {
                m_mpp->m_tmp_file_size.second = offset \
                    - m_mpp->m_tmp_file_size.first;
            }

            m_mpp->m_length += (MULTIPART_BUF_SIZE - m_bufleft);
        } else {
            /* just keep track of the file size */
            m_mpp->m_tmp_file_size.first += (MULTIPART_BUF_SIZE - m_bufleft) \
                + m_reserve[0];
            if (m_mpp->m_tmp_file_size.second == 0) {
                m_mpp->m_tmp_file_size.second = offset \
                    - m_mpp->m_tmp_file_size.first;
            }

            m_mpp->m_length += (MULTIPART_BUF_SIZE - m_bufleft) + m_reserve[0];
        }
    } else if (m_mpp->m_type == MULTIPART_FORMDATA) {
        std::string d;

        /* The buffer contains data so increase the data length counter. */
        m_reqbody_no_files_length += (MULTIPART_BUF_SIZE - m_bufleft) \
            + m_reserve[0];

        /* add this part to the list of parts */

        /* remember where we started */
        if (m_mpp->m_length == 0) {
            m_mpp->m_offset = m_buf_offset;
        }

        if (m_reserve[0] != 0) {
            d.assign(&(m_reserve[1]), m_reserve[0]);
            d.assign(m_buf, MULTIPART_BUF_SIZE - m_bufleft);

            m_mpp->m_length += d.size();
        } else {
            d.assign(m_buf, MULTIPART_BUF_SIZE - m_bufleft);
            m_mpp->m_length += d.size();
        }

        m_mpp->m_value_parts.push_back(std::make_pair(d, m_buf_offset));

        ms_dbg_a(m_transaction, 9,
            "Multipart: Added data to variable: " + d);
    } else {
        ms_dbg_a(m_transaction, 1,
            "Multipart: unknown part type: " \
            + std::to_string(m_mpp->m_type));

        error->assign("Multipart: unknown part type: " \
            + std::to_string(m_mpp->m_type));
        return false;
    }

    /* store the reserved bytes to the multipart
     * context so that they don't get lost
     */
    if (bytes_reserved) {
        m_reserve[0] = bytes_reserved;
        m_reserve[1] = localreserve[0];
        m_reserve[2] = localreserve[1];
        m_buf_offset += bytes_reserved;
    } else {
        m_buf_offset -= m_reserve[0];
        m_reserve[0] = 0;
    }

    return true;
}


int Multipart::process_part_header(std::string *error, int offset) {
    int i, len;

    /* Check for nul bytes. */
    len = MULTIPART_BUF_SIZE - m_bufleft;
    for (i = 0; i < len; i++) {
        if (m_buf[i] == '\0') {
            ms_dbg_a(m_transaction, 1,
                "Multipart: Nul byte in part headers.");

            error->assign("Multipart: Nul byte in part headers.");
            return false;
        }
    }

    i = 0;
    /* The buffer is data so increase the data length counter. */
    m_reqbody_no_files_length += (MULTIPART_BUF_SIZE - m_bufleft);

    if (len > 1) {
        if (m_buf[len - 2] == '\r') {
            m_flag_crlf_line = 1;
        } else {
            m_flag_lf_line = 1;
        }
    } else {
        m_flag_lf_line = 1;
    }

    /* Is this an empty line? */
    if (((m_buf[0] == '\r') && (m_buf[1] == '\n') && (m_buf[2] == '\0'))
        || ((m_buf[0] == '\n') && (m_buf[1] == '\0'))) { /* Empty line. */
        std::string header_value("");
        int rc;

        if (m_mpp->m_headers.count("Content-Disposition") == 0) {
            ms_dbg_a(m_transaction, 1,
                "Multipart: Part missing Content-Disposition header.");

            error->assign("Multipart: Part missing " \
                "Content-Disposition header.");
            return false;
        }
        header_value = m_mpp->m_headers.at("Content-Disposition").second;

        rc = parse_content_disposition(header_value.c_str(),
            m_mpp->m_headers.at("Content-Disposition").first);
        if (rc < 0) {
            ms_dbg_a(m_transaction, 1,
                "Multipart: Invalid Content-Disposition header ("
                + std::to_string(rc) + "): " + header_value);

            error->assign("Multipart: Invalid Content-Disposition header ("
                + std::to_string(rc) + "): " + header_value);
            return false;
        }

        if (m_mpp->m_name.empty()) {
            ms_dbg_a(m_transaction, 1,
                "Multipart: Content-Disposition header missing " \
                "name field.");

            error->assign("Multipart: Content-Disposition header missing " \
                "name field.");

            return false;
        }

        if (!m_mpp->m_filename.empty()) {
            /* Some parsers use crude methods to extract the name and filename
             * values from the C-D header. We need to check for the case where they
             * didn't understand C-D but we did.
             */
            if (strstr(header_value.c_str(), "filename=") == NULL) {
                ms_dbg_a(m_transaction, 1,
                    "Multipart: Invalid Content-Disposition " \
                    "header (filename).");

                error->assign("Multipart: Invalid Content-Disposition " \
                    "header (filename).");
                return false;
            }

            m_mpp->m_type = MULTIPART_FILE;
        } else {
            m_mpp->m_type = MULTIPART_FORMDATA;
        }

        m_mpp_state = 1;
        m_mpp->m_last_header_name.assign("");
    } else {  /* Header line. */
        if (isspace(m_buf[0])) {
            std::string header_value;
            char *data;
            std::string new_value;

            /* header folding, add data to the header we are building */
            m_flag_header_folding = 1;

            /* RFC-2557 states header folding is SP / HTAB, but PHP and
             * perhaps others will take any whitespace.  So, we accept,
             * but with a flag set.
             */
            if ((m_buf[0] != '\t') && (m_buf[0] != ' ')) {
                m_flag_invalid_header_folding = 1;
            }

            if (m_mpp->m_last_header_name.empty()) {
                /* we are not building a header at this moment */
                ms_dbg_a(m_transaction, 1,
                    "Multipart: Invalid part header (folding error).");

                error->assign("Multipart: Invalid part header " \
                    "(folding error).");
                return false;
            }

            /* locate the beginning of data */
            data = m_buf;
            while (isspace(*data)) {
                /* Flag invalid header folding if an invalid RFC-2557
                 * character is used anywhere in the folding prefix.
                 */
                if ((*data != '\t') && (*data != ' ')) {
                    m_flag_invalid_header_folding = 1;
                }
                data++;
                i++;
            }

            new_value = std::string(data);
            utils::string::chomp(&new_value);

            /* update the header value in the table */
            header_value = m_mpp->m_headers.at(
                m_mpp->m_last_header_name).second;
            new_value = header_value + " " +  new_value;
            m_mpp->m_headers.at(m_mpp->m_last_header_name).second = new_value;

            ms_dbg_a(m_transaction, 9,
                "Multipart: Continued folder header \"" \
                + m_mpp->m_last_header_name + "\" with \"" \
                + std::string(data) + "\"");

            if (new_value.size() > MULTIPART_BUF_SIZE) {
                ms_dbg_a(m_transaction, 1, "Multipart: Part header too long.");

                error->assign("Multipart: Part header too long.");
                return false;
            }
        } else {
            char *data;
            std::string header_value;
            std::string header_name;
            /* new header */

            data = m_buf;
            while ((*data != ':') && (*data != '\0')) {
                data++;
                i++;
            }
            if (*data == '\0') {
                ms_dbg_a(m_transaction, 1,
                    "Multipart: Invalid part header (colon missing): " \
                    + std::string(m_buf));

                error->assign("Multipart: Invalid part header " \
                    "(colon missing): " + std::string(m_buf));
                return false;
            }

            /* extract header name */
            header_name = std::string(m_buf, data - m_buf);
            if (data == m_buf) {
                ms_dbg_a(m_transaction, 1,
                    "Multipart: Invalid part header " \
                    "(header name missing).");

                error->assign("Multipart: Invalid part header " \
                    "(header name missing).");
                 return false;
            }

            /* extract the value value */
            data++;
            i++;
            while ((*data == '\t') || (*data == ' ')) {
                data++;
                i++;
            }
            header_value = std::string(data);
            utils::string::chomp(&header_value);

            /* error if the name already exists */
            if (m_mpp->m_headers.count(header_name) > 0) {
                ms_dbg_a(m_transaction, 1,
                    "Multipart: Duplicate part header: " \
                    + header_name + ".");

                return false;
            }

            m_mpp->m_last_header_name.assign(header_name);


            m_mpp->m_headers.emplace(
                std::string(header_name), std::make_pair(offset - len + i,
                    std::string(header_value)));

            ms_dbg_a(m_transaction, 9,
                "Multipart: Added part header \"" + header_name \
                + "\" \"" + header_value + "\".");
        }
    }

    return true;
}


int Multipart::process_boundary(int last_part) {
    /* if there was a part being built finish it */
    if (m_mpp != NULL) {
        /* close the temp file */
        if ((m_mpp->m_type == MULTIPART_FILE)
            && (!m_mpp->m_tmp_file_name.empty())
            && (m_mpp->m_tmp_file_fd != 0)) {
            close(m_mpp->m_tmp_file_fd);
            m_mpp->m_tmp_file_fd = -1;
        }

        if (m_mpp->m_type != MULTIPART_FILE) {
            /* now construct a single string out of the parts */
            for (const auto &i : m_mpp->m_value_parts) {
                if (m_mpp->m_valueOffset == 0) {
                    m_mpp->m_valueOffset = i.second;
                }
                m_mpp->m_value.append(i.first);
            }
        }

        if (m_mpp->m_name.empty() == false) {
            /* add the part to the list of parts */
            m_parts.push_back(m_mpp);

            if (m_mpp->m_type == MULTIPART_FILE) {
                ms_dbg_a(m_transaction, 9,
                    "Multipart: Added file part to the list: name \"" \
                    + m_mpp->m_name + "\" "
                    "file name \"" + m_mpp->m_filename + "\" (offset " \
                    + std::to_string(m_mpp->m_offset) +
                    ", length " + std::to_string(m_mpp->m_length) + ")");
            } else {
                ms_dbg_a(m_transaction, 9,
                    "Multipart: Added part to the list: name \"" \
                    + m_mpp->m_name + "\" "
                    "(offset " + std::to_string(m_mpp->m_offset) \
                    + ", length " + std::to_string(m_mpp->m_length) + ")");
            }
        } else {
            m_flag_invalid_part = true;
            ms_dbg_a(m_transaction, 3,
                "Multipart: Skipping invalid part (part name missing): "
                "(offset " + std::to_string(m_mpp->m_offset) + ", length "
                + std::to_string(m_mpp->m_length) + ")");

            delete m_mpp;
        }

        m_mpp = NULL;
    }

    if (last_part == 0) {
        /* start building a new part */
        m_mpp = new MultipartPart();

        m_mpp_state = 0;

        m_reserve[0] = 0;
        m_reserve[1] = 0;
        m_reserve[2] = 0;
        m_reserve[3] = 0;
    }

    return 1;
}


/**
 * Finalize multipart processing. This method is invoked at the end, when it
 * is clear that there is no more data to be processed.
 */
int Multipart::multipart_complete(std::string *error) {
    m_transaction->m_variableMultipartUnmatchedBoundary.set(
        std::to_string(m_flag_unmatched_boundary),
        m_transaction->m_variableOffset);

    m_transaction->m_variableMultipartDataBefore.set(
        std::to_string(m_flag_data_before),
        m_transaction->m_variableOffset);
    if (m_flag_data_before) {
        ms_dbg_a(m_transaction, 4,
            "Multipart: Warning: seen data before first boundary.");
    }

    m_transaction->m_variableMultipartDataAfter.set(
        std::to_string(m_flag_data_after),
        m_transaction->m_variableOffset);
    if (m_flag_data_after) {
        ms_dbg_a(m_transaction, 4,
            "Multipart: Warning: seen data after last boundary.");
    }

    m_transaction->m_variableMultipartBoundaryQuoted.set(
        std::to_string(m_flag_boundary_quoted),
        m_transaction->m_variableOffset);
    if (m_flag_boundary_quoted) {
        ms_dbg_a(m_transaction, 4,
            "Multipart: Warning: boundary was quoted.");
    }

    m_transaction->m_variableMultipartBoundaryWhiteSpace.set(
        std::to_string(m_flag_boundary_whitespace),
        m_transaction->m_variableOffset);
    if (m_flag_boundary_whitespace) {
        ms_dbg_a(m_transaction, 4,
            "Multipart: Warning: boundary whitespace in C-T header.");
    }

    m_transaction->m_variableMultipartHeaderFolding.set(
        std::to_string(m_flag_header_folding),
        m_transaction->m_variableOffset);
    if (m_flag_header_folding) {
        ms_dbg_a(m_transaction, 4,
            "Multipart: Warning: header folding used.");
    }
    m_transaction->m_variableMultipartLFLine.set(
        std::to_string(m_flag_lf_line),
        m_transaction->m_variableOffset);
    m_transaction->m_variableMultipartCrlfLFLines.set(
        std::to_string(m_flag_crlf_line && m_flag_lf_line),
        m_transaction->m_variableOffset);
    if (m_flag_crlf_line && m_flag_lf_line) {
        ms_dbg_a(m_transaction, 4,
            "Multipart: Warning: mixed line endings used (CRLF/LF).");
    } else if (m_flag_lf_line) {
        ms_dbg_a(m_transaction, 4,
            "Multipart: Warning: incorrect line endings used (LF).");
    }
    m_transaction->m_variableMultipartMissingSemicolon.set(
        std::to_string(m_flag_missing_semicolon),
        m_transaction->m_variableOffset);
    if (m_flag_missing_semicolon) {
        ms_dbg_a(m_transaction, 4,
            "Multipart: Warning: missing semicolon in C-T header.");
    }

    m_transaction->m_variableMultipartInvalidQuoting.set(
        std::to_string(m_flag_invalid_quoting),
        m_transaction->m_variableOffset);
    if (m_flag_invalid_quoting) {
        ms_dbg_a(m_transaction, 4,
            "Multipart: Warning: invalid quoting used.");
    }
    m_transaction->m_variableMultipartInvalidPart.set(
        std::to_string(m_flag_invalid_part),
        m_transaction->m_variableOffset);
    if (m_flag_invalid_part) {
        ms_dbg_a(m_transaction, 4,
            "Multipart: Warning: invalid part parsing.");
    }

    m_transaction->m_variableMultipartInvalidHeaderFolding.set(
        std::to_string(m_flag_invalid_header_folding),
        m_transaction->m_variableOffset);
    if (m_flag_invalid_header_folding) {
        ms_dbg_a(m_transaction, 4,
            "Multipart: Warning: invalid header folding used.");
    }

    m_transaction->m_variableMultipartStrictError.set(
        std::to_string(m_flag_error || m_flag_boundary_quoted != 0
        || m_flag_boundary_whitespace != 0 || m_flag_data_before != 0
        || m_flag_data_after != 0 || m_flag_header_folding != 0
        || m_flag_lf_line != 0 || m_flag_missing_semicolon != 0
        || m_flag_invalid_quoting != 0 || m_flag_invalid_part != 0
        || m_flag_invalid_header_folding != 0
        || m_flag_file_limit_exceeded != 0), m_transaction->m_variableOffset);


    if ((m_seen_data != 0) && (m_is_complete == 0)) {
        if (m_boundary_count > 0) {
            /* Check if we have the final boundary (that we haven't
             * processed yet) in the buffer.
             */
            if (m_buf_contains_line) {
                if (((unsigned int)(MULTIPART_BUF_SIZE - m_bufleft)
                        == (4 + m_boundary.size()))
                    && (*(m_buf) == '-')
                    && (*(m_buf + 1) == '-')
                    && (strncmp(m_buf + 2, m_boundary.c_str(),
                        m_boundary.size()) == 0)
                    && (*(m_buf + 2 + m_boundary.size()) == '-')
                    && (*(m_buf + 2 + m_boundary.size() + 1) == '-')) {
                    /* Looks like the final boundary - process it. */
                    if (process_boundary(1 /* final */) < 0) {
                        m_flag_error = 1;
                        return -1;
                    }

                    /* The payload is complete after all. */
                    m_is_complete = 1;
                }
            }

            if (m_is_complete == 0) {
                ms_dbg_a(m_transaction, 1,
                    "Multipart: Final boundary missing.");
                error->assign("Multipart: Final boundary missing.");
                return false;
            }
        } else {
            ms_dbg_a(m_transaction, 1,
                "Multipart: No boundaries found in payload.");
            error->assign("Multipart: No boundaries found in payload.");
            return false;
        }
    }

    int file_combined_size = 0;
    for (MultipartPart *m : m_parts) {
        // FIXME: duplicate code, see transaction.
        //        we need a helper function for this.
        if (m->m_name.empty()) {
            continue;
        }
        size_t offset = m_transaction->m_variableOffset + 1;

        if (m->m_type == MULTIPART_FILE) {
            std::string tmp_name;
            std::string name;
            if (!m->m_tmp_file_name.empty()) {
                tmp_name.assign(m->m_tmp_file_name);
            }
            if (!m->m_filename.empty()) {
                name.assign(m->m_filename);
            }

            m_transaction->m_variableFiles.set(m->m_filename,
                m->m_filename, m->m_filenameOffset);

            m_transaction->m_variableFilesNames.set(m->m_name,
                m->m_name, m->m_nameOffset);

            m_transaction->m_variableFilesSizes.set(m->m_name,
                std::to_string(m->m_tmp_file_size.first),
                m->m_tmp_file_size.second,
                m->m_tmp_file_size.first);

            m_transaction->m_variableFilesTmpContent.set(m->m_filename,
               m->m_value, m->m_valueOffset);

            m_transaction->m_variableFilesTmpNames.set(m->m_tmp_file_name,
               m->m_tmp_file_name, m->m_filenameOffset);

            file_combined_size = file_combined_size + m->m_tmp_file_size.first;

            m_transaction->m_variableFilesCombinedSize.set(
               std::to_string(file_combined_size),
               m->m_tmp_file_size.second, m->m_tmp_file_size.first);
        } else {
            ms_dbg_a(m_transaction, 4,
                "Adding request argument (BODY): name \"" +
                m->m_name + "\", value \"" + m->m_value + "\"");
            m_transaction->m_variableArgs.set(m->m_name, m->m_value,
                offset + m->m_valueOffset);
            m_transaction->m_variableArgsPost.set(m->m_name, m->m_value,
               offset + m->m_valueOffset);
        }
#if 0
        if (m_transaction->m_namesArgs->empty()) {
            m_transaction->m_namesArgs->assign(key);
        } else {
            m_transaction->m_namesArgs->assign(*m_namesArgs + " " + key);
        }
        if (m_transaction->m_namesArgsPost->empty()) {
            m_transaction->m_namesArgsPost->assign(key);
        } else {
            m_transaction->m_namesArgsPost->assign(
                *m_namesArgsPost + " " + key);
        }

        m_transaction->m_ARGScombinedSize = \
            m_transaction->m_ARGScombinedSize + \
            m->m_name.length() + m->m_value.length();
        m_transaction->m_ARGScombinedSizeStr->assign(
            std::to_string(m_transaction->->m_ARGScombinedSize));
#endif
    }


    return true;
}


int Multipart::count_boundary_params(const std::string& str_header_value) {
    std::string lower = utils::string::tolower(str_header_value);
    const char *header_value = lower.c_str();
    char *duplicate = NULL;
    char *s = NULL;
    int count = 0;

    if (header_value == NULL) {
        return -1;
    }

    duplicate = strdup(header_value);
    if (duplicate == NULL) {
        return -1;
    }

    s = duplicate;
    while ((s = strstr(s, "boundary")) != NULL) {
        s += 8;

        if (strchr(s, '=') != NULL) {
            count++;
        }
    }

    free(duplicate);
    return count;
}


bool Multipart::init(std::string *error) {
    m_bufleft = MULTIPART_BUF_SIZE;
    m_bufptr = m_buf;
    m_buf_contains_line = true;
    m_mpp = NULL;
    const char *m_boundary_tmp = NULL;

    if (m_header.empty()) {
        m_flag_error = true;
        ms_dbg_a(m_transaction, 4,
            "Multipart: Content-Type header not available.");
        error->assign("Multipart: Content-Type header not available.");
        return false;
    }

    if (m_header.size() > 1024) {
        m_flag_error = 1;
        ms_dbg_a(m_transaction, 4,
            "Multipart: Invalid boundary in C-T (length).");
        error->assign("Multipart: Invalid boundary in C-T (length).");
        return false;
    }

    if (strncasecmp(m_header.c_str(), "multipart/form-data", 19) != 0) {
        m_flag_error = 1;
        ms_dbg_a(m_transaction, 4, "Multipart: Invalid MIME type.");
        error->assign("Multipart: Invalid MIME type.");
        return false;
    }

    /* Count how many times the word "boundary" appears in the C-T header. */
    if (count_boundary_params(m_header) > 1) {
        m_flag_error = 1;
        ms_dbg_a(m_transaction, 4,
            "Multipart: Multiple boundary parameters in C-T.");
        error->assign("Multipart: Multiple boundary parameters in C-T.");
        return false;
    }

    m_boundary_tmp = strstr(m_header.c_str(), "boundary");
    if (m_boundary_tmp) {
        m_boundary = std::string(m_boundary_tmp);
        const char *p = NULL;
        const char *b = NULL;
        int seen_semicolon = 0;
        int len = 0;

        /* Check for extra characters before the boundary. */
        for (p = m_header.c_str() + 19;
            p < m_boundary_tmp; p++) {
            if (!isspace(*p)) {
                if ((seen_semicolon == 0) && (*p == ';')) {
                    seen_semicolon = 1; /* It is OK to have one semicolon. */
                } else {
                    m_flag_error = 1;
                    ms_dbg_a(m_transaction, 4,
                        "Multipart: Invalid boundary in C-T " \
                        "(malformed).");
                    error->assign("Multipart: Invalid boundary in C-T " \
                        "(malformed).");
                    return false;
                }
            }
        }

        /* Have we seen the semicolon in the header? */
        if (seen_semicolon == 0) {
            m_flag_missing_semicolon = 1;
        }

        b = strchr(m_boundary_tmp + 8, '=');
        if (b == NULL) {
            m_flag_error = 1;
            ms_dbg_a(m_transaction, 4,
                "Multipart: Invalid boundary in C-T (malformed).");
            error->assign("Multipart: Invalid boundary in C-T (malformed).");
            return false;
        }

        /* Check parameter name ends well. */
        if (b != (m_boundary.c_str() + 8)) {
            /* Check all characters between the end of the boundary
             * and the = character.
             */
            for (p = m_boundary_tmp + 8; p < b; p++) {
                if (isspace(*p)) {
                    /* Flag for whitespace after parameter name. */
                    m_flag_boundary_whitespace = 1;
                } else {
                    m_flag_error = 1;
                    ms_dbg_a(m_transaction, 4,
                        "Multipart: Invalid boundary in C-T " \
                        "(parameter name).");
                    error->assign("Multipart: Invalid boundary in C-T " \
                        "(parameter name).");
                    return false;
                }
            }
        }

        b++; /* Go over the = character. */
        len = strlen(b);

        /* Flag for whitespace before parameter value. */
        if (isspace(*b)) {
            m_flag_boundary_whitespace = 1;
        }

        /* Is the boundary quoted? */
        if ((len >= 2) && (*b == '"') && (*(b + len - 1) == '"')) {
            /* Quoted. */
            m_boundary.assign(std::string(b + 1, len - 2));
            if (m_boundary.empty()) {
                return -1;
            }
            m_flag_boundary_quoted = 1;
        } else {
            /* Not quoted. */

            /* Test for partial quoting. */
            if ((*b == '"')
                || ((len >= 2) && (*(b + len - 1) == '"'))) {
                m_flag_error = 1;
                ms_dbg_a(m_transaction, 4,
                    "Multipart: Invalid boundary in C-T (quote).");
                error->assign("Multipart: Invalid boundary in C-T (quote).");
                return false;
            }

            m_boundary.assign(b);
            if (m_boundary.empty()) {
                return false;
            }

            m_flag_boundary_quoted = 0;
        }

        /* Case-insensitive test for the string "boundary" in the boundary. */
        if (count_boundary_params(m_boundary) != 0) {
            m_flag_error = 1;
            ms_dbg_a(m_transaction, 4,
                "Multipart: Invalid boundary in C-T (content).");
            error->assign("Multipart: Invalid boundary in C-T (content).");
            return false;
        }

        /* Validate the characters used in the boundary. */
        if (boundary_characters_valid(m_boundary.c_str()) != 1) {
            m_flag_error = 1;
            ms_dbg_a(m_transaction, 4,
                "Multipart: Invalid boundary in C-T (characters).");
            error->assign("Multipart: Invalid boundary in C-T (characters).");
            return false;
        }

        ms_dbg_a(m_transaction, 9, "Multipart: Boundary" +
            (m_flag_boundary_quoted ?
                std::string(" (quoted)") : std::string("")) +
            std::string(": ") + m_boundary);

        if (m_boundary.size() == 0) {
            m_flag_error = 1;
            ms_dbg_a(m_transaction, 4,
                "Multipart: Invalid boundary in C-T (empty).");
            error->assign("Multipart: Invalid boundary in C-T (empty).");
            return false;
        }
    } else { /* Could not find boundary in the C-T header. */
        m_flag_error = 1;

        /* Test for case-insensitive boundary. Allowed by the RFC but
         * highly unusual. */
        if (count_boundary_params(m_header) > 0) {
            ms_dbg_a(m_transaction, 4,
                "Multipart: Invalid boundary in C-T (case sensitivity).");
            error->assign("Multipart: Invalid boundary in C-T " \
                "(case sensitivity).");
            return false;
        }

        ms_dbg_a(m_transaction, 4, "Multipart: Boundary not found in C-T.");
        error->assign("Multipart: Boundary not found in C-T.");
        return false;
    }

    return 1;
}


/*
 * Assuming that all data is on data. We are not processing chunks.
 *
 */
bool Multipart::process(const std::string& data, std::string *error,
    int offset) {
    const char *inptr = data.c_str();
    unsigned int inleft = data.size();
    size_t z = 0;

    if (data.size() == 0) return true;
    m_seen_data = true;

    if (m_is_complete) {
        m_flag_data_before = true;

        ms_dbg_a(m_transaction, 4,
            "Multipart: Ignoring data after last boundary (received " \
            + std::to_string(data.size()) + " bytes)");

        return true;
    }

    if (m_bufleft == 0) {
        m_flag_error = 1;
        ms_dbg_a(m_transaction, 4,
            "Multipart: Internal error in process_chunk: no space left " \
            "in the buffer");
        return false;
    }

    /* here we loop through the available data, one byte at a time */
    while (inleft > 0) {
        char c = *inptr;
        int process_buffer = 0;

        z++;

        if ((c == '\r') && (m_bufleft == 1)) {
            /* we don't want to take \r as the last byte in the buffer */
            process_buffer = 1;
        } else {
            inptr++;
            inleft = inleft - 1;

            *(m_bufptr) = c;
            m_bufptr++;
            m_bufleft--;
        }

        /* until we either reach the end of the line
         * or the end of our internal buffer
         */
        if ((c == '\n') || (m_bufleft == 0) || (process_buffer)) {
            int processed_as_boundary = 0;

            *(m_bufptr) = 0;

            /* Do we have something that looks like a boundary? */
            if (m_buf_contains_line && (strlen(m_buf) > 3) && (*(m_buf) == '-')
                && (*(m_buf + 1) == '-')) {
                /* Does it match our boundary? */
                if ((strlen(m_buf) >= m_boundary.size() + 2)
                    && (strncmp(m_buf + 2, m_boundary.c_str(),
                        m_boundary.size()) == 0)) {
                    char *boundary_end = m_buf + 2 + m_boundary.size();
                    /* if it match, AND there was a matched boundary at least,
                       set the m_flag_unmatched_boundary flag to 2
                       this indicates that there were an opened boundary, which
                       matches the reference, and here is the final boundary.
                       The flag will differ from 0, so the previous rules ("!@eq 0")
                       will catch all "errors", without any modification, but we can
                       use the new, permission mode with "@eq 1"
                    */
                    if (m_boundary_count > 0) {
                        m_flag_unmatched_boundary = 2;
                    }
                    int is_final = 0;

                    /* Is this the final boundary? */
                    if ((*boundary_end == '-')
                        && (*(boundary_end + 1)== '-')) {
                        is_final = 1;
                        boundary_end += 2;

                        if (m_is_complete != 0) {
                            m_flag_error = 1;
                            ms_dbg_a(m_transaction, 4,
                                "Multipart: Invalid boundary " \
                                "(final duplicate).");

                            error->assign("Multipart: Invalid boundary " \
                                "(final duplicate).");
                            return false;
                        }
                    }

                    /* Allow for CRLF and LF line endings. */
                    if (((*boundary_end == '\r')
                        && (*(boundary_end + 1) == '\n')
                        && (*(boundary_end + 2) == '\0'))
                        || ((*boundary_end == '\n')
                        && (*(boundary_end + 1) == '\0'))) {
                        if (*boundary_end == '\n') {
                            m_flag_lf_line = 1;
                        } else {
                            m_flag_crlf_line = 1;
                        }

                        if (process_boundary((is_final ? 1 : 0)) < 0) {
                            m_flag_error = true;
                            return false;
                        }

                        if (is_final) {
                            m_is_complete = 1;
                        }

                        processed_as_boundary = 1;
                        m_boundary_count++;
                    } else {
                        /* error */
                        m_flag_error = 1;
                        ms_dbg_a(m_transaction, 4,
                            "Multipart: Invalid boundary: " \
                            + std::string(m_buf));
                        error->assign("Multipart: Invalid boundary: " \
                            + std::string(m_buf));
                        return false;
                    }
                } else { /* It looks like a boundary but */
                         /* we couldn't match it. */
                    char *p = NULL;

                    /* Check if an attempt to use quotes around the
                     * boundary was made. */
                    if ((m_flag_boundary_quoted)
                        && (strlen(m_buf) >= m_boundary.size() + 3)
                        && (*(m_buf + 2) == '"')
                        && (strncmp(m_buf + 3, m_boundary.c_str(),
                            m_boundary.size()) == 0)) {
                        m_flag_error = 1;
                        ms_dbg_a(m_transaction, 4,
                            "Multipart: Invalid boundary (quotes).");
                        error->assign("Multipart: Invalid boundary (quotes).");
                        return false;
                    }

                    /* Check the beginning of the boundary for whitespace. */
                    p = m_buf + 2;
                    while (isspace(*p)) {
                        p++;
                    }

                    if ((p != m_buf + 2)
                        && (strncmp(p, m_boundary.c_str(),
                            m_boundary.size()) == 0)) {
                        /* Found whitespace in front of a boundary. */
                        m_flag_error = 1;
                        ms_dbg_a(m_transaction, 4,
                            "Multipart: Invalid boundary (whitespace).");
                        error->assign("Multipart: Invalid boundary " \
                            "(whitespace).");
                        return false;
                    }

                    m_flag_unmatched_boundary = 1;
                }
            } else { /* We do not think the buffer contains a boundary. */
                /* Look into the buffer to see if there's anything
                 * there that resembles a boundary.
                 */
                if (m_buf_contains_line) {
                    int i, len = (MULTIPART_BUF_SIZE - m_bufleft);
                    char *p = m_buf;

                    for (i = 0; i < len; i++) {
                        if ((p[i] == '-') && (i + 1 < len)
                            && (p[i + 1] == '-')) {
                            if (strncmp(p + i + 2, m_boundary.c_str(),
                                m_boundary.size()) == 0) {
                                m_flag_unmatched_boundary = 1;
                                break;
                            }
                        }
                    }
                }
            }

            /* Process as data if it was not a boundary. */
            if (processed_as_boundary == 0) {
                if (m_mpp == NULL) {
                    m_flag_data_before = 1;
                    ms_dbg_a(m_transaction, 4,
                        "Multipart: Ignoring data before first " \
                        "boundary.");
                } else {
                    if (m_mpp_state == 0) {
                        if ((m_bufleft == 0) || (process_buffer)) {
                            /* part header lines must be shorter than
                             * MULTIPART_BUF_SIZE bytes
                             */
                            m_flag_error = 1;
                            ms_dbg_a(m_transaction, 4,
                                "Multipart: Part header line over " \
                                + std::to_string(MULTIPART_BUF_SIZE) \
                                + " bytes long");
                            error->assign("Multipart: Part header line over " \
                                + std::to_string(MULTIPART_BUF_SIZE) \
                                + " bytes long");
                            return false;
                        }

                        if (process_part_header(error, offset + z) < 0) {
                            m_flag_error = 1;
                            return false;
                        }

                    } else {
                        if (process_part_data(error, offset + z) < 0) {
                            m_flag_error = 1;
                            return false;
                        }
                    }
                }
            }

            /* Update the offset of the data we are about
             * to process. This is to allow us to know the
             * offsets of individual files and variables.
             */
            m_buf_offset += (MULTIPART_BUF_SIZE - m_bufleft);

            /* reset the pointer to the beginning of the buffer
             * and continue to accept input data
             */
            m_bufptr = m_buf;
            m_bufleft = MULTIPART_BUF_SIZE;
            m_buf_contains_line = (c == 0x0a) ? 1 : 0;
        }

        if ((m_is_complete) && (inleft != 0)) {
            m_flag_data_after = 1;
            ms_dbg_a(m_transaction, 4,
                "Multipart: Ignoring data after last boundary (" \
                + std::to_string(inleft) + "bytes left)");
            return true;
        }
    }

    return true;
}


}  // namespace RequestBodyProcessor
}  // namespace modsecurity
