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

#include "transformation.h"

#include <cstring>
#include <iostream>
#include <string>

#include "modsecurity/transaction.h"
#include "modsecurity/actions/action.h"

#include "base64_decode_ext.h"
#include "base64_decode.h"
#include "base64_encode.h"
#include "cmd_line.h"
#include "compress_whitespace.h"
#include "css_decode.h"
#include "escape_seq_decode.h"
#include "hex_decode.h"
#include "hex_encode.h"
#include "html_entity_decode.h"
#include "js_decode.h"
#include "length.h"
#include "lower_case.h"
#include "md5.h"
#include "none.h"
#include "normalise_path.h"
#include "normalise_path_win.h"
#include "parity_even_7bit.h"
#include "parity_odd_7bit.h"
#include "parity_zero_7bit.h"
#include "remove_comments_char.h"
#include "remove_comments.h"
#include "remove_nulls.h"
#include "remove_whitespace.h"
#include "replace_comments.h"
#include "replace_nulls.h"
#include "sha1.h"
#include "sql_hex_decode.h"
#include "trim.h"
#include "trim_left.h"
#include "trim_right.h"
#include "upper_case.h"
#include "url_decode.h"
#include "url_decode_uni.h"
#include "url_encode.h"
#include "utf8_to_unicode.h"


#define IF_MATCH(b) \
    if (a.compare(2, std::strlen(#b), #b) == 0)


namespace modsecurity::actions::transformations {


bool Transformation::transform(std::string &value, const Transaction *trans) const {
    return false;
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


}  // namespace modsecurity::actions::transformations
