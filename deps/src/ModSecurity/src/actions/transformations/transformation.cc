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

#include "src/actions/transformations/transformation.h"

#include <cstring>

#include <iostream>
#include <string>

#include "modsecurity/transaction.h"
#include "modsecurity/actions/action.h"
#include "src/actions/transformations/base64_decode_ext.h"
#include "src/actions/transformations/base64_decode.h"
#include "src/actions/transformations/base64_encode.h"
#include "src/actions/transformations/cmd_line.h"
#include "src/actions/transformations/compress_whitespace.h"
#include "src/actions/transformations/css_decode.h"
#include "src/actions/transformations/escape_seq_decode.h"
#include "src/actions/transformations/hex_decode.h"
#include "src/actions/transformations/hex_encode.h"
#include "src/actions/transformations/html_entity_decode.h"
#include "src/actions/transformations/js_decode.h"
#include "src/actions/transformations/length.h"
#include "src/actions/transformations/lower_case.h"
#include "src/actions/transformations/md5.h"
#include "src/actions/transformations/none.h"
#include "src/actions/transformations/normalise_path.h"
#include "src/actions/transformations/normalise_path_win.h"
#include "src/actions/transformations/parity_even_7bit.h"
#include "src/actions/transformations/parity_odd_7bit.h"
#include "src/actions/transformations/parity_zero_7bit.h"
#include "src/actions/transformations/remove_comments_char.h"
#include "src/actions/transformations/remove_comments.h"
#include "src/actions/transformations/remove_nulls.h"
#include "src/actions/transformations/remove_whitespace.h"
#include "src/actions/transformations/replace_comments.h"
#include "src/actions/transformations/replace_nulls.h"
#include "src/actions/transformations/sha1.h"
#include "src/actions/transformations/sql_hex_decode.h"
#include "src/actions/transformations/trim.h"
#include "src/actions/transformations/trim_left.h"
#include "src/actions/transformations/trim_right.h"
#include "src/actions/transformations/upper_case.h"
#include "src/actions/transformations/url_decode.h"
#include "src/actions/transformations/url_decode_uni.h"
#include "src/actions/transformations/url_encode.h"
#include "src/actions/transformations/utf8_to_unicode.h"


#define IF_MATCH(b) \
    if (a.compare(2, std::strlen(#b), #b) == 0)


namespace modsecurity {
namespace actions {
namespace transformations {


std::string Transformation::evaluate(std::string value,
    Transaction *transaction) {
    return value;
}

Transformation* Transformation::instantiate(std::string a) {
    IF_MATCH(base64DecodeExt) { return new Base64DecodeExt(a); }
    IF_MATCH(base64Decode) { return new Base64Decode(a); }
    IF_MATCH(base64Encode) { return new Base64Encode(a); }
    IF_MATCH(cmd_line) { return new CmdLine(a); }
    IF_MATCH(compress_whitespace) { return new CompressWhitespace(a); }
    IF_MATCH(cssDecode) { return new CssDecode(a); }
    IF_MATCH(escapeSeqDecode) { return new EscapeSeqDecode(a); }
    IF_MATCH(hexDecode) { return new HexDecode(a); }
    IF_MATCH(hexEncode) { return new HexEncode(a); }
    IF_MATCH(htmlEntityDecode) { return new HtmlEntityDecode(a); }
    IF_MATCH(jsDecode) { return new JsDecode(a); }
    IF_MATCH(length) { return new Length(a); }
    IF_MATCH(lowercase) { return new LowerCase(a); }
    IF_MATCH(md5) { return new Md5(a); }
    IF_MATCH(none) { return new None(a); }
    IF_MATCH(normalizePathWin) { return new NormalisePathWin(a); }
    IF_MATCH(normalisePathWin) { return new NormalisePathWin(a); }
    IF_MATCH(normalizePath) { return new NormalisePath(a); }
    IF_MATCH(normalisePath) { return new NormalisePath(a); }
    IF_MATCH(parityEven7bit) { return new ParityEven7bit(a); }
    IF_MATCH(parityOdd7bit) { return new ParityOdd7bit(a); }
    IF_MATCH(parityZero7bit) { return new ParityZero7bit(a); }
    IF_MATCH(removeCommentsChar) { return new RemoveCommentsChar(a); }
    IF_MATCH(removeComments) { return new RemoveComments(a); }
    IF_MATCH(removeNulls) { return new RemoveNulls(a); }
    IF_MATCH(removeWhitespace) { return new RemoveWhitespace(a); }
    IF_MATCH(compressWhitespace) { return new CompressWhitespace(a); }
    IF_MATCH(replaceComments) { return new ReplaceComments(a); }
    IF_MATCH(replaceNulls) { return new ReplaceNulls(a); }
    IF_MATCH(sha1) { return new Sha1(a); }
    IF_MATCH(sqlHexDecode) { return new SqlHexDecode(a); }
    IF_MATCH(transformation) { return new Transformation(a); }
    IF_MATCH(trimLeft) { return new TrimLeft(a); }
    IF_MATCH(trimRight) { return new TrimRight(a); }
    IF_MATCH(trim) { return new Trim(a); }
    IF_MATCH(uppercase) { return new UpperCase(a); }
    IF_MATCH(urlDecodeUni) { return new UrlDecodeUni(a); }
    IF_MATCH(urlDecode) { return new UrlDecode(a); }
    IF_MATCH(urlEncode) { return new UrlEncode(a); }
    IF_MATCH(utf8toUnicode) { return new Utf8ToUnicode(a); }

    return new Transformation(a);
}

}  // namespace transformations
}  // namespace actions
}  // namespace modsecurity
