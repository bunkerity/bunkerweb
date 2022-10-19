// A Bison parser, made by GNU Bison 3.3.2.

// Skeleton interface for Bison LALR(1) parsers in C++

// Copyright (C) 2002-2015, 2018-2019 Free Software Foundation, Inc.

// This program is free software: you can redistribute it and/or modify
// it under the terms of the GNU General Public License as published by
// the Free Software Foundation, either version 3 of the License, or
// (at your option) any later version.

// This program is distributed in the hope that it will be useful,
// but WITHOUT ANY WARRANTY; without even the implied warranty of
// MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
// GNU General Public License for more details.

// You should have received a copy of the GNU General Public License
// along with this program.  If not, see <http://www.gnu.org/licenses/>.

// As a special exception, you may create a larger work that contains
// part or all of the Bison parser skeleton and distribute that work
// under terms of your choice, so long as that work isn't itself a
// parser generator using the skeleton or a modified version thereof
// as a parser skeleton.  Alternatively, if you modify or redistribute
// the parser skeleton itself, you may (at your option) remove this
// special exception, which will cause the skeleton and the resulting
// Bison output files to be licensed under the GNU General Public
// License without this special exception.

// This special exception was added by the Free Software Foundation in
// version 2.2 of Bison.


/**
 ** \file y.tab.h
 ** Define the yy::parser class.
 */

// C++ LALR(1) parser skeleton written by Akim Demaille.

// Undocumented macros, especially those whose name start with YY_,
// are private implementation details.  Do not rely on them.

#ifndef YY_YY_SECLANG_PARSER_HH_INCLUDED
# define YY_YY_SECLANG_PARSER_HH_INCLUDED
// //                    "%code requires" blocks.
#line 10 "seclang-parser.yy" // lalr1.cc:401

#include <string>
#include <iterator>

namespace ModSecurity {
namespace Parser {
class Driver;
}
}

#include "src/rule_script.h"

#include "src/actions/accuracy.h"
#include "src/actions/audit_log.h"
#include "src/actions/block.h"
#include "src/actions/capture.h"
#include "src/actions/chain.h"
#include "src/actions/ctl/audit_log_parts.h"
#include "src/actions/ctl/request_body_access.h"
#include "src/actions/ctl/rule_engine.h"
#include "src/actions/ctl/request_body_processor_json.h"
#include "src/actions/ctl/request_body_processor_xml.h"
#include "src/actions/ctl/request_body_processor_urlencoded.h"
#include "src/actions/ctl/rule_remove_by_id.h"
#include "src/actions/ctl/rule_remove_by_tag.h"
#include "src/actions/ctl/rule_remove_target_by_id.h"
#include "src/actions/ctl/rule_remove_target_by_tag.h"
#include "src/actions/data/status.h"
#include "src/actions/disruptive/allow.h"
#include "src/actions/disruptive/deny.h"
#include "src/actions/disruptive/drop.h"
#include "src/actions/disruptive/pass.h"
#include "src/actions/disruptive/redirect.h"
#include "src/actions/init_col.h"
#include "src/actions/exec.h"
#include "src/actions/log_data.h"
#include "src/actions/log.h"
#include "src/actions/maturity.h"
#include "src/actions/msg.h"
#include "src/actions/multi_match.h"
#include "src/actions/no_audit_log.h"
#include "src/actions/no_log.h"
#include "src/actions/phase.h"
#include "src/actions/rev.h"
#include "src/actions/rule_id.h"
#include "src/actions/set_env.h"
#include "src/actions/set_rsc.h"
#include "src/actions/set_sid.h"
#include "src/actions/set_uid.h"
#include "src/actions/set_var.h"
#include "src/actions/severity.h"
#include "src/actions/skip_after.h"
#include "src/actions/skip.h"
#include "src/actions/tag.h"
#include "src/actions/transformations/none.h"
#include "src/actions/transformations/transformation.h"
#include "src/actions/transformations/url_decode_uni.h"
#include "src/actions/ver.h"
#include "src/actions/xmlns.h"

#include "src/actions/transformations/hex_encode.h"
#include "src/actions/transformations/parity_even_7bit.h"
#include "src/actions/transformations/utf8_to_unicode.h"
#include "src/actions/transformations/parity_zero_7bit.h"
#include "src/actions/transformations/sql_hex_decode.h"
#include "src/actions/transformations/replace_comments.h"
#include "src/actions/transformations/none.h"
#include "src/actions/transformations/url_decode.h"
#include "src/actions/transformations/lower_case.h"
#include "src/actions/transformations/upper_case.h"
#include "src/actions/transformations/hex_decode.h"
#include "src/actions/transformations/url_encode.h"
#include "src/actions/transformations/js_decode.h"
#include "src/actions/transformations/url_decode_uni.h"
#include "src/actions/transformations/parity_odd_7bit.h"
#include "src/actions/transformations/transformation.h"
#include "src/actions/transformations/trim_right.h"
#include "src/actions/transformations/escape_seq_decode.h"
#include "src/actions/transformations/base64_decode_ext.h"
#include "src/actions/transformations/base64_decode.h"
#include "src/actions/transformations/trim.h"
#include "src/actions/transformations/cmd_line.h"
#include "src/actions/transformations/replace_nulls.h"
#include "src/actions/transformations/md5.h"
#include "src/actions/transformations/length.h"
#include "src/actions/transformations/sha1.h"
#include "src/actions/transformations/compress_whitespace.h"
#include "src/actions/transformations/normalise_path_win.h"
#include "src/actions/transformations/remove_nulls.h"
#include "src/actions/transformations/remove_comments.h"
#include "src/actions/transformations/normalise_path.h"
#include "src/actions/transformations/html_entity_decode.h"
#include "src/actions/transformations/trim_left.h"
#include "src/actions/transformations/remove_comments_char.h"
#include "src/actions/transformations/base64_encode.h"
#include "src/actions/transformations/remove_whitespace.h"
#include "src/actions/transformations/css_decode.h"

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
#include "src/operators/verify_svnr.h"
#include "src/operators/within.h"


#include "modsecurity/audit_log.h"
#include "modsecurity/modsecurity.h"
#include "modsecurity/rules_properties.h"
#include "modsecurity/rule.h"
#include "src/operators/operator.h"
#include "src/utils/geo_lookup.h"
#include "src/utils/string.h"
#include "src/utils/system.h"
#include "src/variables/args_combined_size.h"
#include "src/variables/args_get.h"
#include "src/variables/args_get_names.h"
#include "src/variables/args.h"
#include "src/variables/args_names.h"
#include "src/variables/args_post.h"
#include "src/variables/args_post_names.h"
#include "src/variables/auth_type.h"
#include "src/variables/duration.h"
#include "src/variables/env.h"
#include "src/variables/files_combined_size.h"
#include "src/variables/files.h"
#include "src/variables/files_names.h"
#include "src/variables/files_sizes.h"
#include "src/variables/files_tmp_content.h"
#include "src/variables/files_tmp_names.h"
#include "src/variables/full_request.h"
#include "src/variables/full_request_length.h"
#include "src/variables/geo.h"
#include "src/variables/highest_severity.h"
#include "src/variables/inbound_data_error.h"
#include "src/variables/matched_var.h"
#include "src/variables/matched_var_name.h"
#include "src/variables/matched_vars.h"
#include "src/variables/matched_vars_names.h"
#include "src/variables/modsec_build.h"
#include "src/variables/multipart_boundary_quoted.h"
#include "src/variables/multipart_boundary_whitespace.h"
#include "src/variables/multipart_crlf_lf_lines.h"
#include "src/variables/multipart_data_after.h"
#include "src/variables/multipart_data_before.h"
#include "src/variables/multipart_file_limit_exceeded.h"
#include "src/variables/multipart_file_name.h"
#include "src/variables/multipart_header_folding.h"
#include "src/variables/multipart_invalid_header_folding.h"
#include "src/variables/multipart_invalid_part.h"
#include "src/variables/multipart_invalid_quoting.h"
#include "src/variables/multipart_lf_line.h"
#include "src/variables/multipart_missing_semicolon.h"
#include "src/variables/multipart_name.h"
#include "src/variables/multipart_strict_error.h"
#include "src/variables/multipart_unmatched_boundary.h"
#include "src/variables/outbound_data_error.h"
#include "src/variables/path_info.h"
#include "src/variables/query_string.h"
#include "src/variables/remote_addr.h"
#include "src/variables/remote_host.h"
#include "src/variables/remote_port.h"
#include "src/variables/remote_user.h"
#include "src/variables/reqbody_error.h"
#include "src/variables/reqbody_error_msg.h"
#include "src/variables/reqbody_processor_error.h"
#include "src/variables/reqbody_processor_error_msg.h"
#include "src/variables/reqbody_processor.h"
#include "src/variables/request_base_name.h"
#include "src/variables/request_body.h"
#include "src/variables/request_body_length.h"
#include "src/variables/request_cookies.h"
#include "src/variables/request_cookies_names.h"
#include "src/variables/request_file_name.h"
#include "src/variables/request_headers.h"
#include "src/variables/request_headers_names.h"
#include "src/variables/request_line.h"
#include "src/variables/request_method.h"
#include "src/variables/request_protocol.h"
#include "src/variables/request_uri.h"
#include "src/variables/request_uri_raw.h"
#include "src/variables/resource.h"
#include "src/variables/response_body.h"
#include "src/variables/response_content_length.h"
#include "src/variables/response_content_type.h"
#include "src/variables/response_headers.h"
#include "src/variables/response_headers_names.h"
#include "src/variables/response_protocol.h"
#include "src/variables/response_status.h"
#include "src/variables/rule.h"
#include "src/variables/server_addr.h"
#include "src/variables/server_name.h"
#include "src/variables/server_port.h"
#include "src/variables/session_id.h"
#include "src/variables/web_app_id.h"
#include "src/variables/time_day.h"
#include "src/variables/time_epoch.h"
#include "src/variables/time.h"
#include "src/variables/time_hour.h"
#include "src/variables/time_min.h"
#include "src/variables/time_mon.h"
#include "src/variables/time_sec.h"
#include "src/variables/time_wday.h"
#include "src/variables/time_year.h"
#include "src/variables/tx.h"
#include "src/variables/unique_id.h"
#include "src/variables/url_encoded_error.h"
#include "src/variables/user.h"
#include "src/variables/user_id.h"
#include "src/variables/variable.h"
#include "src/variables/xml.h"
#include "src/variables/ip.h"
#include "src/variables/global.h"
#include "src/variables/session.h"
#include "src/variables/status.h"


using namespace modsecurity;
using namespace modsecurity::variables;
using namespace modsecurity::Utils;
using namespace modsecurity::operators;


#define CHECK_VARIATION_DECL \
    Variable *var = NULL; \
    bool t = false;

#define CHECK_VARIATION(a) \
    if (var == NULL) { \
        if (name.at(0) == std::string(#a).at(0)) { \
            name.erase(0, 1); \
            t = true ; \
        } \
    } else { \
        t = false; \
    } \
    if (t)


#define ACTION_NOT_SUPPORTED(a, b) \
    driver.error(b, "Action: " + std::string(a) + " is not yet supported."); \
    YYERROR;


#define OPERATOR_NOT_SUPPORTED(a, b) \
    driver.error(b, "Operator: " + std::string(a) + " is not yet supported."); \
    YYERROR;


#define ACTION_INIT(a, b) \
    std::string error; \
    if (a->init(&error) == false) { \
        driver.error(b, error); \
        YYERROR; \
    }

#define OPERATOR_CONTAINER(a, b) \
    std::unique_ptr<Operator> c(b); \
    a = std::move(c);

#define ACTION_CONTAINER(a, b) \
    std::unique_ptr<actions::Action> c(b); \
    a = std::move(c);

#define VARIABLE_CONTAINER(a, b) \
    std::unique_ptr<Variable> c(b); \
    a = std::move(c);


#line 352 "seclang-parser.hh" // lalr1.cc:401

# include <cassert>
# include <cstdlib> // std::abort
# include <iostream>
# include <stdexcept>
# include <string>
# include <vector>

#if defined __cplusplus
# define YY_CPLUSPLUS __cplusplus
#else
# define YY_CPLUSPLUS 199711L
#endif

// Support move semantics when possible.
#if 201103L <= YY_CPLUSPLUS
# define YY_MOVE           std::move
# define YY_MOVE_OR_COPY   move
# define YY_MOVE_REF(Type) Type&&
# define YY_RVREF(Type)    Type&&
# define YY_COPY(Type)     Type
#else
# define YY_MOVE
# define YY_MOVE_OR_COPY   copy
# define YY_MOVE_REF(Type) Type&
# define YY_RVREF(Type)    const Type&
# define YY_COPY(Type)     const Type&
#endif

// Support noexcept when possible.
#if 201103L <= YY_CPLUSPLUS
# define YY_NOEXCEPT noexcept
# define YY_NOTHROW
#else
# define YY_NOEXCEPT
# define YY_NOTHROW throw ()
#endif

// Support constexpr when possible.
#if 201703 <= YY_CPLUSPLUS
# define YY_CONSTEXPR constexpr
#else
# define YY_CONSTEXPR
#endif
# include "location.hh"
#include <typeinfo>
#ifndef YYASSERT
# include <cassert>
# define YYASSERT assert
#endif


#ifndef YY_ATTRIBUTE
# if (defined __GNUC__                                               \
      && (2 < __GNUC__ || (__GNUC__ == 2 && 96 <= __GNUC_MINOR__)))  \
     || defined __SUNPRO_C && 0x5110 <= __SUNPRO_C
#  define YY_ATTRIBUTE(Spec) __attribute__(Spec)
# else
#  define YY_ATTRIBUTE(Spec) /* empty */
# endif
#endif

#ifndef YY_ATTRIBUTE_PURE
# define YY_ATTRIBUTE_PURE   YY_ATTRIBUTE ((__pure__))
#endif

#ifndef YY_ATTRIBUTE_UNUSED
# define YY_ATTRIBUTE_UNUSED YY_ATTRIBUTE ((__unused__))
#endif

/* Suppress unused-variable warnings by "using" E.  */
#if ! defined lint || defined __GNUC__
# define YYUSE(E) ((void) (E))
#else
# define YYUSE(E) /* empty */
#endif

#if defined __GNUC__ && ! defined __ICC && 407 <= __GNUC__ * 100 + __GNUC_MINOR__
/* Suppress an incorrect diagnostic about yylval being uninitialized.  */
# define YY_IGNORE_MAYBE_UNINITIALIZED_BEGIN \
    _Pragma ("GCC diagnostic push") \
    _Pragma ("GCC diagnostic ignored \"-Wuninitialized\"")\
    _Pragma ("GCC diagnostic ignored \"-Wmaybe-uninitialized\"")
# define YY_IGNORE_MAYBE_UNINITIALIZED_END \
    _Pragma ("GCC diagnostic pop")
#else
# define YY_INITIAL_VALUE(Value) Value
#endif
#ifndef YY_IGNORE_MAYBE_UNINITIALIZED_BEGIN
# define YY_IGNORE_MAYBE_UNINITIALIZED_BEGIN
# define YY_IGNORE_MAYBE_UNINITIALIZED_END
#endif
#ifndef YY_INITIAL_VALUE
# define YY_INITIAL_VALUE(Value) /* Nothing. */
#endif

# ifndef YY_NULLPTR
#  if defined __cplusplus
#   if 201103L <= __cplusplus
#    define YY_NULLPTR nullptr
#   else
#    define YY_NULLPTR 0
#   endif
#  else
#   define YY_NULLPTR ((void*)0)
#  endif
# endif

/* Debug traces.  */
#ifndef YYDEBUG
# define YYDEBUG 1
#endif


namespace yy {
#line 468 "seclang-parser.hh" // lalr1.cc:401



  /// A Bison parser.
  class seclang_parser
  {
  public:
#ifndef YYSTYPE
  /// A buffer to store and retrieve objects.
  ///
  /// Sort of a variant, but does not keep track of the nature
  /// of the stored data, since that knowledge is available
  /// via the current parser state.
  class semantic_type
  {
  public:
    /// Type of *this.
    typedef semantic_type self_type;

    /// Empty construction.
    semantic_type () YY_NOEXCEPT
      : yybuffer_ ()
      , yytypeid_ (YY_NULLPTR)
    {}

    /// Construct and fill.
    template <typename T>
    semantic_type (YY_RVREF (T) t)
      : yytypeid_ (&typeid (T))
    {
      YYASSERT (sizeof (T) <= size);
      new (yyas_<T> ()) T (YY_MOVE (t));
    }

    /// Destruction, allowed only if empty.
    ~semantic_type () YY_NOEXCEPT
    {
      YYASSERT (!yytypeid_);
    }

# if 201103L <= YY_CPLUSPLUS
    /// Instantiate a \a T in here from \a t.
    template <typename T, typename... U>
    T&
    emplace (U&&... u)
    {
      YYASSERT (!yytypeid_);
      YYASSERT (sizeof (T) <= size);
      yytypeid_ = & typeid (T);
      return *new (yyas_<T> ()) T (std::forward <U>(u)...);
    }
# else
    /// Instantiate an empty \a T in here.
    template <typename T>
    T&
    emplace ()
    {
      YYASSERT (!yytypeid_);
      YYASSERT (sizeof (T) <= size);
      yytypeid_ = & typeid (T);
      return *new (yyas_<T> ()) T ();
    }

    /// Instantiate a \a T in here from \a t.
    template <typename T>
    T&
    emplace (const T& t)
    {
      YYASSERT (!yytypeid_);
      YYASSERT (sizeof (T) <= size);
      yytypeid_ = & typeid (T);
      return *new (yyas_<T> ()) T (std::move((T&)t));
    }
# endif

    /// Instantiate an empty \a T in here.
    /// Obsolete, use emplace.
    template <typename T>
    T&
    build ()
    {
      return emplace<T> ();
    }

    /// Instantiate a \a T in here from \a t.
    /// Obsolete, use emplace.
    template <typename T>
    T&
    build (const T& t)
    {
      return emplace<T> (t);
    }

    /// Accessor to a built \a T.
    template <typename T>
    T&
    as () YY_NOEXCEPT
    {
      YYASSERT (yytypeid_);
      YYASSERT (*yytypeid_ == typeid (T));
      YYASSERT (sizeof (T) <= size);
      return *yyas_<T> ();
    }

    /// Const accessor to a built \a T (for %printer).
    template <typename T>
    const T&
    as () const YY_NOEXCEPT
    {
      YYASSERT (yytypeid_);
      YYASSERT (*yytypeid_ == typeid (T));
      YYASSERT (sizeof (T) <= size);
      return *yyas_<T> ();
    }

    /// Swap the content with \a that, of same type.
    ///
    /// Both variants must be built beforehand, because swapping the actual
    /// data requires reading it (with as()), and this is not possible on
    /// unconstructed variants: it would require some dynamic testing, which
    /// should not be the variant's responsibility.
    /// Swapping between built and (possibly) non-built is done with
    /// self_type::move ().
    template <typename T>
    void
    swap (self_type& that) YY_NOEXCEPT
    {
      YYASSERT (yytypeid_);
      YYASSERT (*yytypeid_ == *that.yytypeid_);
      std::swap (as<T> (), that.as<T> ());
    }

    /// Move the content of \a that to this.
    ///
    /// Destroys \a that.
    template <typename T>
    void
    move (self_type& that)
    {
# if 201103L <= YY_CPLUSPLUS
      emplace<T> (std::move (that.as<T> ()));
# else
      emplace<T> ();
      swap<T> (that);
# endif
      that.destroy<T> ();
    }

# if 201103L <= YY_CPLUSPLUS
    /// Move the content of \a that to this.
    template <typename T>
    void
    move (self_type&& that)
    {
      emplace<T> (std::move (that.as<T> ()));
      that.destroy<T> ();
    }
#endif

    /// Copy the content of \a that to this.
    template <typename T>
    void
    copy (const self_type& that)
    {
      emplace<T> (that.as<T> ());
    }

    /// Destroy the stored \a T.
    template <typename T>
    void
    destroy ()
    {
      as<T> ().~T ();
      yytypeid_ = YY_NULLPTR;
    }

  private:
    /// Prohibit blind copies.
    self_type& operator= (const self_type&);
    semantic_type (const self_type&);

    /// Accessor to raw memory as \a T.
    template <typename T>
    T*
    yyas_ () YY_NOEXCEPT
    {
      void *yyp = yybuffer_.yyraw;
      return static_cast<T*> (yyp);
     }

    /// Const accessor to raw memory as \a T.
    template <typename T>
    const T*
    yyas_ () const YY_NOEXCEPT
    {
      const void *yyp = yybuffer_.yyraw;
      return static_cast<const T*> (yyp);
     }

    /// An auxiliary type to compute the largest semantic type.
    union union_type
    {
      // "Accuracy"
      // "Allow"
      // "Append"
      // "AuditLog"
      // "Block"
      // "Capture"
      // "Chain"
      // "ACTION_CTL_AUDIT_ENGINE"
      // "ACTION_CTL_AUDIT_LOG_PARTS"
      // "ACTION_CTL_BDY_JSON"
      // "ACTION_CTL_BDY_XML"
      // "ACTION_CTL_BDY_URLENCODED"
      // "ACTION_CTL_FORCE_REQ_BODY_VAR"
      // "ACTION_CTL_REQUEST_BODY_ACCESS"
      // "ACTION_CTL_RULE_REMOVE_BY_ID"
      // "ACTION_CTL_RULE_REMOVE_BY_TAG"
      // "ACTION_CTL_RULE_REMOVE_TARGET_BY_ID"
      // "ACTION_CTL_RULE_REMOVE_TARGET_BY_TAG"
      // "Deny"
      // "DeprecateVar"
      // "Drop"
      // "Exec"
      // "ExpireVar"
      // "Id"
      // "InitCol"
      // "Log"
      // "LogData"
      // "Maturity"
      // "Msg"
      // "MultiMatch"
      // "NoAuditLog"
      // "NoLog"
      // "Pass"
      // "Pause"
      // "Phase"
      // "Prepend"
      // "Proxy"
      // "Redirect"
      // "Rev"
      // "SanitiseArg"
      // "SanitiseMatched"
      // "SanitiseMatchedBytes"
      // "SanitiseRequestHeader"
      // "SanitiseResponseHeader"
      // "SetEnv"
      // "SetRsc"
      // "SetSid"
      // "SetUID"
      // "Severity"
      // "Skip"
      // "SkipAfter"
      // "Status"
      // "Tag"
      // "ACTION_TRANSFORMATION_BASE_64_ENCODE"
      // "ACTION_TRANSFORMATION_BASE_64_DECODE"
      // "ACTION_TRANSFORMATION_BASE_64_DECODE_EXT"
      // "ACTION_TRANSFORMATION_CMD_LINE"
      // "ACTION_TRANSFORMATION_COMPRESS_WHITESPACE"
      // "ACTION_TRANSFORMATION_CSS_DECODE"
      // "ACTION_TRANSFORMATION_ESCAPE_SEQ_DECODE"
      // "ACTION_TRANSFORMATION_HEX_ENCODE"
      // "ACTION_TRANSFORMATION_HEX_DECODE"
      // "ACTION_TRANSFORMATION_HTML_ENTITY_DECODE"
      // "ACTION_TRANSFORMATION_JS_DECODE"
      // "ACTION_TRANSFORMATION_LENGTH"
      // "ACTION_TRANSFORMATION_LOWERCASE"
      // "ACTION_TRANSFORMATION_MD5"
      // "ACTION_TRANSFORMATION_NONE"
      // "ACTION_TRANSFORMATION_NORMALISE_PATH"
      // "ACTION_TRANSFORMATION_NORMALISE_PATH_WIN"
      // "ACTION_TRANSFORMATION_PARITY_EVEN_7_BIT"
      // "ACTION_TRANSFORMATION_PARITY_ODD_7_BIT"
      // "ACTION_TRANSFORMATION_PARITY_ZERO_7_BIT"
      // "ACTION_TRANSFORMATION_REMOVE_COMMENTS"
      // "ACTION_TRANSFORMATION_REMOVE_COMMENTS_CHAR"
      // "ACTION_TRANSFORMATION_REMOVE_NULLS"
      // "ACTION_TRANSFORMATION_REMOVE_WHITESPACE"
      // "ACTION_TRANSFORMATION_REPLACE_COMMENTS"
      // "ACTION_TRANSFORMATION_REPLACE_NULLS"
      // "ACTION_TRANSFORMATION_SHA1"
      // "ACTION_TRANSFORMATION_SQL_HEX_DECODE"
      // "ACTION_TRANSFORMATION_TRIM"
      // "ACTION_TRANSFORMATION_TRIM_LEFT"
      // "ACTION_TRANSFORMATION_TRIM_RIGHT"
      // "ACTION_TRANSFORMATION_UPPERCASE"
      // "ACTION_TRANSFORMATION_URL_ENCODE"
      // "ACTION_TRANSFORMATION_URL_DECODE"
      // "ACTION_TRANSFORMATION_URL_DECODE_UNI"
      // "ACTION_TRANSFORMATION_UTF8_TO_UNICODE"
      // "Ver"
      // "xmlns"
      // "CONFIG_COMPONENT_SIG"
      // "CONFIG_CONN_ENGINE"
      // "CONFIG_SEC_ARGUMENT_SEPARATOR"
      // "CONFIG_SEC_WEB_APP_ID"
      // "CONFIG_SEC_SERVER_SIG"
      // "CONFIG_DIR_AUDIT_DIR"
      // "CONFIG_DIR_AUDIT_DIR_MOD"
      // "CONFIG_DIR_AUDIT_ENG"
      // "CONFIG_DIR_AUDIT_FLE_MOD"
      // "CONFIG_DIR_AUDIT_LOG"
      // "CONFIG_DIR_AUDIT_LOG2"
      // "CONFIG_DIR_AUDIT_LOG_P"
      // "CONFIG_DIR_AUDIT_STS"
      // "CONFIG_DIR_AUDIT_TPE"
      // "CONFIG_DIR_DEBUG_LOG"
      // "CONFIG_DIR_DEBUG_LVL"
      // "CONFIG_SEC_CACHE_TRANSFORMATIONS"
      // "CONFIG_SEC_DISABLE_BACKEND_COMPRESS"
      // "CONFIG_SEC_HASH_ENGINE"
      // "CONFIG_SEC_HASH_KEY"
      // "CONFIG_SEC_HASH_PARAM"
      // "CONFIG_SEC_HASH_METHOD_RX"
      // "CONFIG_SEC_HASH_METHOD_PM"
      // "CONFIG_SEC_CHROOT_DIR"
      // "CONFIG_DIR_GEO_DB"
      // "CONFIG_DIR_GSB_DB"
      // "CONFIG_SEC_GUARDIAN_LOG"
      // "CONFIG_DIR_PCRE_MATCH_LIMIT"
      // "CONFIG_DIR_PCRE_MATCH_LIMIT_RECURSION"
      // "CONFIG_SEC_CONN_R_STATE_LIMIT"
      // "CONFIG_SEC_CONN_W_STATE_LIMIT"
      // "CONFIG_SEC_SENSOR_ID"
      // "CONFIG_DIR_REQ_BODY"
      // "CONFIG_DIR_REQ_BODY_IN_MEMORY_LIMIT"
      // "CONFIG_DIR_REQ_BODY_LIMIT"
      // "CONFIG_DIR_REQ_BODY_LIMIT_ACTION"
      // "CONFIG_DIR_REQ_BODY_NO_FILES_LIMIT"
      // "CONFIG_DIR_RES_BODY"
      // "CONFIG_DIR_RES_BODY_LIMIT"
      // "CONFIG_DIR_RES_BODY_LIMIT_ACTION"
      // "CONFIG_SEC_RULE_INHERITANCE"
      // "CONFIG_SEC_RULE_PERF_TIME"
      // "CONFIG_DIR_RULE_ENG"
      // "CONFIG_DIR_SEC_ACTION"
      // "CONFIG_DIR_SEC_DEFAULT_ACTION"
      // "CONFIG_DIR_SEC_MARKER"
      // "CONFIG_DIR_UNICODE_MAP_FILE"
      // "CONFIG_DIR_UNICODE_CODE_PAGE"
      // "CONFIG_SEC_COLLECTION_TIMEOUT"
      // "CONFIG_SEC_HTTP_BLKEY"
      // "CONFIG_SEC_INTERCEPT_ON_ERROR"
      // "CONFIG_SEC_REMOTE_RULES_FAIL_ACTION"
      // "CONFIG_SEC_RULE_REMOVE_BY_ID"
      // "CONFIG_SEC_RULE_REMOVE_BY_MSG"
      // "CONFIG_SEC_RULE_REMOVE_BY_TAG"
      // "CONFIG_SEC_RULE_UPDATE_TARGET_BY_TAG"
      // "CONFIG_SEC_RULE_UPDATE_TARGET_BY_MSG"
      // "CONFIG_SEC_RULE_UPDATE_TARGET_BY_ID"
      // "CONFIG_SEC_RULE_UPDATE_ACTION_BY_ID"
      // "CONFIG_UPDLOAD_KEEP_FILES"
      // "CONFIG_UPDLOAD_SAVE_TMP_FILES"
      // "CONFIG_UPLOAD_DIR"
      // "CONFIG_UPLOAD_FILE_LIMIT"
      // "CONFIG_UPLOAD_FILE_MODE"
      // "CONFIG_VALUE_ABORT"
      // "CONFIG_VALUE_DETC"
      // "CONFIG_VALUE_HTTPS"
      // "CONFIG_VALUE_OFF"
      // "CONFIG_VALUE_ON"
      // "CONFIG_VALUE_PARALLEL"
      // "CONFIG_VALUE_PROCESS_PARTIAL"
      // "CONFIG_VALUE_REJECT"
      // "CONFIG_VALUE_RELEVANT_ONLY"
      // "CONFIG_VALUE_SERIAL"
      // "CONFIG_VALUE_WARN"
      // "CONFIG_XML_EXTERNAL_ENTITY"
      // "CONGIG_DIR_RESPONSE_BODY_MP"
      // "CONGIG_DIR_SEC_ARG_SEP"
      // "CONGIG_DIR_SEC_COOKIE_FORMAT"
      // "CONFIG_SEC_COOKIEV0_SEPARATOR"
      // "CONGIG_DIR_SEC_DATA_DIR"
      // "CONGIG_DIR_SEC_STATUS_ENGINE"
      // "CONFIG_SEC_STREAM_IN_BODY_INSPECTION"
      // "CONFIG_SEC_STREAM_OUT_BODY_INSPECTION"
      // "CONGIG_DIR_SEC_TMP_DIR"
      // "DIRECTIVE"
      // "DIRECTIVE_SECRULESCRIPT"
      // "FREE_TEXT_QUOTE_MACRO_EXPANSION"
      // "QUOTATION_MARK"
      // "RUN_TIME_VAR_BLD"
      // "RUN_TIME_VAR_DUR"
      // "RUN_TIME_VAR_HSV"
      // "RUN_TIME_VAR_REMOTE_USER"
      // "RUN_TIME_VAR_TIME"
      // "RUN_TIME_VAR_TIME_DAY"
      // "RUN_TIME_VAR_TIME_EPOCH"
      // "RUN_TIME_VAR_TIME_HOUR"
      // "RUN_TIME_VAR_TIME_MIN"
      // "RUN_TIME_VAR_TIME_MON"
      // "RUN_TIME_VAR_TIME_SEC"
      // "RUN_TIME_VAR_TIME_WDAY"
      // "RUN_TIME_VAR_TIME_YEAR"
      // "VARIABLE"
      // "Dictionary element"
      // "Dictionary element, selected by regexp"
      char dummy1[sizeof (std::string)];

      // op
      // op_before_init
      char dummy2[sizeof (std::unique_ptr<Operator>)];

      // run_time_string
      char dummy3[sizeof (std::unique_ptr<RunTimeString>)];

      // var
      char dummy4[sizeof (std::unique_ptr<Variable>)];

      // act
      // setvar_action
      char dummy5[sizeof (std::unique_ptr<actions::Action>)];

      // variables
      // variables_pre_process
      // variables_may_be_quoted
      char dummy6[sizeof (std::unique_ptr<std::vector<std::unique_ptr<Variable> > > )];

      // actions
      // actions_may_quoted
      char dummy7[sizeof (std::unique_ptr<std::vector<std::unique_ptr<actions::Action> > > )];
    };

    /// The size of the largest semantic type.
    enum { size = sizeof (union_type) };

    /// A buffer to store semantic values.
    union
    {
      /// Strongest alignment constraints.
      long double yyalign_me;
      /// A buffer large enough to store any of the semantic values.
      char yyraw[size];
    } yybuffer_;

    /// Whether the content is built: if defined, the name of the stored type.
    const std::type_info *yytypeid_;
  };

#else
    typedef YYSTYPE semantic_type;
#endif
    /// Symbol locations.
    typedef location location_type;

    /// Syntax errors thrown from user actions.
    struct syntax_error : std::runtime_error
    {
      syntax_error (const location_type& l, const std::string& m)
        : std::runtime_error (m)
        , location (l)
      {}

      syntax_error (const syntax_error& s)
        : std::runtime_error (s.what ())
        , location (s.location)
      {}

      ~syntax_error () YY_NOEXCEPT YY_NOTHROW;

      location_type location;
    };

    /// Tokens.
    struct token
    {
      enum yytokentype
      {
        TOK_END = 0,
        TOK_COMMA = 258,
        TOK_CONFIG_CONTENT_INJECTION = 259,
        TOK_CONGIG_DIR_RESPONSE_BODY_MP_CLEAR = 260,
        TOK_PIPE = 261,
        TOK_NEW_LINE = 262,
        TOK_VAR_COUNT = 263,
        TOK_VAR_EXCLUSION = 264,
        TOK_VARIABLE_ARGS = 265,
        TOK_VARIABLE_ARGS_POST = 266,
        TOK_VARIABLE_ARGS_GET = 267,
        TOK_VARIABLE_FILES_SIZES = 268,
        TOK_VARIABLE_FILES_NAMES = 269,
        TOK_VARIABLE_FILES_TMP_CONTENT = 270,
        TOK_VARIABLE_MULTIPART_FILENAME = 271,
        TOK_VARIABLE_MULTIPART_NAME = 272,
        TOK_VARIABLE_MATCHED_VARS_NAMES = 273,
        TOK_VARIABLE_MATCHED_VARS = 274,
        TOK_VARIABLE_FILES = 275,
        TOK_VARIABLE_REQUEST_COOKIES = 276,
        TOK_VARIABLE_REQUEST_HEADERS = 277,
        TOK_VARIABLE_RESPONSE_HEADERS = 278,
        TOK_VARIABLE_GEO = 279,
        TOK_VARIABLE_REQUEST_COOKIES_NAMES = 280,
        TOK_VARIABLE_ARGS_COMBINED_SIZE = 281,
        TOK_VARIABLE_ARGS_GET_NAMES = 282,
        TOK_VARIABLE_RULE = 283,
        TOK_VARIABLE_ARGS_NAMES = 284,
        TOK_VARIABLE_ARGS_POST_NAMES = 285,
        TOK_VARIABLE_AUTH_TYPE = 286,
        TOK_VARIABLE_FILES_COMBINED_SIZE = 287,
        TOK_VARIABLE_FILES_TMP_NAMES = 288,
        TOK_VARIABLE_FULL_REQUEST = 289,
        TOK_VARIABLE_FULL_REQUEST_LENGTH = 290,
        TOK_VARIABLE_INBOUND_DATA_ERROR = 291,
        TOK_VARIABLE_MATCHED_VAR = 292,
        TOK_VARIABLE_MATCHED_VAR_NAME = 293,
        TOK_VARIABLE_MULTIPART_BOUNDARY_QUOTED = 294,
        TOK_VARIABLE_MULTIPART_BOUNDARY_WHITESPACE = 295,
        TOK_VARIABLE_MULTIPART_CRLF_LF_LINES = 296,
        TOK_VARIABLE_MULTIPART_DATA_AFTER = 297,
        TOK_VARIABLE_MULTIPART_DATA_BEFORE = 298,
        TOK_VARIABLE_MULTIPART_FILE_LIMIT_EXCEEDED = 299,
        TOK_VARIABLE_MULTIPART_HEADER_FOLDING = 300,
        TOK_VARIABLE_MULTIPART_INVALID_HEADER_FOLDING = 301,
        TOK_VARIABLE_MULTIPART_INVALID_PART = 302,
        TOK_VARIABLE_MULTIPART_INVALID_QUOTING = 303,
        TOK_VARIABLE_MULTIPART_LF_LINE = 304,
        TOK_VARIABLE_MULTIPART_MISSING_SEMICOLON = 305,
        TOK_VARIABLE_MULTIPART_SEMICOLON_MISSING = 306,
        TOK_VARIABLE_MULTIPART_STRICT_ERROR = 307,
        TOK_VARIABLE_MULTIPART_UNMATCHED_BOUNDARY = 308,
        TOK_VARIABLE_OUTBOUND_DATA_ERROR = 309,
        TOK_VARIABLE_PATH_INFO = 310,
        TOK_VARIABLE_QUERY_STRING = 311,
        TOK_VARIABLE_REMOTE_ADDR = 312,
        TOK_VARIABLE_REMOTE_HOST = 313,
        TOK_VARIABLE_REMOTE_PORT = 314,
        TOK_VARIABLE_REQBODY_ERROR_MSG = 315,
        TOK_VARIABLE_REQBODY_ERROR = 316,
        TOK_VARIABLE_REQBODY_PROCESSOR_ERROR_MSG = 317,
        TOK_VARIABLE_REQBODY_PROCESSOR_ERROR = 318,
        TOK_VARIABLE_REQBODY_PROCESSOR = 319,
        TOK_VARIABLE_REQUEST_BASENAME = 320,
        TOK_VARIABLE_REQUEST_BODY_LENGTH = 321,
        TOK_VARIABLE_REQUEST_BODY = 322,
        TOK_VARIABLE_REQUEST_FILE_NAME = 323,
        TOK_VARIABLE_REQUEST_HEADERS_NAMES = 324,
        TOK_VARIABLE_REQUEST_LINE = 325,
        TOK_VARIABLE_REQUEST_METHOD = 326,
        TOK_VARIABLE_REQUEST_PROTOCOL = 327,
        TOK_VARIABLE_REQUEST_URI_RAW = 328,
        TOK_VARIABLE_REQUEST_URI = 329,
        TOK_VARIABLE_RESOURCE = 330,
        TOK_VARIABLE_RESPONSE_BODY = 331,
        TOK_VARIABLE_RESPONSE_CONTENT_LENGTH = 332,
        TOK_VARIABLE_RESPONSE_CONTENT_TYPE = 333,
        TOK_VARIABLE_RESPONSE_HEADERS_NAMES = 334,
        TOK_VARIABLE_RESPONSE_PROTOCOL = 335,
        TOK_VARIABLE_RESPONSE_STATUS = 336,
        TOK_VARIABLE_SERVER_ADDR = 337,
        TOK_VARIABLE_SERVER_NAME = 338,
        TOK_VARIABLE_SERVER_PORT = 339,
        TOK_VARIABLE_SESSION_ID = 340,
        TOK_VARIABLE_UNIQUE_ID = 341,
        TOK_VARIABLE_URL_ENCODED_ERROR = 342,
        TOK_VARIABLE_USER_ID = 343,
        TOK_VARIABLE_WEB_APP_ID = 344,
        TOK_VARIABLE_STATUS = 345,
        TOK_VARIABLE_STATUS_LINE = 346,
        TOK_VARIABLE_IP = 347,
        TOK_VARIABLE_GLOBAL = 348,
        TOK_VARIABLE_TX = 349,
        TOK_VARIABLE_SESSION = 350,
        TOK_VARIABLE_USER = 351,
        TOK_RUN_TIME_VAR_ENV = 352,
        TOK_RUN_TIME_VAR_XML = 353,
        TOK_ACTION_SETVAR = 354,
        TOK_SETVAR_OPERATION_EQUALS = 355,
        TOK_SETVAR_OPERATION_EQUALS_PLUS = 356,
        TOK_SETVAR_OPERATION_EQUALS_MINUS = 357,
        TOK_NOT = 358,
        TOK_OPERATOR_BEGINS_WITH = 359,
        TOK_OPERATOR_CONTAINS = 360,
        TOK_OPERATOR_CONTAINS_WORD = 361,
        TOK_OPERATOR_DETECT_SQLI = 362,
        TOK_OPERATOR_DETECT_XSS = 363,
        TOK_OPERATOR_ENDS_WITH = 364,
        TOK_OPERATOR_EQ = 365,
        TOK_OPERATOR_FUZZY_HASH = 366,
        TOK_OPERATOR_GEOLOOKUP = 367,
        TOK_OPERATOR_GE = 368,
        TOK_OPERATOR_GSB_LOOKUP = 369,
        TOK_OPERATOR_GT = 370,
        TOK_OPERATOR_INSPECT_FILE = 371,
        TOK_OPERATOR_IP_MATCH_FROM_FILE = 372,
        TOK_OPERATOR_IP_MATCH = 373,
        TOK_OPERATOR_LE = 374,
        TOK_OPERATOR_LT = 375,
        TOK_OPERATOR_PM_FROM_FILE = 376,
        TOK_OPERATOR_PM = 377,
        TOK_OPERATOR_RBL = 378,
        TOK_OPERATOR_RSUB = 379,
        TOK_OPERATOR_RX_CONTENT_ONLY = 380,
        TOK_OPERATOR_RX = 381,
        TOK_OPERATOR_STR_EQ = 382,
        TOK_OPERATOR_STR_MATCH = 383,
        TOK_OPERATOR_UNCONDITIONAL_MATCH = 384,
        TOK_OPERATOR_VALIDATE_BYTE_RANGE = 385,
        TOK_OPERATOR_VALIDATE_DTD = 386,
        TOK_OPERATOR_VALIDATE_HASH = 387,
        TOK_OPERATOR_VALIDATE_SCHEMA = 388,
        TOK_OPERATOR_VALIDATE_URL_ENCODING = 389,
        TOK_OPERATOR_VALIDATE_UTF8_ENCODING = 390,
        TOK_OPERATOR_VERIFY_CC = 391,
        TOK_OPERATOR_VERIFY_CPF = 392,
        TOK_OPERATOR_VERIFY_SSN = 393,
        TOK_OPERATOR_VERIFY_SVNR = 394,
        TOK_OPERATOR_WITHIN = 395,
        TOK_CONFIG_DIR_AUDIT_LOG_FMT = 396,
        TOK_JSON = 397,
        TOK_NATIVE = 398,
        TOK_ACTION_CTL_RULE_ENGINE = 399,
        TOK_ACTION_ACCURACY = 400,
        TOK_ACTION_ALLOW = 401,
        TOK_ACTION_APPEND = 402,
        TOK_ACTION_AUDIT_LOG = 403,
        TOK_ACTION_BLOCK = 404,
        TOK_ACTION_CAPTURE = 405,
        TOK_ACTION_CHAIN = 406,
        TOK_ACTION_CTL_AUDIT_ENGINE = 407,
        TOK_ACTION_CTL_AUDIT_LOG_PARTS = 408,
        TOK_ACTION_CTL_BDY_JSON = 409,
        TOK_ACTION_CTL_BDY_XML = 410,
        TOK_ACTION_CTL_BDY_URLENCODED = 411,
        TOK_ACTION_CTL_FORCE_REQ_BODY_VAR = 412,
        TOK_ACTION_CTL_REQUEST_BODY_ACCESS = 413,
        TOK_ACTION_CTL_RULE_REMOVE_BY_ID = 414,
        TOK_ACTION_CTL_RULE_REMOVE_BY_TAG = 415,
        TOK_ACTION_CTL_RULE_REMOVE_TARGET_BY_ID = 416,
        TOK_ACTION_CTL_RULE_REMOVE_TARGET_BY_TAG = 417,
        TOK_ACTION_DENY = 418,
        TOK_ACTION_DEPRECATE_VAR = 419,
        TOK_ACTION_DROP = 420,
        TOK_ACTION_EXEC = 421,
        TOK_ACTION_EXPIRE_VAR = 422,
        TOK_ACTION_ID = 423,
        TOK_ACTION_INITCOL = 424,
        TOK_ACTION_LOG = 425,
        TOK_ACTION_LOG_DATA = 426,
        TOK_ACTION_MATURITY = 427,
        TOK_ACTION_MSG = 428,
        TOK_ACTION_MULTI_MATCH = 429,
        TOK_ACTION_NO_AUDIT_LOG = 430,
        TOK_ACTION_NO_LOG = 431,
        TOK_ACTION_PASS = 432,
        TOK_ACTION_PAUSE = 433,
        TOK_ACTION_PHASE = 434,
        TOK_ACTION_PREPEND = 435,
        TOK_ACTION_PROXY = 436,
        TOK_ACTION_REDIRECT = 437,
        TOK_ACTION_REV = 438,
        TOK_ACTION_SANITISE_ARG = 439,
        TOK_ACTION_SANITISE_MATCHED = 440,
        TOK_ACTION_SANITISE_MATCHED_BYTES = 441,
        TOK_ACTION_SANITISE_REQUEST_HEADER = 442,
        TOK_ACTION_SANITISE_RESPONSE_HEADER = 443,
        TOK_ACTION_SETENV = 444,
        TOK_ACTION_SETRSC = 445,
        TOK_ACTION_SETSID = 446,
        TOK_ACTION_SETUID = 447,
        TOK_ACTION_SEVERITY = 448,
        TOK_ACTION_SKIP = 449,
        TOK_ACTION_SKIP_AFTER = 450,
        TOK_ACTION_STATUS = 451,
        TOK_ACTION_TAG = 452,
        TOK_ACTION_TRANSFORMATION_BASE_64_ENCODE = 453,
        TOK_ACTION_TRANSFORMATION_BASE_64_DECODE = 454,
        TOK_ACTION_TRANSFORMATION_BASE_64_DECODE_EXT = 455,
        TOK_ACTION_TRANSFORMATION_CMD_LINE = 456,
        TOK_ACTION_TRANSFORMATION_COMPRESS_WHITESPACE = 457,
        TOK_ACTION_TRANSFORMATION_CSS_DECODE = 458,
        TOK_ACTION_TRANSFORMATION_ESCAPE_SEQ_DECODE = 459,
        TOK_ACTION_TRANSFORMATION_HEX_ENCODE = 460,
        TOK_ACTION_TRANSFORMATION_HEX_DECODE = 461,
        TOK_ACTION_TRANSFORMATION_HTML_ENTITY_DECODE = 462,
        TOK_ACTION_TRANSFORMATION_JS_DECODE = 463,
        TOK_ACTION_TRANSFORMATION_LENGTH = 464,
        TOK_ACTION_TRANSFORMATION_LOWERCASE = 465,
        TOK_ACTION_TRANSFORMATION_MD5 = 466,
        TOK_ACTION_TRANSFORMATION_NONE = 467,
        TOK_ACTION_TRANSFORMATION_NORMALISE_PATH = 468,
        TOK_ACTION_TRANSFORMATION_NORMALISE_PATH_WIN = 469,
        TOK_ACTION_TRANSFORMATION_PARITY_EVEN_7_BIT = 470,
        TOK_ACTION_TRANSFORMATION_PARITY_ODD_7_BIT = 471,
        TOK_ACTION_TRANSFORMATION_PARITY_ZERO_7_BIT = 472,
        TOK_ACTION_TRANSFORMATION_REMOVE_COMMENTS = 473,
        TOK_ACTION_TRANSFORMATION_REMOVE_COMMENTS_CHAR = 474,
        TOK_ACTION_TRANSFORMATION_REMOVE_NULLS = 475,
        TOK_ACTION_TRANSFORMATION_REMOVE_WHITESPACE = 476,
        TOK_ACTION_TRANSFORMATION_REPLACE_COMMENTS = 477,
        TOK_ACTION_TRANSFORMATION_REPLACE_NULLS = 478,
        TOK_ACTION_TRANSFORMATION_SHA1 = 479,
        TOK_ACTION_TRANSFORMATION_SQL_HEX_DECODE = 480,
        TOK_ACTION_TRANSFORMATION_TRIM = 481,
        TOK_ACTION_TRANSFORMATION_TRIM_LEFT = 482,
        TOK_ACTION_TRANSFORMATION_TRIM_RIGHT = 483,
        TOK_ACTION_TRANSFORMATION_UPPERCASE = 484,
        TOK_ACTION_TRANSFORMATION_URL_ENCODE = 485,
        TOK_ACTION_TRANSFORMATION_URL_DECODE = 486,
        TOK_ACTION_TRANSFORMATION_URL_DECODE_UNI = 487,
        TOK_ACTION_TRANSFORMATION_UTF8_TO_UNICODE = 488,
        TOK_ACTION_VER = 489,
        TOK_ACTION_XMLNS = 490,
        TOK_CONFIG_COMPONENT_SIG = 491,
        TOK_CONFIG_CONN_ENGINE = 492,
        TOK_CONFIG_SEC_ARGUMENT_SEPARATOR = 493,
        TOK_CONFIG_SEC_WEB_APP_ID = 494,
        TOK_CONFIG_SEC_SERVER_SIG = 495,
        TOK_CONFIG_DIR_AUDIT_DIR = 496,
        TOK_CONFIG_DIR_AUDIT_DIR_MOD = 497,
        TOK_CONFIG_DIR_AUDIT_ENG = 498,
        TOK_CONFIG_DIR_AUDIT_FLE_MOD = 499,
        TOK_CONFIG_DIR_AUDIT_LOG = 500,
        TOK_CONFIG_DIR_AUDIT_LOG2 = 501,
        TOK_CONFIG_DIR_AUDIT_LOG_P = 502,
        TOK_CONFIG_DIR_AUDIT_STS = 503,
        TOK_CONFIG_DIR_AUDIT_TPE = 504,
        TOK_CONFIG_DIR_DEBUG_LOG = 505,
        TOK_CONFIG_DIR_DEBUG_LVL = 506,
        TOK_CONFIG_SEC_CACHE_TRANSFORMATIONS = 507,
        TOK_CONFIG_SEC_DISABLE_BACKEND_COMPRESS = 508,
        TOK_CONFIG_SEC_HASH_ENGINE = 509,
        TOK_CONFIG_SEC_HASH_KEY = 510,
        TOK_CONFIG_SEC_HASH_PARAM = 511,
        TOK_CONFIG_SEC_HASH_METHOD_RX = 512,
        TOK_CONFIG_SEC_HASH_METHOD_PM = 513,
        TOK_CONFIG_SEC_CHROOT_DIR = 514,
        TOK_CONFIG_DIR_GEO_DB = 515,
        TOK_CONFIG_DIR_GSB_DB = 516,
        TOK_CONFIG_SEC_GUARDIAN_LOG = 517,
        TOK_CONFIG_DIR_PCRE_MATCH_LIMIT = 518,
        TOK_CONFIG_DIR_PCRE_MATCH_LIMIT_RECURSION = 519,
        TOK_CONFIG_SEC_CONN_R_STATE_LIMIT = 520,
        TOK_CONFIG_SEC_CONN_W_STATE_LIMIT = 521,
        TOK_CONFIG_SEC_SENSOR_ID = 522,
        TOK_CONFIG_DIR_REQ_BODY = 523,
        TOK_CONFIG_DIR_REQ_BODY_IN_MEMORY_LIMIT = 524,
        TOK_CONFIG_DIR_REQ_BODY_LIMIT = 525,
        TOK_CONFIG_DIR_REQ_BODY_LIMIT_ACTION = 526,
        TOK_CONFIG_DIR_REQ_BODY_NO_FILES_LIMIT = 527,
        TOK_CONFIG_DIR_RES_BODY = 528,
        TOK_CONFIG_DIR_RES_BODY_LIMIT = 529,
        TOK_CONFIG_DIR_RES_BODY_LIMIT_ACTION = 530,
        TOK_CONFIG_SEC_RULE_INHERITANCE = 531,
        TOK_CONFIG_SEC_RULE_PERF_TIME = 532,
        TOK_CONFIG_DIR_RULE_ENG = 533,
        TOK_CONFIG_DIR_SEC_ACTION = 534,
        TOK_CONFIG_DIR_SEC_DEFAULT_ACTION = 535,
        TOK_CONFIG_DIR_SEC_MARKER = 536,
        TOK_CONFIG_DIR_UNICODE_MAP_FILE = 537,
        TOK_CONFIG_DIR_UNICODE_CODE_PAGE = 538,
        TOK_CONFIG_SEC_COLLECTION_TIMEOUT = 539,
        TOK_CONFIG_SEC_HTTP_BLKEY = 540,
        TOK_CONFIG_SEC_INTERCEPT_ON_ERROR = 541,
        TOK_CONFIG_SEC_REMOTE_RULES_FAIL_ACTION = 542,
        TOK_CONFIG_SEC_RULE_REMOVE_BY_ID = 543,
        TOK_CONFIG_SEC_RULE_REMOVE_BY_MSG = 544,
        TOK_CONFIG_SEC_RULE_REMOVE_BY_TAG = 545,
        TOK_CONFIG_SEC_RULE_UPDATE_TARGET_BY_TAG = 546,
        TOK_CONFIG_SEC_RULE_UPDATE_TARGET_BY_MSG = 547,
        TOK_CONFIG_SEC_RULE_UPDATE_TARGET_BY_ID = 548,
        TOK_CONFIG_SEC_RULE_UPDATE_ACTION_BY_ID = 549,
        TOK_CONFIG_UPDLOAD_KEEP_FILES = 550,
        TOK_CONFIG_UPDLOAD_SAVE_TMP_FILES = 551,
        TOK_CONFIG_UPLOAD_DIR = 552,
        TOK_CONFIG_UPLOAD_FILE_LIMIT = 553,
        TOK_CONFIG_UPLOAD_FILE_MODE = 554,
        TOK_CONFIG_VALUE_ABORT = 555,
        TOK_CONFIG_VALUE_DETC = 556,
        TOK_CONFIG_VALUE_HTTPS = 557,
        TOK_CONFIG_VALUE_OFF = 558,
        TOK_CONFIG_VALUE_ON = 559,
        TOK_CONFIG_VALUE_PARALLEL = 560,
        TOK_CONFIG_VALUE_PROCESS_PARTIAL = 561,
        TOK_CONFIG_VALUE_REJECT = 562,
        TOK_CONFIG_VALUE_RELEVANT_ONLY = 563,
        TOK_CONFIG_VALUE_SERIAL = 564,
        TOK_CONFIG_VALUE_WARN = 565,
        TOK_CONFIG_XML_EXTERNAL_ENTITY = 566,
        TOK_CONGIG_DIR_RESPONSE_BODY_MP = 567,
        TOK_CONGIG_DIR_SEC_ARG_SEP = 568,
        TOK_CONGIG_DIR_SEC_COOKIE_FORMAT = 569,
        TOK_CONFIG_SEC_COOKIEV0_SEPARATOR = 570,
        TOK_CONGIG_DIR_SEC_DATA_DIR = 571,
        TOK_CONGIG_DIR_SEC_STATUS_ENGINE = 572,
        TOK_CONFIG_SEC_STREAM_IN_BODY_INSPECTION = 573,
        TOK_CONFIG_SEC_STREAM_OUT_BODY_INSPECTION = 574,
        TOK_CONGIG_DIR_SEC_TMP_DIR = 575,
        TOK_DIRECTIVE = 576,
        TOK_DIRECTIVE_SECRULESCRIPT = 577,
        TOK_FREE_TEXT_QUOTE_MACRO_EXPANSION = 578,
        TOK_QUOTATION_MARK = 579,
        TOK_RUN_TIME_VAR_BLD = 580,
        TOK_RUN_TIME_VAR_DUR = 581,
        TOK_RUN_TIME_VAR_HSV = 582,
        TOK_RUN_TIME_VAR_REMOTE_USER = 583,
        TOK_RUN_TIME_VAR_TIME = 584,
        TOK_RUN_TIME_VAR_TIME_DAY = 585,
        TOK_RUN_TIME_VAR_TIME_EPOCH = 586,
        TOK_RUN_TIME_VAR_TIME_HOUR = 587,
        TOK_RUN_TIME_VAR_TIME_MIN = 588,
        TOK_RUN_TIME_VAR_TIME_MON = 589,
        TOK_RUN_TIME_VAR_TIME_SEC = 590,
        TOK_RUN_TIME_VAR_TIME_WDAY = 591,
        TOK_RUN_TIME_VAR_TIME_YEAR = 592,
        TOK_VARIABLE = 593,
        TOK_DICT_ELEMENT = 594,
        TOK_DICT_ELEMENT_REGEXP = 595
      };
    };

    /// (External) token type, as returned by yylex.
    typedef token::yytokentype token_type;

    /// Symbol type: an internal symbol number.
    typedef int symbol_number_type;

    /// The symbol type number to denote an empty symbol.
    enum { empty_symbol = -2 };

    /// Internal symbol number for tokens (subsumed by symbol_number_type).
    typedef unsigned short token_number_type;

    /// A complete symbol.
    ///
    /// Expects its Base type to provide access to the symbol type
    /// via type_get ().
    ///
    /// Provide access to semantic value and location.
    template <typename Base>
    struct basic_symbol : Base
    {
      /// Alias to Base.
      typedef Base super_type;

      /// Default constructor.
      basic_symbol ()
        : value ()
        , location ()
      {}

#if 201103L <= YY_CPLUSPLUS
      /// Move constructor.
      basic_symbol (basic_symbol&& that);
#endif

      /// Copy constructor.
      basic_symbol (const basic_symbol& that);

      /// Constructor for valueless symbols, and symbols from each type.
#if 201103L <= YY_CPLUSPLUS
      basic_symbol (typename Base::kind_type t, location_type&& l)
        : Base (t)
        , location (std::move (l))
      {}
#else
      basic_symbol (typename Base::kind_type t, const location_type& l)
        : Base (t)
        , location (l)
      {}
#endif
#if 201103L <= YY_CPLUSPLUS
      basic_symbol (typename Base::kind_type t, std::string&& v, location_type&& l)
        : Base (t)
        , value (std::move (v))
        , location (std::move (l))
      {}
#else
      basic_symbol (typename Base::kind_type t, const std::string& v, const location_type& l)
        : Base (t)
        , value (v)
        , location (l)
      {}
#endif
#if 201103L <= YY_CPLUSPLUS
      basic_symbol (typename Base::kind_type t, std::unique_ptr<Operator>&& v, location_type&& l)
        : Base (t)
        , value (std::move (v))
        , location (std::move (l))
      {}
#else
      basic_symbol (typename Base::kind_type t, const std::unique_ptr<Operator>& v, const location_type& l)
        : Base (t)
        , value (v)
        , location (l)
      {}
#endif
#if 201103L <= YY_CPLUSPLUS
      basic_symbol (typename Base::kind_type t, std::unique_ptr<RunTimeString>&& v, location_type&& l)
        : Base (t)
        , value (std::move (v))
        , location (std::move (l))
      {}
#else
      basic_symbol (typename Base::kind_type t, const std::unique_ptr<RunTimeString>& v, const location_type& l)
        : Base (t)
        , value (v)
        , location (l)
      {}
#endif
#if 201103L <= YY_CPLUSPLUS
      basic_symbol (typename Base::kind_type t, std::unique_ptr<Variable>&& v, location_type&& l)
        : Base (t)
        , value (std::move (v))
        , location (std::move (l))
      {}
#else
      basic_symbol (typename Base::kind_type t, const std::unique_ptr<Variable>& v, const location_type& l)
        : Base (t)
        , value (v)
        , location (l)
      {}
#endif
#if 201103L <= YY_CPLUSPLUS
      basic_symbol (typename Base::kind_type t, std::unique_ptr<actions::Action>&& v, location_type&& l)
        : Base (t)
        , value (std::move (v))
        , location (std::move (l))
      {}
#else
      basic_symbol (typename Base::kind_type t, const std::unique_ptr<actions::Action>& v, const location_type& l)
        : Base (t)
        , value (v)
        , location (l)
      {}
#endif
#if 201103L <= YY_CPLUSPLUS
      basic_symbol (typename Base::kind_type t, std::unique_ptr<std::vector<std::unique_ptr<Variable> > > && v, location_type&& l)
        : Base (t)
        , value (std::move (v))
        , location (std::move (l))
      {}
#else
      basic_symbol (typename Base::kind_type t, const std::unique_ptr<std::vector<std::unique_ptr<Variable> > > & v, const location_type& l)
        : Base (t)
        , value (v)
        , location (l)
      {}
#endif
#if 201103L <= YY_CPLUSPLUS
      basic_symbol (typename Base::kind_type t, std::unique_ptr<std::vector<std::unique_ptr<actions::Action> > > && v, location_type&& l)
        : Base (t)
        , value (std::move (v))
        , location (std::move (l))
      {}
#else
      basic_symbol (typename Base::kind_type t, const std::unique_ptr<std::vector<std::unique_ptr<actions::Action> > > & v, const location_type& l)
        : Base (t)
        , value (v)
        , location (l)
      {}
#endif

      /// Destroy the symbol.
      ~basic_symbol ()
      {
        clear ();
      }

      /// Destroy contents, and record that is empty.
      void clear ()
      {
        // User destructor.
        symbol_number_type yytype = this->type_get ();
        basic_symbol<Base>& yysym = *this;
        (void) yysym;
        switch (yytype)
        {
       default:
          break;
        }

        // Type destructor.
switch (yytype)
    {
      case 145: // "Accuracy"
      case 146: // "Allow"
      case 147: // "Append"
      case 148: // "AuditLog"
      case 149: // "Block"
      case 150: // "Capture"
      case 151: // "Chain"
      case 152: // "ACTION_CTL_AUDIT_ENGINE"
      case 153: // "ACTION_CTL_AUDIT_LOG_PARTS"
      case 154: // "ACTION_CTL_BDY_JSON"
      case 155: // "ACTION_CTL_BDY_XML"
      case 156: // "ACTION_CTL_BDY_URLENCODED"
      case 157: // "ACTION_CTL_FORCE_REQ_BODY_VAR"
      case 158: // "ACTION_CTL_REQUEST_BODY_ACCESS"
      case 159: // "ACTION_CTL_RULE_REMOVE_BY_ID"
      case 160: // "ACTION_CTL_RULE_REMOVE_BY_TAG"
      case 161: // "ACTION_CTL_RULE_REMOVE_TARGET_BY_ID"
      case 162: // "ACTION_CTL_RULE_REMOVE_TARGET_BY_TAG"
      case 163: // "Deny"
      case 164: // "DeprecateVar"
      case 165: // "Drop"
      case 166: // "Exec"
      case 167: // "ExpireVar"
      case 168: // "Id"
      case 169: // "InitCol"
      case 170: // "Log"
      case 171: // "LogData"
      case 172: // "Maturity"
      case 173: // "Msg"
      case 174: // "MultiMatch"
      case 175: // "NoAuditLog"
      case 176: // "NoLog"
      case 177: // "Pass"
      case 178: // "Pause"
      case 179: // "Phase"
      case 180: // "Prepend"
      case 181: // "Proxy"
      case 182: // "Redirect"
      case 183: // "Rev"
      case 184: // "SanitiseArg"
      case 185: // "SanitiseMatched"
      case 186: // "SanitiseMatchedBytes"
      case 187: // "SanitiseRequestHeader"
      case 188: // "SanitiseResponseHeader"
      case 189: // "SetEnv"
      case 190: // "SetRsc"
      case 191: // "SetSid"
      case 192: // "SetUID"
      case 193: // "Severity"
      case 194: // "Skip"
      case 195: // "SkipAfter"
      case 196: // "Status"
      case 197: // "Tag"
      case 198: // "ACTION_TRANSFORMATION_BASE_64_ENCODE"
      case 199: // "ACTION_TRANSFORMATION_BASE_64_DECODE"
      case 200: // "ACTION_TRANSFORMATION_BASE_64_DECODE_EXT"
      case 201: // "ACTION_TRANSFORMATION_CMD_LINE"
      case 202: // "ACTION_TRANSFORMATION_COMPRESS_WHITESPACE"
      case 203: // "ACTION_TRANSFORMATION_CSS_DECODE"
      case 204: // "ACTION_TRANSFORMATION_ESCAPE_SEQ_DECODE"
      case 205: // "ACTION_TRANSFORMATION_HEX_ENCODE"
      case 206: // "ACTION_TRANSFORMATION_HEX_DECODE"
      case 207: // "ACTION_TRANSFORMATION_HTML_ENTITY_DECODE"
      case 208: // "ACTION_TRANSFORMATION_JS_DECODE"
      case 209: // "ACTION_TRANSFORMATION_LENGTH"
      case 210: // "ACTION_TRANSFORMATION_LOWERCASE"
      case 211: // "ACTION_TRANSFORMATION_MD5"
      case 212: // "ACTION_TRANSFORMATION_NONE"
      case 213: // "ACTION_TRANSFORMATION_NORMALISE_PATH"
      case 214: // "ACTION_TRANSFORMATION_NORMALISE_PATH_WIN"
      case 215: // "ACTION_TRANSFORMATION_PARITY_EVEN_7_BIT"
      case 216: // "ACTION_TRANSFORMATION_PARITY_ODD_7_BIT"
      case 217: // "ACTION_TRANSFORMATION_PARITY_ZERO_7_BIT"
      case 218: // "ACTION_TRANSFORMATION_REMOVE_COMMENTS"
      case 219: // "ACTION_TRANSFORMATION_REMOVE_COMMENTS_CHAR"
      case 220: // "ACTION_TRANSFORMATION_REMOVE_NULLS"
      case 221: // "ACTION_TRANSFORMATION_REMOVE_WHITESPACE"
      case 222: // "ACTION_TRANSFORMATION_REPLACE_COMMENTS"
      case 223: // "ACTION_TRANSFORMATION_REPLACE_NULLS"
      case 224: // "ACTION_TRANSFORMATION_SHA1"
      case 225: // "ACTION_TRANSFORMATION_SQL_HEX_DECODE"
      case 226: // "ACTION_TRANSFORMATION_TRIM"
      case 227: // "ACTION_TRANSFORMATION_TRIM_LEFT"
      case 228: // "ACTION_TRANSFORMATION_TRIM_RIGHT"
      case 229: // "ACTION_TRANSFORMATION_UPPERCASE"
      case 230: // "ACTION_TRANSFORMATION_URL_ENCODE"
      case 231: // "ACTION_TRANSFORMATION_URL_DECODE"
      case 232: // "ACTION_TRANSFORMATION_URL_DECODE_UNI"
      case 233: // "ACTION_TRANSFORMATION_UTF8_TO_UNICODE"
      case 234: // "Ver"
      case 235: // "xmlns"
      case 236: // "CONFIG_COMPONENT_SIG"
      case 237: // "CONFIG_CONN_ENGINE"
      case 238: // "CONFIG_SEC_ARGUMENT_SEPARATOR"
      case 239: // "CONFIG_SEC_WEB_APP_ID"
      case 240: // "CONFIG_SEC_SERVER_SIG"
      case 241: // "CONFIG_DIR_AUDIT_DIR"
      case 242: // "CONFIG_DIR_AUDIT_DIR_MOD"
      case 243: // "CONFIG_DIR_AUDIT_ENG"
      case 244: // "CONFIG_DIR_AUDIT_FLE_MOD"
      case 245: // "CONFIG_DIR_AUDIT_LOG"
      case 246: // "CONFIG_DIR_AUDIT_LOG2"
      case 247: // "CONFIG_DIR_AUDIT_LOG_P"
      case 248: // "CONFIG_DIR_AUDIT_STS"
      case 249: // "CONFIG_DIR_AUDIT_TPE"
      case 250: // "CONFIG_DIR_DEBUG_LOG"
      case 251: // "CONFIG_DIR_DEBUG_LVL"
      case 252: // "CONFIG_SEC_CACHE_TRANSFORMATIONS"
      case 253: // "CONFIG_SEC_DISABLE_BACKEND_COMPRESS"
      case 254: // "CONFIG_SEC_HASH_ENGINE"
      case 255: // "CONFIG_SEC_HASH_KEY"
      case 256: // "CONFIG_SEC_HASH_PARAM"
      case 257: // "CONFIG_SEC_HASH_METHOD_RX"
      case 258: // "CONFIG_SEC_HASH_METHOD_PM"
      case 259: // "CONFIG_SEC_CHROOT_DIR"
      case 260: // "CONFIG_DIR_GEO_DB"
      case 261: // "CONFIG_DIR_GSB_DB"
      case 262: // "CONFIG_SEC_GUARDIAN_LOG"
      case 263: // "CONFIG_DIR_PCRE_MATCH_LIMIT"
      case 264: // "CONFIG_DIR_PCRE_MATCH_LIMIT_RECURSION"
      case 265: // "CONFIG_SEC_CONN_R_STATE_LIMIT"
      case 266: // "CONFIG_SEC_CONN_W_STATE_LIMIT"
      case 267: // "CONFIG_SEC_SENSOR_ID"
      case 268: // "CONFIG_DIR_REQ_BODY"
      case 269: // "CONFIG_DIR_REQ_BODY_IN_MEMORY_LIMIT"
      case 270: // "CONFIG_DIR_REQ_BODY_LIMIT"
      case 271: // "CONFIG_DIR_REQ_BODY_LIMIT_ACTION"
      case 272: // "CONFIG_DIR_REQ_BODY_NO_FILES_LIMIT"
      case 273: // "CONFIG_DIR_RES_BODY"
      case 274: // "CONFIG_DIR_RES_BODY_LIMIT"
      case 275: // "CONFIG_DIR_RES_BODY_LIMIT_ACTION"
      case 276: // "CONFIG_SEC_RULE_INHERITANCE"
      case 277: // "CONFIG_SEC_RULE_PERF_TIME"
      case 278: // "CONFIG_DIR_RULE_ENG"
      case 279: // "CONFIG_DIR_SEC_ACTION"
      case 280: // "CONFIG_DIR_SEC_DEFAULT_ACTION"
      case 281: // "CONFIG_DIR_SEC_MARKER"
      case 282: // "CONFIG_DIR_UNICODE_MAP_FILE"
      case 283: // "CONFIG_DIR_UNICODE_CODE_PAGE"
      case 284: // "CONFIG_SEC_COLLECTION_TIMEOUT"
      case 285: // "CONFIG_SEC_HTTP_BLKEY"
      case 286: // "CONFIG_SEC_INTERCEPT_ON_ERROR"
      case 287: // "CONFIG_SEC_REMOTE_RULES_FAIL_ACTION"
      case 288: // "CONFIG_SEC_RULE_REMOVE_BY_ID"
      case 289: // "CONFIG_SEC_RULE_REMOVE_BY_MSG"
      case 290: // "CONFIG_SEC_RULE_REMOVE_BY_TAG"
      case 291: // "CONFIG_SEC_RULE_UPDATE_TARGET_BY_TAG"
      case 292: // "CONFIG_SEC_RULE_UPDATE_TARGET_BY_MSG"
      case 293: // "CONFIG_SEC_RULE_UPDATE_TARGET_BY_ID"
      case 294: // "CONFIG_SEC_RULE_UPDATE_ACTION_BY_ID"
      case 295: // "CONFIG_UPDLOAD_KEEP_FILES"
      case 296: // "CONFIG_UPDLOAD_SAVE_TMP_FILES"
      case 297: // "CONFIG_UPLOAD_DIR"
      case 298: // "CONFIG_UPLOAD_FILE_LIMIT"
      case 299: // "CONFIG_UPLOAD_FILE_MODE"
      case 300: // "CONFIG_VALUE_ABORT"
      case 301: // "CONFIG_VALUE_DETC"
      case 302: // "CONFIG_VALUE_HTTPS"
      case 303: // "CONFIG_VALUE_OFF"
      case 304: // "CONFIG_VALUE_ON"
      case 305: // "CONFIG_VALUE_PARALLEL"
      case 306: // "CONFIG_VALUE_PROCESS_PARTIAL"
      case 307: // "CONFIG_VALUE_REJECT"
      case 308: // "CONFIG_VALUE_RELEVANT_ONLY"
      case 309: // "CONFIG_VALUE_SERIAL"
      case 310: // "CONFIG_VALUE_WARN"
      case 311: // "CONFIG_XML_EXTERNAL_ENTITY"
      case 312: // "CONGIG_DIR_RESPONSE_BODY_MP"
      case 313: // "CONGIG_DIR_SEC_ARG_SEP"
      case 314: // "CONGIG_DIR_SEC_COOKIE_FORMAT"
      case 315: // "CONFIG_SEC_COOKIEV0_SEPARATOR"
      case 316: // "CONGIG_DIR_SEC_DATA_DIR"
      case 317: // "CONGIG_DIR_SEC_STATUS_ENGINE"
      case 318: // "CONFIG_SEC_STREAM_IN_BODY_INSPECTION"
      case 319: // "CONFIG_SEC_STREAM_OUT_BODY_INSPECTION"
      case 320: // "CONGIG_DIR_SEC_TMP_DIR"
      case 321: // "DIRECTIVE"
      case 322: // "DIRECTIVE_SECRULESCRIPT"
      case 323: // "FREE_TEXT_QUOTE_MACRO_EXPANSION"
      case 324: // "QUOTATION_MARK"
      case 325: // "RUN_TIME_VAR_BLD"
      case 326: // "RUN_TIME_VAR_DUR"
      case 327: // "RUN_TIME_VAR_HSV"
      case 328: // "RUN_TIME_VAR_REMOTE_USER"
      case 329: // "RUN_TIME_VAR_TIME"
      case 330: // "RUN_TIME_VAR_TIME_DAY"
      case 331: // "RUN_TIME_VAR_TIME_EPOCH"
      case 332: // "RUN_TIME_VAR_TIME_HOUR"
      case 333: // "RUN_TIME_VAR_TIME_MIN"
      case 334: // "RUN_TIME_VAR_TIME_MON"
      case 335: // "RUN_TIME_VAR_TIME_SEC"
      case 336: // "RUN_TIME_VAR_TIME_WDAY"
      case 337: // "RUN_TIME_VAR_TIME_YEAR"
      case 338: // "VARIABLE"
      case 339: // "Dictionary element"
      case 340: // "Dictionary element, selected by regexp"
        value.template destroy< std::string > ();
        break;

      case 347: // op
      case 348: // op_before_init
        value.template destroy< std::unique_ptr<Operator> > ();
        break;

      case 356: // run_time_string
        value.template destroy< std::unique_ptr<RunTimeString> > ();
        break;

      case 353: // var
        value.template destroy< std::unique_ptr<Variable> > ();
        break;

      case 354: // act
      case 355: // setvar_action
        value.template destroy< std::unique_ptr<actions::Action> > ();
        break;

      case 350: // variables
      case 351: // variables_pre_process
      case 352: // variables_may_be_quoted
        value.template destroy< std::unique_ptr<std::vector<std::unique_ptr<Variable> > >  > ();
        break;

      case 345: // actions
      case 346: // actions_may_quoted
        value.template destroy< std::unique_ptr<std::vector<std::unique_ptr<actions::Action> > >  > ();
        break;

      default:
        break;
    }

        Base::clear ();
      }

      /// Whether empty.
      bool empty () const YY_NOEXCEPT;

      /// Destructive move, \a s is emptied into this.
      void move (basic_symbol& s);

      /// The semantic value.
      semantic_type value;

      /// The location.
      location_type location;

    private:
#if YY_CPLUSPLUS < 201103L
      /// Assignment operator.
      basic_symbol& operator= (const basic_symbol& that);
#endif
    };

    /// Type access provider for token (enum) based symbols.
    struct by_type
    {
      /// Default constructor.
      by_type ();

#if 201103L <= YY_CPLUSPLUS
      /// Move constructor.
      by_type (by_type&& that);
#endif

      /// Copy constructor.
      by_type (const by_type& that);

      /// The symbol type as needed by the constructor.
      typedef token_type kind_type;

      /// Constructor from (external) token numbers.
      by_type (kind_type t);

      /// Record that this symbol is empty.
      void clear ();

      /// Steal the symbol type from \a that.
      void move (by_type& that);

      /// The (internal) type number (corresponding to \a type).
      /// \a empty when empty.
      symbol_number_type type_get () const YY_NOEXCEPT;

      /// The token.
      token_type token () const YY_NOEXCEPT;

      /// The symbol type.
      /// \a empty_symbol when empty.
      /// An int, not token_number_type, to be able to store empty_symbol.
      int type;
    };

    /// "External" symbols: returned by the scanner.
    struct symbol_type : basic_symbol<by_type>
    {
      /// Superclass.
      typedef basic_symbol<by_type> super_type;

      /// Empty symbol.
      symbol_type () {}

      /// Constructor for valueless symbols, and symbols from each type.
#if 201103L <= YY_CPLUSPLUS
      symbol_type (int tok, location_type l)
        : super_type(token_type (tok), std::move (l))
      {
        YYASSERT (tok == token::TOK_END || tok == token::TOK_COMMA || tok == token::TOK_CONFIG_CONTENT_INJECTION || tok == token::TOK_CONGIG_DIR_RESPONSE_BODY_MP_CLEAR || tok == token::TOK_PIPE || tok == token::TOK_NEW_LINE || tok == token::TOK_VAR_COUNT || tok == token::TOK_VAR_EXCLUSION || tok == token::TOK_VARIABLE_ARGS || tok == token::TOK_VARIABLE_ARGS_POST || tok == token::TOK_VARIABLE_ARGS_GET || tok == token::TOK_VARIABLE_FILES_SIZES || tok == token::TOK_VARIABLE_FILES_NAMES || tok == token::TOK_VARIABLE_FILES_TMP_CONTENT || tok == token::TOK_VARIABLE_MULTIPART_FILENAME || tok == token::TOK_VARIABLE_MULTIPART_NAME || tok == token::TOK_VARIABLE_MATCHED_VARS_NAMES || tok == token::TOK_VARIABLE_MATCHED_VARS || tok == token::TOK_VARIABLE_FILES || tok == token::TOK_VARIABLE_REQUEST_COOKIES || tok == token::TOK_VARIABLE_REQUEST_HEADERS || tok == token::TOK_VARIABLE_RESPONSE_HEADERS || tok == token::TOK_VARIABLE_GEO || tok == token::TOK_VARIABLE_REQUEST_COOKIES_NAMES || tok == token::TOK_VARIABLE_ARGS_COMBINED_SIZE || tok == token::TOK_VARIABLE_ARGS_GET_NAMES || tok == token::TOK_VARIABLE_RULE || tok == token::TOK_VARIABLE_ARGS_NAMES || tok == token::TOK_VARIABLE_ARGS_POST_NAMES || tok == token::TOK_VARIABLE_AUTH_TYPE || tok == token::TOK_VARIABLE_FILES_COMBINED_SIZE || tok == token::TOK_VARIABLE_FILES_TMP_NAMES || tok == token::TOK_VARIABLE_FULL_REQUEST || tok == token::TOK_VARIABLE_FULL_REQUEST_LENGTH || tok == token::TOK_VARIABLE_INBOUND_DATA_ERROR || tok == token::TOK_VARIABLE_MATCHED_VAR || tok == token::TOK_VARIABLE_MATCHED_VAR_NAME || tok == token::TOK_VARIABLE_MULTIPART_BOUNDARY_QUOTED || tok == token::TOK_VARIABLE_MULTIPART_BOUNDARY_WHITESPACE || tok == token::TOK_VARIABLE_MULTIPART_CRLF_LF_LINES || tok == token::TOK_VARIABLE_MULTIPART_DATA_AFTER || tok == token::TOK_VARIABLE_MULTIPART_DATA_BEFORE || tok == token::TOK_VARIABLE_MULTIPART_FILE_LIMIT_EXCEEDED || tok == token::TOK_VARIABLE_MULTIPART_HEADER_FOLDING || tok == token::TOK_VARIABLE_MULTIPART_INVALID_HEADER_FOLDING || tok == token::TOK_VARIABLE_MULTIPART_INVALID_PART || tok == token::TOK_VARIABLE_MULTIPART_INVALID_QUOTING || tok == token::TOK_VARIABLE_MULTIPART_LF_LINE || tok == token::TOK_VARIABLE_MULTIPART_MISSING_SEMICOLON || tok == token::TOK_VARIABLE_MULTIPART_SEMICOLON_MISSING || tok == token::TOK_VARIABLE_MULTIPART_STRICT_ERROR || tok == token::TOK_VARIABLE_MULTIPART_UNMATCHED_BOUNDARY || tok == token::TOK_VARIABLE_OUTBOUND_DATA_ERROR || tok == token::TOK_VARIABLE_PATH_INFO || tok == token::TOK_VARIABLE_QUERY_STRING || tok == token::TOK_VARIABLE_REMOTE_ADDR || tok == token::TOK_VARIABLE_REMOTE_HOST || tok == token::TOK_VARIABLE_REMOTE_PORT || tok == token::TOK_VARIABLE_REQBODY_ERROR_MSG || tok == token::TOK_VARIABLE_REQBODY_ERROR || tok == token::TOK_VARIABLE_REQBODY_PROCESSOR_ERROR_MSG || tok == token::TOK_VARIABLE_REQBODY_PROCESSOR_ERROR || tok == token::TOK_VARIABLE_REQBODY_PROCESSOR || tok == token::TOK_VARIABLE_REQUEST_BASENAME || tok == token::TOK_VARIABLE_REQUEST_BODY_LENGTH || tok == token::TOK_VARIABLE_REQUEST_BODY || tok == token::TOK_VARIABLE_REQUEST_FILE_NAME || tok == token::TOK_VARIABLE_REQUEST_HEADERS_NAMES || tok == token::TOK_VARIABLE_REQUEST_LINE || tok == token::TOK_VARIABLE_REQUEST_METHOD || tok == token::TOK_VARIABLE_REQUEST_PROTOCOL || tok == token::TOK_VARIABLE_REQUEST_URI_RAW || tok == token::TOK_VARIABLE_REQUEST_URI || tok == token::TOK_VARIABLE_RESOURCE || tok == token::TOK_VARIABLE_RESPONSE_BODY || tok == token::TOK_VARIABLE_RESPONSE_CONTENT_LENGTH || tok == token::TOK_VARIABLE_RESPONSE_CONTENT_TYPE || tok == token::TOK_VARIABLE_RESPONSE_HEADERS_NAMES || tok == token::TOK_VARIABLE_RESPONSE_PROTOCOL || tok == token::TOK_VARIABLE_RESPONSE_STATUS || tok == token::TOK_VARIABLE_SERVER_ADDR || tok == token::TOK_VARIABLE_SERVER_NAME || tok == token::TOK_VARIABLE_SERVER_PORT || tok == token::TOK_VARIABLE_SESSION_ID || tok == token::TOK_VARIABLE_UNIQUE_ID || tok == token::TOK_VARIABLE_URL_ENCODED_ERROR || tok == token::TOK_VARIABLE_USER_ID || tok == token::TOK_VARIABLE_WEB_APP_ID || tok == token::TOK_VARIABLE_STATUS || tok == token::TOK_VARIABLE_STATUS_LINE || tok == token::TOK_VARIABLE_IP || tok == token::TOK_VARIABLE_GLOBAL || tok == token::TOK_VARIABLE_TX || tok == token::TOK_VARIABLE_SESSION || tok == token::TOK_VARIABLE_USER || tok == token::TOK_RUN_TIME_VAR_ENV || tok == token::TOK_RUN_TIME_VAR_XML || tok == token::TOK_ACTION_SETVAR || tok == token::TOK_SETVAR_OPERATION_EQUALS || tok == token::TOK_SETVAR_OPERATION_EQUALS_PLUS || tok == token::TOK_SETVAR_OPERATION_EQUALS_MINUS || tok == token::TOK_NOT || tok == token::TOK_OPERATOR_BEGINS_WITH || tok == token::TOK_OPERATOR_CONTAINS || tok == token::TOK_OPERATOR_CONTAINS_WORD || tok == token::TOK_OPERATOR_DETECT_SQLI || tok == token::TOK_OPERATOR_DETECT_XSS || tok == token::TOK_OPERATOR_ENDS_WITH || tok == token::TOK_OPERATOR_EQ || tok == token::TOK_OPERATOR_FUZZY_HASH || tok == token::TOK_OPERATOR_GEOLOOKUP || tok == token::TOK_OPERATOR_GE || tok == token::TOK_OPERATOR_GSB_LOOKUP || tok == token::TOK_OPERATOR_GT || tok == token::TOK_OPERATOR_INSPECT_FILE || tok == token::TOK_OPERATOR_IP_MATCH_FROM_FILE || tok == token::TOK_OPERATOR_IP_MATCH || tok == token::TOK_OPERATOR_LE || tok == token::TOK_OPERATOR_LT || tok == token::TOK_OPERATOR_PM_FROM_FILE || tok == token::TOK_OPERATOR_PM || tok == token::TOK_OPERATOR_RBL || tok == token::TOK_OPERATOR_RSUB || tok == token::TOK_OPERATOR_RX_CONTENT_ONLY || tok == token::TOK_OPERATOR_RX || tok == token::TOK_OPERATOR_STR_EQ || tok == token::TOK_OPERATOR_STR_MATCH || tok == token::TOK_OPERATOR_UNCONDITIONAL_MATCH || tok == token::TOK_OPERATOR_VALIDATE_BYTE_RANGE || tok == token::TOK_OPERATOR_VALIDATE_DTD || tok == token::TOK_OPERATOR_VALIDATE_HASH || tok == token::TOK_OPERATOR_VALIDATE_SCHEMA || tok == token::TOK_OPERATOR_VALIDATE_URL_ENCODING || tok == token::TOK_OPERATOR_VALIDATE_UTF8_ENCODING || tok == token::TOK_OPERATOR_VERIFY_CC || tok == token::TOK_OPERATOR_VERIFY_CPF || tok == token::TOK_OPERATOR_VERIFY_SSN || tok == token::TOK_OPERATOR_VERIFY_SVNR || tok == token::TOK_OPERATOR_WITHIN || tok == token::TOK_CONFIG_DIR_AUDIT_LOG_FMT || tok == token::TOK_JSON || tok == token::TOK_NATIVE || tok == token::TOK_ACTION_CTL_RULE_ENGINE);
      }
#else
      symbol_type (int tok, const location_type& l)
        : super_type(token_type (tok), l)
      {
        YYASSERT (tok == token::TOK_END || tok == token::TOK_COMMA || tok == token::TOK_CONFIG_CONTENT_INJECTION || tok == token::TOK_CONGIG_DIR_RESPONSE_BODY_MP_CLEAR || tok == token::TOK_PIPE || tok == token::TOK_NEW_LINE || tok == token::TOK_VAR_COUNT || tok == token::TOK_VAR_EXCLUSION || tok == token::TOK_VARIABLE_ARGS || tok == token::TOK_VARIABLE_ARGS_POST || tok == token::TOK_VARIABLE_ARGS_GET || tok == token::TOK_VARIABLE_FILES_SIZES || tok == token::TOK_VARIABLE_FILES_NAMES || tok == token::TOK_VARIABLE_FILES_TMP_CONTENT || tok == token::TOK_VARIABLE_MULTIPART_FILENAME || tok == token::TOK_VARIABLE_MULTIPART_NAME || tok == token::TOK_VARIABLE_MATCHED_VARS_NAMES || tok == token::TOK_VARIABLE_MATCHED_VARS || tok == token::TOK_VARIABLE_FILES || tok == token::TOK_VARIABLE_REQUEST_COOKIES || tok == token::TOK_VARIABLE_REQUEST_HEADERS || tok == token::TOK_VARIABLE_RESPONSE_HEADERS || tok == token::TOK_VARIABLE_GEO || tok == token::TOK_VARIABLE_REQUEST_COOKIES_NAMES || tok == token::TOK_VARIABLE_ARGS_COMBINED_SIZE || tok == token::TOK_VARIABLE_ARGS_GET_NAMES || tok == token::TOK_VARIABLE_RULE || tok == token::TOK_VARIABLE_ARGS_NAMES || tok == token::TOK_VARIABLE_ARGS_POST_NAMES || tok == token::TOK_VARIABLE_AUTH_TYPE || tok == token::TOK_VARIABLE_FILES_COMBINED_SIZE || tok == token::TOK_VARIABLE_FILES_TMP_NAMES || tok == token::TOK_VARIABLE_FULL_REQUEST || tok == token::TOK_VARIABLE_FULL_REQUEST_LENGTH || tok == token::TOK_VARIABLE_INBOUND_DATA_ERROR || tok == token::TOK_VARIABLE_MATCHED_VAR || tok == token::TOK_VARIABLE_MATCHED_VAR_NAME || tok == token::TOK_VARIABLE_MULTIPART_BOUNDARY_QUOTED || tok == token::TOK_VARIABLE_MULTIPART_BOUNDARY_WHITESPACE || tok == token::TOK_VARIABLE_MULTIPART_CRLF_LF_LINES || tok == token::TOK_VARIABLE_MULTIPART_DATA_AFTER || tok == token::TOK_VARIABLE_MULTIPART_DATA_BEFORE || tok == token::TOK_VARIABLE_MULTIPART_FILE_LIMIT_EXCEEDED || tok == token::TOK_VARIABLE_MULTIPART_HEADER_FOLDING || tok == token::TOK_VARIABLE_MULTIPART_INVALID_HEADER_FOLDING || tok == token::TOK_VARIABLE_MULTIPART_INVALID_PART || tok == token::TOK_VARIABLE_MULTIPART_INVALID_QUOTING || tok == token::TOK_VARIABLE_MULTIPART_LF_LINE || tok == token::TOK_VARIABLE_MULTIPART_MISSING_SEMICOLON || tok == token::TOK_VARIABLE_MULTIPART_SEMICOLON_MISSING || tok == token::TOK_VARIABLE_MULTIPART_STRICT_ERROR || tok == token::TOK_VARIABLE_MULTIPART_UNMATCHED_BOUNDARY || tok == token::TOK_VARIABLE_OUTBOUND_DATA_ERROR || tok == token::TOK_VARIABLE_PATH_INFO || tok == token::TOK_VARIABLE_QUERY_STRING || tok == token::TOK_VARIABLE_REMOTE_ADDR || tok == token::TOK_VARIABLE_REMOTE_HOST || tok == token::TOK_VARIABLE_REMOTE_PORT || tok == token::TOK_VARIABLE_REQBODY_ERROR_MSG || tok == token::TOK_VARIABLE_REQBODY_ERROR || tok == token::TOK_VARIABLE_REQBODY_PROCESSOR_ERROR_MSG || tok == token::TOK_VARIABLE_REQBODY_PROCESSOR_ERROR || tok == token::TOK_VARIABLE_REQBODY_PROCESSOR || tok == token::TOK_VARIABLE_REQUEST_BASENAME || tok == token::TOK_VARIABLE_REQUEST_BODY_LENGTH || tok == token::TOK_VARIABLE_REQUEST_BODY || tok == token::TOK_VARIABLE_REQUEST_FILE_NAME || tok == token::TOK_VARIABLE_REQUEST_HEADERS_NAMES || tok == token::TOK_VARIABLE_REQUEST_LINE || tok == token::TOK_VARIABLE_REQUEST_METHOD || tok == token::TOK_VARIABLE_REQUEST_PROTOCOL || tok == token::TOK_VARIABLE_REQUEST_URI_RAW || tok == token::TOK_VARIABLE_REQUEST_URI || tok == token::TOK_VARIABLE_RESOURCE || tok == token::TOK_VARIABLE_RESPONSE_BODY || tok == token::TOK_VARIABLE_RESPONSE_CONTENT_LENGTH || tok == token::TOK_VARIABLE_RESPONSE_CONTENT_TYPE || tok == token::TOK_VARIABLE_RESPONSE_HEADERS_NAMES || tok == token::TOK_VARIABLE_RESPONSE_PROTOCOL || tok == token::TOK_VARIABLE_RESPONSE_STATUS || tok == token::TOK_VARIABLE_SERVER_ADDR || tok == token::TOK_VARIABLE_SERVER_NAME || tok == token::TOK_VARIABLE_SERVER_PORT || tok == token::TOK_VARIABLE_SESSION_ID || tok == token::TOK_VARIABLE_UNIQUE_ID || tok == token::TOK_VARIABLE_URL_ENCODED_ERROR || tok == token::TOK_VARIABLE_USER_ID || tok == token::TOK_VARIABLE_WEB_APP_ID || tok == token::TOK_VARIABLE_STATUS || tok == token::TOK_VARIABLE_STATUS_LINE || tok == token::TOK_VARIABLE_IP || tok == token::TOK_VARIABLE_GLOBAL || tok == token::TOK_VARIABLE_TX || tok == token::TOK_VARIABLE_SESSION || tok == token::TOK_VARIABLE_USER || tok == token::TOK_RUN_TIME_VAR_ENV || tok == token::TOK_RUN_TIME_VAR_XML || tok == token::TOK_ACTION_SETVAR || tok == token::TOK_SETVAR_OPERATION_EQUALS || tok == token::TOK_SETVAR_OPERATION_EQUALS_PLUS || tok == token::TOK_SETVAR_OPERATION_EQUALS_MINUS || tok == token::TOK_NOT || tok == token::TOK_OPERATOR_BEGINS_WITH || tok == token::TOK_OPERATOR_CONTAINS || tok == token::TOK_OPERATOR_CONTAINS_WORD || tok == token::TOK_OPERATOR_DETECT_SQLI || tok == token::TOK_OPERATOR_DETECT_XSS || tok == token::TOK_OPERATOR_ENDS_WITH || tok == token::TOK_OPERATOR_EQ || tok == token::TOK_OPERATOR_FUZZY_HASH || tok == token::TOK_OPERATOR_GEOLOOKUP || tok == token::TOK_OPERATOR_GE || tok == token::TOK_OPERATOR_GSB_LOOKUP || tok == token::TOK_OPERATOR_GT || tok == token::TOK_OPERATOR_INSPECT_FILE || tok == token::TOK_OPERATOR_IP_MATCH_FROM_FILE || tok == token::TOK_OPERATOR_IP_MATCH || tok == token::TOK_OPERATOR_LE || tok == token::TOK_OPERATOR_LT || tok == token::TOK_OPERATOR_PM_FROM_FILE || tok == token::TOK_OPERATOR_PM || tok == token::TOK_OPERATOR_RBL || tok == token::TOK_OPERATOR_RSUB || tok == token::TOK_OPERATOR_RX_CONTENT_ONLY || tok == token::TOK_OPERATOR_RX || tok == token::TOK_OPERATOR_STR_EQ || tok == token::TOK_OPERATOR_STR_MATCH || tok == token::TOK_OPERATOR_UNCONDITIONAL_MATCH || tok == token::TOK_OPERATOR_VALIDATE_BYTE_RANGE || tok == token::TOK_OPERATOR_VALIDATE_DTD || tok == token::TOK_OPERATOR_VALIDATE_HASH || tok == token::TOK_OPERATOR_VALIDATE_SCHEMA || tok == token::TOK_OPERATOR_VALIDATE_URL_ENCODING || tok == token::TOK_OPERATOR_VALIDATE_UTF8_ENCODING || tok == token::TOK_OPERATOR_VERIFY_CC || tok == token::TOK_OPERATOR_VERIFY_CPF || tok == token::TOK_OPERATOR_VERIFY_SSN || tok == token::TOK_OPERATOR_VERIFY_SVNR || tok == token::TOK_OPERATOR_WITHIN || tok == token::TOK_CONFIG_DIR_AUDIT_LOG_FMT || tok == token::TOK_JSON || tok == token::TOK_NATIVE || tok == token::TOK_ACTION_CTL_RULE_ENGINE);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      symbol_type (int tok, std::string v, location_type l)
        : super_type(token_type (tok), std::move (v), std::move (l))
      {
        YYASSERT (tok == token::TOK_ACTION_ACCURACY || tok == token::TOK_ACTION_ALLOW || tok == token::TOK_ACTION_APPEND || tok == token::TOK_ACTION_AUDIT_LOG || tok == token::TOK_ACTION_BLOCK || tok == token::TOK_ACTION_CAPTURE || tok == token::TOK_ACTION_CHAIN || tok == token::TOK_ACTION_CTL_AUDIT_ENGINE || tok == token::TOK_ACTION_CTL_AUDIT_LOG_PARTS || tok == token::TOK_ACTION_CTL_BDY_JSON || tok == token::TOK_ACTION_CTL_BDY_XML || tok == token::TOK_ACTION_CTL_BDY_URLENCODED || tok == token::TOK_ACTION_CTL_FORCE_REQ_BODY_VAR || tok == token::TOK_ACTION_CTL_REQUEST_BODY_ACCESS || tok == token::TOK_ACTION_CTL_RULE_REMOVE_BY_ID || tok == token::TOK_ACTION_CTL_RULE_REMOVE_BY_TAG || tok == token::TOK_ACTION_CTL_RULE_REMOVE_TARGET_BY_ID || tok == token::TOK_ACTION_CTL_RULE_REMOVE_TARGET_BY_TAG || tok == token::TOK_ACTION_DENY || tok == token::TOK_ACTION_DEPRECATE_VAR || tok == token::TOK_ACTION_DROP || tok == token::TOK_ACTION_EXEC || tok == token::TOK_ACTION_EXPIRE_VAR || tok == token::TOK_ACTION_ID || tok == token::TOK_ACTION_INITCOL || tok == token::TOK_ACTION_LOG || tok == token::TOK_ACTION_LOG_DATA || tok == token::TOK_ACTION_MATURITY || tok == token::TOK_ACTION_MSG || tok == token::TOK_ACTION_MULTI_MATCH || tok == token::TOK_ACTION_NO_AUDIT_LOG || tok == token::TOK_ACTION_NO_LOG || tok == token::TOK_ACTION_PASS || tok == token::TOK_ACTION_PAUSE || tok == token::TOK_ACTION_PHASE || tok == token::TOK_ACTION_PREPEND || tok == token::TOK_ACTION_PROXY || tok == token::TOK_ACTION_REDIRECT || tok == token::TOK_ACTION_REV || tok == token::TOK_ACTION_SANITISE_ARG || tok == token::TOK_ACTION_SANITISE_MATCHED || tok == token::TOK_ACTION_SANITISE_MATCHED_BYTES || tok == token::TOK_ACTION_SANITISE_REQUEST_HEADER || tok == token::TOK_ACTION_SANITISE_RESPONSE_HEADER || tok == token::TOK_ACTION_SETENV || tok == token::TOK_ACTION_SETRSC || tok == token::TOK_ACTION_SETSID || tok == token::TOK_ACTION_SETUID || tok == token::TOK_ACTION_SEVERITY || tok == token::TOK_ACTION_SKIP || tok == token::TOK_ACTION_SKIP_AFTER || tok == token::TOK_ACTION_STATUS || tok == token::TOK_ACTION_TAG || tok == token::TOK_ACTION_TRANSFORMATION_BASE_64_ENCODE || tok == token::TOK_ACTION_TRANSFORMATION_BASE_64_DECODE || tok == token::TOK_ACTION_TRANSFORMATION_BASE_64_DECODE_EXT || tok == token::TOK_ACTION_TRANSFORMATION_CMD_LINE || tok == token::TOK_ACTION_TRANSFORMATION_COMPRESS_WHITESPACE || tok == token::TOK_ACTION_TRANSFORMATION_CSS_DECODE || tok == token::TOK_ACTION_TRANSFORMATION_ESCAPE_SEQ_DECODE || tok == token::TOK_ACTION_TRANSFORMATION_HEX_ENCODE || tok == token::TOK_ACTION_TRANSFORMATION_HEX_DECODE || tok == token::TOK_ACTION_TRANSFORMATION_HTML_ENTITY_DECODE || tok == token::TOK_ACTION_TRANSFORMATION_JS_DECODE || tok == token::TOK_ACTION_TRANSFORMATION_LENGTH || tok == token::TOK_ACTION_TRANSFORMATION_LOWERCASE || tok == token::TOK_ACTION_TRANSFORMATION_MD5 || tok == token::TOK_ACTION_TRANSFORMATION_NONE || tok == token::TOK_ACTION_TRANSFORMATION_NORMALISE_PATH || tok == token::TOK_ACTION_TRANSFORMATION_NORMALISE_PATH_WIN || tok == token::TOK_ACTION_TRANSFORMATION_PARITY_EVEN_7_BIT || tok == token::TOK_ACTION_TRANSFORMATION_PARITY_ODD_7_BIT || tok == token::TOK_ACTION_TRANSFORMATION_PARITY_ZERO_7_BIT || tok == token::TOK_ACTION_TRANSFORMATION_REMOVE_COMMENTS || tok == token::TOK_ACTION_TRANSFORMATION_REMOVE_COMMENTS_CHAR || tok == token::TOK_ACTION_TRANSFORMATION_REMOVE_NULLS || tok == token::TOK_ACTION_TRANSFORMATION_REMOVE_WHITESPACE || tok == token::TOK_ACTION_TRANSFORMATION_REPLACE_COMMENTS || tok == token::TOK_ACTION_TRANSFORMATION_REPLACE_NULLS || tok == token::TOK_ACTION_TRANSFORMATION_SHA1 || tok == token::TOK_ACTION_TRANSFORMATION_SQL_HEX_DECODE || tok == token::TOK_ACTION_TRANSFORMATION_TRIM || tok == token::TOK_ACTION_TRANSFORMATION_TRIM_LEFT || tok == token::TOK_ACTION_TRANSFORMATION_TRIM_RIGHT || tok == token::TOK_ACTION_TRANSFORMATION_UPPERCASE || tok == token::TOK_ACTION_TRANSFORMATION_URL_ENCODE || tok == token::TOK_ACTION_TRANSFORMATION_URL_DECODE || tok == token::TOK_ACTION_TRANSFORMATION_URL_DECODE_UNI || tok == token::TOK_ACTION_TRANSFORMATION_UTF8_TO_UNICODE || tok == token::TOK_ACTION_VER || tok == token::TOK_ACTION_XMLNS || tok == token::TOK_CONFIG_COMPONENT_SIG || tok == token::TOK_CONFIG_CONN_ENGINE || tok == token::TOK_CONFIG_SEC_ARGUMENT_SEPARATOR || tok == token::TOK_CONFIG_SEC_WEB_APP_ID || tok == token::TOK_CONFIG_SEC_SERVER_SIG || tok == token::TOK_CONFIG_DIR_AUDIT_DIR || tok == token::TOK_CONFIG_DIR_AUDIT_DIR_MOD || tok == token::TOK_CONFIG_DIR_AUDIT_ENG || tok == token::TOK_CONFIG_DIR_AUDIT_FLE_MOD || tok == token::TOK_CONFIG_DIR_AUDIT_LOG || tok == token::TOK_CONFIG_DIR_AUDIT_LOG2 || tok == token::TOK_CONFIG_DIR_AUDIT_LOG_P || tok == token::TOK_CONFIG_DIR_AUDIT_STS || tok == token::TOK_CONFIG_DIR_AUDIT_TPE || tok == token::TOK_CONFIG_DIR_DEBUG_LOG || tok == token::TOK_CONFIG_DIR_DEBUG_LVL || tok == token::TOK_CONFIG_SEC_CACHE_TRANSFORMATIONS || tok == token::TOK_CONFIG_SEC_DISABLE_BACKEND_COMPRESS || tok == token::TOK_CONFIG_SEC_HASH_ENGINE || tok == token::TOK_CONFIG_SEC_HASH_KEY || tok == token::TOK_CONFIG_SEC_HASH_PARAM || tok == token::TOK_CONFIG_SEC_HASH_METHOD_RX || tok == token::TOK_CONFIG_SEC_HASH_METHOD_PM || tok == token::TOK_CONFIG_SEC_CHROOT_DIR || tok == token::TOK_CONFIG_DIR_GEO_DB || tok == token::TOK_CONFIG_DIR_GSB_DB || tok == token::TOK_CONFIG_SEC_GUARDIAN_LOG || tok == token::TOK_CONFIG_DIR_PCRE_MATCH_LIMIT || tok == token::TOK_CONFIG_DIR_PCRE_MATCH_LIMIT_RECURSION || tok == token::TOK_CONFIG_SEC_CONN_R_STATE_LIMIT || tok == token::TOK_CONFIG_SEC_CONN_W_STATE_LIMIT || tok == token::TOK_CONFIG_SEC_SENSOR_ID || tok == token::TOK_CONFIG_DIR_REQ_BODY || tok == token::TOK_CONFIG_DIR_REQ_BODY_IN_MEMORY_LIMIT || tok == token::TOK_CONFIG_DIR_REQ_BODY_LIMIT || tok == token::TOK_CONFIG_DIR_REQ_BODY_LIMIT_ACTION || tok == token::TOK_CONFIG_DIR_REQ_BODY_NO_FILES_LIMIT || tok == token::TOK_CONFIG_DIR_RES_BODY || tok == token::TOK_CONFIG_DIR_RES_BODY_LIMIT || tok == token::TOK_CONFIG_DIR_RES_BODY_LIMIT_ACTION || tok == token::TOK_CONFIG_SEC_RULE_INHERITANCE || tok == token::TOK_CONFIG_SEC_RULE_PERF_TIME || tok == token::TOK_CONFIG_DIR_RULE_ENG || tok == token::TOK_CONFIG_DIR_SEC_ACTION || tok == token::TOK_CONFIG_DIR_SEC_DEFAULT_ACTION || tok == token::TOK_CONFIG_DIR_SEC_MARKER || tok == token::TOK_CONFIG_DIR_UNICODE_MAP_FILE || tok == token::TOK_CONFIG_DIR_UNICODE_CODE_PAGE || tok == token::TOK_CONFIG_SEC_COLLECTION_TIMEOUT || tok == token::TOK_CONFIG_SEC_HTTP_BLKEY || tok == token::TOK_CONFIG_SEC_INTERCEPT_ON_ERROR || tok == token::TOK_CONFIG_SEC_REMOTE_RULES_FAIL_ACTION || tok == token::TOK_CONFIG_SEC_RULE_REMOVE_BY_ID || tok == token::TOK_CONFIG_SEC_RULE_REMOVE_BY_MSG || tok == token::TOK_CONFIG_SEC_RULE_REMOVE_BY_TAG || tok == token::TOK_CONFIG_SEC_RULE_UPDATE_TARGET_BY_TAG || tok == token::TOK_CONFIG_SEC_RULE_UPDATE_TARGET_BY_MSG || tok == token::TOK_CONFIG_SEC_RULE_UPDATE_TARGET_BY_ID || tok == token::TOK_CONFIG_SEC_RULE_UPDATE_ACTION_BY_ID || tok == token::TOK_CONFIG_UPDLOAD_KEEP_FILES || tok == token::TOK_CONFIG_UPDLOAD_SAVE_TMP_FILES || tok == token::TOK_CONFIG_UPLOAD_DIR || tok == token::TOK_CONFIG_UPLOAD_FILE_LIMIT || tok == token::TOK_CONFIG_UPLOAD_FILE_MODE || tok == token::TOK_CONFIG_VALUE_ABORT || tok == token::TOK_CONFIG_VALUE_DETC || tok == token::TOK_CONFIG_VALUE_HTTPS || tok == token::TOK_CONFIG_VALUE_OFF || tok == token::TOK_CONFIG_VALUE_ON || tok == token::TOK_CONFIG_VALUE_PARALLEL || tok == token::TOK_CONFIG_VALUE_PROCESS_PARTIAL || tok == token::TOK_CONFIG_VALUE_REJECT || tok == token::TOK_CONFIG_VALUE_RELEVANT_ONLY || tok == token::TOK_CONFIG_VALUE_SERIAL || tok == token::TOK_CONFIG_VALUE_WARN || tok == token::TOK_CONFIG_XML_EXTERNAL_ENTITY || tok == token::TOK_CONGIG_DIR_RESPONSE_BODY_MP || tok == token::TOK_CONGIG_DIR_SEC_ARG_SEP || tok == token::TOK_CONGIG_DIR_SEC_COOKIE_FORMAT || tok == token::TOK_CONFIG_SEC_COOKIEV0_SEPARATOR || tok == token::TOK_CONGIG_DIR_SEC_DATA_DIR || tok == token::TOK_CONGIG_DIR_SEC_STATUS_ENGINE || tok == token::TOK_CONFIG_SEC_STREAM_IN_BODY_INSPECTION || tok == token::TOK_CONFIG_SEC_STREAM_OUT_BODY_INSPECTION || tok == token::TOK_CONGIG_DIR_SEC_TMP_DIR || tok == token::TOK_DIRECTIVE || tok == token::TOK_DIRECTIVE_SECRULESCRIPT || tok == token::TOK_FREE_TEXT_QUOTE_MACRO_EXPANSION || tok == token::TOK_QUOTATION_MARK || tok == token::TOK_RUN_TIME_VAR_BLD || tok == token::TOK_RUN_TIME_VAR_DUR || tok == token::TOK_RUN_TIME_VAR_HSV || tok == token::TOK_RUN_TIME_VAR_REMOTE_USER || tok == token::TOK_RUN_TIME_VAR_TIME || tok == token::TOK_RUN_TIME_VAR_TIME_DAY || tok == token::TOK_RUN_TIME_VAR_TIME_EPOCH || tok == token::TOK_RUN_TIME_VAR_TIME_HOUR || tok == token::TOK_RUN_TIME_VAR_TIME_MIN || tok == token::TOK_RUN_TIME_VAR_TIME_MON || tok == token::TOK_RUN_TIME_VAR_TIME_SEC || tok == token::TOK_RUN_TIME_VAR_TIME_WDAY || tok == token::TOK_RUN_TIME_VAR_TIME_YEAR || tok == token::TOK_VARIABLE || tok == token::TOK_DICT_ELEMENT || tok == token::TOK_DICT_ELEMENT_REGEXP);
      }
#else
      symbol_type (int tok, const std::string& v, const location_type& l)
        : super_type(token_type (tok), v, l)
      {
        YYASSERT (tok == token::TOK_ACTION_ACCURACY || tok == token::TOK_ACTION_ALLOW || tok == token::TOK_ACTION_APPEND || tok == token::TOK_ACTION_AUDIT_LOG || tok == token::TOK_ACTION_BLOCK || tok == token::TOK_ACTION_CAPTURE || tok == token::TOK_ACTION_CHAIN || tok == token::TOK_ACTION_CTL_AUDIT_ENGINE || tok == token::TOK_ACTION_CTL_AUDIT_LOG_PARTS || tok == token::TOK_ACTION_CTL_BDY_JSON || tok == token::TOK_ACTION_CTL_BDY_XML || tok == token::TOK_ACTION_CTL_BDY_URLENCODED || tok == token::TOK_ACTION_CTL_FORCE_REQ_BODY_VAR || tok == token::TOK_ACTION_CTL_REQUEST_BODY_ACCESS || tok == token::TOK_ACTION_CTL_RULE_REMOVE_BY_ID || tok == token::TOK_ACTION_CTL_RULE_REMOVE_BY_TAG || tok == token::TOK_ACTION_CTL_RULE_REMOVE_TARGET_BY_ID || tok == token::TOK_ACTION_CTL_RULE_REMOVE_TARGET_BY_TAG || tok == token::TOK_ACTION_DENY || tok == token::TOK_ACTION_DEPRECATE_VAR || tok == token::TOK_ACTION_DROP || tok == token::TOK_ACTION_EXEC || tok == token::TOK_ACTION_EXPIRE_VAR || tok == token::TOK_ACTION_ID || tok == token::TOK_ACTION_INITCOL || tok == token::TOK_ACTION_LOG || tok == token::TOK_ACTION_LOG_DATA || tok == token::TOK_ACTION_MATURITY || tok == token::TOK_ACTION_MSG || tok == token::TOK_ACTION_MULTI_MATCH || tok == token::TOK_ACTION_NO_AUDIT_LOG || tok == token::TOK_ACTION_NO_LOG || tok == token::TOK_ACTION_PASS || tok == token::TOK_ACTION_PAUSE || tok == token::TOK_ACTION_PHASE || tok == token::TOK_ACTION_PREPEND || tok == token::TOK_ACTION_PROXY || tok == token::TOK_ACTION_REDIRECT || tok == token::TOK_ACTION_REV || tok == token::TOK_ACTION_SANITISE_ARG || tok == token::TOK_ACTION_SANITISE_MATCHED || tok == token::TOK_ACTION_SANITISE_MATCHED_BYTES || tok == token::TOK_ACTION_SANITISE_REQUEST_HEADER || tok == token::TOK_ACTION_SANITISE_RESPONSE_HEADER || tok == token::TOK_ACTION_SETENV || tok == token::TOK_ACTION_SETRSC || tok == token::TOK_ACTION_SETSID || tok == token::TOK_ACTION_SETUID || tok == token::TOK_ACTION_SEVERITY || tok == token::TOK_ACTION_SKIP || tok == token::TOK_ACTION_SKIP_AFTER || tok == token::TOK_ACTION_STATUS || tok == token::TOK_ACTION_TAG || tok == token::TOK_ACTION_TRANSFORMATION_BASE_64_ENCODE || tok == token::TOK_ACTION_TRANSFORMATION_BASE_64_DECODE || tok == token::TOK_ACTION_TRANSFORMATION_BASE_64_DECODE_EXT || tok == token::TOK_ACTION_TRANSFORMATION_CMD_LINE || tok == token::TOK_ACTION_TRANSFORMATION_COMPRESS_WHITESPACE || tok == token::TOK_ACTION_TRANSFORMATION_CSS_DECODE || tok == token::TOK_ACTION_TRANSFORMATION_ESCAPE_SEQ_DECODE || tok == token::TOK_ACTION_TRANSFORMATION_HEX_ENCODE || tok == token::TOK_ACTION_TRANSFORMATION_HEX_DECODE || tok == token::TOK_ACTION_TRANSFORMATION_HTML_ENTITY_DECODE || tok == token::TOK_ACTION_TRANSFORMATION_JS_DECODE || tok == token::TOK_ACTION_TRANSFORMATION_LENGTH || tok == token::TOK_ACTION_TRANSFORMATION_LOWERCASE || tok == token::TOK_ACTION_TRANSFORMATION_MD5 || tok == token::TOK_ACTION_TRANSFORMATION_NONE || tok == token::TOK_ACTION_TRANSFORMATION_NORMALISE_PATH || tok == token::TOK_ACTION_TRANSFORMATION_NORMALISE_PATH_WIN || tok == token::TOK_ACTION_TRANSFORMATION_PARITY_EVEN_7_BIT || tok == token::TOK_ACTION_TRANSFORMATION_PARITY_ODD_7_BIT || tok == token::TOK_ACTION_TRANSFORMATION_PARITY_ZERO_7_BIT || tok == token::TOK_ACTION_TRANSFORMATION_REMOVE_COMMENTS || tok == token::TOK_ACTION_TRANSFORMATION_REMOVE_COMMENTS_CHAR || tok == token::TOK_ACTION_TRANSFORMATION_REMOVE_NULLS || tok == token::TOK_ACTION_TRANSFORMATION_REMOVE_WHITESPACE || tok == token::TOK_ACTION_TRANSFORMATION_REPLACE_COMMENTS || tok == token::TOK_ACTION_TRANSFORMATION_REPLACE_NULLS || tok == token::TOK_ACTION_TRANSFORMATION_SHA1 || tok == token::TOK_ACTION_TRANSFORMATION_SQL_HEX_DECODE || tok == token::TOK_ACTION_TRANSFORMATION_TRIM || tok == token::TOK_ACTION_TRANSFORMATION_TRIM_LEFT || tok == token::TOK_ACTION_TRANSFORMATION_TRIM_RIGHT || tok == token::TOK_ACTION_TRANSFORMATION_UPPERCASE || tok == token::TOK_ACTION_TRANSFORMATION_URL_ENCODE || tok == token::TOK_ACTION_TRANSFORMATION_URL_DECODE || tok == token::TOK_ACTION_TRANSFORMATION_URL_DECODE_UNI || tok == token::TOK_ACTION_TRANSFORMATION_UTF8_TO_UNICODE || tok == token::TOK_ACTION_VER || tok == token::TOK_ACTION_XMLNS || tok == token::TOK_CONFIG_COMPONENT_SIG || tok == token::TOK_CONFIG_CONN_ENGINE || tok == token::TOK_CONFIG_SEC_ARGUMENT_SEPARATOR || tok == token::TOK_CONFIG_SEC_WEB_APP_ID || tok == token::TOK_CONFIG_SEC_SERVER_SIG || tok == token::TOK_CONFIG_DIR_AUDIT_DIR || tok == token::TOK_CONFIG_DIR_AUDIT_DIR_MOD || tok == token::TOK_CONFIG_DIR_AUDIT_ENG || tok == token::TOK_CONFIG_DIR_AUDIT_FLE_MOD || tok == token::TOK_CONFIG_DIR_AUDIT_LOG || tok == token::TOK_CONFIG_DIR_AUDIT_LOG2 || tok == token::TOK_CONFIG_DIR_AUDIT_LOG_P || tok == token::TOK_CONFIG_DIR_AUDIT_STS || tok == token::TOK_CONFIG_DIR_AUDIT_TPE || tok == token::TOK_CONFIG_DIR_DEBUG_LOG || tok == token::TOK_CONFIG_DIR_DEBUG_LVL || tok == token::TOK_CONFIG_SEC_CACHE_TRANSFORMATIONS || tok == token::TOK_CONFIG_SEC_DISABLE_BACKEND_COMPRESS || tok == token::TOK_CONFIG_SEC_HASH_ENGINE || tok == token::TOK_CONFIG_SEC_HASH_KEY || tok == token::TOK_CONFIG_SEC_HASH_PARAM || tok == token::TOK_CONFIG_SEC_HASH_METHOD_RX || tok == token::TOK_CONFIG_SEC_HASH_METHOD_PM || tok == token::TOK_CONFIG_SEC_CHROOT_DIR || tok == token::TOK_CONFIG_DIR_GEO_DB || tok == token::TOK_CONFIG_DIR_GSB_DB || tok == token::TOK_CONFIG_SEC_GUARDIAN_LOG || tok == token::TOK_CONFIG_DIR_PCRE_MATCH_LIMIT || tok == token::TOK_CONFIG_DIR_PCRE_MATCH_LIMIT_RECURSION || tok == token::TOK_CONFIG_SEC_CONN_R_STATE_LIMIT || tok == token::TOK_CONFIG_SEC_CONN_W_STATE_LIMIT || tok == token::TOK_CONFIG_SEC_SENSOR_ID || tok == token::TOK_CONFIG_DIR_REQ_BODY || tok == token::TOK_CONFIG_DIR_REQ_BODY_IN_MEMORY_LIMIT || tok == token::TOK_CONFIG_DIR_REQ_BODY_LIMIT || tok == token::TOK_CONFIG_DIR_REQ_BODY_LIMIT_ACTION || tok == token::TOK_CONFIG_DIR_REQ_BODY_NO_FILES_LIMIT || tok == token::TOK_CONFIG_DIR_RES_BODY || tok == token::TOK_CONFIG_DIR_RES_BODY_LIMIT || tok == token::TOK_CONFIG_DIR_RES_BODY_LIMIT_ACTION || tok == token::TOK_CONFIG_SEC_RULE_INHERITANCE || tok == token::TOK_CONFIG_SEC_RULE_PERF_TIME || tok == token::TOK_CONFIG_DIR_RULE_ENG || tok == token::TOK_CONFIG_DIR_SEC_ACTION || tok == token::TOK_CONFIG_DIR_SEC_DEFAULT_ACTION || tok == token::TOK_CONFIG_DIR_SEC_MARKER || tok == token::TOK_CONFIG_DIR_UNICODE_MAP_FILE || tok == token::TOK_CONFIG_DIR_UNICODE_CODE_PAGE || tok == token::TOK_CONFIG_SEC_COLLECTION_TIMEOUT || tok == token::TOK_CONFIG_SEC_HTTP_BLKEY || tok == token::TOK_CONFIG_SEC_INTERCEPT_ON_ERROR || tok == token::TOK_CONFIG_SEC_REMOTE_RULES_FAIL_ACTION || tok == token::TOK_CONFIG_SEC_RULE_REMOVE_BY_ID || tok == token::TOK_CONFIG_SEC_RULE_REMOVE_BY_MSG || tok == token::TOK_CONFIG_SEC_RULE_REMOVE_BY_TAG || tok == token::TOK_CONFIG_SEC_RULE_UPDATE_TARGET_BY_TAG || tok == token::TOK_CONFIG_SEC_RULE_UPDATE_TARGET_BY_MSG || tok == token::TOK_CONFIG_SEC_RULE_UPDATE_TARGET_BY_ID || tok == token::TOK_CONFIG_SEC_RULE_UPDATE_ACTION_BY_ID || tok == token::TOK_CONFIG_UPDLOAD_KEEP_FILES || tok == token::TOK_CONFIG_UPDLOAD_SAVE_TMP_FILES || tok == token::TOK_CONFIG_UPLOAD_DIR || tok == token::TOK_CONFIG_UPLOAD_FILE_LIMIT || tok == token::TOK_CONFIG_UPLOAD_FILE_MODE || tok == token::TOK_CONFIG_VALUE_ABORT || tok == token::TOK_CONFIG_VALUE_DETC || tok == token::TOK_CONFIG_VALUE_HTTPS || tok == token::TOK_CONFIG_VALUE_OFF || tok == token::TOK_CONFIG_VALUE_ON || tok == token::TOK_CONFIG_VALUE_PARALLEL || tok == token::TOK_CONFIG_VALUE_PROCESS_PARTIAL || tok == token::TOK_CONFIG_VALUE_REJECT || tok == token::TOK_CONFIG_VALUE_RELEVANT_ONLY || tok == token::TOK_CONFIG_VALUE_SERIAL || tok == token::TOK_CONFIG_VALUE_WARN || tok == token::TOK_CONFIG_XML_EXTERNAL_ENTITY || tok == token::TOK_CONGIG_DIR_RESPONSE_BODY_MP || tok == token::TOK_CONGIG_DIR_SEC_ARG_SEP || tok == token::TOK_CONGIG_DIR_SEC_COOKIE_FORMAT || tok == token::TOK_CONFIG_SEC_COOKIEV0_SEPARATOR || tok == token::TOK_CONGIG_DIR_SEC_DATA_DIR || tok == token::TOK_CONGIG_DIR_SEC_STATUS_ENGINE || tok == token::TOK_CONFIG_SEC_STREAM_IN_BODY_INSPECTION || tok == token::TOK_CONFIG_SEC_STREAM_OUT_BODY_INSPECTION || tok == token::TOK_CONGIG_DIR_SEC_TMP_DIR || tok == token::TOK_DIRECTIVE || tok == token::TOK_DIRECTIVE_SECRULESCRIPT || tok == token::TOK_FREE_TEXT_QUOTE_MACRO_EXPANSION || tok == token::TOK_QUOTATION_MARK || tok == token::TOK_RUN_TIME_VAR_BLD || tok == token::TOK_RUN_TIME_VAR_DUR || tok == token::TOK_RUN_TIME_VAR_HSV || tok == token::TOK_RUN_TIME_VAR_REMOTE_USER || tok == token::TOK_RUN_TIME_VAR_TIME || tok == token::TOK_RUN_TIME_VAR_TIME_DAY || tok == token::TOK_RUN_TIME_VAR_TIME_EPOCH || tok == token::TOK_RUN_TIME_VAR_TIME_HOUR || tok == token::TOK_RUN_TIME_VAR_TIME_MIN || tok == token::TOK_RUN_TIME_VAR_TIME_MON || tok == token::TOK_RUN_TIME_VAR_TIME_SEC || tok == token::TOK_RUN_TIME_VAR_TIME_WDAY || tok == token::TOK_RUN_TIME_VAR_TIME_YEAR || tok == token::TOK_VARIABLE || tok == token::TOK_DICT_ELEMENT || tok == token::TOK_DICT_ELEMENT_REGEXP);
      }
#endif
    };

    /// Build a parser object.
    seclang_parser (modsecurity::Parser::Driver& driver_yyarg);
    virtual ~seclang_parser ();

    /// Parse.  An alias for parse ().
    /// \returns  0 iff parsing succeeded.
    int operator() ();

    /// Parse.
    /// \returns  0 iff parsing succeeded.
    virtual int parse ();

#if YYDEBUG
    /// The current debugging stream.
    std::ostream& debug_stream () const YY_ATTRIBUTE_PURE;
    /// Set the current debugging stream.
    void set_debug_stream (std::ostream &);

    /// Type for debugging levels.
    typedef int debug_level_type;
    /// The current debugging level.
    debug_level_type debug_level () const YY_ATTRIBUTE_PURE;
    /// Set the current debugging level.
    void set_debug_level (debug_level_type l);
#endif

    /// Report a syntax error.
    /// \param loc    where the syntax error is found.
    /// \param msg    a description of the syntax error.
    virtual void error (const location_type& loc, const std::string& msg);

    /// Report a syntax error.
    void error (const syntax_error& err);

    // Implementation of make_symbol for each symbol type.
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_END (location_type l)
      {
        return symbol_type (token::TOK_END, std::move (l));
      }
#else
      static
      symbol_type
      make_END (const location_type& l)
      {
        return symbol_type (token::TOK_END, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_COMMA (location_type l)
      {
        return symbol_type (token::TOK_COMMA, std::move (l));
      }
#else
      static
      symbol_type
      make_COMMA (const location_type& l)
      {
        return symbol_type (token::TOK_COMMA, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_CONFIG_CONTENT_INJECTION (location_type l)
      {
        return symbol_type (token::TOK_CONFIG_CONTENT_INJECTION, std::move (l));
      }
#else
      static
      symbol_type
      make_CONFIG_CONTENT_INJECTION (const location_type& l)
      {
        return symbol_type (token::TOK_CONFIG_CONTENT_INJECTION, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_CONGIG_DIR_RESPONSE_BODY_MP_CLEAR (location_type l)
      {
        return symbol_type (token::TOK_CONGIG_DIR_RESPONSE_BODY_MP_CLEAR, std::move (l));
      }
#else
      static
      symbol_type
      make_CONGIG_DIR_RESPONSE_BODY_MP_CLEAR (const location_type& l)
      {
        return symbol_type (token::TOK_CONGIG_DIR_RESPONSE_BODY_MP_CLEAR, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_PIPE (location_type l)
      {
        return symbol_type (token::TOK_PIPE, std::move (l));
      }
#else
      static
      symbol_type
      make_PIPE (const location_type& l)
      {
        return symbol_type (token::TOK_PIPE, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_NEW_LINE (location_type l)
      {
        return symbol_type (token::TOK_NEW_LINE, std::move (l));
      }
#else
      static
      symbol_type
      make_NEW_LINE (const location_type& l)
      {
        return symbol_type (token::TOK_NEW_LINE, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_VAR_COUNT (location_type l)
      {
        return symbol_type (token::TOK_VAR_COUNT, std::move (l));
      }
#else
      static
      symbol_type
      make_VAR_COUNT (const location_type& l)
      {
        return symbol_type (token::TOK_VAR_COUNT, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_VAR_EXCLUSION (location_type l)
      {
        return symbol_type (token::TOK_VAR_EXCLUSION, std::move (l));
      }
#else
      static
      symbol_type
      make_VAR_EXCLUSION (const location_type& l)
      {
        return symbol_type (token::TOK_VAR_EXCLUSION, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_VARIABLE_ARGS (location_type l)
      {
        return symbol_type (token::TOK_VARIABLE_ARGS, std::move (l));
      }
#else
      static
      symbol_type
      make_VARIABLE_ARGS (const location_type& l)
      {
        return symbol_type (token::TOK_VARIABLE_ARGS, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_VARIABLE_ARGS_POST (location_type l)
      {
        return symbol_type (token::TOK_VARIABLE_ARGS_POST, std::move (l));
      }
#else
      static
      symbol_type
      make_VARIABLE_ARGS_POST (const location_type& l)
      {
        return symbol_type (token::TOK_VARIABLE_ARGS_POST, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_VARIABLE_ARGS_GET (location_type l)
      {
        return symbol_type (token::TOK_VARIABLE_ARGS_GET, std::move (l));
      }
#else
      static
      symbol_type
      make_VARIABLE_ARGS_GET (const location_type& l)
      {
        return symbol_type (token::TOK_VARIABLE_ARGS_GET, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_VARIABLE_FILES_SIZES (location_type l)
      {
        return symbol_type (token::TOK_VARIABLE_FILES_SIZES, std::move (l));
      }
#else
      static
      symbol_type
      make_VARIABLE_FILES_SIZES (const location_type& l)
      {
        return symbol_type (token::TOK_VARIABLE_FILES_SIZES, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_VARIABLE_FILES_NAMES (location_type l)
      {
        return symbol_type (token::TOK_VARIABLE_FILES_NAMES, std::move (l));
      }
#else
      static
      symbol_type
      make_VARIABLE_FILES_NAMES (const location_type& l)
      {
        return symbol_type (token::TOK_VARIABLE_FILES_NAMES, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_VARIABLE_FILES_TMP_CONTENT (location_type l)
      {
        return symbol_type (token::TOK_VARIABLE_FILES_TMP_CONTENT, std::move (l));
      }
#else
      static
      symbol_type
      make_VARIABLE_FILES_TMP_CONTENT (const location_type& l)
      {
        return symbol_type (token::TOK_VARIABLE_FILES_TMP_CONTENT, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_VARIABLE_MULTIPART_FILENAME (location_type l)
      {
        return symbol_type (token::TOK_VARIABLE_MULTIPART_FILENAME, std::move (l));
      }
#else
      static
      symbol_type
      make_VARIABLE_MULTIPART_FILENAME (const location_type& l)
      {
        return symbol_type (token::TOK_VARIABLE_MULTIPART_FILENAME, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_VARIABLE_MULTIPART_NAME (location_type l)
      {
        return symbol_type (token::TOK_VARIABLE_MULTIPART_NAME, std::move (l));
      }
#else
      static
      symbol_type
      make_VARIABLE_MULTIPART_NAME (const location_type& l)
      {
        return symbol_type (token::TOK_VARIABLE_MULTIPART_NAME, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_VARIABLE_MATCHED_VARS_NAMES (location_type l)
      {
        return symbol_type (token::TOK_VARIABLE_MATCHED_VARS_NAMES, std::move (l));
      }
#else
      static
      symbol_type
      make_VARIABLE_MATCHED_VARS_NAMES (const location_type& l)
      {
        return symbol_type (token::TOK_VARIABLE_MATCHED_VARS_NAMES, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_VARIABLE_MATCHED_VARS (location_type l)
      {
        return symbol_type (token::TOK_VARIABLE_MATCHED_VARS, std::move (l));
      }
#else
      static
      symbol_type
      make_VARIABLE_MATCHED_VARS (const location_type& l)
      {
        return symbol_type (token::TOK_VARIABLE_MATCHED_VARS, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_VARIABLE_FILES (location_type l)
      {
        return symbol_type (token::TOK_VARIABLE_FILES, std::move (l));
      }
#else
      static
      symbol_type
      make_VARIABLE_FILES (const location_type& l)
      {
        return symbol_type (token::TOK_VARIABLE_FILES, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_VARIABLE_REQUEST_COOKIES (location_type l)
      {
        return symbol_type (token::TOK_VARIABLE_REQUEST_COOKIES, std::move (l));
      }
#else
      static
      symbol_type
      make_VARIABLE_REQUEST_COOKIES (const location_type& l)
      {
        return symbol_type (token::TOK_VARIABLE_REQUEST_COOKIES, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_VARIABLE_REQUEST_HEADERS (location_type l)
      {
        return symbol_type (token::TOK_VARIABLE_REQUEST_HEADERS, std::move (l));
      }
#else
      static
      symbol_type
      make_VARIABLE_REQUEST_HEADERS (const location_type& l)
      {
        return symbol_type (token::TOK_VARIABLE_REQUEST_HEADERS, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_VARIABLE_RESPONSE_HEADERS (location_type l)
      {
        return symbol_type (token::TOK_VARIABLE_RESPONSE_HEADERS, std::move (l));
      }
#else
      static
      symbol_type
      make_VARIABLE_RESPONSE_HEADERS (const location_type& l)
      {
        return symbol_type (token::TOK_VARIABLE_RESPONSE_HEADERS, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_VARIABLE_GEO (location_type l)
      {
        return symbol_type (token::TOK_VARIABLE_GEO, std::move (l));
      }
#else
      static
      symbol_type
      make_VARIABLE_GEO (const location_type& l)
      {
        return symbol_type (token::TOK_VARIABLE_GEO, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_VARIABLE_REQUEST_COOKIES_NAMES (location_type l)
      {
        return symbol_type (token::TOK_VARIABLE_REQUEST_COOKIES_NAMES, std::move (l));
      }
#else
      static
      symbol_type
      make_VARIABLE_REQUEST_COOKIES_NAMES (const location_type& l)
      {
        return symbol_type (token::TOK_VARIABLE_REQUEST_COOKIES_NAMES, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_VARIABLE_ARGS_COMBINED_SIZE (location_type l)
      {
        return symbol_type (token::TOK_VARIABLE_ARGS_COMBINED_SIZE, std::move (l));
      }
#else
      static
      symbol_type
      make_VARIABLE_ARGS_COMBINED_SIZE (const location_type& l)
      {
        return symbol_type (token::TOK_VARIABLE_ARGS_COMBINED_SIZE, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_VARIABLE_ARGS_GET_NAMES (location_type l)
      {
        return symbol_type (token::TOK_VARIABLE_ARGS_GET_NAMES, std::move (l));
      }
#else
      static
      symbol_type
      make_VARIABLE_ARGS_GET_NAMES (const location_type& l)
      {
        return symbol_type (token::TOK_VARIABLE_ARGS_GET_NAMES, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_VARIABLE_RULE (location_type l)
      {
        return symbol_type (token::TOK_VARIABLE_RULE, std::move (l));
      }
#else
      static
      symbol_type
      make_VARIABLE_RULE (const location_type& l)
      {
        return symbol_type (token::TOK_VARIABLE_RULE, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_VARIABLE_ARGS_NAMES (location_type l)
      {
        return symbol_type (token::TOK_VARIABLE_ARGS_NAMES, std::move (l));
      }
#else
      static
      symbol_type
      make_VARIABLE_ARGS_NAMES (const location_type& l)
      {
        return symbol_type (token::TOK_VARIABLE_ARGS_NAMES, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_VARIABLE_ARGS_POST_NAMES (location_type l)
      {
        return symbol_type (token::TOK_VARIABLE_ARGS_POST_NAMES, std::move (l));
      }
#else
      static
      symbol_type
      make_VARIABLE_ARGS_POST_NAMES (const location_type& l)
      {
        return symbol_type (token::TOK_VARIABLE_ARGS_POST_NAMES, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_VARIABLE_AUTH_TYPE (location_type l)
      {
        return symbol_type (token::TOK_VARIABLE_AUTH_TYPE, std::move (l));
      }
#else
      static
      symbol_type
      make_VARIABLE_AUTH_TYPE (const location_type& l)
      {
        return symbol_type (token::TOK_VARIABLE_AUTH_TYPE, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_VARIABLE_FILES_COMBINED_SIZE (location_type l)
      {
        return symbol_type (token::TOK_VARIABLE_FILES_COMBINED_SIZE, std::move (l));
      }
#else
      static
      symbol_type
      make_VARIABLE_FILES_COMBINED_SIZE (const location_type& l)
      {
        return symbol_type (token::TOK_VARIABLE_FILES_COMBINED_SIZE, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_VARIABLE_FILES_TMP_NAMES (location_type l)
      {
        return symbol_type (token::TOK_VARIABLE_FILES_TMP_NAMES, std::move (l));
      }
#else
      static
      symbol_type
      make_VARIABLE_FILES_TMP_NAMES (const location_type& l)
      {
        return symbol_type (token::TOK_VARIABLE_FILES_TMP_NAMES, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_VARIABLE_FULL_REQUEST (location_type l)
      {
        return symbol_type (token::TOK_VARIABLE_FULL_REQUEST, std::move (l));
      }
#else
      static
      symbol_type
      make_VARIABLE_FULL_REQUEST (const location_type& l)
      {
        return symbol_type (token::TOK_VARIABLE_FULL_REQUEST, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_VARIABLE_FULL_REQUEST_LENGTH (location_type l)
      {
        return symbol_type (token::TOK_VARIABLE_FULL_REQUEST_LENGTH, std::move (l));
      }
#else
      static
      symbol_type
      make_VARIABLE_FULL_REQUEST_LENGTH (const location_type& l)
      {
        return symbol_type (token::TOK_VARIABLE_FULL_REQUEST_LENGTH, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_VARIABLE_INBOUND_DATA_ERROR (location_type l)
      {
        return symbol_type (token::TOK_VARIABLE_INBOUND_DATA_ERROR, std::move (l));
      }
#else
      static
      symbol_type
      make_VARIABLE_INBOUND_DATA_ERROR (const location_type& l)
      {
        return symbol_type (token::TOK_VARIABLE_INBOUND_DATA_ERROR, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_VARIABLE_MATCHED_VAR (location_type l)
      {
        return symbol_type (token::TOK_VARIABLE_MATCHED_VAR, std::move (l));
      }
#else
      static
      symbol_type
      make_VARIABLE_MATCHED_VAR (const location_type& l)
      {
        return symbol_type (token::TOK_VARIABLE_MATCHED_VAR, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_VARIABLE_MATCHED_VAR_NAME (location_type l)
      {
        return symbol_type (token::TOK_VARIABLE_MATCHED_VAR_NAME, std::move (l));
      }
#else
      static
      symbol_type
      make_VARIABLE_MATCHED_VAR_NAME (const location_type& l)
      {
        return symbol_type (token::TOK_VARIABLE_MATCHED_VAR_NAME, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_VARIABLE_MULTIPART_BOUNDARY_QUOTED (location_type l)
      {
        return symbol_type (token::TOK_VARIABLE_MULTIPART_BOUNDARY_QUOTED, std::move (l));
      }
#else
      static
      symbol_type
      make_VARIABLE_MULTIPART_BOUNDARY_QUOTED (const location_type& l)
      {
        return symbol_type (token::TOK_VARIABLE_MULTIPART_BOUNDARY_QUOTED, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_VARIABLE_MULTIPART_BOUNDARY_WHITESPACE (location_type l)
      {
        return symbol_type (token::TOK_VARIABLE_MULTIPART_BOUNDARY_WHITESPACE, std::move (l));
      }
#else
      static
      symbol_type
      make_VARIABLE_MULTIPART_BOUNDARY_WHITESPACE (const location_type& l)
      {
        return symbol_type (token::TOK_VARIABLE_MULTIPART_BOUNDARY_WHITESPACE, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_VARIABLE_MULTIPART_CRLF_LF_LINES (location_type l)
      {
        return symbol_type (token::TOK_VARIABLE_MULTIPART_CRLF_LF_LINES, std::move (l));
      }
#else
      static
      symbol_type
      make_VARIABLE_MULTIPART_CRLF_LF_LINES (const location_type& l)
      {
        return symbol_type (token::TOK_VARIABLE_MULTIPART_CRLF_LF_LINES, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_VARIABLE_MULTIPART_DATA_AFTER (location_type l)
      {
        return symbol_type (token::TOK_VARIABLE_MULTIPART_DATA_AFTER, std::move (l));
      }
#else
      static
      symbol_type
      make_VARIABLE_MULTIPART_DATA_AFTER (const location_type& l)
      {
        return symbol_type (token::TOK_VARIABLE_MULTIPART_DATA_AFTER, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_VARIABLE_MULTIPART_DATA_BEFORE (location_type l)
      {
        return symbol_type (token::TOK_VARIABLE_MULTIPART_DATA_BEFORE, std::move (l));
      }
#else
      static
      symbol_type
      make_VARIABLE_MULTIPART_DATA_BEFORE (const location_type& l)
      {
        return symbol_type (token::TOK_VARIABLE_MULTIPART_DATA_BEFORE, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_VARIABLE_MULTIPART_FILE_LIMIT_EXCEEDED (location_type l)
      {
        return symbol_type (token::TOK_VARIABLE_MULTIPART_FILE_LIMIT_EXCEEDED, std::move (l));
      }
#else
      static
      symbol_type
      make_VARIABLE_MULTIPART_FILE_LIMIT_EXCEEDED (const location_type& l)
      {
        return symbol_type (token::TOK_VARIABLE_MULTIPART_FILE_LIMIT_EXCEEDED, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_VARIABLE_MULTIPART_HEADER_FOLDING (location_type l)
      {
        return symbol_type (token::TOK_VARIABLE_MULTIPART_HEADER_FOLDING, std::move (l));
      }
#else
      static
      symbol_type
      make_VARIABLE_MULTIPART_HEADER_FOLDING (const location_type& l)
      {
        return symbol_type (token::TOK_VARIABLE_MULTIPART_HEADER_FOLDING, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_VARIABLE_MULTIPART_INVALID_HEADER_FOLDING (location_type l)
      {
        return symbol_type (token::TOK_VARIABLE_MULTIPART_INVALID_HEADER_FOLDING, std::move (l));
      }
#else
      static
      symbol_type
      make_VARIABLE_MULTIPART_INVALID_HEADER_FOLDING (const location_type& l)
      {
        return symbol_type (token::TOK_VARIABLE_MULTIPART_INVALID_HEADER_FOLDING, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_VARIABLE_MULTIPART_INVALID_PART (location_type l)
      {
        return symbol_type (token::TOK_VARIABLE_MULTIPART_INVALID_PART, std::move (l));
      }
#else
      static
      symbol_type
      make_VARIABLE_MULTIPART_INVALID_PART (const location_type& l)
      {
        return symbol_type (token::TOK_VARIABLE_MULTIPART_INVALID_PART, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_VARIABLE_MULTIPART_INVALID_QUOTING (location_type l)
      {
        return symbol_type (token::TOK_VARIABLE_MULTIPART_INVALID_QUOTING, std::move (l));
      }
#else
      static
      symbol_type
      make_VARIABLE_MULTIPART_INVALID_QUOTING (const location_type& l)
      {
        return symbol_type (token::TOK_VARIABLE_MULTIPART_INVALID_QUOTING, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_VARIABLE_MULTIPART_LF_LINE (location_type l)
      {
        return symbol_type (token::TOK_VARIABLE_MULTIPART_LF_LINE, std::move (l));
      }
#else
      static
      symbol_type
      make_VARIABLE_MULTIPART_LF_LINE (const location_type& l)
      {
        return symbol_type (token::TOK_VARIABLE_MULTIPART_LF_LINE, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_VARIABLE_MULTIPART_MISSING_SEMICOLON (location_type l)
      {
        return symbol_type (token::TOK_VARIABLE_MULTIPART_MISSING_SEMICOLON, std::move (l));
      }
#else
      static
      symbol_type
      make_VARIABLE_MULTIPART_MISSING_SEMICOLON (const location_type& l)
      {
        return symbol_type (token::TOK_VARIABLE_MULTIPART_MISSING_SEMICOLON, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_VARIABLE_MULTIPART_SEMICOLON_MISSING (location_type l)
      {
        return symbol_type (token::TOK_VARIABLE_MULTIPART_SEMICOLON_MISSING, std::move (l));
      }
#else
      static
      symbol_type
      make_VARIABLE_MULTIPART_SEMICOLON_MISSING (const location_type& l)
      {
        return symbol_type (token::TOK_VARIABLE_MULTIPART_SEMICOLON_MISSING, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_VARIABLE_MULTIPART_STRICT_ERROR (location_type l)
      {
        return symbol_type (token::TOK_VARIABLE_MULTIPART_STRICT_ERROR, std::move (l));
      }
#else
      static
      symbol_type
      make_VARIABLE_MULTIPART_STRICT_ERROR (const location_type& l)
      {
        return symbol_type (token::TOK_VARIABLE_MULTIPART_STRICT_ERROR, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_VARIABLE_MULTIPART_UNMATCHED_BOUNDARY (location_type l)
      {
        return symbol_type (token::TOK_VARIABLE_MULTIPART_UNMATCHED_BOUNDARY, std::move (l));
      }
#else
      static
      symbol_type
      make_VARIABLE_MULTIPART_UNMATCHED_BOUNDARY (const location_type& l)
      {
        return symbol_type (token::TOK_VARIABLE_MULTIPART_UNMATCHED_BOUNDARY, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_VARIABLE_OUTBOUND_DATA_ERROR (location_type l)
      {
        return symbol_type (token::TOK_VARIABLE_OUTBOUND_DATA_ERROR, std::move (l));
      }
#else
      static
      symbol_type
      make_VARIABLE_OUTBOUND_DATA_ERROR (const location_type& l)
      {
        return symbol_type (token::TOK_VARIABLE_OUTBOUND_DATA_ERROR, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_VARIABLE_PATH_INFO (location_type l)
      {
        return symbol_type (token::TOK_VARIABLE_PATH_INFO, std::move (l));
      }
#else
      static
      symbol_type
      make_VARIABLE_PATH_INFO (const location_type& l)
      {
        return symbol_type (token::TOK_VARIABLE_PATH_INFO, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_VARIABLE_QUERY_STRING (location_type l)
      {
        return symbol_type (token::TOK_VARIABLE_QUERY_STRING, std::move (l));
      }
#else
      static
      symbol_type
      make_VARIABLE_QUERY_STRING (const location_type& l)
      {
        return symbol_type (token::TOK_VARIABLE_QUERY_STRING, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_VARIABLE_REMOTE_ADDR (location_type l)
      {
        return symbol_type (token::TOK_VARIABLE_REMOTE_ADDR, std::move (l));
      }
#else
      static
      symbol_type
      make_VARIABLE_REMOTE_ADDR (const location_type& l)
      {
        return symbol_type (token::TOK_VARIABLE_REMOTE_ADDR, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_VARIABLE_REMOTE_HOST (location_type l)
      {
        return symbol_type (token::TOK_VARIABLE_REMOTE_HOST, std::move (l));
      }
#else
      static
      symbol_type
      make_VARIABLE_REMOTE_HOST (const location_type& l)
      {
        return symbol_type (token::TOK_VARIABLE_REMOTE_HOST, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_VARIABLE_REMOTE_PORT (location_type l)
      {
        return symbol_type (token::TOK_VARIABLE_REMOTE_PORT, std::move (l));
      }
#else
      static
      symbol_type
      make_VARIABLE_REMOTE_PORT (const location_type& l)
      {
        return symbol_type (token::TOK_VARIABLE_REMOTE_PORT, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_VARIABLE_REQBODY_ERROR_MSG (location_type l)
      {
        return symbol_type (token::TOK_VARIABLE_REQBODY_ERROR_MSG, std::move (l));
      }
#else
      static
      symbol_type
      make_VARIABLE_REQBODY_ERROR_MSG (const location_type& l)
      {
        return symbol_type (token::TOK_VARIABLE_REQBODY_ERROR_MSG, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_VARIABLE_REQBODY_ERROR (location_type l)
      {
        return symbol_type (token::TOK_VARIABLE_REQBODY_ERROR, std::move (l));
      }
#else
      static
      symbol_type
      make_VARIABLE_REQBODY_ERROR (const location_type& l)
      {
        return symbol_type (token::TOK_VARIABLE_REQBODY_ERROR, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_VARIABLE_REQBODY_PROCESSOR_ERROR_MSG (location_type l)
      {
        return symbol_type (token::TOK_VARIABLE_REQBODY_PROCESSOR_ERROR_MSG, std::move (l));
      }
#else
      static
      symbol_type
      make_VARIABLE_REQBODY_PROCESSOR_ERROR_MSG (const location_type& l)
      {
        return symbol_type (token::TOK_VARIABLE_REQBODY_PROCESSOR_ERROR_MSG, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_VARIABLE_REQBODY_PROCESSOR_ERROR (location_type l)
      {
        return symbol_type (token::TOK_VARIABLE_REQBODY_PROCESSOR_ERROR, std::move (l));
      }
#else
      static
      symbol_type
      make_VARIABLE_REQBODY_PROCESSOR_ERROR (const location_type& l)
      {
        return symbol_type (token::TOK_VARIABLE_REQBODY_PROCESSOR_ERROR, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_VARIABLE_REQBODY_PROCESSOR (location_type l)
      {
        return symbol_type (token::TOK_VARIABLE_REQBODY_PROCESSOR, std::move (l));
      }
#else
      static
      symbol_type
      make_VARIABLE_REQBODY_PROCESSOR (const location_type& l)
      {
        return symbol_type (token::TOK_VARIABLE_REQBODY_PROCESSOR, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_VARIABLE_REQUEST_BASENAME (location_type l)
      {
        return symbol_type (token::TOK_VARIABLE_REQUEST_BASENAME, std::move (l));
      }
#else
      static
      symbol_type
      make_VARIABLE_REQUEST_BASENAME (const location_type& l)
      {
        return symbol_type (token::TOK_VARIABLE_REQUEST_BASENAME, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_VARIABLE_REQUEST_BODY_LENGTH (location_type l)
      {
        return symbol_type (token::TOK_VARIABLE_REQUEST_BODY_LENGTH, std::move (l));
      }
#else
      static
      symbol_type
      make_VARIABLE_REQUEST_BODY_LENGTH (const location_type& l)
      {
        return symbol_type (token::TOK_VARIABLE_REQUEST_BODY_LENGTH, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_VARIABLE_REQUEST_BODY (location_type l)
      {
        return symbol_type (token::TOK_VARIABLE_REQUEST_BODY, std::move (l));
      }
#else
      static
      symbol_type
      make_VARIABLE_REQUEST_BODY (const location_type& l)
      {
        return symbol_type (token::TOK_VARIABLE_REQUEST_BODY, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_VARIABLE_REQUEST_FILE_NAME (location_type l)
      {
        return symbol_type (token::TOK_VARIABLE_REQUEST_FILE_NAME, std::move (l));
      }
#else
      static
      symbol_type
      make_VARIABLE_REQUEST_FILE_NAME (const location_type& l)
      {
        return symbol_type (token::TOK_VARIABLE_REQUEST_FILE_NAME, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_VARIABLE_REQUEST_HEADERS_NAMES (location_type l)
      {
        return symbol_type (token::TOK_VARIABLE_REQUEST_HEADERS_NAMES, std::move (l));
      }
#else
      static
      symbol_type
      make_VARIABLE_REQUEST_HEADERS_NAMES (const location_type& l)
      {
        return symbol_type (token::TOK_VARIABLE_REQUEST_HEADERS_NAMES, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_VARIABLE_REQUEST_LINE (location_type l)
      {
        return symbol_type (token::TOK_VARIABLE_REQUEST_LINE, std::move (l));
      }
#else
      static
      symbol_type
      make_VARIABLE_REQUEST_LINE (const location_type& l)
      {
        return symbol_type (token::TOK_VARIABLE_REQUEST_LINE, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_VARIABLE_REQUEST_METHOD (location_type l)
      {
        return symbol_type (token::TOK_VARIABLE_REQUEST_METHOD, std::move (l));
      }
#else
      static
      symbol_type
      make_VARIABLE_REQUEST_METHOD (const location_type& l)
      {
        return symbol_type (token::TOK_VARIABLE_REQUEST_METHOD, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_VARIABLE_REQUEST_PROTOCOL (location_type l)
      {
        return symbol_type (token::TOK_VARIABLE_REQUEST_PROTOCOL, std::move (l));
      }
#else
      static
      symbol_type
      make_VARIABLE_REQUEST_PROTOCOL (const location_type& l)
      {
        return symbol_type (token::TOK_VARIABLE_REQUEST_PROTOCOL, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_VARIABLE_REQUEST_URI_RAW (location_type l)
      {
        return symbol_type (token::TOK_VARIABLE_REQUEST_URI_RAW, std::move (l));
      }
#else
      static
      symbol_type
      make_VARIABLE_REQUEST_URI_RAW (const location_type& l)
      {
        return symbol_type (token::TOK_VARIABLE_REQUEST_URI_RAW, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_VARIABLE_REQUEST_URI (location_type l)
      {
        return symbol_type (token::TOK_VARIABLE_REQUEST_URI, std::move (l));
      }
#else
      static
      symbol_type
      make_VARIABLE_REQUEST_URI (const location_type& l)
      {
        return symbol_type (token::TOK_VARIABLE_REQUEST_URI, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_VARIABLE_RESOURCE (location_type l)
      {
        return symbol_type (token::TOK_VARIABLE_RESOURCE, std::move (l));
      }
#else
      static
      symbol_type
      make_VARIABLE_RESOURCE (const location_type& l)
      {
        return symbol_type (token::TOK_VARIABLE_RESOURCE, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_VARIABLE_RESPONSE_BODY (location_type l)
      {
        return symbol_type (token::TOK_VARIABLE_RESPONSE_BODY, std::move (l));
      }
#else
      static
      symbol_type
      make_VARIABLE_RESPONSE_BODY (const location_type& l)
      {
        return symbol_type (token::TOK_VARIABLE_RESPONSE_BODY, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_VARIABLE_RESPONSE_CONTENT_LENGTH (location_type l)
      {
        return symbol_type (token::TOK_VARIABLE_RESPONSE_CONTENT_LENGTH, std::move (l));
      }
#else
      static
      symbol_type
      make_VARIABLE_RESPONSE_CONTENT_LENGTH (const location_type& l)
      {
        return symbol_type (token::TOK_VARIABLE_RESPONSE_CONTENT_LENGTH, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_VARIABLE_RESPONSE_CONTENT_TYPE (location_type l)
      {
        return symbol_type (token::TOK_VARIABLE_RESPONSE_CONTENT_TYPE, std::move (l));
      }
#else
      static
      symbol_type
      make_VARIABLE_RESPONSE_CONTENT_TYPE (const location_type& l)
      {
        return symbol_type (token::TOK_VARIABLE_RESPONSE_CONTENT_TYPE, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_VARIABLE_RESPONSE_HEADERS_NAMES (location_type l)
      {
        return symbol_type (token::TOK_VARIABLE_RESPONSE_HEADERS_NAMES, std::move (l));
      }
#else
      static
      symbol_type
      make_VARIABLE_RESPONSE_HEADERS_NAMES (const location_type& l)
      {
        return symbol_type (token::TOK_VARIABLE_RESPONSE_HEADERS_NAMES, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_VARIABLE_RESPONSE_PROTOCOL (location_type l)
      {
        return symbol_type (token::TOK_VARIABLE_RESPONSE_PROTOCOL, std::move (l));
      }
#else
      static
      symbol_type
      make_VARIABLE_RESPONSE_PROTOCOL (const location_type& l)
      {
        return symbol_type (token::TOK_VARIABLE_RESPONSE_PROTOCOL, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_VARIABLE_RESPONSE_STATUS (location_type l)
      {
        return symbol_type (token::TOK_VARIABLE_RESPONSE_STATUS, std::move (l));
      }
#else
      static
      symbol_type
      make_VARIABLE_RESPONSE_STATUS (const location_type& l)
      {
        return symbol_type (token::TOK_VARIABLE_RESPONSE_STATUS, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_VARIABLE_SERVER_ADDR (location_type l)
      {
        return symbol_type (token::TOK_VARIABLE_SERVER_ADDR, std::move (l));
      }
#else
      static
      symbol_type
      make_VARIABLE_SERVER_ADDR (const location_type& l)
      {
        return symbol_type (token::TOK_VARIABLE_SERVER_ADDR, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_VARIABLE_SERVER_NAME (location_type l)
      {
        return symbol_type (token::TOK_VARIABLE_SERVER_NAME, std::move (l));
      }
#else
      static
      symbol_type
      make_VARIABLE_SERVER_NAME (const location_type& l)
      {
        return symbol_type (token::TOK_VARIABLE_SERVER_NAME, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_VARIABLE_SERVER_PORT (location_type l)
      {
        return symbol_type (token::TOK_VARIABLE_SERVER_PORT, std::move (l));
      }
#else
      static
      symbol_type
      make_VARIABLE_SERVER_PORT (const location_type& l)
      {
        return symbol_type (token::TOK_VARIABLE_SERVER_PORT, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_VARIABLE_SESSION_ID (location_type l)
      {
        return symbol_type (token::TOK_VARIABLE_SESSION_ID, std::move (l));
      }
#else
      static
      symbol_type
      make_VARIABLE_SESSION_ID (const location_type& l)
      {
        return symbol_type (token::TOK_VARIABLE_SESSION_ID, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_VARIABLE_UNIQUE_ID (location_type l)
      {
        return symbol_type (token::TOK_VARIABLE_UNIQUE_ID, std::move (l));
      }
#else
      static
      symbol_type
      make_VARIABLE_UNIQUE_ID (const location_type& l)
      {
        return symbol_type (token::TOK_VARIABLE_UNIQUE_ID, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_VARIABLE_URL_ENCODED_ERROR (location_type l)
      {
        return symbol_type (token::TOK_VARIABLE_URL_ENCODED_ERROR, std::move (l));
      }
#else
      static
      symbol_type
      make_VARIABLE_URL_ENCODED_ERROR (const location_type& l)
      {
        return symbol_type (token::TOK_VARIABLE_URL_ENCODED_ERROR, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_VARIABLE_USER_ID (location_type l)
      {
        return symbol_type (token::TOK_VARIABLE_USER_ID, std::move (l));
      }
#else
      static
      symbol_type
      make_VARIABLE_USER_ID (const location_type& l)
      {
        return symbol_type (token::TOK_VARIABLE_USER_ID, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_VARIABLE_WEB_APP_ID (location_type l)
      {
        return symbol_type (token::TOK_VARIABLE_WEB_APP_ID, std::move (l));
      }
#else
      static
      symbol_type
      make_VARIABLE_WEB_APP_ID (const location_type& l)
      {
        return symbol_type (token::TOK_VARIABLE_WEB_APP_ID, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_VARIABLE_STATUS (location_type l)
      {
        return symbol_type (token::TOK_VARIABLE_STATUS, std::move (l));
      }
#else
      static
      symbol_type
      make_VARIABLE_STATUS (const location_type& l)
      {
        return symbol_type (token::TOK_VARIABLE_STATUS, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_VARIABLE_STATUS_LINE (location_type l)
      {
        return symbol_type (token::TOK_VARIABLE_STATUS_LINE, std::move (l));
      }
#else
      static
      symbol_type
      make_VARIABLE_STATUS_LINE (const location_type& l)
      {
        return symbol_type (token::TOK_VARIABLE_STATUS_LINE, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_VARIABLE_IP (location_type l)
      {
        return symbol_type (token::TOK_VARIABLE_IP, std::move (l));
      }
#else
      static
      symbol_type
      make_VARIABLE_IP (const location_type& l)
      {
        return symbol_type (token::TOK_VARIABLE_IP, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_VARIABLE_GLOBAL (location_type l)
      {
        return symbol_type (token::TOK_VARIABLE_GLOBAL, std::move (l));
      }
#else
      static
      symbol_type
      make_VARIABLE_GLOBAL (const location_type& l)
      {
        return symbol_type (token::TOK_VARIABLE_GLOBAL, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_VARIABLE_TX (location_type l)
      {
        return symbol_type (token::TOK_VARIABLE_TX, std::move (l));
      }
#else
      static
      symbol_type
      make_VARIABLE_TX (const location_type& l)
      {
        return symbol_type (token::TOK_VARIABLE_TX, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_VARIABLE_SESSION (location_type l)
      {
        return symbol_type (token::TOK_VARIABLE_SESSION, std::move (l));
      }
#else
      static
      symbol_type
      make_VARIABLE_SESSION (const location_type& l)
      {
        return symbol_type (token::TOK_VARIABLE_SESSION, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_VARIABLE_USER (location_type l)
      {
        return symbol_type (token::TOK_VARIABLE_USER, std::move (l));
      }
#else
      static
      symbol_type
      make_VARIABLE_USER (const location_type& l)
      {
        return symbol_type (token::TOK_VARIABLE_USER, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_RUN_TIME_VAR_ENV (location_type l)
      {
        return symbol_type (token::TOK_RUN_TIME_VAR_ENV, std::move (l));
      }
#else
      static
      symbol_type
      make_RUN_TIME_VAR_ENV (const location_type& l)
      {
        return symbol_type (token::TOK_RUN_TIME_VAR_ENV, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_RUN_TIME_VAR_XML (location_type l)
      {
        return symbol_type (token::TOK_RUN_TIME_VAR_XML, std::move (l));
      }
#else
      static
      symbol_type
      make_RUN_TIME_VAR_XML (const location_type& l)
      {
        return symbol_type (token::TOK_RUN_TIME_VAR_XML, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_ACTION_SETVAR (location_type l)
      {
        return symbol_type (token::TOK_ACTION_SETVAR, std::move (l));
      }
#else
      static
      symbol_type
      make_ACTION_SETVAR (const location_type& l)
      {
        return symbol_type (token::TOK_ACTION_SETVAR, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_SETVAR_OPERATION_EQUALS (location_type l)
      {
        return symbol_type (token::TOK_SETVAR_OPERATION_EQUALS, std::move (l));
      }
#else
      static
      symbol_type
      make_SETVAR_OPERATION_EQUALS (const location_type& l)
      {
        return symbol_type (token::TOK_SETVAR_OPERATION_EQUALS, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_SETVAR_OPERATION_EQUALS_PLUS (location_type l)
      {
        return symbol_type (token::TOK_SETVAR_OPERATION_EQUALS_PLUS, std::move (l));
      }
#else
      static
      symbol_type
      make_SETVAR_OPERATION_EQUALS_PLUS (const location_type& l)
      {
        return symbol_type (token::TOK_SETVAR_OPERATION_EQUALS_PLUS, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_SETVAR_OPERATION_EQUALS_MINUS (location_type l)
      {
        return symbol_type (token::TOK_SETVAR_OPERATION_EQUALS_MINUS, std::move (l));
      }
#else
      static
      symbol_type
      make_SETVAR_OPERATION_EQUALS_MINUS (const location_type& l)
      {
        return symbol_type (token::TOK_SETVAR_OPERATION_EQUALS_MINUS, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_NOT (location_type l)
      {
        return symbol_type (token::TOK_NOT, std::move (l));
      }
#else
      static
      symbol_type
      make_NOT (const location_type& l)
      {
        return symbol_type (token::TOK_NOT, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_OPERATOR_BEGINS_WITH (location_type l)
      {
        return symbol_type (token::TOK_OPERATOR_BEGINS_WITH, std::move (l));
      }
#else
      static
      symbol_type
      make_OPERATOR_BEGINS_WITH (const location_type& l)
      {
        return symbol_type (token::TOK_OPERATOR_BEGINS_WITH, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_OPERATOR_CONTAINS (location_type l)
      {
        return symbol_type (token::TOK_OPERATOR_CONTAINS, std::move (l));
      }
#else
      static
      symbol_type
      make_OPERATOR_CONTAINS (const location_type& l)
      {
        return symbol_type (token::TOK_OPERATOR_CONTAINS, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_OPERATOR_CONTAINS_WORD (location_type l)
      {
        return symbol_type (token::TOK_OPERATOR_CONTAINS_WORD, std::move (l));
      }
#else
      static
      symbol_type
      make_OPERATOR_CONTAINS_WORD (const location_type& l)
      {
        return symbol_type (token::TOK_OPERATOR_CONTAINS_WORD, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_OPERATOR_DETECT_SQLI (location_type l)
      {
        return symbol_type (token::TOK_OPERATOR_DETECT_SQLI, std::move (l));
      }
#else
      static
      symbol_type
      make_OPERATOR_DETECT_SQLI (const location_type& l)
      {
        return symbol_type (token::TOK_OPERATOR_DETECT_SQLI, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_OPERATOR_DETECT_XSS (location_type l)
      {
        return symbol_type (token::TOK_OPERATOR_DETECT_XSS, std::move (l));
      }
#else
      static
      symbol_type
      make_OPERATOR_DETECT_XSS (const location_type& l)
      {
        return symbol_type (token::TOK_OPERATOR_DETECT_XSS, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_OPERATOR_ENDS_WITH (location_type l)
      {
        return symbol_type (token::TOK_OPERATOR_ENDS_WITH, std::move (l));
      }
#else
      static
      symbol_type
      make_OPERATOR_ENDS_WITH (const location_type& l)
      {
        return symbol_type (token::TOK_OPERATOR_ENDS_WITH, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_OPERATOR_EQ (location_type l)
      {
        return symbol_type (token::TOK_OPERATOR_EQ, std::move (l));
      }
#else
      static
      symbol_type
      make_OPERATOR_EQ (const location_type& l)
      {
        return symbol_type (token::TOK_OPERATOR_EQ, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_OPERATOR_FUZZY_HASH (location_type l)
      {
        return symbol_type (token::TOK_OPERATOR_FUZZY_HASH, std::move (l));
      }
#else
      static
      symbol_type
      make_OPERATOR_FUZZY_HASH (const location_type& l)
      {
        return symbol_type (token::TOK_OPERATOR_FUZZY_HASH, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_OPERATOR_GEOLOOKUP (location_type l)
      {
        return symbol_type (token::TOK_OPERATOR_GEOLOOKUP, std::move (l));
      }
#else
      static
      symbol_type
      make_OPERATOR_GEOLOOKUP (const location_type& l)
      {
        return symbol_type (token::TOK_OPERATOR_GEOLOOKUP, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_OPERATOR_GE (location_type l)
      {
        return symbol_type (token::TOK_OPERATOR_GE, std::move (l));
      }
#else
      static
      symbol_type
      make_OPERATOR_GE (const location_type& l)
      {
        return symbol_type (token::TOK_OPERATOR_GE, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_OPERATOR_GSB_LOOKUP (location_type l)
      {
        return symbol_type (token::TOK_OPERATOR_GSB_LOOKUP, std::move (l));
      }
#else
      static
      symbol_type
      make_OPERATOR_GSB_LOOKUP (const location_type& l)
      {
        return symbol_type (token::TOK_OPERATOR_GSB_LOOKUP, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_OPERATOR_GT (location_type l)
      {
        return symbol_type (token::TOK_OPERATOR_GT, std::move (l));
      }
#else
      static
      symbol_type
      make_OPERATOR_GT (const location_type& l)
      {
        return symbol_type (token::TOK_OPERATOR_GT, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_OPERATOR_INSPECT_FILE (location_type l)
      {
        return symbol_type (token::TOK_OPERATOR_INSPECT_FILE, std::move (l));
      }
#else
      static
      symbol_type
      make_OPERATOR_INSPECT_FILE (const location_type& l)
      {
        return symbol_type (token::TOK_OPERATOR_INSPECT_FILE, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_OPERATOR_IP_MATCH_FROM_FILE (location_type l)
      {
        return symbol_type (token::TOK_OPERATOR_IP_MATCH_FROM_FILE, std::move (l));
      }
#else
      static
      symbol_type
      make_OPERATOR_IP_MATCH_FROM_FILE (const location_type& l)
      {
        return symbol_type (token::TOK_OPERATOR_IP_MATCH_FROM_FILE, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_OPERATOR_IP_MATCH (location_type l)
      {
        return symbol_type (token::TOK_OPERATOR_IP_MATCH, std::move (l));
      }
#else
      static
      symbol_type
      make_OPERATOR_IP_MATCH (const location_type& l)
      {
        return symbol_type (token::TOK_OPERATOR_IP_MATCH, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_OPERATOR_LE (location_type l)
      {
        return symbol_type (token::TOK_OPERATOR_LE, std::move (l));
      }
#else
      static
      symbol_type
      make_OPERATOR_LE (const location_type& l)
      {
        return symbol_type (token::TOK_OPERATOR_LE, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_OPERATOR_LT (location_type l)
      {
        return symbol_type (token::TOK_OPERATOR_LT, std::move (l));
      }
#else
      static
      symbol_type
      make_OPERATOR_LT (const location_type& l)
      {
        return symbol_type (token::TOK_OPERATOR_LT, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_OPERATOR_PM_FROM_FILE (location_type l)
      {
        return symbol_type (token::TOK_OPERATOR_PM_FROM_FILE, std::move (l));
      }
#else
      static
      symbol_type
      make_OPERATOR_PM_FROM_FILE (const location_type& l)
      {
        return symbol_type (token::TOK_OPERATOR_PM_FROM_FILE, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_OPERATOR_PM (location_type l)
      {
        return symbol_type (token::TOK_OPERATOR_PM, std::move (l));
      }
#else
      static
      symbol_type
      make_OPERATOR_PM (const location_type& l)
      {
        return symbol_type (token::TOK_OPERATOR_PM, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_OPERATOR_RBL (location_type l)
      {
        return symbol_type (token::TOK_OPERATOR_RBL, std::move (l));
      }
#else
      static
      symbol_type
      make_OPERATOR_RBL (const location_type& l)
      {
        return symbol_type (token::TOK_OPERATOR_RBL, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_OPERATOR_RSUB (location_type l)
      {
        return symbol_type (token::TOK_OPERATOR_RSUB, std::move (l));
      }
#else
      static
      symbol_type
      make_OPERATOR_RSUB (const location_type& l)
      {
        return symbol_type (token::TOK_OPERATOR_RSUB, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_OPERATOR_RX_CONTENT_ONLY (location_type l)
      {
        return symbol_type (token::TOK_OPERATOR_RX_CONTENT_ONLY, std::move (l));
      }
#else
      static
      symbol_type
      make_OPERATOR_RX_CONTENT_ONLY (const location_type& l)
      {
        return symbol_type (token::TOK_OPERATOR_RX_CONTENT_ONLY, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_OPERATOR_RX (location_type l)
      {
        return symbol_type (token::TOK_OPERATOR_RX, std::move (l));
      }
#else
      static
      symbol_type
      make_OPERATOR_RX (const location_type& l)
      {
        return symbol_type (token::TOK_OPERATOR_RX, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_OPERATOR_STR_EQ (location_type l)
      {
        return symbol_type (token::TOK_OPERATOR_STR_EQ, std::move (l));
      }
#else
      static
      symbol_type
      make_OPERATOR_STR_EQ (const location_type& l)
      {
        return symbol_type (token::TOK_OPERATOR_STR_EQ, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_OPERATOR_STR_MATCH (location_type l)
      {
        return symbol_type (token::TOK_OPERATOR_STR_MATCH, std::move (l));
      }
#else
      static
      symbol_type
      make_OPERATOR_STR_MATCH (const location_type& l)
      {
        return symbol_type (token::TOK_OPERATOR_STR_MATCH, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_OPERATOR_UNCONDITIONAL_MATCH (location_type l)
      {
        return symbol_type (token::TOK_OPERATOR_UNCONDITIONAL_MATCH, std::move (l));
      }
#else
      static
      symbol_type
      make_OPERATOR_UNCONDITIONAL_MATCH (const location_type& l)
      {
        return symbol_type (token::TOK_OPERATOR_UNCONDITIONAL_MATCH, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_OPERATOR_VALIDATE_BYTE_RANGE (location_type l)
      {
        return symbol_type (token::TOK_OPERATOR_VALIDATE_BYTE_RANGE, std::move (l));
      }
#else
      static
      symbol_type
      make_OPERATOR_VALIDATE_BYTE_RANGE (const location_type& l)
      {
        return symbol_type (token::TOK_OPERATOR_VALIDATE_BYTE_RANGE, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_OPERATOR_VALIDATE_DTD (location_type l)
      {
        return symbol_type (token::TOK_OPERATOR_VALIDATE_DTD, std::move (l));
      }
#else
      static
      symbol_type
      make_OPERATOR_VALIDATE_DTD (const location_type& l)
      {
        return symbol_type (token::TOK_OPERATOR_VALIDATE_DTD, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_OPERATOR_VALIDATE_HASH (location_type l)
      {
        return symbol_type (token::TOK_OPERATOR_VALIDATE_HASH, std::move (l));
      }
#else
      static
      symbol_type
      make_OPERATOR_VALIDATE_HASH (const location_type& l)
      {
        return symbol_type (token::TOK_OPERATOR_VALIDATE_HASH, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_OPERATOR_VALIDATE_SCHEMA (location_type l)
      {
        return symbol_type (token::TOK_OPERATOR_VALIDATE_SCHEMA, std::move (l));
      }
#else
      static
      symbol_type
      make_OPERATOR_VALIDATE_SCHEMA (const location_type& l)
      {
        return symbol_type (token::TOK_OPERATOR_VALIDATE_SCHEMA, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_OPERATOR_VALIDATE_URL_ENCODING (location_type l)
      {
        return symbol_type (token::TOK_OPERATOR_VALIDATE_URL_ENCODING, std::move (l));
      }
#else
      static
      symbol_type
      make_OPERATOR_VALIDATE_URL_ENCODING (const location_type& l)
      {
        return symbol_type (token::TOK_OPERATOR_VALIDATE_URL_ENCODING, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_OPERATOR_VALIDATE_UTF8_ENCODING (location_type l)
      {
        return symbol_type (token::TOK_OPERATOR_VALIDATE_UTF8_ENCODING, std::move (l));
      }
#else
      static
      symbol_type
      make_OPERATOR_VALIDATE_UTF8_ENCODING (const location_type& l)
      {
        return symbol_type (token::TOK_OPERATOR_VALIDATE_UTF8_ENCODING, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_OPERATOR_VERIFY_CC (location_type l)
      {
        return symbol_type (token::TOK_OPERATOR_VERIFY_CC, std::move (l));
      }
#else
      static
      symbol_type
      make_OPERATOR_VERIFY_CC (const location_type& l)
      {
        return symbol_type (token::TOK_OPERATOR_VERIFY_CC, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_OPERATOR_VERIFY_CPF (location_type l)
      {
        return symbol_type (token::TOK_OPERATOR_VERIFY_CPF, std::move (l));
      }
#else
      static
      symbol_type
      make_OPERATOR_VERIFY_CPF (const location_type& l)
      {
        return symbol_type (token::TOK_OPERATOR_VERIFY_CPF, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_OPERATOR_VERIFY_SSN (location_type l)
      {
        return symbol_type (token::TOK_OPERATOR_VERIFY_SSN, std::move (l));
      }
#else
      static
      symbol_type
      make_OPERATOR_VERIFY_SSN (const location_type& l)
      {
        return symbol_type (token::TOK_OPERATOR_VERIFY_SSN, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_OPERATOR_VERIFY_SVNR (location_type l)
      {
        return symbol_type (token::TOK_OPERATOR_VERIFY_SVNR, std::move (l));
      }
#else
      static
      symbol_type
      make_OPERATOR_VERIFY_SVNR (const location_type& l)
      {
        return symbol_type (token::TOK_OPERATOR_VERIFY_SVNR, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_OPERATOR_WITHIN (location_type l)
      {
        return symbol_type (token::TOK_OPERATOR_WITHIN, std::move (l));
      }
#else
      static
      symbol_type
      make_OPERATOR_WITHIN (const location_type& l)
      {
        return symbol_type (token::TOK_OPERATOR_WITHIN, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_CONFIG_DIR_AUDIT_LOG_FMT (location_type l)
      {
        return symbol_type (token::TOK_CONFIG_DIR_AUDIT_LOG_FMT, std::move (l));
      }
#else
      static
      symbol_type
      make_CONFIG_DIR_AUDIT_LOG_FMT (const location_type& l)
      {
        return symbol_type (token::TOK_CONFIG_DIR_AUDIT_LOG_FMT, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_JSON (location_type l)
      {
        return symbol_type (token::TOK_JSON, std::move (l));
      }
#else
      static
      symbol_type
      make_JSON (const location_type& l)
      {
        return symbol_type (token::TOK_JSON, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_NATIVE (location_type l)
      {
        return symbol_type (token::TOK_NATIVE, std::move (l));
      }
#else
      static
      symbol_type
      make_NATIVE (const location_type& l)
      {
        return symbol_type (token::TOK_NATIVE, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_ACTION_CTL_RULE_ENGINE (location_type l)
      {
        return symbol_type (token::TOK_ACTION_CTL_RULE_ENGINE, std::move (l));
      }
#else
      static
      symbol_type
      make_ACTION_CTL_RULE_ENGINE (const location_type& l)
      {
        return symbol_type (token::TOK_ACTION_CTL_RULE_ENGINE, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_ACTION_ACCURACY (std::string v, location_type l)
      {
        return symbol_type (token::TOK_ACTION_ACCURACY, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_ACTION_ACCURACY (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_ACTION_ACCURACY, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_ACTION_ALLOW (std::string v, location_type l)
      {
        return symbol_type (token::TOK_ACTION_ALLOW, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_ACTION_ALLOW (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_ACTION_ALLOW, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_ACTION_APPEND (std::string v, location_type l)
      {
        return symbol_type (token::TOK_ACTION_APPEND, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_ACTION_APPEND (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_ACTION_APPEND, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_ACTION_AUDIT_LOG (std::string v, location_type l)
      {
        return symbol_type (token::TOK_ACTION_AUDIT_LOG, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_ACTION_AUDIT_LOG (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_ACTION_AUDIT_LOG, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_ACTION_BLOCK (std::string v, location_type l)
      {
        return symbol_type (token::TOK_ACTION_BLOCK, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_ACTION_BLOCK (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_ACTION_BLOCK, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_ACTION_CAPTURE (std::string v, location_type l)
      {
        return symbol_type (token::TOK_ACTION_CAPTURE, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_ACTION_CAPTURE (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_ACTION_CAPTURE, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_ACTION_CHAIN (std::string v, location_type l)
      {
        return symbol_type (token::TOK_ACTION_CHAIN, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_ACTION_CHAIN (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_ACTION_CHAIN, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_ACTION_CTL_AUDIT_ENGINE (std::string v, location_type l)
      {
        return symbol_type (token::TOK_ACTION_CTL_AUDIT_ENGINE, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_ACTION_CTL_AUDIT_ENGINE (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_ACTION_CTL_AUDIT_ENGINE, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_ACTION_CTL_AUDIT_LOG_PARTS (std::string v, location_type l)
      {
        return symbol_type (token::TOK_ACTION_CTL_AUDIT_LOG_PARTS, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_ACTION_CTL_AUDIT_LOG_PARTS (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_ACTION_CTL_AUDIT_LOG_PARTS, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_ACTION_CTL_BDY_JSON (std::string v, location_type l)
      {
        return symbol_type (token::TOK_ACTION_CTL_BDY_JSON, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_ACTION_CTL_BDY_JSON (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_ACTION_CTL_BDY_JSON, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_ACTION_CTL_BDY_XML (std::string v, location_type l)
      {
        return symbol_type (token::TOK_ACTION_CTL_BDY_XML, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_ACTION_CTL_BDY_XML (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_ACTION_CTL_BDY_XML, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_ACTION_CTL_BDY_URLENCODED (std::string v, location_type l)
      {
        return symbol_type (token::TOK_ACTION_CTL_BDY_URLENCODED, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_ACTION_CTL_BDY_URLENCODED (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_ACTION_CTL_BDY_URLENCODED, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_ACTION_CTL_FORCE_REQ_BODY_VAR (std::string v, location_type l)
      {
        return symbol_type (token::TOK_ACTION_CTL_FORCE_REQ_BODY_VAR, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_ACTION_CTL_FORCE_REQ_BODY_VAR (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_ACTION_CTL_FORCE_REQ_BODY_VAR, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_ACTION_CTL_REQUEST_BODY_ACCESS (std::string v, location_type l)
      {
        return symbol_type (token::TOK_ACTION_CTL_REQUEST_BODY_ACCESS, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_ACTION_CTL_REQUEST_BODY_ACCESS (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_ACTION_CTL_REQUEST_BODY_ACCESS, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_ACTION_CTL_RULE_REMOVE_BY_ID (std::string v, location_type l)
      {
        return symbol_type (token::TOK_ACTION_CTL_RULE_REMOVE_BY_ID, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_ACTION_CTL_RULE_REMOVE_BY_ID (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_ACTION_CTL_RULE_REMOVE_BY_ID, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_ACTION_CTL_RULE_REMOVE_BY_TAG (std::string v, location_type l)
      {
        return symbol_type (token::TOK_ACTION_CTL_RULE_REMOVE_BY_TAG, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_ACTION_CTL_RULE_REMOVE_BY_TAG (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_ACTION_CTL_RULE_REMOVE_BY_TAG, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_ACTION_CTL_RULE_REMOVE_TARGET_BY_ID (std::string v, location_type l)
      {
        return symbol_type (token::TOK_ACTION_CTL_RULE_REMOVE_TARGET_BY_ID, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_ACTION_CTL_RULE_REMOVE_TARGET_BY_ID (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_ACTION_CTL_RULE_REMOVE_TARGET_BY_ID, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_ACTION_CTL_RULE_REMOVE_TARGET_BY_TAG (std::string v, location_type l)
      {
        return symbol_type (token::TOK_ACTION_CTL_RULE_REMOVE_TARGET_BY_TAG, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_ACTION_CTL_RULE_REMOVE_TARGET_BY_TAG (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_ACTION_CTL_RULE_REMOVE_TARGET_BY_TAG, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_ACTION_DENY (std::string v, location_type l)
      {
        return symbol_type (token::TOK_ACTION_DENY, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_ACTION_DENY (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_ACTION_DENY, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_ACTION_DEPRECATE_VAR (std::string v, location_type l)
      {
        return symbol_type (token::TOK_ACTION_DEPRECATE_VAR, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_ACTION_DEPRECATE_VAR (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_ACTION_DEPRECATE_VAR, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_ACTION_DROP (std::string v, location_type l)
      {
        return symbol_type (token::TOK_ACTION_DROP, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_ACTION_DROP (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_ACTION_DROP, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_ACTION_EXEC (std::string v, location_type l)
      {
        return symbol_type (token::TOK_ACTION_EXEC, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_ACTION_EXEC (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_ACTION_EXEC, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_ACTION_EXPIRE_VAR (std::string v, location_type l)
      {
        return symbol_type (token::TOK_ACTION_EXPIRE_VAR, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_ACTION_EXPIRE_VAR (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_ACTION_EXPIRE_VAR, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_ACTION_ID (std::string v, location_type l)
      {
        return symbol_type (token::TOK_ACTION_ID, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_ACTION_ID (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_ACTION_ID, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_ACTION_INITCOL (std::string v, location_type l)
      {
        return symbol_type (token::TOK_ACTION_INITCOL, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_ACTION_INITCOL (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_ACTION_INITCOL, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_ACTION_LOG (std::string v, location_type l)
      {
        return symbol_type (token::TOK_ACTION_LOG, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_ACTION_LOG (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_ACTION_LOG, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_ACTION_LOG_DATA (std::string v, location_type l)
      {
        return symbol_type (token::TOK_ACTION_LOG_DATA, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_ACTION_LOG_DATA (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_ACTION_LOG_DATA, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_ACTION_MATURITY (std::string v, location_type l)
      {
        return symbol_type (token::TOK_ACTION_MATURITY, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_ACTION_MATURITY (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_ACTION_MATURITY, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_ACTION_MSG (std::string v, location_type l)
      {
        return symbol_type (token::TOK_ACTION_MSG, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_ACTION_MSG (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_ACTION_MSG, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_ACTION_MULTI_MATCH (std::string v, location_type l)
      {
        return symbol_type (token::TOK_ACTION_MULTI_MATCH, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_ACTION_MULTI_MATCH (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_ACTION_MULTI_MATCH, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_ACTION_NO_AUDIT_LOG (std::string v, location_type l)
      {
        return symbol_type (token::TOK_ACTION_NO_AUDIT_LOG, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_ACTION_NO_AUDIT_LOG (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_ACTION_NO_AUDIT_LOG, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_ACTION_NO_LOG (std::string v, location_type l)
      {
        return symbol_type (token::TOK_ACTION_NO_LOG, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_ACTION_NO_LOG (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_ACTION_NO_LOG, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_ACTION_PASS (std::string v, location_type l)
      {
        return symbol_type (token::TOK_ACTION_PASS, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_ACTION_PASS (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_ACTION_PASS, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_ACTION_PAUSE (std::string v, location_type l)
      {
        return symbol_type (token::TOK_ACTION_PAUSE, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_ACTION_PAUSE (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_ACTION_PAUSE, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_ACTION_PHASE (std::string v, location_type l)
      {
        return symbol_type (token::TOK_ACTION_PHASE, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_ACTION_PHASE (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_ACTION_PHASE, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_ACTION_PREPEND (std::string v, location_type l)
      {
        return symbol_type (token::TOK_ACTION_PREPEND, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_ACTION_PREPEND (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_ACTION_PREPEND, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_ACTION_PROXY (std::string v, location_type l)
      {
        return symbol_type (token::TOK_ACTION_PROXY, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_ACTION_PROXY (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_ACTION_PROXY, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_ACTION_REDIRECT (std::string v, location_type l)
      {
        return symbol_type (token::TOK_ACTION_REDIRECT, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_ACTION_REDIRECT (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_ACTION_REDIRECT, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_ACTION_REV (std::string v, location_type l)
      {
        return symbol_type (token::TOK_ACTION_REV, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_ACTION_REV (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_ACTION_REV, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_ACTION_SANITISE_ARG (std::string v, location_type l)
      {
        return symbol_type (token::TOK_ACTION_SANITISE_ARG, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_ACTION_SANITISE_ARG (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_ACTION_SANITISE_ARG, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_ACTION_SANITISE_MATCHED (std::string v, location_type l)
      {
        return symbol_type (token::TOK_ACTION_SANITISE_MATCHED, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_ACTION_SANITISE_MATCHED (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_ACTION_SANITISE_MATCHED, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_ACTION_SANITISE_MATCHED_BYTES (std::string v, location_type l)
      {
        return symbol_type (token::TOK_ACTION_SANITISE_MATCHED_BYTES, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_ACTION_SANITISE_MATCHED_BYTES (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_ACTION_SANITISE_MATCHED_BYTES, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_ACTION_SANITISE_REQUEST_HEADER (std::string v, location_type l)
      {
        return symbol_type (token::TOK_ACTION_SANITISE_REQUEST_HEADER, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_ACTION_SANITISE_REQUEST_HEADER (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_ACTION_SANITISE_REQUEST_HEADER, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_ACTION_SANITISE_RESPONSE_HEADER (std::string v, location_type l)
      {
        return symbol_type (token::TOK_ACTION_SANITISE_RESPONSE_HEADER, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_ACTION_SANITISE_RESPONSE_HEADER (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_ACTION_SANITISE_RESPONSE_HEADER, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_ACTION_SETENV (std::string v, location_type l)
      {
        return symbol_type (token::TOK_ACTION_SETENV, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_ACTION_SETENV (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_ACTION_SETENV, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_ACTION_SETRSC (std::string v, location_type l)
      {
        return symbol_type (token::TOK_ACTION_SETRSC, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_ACTION_SETRSC (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_ACTION_SETRSC, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_ACTION_SETSID (std::string v, location_type l)
      {
        return symbol_type (token::TOK_ACTION_SETSID, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_ACTION_SETSID (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_ACTION_SETSID, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_ACTION_SETUID (std::string v, location_type l)
      {
        return symbol_type (token::TOK_ACTION_SETUID, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_ACTION_SETUID (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_ACTION_SETUID, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_ACTION_SEVERITY (std::string v, location_type l)
      {
        return symbol_type (token::TOK_ACTION_SEVERITY, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_ACTION_SEVERITY (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_ACTION_SEVERITY, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_ACTION_SKIP (std::string v, location_type l)
      {
        return symbol_type (token::TOK_ACTION_SKIP, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_ACTION_SKIP (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_ACTION_SKIP, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_ACTION_SKIP_AFTER (std::string v, location_type l)
      {
        return symbol_type (token::TOK_ACTION_SKIP_AFTER, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_ACTION_SKIP_AFTER (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_ACTION_SKIP_AFTER, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_ACTION_STATUS (std::string v, location_type l)
      {
        return symbol_type (token::TOK_ACTION_STATUS, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_ACTION_STATUS (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_ACTION_STATUS, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_ACTION_TAG (std::string v, location_type l)
      {
        return symbol_type (token::TOK_ACTION_TAG, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_ACTION_TAG (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_ACTION_TAG, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_ACTION_TRANSFORMATION_BASE_64_ENCODE (std::string v, location_type l)
      {
        return symbol_type (token::TOK_ACTION_TRANSFORMATION_BASE_64_ENCODE, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_ACTION_TRANSFORMATION_BASE_64_ENCODE (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_ACTION_TRANSFORMATION_BASE_64_ENCODE, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_ACTION_TRANSFORMATION_BASE_64_DECODE (std::string v, location_type l)
      {
        return symbol_type (token::TOK_ACTION_TRANSFORMATION_BASE_64_DECODE, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_ACTION_TRANSFORMATION_BASE_64_DECODE (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_ACTION_TRANSFORMATION_BASE_64_DECODE, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_ACTION_TRANSFORMATION_BASE_64_DECODE_EXT (std::string v, location_type l)
      {
        return symbol_type (token::TOK_ACTION_TRANSFORMATION_BASE_64_DECODE_EXT, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_ACTION_TRANSFORMATION_BASE_64_DECODE_EXT (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_ACTION_TRANSFORMATION_BASE_64_DECODE_EXT, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_ACTION_TRANSFORMATION_CMD_LINE (std::string v, location_type l)
      {
        return symbol_type (token::TOK_ACTION_TRANSFORMATION_CMD_LINE, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_ACTION_TRANSFORMATION_CMD_LINE (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_ACTION_TRANSFORMATION_CMD_LINE, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_ACTION_TRANSFORMATION_COMPRESS_WHITESPACE (std::string v, location_type l)
      {
        return symbol_type (token::TOK_ACTION_TRANSFORMATION_COMPRESS_WHITESPACE, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_ACTION_TRANSFORMATION_COMPRESS_WHITESPACE (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_ACTION_TRANSFORMATION_COMPRESS_WHITESPACE, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_ACTION_TRANSFORMATION_CSS_DECODE (std::string v, location_type l)
      {
        return symbol_type (token::TOK_ACTION_TRANSFORMATION_CSS_DECODE, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_ACTION_TRANSFORMATION_CSS_DECODE (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_ACTION_TRANSFORMATION_CSS_DECODE, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_ACTION_TRANSFORMATION_ESCAPE_SEQ_DECODE (std::string v, location_type l)
      {
        return symbol_type (token::TOK_ACTION_TRANSFORMATION_ESCAPE_SEQ_DECODE, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_ACTION_TRANSFORMATION_ESCAPE_SEQ_DECODE (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_ACTION_TRANSFORMATION_ESCAPE_SEQ_DECODE, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_ACTION_TRANSFORMATION_HEX_ENCODE (std::string v, location_type l)
      {
        return symbol_type (token::TOK_ACTION_TRANSFORMATION_HEX_ENCODE, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_ACTION_TRANSFORMATION_HEX_ENCODE (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_ACTION_TRANSFORMATION_HEX_ENCODE, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_ACTION_TRANSFORMATION_HEX_DECODE (std::string v, location_type l)
      {
        return symbol_type (token::TOK_ACTION_TRANSFORMATION_HEX_DECODE, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_ACTION_TRANSFORMATION_HEX_DECODE (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_ACTION_TRANSFORMATION_HEX_DECODE, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_ACTION_TRANSFORMATION_HTML_ENTITY_DECODE (std::string v, location_type l)
      {
        return symbol_type (token::TOK_ACTION_TRANSFORMATION_HTML_ENTITY_DECODE, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_ACTION_TRANSFORMATION_HTML_ENTITY_DECODE (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_ACTION_TRANSFORMATION_HTML_ENTITY_DECODE, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_ACTION_TRANSFORMATION_JS_DECODE (std::string v, location_type l)
      {
        return symbol_type (token::TOK_ACTION_TRANSFORMATION_JS_DECODE, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_ACTION_TRANSFORMATION_JS_DECODE (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_ACTION_TRANSFORMATION_JS_DECODE, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_ACTION_TRANSFORMATION_LENGTH (std::string v, location_type l)
      {
        return symbol_type (token::TOK_ACTION_TRANSFORMATION_LENGTH, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_ACTION_TRANSFORMATION_LENGTH (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_ACTION_TRANSFORMATION_LENGTH, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_ACTION_TRANSFORMATION_LOWERCASE (std::string v, location_type l)
      {
        return symbol_type (token::TOK_ACTION_TRANSFORMATION_LOWERCASE, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_ACTION_TRANSFORMATION_LOWERCASE (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_ACTION_TRANSFORMATION_LOWERCASE, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_ACTION_TRANSFORMATION_MD5 (std::string v, location_type l)
      {
        return symbol_type (token::TOK_ACTION_TRANSFORMATION_MD5, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_ACTION_TRANSFORMATION_MD5 (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_ACTION_TRANSFORMATION_MD5, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_ACTION_TRANSFORMATION_NONE (std::string v, location_type l)
      {
        return symbol_type (token::TOK_ACTION_TRANSFORMATION_NONE, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_ACTION_TRANSFORMATION_NONE (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_ACTION_TRANSFORMATION_NONE, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_ACTION_TRANSFORMATION_NORMALISE_PATH (std::string v, location_type l)
      {
        return symbol_type (token::TOK_ACTION_TRANSFORMATION_NORMALISE_PATH, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_ACTION_TRANSFORMATION_NORMALISE_PATH (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_ACTION_TRANSFORMATION_NORMALISE_PATH, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_ACTION_TRANSFORMATION_NORMALISE_PATH_WIN (std::string v, location_type l)
      {
        return symbol_type (token::TOK_ACTION_TRANSFORMATION_NORMALISE_PATH_WIN, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_ACTION_TRANSFORMATION_NORMALISE_PATH_WIN (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_ACTION_TRANSFORMATION_NORMALISE_PATH_WIN, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_ACTION_TRANSFORMATION_PARITY_EVEN_7_BIT (std::string v, location_type l)
      {
        return symbol_type (token::TOK_ACTION_TRANSFORMATION_PARITY_EVEN_7_BIT, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_ACTION_TRANSFORMATION_PARITY_EVEN_7_BIT (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_ACTION_TRANSFORMATION_PARITY_EVEN_7_BIT, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_ACTION_TRANSFORMATION_PARITY_ODD_7_BIT (std::string v, location_type l)
      {
        return symbol_type (token::TOK_ACTION_TRANSFORMATION_PARITY_ODD_7_BIT, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_ACTION_TRANSFORMATION_PARITY_ODD_7_BIT (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_ACTION_TRANSFORMATION_PARITY_ODD_7_BIT, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_ACTION_TRANSFORMATION_PARITY_ZERO_7_BIT (std::string v, location_type l)
      {
        return symbol_type (token::TOK_ACTION_TRANSFORMATION_PARITY_ZERO_7_BIT, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_ACTION_TRANSFORMATION_PARITY_ZERO_7_BIT (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_ACTION_TRANSFORMATION_PARITY_ZERO_7_BIT, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_ACTION_TRANSFORMATION_REMOVE_COMMENTS (std::string v, location_type l)
      {
        return symbol_type (token::TOK_ACTION_TRANSFORMATION_REMOVE_COMMENTS, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_ACTION_TRANSFORMATION_REMOVE_COMMENTS (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_ACTION_TRANSFORMATION_REMOVE_COMMENTS, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_ACTION_TRANSFORMATION_REMOVE_COMMENTS_CHAR (std::string v, location_type l)
      {
        return symbol_type (token::TOK_ACTION_TRANSFORMATION_REMOVE_COMMENTS_CHAR, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_ACTION_TRANSFORMATION_REMOVE_COMMENTS_CHAR (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_ACTION_TRANSFORMATION_REMOVE_COMMENTS_CHAR, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_ACTION_TRANSFORMATION_REMOVE_NULLS (std::string v, location_type l)
      {
        return symbol_type (token::TOK_ACTION_TRANSFORMATION_REMOVE_NULLS, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_ACTION_TRANSFORMATION_REMOVE_NULLS (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_ACTION_TRANSFORMATION_REMOVE_NULLS, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_ACTION_TRANSFORMATION_REMOVE_WHITESPACE (std::string v, location_type l)
      {
        return symbol_type (token::TOK_ACTION_TRANSFORMATION_REMOVE_WHITESPACE, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_ACTION_TRANSFORMATION_REMOVE_WHITESPACE (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_ACTION_TRANSFORMATION_REMOVE_WHITESPACE, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_ACTION_TRANSFORMATION_REPLACE_COMMENTS (std::string v, location_type l)
      {
        return symbol_type (token::TOK_ACTION_TRANSFORMATION_REPLACE_COMMENTS, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_ACTION_TRANSFORMATION_REPLACE_COMMENTS (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_ACTION_TRANSFORMATION_REPLACE_COMMENTS, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_ACTION_TRANSFORMATION_REPLACE_NULLS (std::string v, location_type l)
      {
        return symbol_type (token::TOK_ACTION_TRANSFORMATION_REPLACE_NULLS, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_ACTION_TRANSFORMATION_REPLACE_NULLS (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_ACTION_TRANSFORMATION_REPLACE_NULLS, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_ACTION_TRANSFORMATION_SHA1 (std::string v, location_type l)
      {
        return symbol_type (token::TOK_ACTION_TRANSFORMATION_SHA1, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_ACTION_TRANSFORMATION_SHA1 (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_ACTION_TRANSFORMATION_SHA1, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_ACTION_TRANSFORMATION_SQL_HEX_DECODE (std::string v, location_type l)
      {
        return symbol_type (token::TOK_ACTION_TRANSFORMATION_SQL_HEX_DECODE, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_ACTION_TRANSFORMATION_SQL_HEX_DECODE (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_ACTION_TRANSFORMATION_SQL_HEX_DECODE, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_ACTION_TRANSFORMATION_TRIM (std::string v, location_type l)
      {
        return symbol_type (token::TOK_ACTION_TRANSFORMATION_TRIM, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_ACTION_TRANSFORMATION_TRIM (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_ACTION_TRANSFORMATION_TRIM, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_ACTION_TRANSFORMATION_TRIM_LEFT (std::string v, location_type l)
      {
        return symbol_type (token::TOK_ACTION_TRANSFORMATION_TRIM_LEFT, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_ACTION_TRANSFORMATION_TRIM_LEFT (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_ACTION_TRANSFORMATION_TRIM_LEFT, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_ACTION_TRANSFORMATION_TRIM_RIGHT (std::string v, location_type l)
      {
        return symbol_type (token::TOK_ACTION_TRANSFORMATION_TRIM_RIGHT, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_ACTION_TRANSFORMATION_TRIM_RIGHT (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_ACTION_TRANSFORMATION_TRIM_RIGHT, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_ACTION_TRANSFORMATION_UPPERCASE (std::string v, location_type l)
      {
        return symbol_type (token::TOK_ACTION_TRANSFORMATION_UPPERCASE, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_ACTION_TRANSFORMATION_UPPERCASE (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_ACTION_TRANSFORMATION_UPPERCASE, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_ACTION_TRANSFORMATION_URL_ENCODE (std::string v, location_type l)
      {
        return symbol_type (token::TOK_ACTION_TRANSFORMATION_URL_ENCODE, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_ACTION_TRANSFORMATION_URL_ENCODE (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_ACTION_TRANSFORMATION_URL_ENCODE, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_ACTION_TRANSFORMATION_URL_DECODE (std::string v, location_type l)
      {
        return symbol_type (token::TOK_ACTION_TRANSFORMATION_URL_DECODE, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_ACTION_TRANSFORMATION_URL_DECODE (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_ACTION_TRANSFORMATION_URL_DECODE, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_ACTION_TRANSFORMATION_URL_DECODE_UNI (std::string v, location_type l)
      {
        return symbol_type (token::TOK_ACTION_TRANSFORMATION_URL_DECODE_UNI, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_ACTION_TRANSFORMATION_URL_DECODE_UNI (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_ACTION_TRANSFORMATION_URL_DECODE_UNI, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_ACTION_TRANSFORMATION_UTF8_TO_UNICODE (std::string v, location_type l)
      {
        return symbol_type (token::TOK_ACTION_TRANSFORMATION_UTF8_TO_UNICODE, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_ACTION_TRANSFORMATION_UTF8_TO_UNICODE (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_ACTION_TRANSFORMATION_UTF8_TO_UNICODE, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_ACTION_VER (std::string v, location_type l)
      {
        return symbol_type (token::TOK_ACTION_VER, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_ACTION_VER (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_ACTION_VER, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_ACTION_XMLNS (std::string v, location_type l)
      {
        return symbol_type (token::TOK_ACTION_XMLNS, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_ACTION_XMLNS (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_ACTION_XMLNS, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_CONFIG_COMPONENT_SIG (std::string v, location_type l)
      {
        return symbol_type (token::TOK_CONFIG_COMPONENT_SIG, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_CONFIG_COMPONENT_SIG (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_CONFIG_COMPONENT_SIG, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_CONFIG_CONN_ENGINE (std::string v, location_type l)
      {
        return symbol_type (token::TOK_CONFIG_CONN_ENGINE, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_CONFIG_CONN_ENGINE (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_CONFIG_CONN_ENGINE, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_CONFIG_SEC_ARGUMENT_SEPARATOR (std::string v, location_type l)
      {
        return symbol_type (token::TOK_CONFIG_SEC_ARGUMENT_SEPARATOR, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_CONFIG_SEC_ARGUMENT_SEPARATOR (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_CONFIG_SEC_ARGUMENT_SEPARATOR, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_CONFIG_SEC_WEB_APP_ID (std::string v, location_type l)
      {
        return symbol_type (token::TOK_CONFIG_SEC_WEB_APP_ID, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_CONFIG_SEC_WEB_APP_ID (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_CONFIG_SEC_WEB_APP_ID, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_CONFIG_SEC_SERVER_SIG (std::string v, location_type l)
      {
        return symbol_type (token::TOK_CONFIG_SEC_SERVER_SIG, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_CONFIG_SEC_SERVER_SIG (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_CONFIG_SEC_SERVER_SIG, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_CONFIG_DIR_AUDIT_DIR (std::string v, location_type l)
      {
        return symbol_type (token::TOK_CONFIG_DIR_AUDIT_DIR, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_CONFIG_DIR_AUDIT_DIR (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_CONFIG_DIR_AUDIT_DIR, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_CONFIG_DIR_AUDIT_DIR_MOD (std::string v, location_type l)
      {
        return symbol_type (token::TOK_CONFIG_DIR_AUDIT_DIR_MOD, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_CONFIG_DIR_AUDIT_DIR_MOD (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_CONFIG_DIR_AUDIT_DIR_MOD, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_CONFIG_DIR_AUDIT_ENG (std::string v, location_type l)
      {
        return symbol_type (token::TOK_CONFIG_DIR_AUDIT_ENG, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_CONFIG_DIR_AUDIT_ENG (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_CONFIG_DIR_AUDIT_ENG, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_CONFIG_DIR_AUDIT_FLE_MOD (std::string v, location_type l)
      {
        return symbol_type (token::TOK_CONFIG_DIR_AUDIT_FLE_MOD, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_CONFIG_DIR_AUDIT_FLE_MOD (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_CONFIG_DIR_AUDIT_FLE_MOD, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_CONFIG_DIR_AUDIT_LOG (std::string v, location_type l)
      {
        return symbol_type (token::TOK_CONFIG_DIR_AUDIT_LOG, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_CONFIG_DIR_AUDIT_LOG (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_CONFIG_DIR_AUDIT_LOG, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_CONFIG_DIR_AUDIT_LOG2 (std::string v, location_type l)
      {
        return symbol_type (token::TOK_CONFIG_DIR_AUDIT_LOG2, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_CONFIG_DIR_AUDIT_LOG2 (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_CONFIG_DIR_AUDIT_LOG2, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_CONFIG_DIR_AUDIT_LOG_P (std::string v, location_type l)
      {
        return symbol_type (token::TOK_CONFIG_DIR_AUDIT_LOG_P, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_CONFIG_DIR_AUDIT_LOG_P (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_CONFIG_DIR_AUDIT_LOG_P, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_CONFIG_DIR_AUDIT_STS (std::string v, location_type l)
      {
        return symbol_type (token::TOK_CONFIG_DIR_AUDIT_STS, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_CONFIG_DIR_AUDIT_STS (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_CONFIG_DIR_AUDIT_STS, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_CONFIG_DIR_AUDIT_TPE (std::string v, location_type l)
      {
        return symbol_type (token::TOK_CONFIG_DIR_AUDIT_TPE, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_CONFIG_DIR_AUDIT_TPE (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_CONFIG_DIR_AUDIT_TPE, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_CONFIG_DIR_DEBUG_LOG (std::string v, location_type l)
      {
        return symbol_type (token::TOK_CONFIG_DIR_DEBUG_LOG, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_CONFIG_DIR_DEBUG_LOG (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_CONFIG_DIR_DEBUG_LOG, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_CONFIG_DIR_DEBUG_LVL (std::string v, location_type l)
      {
        return symbol_type (token::TOK_CONFIG_DIR_DEBUG_LVL, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_CONFIG_DIR_DEBUG_LVL (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_CONFIG_DIR_DEBUG_LVL, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_CONFIG_SEC_CACHE_TRANSFORMATIONS (std::string v, location_type l)
      {
        return symbol_type (token::TOK_CONFIG_SEC_CACHE_TRANSFORMATIONS, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_CONFIG_SEC_CACHE_TRANSFORMATIONS (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_CONFIG_SEC_CACHE_TRANSFORMATIONS, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_CONFIG_SEC_DISABLE_BACKEND_COMPRESS (std::string v, location_type l)
      {
        return symbol_type (token::TOK_CONFIG_SEC_DISABLE_BACKEND_COMPRESS, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_CONFIG_SEC_DISABLE_BACKEND_COMPRESS (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_CONFIG_SEC_DISABLE_BACKEND_COMPRESS, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_CONFIG_SEC_HASH_ENGINE (std::string v, location_type l)
      {
        return symbol_type (token::TOK_CONFIG_SEC_HASH_ENGINE, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_CONFIG_SEC_HASH_ENGINE (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_CONFIG_SEC_HASH_ENGINE, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_CONFIG_SEC_HASH_KEY (std::string v, location_type l)
      {
        return symbol_type (token::TOK_CONFIG_SEC_HASH_KEY, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_CONFIG_SEC_HASH_KEY (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_CONFIG_SEC_HASH_KEY, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_CONFIG_SEC_HASH_PARAM (std::string v, location_type l)
      {
        return symbol_type (token::TOK_CONFIG_SEC_HASH_PARAM, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_CONFIG_SEC_HASH_PARAM (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_CONFIG_SEC_HASH_PARAM, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_CONFIG_SEC_HASH_METHOD_RX (std::string v, location_type l)
      {
        return symbol_type (token::TOK_CONFIG_SEC_HASH_METHOD_RX, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_CONFIG_SEC_HASH_METHOD_RX (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_CONFIG_SEC_HASH_METHOD_RX, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_CONFIG_SEC_HASH_METHOD_PM (std::string v, location_type l)
      {
        return symbol_type (token::TOK_CONFIG_SEC_HASH_METHOD_PM, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_CONFIG_SEC_HASH_METHOD_PM (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_CONFIG_SEC_HASH_METHOD_PM, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_CONFIG_SEC_CHROOT_DIR (std::string v, location_type l)
      {
        return symbol_type (token::TOK_CONFIG_SEC_CHROOT_DIR, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_CONFIG_SEC_CHROOT_DIR (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_CONFIG_SEC_CHROOT_DIR, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_CONFIG_DIR_GEO_DB (std::string v, location_type l)
      {
        return symbol_type (token::TOK_CONFIG_DIR_GEO_DB, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_CONFIG_DIR_GEO_DB (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_CONFIG_DIR_GEO_DB, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_CONFIG_DIR_GSB_DB (std::string v, location_type l)
      {
        return symbol_type (token::TOK_CONFIG_DIR_GSB_DB, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_CONFIG_DIR_GSB_DB (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_CONFIG_DIR_GSB_DB, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_CONFIG_SEC_GUARDIAN_LOG (std::string v, location_type l)
      {
        return symbol_type (token::TOK_CONFIG_SEC_GUARDIAN_LOG, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_CONFIG_SEC_GUARDIAN_LOG (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_CONFIG_SEC_GUARDIAN_LOG, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_CONFIG_DIR_PCRE_MATCH_LIMIT (std::string v, location_type l)
      {
        return symbol_type (token::TOK_CONFIG_DIR_PCRE_MATCH_LIMIT, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_CONFIG_DIR_PCRE_MATCH_LIMIT (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_CONFIG_DIR_PCRE_MATCH_LIMIT, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_CONFIG_DIR_PCRE_MATCH_LIMIT_RECURSION (std::string v, location_type l)
      {
        return symbol_type (token::TOK_CONFIG_DIR_PCRE_MATCH_LIMIT_RECURSION, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_CONFIG_DIR_PCRE_MATCH_LIMIT_RECURSION (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_CONFIG_DIR_PCRE_MATCH_LIMIT_RECURSION, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_CONFIG_SEC_CONN_R_STATE_LIMIT (std::string v, location_type l)
      {
        return symbol_type (token::TOK_CONFIG_SEC_CONN_R_STATE_LIMIT, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_CONFIG_SEC_CONN_R_STATE_LIMIT (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_CONFIG_SEC_CONN_R_STATE_LIMIT, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_CONFIG_SEC_CONN_W_STATE_LIMIT (std::string v, location_type l)
      {
        return symbol_type (token::TOK_CONFIG_SEC_CONN_W_STATE_LIMIT, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_CONFIG_SEC_CONN_W_STATE_LIMIT (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_CONFIG_SEC_CONN_W_STATE_LIMIT, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_CONFIG_SEC_SENSOR_ID (std::string v, location_type l)
      {
        return symbol_type (token::TOK_CONFIG_SEC_SENSOR_ID, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_CONFIG_SEC_SENSOR_ID (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_CONFIG_SEC_SENSOR_ID, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_CONFIG_DIR_REQ_BODY (std::string v, location_type l)
      {
        return symbol_type (token::TOK_CONFIG_DIR_REQ_BODY, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_CONFIG_DIR_REQ_BODY (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_CONFIG_DIR_REQ_BODY, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_CONFIG_DIR_REQ_BODY_IN_MEMORY_LIMIT (std::string v, location_type l)
      {
        return symbol_type (token::TOK_CONFIG_DIR_REQ_BODY_IN_MEMORY_LIMIT, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_CONFIG_DIR_REQ_BODY_IN_MEMORY_LIMIT (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_CONFIG_DIR_REQ_BODY_IN_MEMORY_LIMIT, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_CONFIG_DIR_REQ_BODY_LIMIT (std::string v, location_type l)
      {
        return symbol_type (token::TOK_CONFIG_DIR_REQ_BODY_LIMIT, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_CONFIG_DIR_REQ_BODY_LIMIT (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_CONFIG_DIR_REQ_BODY_LIMIT, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_CONFIG_DIR_REQ_BODY_LIMIT_ACTION (std::string v, location_type l)
      {
        return symbol_type (token::TOK_CONFIG_DIR_REQ_BODY_LIMIT_ACTION, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_CONFIG_DIR_REQ_BODY_LIMIT_ACTION (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_CONFIG_DIR_REQ_BODY_LIMIT_ACTION, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_CONFIG_DIR_REQ_BODY_NO_FILES_LIMIT (std::string v, location_type l)
      {
        return symbol_type (token::TOK_CONFIG_DIR_REQ_BODY_NO_FILES_LIMIT, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_CONFIG_DIR_REQ_BODY_NO_FILES_LIMIT (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_CONFIG_DIR_REQ_BODY_NO_FILES_LIMIT, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_CONFIG_DIR_RES_BODY (std::string v, location_type l)
      {
        return symbol_type (token::TOK_CONFIG_DIR_RES_BODY, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_CONFIG_DIR_RES_BODY (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_CONFIG_DIR_RES_BODY, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_CONFIG_DIR_RES_BODY_LIMIT (std::string v, location_type l)
      {
        return symbol_type (token::TOK_CONFIG_DIR_RES_BODY_LIMIT, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_CONFIG_DIR_RES_BODY_LIMIT (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_CONFIG_DIR_RES_BODY_LIMIT, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_CONFIG_DIR_RES_BODY_LIMIT_ACTION (std::string v, location_type l)
      {
        return symbol_type (token::TOK_CONFIG_DIR_RES_BODY_LIMIT_ACTION, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_CONFIG_DIR_RES_BODY_LIMIT_ACTION (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_CONFIG_DIR_RES_BODY_LIMIT_ACTION, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_CONFIG_SEC_RULE_INHERITANCE (std::string v, location_type l)
      {
        return symbol_type (token::TOK_CONFIG_SEC_RULE_INHERITANCE, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_CONFIG_SEC_RULE_INHERITANCE (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_CONFIG_SEC_RULE_INHERITANCE, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_CONFIG_SEC_RULE_PERF_TIME (std::string v, location_type l)
      {
        return symbol_type (token::TOK_CONFIG_SEC_RULE_PERF_TIME, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_CONFIG_SEC_RULE_PERF_TIME (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_CONFIG_SEC_RULE_PERF_TIME, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_CONFIG_DIR_RULE_ENG (std::string v, location_type l)
      {
        return symbol_type (token::TOK_CONFIG_DIR_RULE_ENG, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_CONFIG_DIR_RULE_ENG (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_CONFIG_DIR_RULE_ENG, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_CONFIG_DIR_SEC_ACTION (std::string v, location_type l)
      {
        return symbol_type (token::TOK_CONFIG_DIR_SEC_ACTION, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_CONFIG_DIR_SEC_ACTION (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_CONFIG_DIR_SEC_ACTION, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_CONFIG_DIR_SEC_DEFAULT_ACTION (std::string v, location_type l)
      {
        return symbol_type (token::TOK_CONFIG_DIR_SEC_DEFAULT_ACTION, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_CONFIG_DIR_SEC_DEFAULT_ACTION (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_CONFIG_DIR_SEC_DEFAULT_ACTION, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_CONFIG_DIR_SEC_MARKER (std::string v, location_type l)
      {
        return symbol_type (token::TOK_CONFIG_DIR_SEC_MARKER, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_CONFIG_DIR_SEC_MARKER (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_CONFIG_DIR_SEC_MARKER, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_CONFIG_DIR_UNICODE_MAP_FILE (std::string v, location_type l)
      {
        return symbol_type (token::TOK_CONFIG_DIR_UNICODE_MAP_FILE, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_CONFIG_DIR_UNICODE_MAP_FILE (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_CONFIG_DIR_UNICODE_MAP_FILE, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_CONFIG_DIR_UNICODE_CODE_PAGE (std::string v, location_type l)
      {
        return symbol_type (token::TOK_CONFIG_DIR_UNICODE_CODE_PAGE, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_CONFIG_DIR_UNICODE_CODE_PAGE (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_CONFIG_DIR_UNICODE_CODE_PAGE, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_CONFIG_SEC_COLLECTION_TIMEOUT (std::string v, location_type l)
      {
        return symbol_type (token::TOK_CONFIG_SEC_COLLECTION_TIMEOUT, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_CONFIG_SEC_COLLECTION_TIMEOUT (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_CONFIG_SEC_COLLECTION_TIMEOUT, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_CONFIG_SEC_HTTP_BLKEY (std::string v, location_type l)
      {
        return symbol_type (token::TOK_CONFIG_SEC_HTTP_BLKEY, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_CONFIG_SEC_HTTP_BLKEY (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_CONFIG_SEC_HTTP_BLKEY, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_CONFIG_SEC_INTERCEPT_ON_ERROR (std::string v, location_type l)
      {
        return symbol_type (token::TOK_CONFIG_SEC_INTERCEPT_ON_ERROR, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_CONFIG_SEC_INTERCEPT_ON_ERROR (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_CONFIG_SEC_INTERCEPT_ON_ERROR, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_CONFIG_SEC_REMOTE_RULES_FAIL_ACTION (std::string v, location_type l)
      {
        return symbol_type (token::TOK_CONFIG_SEC_REMOTE_RULES_FAIL_ACTION, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_CONFIG_SEC_REMOTE_RULES_FAIL_ACTION (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_CONFIG_SEC_REMOTE_RULES_FAIL_ACTION, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_CONFIG_SEC_RULE_REMOVE_BY_ID (std::string v, location_type l)
      {
        return symbol_type (token::TOK_CONFIG_SEC_RULE_REMOVE_BY_ID, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_CONFIG_SEC_RULE_REMOVE_BY_ID (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_CONFIG_SEC_RULE_REMOVE_BY_ID, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_CONFIG_SEC_RULE_REMOVE_BY_MSG (std::string v, location_type l)
      {
        return symbol_type (token::TOK_CONFIG_SEC_RULE_REMOVE_BY_MSG, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_CONFIG_SEC_RULE_REMOVE_BY_MSG (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_CONFIG_SEC_RULE_REMOVE_BY_MSG, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_CONFIG_SEC_RULE_REMOVE_BY_TAG (std::string v, location_type l)
      {
        return symbol_type (token::TOK_CONFIG_SEC_RULE_REMOVE_BY_TAG, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_CONFIG_SEC_RULE_REMOVE_BY_TAG (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_CONFIG_SEC_RULE_REMOVE_BY_TAG, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_CONFIG_SEC_RULE_UPDATE_TARGET_BY_TAG (std::string v, location_type l)
      {
        return symbol_type (token::TOK_CONFIG_SEC_RULE_UPDATE_TARGET_BY_TAG, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_CONFIG_SEC_RULE_UPDATE_TARGET_BY_TAG (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_CONFIG_SEC_RULE_UPDATE_TARGET_BY_TAG, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_CONFIG_SEC_RULE_UPDATE_TARGET_BY_MSG (std::string v, location_type l)
      {
        return symbol_type (token::TOK_CONFIG_SEC_RULE_UPDATE_TARGET_BY_MSG, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_CONFIG_SEC_RULE_UPDATE_TARGET_BY_MSG (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_CONFIG_SEC_RULE_UPDATE_TARGET_BY_MSG, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_CONFIG_SEC_RULE_UPDATE_TARGET_BY_ID (std::string v, location_type l)
      {
        return symbol_type (token::TOK_CONFIG_SEC_RULE_UPDATE_TARGET_BY_ID, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_CONFIG_SEC_RULE_UPDATE_TARGET_BY_ID (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_CONFIG_SEC_RULE_UPDATE_TARGET_BY_ID, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_CONFIG_SEC_RULE_UPDATE_ACTION_BY_ID (std::string v, location_type l)
      {
        return symbol_type (token::TOK_CONFIG_SEC_RULE_UPDATE_ACTION_BY_ID, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_CONFIG_SEC_RULE_UPDATE_ACTION_BY_ID (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_CONFIG_SEC_RULE_UPDATE_ACTION_BY_ID, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_CONFIG_UPDLOAD_KEEP_FILES (std::string v, location_type l)
      {
        return symbol_type (token::TOK_CONFIG_UPDLOAD_KEEP_FILES, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_CONFIG_UPDLOAD_KEEP_FILES (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_CONFIG_UPDLOAD_KEEP_FILES, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_CONFIG_UPDLOAD_SAVE_TMP_FILES (std::string v, location_type l)
      {
        return symbol_type (token::TOK_CONFIG_UPDLOAD_SAVE_TMP_FILES, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_CONFIG_UPDLOAD_SAVE_TMP_FILES (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_CONFIG_UPDLOAD_SAVE_TMP_FILES, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_CONFIG_UPLOAD_DIR (std::string v, location_type l)
      {
        return symbol_type (token::TOK_CONFIG_UPLOAD_DIR, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_CONFIG_UPLOAD_DIR (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_CONFIG_UPLOAD_DIR, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_CONFIG_UPLOAD_FILE_LIMIT (std::string v, location_type l)
      {
        return symbol_type (token::TOK_CONFIG_UPLOAD_FILE_LIMIT, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_CONFIG_UPLOAD_FILE_LIMIT (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_CONFIG_UPLOAD_FILE_LIMIT, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_CONFIG_UPLOAD_FILE_MODE (std::string v, location_type l)
      {
        return symbol_type (token::TOK_CONFIG_UPLOAD_FILE_MODE, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_CONFIG_UPLOAD_FILE_MODE (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_CONFIG_UPLOAD_FILE_MODE, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_CONFIG_VALUE_ABORT (std::string v, location_type l)
      {
        return symbol_type (token::TOK_CONFIG_VALUE_ABORT, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_CONFIG_VALUE_ABORT (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_CONFIG_VALUE_ABORT, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_CONFIG_VALUE_DETC (std::string v, location_type l)
      {
        return symbol_type (token::TOK_CONFIG_VALUE_DETC, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_CONFIG_VALUE_DETC (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_CONFIG_VALUE_DETC, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_CONFIG_VALUE_HTTPS (std::string v, location_type l)
      {
        return symbol_type (token::TOK_CONFIG_VALUE_HTTPS, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_CONFIG_VALUE_HTTPS (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_CONFIG_VALUE_HTTPS, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_CONFIG_VALUE_OFF (std::string v, location_type l)
      {
        return symbol_type (token::TOK_CONFIG_VALUE_OFF, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_CONFIG_VALUE_OFF (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_CONFIG_VALUE_OFF, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_CONFIG_VALUE_ON (std::string v, location_type l)
      {
        return symbol_type (token::TOK_CONFIG_VALUE_ON, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_CONFIG_VALUE_ON (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_CONFIG_VALUE_ON, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_CONFIG_VALUE_PARALLEL (std::string v, location_type l)
      {
        return symbol_type (token::TOK_CONFIG_VALUE_PARALLEL, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_CONFIG_VALUE_PARALLEL (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_CONFIG_VALUE_PARALLEL, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_CONFIG_VALUE_PROCESS_PARTIAL (std::string v, location_type l)
      {
        return symbol_type (token::TOK_CONFIG_VALUE_PROCESS_PARTIAL, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_CONFIG_VALUE_PROCESS_PARTIAL (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_CONFIG_VALUE_PROCESS_PARTIAL, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_CONFIG_VALUE_REJECT (std::string v, location_type l)
      {
        return symbol_type (token::TOK_CONFIG_VALUE_REJECT, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_CONFIG_VALUE_REJECT (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_CONFIG_VALUE_REJECT, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_CONFIG_VALUE_RELEVANT_ONLY (std::string v, location_type l)
      {
        return symbol_type (token::TOK_CONFIG_VALUE_RELEVANT_ONLY, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_CONFIG_VALUE_RELEVANT_ONLY (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_CONFIG_VALUE_RELEVANT_ONLY, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_CONFIG_VALUE_SERIAL (std::string v, location_type l)
      {
        return symbol_type (token::TOK_CONFIG_VALUE_SERIAL, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_CONFIG_VALUE_SERIAL (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_CONFIG_VALUE_SERIAL, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_CONFIG_VALUE_WARN (std::string v, location_type l)
      {
        return symbol_type (token::TOK_CONFIG_VALUE_WARN, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_CONFIG_VALUE_WARN (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_CONFIG_VALUE_WARN, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_CONFIG_XML_EXTERNAL_ENTITY (std::string v, location_type l)
      {
        return symbol_type (token::TOK_CONFIG_XML_EXTERNAL_ENTITY, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_CONFIG_XML_EXTERNAL_ENTITY (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_CONFIG_XML_EXTERNAL_ENTITY, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_CONGIG_DIR_RESPONSE_BODY_MP (std::string v, location_type l)
      {
        return symbol_type (token::TOK_CONGIG_DIR_RESPONSE_BODY_MP, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_CONGIG_DIR_RESPONSE_BODY_MP (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_CONGIG_DIR_RESPONSE_BODY_MP, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_CONGIG_DIR_SEC_ARG_SEP (std::string v, location_type l)
      {
        return symbol_type (token::TOK_CONGIG_DIR_SEC_ARG_SEP, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_CONGIG_DIR_SEC_ARG_SEP (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_CONGIG_DIR_SEC_ARG_SEP, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_CONGIG_DIR_SEC_COOKIE_FORMAT (std::string v, location_type l)
      {
        return symbol_type (token::TOK_CONGIG_DIR_SEC_COOKIE_FORMAT, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_CONGIG_DIR_SEC_COOKIE_FORMAT (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_CONGIG_DIR_SEC_COOKIE_FORMAT, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_CONFIG_SEC_COOKIEV0_SEPARATOR (std::string v, location_type l)
      {
        return symbol_type (token::TOK_CONFIG_SEC_COOKIEV0_SEPARATOR, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_CONFIG_SEC_COOKIEV0_SEPARATOR (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_CONFIG_SEC_COOKIEV0_SEPARATOR, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_CONGIG_DIR_SEC_DATA_DIR (std::string v, location_type l)
      {
        return symbol_type (token::TOK_CONGIG_DIR_SEC_DATA_DIR, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_CONGIG_DIR_SEC_DATA_DIR (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_CONGIG_DIR_SEC_DATA_DIR, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_CONGIG_DIR_SEC_STATUS_ENGINE (std::string v, location_type l)
      {
        return symbol_type (token::TOK_CONGIG_DIR_SEC_STATUS_ENGINE, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_CONGIG_DIR_SEC_STATUS_ENGINE (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_CONGIG_DIR_SEC_STATUS_ENGINE, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_CONFIG_SEC_STREAM_IN_BODY_INSPECTION (std::string v, location_type l)
      {
        return symbol_type (token::TOK_CONFIG_SEC_STREAM_IN_BODY_INSPECTION, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_CONFIG_SEC_STREAM_IN_BODY_INSPECTION (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_CONFIG_SEC_STREAM_IN_BODY_INSPECTION, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_CONFIG_SEC_STREAM_OUT_BODY_INSPECTION (std::string v, location_type l)
      {
        return symbol_type (token::TOK_CONFIG_SEC_STREAM_OUT_BODY_INSPECTION, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_CONFIG_SEC_STREAM_OUT_BODY_INSPECTION (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_CONFIG_SEC_STREAM_OUT_BODY_INSPECTION, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_CONGIG_DIR_SEC_TMP_DIR (std::string v, location_type l)
      {
        return symbol_type (token::TOK_CONGIG_DIR_SEC_TMP_DIR, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_CONGIG_DIR_SEC_TMP_DIR (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_CONGIG_DIR_SEC_TMP_DIR, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_DIRECTIVE (std::string v, location_type l)
      {
        return symbol_type (token::TOK_DIRECTIVE, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_DIRECTIVE (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_DIRECTIVE, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_DIRECTIVE_SECRULESCRIPT (std::string v, location_type l)
      {
        return symbol_type (token::TOK_DIRECTIVE_SECRULESCRIPT, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_DIRECTIVE_SECRULESCRIPT (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_DIRECTIVE_SECRULESCRIPT, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_FREE_TEXT_QUOTE_MACRO_EXPANSION (std::string v, location_type l)
      {
        return symbol_type (token::TOK_FREE_TEXT_QUOTE_MACRO_EXPANSION, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_FREE_TEXT_QUOTE_MACRO_EXPANSION (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_FREE_TEXT_QUOTE_MACRO_EXPANSION, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_QUOTATION_MARK (std::string v, location_type l)
      {
        return symbol_type (token::TOK_QUOTATION_MARK, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_QUOTATION_MARK (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_QUOTATION_MARK, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_RUN_TIME_VAR_BLD (std::string v, location_type l)
      {
        return symbol_type (token::TOK_RUN_TIME_VAR_BLD, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_RUN_TIME_VAR_BLD (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_RUN_TIME_VAR_BLD, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_RUN_TIME_VAR_DUR (std::string v, location_type l)
      {
        return symbol_type (token::TOK_RUN_TIME_VAR_DUR, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_RUN_TIME_VAR_DUR (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_RUN_TIME_VAR_DUR, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_RUN_TIME_VAR_HSV (std::string v, location_type l)
      {
        return symbol_type (token::TOK_RUN_TIME_VAR_HSV, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_RUN_TIME_VAR_HSV (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_RUN_TIME_VAR_HSV, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_RUN_TIME_VAR_REMOTE_USER (std::string v, location_type l)
      {
        return symbol_type (token::TOK_RUN_TIME_VAR_REMOTE_USER, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_RUN_TIME_VAR_REMOTE_USER (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_RUN_TIME_VAR_REMOTE_USER, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_RUN_TIME_VAR_TIME (std::string v, location_type l)
      {
        return symbol_type (token::TOK_RUN_TIME_VAR_TIME, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_RUN_TIME_VAR_TIME (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_RUN_TIME_VAR_TIME, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_RUN_TIME_VAR_TIME_DAY (std::string v, location_type l)
      {
        return symbol_type (token::TOK_RUN_TIME_VAR_TIME_DAY, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_RUN_TIME_VAR_TIME_DAY (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_RUN_TIME_VAR_TIME_DAY, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_RUN_TIME_VAR_TIME_EPOCH (std::string v, location_type l)
      {
        return symbol_type (token::TOK_RUN_TIME_VAR_TIME_EPOCH, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_RUN_TIME_VAR_TIME_EPOCH (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_RUN_TIME_VAR_TIME_EPOCH, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_RUN_TIME_VAR_TIME_HOUR (std::string v, location_type l)
      {
        return symbol_type (token::TOK_RUN_TIME_VAR_TIME_HOUR, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_RUN_TIME_VAR_TIME_HOUR (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_RUN_TIME_VAR_TIME_HOUR, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_RUN_TIME_VAR_TIME_MIN (std::string v, location_type l)
      {
        return symbol_type (token::TOK_RUN_TIME_VAR_TIME_MIN, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_RUN_TIME_VAR_TIME_MIN (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_RUN_TIME_VAR_TIME_MIN, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_RUN_TIME_VAR_TIME_MON (std::string v, location_type l)
      {
        return symbol_type (token::TOK_RUN_TIME_VAR_TIME_MON, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_RUN_TIME_VAR_TIME_MON (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_RUN_TIME_VAR_TIME_MON, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_RUN_TIME_VAR_TIME_SEC (std::string v, location_type l)
      {
        return symbol_type (token::TOK_RUN_TIME_VAR_TIME_SEC, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_RUN_TIME_VAR_TIME_SEC (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_RUN_TIME_VAR_TIME_SEC, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_RUN_TIME_VAR_TIME_WDAY (std::string v, location_type l)
      {
        return symbol_type (token::TOK_RUN_TIME_VAR_TIME_WDAY, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_RUN_TIME_VAR_TIME_WDAY (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_RUN_TIME_VAR_TIME_WDAY, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_RUN_TIME_VAR_TIME_YEAR (std::string v, location_type l)
      {
        return symbol_type (token::TOK_RUN_TIME_VAR_TIME_YEAR, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_RUN_TIME_VAR_TIME_YEAR (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_RUN_TIME_VAR_TIME_YEAR, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_VARIABLE (std::string v, location_type l)
      {
        return symbol_type (token::TOK_VARIABLE, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_VARIABLE (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_VARIABLE, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_DICT_ELEMENT (std::string v, location_type l)
      {
        return symbol_type (token::TOK_DICT_ELEMENT, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_DICT_ELEMENT (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_DICT_ELEMENT, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_DICT_ELEMENT_REGEXP (std::string v, location_type l)
      {
        return symbol_type (token::TOK_DICT_ELEMENT_REGEXP, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_DICT_ELEMENT_REGEXP (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_DICT_ELEMENT_REGEXP, v, l);
      }
#endif


  private:
    /// This class is not copyable.
    seclang_parser (const seclang_parser&);
    seclang_parser& operator= (const seclang_parser&);

    /// State numbers.
    typedef int state_type;

    /// Generate an error message.
    /// \param yystate   the state where the error occurred.
    /// \param yyla      the lookahead token.
    virtual std::string yysyntax_error_ (state_type yystate,
                                         const symbol_type& yyla) const;

    /// Compute post-reduction state.
    /// \param yystate   the current state
    /// \param yysym     the nonterminal to push on the stack
    state_type yy_lr_goto_state_ (state_type yystate, int yysym);

    /// Whether the given \c yypact_ value indicates a defaulted state.
    /// \param yyvalue   the value to check
    static bool yy_pact_value_is_default_ (int yyvalue);

    /// Whether the given \c yytable_ value indicates a syntax error.
    /// \param yyvalue   the value to check
    static bool yy_table_value_is_error_ (int yyvalue);

    static const short yypact_ninf_;
    static const signed char yytable_ninf_;

    /// Convert a scanner token number \a t to a symbol number.
    static token_number_type yytranslate_ (token_type t);

    // Tables.
  // YYPACT[STATE-NUM] -- Index in YYTABLE of the portion describing
  // STATE-NUM.
  static const short yypact_[];

  // YYDEFACT[STATE-NUM] -- Default reduction number in state STATE-NUM.
  // Performed when YYTABLE does not specify something else to do.  Zero
  // means the default is an error.
  static const unsigned short yydefact_[];

  // YYPGOTO[NTERM-NUM].
  static const short yypgoto_[];

  // YYDEFGOTO[NTERM-NUM].
  static const short yydefgoto_[];

  // YYTABLE[YYPACT[STATE-NUM]] -- What to do in state STATE-NUM.  If
  // positive, shift that token.  If negative, reduce the rule whose
  // number is the opposite.  If YYTABLE_NINF, syntax error.
  static const unsigned short yytable_[];

  static const short yycheck_[];

  // YYSTOS[STATE-NUM] -- The (internal number of the) accessing
  // symbol of state STATE-NUM.
  static const unsigned short yystos_[];

  // YYR1[YYN] -- Symbol number of symbol that rule YYN derives.
  static const unsigned short yyr1_[];

  // YYR2[YYN] -- Number of symbols on the right hand side of rule YYN.
  static const unsigned char yyr2_[];


    /// Convert the symbol name \a n to a form suitable for a diagnostic.
    static std::string yytnamerr_ (const char *n);


    /// For a symbol, its name in clear.
    static const char* const yytname_[];
#if YYDEBUG
  // YYRLINE[YYN] -- Source line where rule number YYN was defined.
  static const unsigned short yyrline_[];
    /// Report on the debug stream that the rule \a r is going to be reduced.
    virtual void yy_reduce_print_ (int r);
    /// Print the state stack on the debug stream.
    virtual void yystack_print_ ();

    /// Debugging level.
    int yydebug_;
    /// Debug stream.
    std::ostream* yycdebug_;

    /// \brief Display a symbol type, value and location.
    /// \param yyo    The output stream.
    /// \param yysym  The symbol.
    template <typename Base>
    void yy_print_ (std::ostream& yyo, const basic_symbol<Base>& yysym) const;
#endif

    /// \brief Reclaim the memory associated to a symbol.
    /// \param yymsg     Why this token is reclaimed.
    ///                  If null, print nothing.
    /// \param yysym     The symbol.
    template <typename Base>
    void yy_destroy_ (const char* yymsg, basic_symbol<Base>& yysym) const;

  private:
    /// Type access provider for state based symbols.
    struct by_state
    {
      /// Default constructor.
      by_state () YY_NOEXCEPT;

      /// The symbol type as needed by the constructor.
      typedef state_type kind_type;

      /// Constructor.
      by_state (kind_type s) YY_NOEXCEPT;

      /// Copy constructor.
      by_state (const by_state& that) YY_NOEXCEPT;

      /// Record that this symbol is empty.
      void clear () YY_NOEXCEPT;

      /// Steal the symbol type from \a that.
      void move (by_state& that);

      /// The (internal) type number (corresponding to \a state).
      /// \a empty_symbol when empty.
      symbol_number_type type_get () const YY_NOEXCEPT;

      /// The state number used to denote an empty symbol.
      enum { empty_state = -1 };

      /// The state.
      /// \a empty when empty.
      state_type state;
    };

    /// "Internal" symbol: element of the stack.
    struct stack_symbol_type : basic_symbol<by_state>
    {
      /// Superclass.
      typedef basic_symbol<by_state> super_type;
      /// Construct an empty symbol.
      stack_symbol_type ();
      /// Move or copy construction.
      stack_symbol_type (YY_RVREF (stack_symbol_type) that);
      /// Steal the contents from \a sym to build this.
      stack_symbol_type (state_type s, YY_MOVE_REF (symbol_type) sym);
#if YY_CPLUSPLUS < 201103L
      /// Assignment, needed by push_back by some old implementations.
      /// Moves the contents of that.
      stack_symbol_type& operator= (stack_symbol_type& that);
#endif
    };

    /// A stack with random access from its top.
    template <typename T, typename S = std::vector<T> >
    class stack
    {
    public:
      // Hide our reversed order.
      typedef typename S::reverse_iterator iterator;
      typedef typename S::const_reverse_iterator const_iterator;
      typedef typename S::size_type size_type;

      stack (size_type n = 200)
        : seq_ (n)
      {}

      /// Random access.
      ///
      /// Index 0 returns the topmost element.
      T&
      operator[] (size_type i)
      {
        return seq_[size () - 1 - i];
      }

      /// Random access.
      ///
      /// Index 0 returns the topmost element.
      T&
      operator[] (int i)
      {
        return operator[] (size_type (i));
      }

      /// Random access.
      ///
      /// Index 0 returns the topmost element.
      const T&
      operator[] (size_type i) const
      {
        return seq_[size () - 1 - i];
      }

      /// Random access.
      ///
      /// Index 0 returns the topmost element.
      const T&
      operator[] (int i) const
      {
        return operator[] (size_type (i));
      }

      /// Steal the contents of \a t.
      ///
      /// Close to move-semantics.
      void
      push (YY_MOVE_REF (T) t)
      {
        seq_.push_back (T ());
        operator[] (0).move (t);
      }

      /// Pop elements from the stack.
      void
      pop (int n = 1) YY_NOEXCEPT
      {
        for (; 0 < n; --n)
          seq_.pop_back ();
      }

      /// Pop all elements from the stack.
      void
      clear () YY_NOEXCEPT
      {
        seq_.clear ();
      }

      /// Number of elements on the stack.
      size_type
      size () const YY_NOEXCEPT
      {
        return seq_.size ();
      }

      /// Iterator on top of the stack (going downwards).
      const_iterator
      begin () const YY_NOEXCEPT
      {
        return seq_.rbegin ();
      }

      /// Bottom of the stack.
      const_iterator
      end () const YY_NOEXCEPT
      {
        return seq_.rend ();
      }

      /// Present a slice of the top of a stack.
      class slice
      {
      public:
        slice (const stack& stack, int range)
          : stack_ (stack)
          , range_ (range)
        {}

        const T&
        operator[] (int i) const
        {
          return stack_[range_ - i];
        }

      private:
        const stack& stack_;
        int range_;
      };

    private:
      stack (const stack&);
      stack& operator= (const stack&);
      /// The wrapped container.
      S seq_;
    };


    /// Stack type.
    typedef stack<stack_symbol_type> stack_type;

    /// The stack.
    stack_type yystack_;

    /// Push a new state on the stack.
    /// \param m    a debug message to display
    ///             if null, no trace is output.
    /// \param sym  the symbol
    /// \warning the contents of \a s.value is stolen.
    void yypush_ (const char* m, YY_MOVE_REF (stack_symbol_type) sym);

    /// Push a new look ahead token on the state on the stack.
    /// \param m    a debug message to display
    ///             if null, no trace is output.
    /// \param s    the state
    /// \param sym  the symbol (for its value and location).
    /// \warning the contents of \a sym.value is stolen.
    void yypush_ (const char* m, state_type s, YY_MOVE_REF (symbol_type) sym);

    /// Pop \a n symbols from the stack.
    void yypop_ (int n = 1);

    /// Constants.
    enum
    {
      yyeof_ = 0,
      yylast_ = 3304,     ///< Last index in yytable_.
      yynnts_ = 16,  ///< Number of nonterminal symbols.
      yyfinal_ = 336, ///< Termination state number.
      yyterror_ = 1,
      yyerrcode_ = 256,
      yyntokens_ = 341  ///< Number of tokens.
    };


    // User arguments.
    modsecurity::Parser::Driver& driver;
  };

  inline
  seclang_parser::token_number_type
  seclang_parser::yytranslate_ (token_type t)
  {
    // YYTRANSLATE[TOKEN-NUM] -- Symbol number corresponding to
    // TOKEN-NUM as returned by yylex.
    static
    const token_number_type
    translate_table[] =
    {
       0,     2,     2,     2,     2,     2,     2,     2,     2,     2,
       2,     2,     2,     2,     2,     2,     2,     2,     2,     2,
       2,     2,     2,     2,     2,     2,     2,     2,     2,     2,
       2,     2,     2,     2,     2,     2,     2,     2,     2,     2,
       2,     2,     2,     2,     2,     2,     2,     2,     2,     2,
       2,     2,     2,     2,     2,     2,     2,     2,     2,     2,
       2,     2,     2,     2,     2,     2,     2,     2,     2,     2,
       2,     2,     2,     2,     2,     2,     2,     2,     2,     2,
       2,     2,     2,     2,     2,     2,     2,     2,     2,     2,
       2,     2,     2,     2,     2,     2,     2,     2,     2,     2,
       2,     2,     2,     2,     2,     2,     2,     2,     2,     2,
       2,     2,     2,     2,     2,     2,     2,     2,     2,     2,
       2,     2,     2,     2,     2,     2,     2,     2,     2,     2,
       2,     2,     2,     2,     2,     2,     2,     2,     2,     2,
       2,     2,     2,     2,     2,     2,     2,     2,     2,     2,
       2,     2,     2,     2,     2,     2,     2,     2,     2,     2,
       2,     2,     2,     2,     2,     2,     2,     2,     2,     2,
       2,     2,     2,     2,     2,     2,     2,     2,     2,     2,
       2,     2,     2,     2,     2,     2,     2,     2,     2,     2,
       2,     2,     2,     2,     2,     2,     2,     2,     2,     2,
       2,     2,     2,     2,     2,     2,     2,     2,     2,     2,
       2,     2,     2,     2,     2,     2,     2,     2,     2,     2,
       2,     2,     2,     2,     2,     2,     2,     2,     2,     2,
       2,     2,     2,     2,     2,     2,     2,     2,     2,     2,
       2,     2,     2,     2,     2,     2,     2,     2,     2,     2,
       2,     2,     2,     2,     2,     2,     1,     2,     3,     4,
       5,     6,     7,     8,     9,    10,    11,    12,    13,    14,
      15,    16,    17,    18,    19,    20,    21,    22,    23,    24,
      25,    26,    27,    28,    29,    30,    31,    32,    33,    34,
      35,    36,    37,    38,    39,    40,    41,    42,    43,    44,
      45,    46,    47,    48,    49,    50,    51,    52,    53,    54,
      55,    56,    57,    58,    59,    60,    61,    62,    63,    64,
      65,    66,    67,    68,    69,    70,    71,    72,    73,    74,
      75,    76,    77,    78,    79,    80,    81,    82,    83,    84,
      85,    86,    87,    88,    89,    90,    91,    92,    93,    94,
      95,    96,    97,    98,    99,   100,   101,   102,   103,   104,
     105,   106,   107,   108,   109,   110,   111,   112,   113,   114,
     115,   116,   117,   118,   119,   120,   121,   122,   123,   124,
     125,   126,   127,   128,   129,   130,   131,   132,   133,   134,
     135,   136,   137,   138,   139,   140,   141,   142,   143,   144,
     145,   146,   147,   148,   149,   150,   151,   152,   153,   154,
     155,   156,   157,   158,   159,   160,   161,   162,   163,   164,
     165,   166,   167,   168,   169,   170,   171,   172,   173,   174,
     175,   176,   177,   178,   179,   180,   181,   182,   183,   184,
     185,   186,   187,   188,   189,   190,   191,   192,   193,   194,
     195,   196,   197,   198,   199,   200,   201,   202,   203,   204,
     205,   206,   207,   208,   209,   210,   211,   212,   213,   214,
     215,   216,   217,   218,   219,   220,   221,   222,   223,   224,
     225,   226,   227,   228,   229,   230,   231,   232,   233,   234,
     235,   236,   237,   238,   239,   240,   241,   242,   243,   244,
     245,   246,   247,   248,   249,   250,   251,   252,   253,   254,
     255,   256,   257,   258,   259,   260,   261,   262,   263,   264,
     265,   266,   267,   268,   269,   270,   271,   272,   273,   274,
     275,   276,   277,   278,   279,   280,   281,   282,   283,   284,
     285,   286,   287,   288,   289,   290,   291,   292,   293,   294,
     295,   296,   297,   298,   299,   300,   301,   302,   303,   304,
     305,   306,   307,   308,   309,   310,   311,   312,   313,   314,
     315,   316,   317,   318,   319,   320,   321,   322,   323,   324,
     325,   326,   327,   328,   329,   330,   331,   332,   333,   334,
     335,   336,   337,   338,   339,   340
    };
    const unsigned user_token_number_max_ = 595;
    const token_number_type undef_token_ = 2;

    if (static_cast<int> (t) <= yyeof_)
      return yyeof_;
    else if (static_cast<unsigned> (t) <= user_token_number_max_)
      return translate_table[t];
    else
      return undef_token_;
  }

  // basic_symbol.
#if 201103L <= YY_CPLUSPLUS
  template <typename Base>
  seclang_parser::basic_symbol<Base>::basic_symbol (basic_symbol&& that)
    : Base (std::move (that))
    , value ()
    , location (std::move (that.location))
  {
    switch (this->type_get ())
    {
      case 145: // "Accuracy"
      case 146: // "Allow"
      case 147: // "Append"
      case 148: // "AuditLog"
      case 149: // "Block"
      case 150: // "Capture"
      case 151: // "Chain"
      case 152: // "ACTION_CTL_AUDIT_ENGINE"
      case 153: // "ACTION_CTL_AUDIT_LOG_PARTS"
      case 154: // "ACTION_CTL_BDY_JSON"
      case 155: // "ACTION_CTL_BDY_XML"
      case 156: // "ACTION_CTL_BDY_URLENCODED"
      case 157: // "ACTION_CTL_FORCE_REQ_BODY_VAR"
      case 158: // "ACTION_CTL_REQUEST_BODY_ACCESS"
      case 159: // "ACTION_CTL_RULE_REMOVE_BY_ID"
      case 160: // "ACTION_CTL_RULE_REMOVE_BY_TAG"
      case 161: // "ACTION_CTL_RULE_REMOVE_TARGET_BY_ID"
      case 162: // "ACTION_CTL_RULE_REMOVE_TARGET_BY_TAG"
      case 163: // "Deny"
      case 164: // "DeprecateVar"
      case 165: // "Drop"
      case 166: // "Exec"
      case 167: // "ExpireVar"
      case 168: // "Id"
      case 169: // "InitCol"
      case 170: // "Log"
      case 171: // "LogData"
      case 172: // "Maturity"
      case 173: // "Msg"
      case 174: // "MultiMatch"
      case 175: // "NoAuditLog"
      case 176: // "NoLog"
      case 177: // "Pass"
      case 178: // "Pause"
      case 179: // "Phase"
      case 180: // "Prepend"
      case 181: // "Proxy"
      case 182: // "Redirect"
      case 183: // "Rev"
      case 184: // "SanitiseArg"
      case 185: // "SanitiseMatched"
      case 186: // "SanitiseMatchedBytes"
      case 187: // "SanitiseRequestHeader"
      case 188: // "SanitiseResponseHeader"
      case 189: // "SetEnv"
      case 190: // "SetRsc"
      case 191: // "SetSid"
      case 192: // "SetUID"
      case 193: // "Severity"
      case 194: // "Skip"
      case 195: // "SkipAfter"
      case 196: // "Status"
      case 197: // "Tag"
      case 198: // "ACTION_TRANSFORMATION_BASE_64_ENCODE"
      case 199: // "ACTION_TRANSFORMATION_BASE_64_DECODE"
      case 200: // "ACTION_TRANSFORMATION_BASE_64_DECODE_EXT"
      case 201: // "ACTION_TRANSFORMATION_CMD_LINE"
      case 202: // "ACTION_TRANSFORMATION_COMPRESS_WHITESPACE"
      case 203: // "ACTION_TRANSFORMATION_CSS_DECODE"
      case 204: // "ACTION_TRANSFORMATION_ESCAPE_SEQ_DECODE"
      case 205: // "ACTION_TRANSFORMATION_HEX_ENCODE"
      case 206: // "ACTION_TRANSFORMATION_HEX_DECODE"
      case 207: // "ACTION_TRANSFORMATION_HTML_ENTITY_DECODE"
      case 208: // "ACTION_TRANSFORMATION_JS_DECODE"
      case 209: // "ACTION_TRANSFORMATION_LENGTH"
      case 210: // "ACTION_TRANSFORMATION_LOWERCASE"
      case 211: // "ACTION_TRANSFORMATION_MD5"
      case 212: // "ACTION_TRANSFORMATION_NONE"
      case 213: // "ACTION_TRANSFORMATION_NORMALISE_PATH"
      case 214: // "ACTION_TRANSFORMATION_NORMALISE_PATH_WIN"
      case 215: // "ACTION_TRANSFORMATION_PARITY_EVEN_7_BIT"
      case 216: // "ACTION_TRANSFORMATION_PARITY_ODD_7_BIT"
      case 217: // "ACTION_TRANSFORMATION_PARITY_ZERO_7_BIT"
      case 218: // "ACTION_TRANSFORMATION_REMOVE_COMMENTS"
      case 219: // "ACTION_TRANSFORMATION_REMOVE_COMMENTS_CHAR"
      case 220: // "ACTION_TRANSFORMATION_REMOVE_NULLS"
      case 221: // "ACTION_TRANSFORMATION_REMOVE_WHITESPACE"
      case 222: // "ACTION_TRANSFORMATION_REPLACE_COMMENTS"
      case 223: // "ACTION_TRANSFORMATION_REPLACE_NULLS"
      case 224: // "ACTION_TRANSFORMATION_SHA1"
      case 225: // "ACTION_TRANSFORMATION_SQL_HEX_DECODE"
      case 226: // "ACTION_TRANSFORMATION_TRIM"
      case 227: // "ACTION_TRANSFORMATION_TRIM_LEFT"
      case 228: // "ACTION_TRANSFORMATION_TRIM_RIGHT"
      case 229: // "ACTION_TRANSFORMATION_UPPERCASE"
      case 230: // "ACTION_TRANSFORMATION_URL_ENCODE"
      case 231: // "ACTION_TRANSFORMATION_URL_DECODE"
      case 232: // "ACTION_TRANSFORMATION_URL_DECODE_UNI"
      case 233: // "ACTION_TRANSFORMATION_UTF8_TO_UNICODE"
      case 234: // "Ver"
      case 235: // "xmlns"
      case 236: // "CONFIG_COMPONENT_SIG"
      case 237: // "CONFIG_CONN_ENGINE"
      case 238: // "CONFIG_SEC_ARGUMENT_SEPARATOR"
      case 239: // "CONFIG_SEC_WEB_APP_ID"
      case 240: // "CONFIG_SEC_SERVER_SIG"
      case 241: // "CONFIG_DIR_AUDIT_DIR"
      case 242: // "CONFIG_DIR_AUDIT_DIR_MOD"
      case 243: // "CONFIG_DIR_AUDIT_ENG"
      case 244: // "CONFIG_DIR_AUDIT_FLE_MOD"
      case 245: // "CONFIG_DIR_AUDIT_LOG"
      case 246: // "CONFIG_DIR_AUDIT_LOG2"
      case 247: // "CONFIG_DIR_AUDIT_LOG_P"
      case 248: // "CONFIG_DIR_AUDIT_STS"
      case 249: // "CONFIG_DIR_AUDIT_TPE"
      case 250: // "CONFIG_DIR_DEBUG_LOG"
      case 251: // "CONFIG_DIR_DEBUG_LVL"
      case 252: // "CONFIG_SEC_CACHE_TRANSFORMATIONS"
      case 253: // "CONFIG_SEC_DISABLE_BACKEND_COMPRESS"
      case 254: // "CONFIG_SEC_HASH_ENGINE"
      case 255: // "CONFIG_SEC_HASH_KEY"
      case 256: // "CONFIG_SEC_HASH_PARAM"
      case 257: // "CONFIG_SEC_HASH_METHOD_RX"
      case 258: // "CONFIG_SEC_HASH_METHOD_PM"
      case 259: // "CONFIG_SEC_CHROOT_DIR"
      case 260: // "CONFIG_DIR_GEO_DB"
      case 261: // "CONFIG_DIR_GSB_DB"
      case 262: // "CONFIG_SEC_GUARDIAN_LOG"
      case 263: // "CONFIG_DIR_PCRE_MATCH_LIMIT"
      case 264: // "CONFIG_DIR_PCRE_MATCH_LIMIT_RECURSION"
      case 265: // "CONFIG_SEC_CONN_R_STATE_LIMIT"
      case 266: // "CONFIG_SEC_CONN_W_STATE_LIMIT"
      case 267: // "CONFIG_SEC_SENSOR_ID"
      case 268: // "CONFIG_DIR_REQ_BODY"
      case 269: // "CONFIG_DIR_REQ_BODY_IN_MEMORY_LIMIT"
      case 270: // "CONFIG_DIR_REQ_BODY_LIMIT"
      case 271: // "CONFIG_DIR_REQ_BODY_LIMIT_ACTION"
      case 272: // "CONFIG_DIR_REQ_BODY_NO_FILES_LIMIT"
      case 273: // "CONFIG_DIR_RES_BODY"
      case 274: // "CONFIG_DIR_RES_BODY_LIMIT"
      case 275: // "CONFIG_DIR_RES_BODY_LIMIT_ACTION"
      case 276: // "CONFIG_SEC_RULE_INHERITANCE"
      case 277: // "CONFIG_SEC_RULE_PERF_TIME"
      case 278: // "CONFIG_DIR_RULE_ENG"
      case 279: // "CONFIG_DIR_SEC_ACTION"
      case 280: // "CONFIG_DIR_SEC_DEFAULT_ACTION"
      case 281: // "CONFIG_DIR_SEC_MARKER"
      case 282: // "CONFIG_DIR_UNICODE_MAP_FILE"
      case 283: // "CONFIG_DIR_UNICODE_CODE_PAGE"
      case 284: // "CONFIG_SEC_COLLECTION_TIMEOUT"
      case 285: // "CONFIG_SEC_HTTP_BLKEY"
      case 286: // "CONFIG_SEC_INTERCEPT_ON_ERROR"
      case 287: // "CONFIG_SEC_REMOTE_RULES_FAIL_ACTION"
      case 288: // "CONFIG_SEC_RULE_REMOVE_BY_ID"
      case 289: // "CONFIG_SEC_RULE_REMOVE_BY_MSG"
      case 290: // "CONFIG_SEC_RULE_REMOVE_BY_TAG"
      case 291: // "CONFIG_SEC_RULE_UPDATE_TARGET_BY_TAG"
      case 292: // "CONFIG_SEC_RULE_UPDATE_TARGET_BY_MSG"
      case 293: // "CONFIG_SEC_RULE_UPDATE_TARGET_BY_ID"
      case 294: // "CONFIG_SEC_RULE_UPDATE_ACTION_BY_ID"
      case 295: // "CONFIG_UPDLOAD_KEEP_FILES"
      case 296: // "CONFIG_UPDLOAD_SAVE_TMP_FILES"
      case 297: // "CONFIG_UPLOAD_DIR"
      case 298: // "CONFIG_UPLOAD_FILE_LIMIT"
      case 299: // "CONFIG_UPLOAD_FILE_MODE"
      case 300: // "CONFIG_VALUE_ABORT"
      case 301: // "CONFIG_VALUE_DETC"
      case 302: // "CONFIG_VALUE_HTTPS"
      case 303: // "CONFIG_VALUE_OFF"
      case 304: // "CONFIG_VALUE_ON"
      case 305: // "CONFIG_VALUE_PARALLEL"
      case 306: // "CONFIG_VALUE_PROCESS_PARTIAL"
      case 307: // "CONFIG_VALUE_REJECT"
      case 308: // "CONFIG_VALUE_RELEVANT_ONLY"
      case 309: // "CONFIG_VALUE_SERIAL"
      case 310: // "CONFIG_VALUE_WARN"
      case 311: // "CONFIG_XML_EXTERNAL_ENTITY"
      case 312: // "CONGIG_DIR_RESPONSE_BODY_MP"
      case 313: // "CONGIG_DIR_SEC_ARG_SEP"
      case 314: // "CONGIG_DIR_SEC_COOKIE_FORMAT"
      case 315: // "CONFIG_SEC_COOKIEV0_SEPARATOR"
      case 316: // "CONGIG_DIR_SEC_DATA_DIR"
      case 317: // "CONGIG_DIR_SEC_STATUS_ENGINE"
      case 318: // "CONFIG_SEC_STREAM_IN_BODY_INSPECTION"
      case 319: // "CONFIG_SEC_STREAM_OUT_BODY_INSPECTION"
      case 320: // "CONGIG_DIR_SEC_TMP_DIR"
      case 321: // "DIRECTIVE"
      case 322: // "DIRECTIVE_SECRULESCRIPT"
      case 323: // "FREE_TEXT_QUOTE_MACRO_EXPANSION"
      case 324: // "QUOTATION_MARK"
      case 325: // "RUN_TIME_VAR_BLD"
      case 326: // "RUN_TIME_VAR_DUR"
      case 327: // "RUN_TIME_VAR_HSV"
      case 328: // "RUN_TIME_VAR_REMOTE_USER"
      case 329: // "RUN_TIME_VAR_TIME"
      case 330: // "RUN_TIME_VAR_TIME_DAY"
      case 331: // "RUN_TIME_VAR_TIME_EPOCH"
      case 332: // "RUN_TIME_VAR_TIME_HOUR"
      case 333: // "RUN_TIME_VAR_TIME_MIN"
      case 334: // "RUN_TIME_VAR_TIME_MON"
      case 335: // "RUN_TIME_VAR_TIME_SEC"
      case 336: // "RUN_TIME_VAR_TIME_WDAY"
      case 337: // "RUN_TIME_VAR_TIME_YEAR"
      case 338: // "VARIABLE"
      case 339: // "Dictionary element"
      case 340: // "Dictionary element, selected by regexp"
        value.move< std::string > (std::move (that.value));
        break;

      case 347: // op
      case 348: // op_before_init
        value.move< std::unique_ptr<Operator> > (std::move (that.value));
        break;

      case 356: // run_time_string
        value.move< std::unique_ptr<RunTimeString> > (std::move (that.value));
        break;

      case 353: // var
        value.move< std::unique_ptr<Variable> > (std::move (that.value));
        break;

      case 354: // act
      case 355: // setvar_action
        value.move< std::unique_ptr<actions::Action> > (std::move (that.value));
        break;

      case 350: // variables
      case 351: // variables_pre_process
      case 352: // variables_may_be_quoted
        value.move< std::unique_ptr<std::vector<std::unique_ptr<Variable> > >  > (std::move (that.value));
        break;

      case 345: // actions
      case 346: // actions_may_quoted
        value.move< std::unique_ptr<std::vector<std::unique_ptr<actions::Action> > >  > (std::move (that.value));
        break;

      default:
        break;
    }

  }
#endif

  template <typename Base>
  seclang_parser::basic_symbol<Base>::basic_symbol (const basic_symbol& that)
    : Base (that)
    , value ()
    , location (that.location)
  {
    switch (this->type_get ())
    {
      case 145: // "Accuracy"
      case 146: // "Allow"
      case 147: // "Append"
      case 148: // "AuditLog"
      case 149: // "Block"
      case 150: // "Capture"
      case 151: // "Chain"
      case 152: // "ACTION_CTL_AUDIT_ENGINE"
      case 153: // "ACTION_CTL_AUDIT_LOG_PARTS"
      case 154: // "ACTION_CTL_BDY_JSON"
      case 155: // "ACTION_CTL_BDY_XML"
      case 156: // "ACTION_CTL_BDY_URLENCODED"
      case 157: // "ACTION_CTL_FORCE_REQ_BODY_VAR"
      case 158: // "ACTION_CTL_REQUEST_BODY_ACCESS"
      case 159: // "ACTION_CTL_RULE_REMOVE_BY_ID"
      case 160: // "ACTION_CTL_RULE_REMOVE_BY_TAG"
      case 161: // "ACTION_CTL_RULE_REMOVE_TARGET_BY_ID"
      case 162: // "ACTION_CTL_RULE_REMOVE_TARGET_BY_TAG"
      case 163: // "Deny"
      case 164: // "DeprecateVar"
      case 165: // "Drop"
      case 166: // "Exec"
      case 167: // "ExpireVar"
      case 168: // "Id"
      case 169: // "InitCol"
      case 170: // "Log"
      case 171: // "LogData"
      case 172: // "Maturity"
      case 173: // "Msg"
      case 174: // "MultiMatch"
      case 175: // "NoAuditLog"
      case 176: // "NoLog"
      case 177: // "Pass"
      case 178: // "Pause"
      case 179: // "Phase"
      case 180: // "Prepend"
      case 181: // "Proxy"
      case 182: // "Redirect"
      case 183: // "Rev"
      case 184: // "SanitiseArg"
      case 185: // "SanitiseMatched"
      case 186: // "SanitiseMatchedBytes"
      case 187: // "SanitiseRequestHeader"
      case 188: // "SanitiseResponseHeader"
      case 189: // "SetEnv"
      case 190: // "SetRsc"
      case 191: // "SetSid"
      case 192: // "SetUID"
      case 193: // "Severity"
      case 194: // "Skip"
      case 195: // "SkipAfter"
      case 196: // "Status"
      case 197: // "Tag"
      case 198: // "ACTION_TRANSFORMATION_BASE_64_ENCODE"
      case 199: // "ACTION_TRANSFORMATION_BASE_64_DECODE"
      case 200: // "ACTION_TRANSFORMATION_BASE_64_DECODE_EXT"
      case 201: // "ACTION_TRANSFORMATION_CMD_LINE"
      case 202: // "ACTION_TRANSFORMATION_COMPRESS_WHITESPACE"
      case 203: // "ACTION_TRANSFORMATION_CSS_DECODE"
      case 204: // "ACTION_TRANSFORMATION_ESCAPE_SEQ_DECODE"
      case 205: // "ACTION_TRANSFORMATION_HEX_ENCODE"
      case 206: // "ACTION_TRANSFORMATION_HEX_DECODE"
      case 207: // "ACTION_TRANSFORMATION_HTML_ENTITY_DECODE"
      case 208: // "ACTION_TRANSFORMATION_JS_DECODE"
      case 209: // "ACTION_TRANSFORMATION_LENGTH"
      case 210: // "ACTION_TRANSFORMATION_LOWERCASE"
      case 211: // "ACTION_TRANSFORMATION_MD5"
      case 212: // "ACTION_TRANSFORMATION_NONE"
      case 213: // "ACTION_TRANSFORMATION_NORMALISE_PATH"
      case 214: // "ACTION_TRANSFORMATION_NORMALISE_PATH_WIN"
      case 215: // "ACTION_TRANSFORMATION_PARITY_EVEN_7_BIT"
      case 216: // "ACTION_TRANSFORMATION_PARITY_ODD_7_BIT"
      case 217: // "ACTION_TRANSFORMATION_PARITY_ZERO_7_BIT"
      case 218: // "ACTION_TRANSFORMATION_REMOVE_COMMENTS"
      case 219: // "ACTION_TRANSFORMATION_REMOVE_COMMENTS_CHAR"
      case 220: // "ACTION_TRANSFORMATION_REMOVE_NULLS"
      case 221: // "ACTION_TRANSFORMATION_REMOVE_WHITESPACE"
      case 222: // "ACTION_TRANSFORMATION_REPLACE_COMMENTS"
      case 223: // "ACTION_TRANSFORMATION_REPLACE_NULLS"
      case 224: // "ACTION_TRANSFORMATION_SHA1"
      case 225: // "ACTION_TRANSFORMATION_SQL_HEX_DECODE"
      case 226: // "ACTION_TRANSFORMATION_TRIM"
      case 227: // "ACTION_TRANSFORMATION_TRIM_LEFT"
      case 228: // "ACTION_TRANSFORMATION_TRIM_RIGHT"
      case 229: // "ACTION_TRANSFORMATION_UPPERCASE"
      case 230: // "ACTION_TRANSFORMATION_URL_ENCODE"
      case 231: // "ACTION_TRANSFORMATION_URL_DECODE"
      case 232: // "ACTION_TRANSFORMATION_URL_DECODE_UNI"
      case 233: // "ACTION_TRANSFORMATION_UTF8_TO_UNICODE"
      case 234: // "Ver"
      case 235: // "xmlns"
      case 236: // "CONFIG_COMPONENT_SIG"
      case 237: // "CONFIG_CONN_ENGINE"
      case 238: // "CONFIG_SEC_ARGUMENT_SEPARATOR"
      case 239: // "CONFIG_SEC_WEB_APP_ID"
      case 240: // "CONFIG_SEC_SERVER_SIG"
      case 241: // "CONFIG_DIR_AUDIT_DIR"
      case 242: // "CONFIG_DIR_AUDIT_DIR_MOD"
      case 243: // "CONFIG_DIR_AUDIT_ENG"
      case 244: // "CONFIG_DIR_AUDIT_FLE_MOD"
      case 245: // "CONFIG_DIR_AUDIT_LOG"
      case 246: // "CONFIG_DIR_AUDIT_LOG2"
      case 247: // "CONFIG_DIR_AUDIT_LOG_P"
      case 248: // "CONFIG_DIR_AUDIT_STS"
      case 249: // "CONFIG_DIR_AUDIT_TPE"
      case 250: // "CONFIG_DIR_DEBUG_LOG"
      case 251: // "CONFIG_DIR_DEBUG_LVL"
      case 252: // "CONFIG_SEC_CACHE_TRANSFORMATIONS"
      case 253: // "CONFIG_SEC_DISABLE_BACKEND_COMPRESS"
      case 254: // "CONFIG_SEC_HASH_ENGINE"
      case 255: // "CONFIG_SEC_HASH_KEY"
      case 256: // "CONFIG_SEC_HASH_PARAM"
      case 257: // "CONFIG_SEC_HASH_METHOD_RX"
      case 258: // "CONFIG_SEC_HASH_METHOD_PM"
      case 259: // "CONFIG_SEC_CHROOT_DIR"
      case 260: // "CONFIG_DIR_GEO_DB"
      case 261: // "CONFIG_DIR_GSB_DB"
      case 262: // "CONFIG_SEC_GUARDIAN_LOG"
      case 263: // "CONFIG_DIR_PCRE_MATCH_LIMIT"
      case 264: // "CONFIG_DIR_PCRE_MATCH_LIMIT_RECURSION"
      case 265: // "CONFIG_SEC_CONN_R_STATE_LIMIT"
      case 266: // "CONFIG_SEC_CONN_W_STATE_LIMIT"
      case 267: // "CONFIG_SEC_SENSOR_ID"
      case 268: // "CONFIG_DIR_REQ_BODY"
      case 269: // "CONFIG_DIR_REQ_BODY_IN_MEMORY_LIMIT"
      case 270: // "CONFIG_DIR_REQ_BODY_LIMIT"
      case 271: // "CONFIG_DIR_REQ_BODY_LIMIT_ACTION"
      case 272: // "CONFIG_DIR_REQ_BODY_NO_FILES_LIMIT"
      case 273: // "CONFIG_DIR_RES_BODY"
      case 274: // "CONFIG_DIR_RES_BODY_LIMIT"
      case 275: // "CONFIG_DIR_RES_BODY_LIMIT_ACTION"
      case 276: // "CONFIG_SEC_RULE_INHERITANCE"
      case 277: // "CONFIG_SEC_RULE_PERF_TIME"
      case 278: // "CONFIG_DIR_RULE_ENG"
      case 279: // "CONFIG_DIR_SEC_ACTION"
      case 280: // "CONFIG_DIR_SEC_DEFAULT_ACTION"
      case 281: // "CONFIG_DIR_SEC_MARKER"
      case 282: // "CONFIG_DIR_UNICODE_MAP_FILE"
      case 283: // "CONFIG_DIR_UNICODE_CODE_PAGE"
      case 284: // "CONFIG_SEC_COLLECTION_TIMEOUT"
      case 285: // "CONFIG_SEC_HTTP_BLKEY"
      case 286: // "CONFIG_SEC_INTERCEPT_ON_ERROR"
      case 287: // "CONFIG_SEC_REMOTE_RULES_FAIL_ACTION"
      case 288: // "CONFIG_SEC_RULE_REMOVE_BY_ID"
      case 289: // "CONFIG_SEC_RULE_REMOVE_BY_MSG"
      case 290: // "CONFIG_SEC_RULE_REMOVE_BY_TAG"
      case 291: // "CONFIG_SEC_RULE_UPDATE_TARGET_BY_TAG"
      case 292: // "CONFIG_SEC_RULE_UPDATE_TARGET_BY_MSG"
      case 293: // "CONFIG_SEC_RULE_UPDATE_TARGET_BY_ID"
      case 294: // "CONFIG_SEC_RULE_UPDATE_ACTION_BY_ID"
      case 295: // "CONFIG_UPDLOAD_KEEP_FILES"
      case 296: // "CONFIG_UPDLOAD_SAVE_TMP_FILES"
      case 297: // "CONFIG_UPLOAD_DIR"
      case 298: // "CONFIG_UPLOAD_FILE_LIMIT"
      case 299: // "CONFIG_UPLOAD_FILE_MODE"
      case 300: // "CONFIG_VALUE_ABORT"
      case 301: // "CONFIG_VALUE_DETC"
      case 302: // "CONFIG_VALUE_HTTPS"
      case 303: // "CONFIG_VALUE_OFF"
      case 304: // "CONFIG_VALUE_ON"
      case 305: // "CONFIG_VALUE_PARALLEL"
      case 306: // "CONFIG_VALUE_PROCESS_PARTIAL"
      case 307: // "CONFIG_VALUE_REJECT"
      case 308: // "CONFIG_VALUE_RELEVANT_ONLY"
      case 309: // "CONFIG_VALUE_SERIAL"
      case 310: // "CONFIG_VALUE_WARN"
      case 311: // "CONFIG_XML_EXTERNAL_ENTITY"
      case 312: // "CONGIG_DIR_RESPONSE_BODY_MP"
      case 313: // "CONGIG_DIR_SEC_ARG_SEP"
      case 314: // "CONGIG_DIR_SEC_COOKIE_FORMAT"
      case 315: // "CONFIG_SEC_COOKIEV0_SEPARATOR"
      case 316: // "CONGIG_DIR_SEC_DATA_DIR"
      case 317: // "CONGIG_DIR_SEC_STATUS_ENGINE"
      case 318: // "CONFIG_SEC_STREAM_IN_BODY_INSPECTION"
      case 319: // "CONFIG_SEC_STREAM_OUT_BODY_INSPECTION"
      case 320: // "CONGIG_DIR_SEC_TMP_DIR"
      case 321: // "DIRECTIVE"
      case 322: // "DIRECTIVE_SECRULESCRIPT"
      case 323: // "FREE_TEXT_QUOTE_MACRO_EXPANSION"
      case 324: // "QUOTATION_MARK"
      case 325: // "RUN_TIME_VAR_BLD"
      case 326: // "RUN_TIME_VAR_DUR"
      case 327: // "RUN_TIME_VAR_HSV"
      case 328: // "RUN_TIME_VAR_REMOTE_USER"
      case 329: // "RUN_TIME_VAR_TIME"
      case 330: // "RUN_TIME_VAR_TIME_DAY"
      case 331: // "RUN_TIME_VAR_TIME_EPOCH"
      case 332: // "RUN_TIME_VAR_TIME_HOUR"
      case 333: // "RUN_TIME_VAR_TIME_MIN"
      case 334: // "RUN_TIME_VAR_TIME_MON"
      case 335: // "RUN_TIME_VAR_TIME_SEC"
      case 336: // "RUN_TIME_VAR_TIME_WDAY"
      case 337: // "RUN_TIME_VAR_TIME_YEAR"
      case 338: // "VARIABLE"
      case 339: // "Dictionary element"
      case 340: // "Dictionary element, selected by regexp"
        value.copy< std::string > (YY_MOVE (that.value));
        break;

      case 347: // op
      case 348: // op_before_init
        value.copy< std::unique_ptr<Operator> > (YY_MOVE (that.value));
        break;

      case 356: // run_time_string
        value.copy< std::unique_ptr<RunTimeString> > (YY_MOVE (that.value));
        break;

      case 353: // var
        value.copy< std::unique_ptr<Variable> > (YY_MOVE (that.value));
        break;

      case 354: // act
      case 355: // setvar_action
        value.copy< std::unique_ptr<actions::Action> > (YY_MOVE (that.value));
        break;

      case 350: // variables
      case 351: // variables_pre_process
      case 352: // variables_may_be_quoted
        value.copy< std::unique_ptr<std::vector<std::unique_ptr<Variable> > >  > (YY_MOVE (that.value));
        break;

      case 345: // actions
      case 346: // actions_may_quoted
        value.copy< std::unique_ptr<std::vector<std::unique_ptr<actions::Action> > >  > (YY_MOVE (that.value));
        break;

      default:
        break;
    }

  }



  template <typename Base>
  bool
  seclang_parser::basic_symbol<Base>::empty () const YY_NOEXCEPT
  {
    return Base::type_get () == empty_symbol;
  }

  template <typename Base>
  void
  seclang_parser::basic_symbol<Base>::move (basic_symbol& s)
  {
    super_type::move (s);
    switch (this->type_get ())
    {
      case 145: // "Accuracy"
      case 146: // "Allow"
      case 147: // "Append"
      case 148: // "AuditLog"
      case 149: // "Block"
      case 150: // "Capture"
      case 151: // "Chain"
      case 152: // "ACTION_CTL_AUDIT_ENGINE"
      case 153: // "ACTION_CTL_AUDIT_LOG_PARTS"
      case 154: // "ACTION_CTL_BDY_JSON"
      case 155: // "ACTION_CTL_BDY_XML"
      case 156: // "ACTION_CTL_BDY_URLENCODED"
      case 157: // "ACTION_CTL_FORCE_REQ_BODY_VAR"
      case 158: // "ACTION_CTL_REQUEST_BODY_ACCESS"
      case 159: // "ACTION_CTL_RULE_REMOVE_BY_ID"
      case 160: // "ACTION_CTL_RULE_REMOVE_BY_TAG"
      case 161: // "ACTION_CTL_RULE_REMOVE_TARGET_BY_ID"
      case 162: // "ACTION_CTL_RULE_REMOVE_TARGET_BY_TAG"
      case 163: // "Deny"
      case 164: // "DeprecateVar"
      case 165: // "Drop"
      case 166: // "Exec"
      case 167: // "ExpireVar"
      case 168: // "Id"
      case 169: // "InitCol"
      case 170: // "Log"
      case 171: // "LogData"
      case 172: // "Maturity"
      case 173: // "Msg"
      case 174: // "MultiMatch"
      case 175: // "NoAuditLog"
      case 176: // "NoLog"
      case 177: // "Pass"
      case 178: // "Pause"
      case 179: // "Phase"
      case 180: // "Prepend"
      case 181: // "Proxy"
      case 182: // "Redirect"
      case 183: // "Rev"
      case 184: // "SanitiseArg"
      case 185: // "SanitiseMatched"
      case 186: // "SanitiseMatchedBytes"
      case 187: // "SanitiseRequestHeader"
      case 188: // "SanitiseResponseHeader"
      case 189: // "SetEnv"
      case 190: // "SetRsc"
      case 191: // "SetSid"
      case 192: // "SetUID"
      case 193: // "Severity"
      case 194: // "Skip"
      case 195: // "SkipAfter"
      case 196: // "Status"
      case 197: // "Tag"
      case 198: // "ACTION_TRANSFORMATION_BASE_64_ENCODE"
      case 199: // "ACTION_TRANSFORMATION_BASE_64_DECODE"
      case 200: // "ACTION_TRANSFORMATION_BASE_64_DECODE_EXT"
      case 201: // "ACTION_TRANSFORMATION_CMD_LINE"
      case 202: // "ACTION_TRANSFORMATION_COMPRESS_WHITESPACE"
      case 203: // "ACTION_TRANSFORMATION_CSS_DECODE"
      case 204: // "ACTION_TRANSFORMATION_ESCAPE_SEQ_DECODE"
      case 205: // "ACTION_TRANSFORMATION_HEX_ENCODE"
      case 206: // "ACTION_TRANSFORMATION_HEX_DECODE"
      case 207: // "ACTION_TRANSFORMATION_HTML_ENTITY_DECODE"
      case 208: // "ACTION_TRANSFORMATION_JS_DECODE"
      case 209: // "ACTION_TRANSFORMATION_LENGTH"
      case 210: // "ACTION_TRANSFORMATION_LOWERCASE"
      case 211: // "ACTION_TRANSFORMATION_MD5"
      case 212: // "ACTION_TRANSFORMATION_NONE"
      case 213: // "ACTION_TRANSFORMATION_NORMALISE_PATH"
      case 214: // "ACTION_TRANSFORMATION_NORMALISE_PATH_WIN"
      case 215: // "ACTION_TRANSFORMATION_PARITY_EVEN_7_BIT"
      case 216: // "ACTION_TRANSFORMATION_PARITY_ODD_7_BIT"
      case 217: // "ACTION_TRANSFORMATION_PARITY_ZERO_7_BIT"
      case 218: // "ACTION_TRANSFORMATION_REMOVE_COMMENTS"
      case 219: // "ACTION_TRANSFORMATION_REMOVE_COMMENTS_CHAR"
      case 220: // "ACTION_TRANSFORMATION_REMOVE_NULLS"
      case 221: // "ACTION_TRANSFORMATION_REMOVE_WHITESPACE"
      case 222: // "ACTION_TRANSFORMATION_REPLACE_COMMENTS"
      case 223: // "ACTION_TRANSFORMATION_REPLACE_NULLS"
      case 224: // "ACTION_TRANSFORMATION_SHA1"
      case 225: // "ACTION_TRANSFORMATION_SQL_HEX_DECODE"
      case 226: // "ACTION_TRANSFORMATION_TRIM"
      case 227: // "ACTION_TRANSFORMATION_TRIM_LEFT"
      case 228: // "ACTION_TRANSFORMATION_TRIM_RIGHT"
      case 229: // "ACTION_TRANSFORMATION_UPPERCASE"
      case 230: // "ACTION_TRANSFORMATION_URL_ENCODE"
      case 231: // "ACTION_TRANSFORMATION_URL_DECODE"
      case 232: // "ACTION_TRANSFORMATION_URL_DECODE_UNI"
      case 233: // "ACTION_TRANSFORMATION_UTF8_TO_UNICODE"
      case 234: // "Ver"
      case 235: // "xmlns"
      case 236: // "CONFIG_COMPONENT_SIG"
      case 237: // "CONFIG_CONN_ENGINE"
      case 238: // "CONFIG_SEC_ARGUMENT_SEPARATOR"
      case 239: // "CONFIG_SEC_WEB_APP_ID"
      case 240: // "CONFIG_SEC_SERVER_SIG"
      case 241: // "CONFIG_DIR_AUDIT_DIR"
      case 242: // "CONFIG_DIR_AUDIT_DIR_MOD"
      case 243: // "CONFIG_DIR_AUDIT_ENG"
      case 244: // "CONFIG_DIR_AUDIT_FLE_MOD"
      case 245: // "CONFIG_DIR_AUDIT_LOG"
      case 246: // "CONFIG_DIR_AUDIT_LOG2"
      case 247: // "CONFIG_DIR_AUDIT_LOG_P"
      case 248: // "CONFIG_DIR_AUDIT_STS"
      case 249: // "CONFIG_DIR_AUDIT_TPE"
      case 250: // "CONFIG_DIR_DEBUG_LOG"
      case 251: // "CONFIG_DIR_DEBUG_LVL"
      case 252: // "CONFIG_SEC_CACHE_TRANSFORMATIONS"
      case 253: // "CONFIG_SEC_DISABLE_BACKEND_COMPRESS"
      case 254: // "CONFIG_SEC_HASH_ENGINE"
      case 255: // "CONFIG_SEC_HASH_KEY"
      case 256: // "CONFIG_SEC_HASH_PARAM"
      case 257: // "CONFIG_SEC_HASH_METHOD_RX"
      case 258: // "CONFIG_SEC_HASH_METHOD_PM"
      case 259: // "CONFIG_SEC_CHROOT_DIR"
      case 260: // "CONFIG_DIR_GEO_DB"
      case 261: // "CONFIG_DIR_GSB_DB"
      case 262: // "CONFIG_SEC_GUARDIAN_LOG"
      case 263: // "CONFIG_DIR_PCRE_MATCH_LIMIT"
      case 264: // "CONFIG_DIR_PCRE_MATCH_LIMIT_RECURSION"
      case 265: // "CONFIG_SEC_CONN_R_STATE_LIMIT"
      case 266: // "CONFIG_SEC_CONN_W_STATE_LIMIT"
      case 267: // "CONFIG_SEC_SENSOR_ID"
      case 268: // "CONFIG_DIR_REQ_BODY"
      case 269: // "CONFIG_DIR_REQ_BODY_IN_MEMORY_LIMIT"
      case 270: // "CONFIG_DIR_REQ_BODY_LIMIT"
      case 271: // "CONFIG_DIR_REQ_BODY_LIMIT_ACTION"
      case 272: // "CONFIG_DIR_REQ_BODY_NO_FILES_LIMIT"
      case 273: // "CONFIG_DIR_RES_BODY"
      case 274: // "CONFIG_DIR_RES_BODY_LIMIT"
      case 275: // "CONFIG_DIR_RES_BODY_LIMIT_ACTION"
      case 276: // "CONFIG_SEC_RULE_INHERITANCE"
      case 277: // "CONFIG_SEC_RULE_PERF_TIME"
      case 278: // "CONFIG_DIR_RULE_ENG"
      case 279: // "CONFIG_DIR_SEC_ACTION"
      case 280: // "CONFIG_DIR_SEC_DEFAULT_ACTION"
      case 281: // "CONFIG_DIR_SEC_MARKER"
      case 282: // "CONFIG_DIR_UNICODE_MAP_FILE"
      case 283: // "CONFIG_DIR_UNICODE_CODE_PAGE"
      case 284: // "CONFIG_SEC_COLLECTION_TIMEOUT"
      case 285: // "CONFIG_SEC_HTTP_BLKEY"
      case 286: // "CONFIG_SEC_INTERCEPT_ON_ERROR"
      case 287: // "CONFIG_SEC_REMOTE_RULES_FAIL_ACTION"
      case 288: // "CONFIG_SEC_RULE_REMOVE_BY_ID"
      case 289: // "CONFIG_SEC_RULE_REMOVE_BY_MSG"
      case 290: // "CONFIG_SEC_RULE_REMOVE_BY_TAG"
      case 291: // "CONFIG_SEC_RULE_UPDATE_TARGET_BY_TAG"
      case 292: // "CONFIG_SEC_RULE_UPDATE_TARGET_BY_MSG"
      case 293: // "CONFIG_SEC_RULE_UPDATE_TARGET_BY_ID"
      case 294: // "CONFIG_SEC_RULE_UPDATE_ACTION_BY_ID"
      case 295: // "CONFIG_UPDLOAD_KEEP_FILES"
      case 296: // "CONFIG_UPDLOAD_SAVE_TMP_FILES"
      case 297: // "CONFIG_UPLOAD_DIR"
      case 298: // "CONFIG_UPLOAD_FILE_LIMIT"
      case 299: // "CONFIG_UPLOAD_FILE_MODE"
      case 300: // "CONFIG_VALUE_ABORT"
      case 301: // "CONFIG_VALUE_DETC"
      case 302: // "CONFIG_VALUE_HTTPS"
      case 303: // "CONFIG_VALUE_OFF"
      case 304: // "CONFIG_VALUE_ON"
      case 305: // "CONFIG_VALUE_PARALLEL"
      case 306: // "CONFIG_VALUE_PROCESS_PARTIAL"
      case 307: // "CONFIG_VALUE_REJECT"
      case 308: // "CONFIG_VALUE_RELEVANT_ONLY"
      case 309: // "CONFIG_VALUE_SERIAL"
      case 310: // "CONFIG_VALUE_WARN"
      case 311: // "CONFIG_XML_EXTERNAL_ENTITY"
      case 312: // "CONGIG_DIR_RESPONSE_BODY_MP"
      case 313: // "CONGIG_DIR_SEC_ARG_SEP"
      case 314: // "CONGIG_DIR_SEC_COOKIE_FORMAT"
      case 315: // "CONFIG_SEC_COOKIEV0_SEPARATOR"
      case 316: // "CONGIG_DIR_SEC_DATA_DIR"
      case 317: // "CONGIG_DIR_SEC_STATUS_ENGINE"
      case 318: // "CONFIG_SEC_STREAM_IN_BODY_INSPECTION"
      case 319: // "CONFIG_SEC_STREAM_OUT_BODY_INSPECTION"
      case 320: // "CONGIG_DIR_SEC_TMP_DIR"
      case 321: // "DIRECTIVE"
      case 322: // "DIRECTIVE_SECRULESCRIPT"
      case 323: // "FREE_TEXT_QUOTE_MACRO_EXPANSION"
      case 324: // "QUOTATION_MARK"
      case 325: // "RUN_TIME_VAR_BLD"
      case 326: // "RUN_TIME_VAR_DUR"
      case 327: // "RUN_TIME_VAR_HSV"
      case 328: // "RUN_TIME_VAR_REMOTE_USER"
      case 329: // "RUN_TIME_VAR_TIME"
      case 330: // "RUN_TIME_VAR_TIME_DAY"
      case 331: // "RUN_TIME_VAR_TIME_EPOCH"
      case 332: // "RUN_TIME_VAR_TIME_HOUR"
      case 333: // "RUN_TIME_VAR_TIME_MIN"
      case 334: // "RUN_TIME_VAR_TIME_MON"
      case 335: // "RUN_TIME_VAR_TIME_SEC"
      case 336: // "RUN_TIME_VAR_TIME_WDAY"
      case 337: // "RUN_TIME_VAR_TIME_YEAR"
      case 338: // "VARIABLE"
      case 339: // "Dictionary element"
      case 340: // "Dictionary element, selected by regexp"
        value.move< std::string > (YY_MOVE (s.value));
        break;

      case 347: // op
      case 348: // op_before_init
        value.move< std::unique_ptr<Operator> > (YY_MOVE (s.value));
        break;

      case 356: // run_time_string
        value.move< std::unique_ptr<RunTimeString> > (YY_MOVE (s.value));
        break;

      case 353: // var
        value.move< std::unique_ptr<Variable> > (YY_MOVE (s.value));
        break;

      case 354: // act
      case 355: // setvar_action
        value.move< std::unique_ptr<actions::Action> > (YY_MOVE (s.value));
        break;

      case 350: // variables
      case 351: // variables_pre_process
      case 352: // variables_may_be_quoted
        value.move< std::unique_ptr<std::vector<std::unique_ptr<Variable> > >  > (YY_MOVE (s.value));
        break;

      case 345: // actions
      case 346: // actions_may_quoted
        value.move< std::unique_ptr<std::vector<std::unique_ptr<actions::Action> > >  > (YY_MOVE (s.value));
        break;

      default:
        break;
    }

    location = YY_MOVE (s.location);
  }

  // by_type.
  inline
  seclang_parser::by_type::by_type ()
    : type (empty_symbol)
  {}

#if 201103L <= YY_CPLUSPLUS
  inline
  seclang_parser::by_type::by_type (by_type&& that)
    : type (that.type)
  {
    that.clear ();
  }
#endif

  inline
  seclang_parser::by_type::by_type (const by_type& that)
    : type (that.type)
  {}

  inline
  seclang_parser::by_type::by_type (token_type t)
    : type (yytranslate_ (t))
  {}

  inline
  void
  seclang_parser::by_type::clear ()
  {
    type = empty_symbol;
  }

  inline
  void
  seclang_parser::by_type::move (by_type& that)
  {
    type = that.type;
    that.clear ();
  }

  inline
  int
  seclang_parser::by_type::type_get () const YY_NOEXCEPT
  {
    return type;
  }

  inline
  seclang_parser::token_type
  seclang_parser::by_type::token () const YY_NOEXCEPT
  {
    // YYTOKNUM[NUM] -- (External) token number corresponding to the
    // (internal) symbol number NUM (which must be that of a token).  */
    static
    const unsigned short
    yytoken_number_[] =
    {
       0,   256,   257,   258,   259,   260,   261,   262,   263,   264,
     265,   266,   267,   268,   269,   270,   271,   272,   273,   274,
     275,   276,   277,   278,   279,   280,   281,   282,   283,   284,
     285,   286,   287,   288,   289,   290,   291,   292,   293,   294,
     295,   296,   297,   298,   299,   300,   301,   302,   303,   304,
     305,   306,   307,   308,   309,   310,   311,   312,   313,   314,
     315,   316,   317,   318,   319,   320,   321,   322,   323,   324,
     325,   326,   327,   328,   329,   330,   331,   332,   333,   334,
     335,   336,   337,   338,   339,   340,   341,   342,   343,   344,
     345,   346,   347,   348,   349,   350,   351,   352,   353,   354,
     355,   356,   357,   358,   359,   360,   361,   362,   363,   364,
     365,   366,   367,   368,   369,   370,   371,   372,   373,   374,
     375,   376,   377,   378,   379,   380,   381,   382,   383,   384,
     385,   386,   387,   388,   389,   390,   391,   392,   393,   394,
     395,   396,   397,   398,   399,   400,   401,   402,   403,   404,
     405,   406,   407,   408,   409,   410,   411,   412,   413,   414,
     415,   416,   417,   418,   419,   420,   421,   422,   423,   424,
     425,   426,   427,   428,   429,   430,   431,   432,   433,   434,
     435,   436,   437,   438,   439,   440,   441,   442,   443,   444,
     445,   446,   447,   448,   449,   450,   451,   452,   453,   454,
     455,   456,   457,   458,   459,   460,   461,   462,   463,   464,
     465,   466,   467,   468,   469,   470,   471,   472,   473,   474,
     475,   476,   477,   478,   479,   480,   481,   482,   483,   484,
     485,   486,   487,   488,   489,   490,   491,   492,   493,   494,
     495,   496,   497,   498,   499,   500,   501,   502,   503,   504,
     505,   506,   507,   508,   509,   510,   511,   512,   513,   514,
     515,   516,   517,   518,   519,   520,   521,   522,   523,   524,
     525,   526,   527,   528,   529,   530,   531,   532,   533,   534,
     535,   536,   537,   538,   539,   540,   541,   542,   543,   544,
     545,   546,   547,   548,   549,   550,   551,   552,   553,   554,
     555,   556,   557,   558,   559,   560,   561,   562,   563,   564,
     565,   566,   567,   568,   569,   570,   571,   572,   573,   574,
     575,   576,   577,   578,   579,   580,   581,   582,   583,   584,
     585,   586,   587,   588,   589,   590,   591,   592,   593,   594,
     595
    };
    return token_type (yytoken_number_[type]);
  }


} // yy
#line 8132 "seclang-parser.hh" // lalr1.cc:401




#endif // !YY_YY_SECLANG_PARSER_HH_INCLUDED
