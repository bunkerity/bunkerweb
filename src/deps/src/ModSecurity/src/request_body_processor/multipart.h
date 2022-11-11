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

#include <string>
#include <iostream>
#include <list>
#include <unordered_map>
#include <utility>

#ifndef SRC_REQUEST_BODY_PROCESSOR_MULTIPART_H_
#define SRC_REQUEST_BODY_PROCESSOR_MULTIPART_H_

#include "modsecurity/transaction.h"

namespace modsecurity {
namespace RequestBodyProcessor {

#define MULTIPART_BUF_SIZE 4096
#define MULTIPART_FORMDATA 1
#define MULTIPART_FILE 2


struct MyHash {
    size_t operator()(const std::string& Keyval) const {
        size_t h = 0;
        std::for_each(Keyval.begin(), Keyval.end(), [&](char c) {
            h += tolower(c);
        });
        return h;
    }
};


struct MyEqual {
    bool operator()(const std::string& Left, const std::string& Right) const {
        return Left.size() == Right.size()
             && std::equal(Left.begin(), Left.end(), Right.begin(),
            [](char a, char b) {
                return tolower(a) == tolower(b);
            });
    }
};


class MultipartPart {
 public:
    MultipartPart()
     : m_type(MULTIPART_FORMDATA),
     m_tmp_file_fd(0),
     m_offset(0),
     m_filenameOffset(0),
     m_nameOffset(0),
     m_valueOffset(0),
     m_length(0) {
         m_tmp_file_size.first = 0;
         m_tmp_file_size.second = 0;
    }

    ~MultipartPart() {
        m_headers.clear();
        m_value_parts.clear();
    }

    /* part type, can be MULTIPART_FORMDATA or MULTIPART_FILE */
    int m_type;

    /* the name */
    std::string m_name;
    size_t m_nameOffset;

    /* variables only, variable value */
    std::string m_value;
    size_t m_valueOffset;

    std::list<std::pair<std::string, int>> m_value_parts;

    /* files only, the content type (where available) */
    /* std::string m_content_type; */

    /* files only, the name of the temporary file holding data */
    std::string m_tmp_file_name;
    int m_tmp_file_fd;
    std::pair<size_t, size_t> m_tmp_file_size;

    /* files only, filename as supplied by the browser */
    std::string m_filename;
    size_t m_filenameOffset;

    std::string m_last_header_name;
    std::unordered_map<std::string, std::pair<size_t, std::string>,
        MyHash, MyEqual> m_headers;

    unsigned int m_offset;
    unsigned int m_length;
};


class Multipart {
 public:
    Multipart(std::string header, Transaction *transaction);
    ~Multipart();

    bool init(std::string *err);

    int boundary_characters_valid(const char *boundary);
    int count_boundary_params(const std::string& str_header_value);
    int is_token_char(unsigned char c);
    int multipart_complete(std::string *err);

    int parse_content_disposition(const char *c_d_value, int offset);
    bool process(const std::string& data, std::string *err, int offset);
    int process_boundary(int last_part);
    int process_part_header(std::string *error, int offset);
    int process_part_data(std::string *error, size_t offset);

    int tmp_file_name(std::string *filename) const;

    void validate_quotes(const char *data);

    size_t m_reqbody_no_files_length;
    std::list<MultipartPart *> m_parts;

    /* Number of parts that are files */
    int m_nfiles;

    /* mime boundary used to detect when
     * parts end and begin
     */
    std::string m_boundary;
    int  m_boundary_count;

    /* internal buffer and other variables
     * used while parsing
     */
    char m_buf[MULTIPART_BUF_SIZE + 2];
    int m_buf_contains_line;
    char *m_bufptr;
    int m_bufleft;

    unsigned int m_buf_offset;

    /* pointer that keeps track of a part while
     * it is being built
     */
    MultipartPart *m_mpp;


    /* part parsing state; 0 means we are reading
     * headers, 1 means we are collecting data
     */
    int m_mpp_state;

    /* because of the way this parsing algorithm
     * works we hold back the last two bytes of
     * each data chunk so that we can discard it
     * later if the next data chunk proves to be
     * a boundary; the first byte is an indicator
     * 0 - no content, 1 - two data bytes available
     */
    char m_reserve[4];

    int m_seen_data;
    int m_is_complete;

    int m_flag_error;
    int m_flag_data_before;
    int m_flag_data_after;
    int m_flag_header_folding;
    int m_flag_boundary_quoted;
    int m_flag_lf_line;
    int m_flag_crlf_line;
    int m_flag_unmatched_boundary;
    int m_flag_boundary_whitespace;
    int m_flag_missing_semicolon;
    int m_flag_invalid_quoting;
    int m_flag_invalid_part;
    int m_flag_invalid_header_folding;
    int m_flag_file_limit_exceeded;

 private:
    std::string m_header;
    Transaction *m_transaction;
};


}  // namespace RequestBodyProcessor
}  // namespace modsecurity

#endif  // SRC_REQUEST_BODY_PROCESSOR_MULTIPART_H_
