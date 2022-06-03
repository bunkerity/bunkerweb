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


#include <string.h>

#include "modsecurity/modsecurity.h"
#include "modsecurity/rules.h"
#include "src/actions/transformations/transformation.h"

/**
 * for i in $(ls -l src/actions/transformations/*.h | awk {'print $9'}); do echo "#include \"$i\""; done;
 *
 */
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
#include "src/actions/transformations/transformation.h"
#include "src/actions/transformations/trim.h"
#include "src/actions/transformations/trim_left.h"
#include "src/actions/transformations/trim_right.h"
#include "src/actions/transformations/url_decode.h"
#include "src/actions/transformations/url_decode_uni.h"
#include "src/actions/transformations/url_encode.h"
#include "src/actions/transformations/utf8_to_unicode.h"



/**
 * for i in $(ls -l src/operators/*.h | awk {'print $9'}); do echo "#include \"$i\""; done;
 *
 */
#include "src/operators/begins_with.h"
#include "src/operators/contains.h"
#include "src/operators/contains_word.h"
#include "src/operators/detect_sqli.h"
#include "src/operators/detect_xss.h"
#include "src/operators/ends_with.h"
#include "src/operators/eq.h"
#include "src/operators/fuzzy_hash.h"
#include "src/operators/ge.h"
#include "src/operators/geo_lookup.h"
#include "src/operators/gsblookup.h"
#include "src/operators/gt.h"
#include "src/operators/inspect_file.h"
#include "src/operators/ip_match_f.h"
#include "src/operators/ip_match_from_file.h"
#include "src/operators/ip_match.h"
#include "src/operators/le.h"
#include "src/operators/lt.h"
#include "src/operators/no_match.h"
#include "src/operators/operator.h"
#include "src/operators/pm_f.h"
#include "src/operators/pm_from_file.h"
#include "src/operators/pm.h"
#include "src/operators/rbl.h"
#include "src/operators/rsub.h"
#include "src/operators/rx.h"
#include "src/operators/str_eq.h"
#include "src/operators/str_match.h"
#include "src/operators/unconditional_match.h"
#include "src/operators/validate_byte_range.h"
#include "src/operators/validate_dtd.h"
#include "src/operators/validate_hash.h"
#include "src/operators/validate_schema.h"
#include "src/operators/validate_url_encoding.h"
#include "src/operators/validate_utf8_encoding.h"
#include "src/operators/verify_cc.h"
#include "src/operators/verify_cpf.h"
#include "src/operators/verify_ssn.h"
#include "src/operators/within.h"


using namespace modsecurity::actions::transformations;
using namespace modsecurity::operators;
using namespace modsecurity;

#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <signal.h>
#include <string.h>


int main(int argc, char** argv) {
    uint8_t buf[128];

    std::string lastString;

    while (__AFL_LOOP(1000)) {
        ssize_t read_bytes;
        // (re-) initialize the library and read new input
        memset(buf, 0, 128);
        read_bytes = read(STDIN_FILENO, buf, 128);

        std::string currentString = std::string(read_bytes, 128);
        std::string s = currentString;
        std::string z = lastString;

        ModSecurity *ms = new ModSecurity();
        Rules *rules = new Rules();
        // Here it is possible to load a real transaction from a JSON.
        // like we do on the regression tests.
        Transaction *t = new Transaction(ms, rules, NULL);


        /**
        * Transformations, generated by:
        *
        * for i in $(grep "class " -Ri src/actions/transformations/* | grep " :" | grep -v "InstantCache" | awk {'print $2'}); do echo $i *$(echo $i | awk '{print tolower($0)}') = new $i\(\"$i\"\)\; $(echo $i | awk '{print tolower($0)}')-\>evaluate\(s, NULL\)\; delete $(echo $i | awk '{print tolower($0)}')\;; done;
        *
        */
Base64DecodeExt *base64decodeext = new Base64DecodeExt("Base64DecodeExt"); base64decodeext->evaluate(s, NULL); delete base64decodeext;
Base64Decode *base64decode = new Base64Decode("Base64Decode"); base64decode->evaluate(s, NULL); delete base64decode;
Base64Encode *base64encode = new Base64Encode("Base64Encode"); base64encode->evaluate(s, NULL); delete base64encode;
CmdLine *cmdline = new CmdLine("CmdLine"); cmdline->evaluate(s, NULL); delete cmdline;
CompressWhitespace *compresswhitespace = new CompressWhitespace("CompressWhitespace"); compresswhitespace->evaluate(s, NULL); delete compresswhitespace;
CssDecode *cssdecode = new CssDecode("CssDecode"); cssdecode->evaluate(s, NULL); delete cssdecode;
EscapeSeqDecode *escapeseqdecode = new EscapeSeqDecode("EscapeSeqDecode"); escapeseqdecode->evaluate(s, NULL); delete escapeseqdecode;
HexDecode *hexdecode = new HexDecode("HexDecode"); hexdecode->evaluate(s, NULL); delete hexdecode;
HexEncode *hexencode = new HexEncode("HexEncode"); hexencode->evaluate(s, NULL); delete hexencode;
HtmlEntityDecode *htmlentitydecode = new HtmlEntityDecode("HtmlEntityDecode"); htmlentitydecode->evaluate(s, NULL); delete htmlentitydecode;
JsDecode *jsdecode = new JsDecode("JsDecode"); jsdecode->evaluate(s, NULL); delete jsdecode;
Length *length = new Length("Length"); length->evaluate(s, NULL); delete length;
LowerCase *lowercase = new LowerCase("LowerCase"); lowercase->evaluate(s, NULL); delete lowercase;
Md5 *md5 = new Md5("Md5"); md5->evaluate(s, NULL); delete md5;
None *none = new None("None"); none->evaluate(s, NULL); delete none;
NormalisePath *normalisepath = new NormalisePath("NormalisePath"); normalisepath->evaluate(s, NULL); delete normalisepath;
NormalisePathWin *normalisepathwin = new NormalisePathWin("NormalisePathWin"); normalisepathwin->evaluate(s, NULL); delete normalisepathwin;
ParityEven7bit *parityeven7bit = new ParityEven7bit("ParityEven7bit"); parityeven7bit->evaluate(s, NULL); delete parityeven7bit;
ParityOdd7bit *parityodd7bit = new ParityOdd7bit("ParityOdd7bit"); parityodd7bit->evaluate(s, NULL); delete parityodd7bit;
ParityZero7bit *parityzero7bit = new ParityZero7bit("ParityZero7bit"); parityzero7bit->evaluate(s, NULL); delete parityzero7bit;
RemoveCommentsChar *removecommentschar = new RemoveCommentsChar("RemoveCommentsChar"); removecommentschar->evaluate(s, NULL); delete removecommentschar;
RemoveComments *removecomments = new RemoveComments("RemoveComments"); removecomments->evaluate(s, NULL); delete removecomments;
RemoveNulls *removenulls = new RemoveNulls("RemoveNulls"); removenulls->evaluate(s, NULL); delete removenulls;
RemoveWhitespace *removewhitespace = new RemoveWhitespace("RemoveWhitespace"); removewhitespace->evaluate(s, NULL); delete removewhitespace;
ReplaceComments *replacecomments = new ReplaceComments("ReplaceComments"); replacecomments->evaluate(s, NULL); delete replacecomments;
ReplaceNulls *replacenulls = new ReplaceNulls("ReplaceNulls"); replacenulls->evaluate(s, NULL); delete replacenulls;
Sha1 *sha1 = new Sha1("Sha1"); sha1->evaluate(s, NULL); delete sha1;
SqlHexDecode *sqlhexdecode = new SqlHexDecode("SqlHexDecode"); sqlhexdecode->evaluate(s, NULL); delete sqlhexdecode;
Transformation *transformation = new Transformation("Transformation"); transformation->evaluate(s, NULL); delete transformation;
Trim *trim = new Trim("Trim"); trim->evaluate(s, NULL); delete trim;
TrimLeft *trimleft = new TrimLeft("TrimLeft"); trimleft->evaluate(s, NULL); delete trimleft;
TrimRight *trimright = new TrimRight("TrimRight"); trimright->evaluate(s, NULL); delete trimright;
UrlDecode *urldecode = new UrlDecode("UrlDecode"); urldecode->evaluate(s, NULL); delete urldecode;
UrlDecodeUni *urldecodeuni = new UrlDecodeUni("UrlDecodeUni"); urldecodeuni->evaluate(s, NULL); delete urldecodeuni;
UrlEncode *urlencode = new UrlEncode("UrlEncode"); urlencode->evaluate(s, NULL); delete urlencode;
Utf8ToUnicode *utf8tounicode = new Utf8ToUnicode("Utf8ToUnicode"); utf8tounicode->evaluate(s, NULL); delete utf8tounicode;



        /**
        * Operators, generated by:
        *
        * for i in $(grep "class " -Ri src/operators/* | grep " :" | awk {'print $2'}); do echo $i *$(echo $i | awk '{print tolower($0)}') = new $i\(\"$i\", z, false\)\; $(echo $i | awk '{print tolower($0)}')-\>evaluate\(t, s\)\; delete $(echo $i | awk '{print tolower($0)}')\;; done;
        *
        */
BeginsWith *beginswith = new BeginsWith("BeginsWith", z, false); beginswith->evaluate(t, s); delete beginswith;
Contains *contains = new Contains("Contains", z, false); contains->evaluate(t, s); delete contains;
ContainsWord *containsword = new ContainsWord("ContainsWord", z, false); containsword->evaluate(t, s); delete containsword;
DetectSQLi *detectsqli = new DetectSQLi("DetectSQLi", z, false); detectsqli->evaluate(t, s); delete detectsqli;
DetectXSS *detectxss = new DetectXSS("DetectXSS", z, false); detectxss->evaluate(t, s); delete detectxss;
EndsWith *endswith = new EndsWith("EndsWith", z, false); endswith->evaluate(t, s); delete endswith;
Eq *eq = new Eq("Eq", z, false); eq->evaluate(t, s); delete eq;
FuzzyHash *fuzzyhash = new FuzzyHash("FuzzyHash", z, false); fuzzyhash->evaluate(t, s); delete fuzzyhash;
Ge *ge = new Ge("Ge", z, false); ge->evaluate(t, s); delete ge;
GeoLookup *geolookup = new GeoLookup("GeoLookup", z, false); geolookup->evaluate(t, s); delete geolookup;
GsbLookup *gsblookup = new GsbLookup("GsbLookup", z, false); gsblookup->evaluate(t, s); delete gsblookup;
Gt *gt = new Gt("Gt", z, false); gt->evaluate(t, s); delete gt;
InspectFile *inspectfile = new InspectFile("InspectFile", z, false); inspectfile->evaluate(t, s); delete inspectfile;
IpMatchF *ipmatchf = new IpMatchF("IpMatchF", z, false); ipmatchf->evaluate(t, s); delete ipmatchf;
IpMatchFromFile *ipmatchfromfile = new IpMatchFromFile("IpMatchFromFile", z, false); ipmatchfromfile->evaluate(t, s); delete ipmatchfromfile;
IpMatch *ipmatch = new IpMatch("IpMatch", z, false); ipmatch->evaluate(t, s); delete ipmatch;
Le *le = new Le("Le", z, false); le->evaluate(t, s); delete le;
Lt *lt = new Lt("Lt", z, false); lt->evaluate(t, s); delete lt;
NoMatch *nomatch = new NoMatch("NoMatch", z, false); nomatch->evaluate(t, s); delete nomatch;
PmF *pmf = new PmF("PmF", z, false); pmf->evaluate(t, s); delete pmf;
PmFromFile *pmfromfile = new PmFromFile("PmFromFile", z, false); pmfromfile->evaluate(t, s); delete pmfromfile;
Pm *pm = new Pm("Pm", z, false); pm->evaluate(t, s); delete pm;
// Rbl test is too slow to be tested here.
// Rbl *rbl = new Rbl("Rbl", z, false); rbl->evaluate(t, s); delete rbl;
Rsub *rsub = new Rsub("Rsub", z, false); rsub->evaluate(t, s); delete rsub;
Rx *rx = new Rx("Rx", z, false); rx->evaluate(t, s); delete rx;

StrEq *streq = new StrEq("StrEq", z, false); streq->evaluate(t, s); delete streq;

StrMatch *strmatch = new StrMatch("StrMatch", z, false); strmatch->evaluate(t, s); delete strmatch;
UnconditionalMatch *unconditionalmatch = new UnconditionalMatch("UnconditionalMatch", z, false); unconditionalmatch->evaluate(t, s); delete unconditionalmatch;
ValidateByteRange *validatebyterange = new ValidateByteRange("ValidateByteRange", z, false); validatebyterange->evaluate(t, s); delete validatebyterange;
ValidateDTD *validatedtd = new ValidateDTD("ValidateDTD", z, false); validatedtd->evaluate(t, s); delete validatedtd;
ValidateHash *validatehash = new ValidateHash("ValidateHash", z, false); validatehash->evaluate(t, s); delete validatehash;
ValidateSchema *validateschema = new ValidateSchema("ValidateSchema", z, false); validateschema->evaluate(t, s); delete validateschema;
ValidateUrlEncoding *validateurlencoding = new ValidateUrlEncoding("ValidateUrlEncoding", z, false); validateurlencoding->evaluate(t, s); delete validateurlencoding;
ValidateUtf8Encoding *validateutf8encoding = new ValidateUtf8Encoding("ValidateUtf8Encoding", z, false); validateutf8encoding->evaluate(t, s); delete validateutf8encoding;
VerifyCC *verifycc = new VerifyCC("VerifyCC", z, false); verifycc->evaluate(t, s); delete verifycc;
VerifyCPF *verifycpf = new VerifyCPF("VerifyCPF", z, false); verifycpf->evaluate(t, s); delete verifycpf;
VerifySSN *verifyssn = new VerifySSN("VerifySSN", z, false); verifyssn->evaluate(t, s); delete verifyssn;
Within *within = new Within("Within", z, false); within->evaluate(t, s); delete within;

        /**
        * ModSec API
        *
        */
#if 0
    t->processConnection(s.c_str(), 123, s.c_str(), 123);
    t->processURI(s.c_str(), z.c_str(), z.c_str());
    t->addRequestHeader(s, z);
    t->addRequestHeader(s, s);
    t->addRequestHeader(z, z);
    t->addRequestHeader(z, s);
    t->processRequestHeaders();
    t->appendRequestBody((const unsigned char *)s.c_str(), s.length());
    t->processRequestBody();
    t->addResponseHeader(s, z);
    t->addResponseHeader(s, s);
    t->addResponseHeader(z, z);
    t->addResponseHeader(z, s);
    t->processResponseHeaders();
    t->appendResponseBody((const unsigned char *)s.c_str(), s.length());
    t->processResponseBody();
#endif


        delete t;
        delete rules;
        delete ms;

        lastString = currentString;
    }
    return 0;
}

