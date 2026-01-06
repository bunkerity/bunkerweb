// A Bison parser, made by GNU Bison 3.8.2.

// Skeleton interface for Bison LALR(1) parsers in C++

// Copyright (C) 2002-2015, 2018-2021 Free Software Foundation, Inc.

// This program is free software: you can redistribute it and/or modify
// it under the terms of the GNU General Public License as published by
// the Free Software Foundation, either version 3 of the License, or
// (at your option) any later version.

// This program is distributed in the hope that it will be useful,
// but WITHOUT ANY WARRANTY; without even the implied warranty of
// MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
// GNU General Public License for more details.

// You should have received a copy of the GNU General Public License
// along with this program.  If not, see <https://www.gnu.org/licenses/>.

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

// DO NOT RELY ON FEATURES THAT ARE NOT DOCUMENTED in the manual,
// especially those whose name start with YY_ or yy_.  They are
// private implementation details that can be changed or removed.

#ifndef YY_YY_SECLANG_PARSER_HH_INCLUDED
# define YY_YY_SECLANG_PARSER_HH_INCLUDED
// "%code requires" blocks.
#line 10 "seclang-parser.yy"

#include <string>
#include <iterator>

namespace ModSecurity {
namespace Parser {
class Driver;
}
}

#include "modsecurity/rule_unconditional.h"
#include "src/rule_script.h"

#include "src/actions/accuracy.h"
#include "src/actions/audit_log.h"
#include "src/actions/block.h"
#include "src/actions/capture.h"
#include "src/actions/chain.h"
#include "src/actions/ctl/audit_engine.h"
#include "src/actions/ctl/audit_log_parts.h"
#include "src/actions/ctl/parse_xml_into_args.h"
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
#include "src/actions/expire_var.h"
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
#include "src/actions/ver.h"
#include "src/actions/xmlns.h"

#include "src/actions/transformations/none.h"
#include "src/actions/transformations/transformation.h"
#include "src/actions/transformations/url_decode_uni.h"
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
#include "src/operators/rx_global.h"
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
#include "modsecurity/rules_set_properties.h"
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
#include "src/variables/msc_pcre_error.h"
#include "src/variables/msc_pcre_limits_exceeded.h"
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
#include "src/variables/multipart_part_headers.h"
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


#line 360 "seclang-parser.hh"

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
#ifndef YY_ASSERT
# include <cassert>
# define YY_ASSERT assert
#endif


#ifndef YY_ATTRIBUTE_PURE
# if defined __GNUC__ && 2 < __GNUC__ + (96 <= __GNUC_MINOR__)
#  define YY_ATTRIBUTE_PURE __attribute__ ((__pure__))
# else
#  define YY_ATTRIBUTE_PURE
# endif
#endif

#ifndef YY_ATTRIBUTE_UNUSED
# if defined __GNUC__ && 2 < __GNUC__ + (7 <= __GNUC_MINOR__)
#  define YY_ATTRIBUTE_UNUSED __attribute__ ((__unused__))
# else
#  define YY_ATTRIBUTE_UNUSED
# endif
#endif

/* Suppress unused-variable warnings by "using" E.  */
#if ! defined lint || defined __GNUC__
# define YY_USE(E) ((void) (E))
#else
# define YY_USE(E) /* empty */
#endif

/* Suppress an incorrect diagnostic about yylval being uninitialized.  */
#if defined __GNUC__ && ! defined __ICC && 406 <= __GNUC__ * 100 + __GNUC_MINOR__
# if __GNUC__ * 100 + __GNUC_MINOR__ < 407
#  define YY_IGNORE_MAYBE_UNINITIALIZED_BEGIN                           \
    _Pragma ("GCC diagnostic push")                                     \
    _Pragma ("GCC diagnostic ignored \"-Wuninitialized\"")
# else
#  define YY_IGNORE_MAYBE_UNINITIALIZED_BEGIN                           \
    _Pragma ("GCC diagnostic push")                                     \
    _Pragma ("GCC diagnostic ignored \"-Wuninitialized\"")              \
    _Pragma ("GCC diagnostic ignored \"-Wmaybe-uninitialized\"")
# endif
# define YY_IGNORE_MAYBE_UNINITIALIZED_END      \
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

#if defined __cplusplus && defined __GNUC__ && ! defined __ICC && 6 <= __GNUC__
# define YY_IGNORE_USELESS_CAST_BEGIN                          \
    _Pragma ("GCC diagnostic push")                            \
    _Pragma ("GCC diagnostic ignored \"-Wuseless-cast\"")
# define YY_IGNORE_USELESS_CAST_END            \
    _Pragma ("GCC diagnostic pop")
#endif
#ifndef YY_IGNORE_USELESS_CAST_BEGIN
# define YY_IGNORE_USELESS_CAST_BEGIN
# define YY_IGNORE_USELESS_CAST_END
#endif

# ifndef YY_CAST
#  ifdef __cplusplus
#   define YY_CAST(Type, Val) static_cast<Type> (Val)
#   define YY_REINTERPRET_CAST(Type, Val) reinterpret_cast<Type> (Val)
#  else
#   define YY_CAST(Type, Val) ((Type) (Val))
#   define YY_REINTERPRET_CAST(Type, Val) ((Type) (Val))
#  endif
# endif
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
#line 500 "seclang-parser.hh"




  /// A Bison parser.
  class seclang_parser
  {
  public:
#ifdef YYSTYPE
# ifdef __GNUC__
#  pragma GCC message "bison: do not #define YYSTYPE in C++, use %define api.value.type"
# endif
    typedef YYSTYPE value_type;
#else
  /// A buffer to store and retrieve objects.
  ///
  /// Sort of a variant, but does not keep track of the nature
  /// of the stored data, since that knowledge is available
  /// via the current parser state.
  class value_type
  {
  public:
    /// Type of *this.
    typedef value_type self_type;

    /// Empty construction.
    value_type () YY_NOEXCEPT
      : yyraw_ ()
      , yytypeid_ (YY_NULLPTR)
    {}

    /// Construct and fill.
    template <typename T>
    value_type (YY_RVREF (T) t)
      : yytypeid_ (&typeid (T))
    {
      YY_ASSERT (sizeof (T) <= size);
      new (yyas_<T> ()) T (YY_MOVE (t));
    }

#if 201103L <= YY_CPLUSPLUS
    /// Non copyable.
    value_type (const self_type&) = delete;
    /// Non copyable.
    self_type& operator= (const self_type&) = delete;
#endif

    /// Destruction, allowed only if empty.
    ~value_type () YY_NOEXCEPT
    {
      YY_ASSERT (!yytypeid_);
    }

# if 201103L <= YY_CPLUSPLUS
    /// Instantiate a \a T in here from \a t.
    template <typename T, typename... U>
    T&
    emplace (U&&... u)
    {
      YY_ASSERT (!yytypeid_);
      YY_ASSERT (sizeof (T) <= size);
      yytypeid_ = & typeid (T);
      return *new (yyas_<T> ()) T (std::forward <U>(u)...);
    }
# else
    /// Instantiate an empty \a T in here.
    template <typename T>
    T&
    emplace ()
    {
      YY_ASSERT (!yytypeid_);
      YY_ASSERT (sizeof (T) <= size);
      yytypeid_ = & typeid (T);
      return *new (yyas_<T> ()) T ();
    }

    /// Instantiate a \a T in here from \a t.
    template <typename T>
    T&
    emplace (const T& t)
    {
      YY_ASSERT (!yytypeid_);
      YY_ASSERT (sizeof (T) <= size);
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
      YY_ASSERT (yytypeid_);
      YY_ASSERT (*yytypeid_ == typeid (T));
      YY_ASSERT (sizeof (T) <= size);
      return *yyas_<T> ();
    }

    /// Const accessor to a built \a T (for %printer).
    template <typename T>
    const T&
    as () const YY_NOEXCEPT
    {
      YY_ASSERT (yytypeid_);
      YY_ASSERT (*yytypeid_ == typeid (T));
      YY_ASSERT (sizeof (T) <= size);
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
      YY_ASSERT (yytypeid_);
      YY_ASSERT (*yytypeid_ == *that.yytypeid_);
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
#if YY_CPLUSPLUS < 201103L
    /// Non copyable.
    value_type (const self_type&);
    /// Non copyable.
    self_type& operator= (const self_type&);
#endif

    /// Accessor to raw memory as \a T.
    template <typename T>
    T*
    yyas_ () YY_NOEXCEPT
    {
      void *yyp = yyraw_;
      return static_cast<T*> (yyp);
     }

    /// Const accessor to raw memory as \a T.
    template <typename T>
    const T*
    yyas_ () const YY_NOEXCEPT
    {
      const void *yyp = yyraw_;
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
      // "ACTION_CTL_PARSE_XML_INTO_ARGS"
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
      // "CONFIG_DIR_AUDIT_PREFIX"
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
      // "CONFIG_DIR_ARGS_LIMIT"
      // "CONFIG_DIR_REQ_BODY_JSON_DEPTH_LIMIT"
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
      // "CONFIG_VALUE_ONLYARGS"
      // "CONFIG_VALUE_OFF"
      // "CONFIG_VALUE_ON"
      // "CONFIG_VALUE_PARALLEL"
      // "CONFIG_VALUE_PROCESS_PARTIAL"
      // "CONFIG_VALUE_REJECT"
      // "CONFIG_VALUE_RELEVANT_ONLY"
      // "CONFIG_VALUE_SERIAL"
      // "CONFIG_VALUE_WARN"
      // "CONFIG_XML_EXTERNAL_ENTITY"
      // "CONFIG_XML_PARSE_XML_INTO_ARGS"
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
      // "Dictionary element, with equals"
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
      long double yyalign_me_;
      /// A buffer large enough to store any of the semantic values.
      char yyraw_[size];
    };

    /// Whether the content is built: if defined, the name of the stored type.
    const std::type_info *yytypeid_;
  };

#endif
    /// Backward compatibility (Bison 3.8).
    typedef value_type semantic_type;

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

    /// Token kinds.
    struct token
    {
      enum token_kind_type
      {
        TOK_YYEMPTY = -2,
    TOK_END = 0,                   // "end of file"
    TOK_YYerror = 256,             // error
    TOK_YYUNDEF = 257,             // "invalid token"
    TOK_COMMA = 258,               // ","
    TOK_CONFIG_CONTENT_INJECTION = 259, // "CONFIG_CONTENT_INJECTION"
    TOK_CONGIG_DIR_RESPONSE_BODY_MP_CLEAR = 260, // "CONGIG_DIR_RESPONSE_BODY_MP_CLEAR"
    TOK_PIPE = 261,                // PIPE
    TOK_NEW_LINE = 262,            // NEW_LINE
    TOK_VAR_COUNT = 263,           // VAR_COUNT
    TOK_VAR_EXCLUSION = 264,       // VAR_EXCLUSION
    TOK_VARIABLE_ARGS = 265,       // VARIABLE_ARGS
    TOK_VARIABLE_ARGS_POST = 266,  // VARIABLE_ARGS_POST
    TOK_VARIABLE_ARGS_GET = 267,   // VARIABLE_ARGS_GET
    TOK_VARIABLE_FILES_SIZES = 268, // VARIABLE_FILES_SIZES
    TOK_VARIABLE_FILES_NAMES = 269, // VARIABLE_FILES_NAMES
    TOK_VARIABLE_FILES_TMP_CONTENT = 270, // VARIABLE_FILES_TMP_CONTENT
    TOK_VARIABLE_MULTIPART_FILENAME = 271, // VARIABLE_MULTIPART_FILENAME
    TOK_VARIABLE_MULTIPART_NAME = 272, // VARIABLE_MULTIPART_NAME
    TOK_VARIABLE_MATCHED_VARS_NAMES = 273, // VARIABLE_MATCHED_VARS_NAMES
    TOK_VARIABLE_MATCHED_VARS = 274, // VARIABLE_MATCHED_VARS
    TOK_VARIABLE_FILES = 275,      // VARIABLE_FILES
    TOK_VARIABLE_REQUEST_COOKIES = 276, // VARIABLE_REQUEST_COOKIES
    TOK_VARIABLE_REQUEST_HEADERS = 277, // VARIABLE_REQUEST_HEADERS
    TOK_VARIABLE_RESPONSE_HEADERS = 278, // VARIABLE_RESPONSE_HEADERS
    TOK_VARIABLE_GEO = 279,        // VARIABLE_GEO
    TOK_VARIABLE_REQUEST_COOKIES_NAMES = 280, // VARIABLE_REQUEST_COOKIES_NAMES
    TOK_VARIABLE_MULTIPART_PART_HEADERS = 281, // VARIABLE_MULTIPART_PART_HEADERS
    TOK_VARIABLE_ARGS_COMBINED_SIZE = 282, // VARIABLE_ARGS_COMBINED_SIZE
    TOK_VARIABLE_ARGS_GET_NAMES = 283, // VARIABLE_ARGS_GET_NAMES
    TOK_VARIABLE_RULE = 284,       // VARIABLE_RULE
    TOK_VARIABLE_ARGS_NAMES = 285, // "Variable ARGS_NAMES"
    TOK_VARIABLE_ARGS_POST_NAMES = 286, // VARIABLE_ARGS_POST_NAMES
    TOK_VARIABLE_AUTH_TYPE = 287,  // "AUTH_TYPE"
    TOK_VARIABLE_FILES_COMBINED_SIZE = 288, // "FILES_COMBINED_SIZE"
    TOK_VARIABLE_FILES_TMP_NAMES = 289, // "FILES_TMPNAMES"
    TOK_VARIABLE_FULL_REQUEST = 290, // "FULL_REQUEST"
    TOK_VARIABLE_FULL_REQUEST_LENGTH = 291, // "FULL_REQUEST_LENGTH"
    TOK_VARIABLE_INBOUND_DATA_ERROR = 292, // "INBOUND_DATA_ERROR"
    TOK_VARIABLE_MATCHED_VAR = 293, // "MATCHED_VAR"
    TOK_VARIABLE_MATCHED_VAR_NAME = 294, // "MATCHED_VAR_NAME"
    TOK_VARIABLE_MSC_PCRE_ERROR = 295, // "MSC_PCRE_ERROR"
    TOK_VARIABLE_MSC_PCRE_LIMITS_EXCEEDED = 296, // "MSC_PCRE_LIMITS_EXCEEDED"
    TOK_VARIABLE_MULTIPART_BOUNDARY_QUOTED = 297, // VARIABLE_MULTIPART_BOUNDARY_QUOTED
    TOK_VARIABLE_MULTIPART_BOUNDARY_WHITESPACE = 298, // VARIABLE_MULTIPART_BOUNDARY_WHITESPACE
    TOK_VARIABLE_MULTIPART_CRLF_LF_LINES = 299, // "MULTIPART_CRLF_LF_LINES"
    TOK_VARIABLE_MULTIPART_DATA_AFTER = 300, // "MULTIPART_DATA_AFTER"
    TOK_VARIABLE_MULTIPART_DATA_BEFORE = 301, // VARIABLE_MULTIPART_DATA_BEFORE
    TOK_VARIABLE_MULTIPART_FILE_LIMIT_EXCEEDED = 302, // "MULTIPART_FILE_LIMIT_EXCEEDED"
    TOK_VARIABLE_MULTIPART_HEADER_FOLDING = 303, // "MULTIPART_HEADER_FOLDING"
    TOK_VARIABLE_MULTIPART_INVALID_HEADER_FOLDING = 304, // "MULTIPART_INVALID_HEADER_FOLDING"
    TOK_VARIABLE_MULTIPART_INVALID_PART = 305, // VARIABLE_MULTIPART_INVALID_PART
    TOK_VARIABLE_MULTIPART_INVALID_QUOTING = 306, // "MULTIPART_INVALID_QUOTING"
    TOK_VARIABLE_MULTIPART_LF_LINE = 307, // VARIABLE_MULTIPART_LF_LINE
    TOK_VARIABLE_MULTIPART_MISSING_SEMICOLON = 308, // VARIABLE_MULTIPART_MISSING_SEMICOLON
    TOK_VARIABLE_MULTIPART_SEMICOLON_MISSING = 309, // VARIABLE_MULTIPART_SEMICOLON_MISSING
    TOK_VARIABLE_MULTIPART_STRICT_ERROR = 310, // "MULTIPART_STRICT_ERROR"
    TOK_VARIABLE_MULTIPART_UNMATCHED_BOUNDARY = 311, // "MULTIPART_UNMATCHED_BOUNDARY"
    TOK_VARIABLE_OUTBOUND_DATA_ERROR = 312, // "OUTBOUND_DATA_ERROR"
    TOK_VARIABLE_PATH_INFO = 313,  // "PATH_INFO"
    TOK_VARIABLE_QUERY_STRING = 314, // "QUERY_STRING"
    TOK_VARIABLE_REMOTE_ADDR = 315, // "REMOTE_ADDR"
    TOK_VARIABLE_REMOTE_HOST = 316, // "REMOTE_HOST"
    TOK_VARIABLE_REMOTE_PORT = 317, // "REMOTE_PORT"
    TOK_VARIABLE_REQBODY_ERROR_MSG = 318, // "REQBODY_ERROR_MSG"
    TOK_VARIABLE_REQBODY_ERROR = 319, // "REQBODY_ERROR"
    TOK_VARIABLE_REQBODY_PROCESSOR_ERROR_MSG = 320, // "REQBODY_PROCESSOR_ERROR_MSG"
    TOK_VARIABLE_REQBODY_PROCESSOR_ERROR = 321, // "REQBODY_PROCESSOR_ERROR"
    TOK_VARIABLE_REQBODY_PROCESSOR = 322, // "REQBODY_PROCESSOR"
    TOK_VARIABLE_REQUEST_BASENAME = 323, // "REQUEST_BASENAME"
    TOK_VARIABLE_REQUEST_BODY_LENGTH = 324, // "REQUEST_BODY_LENGTH"
    TOK_VARIABLE_REQUEST_BODY = 325, // "REQUEST_BODY"
    TOK_VARIABLE_REQUEST_FILE_NAME = 326, // "REQUEST_FILENAME"
    TOK_VARIABLE_REQUEST_HEADERS_NAMES = 327, // VARIABLE_REQUEST_HEADERS_NAMES
    TOK_VARIABLE_REQUEST_LINE = 328, // "REQUEST_LINE"
    TOK_VARIABLE_REQUEST_METHOD = 329, // "REQUEST_METHOD"
    TOK_VARIABLE_REQUEST_PROTOCOL = 330, // "REQUEST_PROTOCOL"
    TOK_VARIABLE_REQUEST_URI_RAW = 331, // "REQUEST_URI_RAW"
    TOK_VARIABLE_REQUEST_URI = 332, // "REQUEST_URI"
    TOK_VARIABLE_RESOURCE = 333,   // "RESOURCE"
    TOK_VARIABLE_RESPONSE_BODY = 334, // "RESPONSE_BODY"
    TOK_VARIABLE_RESPONSE_CONTENT_LENGTH = 335, // "RESPONSE_CONTENT_LENGTH"
    TOK_VARIABLE_RESPONSE_CONTENT_TYPE = 336, // VARIABLE_RESPONSE_CONTENT_TYPE
    TOK_VARIABLE_RESPONSE_HEADERS_NAMES = 337, // VARIABLE_RESPONSE_HEADERS_NAMES
    TOK_VARIABLE_RESPONSE_PROTOCOL = 338, // "RESPONSE_PROTOCOL"
    TOK_VARIABLE_RESPONSE_STATUS = 339, // "RESPONSE_STATUS"
    TOK_VARIABLE_SERVER_ADDR = 340, // "SERVER_ADDR"
    TOK_VARIABLE_SERVER_NAME = 341, // "SERVER_NAME"
    TOK_VARIABLE_SERVER_PORT = 342, // "SERVER_PORT"
    TOK_VARIABLE_SESSION_ID = 343, // "SESSIONID"
    TOK_VARIABLE_UNIQUE_ID = 344,  // "UNIQUE_ID"
    TOK_VARIABLE_URL_ENCODED_ERROR = 345, // "URLENCODED_ERROR"
    TOK_VARIABLE_USER_ID = 346,    // "USERID"
    TOK_VARIABLE_WEB_APP_ID = 347, // "WEBAPPID"
    TOK_VARIABLE_STATUS = 348,     // "VARIABLE_STATUS"
    TOK_VARIABLE_STATUS_LINE = 349, // "VARIABLE_STATUS_LINE"
    TOK_VARIABLE_IP = 350,         // "VARIABLE_IP"
    TOK_VARIABLE_GLOBAL = 351,     // "VARIABLE_GLOBAL"
    TOK_VARIABLE_TX = 352,         // "VARIABLE_TX"
    TOK_VARIABLE_SESSION = 353,    // "VARIABLE_SESSION"
    TOK_VARIABLE_USER = 354,       // "VARIABLE_USER"
    TOK_RUN_TIME_VAR_ENV = 355,    // "RUN_TIME_VAR_ENV"
    TOK_RUN_TIME_VAR_XML = 356,    // "RUN_TIME_VAR_XML"
    TOK_ACTION_SETVAR = 357,       // "SetVar"
    TOK_SETVAR_OPERATION_EQUALS = 358, // SETVAR_OPERATION_EQUALS
    TOK_SETVAR_OPERATION_EQUALS_PLUS = 359, // SETVAR_OPERATION_EQUALS_PLUS
    TOK_SETVAR_OPERATION_EQUALS_MINUS = 360, // SETVAR_OPERATION_EQUALS_MINUS
    TOK_NOT = 361,                 // "NOT"
    TOK_OPERATOR_BEGINS_WITH = 362, // "OPERATOR_BEGINS_WITH"
    TOK_OPERATOR_CONTAINS = 363,   // "OPERATOR_CONTAINS"
    TOK_OPERATOR_CONTAINS_WORD = 364, // "OPERATOR_CONTAINS_WORD"
    TOK_OPERATOR_DETECT_SQLI = 365, // "OPERATOR_DETECT_SQLI"
    TOK_OPERATOR_DETECT_XSS = 366, // "OPERATOR_DETECT_XSS"
    TOK_OPERATOR_ENDS_WITH = 367,  // "OPERATOR_ENDS_WITH"
    TOK_OPERATOR_EQ = 368,         // "OPERATOR_EQ"
    TOK_OPERATOR_FUZZY_HASH = 369, // "OPERATOR_FUZZY_HASH"
    TOK_OPERATOR_GEOLOOKUP = 370,  // "OPERATOR_GEOLOOKUP"
    TOK_OPERATOR_GE = 371,         // "OPERATOR_GE"
    TOK_OPERATOR_GSB_LOOKUP = 372, // "OPERATOR_GSB_LOOKUP"
    TOK_OPERATOR_GT = 373,         // "OPERATOR_GT"
    TOK_OPERATOR_INSPECT_FILE = 374, // "OPERATOR_INSPECT_FILE"
    TOK_OPERATOR_IP_MATCH_FROM_FILE = 375, // "OPERATOR_IP_MATCH_FROM_FILE"
    TOK_OPERATOR_IP_MATCH = 376,   // "OPERATOR_IP_MATCH"
    TOK_OPERATOR_LE = 377,         // "OPERATOR_LE"
    TOK_OPERATOR_LT = 378,         // "OPERATOR_LT"
    TOK_OPERATOR_PM_FROM_FILE = 379, // "OPERATOR_PM_FROM_FILE"
    TOK_OPERATOR_PM = 380,         // "OPERATOR_PM"
    TOK_OPERATOR_RBL = 381,        // "OPERATOR_RBL"
    TOK_OPERATOR_RSUB = 382,       // "OPERATOR_RSUB"
    TOK_OPERATOR_RX_CONTENT_ONLY = 383, // "Operator RX (content only)"
    TOK_OPERATOR_RX = 384,         // "OPERATOR_RX"
    TOK_OPERATOR_RX_GLOBAL = 385,  // "OPERATOR_RX_GLOBAL"
    TOK_OPERATOR_STR_EQ = 386,     // "OPERATOR_STR_EQ"
    TOK_OPERATOR_STR_MATCH = 387,  // "OPERATOR_STR_MATCH"
    TOK_OPERATOR_UNCONDITIONAL_MATCH = 388, // "OPERATOR_UNCONDITIONAL_MATCH"
    TOK_OPERATOR_VALIDATE_BYTE_RANGE = 389, // "OPERATOR_VALIDATE_BYTE_RANGE"
    TOK_OPERATOR_VALIDATE_DTD = 390, // "OPERATOR_VALIDATE_DTD"
    TOK_OPERATOR_VALIDATE_HASH = 391, // "OPERATOR_VALIDATE_HASH"
    TOK_OPERATOR_VALIDATE_SCHEMA = 392, // "OPERATOR_VALIDATE_SCHEMA"
    TOK_OPERATOR_VALIDATE_URL_ENCODING = 393, // "OPERATOR_VALIDATE_URL_ENCODING"
    TOK_OPERATOR_VALIDATE_UTF8_ENCODING = 394, // "OPERATOR_VALIDATE_UTF8_ENCODING"
    TOK_OPERATOR_VERIFY_CC = 395,  // "OPERATOR_VERIFY_CC"
    TOK_OPERATOR_VERIFY_CPF = 396, // "OPERATOR_VERIFY_CPF"
    TOK_OPERATOR_VERIFY_SSN = 397, // "OPERATOR_VERIFY_SSN"
    TOK_OPERATOR_VERIFY_SVNR = 398, // "OPERATOR_VERIFY_SVNR"
    TOK_OPERATOR_WITHIN = 399,     // "OPERATOR_WITHIN"
    TOK_CONFIG_DIR_AUDIT_LOG_FMT = 400, // CONFIG_DIR_AUDIT_LOG_FMT
    TOK_JSON = 401,                // JSON
    TOK_NATIVE = 402,              // NATIVE
    TOK_ACTION_CTL_RULE_ENGINE = 403, // "ACTION_CTL_RULE_ENGINE"
    TOK_ACTION_ACCURACY = 404,     // "Accuracy"
    TOK_ACTION_ALLOW = 405,        // "Allow"
    TOK_ACTION_APPEND = 406,       // "Append"
    TOK_ACTION_AUDIT_LOG = 407,    // "AuditLog"
    TOK_ACTION_BLOCK = 408,        // "Block"
    TOK_ACTION_CAPTURE = 409,      // "Capture"
    TOK_ACTION_CHAIN = 410,        // "Chain"
    TOK_ACTION_CTL_AUDIT_ENGINE = 411, // "ACTION_CTL_AUDIT_ENGINE"
    TOK_ACTION_CTL_AUDIT_LOG_PARTS = 412, // "ACTION_CTL_AUDIT_LOG_PARTS"
    TOK_ACTION_CTL_BDY_JSON = 413, // "ACTION_CTL_BDY_JSON"
    TOK_ACTION_CTL_BDY_XML = 414,  // "ACTION_CTL_BDY_XML"
    TOK_ACTION_CTL_BDY_URLENCODED = 415, // "ACTION_CTL_BDY_URLENCODED"
    TOK_ACTION_CTL_FORCE_REQ_BODY_VAR = 416, // "ACTION_CTL_FORCE_REQ_BODY_VAR"
    TOK_ACTION_CTL_PARSE_XML_INTO_ARGS = 417, // "ACTION_CTL_PARSE_XML_INTO_ARGS"
    TOK_ACTION_CTL_REQUEST_BODY_ACCESS = 418, // "ACTION_CTL_REQUEST_BODY_ACCESS"
    TOK_ACTION_CTL_RULE_REMOVE_BY_ID = 419, // "ACTION_CTL_RULE_REMOVE_BY_ID"
    TOK_ACTION_CTL_RULE_REMOVE_BY_TAG = 420, // "ACTION_CTL_RULE_REMOVE_BY_TAG"
    TOK_ACTION_CTL_RULE_REMOVE_TARGET_BY_ID = 421, // "ACTION_CTL_RULE_REMOVE_TARGET_BY_ID"
    TOK_ACTION_CTL_RULE_REMOVE_TARGET_BY_TAG = 422, // "ACTION_CTL_RULE_REMOVE_TARGET_BY_TAG"
    TOK_ACTION_DENY = 423,         // "Deny"
    TOK_ACTION_DEPRECATE_VAR = 424, // "DeprecateVar"
    TOK_ACTION_DROP = 425,         // "Drop"
    TOK_ACTION_EXEC = 426,         // "Exec"
    TOK_ACTION_EXPIRE_VAR = 427,   // "ExpireVar"
    TOK_ACTION_ID = 428,           // "Id"
    TOK_ACTION_INITCOL = 429,      // "InitCol"
    TOK_ACTION_LOG = 430,          // "Log"
    TOK_ACTION_LOG_DATA = 431,     // "LogData"
    TOK_ACTION_MATURITY = 432,     // "Maturity"
    TOK_ACTION_MSG = 433,          // "Msg"
    TOK_ACTION_MULTI_MATCH = 434,  // "MultiMatch"
    TOK_ACTION_NO_AUDIT_LOG = 435, // "NoAuditLog"
    TOK_ACTION_NO_LOG = 436,       // "NoLog"
    TOK_ACTION_PASS = 437,         // "Pass"
    TOK_ACTION_PAUSE = 438,        // "Pause"
    TOK_ACTION_PHASE = 439,        // "Phase"
    TOK_ACTION_PREPEND = 440,      // "Prepend"
    TOK_ACTION_PROXY = 441,        // "Proxy"
    TOK_ACTION_REDIRECT = 442,     // "Redirect"
    TOK_ACTION_REV = 443,          // "Rev"
    TOK_ACTION_SANITISE_ARG = 444, // "SanitiseArg"
    TOK_ACTION_SANITISE_MATCHED = 445, // "SanitiseMatched"
    TOK_ACTION_SANITISE_MATCHED_BYTES = 446, // "SanitiseMatchedBytes"
    TOK_ACTION_SANITISE_REQUEST_HEADER = 447, // "SanitiseRequestHeader"
    TOK_ACTION_SANITISE_RESPONSE_HEADER = 448, // "SanitiseResponseHeader"
    TOK_ACTION_SETENV = 449,       // "SetEnv"
    TOK_ACTION_SETRSC = 450,       // "SetRsc"
    TOK_ACTION_SETSID = 451,       // "SetSid"
    TOK_ACTION_SETUID = 452,       // "SetUID"
    TOK_ACTION_SEVERITY = 453,     // "Severity"
    TOK_ACTION_SKIP = 454,         // "Skip"
    TOK_ACTION_SKIP_AFTER = 455,   // "SkipAfter"
    TOK_ACTION_STATUS = 456,       // "Status"
    TOK_ACTION_TAG = 457,          // "Tag"
    TOK_ACTION_TRANSFORMATION_BASE_64_ENCODE = 458, // "ACTION_TRANSFORMATION_BASE_64_ENCODE"
    TOK_ACTION_TRANSFORMATION_BASE_64_DECODE = 459, // "ACTION_TRANSFORMATION_BASE_64_DECODE"
    TOK_ACTION_TRANSFORMATION_BASE_64_DECODE_EXT = 460, // "ACTION_TRANSFORMATION_BASE_64_DECODE_EXT"
    TOK_ACTION_TRANSFORMATION_CMD_LINE = 461, // "ACTION_TRANSFORMATION_CMD_LINE"
    TOK_ACTION_TRANSFORMATION_COMPRESS_WHITESPACE = 462, // "ACTION_TRANSFORMATION_COMPRESS_WHITESPACE"
    TOK_ACTION_TRANSFORMATION_CSS_DECODE = 463, // "ACTION_TRANSFORMATION_CSS_DECODE"
    TOK_ACTION_TRANSFORMATION_ESCAPE_SEQ_DECODE = 464, // "ACTION_TRANSFORMATION_ESCAPE_SEQ_DECODE"
    TOK_ACTION_TRANSFORMATION_HEX_ENCODE = 465, // "ACTION_TRANSFORMATION_HEX_ENCODE"
    TOK_ACTION_TRANSFORMATION_HEX_DECODE = 466, // "ACTION_TRANSFORMATION_HEX_DECODE"
    TOK_ACTION_TRANSFORMATION_HTML_ENTITY_DECODE = 467, // "ACTION_TRANSFORMATION_HTML_ENTITY_DECODE"
    TOK_ACTION_TRANSFORMATION_JS_DECODE = 468, // "ACTION_TRANSFORMATION_JS_DECODE"
    TOK_ACTION_TRANSFORMATION_LENGTH = 469, // "ACTION_TRANSFORMATION_LENGTH"
    TOK_ACTION_TRANSFORMATION_LOWERCASE = 470, // "ACTION_TRANSFORMATION_LOWERCASE"
    TOK_ACTION_TRANSFORMATION_MD5 = 471, // "ACTION_TRANSFORMATION_MD5"
    TOK_ACTION_TRANSFORMATION_NONE = 472, // "ACTION_TRANSFORMATION_NONE"
    TOK_ACTION_TRANSFORMATION_NORMALISE_PATH = 473, // "ACTION_TRANSFORMATION_NORMALISE_PATH"
    TOK_ACTION_TRANSFORMATION_NORMALISE_PATH_WIN = 474, // "ACTION_TRANSFORMATION_NORMALISE_PATH_WIN"
    TOK_ACTION_TRANSFORMATION_PARITY_EVEN_7_BIT = 475, // "ACTION_TRANSFORMATION_PARITY_EVEN_7_BIT"
    TOK_ACTION_TRANSFORMATION_PARITY_ODD_7_BIT = 476, // "ACTION_TRANSFORMATION_PARITY_ODD_7_BIT"
    TOK_ACTION_TRANSFORMATION_PARITY_ZERO_7_BIT = 477, // "ACTION_TRANSFORMATION_PARITY_ZERO_7_BIT"
    TOK_ACTION_TRANSFORMATION_REMOVE_COMMENTS = 478, // "ACTION_TRANSFORMATION_REMOVE_COMMENTS"
    TOK_ACTION_TRANSFORMATION_REMOVE_COMMENTS_CHAR = 479, // "ACTION_TRANSFORMATION_REMOVE_COMMENTS_CHAR"
    TOK_ACTION_TRANSFORMATION_REMOVE_NULLS = 480, // "ACTION_TRANSFORMATION_REMOVE_NULLS"
    TOK_ACTION_TRANSFORMATION_REMOVE_WHITESPACE = 481, // "ACTION_TRANSFORMATION_REMOVE_WHITESPACE"
    TOK_ACTION_TRANSFORMATION_REPLACE_COMMENTS = 482, // "ACTION_TRANSFORMATION_REPLACE_COMMENTS"
    TOK_ACTION_TRANSFORMATION_REPLACE_NULLS = 483, // "ACTION_TRANSFORMATION_REPLACE_NULLS"
    TOK_ACTION_TRANSFORMATION_SHA1 = 484, // "ACTION_TRANSFORMATION_SHA1"
    TOK_ACTION_TRANSFORMATION_SQL_HEX_DECODE = 485, // "ACTION_TRANSFORMATION_SQL_HEX_DECODE"
    TOK_ACTION_TRANSFORMATION_TRIM = 486, // "ACTION_TRANSFORMATION_TRIM"
    TOK_ACTION_TRANSFORMATION_TRIM_LEFT = 487, // "ACTION_TRANSFORMATION_TRIM_LEFT"
    TOK_ACTION_TRANSFORMATION_TRIM_RIGHT = 488, // "ACTION_TRANSFORMATION_TRIM_RIGHT"
    TOK_ACTION_TRANSFORMATION_UPPERCASE = 489, // "ACTION_TRANSFORMATION_UPPERCASE"
    TOK_ACTION_TRANSFORMATION_URL_ENCODE = 490, // "ACTION_TRANSFORMATION_URL_ENCODE"
    TOK_ACTION_TRANSFORMATION_URL_DECODE = 491, // "ACTION_TRANSFORMATION_URL_DECODE"
    TOK_ACTION_TRANSFORMATION_URL_DECODE_UNI = 492, // "ACTION_TRANSFORMATION_URL_DECODE_UNI"
    TOK_ACTION_TRANSFORMATION_UTF8_TO_UNICODE = 493, // "ACTION_TRANSFORMATION_UTF8_TO_UNICODE"
    TOK_ACTION_VER = 494,          // "Ver"
    TOK_ACTION_XMLNS = 495,        // "xmlns"
    TOK_CONFIG_COMPONENT_SIG = 496, // "CONFIG_COMPONENT_SIG"
    TOK_CONFIG_CONN_ENGINE = 497,  // "CONFIG_CONN_ENGINE"
    TOK_CONFIG_SEC_ARGUMENT_SEPARATOR = 498, // "CONFIG_SEC_ARGUMENT_SEPARATOR"
    TOK_CONFIG_SEC_WEB_APP_ID = 499, // "CONFIG_SEC_WEB_APP_ID"
    TOK_CONFIG_SEC_SERVER_SIG = 500, // "CONFIG_SEC_SERVER_SIG"
    TOK_CONFIG_DIR_AUDIT_DIR = 501, // "CONFIG_DIR_AUDIT_DIR"
    TOK_CONFIG_DIR_AUDIT_DIR_MOD = 502, // "CONFIG_DIR_AUDIT_DIR_MOD"
    TOK_CONFIG_DIR_AUDIT_ENG = 503, // "CONFIG_DIR_AUDIT_ENG"
    TOK_CONFIG_DIR_AUDIT_FLE_MOD = 504, // "CONFIG_DIR_AUDIT_FLE_MOD"
    TOK_CONFIG_DIR_AUDIT_LOG = 505, // "CONFIG_DIR_AUDIT_LOG"
    TOK_CONFIG_DIR_AUDIT_LOG2 = 506, // "CONFIG_DIR_AUDIT_LOG2"
    TOK_CONFIG_DIR_AUDIT_LOG_P = 507, // "CONFIG_DIR_AUDIT_LOG_P"
    TOK_CONFIG_DIR_AUDIT_STS = 508, // "CONFIG_DIR_AUDIT_STS"
    TOK_CONFIG_DIR_AUDIT_PREFIX = 509, // "CONFIG_DIR_AUDIT_PREFIX"
    TOK_CONFIG_DIR_AUDIT_TPE = 510, // "CONFIG_DIR_AUDIT_TPE"
    TOK_CONFIG_DIR_DEBUG_LOG = 511, // "CONFIG_DIR_DEBUG_LOG"
    TOK_CONFIG_DIR_DEBUG_LVL = 512, // "CONFIG_DIR_DEBUG_LVL"
    TOK_CONFIG_SEC_CACHE_TRANSFORMATIONS = 513, // "CONFIG_SEC_CACHE_TRANSFORMATIONS"
    TOK_CONFIG_SEC_DISABLE_BACKEND_COMPRESS = 514, // "CONFIG_SEC_DISABLE_BACKEND_COMPRESS"
    TOK_CONFIG_SEC_HASH_ENGINE = 515, // "CONFIG_SEC_HASH_ENGINE"
    TOK_CONFIG_SEC_HASH_KEY = 516, // "CONFIG_SEC_HASH_KEY"
    TOK_CONFIG_SEC_HASH_PARAM = 517, // "CONFIG_SEC_HASH_PARAM"
    TOK_CONFIG_SEC_HASH_METHOD_RX = 518, // "CONFIG_SEC_HASH_METHOD_RX"
    TOK_CONFIG_SEC_HASH_METHOD_PM = 519, // "CONFIG_SEC_HASH_METHOD_PM"
    TOK_CONFIG_SEC_CHROOT_DIR = 520, // "CONFIG_SEC_CHROOT_DIR"
    TOK_CONFIG_DIR_GEO_DB = 521,   // "CONFIG_DIR_GEO_DB"
    TOK_CONFIG_DIR_GSB_DB = 522,   // "CONFIG_DIR_GSB_DB"
    TOK_CONFIG_SEC_GUARDIAN_LOG = 523, // "CONFIG_SEC_GUARDIAN_LOG"
    TOK_CONFIG_DIR_PCRE_MATCH_LIMIT = 524, // "CONFIG_DIR_PCRE_MATCH_LIMIT"
    TOK_CONFIG_DIR_PCRE_MATCH_LIMIT_RECURSION = 525, // "CONFIG_DIR_PCRE_MATCH_LIMIT_RECURSION"
    TOK_CONFIG_SEC_CONN_R_STATE_LIMIT = 526, // "CONFIG_SEC_CONN_R_STATE_LIMIT"
    TOK_CONFIG_SEC_CONN_W_STATE_LIMIT = 527, // "CONFIG_SEC_CONN_W_STATE_LIMIT"
    TOK_CONFIG_SEC_SENSOR_ID = 528, // "CONFIG_SEC_SENSOR_ID"
    TOK_CONFIG_DIR_ARGS_LIMIT = 529, // "CONFIG_DIR_ARGS_LIMIT"
    TOK_CONFIG_DIR_REQ_BODY_JSON_DEPTH_LIMIT = 530, // "CONFIG_DIR_REQ_BODY_JSON_DEPTH_LIMIT"
    TOK_CONFIG_DIR_REQ_BODY = 531, // "CONFIG_DIR_REQ_BODY"
    TOK_CONFIG_DIR_REQ_BODY_IN_MEMORY_LIMIT = 532, // "CONFIG_DIR_REQ_BODY_IN_MEMORY_LIMIT"
    TOK_CONFIG_DIR_REQ_BODY_LIMIT = 533, // "CONFIG_DIR_REQ_BODY_LIMIT"
    TOK_CONFIG_DIR_REQ_BODY_LIMIT_ACTION = 534, // "CONFIG_DIR_REQ_BODY_LIMIT_ACTION"
    TOK_CONFIG_DIR_REQ_BODY_NO_FILES_LIMIT = 535, // "CONFIG_DIR_REQ_BODY_NO_FILES_LIMIT"
    TOK_CONFIG_DIR_RES_BODY = 536, // "CONFIG_DIR_RES_BODY"
    TOK_CONFIG_DIR_RES_BODY_LIMIT = 537, // "CONFIG_DIR_RES_BODY_LIMIT"
    TOK_CONFIG_DIR_RES_BODY_LIMIT_ACTION = 538, // "CONFIG_DIR_RES_BODY_LIMIT_ACTION"
    TOK_CONFIG_SEC_RULE_INHERITANCE = 539, // "CONFIG_SEC_RULE_INHERITANCE"
    TOK_CONFIG_SEC_RULE_PERF_TIME = 540, // "CONFIG_SEC_RULE_PERF_TIME"
    TOK_CONFIG_DIR_RULE_ENG = 541, // "CONFIG_DIR_RULE_ENG"
    TOK_CONFIG_DIR_SEC_ACTION = 542, // "CONFIG_DIR_SEC_ACTION"
    TOK_CONFIG_DIR_SEC_DEFAULT_ACTION = 543, // "CONFIG_DIR_SEC_DEFAULT_ACTION"
    TOK_CONFIG_DIR_SEC_MARKER = 544, // "CONFIG_DIR_SEC_MARKER"
    TOK_CONFIG_DIR_UNICODE_MAP_FILE = 545, // "CONFIG_DIR_UNICODE_MAP_FILE"
    TOK_CONFIG_DIR_UNICODE_CODE_PAGE = 546, // "CONFIG_DIR_UNICODE_CODE_PAGE"
    TOK_CONFIG_SEC_COLLECTION_TIMEOUT = 547, // "CONFIG_SEC_COLLECTION_TIMEOUT"
    TOK_CONFIG_SEC_HTTP_BLKEY = 548, // "CONFIG_SEC_HTTP_BLKEY"
    TOK_CONFIG_SEC_INTERCEPT_ON_ERROR = 549, // "CONFIG_SEC_INTERCEPT_ON_ERROR"
    TOK_CONFIG_SEC_REMOTE_RULES_FAIL_ACTION = 550, // "CONFIG_SEC_REMOTE_RULES_FAIL_ACTION"
    TOK_CONFIG_SEC_RULE_REMOVE_BY_ID = 551, // "CONFIG_SEC_RULE_REMOVE_BY_ID"
    TOK_CONFIG_SEC_RULE_REMOVE_BY_MSG = 552, // "CONFIG_SEC_RULE_REMOVE_BY_MSG"
    TOK_CONFIG_SEC_RULE_REMOVE_BY_TAG = 553, // "CONFIG_SEC_RULE_REMOVE_BY_TAG"
    TOK_CONFIG_SEC_RULE_UPDATE_TARGET_BY_TAG = 554, // "CONFIG_SEC_RULE_UPDATE_TARGET_BY_TAG"
    TOK_CONFIG_SEC_RULE_UPDATE_TARGET_BY_MSG = 555, // "CONFIG_SEC_RULE_UPDATE_TARGET_BY_MSG"
    TOK_CONFIG_SEC_RULE_UPDATE_TARGET_BY_ID = 556, // "CONFIG_SEC_RULE_UPDATE_TARGET_BY_ID"
    TOK_CONFIG_SEC_RULE_UPDATE_ACTION_BY_ID = 557, // "CONFIG_SEC_RULE_UPDATE_ACTION_BY_ID"
    TOK_CONFIG_UPDLOAD_KEEP_FILES = 558, // "CONFIG_UPDLOAD_KEEP_FILES"
    TOK_CONFIG_UPDLOAD_SAVE_TMP_FILES = 559, // "CONFIG_UPDLOAD_SAVE_TMP_FILES"
    TOK_CONFIG_UPLOAD_DIR = 560,   // "CONFIG_UPLOAD_DIR"
    TOK_CONFIG_UPLOAD_FILE_LIMIT = 561, // "CONFIG_UPLOAD_FILE_LIMIT"
    TOK_CONFIG_UPLOAD_FILE_MODE = 562, // "CONFIG_UPLOAD_FILE_MODE"
    TOK_CONFIG_VALUE_ABORT = 563,  // "CONFIG_VALUE_ABORT"
    TOK_CONFIG_VALUE_DETC = 564,   // "CONFIG_VALUE_DETC"
    TOK_CONFIG_VALUE_HTTPS = 565,  // "CONFIG_VALUE_HTTPS"
    TOK_CONFIG_VALUE_ONLYARGS = 566, // "CONFIG_VALUE_ONLYARGS"
    TOK_CONFIG_VALUE_OFF = 567,    // "CONFIG_VALUE_OFF"
    TOK_CONFIG_VALUE_ON = 568,     // "CONFIG_VALUE_ON"
    TOK_CONFIG_VALUE_PARALLEL = 569, // "CONFIG_VALUE_PARALLEL"
    TOK_CONFIG_VALUE_PROCESS_PARTIAL = 570, // "CONFIG_VALUE_PROCESS_PARTIAL"
    TOK_CONFIG_VALUE_REJECT = 571, // "CONFIG_VALUE_REJECT"
    TOK_CONFIG_VALUE_RELEVANT_ONLY = 572, // "CONFIG_VALUE_RELEVANT_ONLY"
    TOK_CONFIG_VALUE_SERIAL = 573, // "CONFIG_VALUE_SERIAL"
    TOK_CONFIG_VALUE_WARN = 574,   // "CONFIG_VALUE_WARN"
    TOK_CONFIG_XML_EXTERNAL_ENTITY = 575, // "CONFIG_XML_EXTERNAL_ENTITY"
    TOK_CONFIG_XML_PARSE_XML_INTO_ARGS = 576, // "CONFIG_XML_PARSE_XML_INTO_ARGS"
    TOK_CONGIG_DIR_RESPONSE_BODY_MP = 577, // "CONGIG_DIR_RESPONSE_BODY_MP"
    TOK_CONGIG_DIR_SEC_ARG_SEP = 578, // "CONGIG_DIR_SEC_ARG_SEP"
    TOK_CONGIG_DIR_SEC_COOKIE_FORMAT = 579, // "CONGIG_DIR_SEC_COOKIE_FORMAT"
    TOK_CONFIG_SEC_COOKIEV0_SEPARATOR = 580, // "CONFIG_SEC_COOKIEV0_SEPARATOR"
    TOK_CONGIG_DIR_SEC_DATA_DIR = 581, // "CONGIG_DIR_SEC_DATA_DIR"
    TOK_CONGIG_DIR_SEC_STATUS_ENGINE = 582, // "CONGIG_DIR_SEC_STATUS_ENGINE"
    TOK_CONFIG_SEC_STREAM_IN_BODY_INSPECTION = 583, // "CONFIG_SEC_STREAM_IN_BODY_INSPECTION"
    TOK_CONFIG_SEC_STREAM_OUT_BODY_INSPECTION = 584, // "CONFIG_SEC_STREAM_OUT_BODY_INSPECTION"
    TOK_CONGIG_DIR_SEC_TMP_DIR = 585, // "CONGIG_DIR_SEC_TMP_DIR"
    TOK_DIRECTIVE = 586,           // "DIRECTIVE"
    TOK_DIRECTIVE_SECRULESCRIPT = 587, // "DIRECTIVE_SECRULESCRIPT"
    TOK_FREE_TEXT_QUOTE_MACRO_EXPANSION = 588, // "FREE_TEXT_QUOTE_MACRO_EXPANSION"
    TOK_QUOTATION_MARK = 589,      // "QUOTATION_MARK"
    TOK_RUN_TIME_VAR_BLD = 590,    // "RUN_TIME_VAR_BLD"
    TOK_RUN_TIME_VAR_DUR = 591,    // "RUN_TIME_VAR_DUR"
    TOK_RUN_TIME_VAR_HSV = 592,    // "RUN_TIME_VAR_HSV"
    TOK_RUN_TIME_VAR_REMOTE_USER = 593, // "RUN_TIME_VAR_REMOTE_USER"
    TOK_RUN_TIME_VAR_TIME = 594,   // "RUN_TIME_VAR_TIME"
    TOK_RUN_TIME_VAR_TIME_DAY = 595, // "RUN_TIME_VAR_TIME_DAY"
    TOK_RUN_TIME_VAR_TIME_EPOCH = 596, // "RUN_TIME_VAR_TIME_EPOCH"
    TOK_RUN_TIME_VAR_TIME_HOUR = 597, // "RUN_TIME_VAR_TIME_HOUR"
    TOK_RUN_TIME_VAR_TIME_MIN = 598, // "RUN_TIME_VAR_TIME_MIN"
    TOK_RUN_TIME_VAR_TIME_MON = 599, // "RUN_TIME_VAR_TIME_MON"
    TOK_RUN_TIME_VAR_TIME_SEC = 600, // "RUN_TIME_VAR_TIME_SEC"
    TOK_RUN_TIME_VAR_TIME_WDAY = 601, // "RUN_TIME_VAR_TIME_WDAY"
    TOK_RUN_TIME_VAR_TIME_YEAR = 602, // "RUN_TIME_VAR_TIME_YEAR"
    TOK_VARIABLE = 603,            // "VARIABLE"
    TOK_DICT_ELEMENT = 604,        // "Dictionary element"
    TOK_DICT_ELEMENT_WITH_EQUALS = 605, // "Dictionary element, with equals"
    TOK_DICT_ELEMENT_REGEXP = 606  // "Dictionary element, selected by regexp"
      };
      /// Backward compatibility alias (Bison 3.6).
      typedef token_kind_type yytokentype;
    };

    /// Token kind, as returned by yylex.
    typedef token::token_kind_type token_kind_type;

    /// Backward compatibility alias (Bison 3.6).
    typedef token_kind_type token_type;

    /// Symbol kinds.
    struct symbol_kind
    {
      enum symbol_kind_type
      {
        YYNTOKENS = 352, ///< Number of tokens.
        S_YYEMPTY = -2,
        S_YYEOF = 0,                             // "end of file"
        S_YYerror = 1,                           // error
        S_YYUNDEF = 2,                           // "invalid token"
        S_COMMA = 3,                             // ","
        S_CONFIG_CONTENT_INJECTION = 4,          // "CONFIG_CONTENT_INJECTION"
        S_CONGIG_DIR_RESPONSE_BODY_MP_CLEAR = 5, // "CONGIG_DIR_RESPONSE_BODY_MP_CLEAR"
        S_PIPE = 6,                              // PIPE
        S_NEW_LINE = 7,                          // NEW_LINE
        S_VAR_COUNT = 8,                         // VAR_COUNT
        S_VAR_EXCLUSION = 9,                     // VAR_EXCLUSION
        S_VARIABLE_ARGS = 10,                    // VARIABLE_ARGS
        S_VARIABLE_ARGS_POST = 11,               // VARIABLE_ARGS_POST
        S_VARIABLE_ARGS_GET = 12,                // VARIABLE_ARGS_GET
        S_VARIABLE_FILES_SIZES = 13,             // VARIABLE_FILES_SIZES
        S_VARIABLE_FILES_NAMES = 14,             // VARIABLE_FILES_NAMES
        S_VARIABLE_FILES_TMP_CONTENT = 15,       // VARIABLE_FILES_TMP_CONTENT
        S_VARIABLE_MULTIPART_FILENAME = 16,      // VARIABLE_MULTIPART_FILENAME
        S_VARIABLE_MULTIPART_NAME = 17,          // VARIABLE_MULTIPART_NAME
        S_VARIABLE_MATCHED_VARS_NAMES = 18,      // VARIABLE_MATCHED_VARS_NAMES
        S_VARIABLE_MATCHED_VARS = 19,            // VARIABLE_MATCHED_VARS
        S_VARIABLE_FILES = 20,                   // VARIABLE_FILES
        S_VARIABLE_REQUEST_COOKIES = 21,         // VARIABLE_REQUEST_COOKIES
        S_VARIABLE_REQUEST_HEADERS = 22,         // VARIABLE_REQUEST_HEADERS
        S_VARIABLE_RESPONSE_HEADERS = 23,        // VARIABLE_RESPONSE_HEADERS
        S_VARIABLE_GEO = 24,                     // VARIABLE_GEO
        S_VARIABLE_REQUEST_COOKIES_NAMES = 25,   // VARIABLE_REQUEST_COOKIES_NAMES
        S_VARIABLE_MULTIPART_PART_HEADERS = 26,  // VARIABLE_MULTIPART_PART_HEADERS
        S_VARIABLE_ARGS_COMBINED_SIZE = 27,      // VARIABLE_ARGS_COMBINED_SIZE
        S_VARIABLE_ARGS_GET_NAMES = 28,          // VARIABLE_ARGS_GET_NAMES
        S_VARIABLE_RULE = 29,                    // VARIABLE_RULE
        S_VARIABLE_ARGS_NAMES = 30,              // "Variable ARGS_NAMES"
        S_VARIABLE_ARGS_POST_NAMES = 31,         // VARIABLE_ARGS_POST_NAMES
        S_VARIABLE_AUTH_TYPE = 32,               // "AUTH_TYPE"
        S_VARIABLE_FILES_COMBINED_SIZE = 33,     // "FILES_COMBINED_SIZE"
        S_VARIABLE_FILES_TMP_NAMES = 34,         // "FILES_TMPNAMES"
        S_VARIABLE_FULL_REQUEST = 35,            // "FULL_REQUEST"
        S_VARIABLE_FULL_REQUEST_LENGTH = 36,     // "FULL_REQUEST_LENGTH"
        S_VARIABLE_INBOUND_DATA_ERROR = 37,      // "INBOUND_DATA_ERROR"
        S_VARIABLE_MATCHED_VAR = 38,             // "MATCHED_VAR"
        S_VARIABLE_MATCHED_VAR_NAME = 39,        // "MATCHED_VAR_NAME"
        S_VARIABLE_MSC_PCRE_ERROR = 40,          // "MSC_PCRE_ERROR"
        S_VARIABLE_MSC_PCRE_LIMITS_EXCEEDED = 41, // "MSC_PCRE_LIMITS_EXCEEDED"
        S_VARIABLE_MULTIPART_BOUNDARY_QUOTED = 42, // VARIABLE_MULTIPART_BOUNDARY_QUOTED
        S_VARIABLE_MULTIPART_BOUNDARY_WHITESPACE = 43, // VARIABLE_MULTIPART_BOUNDARY_WHITESPACE
        S_VARIABLE_MULTIPART_CRLF_LF_LINES = 44, // "MULTIPART_CRLF_LF_LINES"
        S_VARIABLE_MULTIPART_DATA_AFTER = 45,    // "MULTIPART_DATA_AFTER"
        S_VARIABLE_MULTIPART_DATA_BEFORE = 46,   // VARIABLE_MULTIPART_DATA_BEFORE
        S_VARIABLE_MULTIPART_FILE_LIMIT_EXCEEDED = 47, // "MULTIPART_FILE_LIMIT_EXCEEDED"
        S_VARIABLE_MULTIPART_HEADER_FOLDING = 48, // "MULTIPART_HEADER_FOLDING"
        S_VARIABLE_MULTIPART_INVALID_HEADER_FOLDING = 49, // "MULTIPART_INVALID_HEADER_FOLDING"
        S_VARIABLE_MULTIPART_INVALID_PART = 50,  // VARIABLE_MULTIPART_INVALID_PART
        S_VARIABLE_MULTIPART_INVALID_QUOTING = 51, // "MULTIPART_INVALID_QUOTING"
        S_VARIABLE_MULTIPART_LF_LINE = 52,       // VARIABLE_MULTIPART_LF_LINE
        S_VARIABLE_MULTIPART_MISSING_SEMICOLON = 53, // VARIABLE_MULTIPART_MISSING_SEMICOLON
        S_VARIABLE_MULTIPART_SEMICOLON_MISSING = 54, // VARIABLE_MULTIPART_SEMICOLON_MISSING
        S_VARIABLE_MULTIPART_STRICT_ERROR = 55,  // "MULTIPART_STRICT_ERROR"
        S_VARIABLE_MULTIPART_UNMATCHED_BOUNDARY = 56, // "MULTIPART_UNMATCHED_BOUNDARY"
        S_VARIABLE_OUTBOUND_DATA_ERROR = 57,     // "OUTBOUND_DATA_ERROR"
        S_VARIABLE_PATH_INFO = 58,               // "PATH_INFO"
        S_VARIABLE_QUERY_STRING = 59,            // "QUERY_STRING"
        S_VARIABLE_REMOTE_ADDR = 60,             // "REMOTE_ADDR"
        S_VARIABLE_REMOTE_HOST = 61,             // "REMOTE_HOST"
        S_VARIABLE_REMOTE_PORT = 62,             // "REMOTE_PORT"
        S_VARIABLE_REQBODY_ERROR_MSG = 63,       // "REQBODY_ERROR_MSG"
        S_VARIABLE_REQBODY_ERROR = 64,           // "REQBODY_ERROR"
        S_VARIABLE_REQBODY_PROCESSOR_ERROR_MSG = 65, // "REQBODY_PROCESSOR_ERROR_MSG"
        S_VARIABLE_REQBODY_PROCESSOR_ERROR = 66, // "REQBODY_PROCESSOR_ERROR"
        S_VARIABLE_REQBODY_PROCESSOR = 67,       // "REQBODY_PROCESSOR"
        S_VARIABLE_REQUEST_BASENAME = 68,        // "REQUEST_BASENAME"
        S_VARIABLE_REQUEST_BODY_LENGTH = 69,     // "REQUEST_BODY_LENGTH"
        S_VARIABLE_REQUEST_BODY = 70,            // "REQUEST_BODY"
        S_VARIABLE_REQUEST_FILE_NAME = 71,       // "REQUEST_FILENAME"
        S_VARIABLE_REQUEST_HEADERS_NAMES = 72,   // VARIABLE_REQUEST_HEADERS_NAMES
        S_VARIABLE_REQUEST_LINE = 73,            // "REQUEST_LINE"
        S_VARIABLE_REQUEST_METHOD = 74,          // "REQUEST_METHOD"
        S_VARIABLE_REQUEST_PROTOCOL = 75,        // "REQUEST_PROTOCOL"
        S_VARIABLE_REQUEST_URI_RAW = 76,         // "REQUEST_URI_RAW"
        S_VARIABLE_REQUEST_URI = 77,             // "REQUEST_URI"
        S_VARIABLE_RESOURCE = 78,                // "RESOURCE"
        S_VARIABLE_RESPONSE_BODY = 79,           // "RESPONSE_BODY"
        S_VARIABLE_RESPONSE_CONTENT_LENGTH = 80, // "RESPONSE_CONTENT_LENGTH"
        S_VARIABLE_RESPONSE_CONTENT_TYPE = 81,   // VARIABLE_RESPONSE_CONTENT_TYPE
        S_VARIABLE_RESPONSE_HEADERS_NAMES = 82,  // VARIABLE_RESPONSE_HEADERS_NAMES
        S_VARIABLE_RESPONSE_PROTOCOL = 83,       // "RESPONSE_PROTOCOL"
        S_VARIABLE_RESPONSE_STATUS = 84,         // "RESPONSE_STATUS"
        S_VARIABLE_SERVER_ADDR = 85,             // "SERVER_ADDR"
        S_VARIABLE_SERVER_NAME = 86,             // "SERVER_NAME"
        S_VARIABLE_SERVER_PORT = 87,             // "SERVER_PORT"
        S_VARIABLE_SESSION_ID = 88,              // "SESSIONID"
        S_VARIABLE_UNIQUE_ID = 89,               // "UNIQUE_ID"
        S_VARIABLE_URL_ENCODED_ERROR = 90,       // "URLENCODED_ERROR"
        S_VARIABLE_USER_ID = 91,                 // "USERID"
        S_VARIABLE_WEB_APP_ID = 92,              // "WEBAPPID"
        S_VARIABLE_STATUS = 93,                  // "VARIABLE_STATUS"
        S_VARIABLE_STATUS_LINE = 94,             // "VARIABLE_STATUS_LINE"
        S_VARIABLE_IP = 95,                      // "VARIABLE_IP"
        S_VARIABLE_GLOBAL = 96,                  // "VARIABLE_GLOBAL"
        S_VARIABLE_TX = 97,                      // "VARIABLE_TX"
        S_VARIABLE_SESSION = 98,                 // "VARIABLE_SESSION"
        S_VARIABLE_USER = 99,                    // "VARIABLE_USER"
        S_RUN_TIME_VAR_ENV = 100,                // "RUN_TIME_VAR_ENV"
        S_RUN_TIME_VAR_XML = 101,                // "RUN_TIME_VAR_XML"
        S_ACTION_SETVAR = 102,                   // "SetVar"
        S_SETVAR_OPERATION_EQUALS = 103,         // SETVAR_OPERATION_EQUALS
        S_SETVAR_OPERATION_EQUALS_PLUS = 104,    // SETVAR_OPERATION_EQUALS_PLUS
        S_SETVAR_OPERATION_EQUALS_MINUS = 105,   // SETVAR_OPERATION_EQUALS_MINUS
        S_NOT = 106,                             // "NOT"
        S_OPERATOR_BEGINS_WITH = 107,            // "OPERATOR_BEGINS_WITH"
        S_OPERATOR_CONTAINS = 108,               // "OPERATOR_CONTAINS"
        S_OPERATOR_CONTAINS_WORD = 109,          // "OPERATOR_CONTAINS_WORD"
        S_OPERATOR_DETECT_SQLI = 110,            // "OPERATOR_DETECT_SQLI"
        S_OPERATOR_DETECT_XSS = 111,             // "OPERATOR_DETECT_XSS"
        S_OPERATOR_ENDS_WITH = 112,              // "OPERATOR_ENDS_WITH"
        S_OPERATOR_EQ = 113,                     // "OPERATOR_EQ"
        S_OPERATOR_FUZZY_HASH = 114,             // "OPERATOR_FUZZY_HASH"
        S_OPERATOR_GEOLOOKUP = 115,              // "OPERATOR_GEOLOOKUP"
        S_OPERATOR_GE = 116,                     // "OPERATOR_GE"
        S_OPERATOR_GSB_LOOKUP = 117,             // "OPERATOR_GSB_LOOKUP"
        S_OPERATOR_GT = 118,                     // "OPERATOR_GT"
        S_OPERATOR_INSPECT_FILE = 119,           // "OPERATOR_INSPECT_FILE"
        S_OPERATOR_IP_MATCH_FROM_FILE = 120,     // "OPERATOR_IP_MATCH_FROM_FILE"
        S_OPERATOR_IP_MATCH = 121,               // "OPERATOR_IP_MATCH"
        S_OPERATOR_LE = 122,                     // "OPERATOR_LE"
        S_OPERATOR_LT = 123,                     // "OPERATOR_LT"
        S_OPERATOR_PM_FROM_FILE = 124,           // "OPERATOR_PM_FROM_FILE"
        S_OPERATOR_PM = 125,                     // "OPERATOR_PM"
        S_OPERATOR_RBL = 126,                    // "OPERATOR_RBL"
        S_OPERATOR_RSUB = 127,                   // "OPERATOR_RSUB"
        S_OPERATOR_RX_CONTENT_ONLY = 128,        // "Operator RX (content only)"
        S_OPERATOR_RX = 129,                     // "OPERATOR_RX"
        S_OPERATOR_RX_GLOBAL = 130,              // "OPERATOR_RX_GLOBAL"
        S_OPERATOR_STR_EQ = 131,                 // "OPERATOR_STR_EQ"
        S_OPERATOR_STR_MATCH = 132,              // "OPERATOR_STR_MATCH"
        S_OPERATOR_UNCONDITIONAL_MATCH = 133,    // "OPERATOR_UNCONDITIONAL_MATCH"
        S_OPERATOR_VALIDATE_BYTE_RANGE = 134,    // "OPERATOR_VALIDATE_BYTE_RANGE"
        S_OPERATOR_VALIDATE_DTD = 135,           // "OPERATOR_VALIDATE_DTD"
        S_OPERATOR_VALIDATE_HASH = 136,          // "OPERATOR_VALIDATE_HASH"
        S_OPERATOR_VALIDATE_SCHEMA = 137,        // "OPERATOR_VALIDATE_SCHEMA"
        S_OPERATOR_VALIDATE_URL_ENCODING = 138,  // "OPERATOR_VALIDATE_URL_ENCODING"
        S_OPERATOR_VALIDATE_UTF8_ENCODING = 139, // "OPERATOR_VALIDATE_UTF8_ENCODING"
        S_OPERATOR_VERIFY_CC = 140,              // "OPERATOR_VERIFY_CC"
        S_OPERATOR_VERIFY_CPF = 141,             // "OPERATOR_VERIFY_CPF"
        S_OPERATOR_VERIFY_SSN = 142,             // "OPERATOR_VERIFY_SSN"
        S_OPERATOR_VERIFY_SVNR = 143,            // "OPERATOR_VERIFY_SVNR"
        S_OPERATOR_WITHIN = 144,                 // "OPERATOR_WITHIN"
        S_CONFIG_DIR_AUDIT_LOG_FMT = 145,        // CONFIG_DIR_AUDIT_LOG_FMT
        S_JSON = 146,                            // JSON
        S_NATIVE = 147,                          // NATIVE
        S_ACTION_CTL_RULE_ENGINE = 148,          // "ACTION_CTL_RULE_ENGINE"
        S_ACTION_ACCURACY = 149,                 // "Accuracy"
        S_ACTION_ALLOW = 150,                    // "Allow"
        S_ACTION_APPEND = 151,                   // "Append"
        S_ACTION_AUDIT_LOG = 152,                // "AuditLog"
        S_ACTION_BLOCK = 153,                    // "Block"
        S_ACTION_CAPTURE = 154,                  // "Capture"
        S_ACTION_CHAIN = 155,                    // "Chain"
        S_ACTION_CTL_AUDIT_ENGINE = 156,         // "ACTION_CTL_AUDIT_ENGINE"
        S_ACTION_CTL_AUDIT_LOG_PARTS = 157,      // "ACTION_CTL_AUDIT_LOG_PARTS"
        S_ACTION_CTL_BDY_JSON = 158,             // "ACTION_CTL_BDY_JSON"
        S_ACTION_CTL_BDY_XML = 159,              // "ACTION_CTL_BDY_XML"
        S_ACTION_CTL_BDY_URLENCODED = 160,       // "ACTION_CTL_BDY_URLENCODED"
        S_ACTION_CTL_FORCE_REQ_BODY_VAR = 161,   // "ACTION_CTL_FORCE_REQ_BODY_VAR"
        S_ACTION_CTL_PARSE_XML_INTO_ARGS = 162,  // "ACTION_CTL_PARSE_XML_INTO_ARGS"
        S_ACTION_CTL_REQUEST_BODY_ACCESS = 163,  // "ACTION_CTL_REQUEST_BODY_ACCESS"
        S_ACTION_CTL_RULE_REMOVE_BY_ID = 164,    // "ACTION_CTL_RULE_REMOVE_BY_ID"
        S_ACTION_CTL_RULE_REMOVE_BY_TAG = 165,   // "ACTION_CTL_RULE_REMOVE_BY_TAG"
        S_ACTION_CTL_RULE_REMOVE_TARGET_BY_ID = 166, // "ACTION_CTL_RULE_REMOVE_TARGET_BY_ID"
        S_ACTION_CTL_RULE_REMOVE_TARGET_BY_TAG = 167, // "ACTION_CTL_RULE_REMOVE_TARGET_BY_TAG"
        S_ACTION_DENY = 168,                     // "Deny"
        S_ACTION_DEPRECATE_VAR = 169,            // "DeprecateVar"
        S_ACTION_DROP = 170,                     // "Drop"
        S_ACTION_EXEC = 171,                     // "Exec"
        S_ACTION_EXPIRE_VAR = 172,               // "ExpireVar"
        S_ACTION_ID = 173,                       // "Id"
        S_ACTION_INITCOL = 174,                  // "InitCol"
        S_ACTION_LOG = 175,                      // "Log"
        S_ACTION_LOG_DATA = 176,                 // "LogData"
        S_ACTION_MATURITY = 177,                 // "Maturity"
        S_ACTION_MSG = 178,                      // "Msg"
        S_ACTION_MULTI_MATCH = 179,              // "MultiMatch"
        S_ACTION_NO_AUDIT_LOG = 180,             // "NoAuditLog"
        S_ACTION_NO_LOG = 181,                   // "NoLog"
        S_ACTION_PASS = 182,                     // "Pass"
        S_ACTION_PAUSE = 183,                    // "Pause"
        S_ACTION_PHASE = 184,                    // "Phase"
        S_ACTION_PREPEND = 185,                  // "Prepend"
        S_ACTION_PROXY = 186,                    // "Proxy"
        S_ACTION_REDIRECT = 187,                 // "Redirect"
        S_ACTION_REV = 188,                      // "Rev"
        S_ACTION_SANITISE_ARG = 189,             // "SanitiseArg"
        S_ACTION_SANITISE_MATCHED = 190,         // "SanitiseMatched"
        S_ACTION_SANITISE_MATCHED_BYTES = 191,   // "SanitiseMatchedBytes"
        S_ACTION_SANITISE_REQUEST_HEADER = 192,  // "SanitiseRequestHeader"
        S_ACTION_SANITISE_RESPONSE_HEADER = 193, // "SanitiseResponseHeader"
        S_ACTION_SETENV = 194,                   // "SetEnv"
        S_ACTION_SETRSC = 195,                   // "SetRsc"
        S_ACTION_SETSID = 196,                   // "SetSid"
        S_ACTION_SETUID = 197,                   // "SetUID"
        S_ACTION_SEVERITY = 198,                 // "Severity"
        S_ACTION_SKIP = 199,                     // "Skip"
        S_ACTION_SKIP_AFTER = 200,               // "SkipAfter"
        S_ACTION_STATUS = 201,                   // "Status"
        S_ACTION_TAG = 202,                      // "Tag"
        S_ACTION_TRANSFORMATION_BASE_64_ENCODE = 203, // "ACTION_TRANSFORMATION_BASE_64_ENCODE"
        S_ACTION_TRANSFORMATION_BASE_64_DECODE = 204, // "ACTION_TRANSFORMATION_BASE_64_DECODE"
        S_ACTION_TRANSFORMATION_BASE_64_DECODE_EXT = 205, // "ACTION_TRANSFORMATION_BASE_64_DECODE_EXT"
        S_ACTION_TRANSFORMATION_CMD_LINE = 206,  // "ACTION_TRANSFORMATION_CMD_LINE"
        S_ACTION_TRANSFORMATION_COMPRESS_WHITESPACE = 207, // "ACTION_TRANSFORMATION_COMPRESS_WHITESPACE"
        S_ACTION_TRANSFORMATION_CSS_DECODE = 208, // "ACTION_TRANSFORMATION_CSS_DECODE"
        S_ACTION_TRANSFORMATION_ESCAPE_SEQ_DECODE = 209, // "ACTION_TRANSFORMATION_ESCAPE_SEQ_DECODE"
        S_ACTION_TRANSFORMATION_HEX_ENCODE = 210, // "ACTION_TRANSFORMATION_HEX_ENCODE"
        S_ACTION_TRANSFORMATION_HEX_DECODE = 211, // "ACTION_TRANSFORMATION_HEX_DECODE"
        S_ACTION_TRANSFORMATION_HTML_ENTITY_DECODE = 212, // "ACTION_TRANSFORMATION_HTML_ENTITY_DECODE"
        S_ACTION_TRANSFORMATION_JS_DECODE = 213, // "ACTION_TRANSFORMATION_JS_DECODE"
        S_ACTION_TRANSFORMATION_LENGTH = 214,    // "ACTION_TRANSFORMATION_LENGTH"
        S_ACTION_TRANSFORMATION_LOWERCASE = 215, // "ACTION_TRANSFORMATION_LOWERCASE"
        S_ACTION_TRANSFORMATION_MD5 = 216,       // "ACTION_TRANSFORMATION_MD5"
        S_ACTION_TRANSFORMATION_NONE = 217,      // "ACTION_TRANSFORMATION_NONE"
        S_ACTION_TRANSFORMATION_NORMALISE_PATH = 218, // "ACTION_TRANSFORMATION_NORMALISE_PATH"
        S_ACTION_TRANSFORMATION_NORMALISE_PATH_WIN = 219, // "ACTION_TRANSFORMATION_NORMALISE_PATH_WIN"
        S_ACTION_TRANSFORMATION_PARITY_EVEN_7_BIT = 220, // "ACTION_TRANSFORMATION_PARITY_EVEN_7_BIT"
        S_ACTION_TRANSFORMATION_PARITY_ODD_7_BIT = 221, // "ACTION_TRANSFORMATION_PARITY_ODD_7_BIT"
        S_ACTION_TRANSFORMATION_PARITY_ZERO_7_BIT = 222, // "ACTION_TRANSFORMATION_PARITY_ZERO_7_BIT"
        S_ACTION_TRANSFORMATION_REMOVE_COMMENTS = 223, // "ACTION_TRANSFORMATION_REMOVE_COMMENTS"
        S_ACTION_TRANSFORMATION_REMOVE_COMMENTS_CHAR = 224, // "ACTION_TRANSFORMATION_REMOVE_COMMENTS_CHAR"
        S_ACTION_TRANSFORMATION_REMOVE_NULLS = 225, // "ACTION_TRANSFORMATION_REMOVE_NULLS"
        S_ACTION_TRANSFORMATION_REMOVE_WHITESPACE = 226, // "ACTION_TRANSFORMATION_REMOVE_WHITESPACE"
        S_ACTION_TRANSFORMATION_REPLACE_COMMENTS = 227, // "ACTION_TRANSFORMATION_REPLACE_COMMENTS"
        S_ACTION_TRANSFORMATION_REPLACE_NULLS = 228, // "ACTION_TRANSFORMATION_REPLACE_NULLS"
        S_ACTION_TRANSFORMATION_SHA1 = 229,      // "ACTION_TRANSFORMATION_SHA1"
        S_ACTION_TRANSFORMATION_SQL_HEX_DECODE = 230, // "ACTION_TRANSFORMATION_SQL_HEX_DECODE"
        S_ACTION_TRANSFORMATION_TRIM = 231,      // "ACTION_TRANSFORMATION_TRIM"
        S_ACTION_TRANSFORMATION_TRIM_LEFT = 232, // "ACTION_TRANSFORMATION_TRIM_LEFT"
        S_ACTION_TRANSFORMATION_TRIM_RIGHT = 233, // "ACTION_TRANSFORMATION_TRIM_RIGHT"
        S_ACTION_TRANSFORMATION_UPPERCASE = 234, // "ACTION_TRANSFORMATION_UPPERCASE"
        S_ACTION_TRANSFORMATION_URL_ENCODE = 235, // "ACTION_TRANSFORMATION_URL_ENCODE"
        S_ACTION_TRANSFORMATION_URL_DECODE = 236, // "ACTION_TRANSFORMATION_URL_DECODE"
        S_ACTION_TRANSFORMATION_URL_DECODE_UNI = 237, // "ACTION_TRANSFORMATION_URL_DECODE_UNI"
        S_ACTION_TRANSFORMATION_UTF8_TO_UNICODE = 238, // "ACTION_TRANSFORMATION_UTF8_TO_UNICODE"
        S_ACTION_VER = 239,                      // "Ver"
        S_ACTION_XMLNS = 240,                    // "xmlns"
        S_CONFIG_COMPONENT_SIG = 241,            // "CONFIG_COMPONENT_SIG"
        S_CONFIG_CONN_ENGINE = 242,              // "CONFIG_CONN_ENGINE"
        S_CONFIG_SEC_ARGUMENT_SEPARATOR = 243,   // "CONFIG_SEC_ARGUMENT_SEPARATOR"
        S_CONFIG_SEC_WEB_APP_ID = 244,           // "CONFIG_SEC_WEB_APP_ID"
        S_CONFIG_SEC_SERVER_SIG = 245,           // "CONFIG_SEC_SERVER_SIG"
        S_CONFIG_DIR_AUDIT_DIR = 246,            // "CONFIG_DIR_AUDIT_DIR"
        S_CONFIG_DIR_AUDIT_DIR_MOD = 247,        // "CONFIG_DIR_AUDIT_DIR_MOD"
        S_CONFIG_DIR_AUDIT_ENG = 248,            // "CONFIG_DIR_AUDIT_ENG"
        S_CONFIG_DIR_AUDIT_FLE_MOD = 249,        // "CONFIG_DIR_AUDIT_FLE_MOD"
        S_CONFIG_DIR_AUDIT_LOG = 250,            // "CONFIG_DIR_AUDIT_LOG"
        S_CONFIG_DIR_AUDIT_LOG2 = 251,           // "CONFIG_DIR_AUDIT_LOG2"
        S_CONFIG_DIR_AUDIT_LOG_P = 252,          // "CONFIG_DIR_AUDIT_LOG_P"
        S_CONFIG_DIR_AUDIT_STS = 253,            // "CONFIG_DIR_AUDIT_STS"
        S_CONFIG_DIR_AUDIT_PREFIX = 254,         // "CONFIG_DIR_AUDIT_PREFIX"
        S_CONFIG_DIR_AUDIT_TPE = 255,            // "CONFIG_DIR_AUDIT_TPE"
        S_CONFIG_DIR_DEBUG_LOG = 256,            // "CONFIG_DIR_DEBUG_LOG"
        S_CONFIG_DIR_DEBUG_LVL = 257,            // "CONFIG_DIR_DEBUG_LVL"
        S_CONFIG_SEC_CACHE_TRANSFORMATIONS = 258, // "CONFIG_SEC_CACHE_TRANSFORMATIONS"
        S_CONFIG_SEC_DISABLE_BACKEND_COMPRESS = 259, // "CONFIG_SEC_DISABLE_BACKEND_COMPRESS"
        S_CONFIG_SEC_HASH_ENGINE = 260,          // "CONFIG_SEC_HASH_ENGINE"
        S_CONFIG_SEC_HASH_KEY = 261,             // "CONFIG_SEC_HASH_KEY"
        S_CONFIG_SEC_HASH_PARAM = 262,           // "CONFIG_SEC_HASH_PARAM"
        S_CONFIG_SEC_HASH_METHOD_RX = 263,       // "CONFIG_SEC_HASH_METHOD_RX"
        S_CONFIG_SEC_HASH_METHOD_PM = 264,       // "CONFIG_SEC_HASH_METHOD_PM"
        S_CONFIG_SEC_CHROOT_DIR = 265,           // "CONFIG_SEC_CHROOT_DIR"
        S_CONFIG_DIR_GEO_DB = 266,               // "CONFIG_DIR_GEO_DB"
        S_CONFIG_DIR_GSB_DB = 267,               // "CONFIG_DIR_GSB_DB"
        S_CONFIG_SEC_GUARDIAN_LOG = 268,         // "CONFIG_SEC_GUARDIAN_LOG"
        S_CONFIG_DIR_PCRE_MATCH_LIMIT = 269,     // "CONFIG_DIR_PCRE_MATCH_LIMIT"
        S_CONFIG_DIR_PCRE_MATCH_LIMIT_RECURSION = 270, // "CONFIG_DIR_PCRE_MATCH_LIMIT_RECURSION"
        S_CONFIG_SEC_CONN_R_STATE_LIMIT = 271,   // "CONFIG_SEC_CONN_R_STATE_LIMIT"
        S_CONFIG_SEC_CONN_W_STATE_LIMIT = 272,   // "CONFIG_SEC_CONN_W_STATE_LIMIT"
        S_CONFIG_SEC_SENSOR_ID = 273,            // "CONFIG_SEC_SENSOR_ID"
        S_CONFIG_DIR_ARGS_LIMIT = 274,           // "CONFIG_DIR_ARGS_LIMIT"
        S_CONFIG_DIR_REQ_BODY_JSON_DEPTH_LIMIT = 275, // "CONFIG_DIR_REQ_BODY_JSON_DEPTH_LIMIT"
        S_CONFIG_DIR_REQ_BODY = 276,             // "CONFIG_DIR_REQ_BODY"
        S_CONFIG_DIR_REQ_BODY_IN_MEMORY_LIMIT = 277, // "CONFIG_DIR_REQ_BODY_IN_MEMORY_LIMIT"
        S_CONFIG_DIR_REQ_BODY_LIMIT = 278,       // "CONFIG_DIR_REQ_BODY_LIMIT"
        S_CONFIG_DIR_REQ_BODY_LIMIT_ACTION = 279, // "CONFIG_DIR_REQ_BODY_LIMIT_ACTION"
        S_CONFIG_DIR_REQ_BODY_NO_FILES_LIMIT = 280, // "CONFIG_DIR_REQ_BODY_NO_FILES_LIMIT"
        S_CONFIG_DIR_RES_BODY = 281,             // "CONFIG_DIR_RES_BODY"
        S_CONFIG_DIR_RES_BODY_LIMIT = 282,       // "CONFIG_DIR_RES_BODY_LIMIT"
        S_CONFIG_DIR_RES_BODY_LIMIT_ACTION = 283, // "CONFIG_DIR_RES_BODY_LIMIT_ACTION"
        S_CONFIG_SEC_RULE_INHERITANCE = 284,     // "CONFIG_SEC_RULE_INHERITANCE"
        S_CONFIG_SEC_RULE_PERF_TIME = 285,       // "CONFIG_SEC_RULE_PERF_TIME"
        S_CONFIG_DIR_RULE_ENG = 286,             // "CONFIG_DIR_RULE_ENG"
        S_CONFIG_DIR_SEC_ACTION = 287,           // "CONFIG_DIR_SEC_ACTION"
        S_CONFIG_DIR_SEC_DEFAULT_ACTION = 288,   // "CONFIG_DIR_SEC_DEFAULT_ACTION"
        S_CONFIG_DIR_SEC_MARKER = 289,           // "CONFIG_DIR_SEC_MARKER"
        S_CONFIG_DIR_UNICODE_MAP_FILE = 290,     // "CONFIG_DIR_UNICODE_MAP_FILE"
        S_CONFIG_DIR_UNICODE_CODE_PAGE = 291,    // "CONFIG_DIR_UNICODE_CODE_PAGE"
        S_CONFIG_SEC_COLLECTION_TIMEOUT = 292,   // "CONFIG_SEC_COLLECTION_TIMEOUT"
        S_CONFIG_SEC_HTTP_BLKEY = 293,           // "CONFIG_SEC_HTTP_BLKEY"
        S_CONFIG_SEC_INTERCEPT_ON_ERROR = 294,   // "CONFIG_SEC_INTERCEPT_ON_ERROR"
        S_CONFIG_SEC_REMOTE_RULES_FAIL_ACTION = 295, // "CONFIG_SEC_REMOTE_RULES_FAIL_ACTION"
        S_CONFIG_SEC_RULE_REMOVE_BY_ID = 296,    // "CONFIG_SEC_RULE_REMOVE_BY_ID"
        S_CONFIG_SEC_RULE_REMOVE_BY_MSG = 297,   // "CONFIG_SEC_RULE_REMOVE_BY_MSG"
        S_CONFIG_SEC_RULE_REMOVE_BY_TAG = 298,   // "CONFIG_SEC_RULE_REMOVE_BY_TAG"
        S_CONFIG_SEC_RULE_UPDATE_TARGET_BY_TAG = 299, // "CONFIG_SEC_RULE_UPDATE_TARGET_BY_TAG"
        S_CONFIG_SEC_RULE_UPDATE_TARGET_BY_MSG = 300, // "CONFIG_SEC_RULE_UPDATE_TARGET_BY_MSG"
        S_CONFIG_SEC_RULE_UPDATE_TARGET_BY_ID = 301, // "CONFIG_SEC_RULE_UPDATE_TARGET_BY_ID"
        S_CONFIG_SEC_RULE_UPDATE_ACTION_BY_ID = 302, // "CONFIG_SEC_RULE_UPDATE_ACTION_BY_ID"
        S_CONFIG_UPDLOAD_KEEP_FILES = 303,       // "CONFIG_UPDLOAD_KEEP_FILES"
        S_CONFIG_UPDLOAD_SAVE_TMP_FILES = 304,   // "CONFIG_UPDLOAD_SAVE_TMP_FILES"
        S_CONFIG_UPLOAD_DIR = 305,               // "CONFIG_UPLOAD_DIR"
        S_CONFIG_UPLOAD_FILE_LIMIT = 306,        // "CONFIG_UPLOAD_FILE_LIMIT"
        S_CONFIG_UPLOAD_FILE_MODE = 307,         // "CONFIG_UPLOAD_FILE_MODE"
        S_CONFIG_VALUE_ABORT = 308,              // "CONFIG_VALUE_ABORT"
        S_CONFIG_VALUE_DETC = 309,               // "CONFIG_VALUE_DETC"
        S_CONFIG_VALUE_HTTPS = 310,              // "CONFIG_VALUE_HTTPS"
        S_CONFIG_VALUE_ONLYARGS = 311,           // "CONFIG_VALUE_ONLYARGS"
        S_CONFIG_VALUE_OFF = 312,                // "CONFIG_VALUE_OFF"
        S_CONFIG_VALUE_ON = 313,                 // "CONFIG_VALUE_ON"
        S_CONFIG_VALUE_PARALLEL = 314,           // "CONFIG_VALUE_PARALLEL"
        S_CONFIG_VALUE_PROCESS_PARTIAL = 315,    // "CONFIG_VALUE_PROCESS_PARTIAL"
        S_CONFIG_VALUE_REJECT = 316,             // "CONFIG_VALUE_REJECT"
        S_CONFIG_VALUE_RELEVANT_ONLY = 317,      // "CONFIG_VALUE_RELEVANT_ONLY"
        S_CONFIG_VALUE_SERIAL = 318,             // "CONFIG_VALUE_SERIAL"
        S_CONFIG_VALUE_WARN = 319,               // "CONFIG_VALUE_WARN"
        S_CONFIG_XML_EXTERNAL_ENTITY = 320,      // "CONFIG_XML_EXTERNAL_ENTITY"
        S_CONFIG_XML_PARSE_XML_INTO_ARGS = 321,  // "CONFIG_XML_PARSE_XML_INTO_ARGS"
        S_CONGIG_DIR_RESPONSE_BODY_MP = 322,     // "CONGIG_DIR_RESPONSE_BODY_MP"
        S_CONGIG_DIR_SEC_ARG_SEP = 323,          // "CONGIG_DIR_SEC_ARG_SEP"
        S_CONGIG_DIR_SEC_COOKIE_FORMAT = 324,    // "CONGIG_DIR_SEC_COOKIE_FORMAT"
        S_CONFIG_SEC_COOKIEV0_SEPARATOR = 325,   // "CONFIG_SEC_COOKIEV0_SEPARATOR"
        S_CONGIG_DIR_SEC_DATA_DIR = 326,         // "CONGIG_DIR_SEC_DATA_DIR"
        S_CONGIG_DIR_SEC_STATUS_ENGINE = 327,    // "CONGIG_DIR_SEC_STATUS_ENGINE"
        S_CONFIG_SEC_STREAM_IN_BODY_INSPECTION = 328, // "CONFIG_SEC_STREAM_IN_BODY_INSPECTION"
        S_CONFIG_SEC_STREAM_OUT_BODY_INSPECTION = 329, // "CONFIG_SEC_STREAM_OUT_BODY_INSPECTION"
        S_CONGIG_DIR_SEC_TMP_DIR = 330,          // "CONGIG_DIR_SEC_TMP_DIR"
        S_DIRECTIVE = 331,                       // "DIRECTIVE"
        S_DIRECTIVE_SECRULESCRIPT = 332,         // "DIRECTIVE_SECRULESCRIPT"
        S_FREE_TEXT_QUOTE_MACRO_EXPANSION = 333, // "FREE_TEXT_QUOTE_MACRO_EXPANSION"
        S_QUOTATION_MARK = 334,                  // "QUOTATION_MARK"
        S_RUN_TIME_VAR_BLD = 335,                // "RUN_TIME_VAR_BLD"
        S_RUN_TIME_VAR_DUR = 336,                // "RUN_TIME_VAR_DUR"
        S_RUN_TIME_VAR_HSV = 337,                // "RUN_TIME_VAR_HSV"
        S_RUN_TIME_VAR_REMOTE_USER = 338,        // "RUN_TIME_VAR_REMOTE_USER"
        S_RUN_TIME_VAR_TIME = 339,               // "RUN_TIME_VAR_TIME"
        S_RUN_TIME_VAR_TIME_DAY = 340,           // "RUN_TIME_VAR_TIME_DAY"
        S_RUN_TIME_VAR_TIME_EPOCH = 341,         // "RUN_TIME_VAR_TIME_EPOCH"
        S_RUN_TIME_VAR_TIME_HOUR = 342,          // "RUN_TIME_VAR_TIME_HOUR"
        S_RUN_TIME_VAR_TIME_MIN = 343,           // "RUN_TIME_VAR_TIME_MIN"
        S_RUN_TIME_VAR_TIME_MON = 344,           // "RUN_TIME_VAR_TIME_MON"
        S_RUN_TIME_VAR_TIME_SEC = 345,           // "RUN_TIME_VAR_TIME_SEC"
        S_RUN_TIME_VAR_TIME_WDAY = 346,          // "RUN_TIME_VAR_TIME_WDAY"
        S_RUN_TIME_VAR_TIME_YEAR = 347,          // "RUN_TIME_VAR_TIME_YEAR"
        S_VARIABLE = 348,                        // "VARIABLE"
        S_DICT_ELEMENT = 349,                    // "Dictionary element"
        S_DICT_ELEMENT_WITH_EQUALS = 350,        // "Dictionary element, with equals"
        S_DICT_ELEMENT_REGEXP = 351,             // "Dictionary element, selected by regexp"
        S_YYACCEPT = 352,                        // $accept
        S_input = 353,                           // input
        S_line = 354,                            // line
        S_audit_log = 355,                       // audit_log
        S_actions = 356,                         // actions
        S_actions_may_quoted = 357,              // actions_may_quoted
        S_op = 358,                              // op
        S_op_before_init = 359,                  // op_before_init
        S_expression = 360,                      // expression
        S_variables = 361,                       // variables
        S_variables_pre_process = 362,           // variables_pre_process
        S_variables_may_be_quoted = 363,         // variables_may_be_quoted
        S_var = 364,                             // var
        S_act = 365,                             // act
        S_setvar_action = 366,                   // setvar_action
        S_run_time_string = 367                  // run_time_string
      };
    };

    /// (Internal) symbol kind.
    typedef symbol_kind::symbol_kind_type symbol_kind_type;

    /// The number of tokens.
    static const symbol_kind_type YYNTOKENS = symbol_kind::YYNTOKENS;

    /// A complete symbol.
    ///
    /// Expects its Base type to provide access to the symbol kind
    /// via kind ().
    ///
    /// Provide access to semantic value and location.
    template <typename Base>
    struct basic_symbol : Base
    {
      /// Alias to Base.
      typedef Base super_type;

      /// Default constructor.
      basic_symbol () YY_NOEXCEPT
        : value ()
        , location ()
      {}

#if 201103L <= YY_CPLUSPLUS
      /// Move constructor.
      basic_symbol (basic_symbol&& that)
        : Base (std::move (that))
        , value ()
        , location (std::move (that.location))
      {
        switch (this->kind ())
    {
      case symbol_kind::S_ACTION_ACCURACY: // "Accuracy"
      case symbol_kind::S_ACTION_ALLOW: // "Allow"
      case symbol_kind::S_ACTION_APPEND: // "Append"
      case symbol_kind::S_ACTION_AUDIT_LOG: // "AuditLog"
      case symbol_kind::S_ACTION_BLOCK: // "Block"
      case symbol_kind::S_ACTION_CAPTURE: // "Capture"
      case symbol_kind::S_ACTION_CHAIN: // "Chain"
      case symbol_kind::S_ACTION_CTL_AUDIT_ENGINE: // "ACTION_CTL_AUDIT_ENGINE"
      case symbol_kind::S_ACTION_CTL_AUDIT_LOG_PARTS: // "ACTION_CTL_AUDIT_LOG_PARTS"
      case symbol_kind::S_ACTION_CTL_BDY_JSON: // "ACTION_CTL_BDY_JSON"
      case symbol_kind::S_ACTION_CTL_BDY_XML: // "ACTION_CTL_BDY_XML"
      case symbol_kind::S_ACTION_CTL_BDY_URLENCODED: // "ACTION_CTL_BDY_URLENCODED"
      case symbol_kind::S_ACTION_CTL_FORCE_REQ_BODY_VAR: // "ACTION_CTL_FORCE_REQ_BODY_VAR"
      case symbol_kind::S_ACTION_CTL_PARSE_XML_INTO_ARGS: // "ACTION_CTL_PARSE_XML_INTO_ARGS"
      case symbol_kind::S_ACTION_CTL_REQUEST_BODY_ACCESS: // "ACTION_CTL_REQUEST_BODY_ACCESS"
      case symbol_kind::S_ACTION_CTL_RULE_REMOVE_BY_ID: // "ACTION_CTL_RULE_REMOVE_BY_ID"
      case symbol_kind::S_ACTION_CTL_RULE_REMOVE_BY_TAG: // "ACTION_CTL_RULE_REMOVE_BY_TAG"
      case symbol_kind::S_ACTION_CTL_RULE_REMOVE_TARGET_BY_ID: // "ACTION_CTL_RULE_REMOVE_TARGET_BY_ID"
      case symbol_kind::S_ACTION_CTL_RULE_REMOVE_TARGET_BY_TAG: // "ACTION_CTL_RULE_REMOVE_TARGET_BY_TAG"
      case symbol_kind::S_ACTION_DENY: // "Deny"
      case symbol_kind::S_ACTION_DEPRECATE_VAR: // "DeprecateVar"
      case symbol_kind::S_ACTION_DROP: // "Drop"
      case symbol_kind::S_ACTION_EXEC: // "Exec"
      case symbol_kind::S_ACTION_EXPIRE_VAR: // "ExpireVar"
      case symbol_kind::S_ACTION_ID: // "Id"
      case symbol_kind::S_ACTION_INITCOL: // "InitCol"
      case symbol_kind::S_ACTION_LOG: // "Log"
      case symbol_kind::S_ACTION_LOG_DATA: // "LogData"
      case symbol_kind::S_ACTION_MATURITY: // "Maturity"
      case symbol_kind::S_ACTION_MSG: // "Msg"
      case symbol_kind::S_ACTION_MULTI_MATCH: // "MultiMatch"
      case symbol_kind::S_ACTION_NO_AUDIT_LOG: // "NoAuditLog"
      case symbol_kind::S_ACTION_NO_LOG: // "NoLog"
      case symbol_kind::S_ACTION_PASS: // "Pass"
      case symbol_kind::S_ACTION_PAUSE: // "Pause"
      case symbol_kind::S_ACTION_PHASE: // "Phase"
      case symbol_kind::S_ACTION_PREPEND: // "Prepend"
      case symbol_kind::S_ACTION_PROXY: // "Proxy"
      case symbol_kind::S_ACTION_REDIRECT: // "Redirect"
      case symbol_kind::S_ACTION_REV: // "Rev"
      case symbol_kind::S_ACTION_SANITISE_ARG: // "SanitiseArg"
      case symbol_kind::S_ACTION_SANITISE_MATCHED: // "SanitiseMatched"
      case symbol_kind::S_ACTION_SANITISE_MATCHED_BYTES: // "SanitiseMatchedBytes"
      case symbol_kind::S_ACTION_SANITISE_REQUEST_HEADER: // "SanitiseRequestHeader"
      case symbol_kind::S_ACTION_SANITISE_RESPONSE_HEADER: // "SanitiseResponseHeader"
      case symbol_kind::S_ACTION_SETENV: // "SetEnv"
      case symbol_kind::S_ACTION_SETRSC: // "SetRsc"
      case symbol_kind::S_ACTION_SETSID: // "SetSid"
      case symbol_kind::S_ACTION_SETUID: // "SetUID"
      case symbol_kind::S_ACTION_SEVERITY: // "Severity"
      case symbol_kind::S_ACTION_SKIP: // "Skip"
      case symbol_kind::S_ACTION_SKIP_AFTER: // "SkipAfter"
      case symbol_kind::S_ACTION_STATUS: // "Status"
      case symbol_kind::S_ACTION_TAG: // "Tag"
      case symbol_kind::S_ACTION_TRANSFORMATION_BASE_64_ENCODE: // "ACTION_TRANSFORMATION_BASE_64_ENCODE"
      case symbol_kind::S_ACTION_TRANSFORMATION_BASE_64_DECODE: // "ACTION_TRANSFORMATION_BASE_64_DECODE"
      case symbol_kind::S_ACTION_TRANSFORMATION_BASE_64_DECODE_EXT: // "ACTION_TRANSFORMATION_BASE_64_DECODE_EXT"
      case symbol_kind::S_ACTION_TRANSFORMATION_CMD_LINE: // "ACTION_TRANSFORMATION_CMD_LINE"
      case symbol_kind::S_ACTION_TRANSFORMATION_COMPRESS_WHITESPACE: // "ACTION_TRANSFORMATION_COMPRESS_WHITESPACE"
      case symbol_kind::S_ACTION_TRANSFORMATION_CSS_DECODE: // "ACTION_TRANSFORMATION_CSS_DECODE"
      case symbol_kind::S_ACTION_TRANSFORMATION_ESCAPE_SEQ_DECODE: // "ACTION_TRANSFORMATION_ESCAPE_SEQ_DECODE"
      case symbol_kind::S_ACTION_TRANSFORMATION_HEX_ENCODE: // "ACTION_TRANSFORMATION_HEX_ENCODE"
      case symbol_kind::S_ACTION_TRANSFORMATION_HEX_DECODE: // "ACTION_TRANSFORMATION_HEX_DECODE"
      case symbol_kind::S_ACTION_TRANSFORMATION_HTML_ENTITY_DECODE: // "ACTION_TRANSFORMATION_HTML_ENTITY_DECODE"
      case symbol_kind::S_ACTION_TRANSFORMATION_JS_DECODE: // "ACTION_TRANSFORMATION_JS_DECODE"
      case symbol_kind::S_ACTION_TRANSFORMATION_LENGTH: // "ACTION_TRANSFORMATION_LENGTH"
      case symbol_kind::S_ACTION_TRANSFORMATION_LOWERCASE: // "ACTION_TRANSFORMATION_LOWERCASE"
      case symbol_kind::S_ACTION_TRANSFORMATION_MD5: // "ACTION_TRANSFORMATION_MD5"
      case symbol_kind::S_ACTION_TRANSFORMATION_NONE: // "ACTION_TRANSFORMATION_NONE"
      case symbol_kind::S_ACTION_TRANSFORMATION_NORMALISE_PATH: // "ACTION_TRANSFORMATION_NORMALISE_PATH"
      case symbol_kind::S_ACTION_TRANSFORMATION_NORMALISE_PATH_WIN: // "ACTION_TRANSFORMATION_NORMALISE_PATH_WIN"
      case symbol_kind::S_ACTION_TRANSFORMATION_PARITY_EVEN_7_BIT: // "ACTION_TRANSFORMATION_PARITY_EVEN_7_BIT"
      case symbol_kind::S_ACTION_TRANSFORMATION_PARITY_ODD_7_BIT: // "ACTION_TRANSFORMATION_PARITY_ODD_7_BIT"
      case symbol_kind::S_ACTION_TRANSFORMATION_PARITY_ZERO_7_BIT: // "ACTION_TRANSFORMATION_PARITY_ZERO_7_BIT"
      case symbol_kind::S_ACTION_TRANSFORMATION_REMOVE_COMMENTS: // "ACTION_TRANSFORMATION_REMOVE_COMMENTS"
      case symbol_kind::S_ACTION_TRANSFORMATION_REMOVE_COMMENTS_CHAR: // "ACTION_TRANSFORMATION_REMOVE_COMMENTS_CHAR"
      case symbol_kind::S_ACTION_TRANSFORMATION_REMOVE_NULLS: // "ACTION_TRANSFORMATION_REMOVE_NULLS"
      case symbol_kind::S_ACTION_TRANSFORMATION_REMOVE_WHITESPACE: // "ACTION_TRANSFORMATION_REMOVE_WHITESPACE"
      case symbol_kind::S_ACTION_TRANSFORMATION_REPLACE_COMMENTS: // "ACTION_TRANSFORMATION_REPLACE_COMMENTS"
      case symbol_kind::S_ACTION_TRANSFORMATION_REPLACE_NULLS: // "ACTION_TRANSFORMATION_REPLACE_NULLS"
      case symbol_kind::S_ACTION_TRANSFORMATION_SHA1: // "ACTION_TRANSFORMATION_SHA1"
      case symbol_kind::S_ACTION_TRANSFORMATION_SQL_HEX_DECODE: // "ACTION_TRANSFORMATION_SQL_HEX_DECODE"
      case symbol_kind::S_ACTION_TRANSFORMATION_TRIM: // "ACTION_TRANSFORMATION_TRIM"
      case symbol_kind::S_ACTION_TRANSFORMATION_TRIM_LEFT: // "ACTION_TRANSFORMATION_TRIM_LEFT"
      case symbol_kind::S_ACTION_TRANSFORMATION_TRIM_RIGHT: // "ACTION_TRANSFORMATION_TRIM_RIGHT"
      case symbol_kind::S_ACTION_TRANSFORMATION_UPPERCASE: // "ACTION_TRANSFORMATION_UPPERCASE"
      case symbol_kind::S_ACTION_TRANSFORMATION_URL_ENCODE: // "ACTION_TRANSFORMATION_URL_ENCODE"
      case symbol_kind::S_ACTION_TRANSFORMATION_URL_DECODE: // "ACTION_TRANSFORMATION_URL_DECODE"
      case symbol_kind::S_ACTION_TRANSFORMATION_URL_DECODE_UNI: // "ACTION_TRANSFORMATION_URL_DECODE_UNI"
      case symbol_kind::S_ACTION_TRANSFORMATION_UTF8_TO_UNICODE: // "ACTION_TRANSFORMATION_UTF8_TO_UNICODE"
      case symbol_kind::S_ACTION_VER: // "Ver"
      case symbol_kind::S_ACTION_XMLNS: // "xmlns"
      case symbol_kind::S_CONFIG_COMPONENT_SIG: // "CONFIG_COMPONENT_SIG"
      case symbol_kind::S_CONFIG_CONN_ENGINE: // "CONFIG_CONN_ENGINE"
      case symbol_kind::S_CONFIG_SEC_ARGUMENT_SEPARATOR: // "CONFIG_SEC_ARGUMENT_SEPARATOR"
      case symbol_kind::S_CONFIG_SEC_WEB_APP_ID: // "CONFIG_SEC_WEB_APP_ID"
      case symbol_kind::S_CONFIG_SEC_SERVER_SIG: // "CONFIG_SEC_SERVER_SIG"
      case symbol_kind::S_CONFIG_DIR_AUDIT_DIR: // "CONFIG_DIR_AUDIT_DIR"
      case symbol_kind::S_CONFIG_DIR_AUDIT_DIR_MOD: // "CONFIG_DIR_AUDIT_DIR_MOD"
      case symbol_kind::S_CONFIG_DIR_AUDIT_ENG: // "CONFIG_DIR_AUDIT_ENG"
      case symbol_kind::S_CONFIG_DIR_AUDIT_FLE_MOD: // "CONFIG_DIR_AUDIT_FLE_MOD"
      case symbol_kind::S_CONFIG_DIR_AUDIT_LOG: // "CONFIG_DIR_AUDIT_LOG"
      case symbol_kind::S_CONFIG_DIR_AUDIT_LOG2: // "CONFIG_DIR_AUDIT_LOG2"
      case symbol_kind::S_CONFIG_DIR_AUDIT_LOG_P: // "CONFIG_DIR_AUDIT_LOG_P"
      case symbol_kind::S_CONFIG_DIR_AUDIT_STS: // "CONFIG_DIR_AUDIT_STS"
      case symbol_kind::S_CONFIG_DIR_AUDIT_PREFIX: // "CONFIG_DIR_AUDIT_PREFIX"
      case symbol_kind::S_CONFIG_DIR_AUDIT_TPE: // "CONFIG_DIR_AUDIT_TPE"
      case symbol_kind::S_CONFIG_DIR_DEBUG_LOG: // "CONFIG_DIR_DEBUG_LOG"
      case symbol_kind::S_CONFIG_DIR_DEBUG_LVL: // "CONFIG_DIR_DEBUG_LVL"
      case symbol_kind::S_CONFIG_SEC_CACHE_TRANSFORMATIONS: // "CONFIG_SEC_CACHE_TRANSFORMATIONS"
      case symbol_kind::S_CONFIG_SEC_DISABLE_BACKEND_COMPRESS: // "CONFIG_SEC_DISABLE_BACKEND_COMPRESS"
      case symbol_kind::S_CONFIG_SEC_HASH_ENGINE: // "CONFIG_SEC_HASH_ENGINE"
      case symbol_kind::S_CONFIG_SEC_HASH_KEY: // "CONFIG_SEC_HASH_KEY"
      case symbol_kind::S_CONFIG_SEC_HASH_PARAM: // "CONFIG_SEC_HASH_PARAM"
      case symbol_kind::S_CONFIG_SEC_HASH_METHOD_RX: // "CONFIG_SEC_HASH_METHOD_RX"
      case symbol_kind::S_CONFIG_SEC_HASH_METHOD_PM: // "CONFIG_SEC_HASH_METHOD_PM"
      case symbol_kind::S_CONFIG_SEC_CHROOT_DIR: // "CONFIG_SEC_CHROOT_DIR"
      case symbol_kind::S_CONFIG_DIR_GEO_DB: // "CONFIG_DIR_GEO_DB"
      case symbol_kind::S_CONFIG_DIR_GSB_DB: // "CONFIG_DIR_GSB_DB"
      case symbol_kind::S_CONFIG_SEC_GUARDIAN_LOG: // "CONFIG_SEC_GUARDIAN_LOG"
      case symbol_kind::S_CONFIG_DIR_PCRE_MATCH_LIMIT: // "CONFIG_DIR_PCRE_MATCH_LIMIT"
      case symbol_kind::S_CONFIG_DIR_PCRE_MATCH_LIMIT_RECURSION: // "CONFIG_DIR_PCRE_MATCH_LIMIT_RECURSION"
      case symbol_kind::S_CONFIG_SEC_CONN_R_STATE_LIMIT: // "CONFIG_SEC_CONN_R_STATE_LIMIT"
      case symbol_kind::S_CONFIG_SEC_CONN_W_STATE_LIMIT: // "CONFIG_SEC_CONN_W_STATE_LIMIT"
      case symbol_kind::S_CONFIG_SEC_SENSOR_ID: // "CONFIG_SEC_SENSOR_ID"
      case symbol_kind::S_CONFIG_DIR_ARGS_LIMIT: // "CONFIG_DIR_ARGS_LIMIT"
      case symbol_kind::S_CONFIG_DIR_REQ_BODY_JSON_DEPTH_LIMIT: // "CONFIG_DIR_REQ_BODY_JSON_DEPTH_LIMIT"
      case symbol_kind::S_CONFIG_DIR_REQ_BODY: // "CONFIG_DIR_REQ_BODY"
      case symbol_kind::S_CONFIG_DIR_REQ_BODY_IN_MEMORY_LIMIT: // "CONFIG_DIR_REQ_BODY_IN_MEMORY_LIMIT"
      case symbol_kind::S_CONFIG_DIR_REQ_BODY_LIMIT: // "CONFIG_DIR_REQ_BODY_LIMIT"
      case symbol_kind::S_CONFIG_DIR_REQ_BODY_LIMIT_ACTION: // "CONFIG_DIR_REQ_BODY_LIMIT_ACTION"
      case symbol_kind::S_CONFIG_DIR_REQ_BODY_NO_FILES_LIMIT: // "CONFIG_DIR_REQ_BODY_NO_FILES_LIMIT"
      case symbol_kind::S_CONFIG_DIR_RES_BODY: // "CONFIG_DIR_RES_BODY"
      case symbol_kind::S_CONFIG_DIR_RES_BODY_LIMIT: // "CONFIG_DIR_RES_BODY_LIMIT"
      case symbol_kind::S_CONFIG_DIR_RES_BODY_LIMIT_ACTION: // "CONFIG_DIR_RES_BODY_LIMIT_ACTION"
      case symbol_kind::S_CONFIG_SEC_RULE_INHERITANCE: // "CONFIG_SEC_RULE_INHERITANCE"
      case symbol_kind::S_CONFIG_SEC_RULE_PERF_TIME: // "CONFIG_SEC_RULE_PERF_TIME"
      case symbol_kind::S_CONFIG_DIR_RULE_ENG: // "CONFIG_DIR_RULE_ENG"
      case symbol_kind::S_CONFIG_DIR_SEC_ACTION: // "CONFIG_DIR_SEC_ACTION"
      case symbol_kind::S_CONFIG_DIR_SEC_DEFAULT_ACTION: // "CONFIG_DIR_SEC_DEFAULT_ACTION"
      case symbol_kind::S_CONFIG_DIR_SEC_MARKER: // "CONFIG_DIR_SEC_MARKER"
      case symbol_kind::S_CONFIG_DIR_UNICODE_MAP_FILE: // "CONFIG_DIR_UNICODE_MAP_FILE"
      case symbol_kind::S_CONFIG_DIR_UNICODE_CODE_PAGE: // "CONFIG_DIR_UNICODE_CODE_PAGE"
      case symbol_kind::S_CONFIG_SEC_COLLECTION_TIMEOUT: // "CONFIG_SEC_COLLECTION_TIMEOUT"
      case symbol_kind::S_CONFIG_SEC_HTTP_BLKEY: // "CONFIG_SEC_HTTP_BLKEY"
      case symbol_kind::S_CONFIG_SEC_INTERCEPT_ON_ERROR: // "CONFIG_SEC_INTERCEPT_ON_ERROR"
      case symbol_kind::S_CONFIG_SEC_REMOTE_RULES_FAIL_ACTION: // "CONFIG_SEC_REMOTE_RULES_FAIL_ACTION"
      case symbol_kind::S_CONFIG_SEC_RULE_REMOVE_BY_ID: // "CONFIG_SEC_RULE_REMOVE_BY_ID"
      case symbol_kind::S_CONFIG_SEC_RULE_REMOVE_BY_MSG: // "CONFIG_SEC_RULE_REMOVE_BY_MSG"
      case symbol_kind::S_CONFIG_SEC_RULE_REMOVE_BY_TAG: // "CONFIG_SEC_RULE_REMOVE_BY_TAG"
      case symbol_kind::S_CONFIG_SEC_RULE_UPDATE_TARGET_BY_TAG: // "CONFIG_SEC_RULE_UPDATE_TARGET_BY_TAG"
      case symbol_kind::S_CONFIG_SEC_RULE_UPDATE_TARGET_BY_MSG: // "CONFIG_SEC_RULE_UPDATE_TARGET_BY_MSG"
      case symbol_kind::S_CONFIG_SEC_RULE_UPDATE_TARGET_BY_ID: // "CONFIG_SEC_RULE_UPDATE_TARGET_BY_ID"
      case symbol_kind::S_CONFIG_SEC_RULE_UPDATE_ACTION_BY_ID: // "CONFIG_SEC_RULE_UPDATE_ACTION_BY_ID"
      case symbol_kind::S_CONFIG_UPDLOAD_KEEP_FILES: // "CONFIG_UPDLOAD_KEEP_FILES"
      case symbol_kind::S_CONFIG_UPDLOAD_SAVE_TMP_FILES: // "CONFIG_UPDLOAD_SAVE_TMP_FILES"
      case symbol_kind::S_CONFIG_UPLOAD_DIR: // "CONFIG_UPLOAD_DIR"
      case symbol_kind::S_CONFIG_UPLOAD_FILE_LIMIT: // "CONFIG_UPLOAD_FILE_LIMIT"
      case symbol_kind::S_CONFIG_UPLOAD_FILE_MODE: // "CONFIG_UPLOAD_FILE_MODE"
      case symbol_kind::S_CONFIG_VALUE_ABORT: // "CONFIG_VALUE_ABORT"
      case symbol_kind::S_CONFIG_VALUE_DETC: // "CONFIG_VALUE_DETC"
      case symbol_kind::S_CONFIG_VALUE_HTTPS: // "CONFIG_VALUE_HTTPS"
      case symbol_kind::S_CONFIG_VALUE_ONLYARGS: // "CONFIG_VALUE_ONLYARGS"
      case symbol_kind::S_CONFIG_VALUE_OFF: // "CONFIG_VALUE_OFF"
      case symbol_kind::S_CONFIG_VALUE_ON: // "CONFIG_VALUE_ON"
      case symbol_kind::S_CONFIG_VALUE_PARALLEL: // "CONFIG_VALUE_PARALLEL"
      case symbol_kind::S_CONFIG_VALUE_PROCESS_PARTIAL: // "CONFIG_VALUE_PROCESS_PARTIAL"
      case symbol_kind::S_CONFIG_VALUE_REJECT: // "CONFIG_VALUE_REJECT"
      case symbol_kind::S_CONFIG_VALUE_RELEVANT_ONLY: // "CONFIG_VALUE_RELEVANT_ONLY"
      case symbol_kind::S_CONFIG_VALUE_SERIAL: // "CONFIG_VALUE_SERIAL"
      case symbol_kind::S_CONFIG_VALUE_WARN: // "CONFIG_VALUE_WARN"
      case symbol_kind::S_CONFIG_XML_EXTERNAL_ENTITY: // "CONFIG_XML_EXTERNAL_ENTITY"
      case symbol_kind::S_CONFIG_XML_PARSE_XML_INTO_ARGS: // "CONFIG_XML_PARSE_XML_INTO_ARGS"
      case symbol_kind::S_CONGIG_DIR_RESPONSE_BODY_MP: // "CONGIG_DIR_RESPONSE_BODY_MP"
      case symbol_kind::S_CONGIG_DIR_SEC_ARG_SEP: // "CONGIG_DIR_SEC_ARG_SEP"
      case symbol_kind::S_CONGIG_DIR_SEC_COOKIE_FORMAT: // "CONGIG_DIR_SEC_COOKIE_FORMAT"
      case symbol_kind::S_CONFIG_SEC_COOKIEV0_SEPARATOR: // "CONFIG_SEC_COOKIEV0_SEPARATOR"
      case symbol_kind::S_CONGIG_DIR_SEC_DATA_DIR: // "CONGIG_DIR_SEC_DATA_DIR"
      case symbol_kind::S_CONGIG_DIR_SEC_STATUS_ENGINE: // "CONGIG_DIR_SEC_STATUS_ENGINE"
      case symbol_kind::S_CONFIG_SEC_STREAM_IN_BODY_INSPECTION: // "CONFIG_SEC_STREAM_IN_BODY_INSPECTION"
      case symbol_kind::S_CONFIG_SEC_STREAM_OUT_BODY_INSPECTION: // "CONFIG_SEC_STREAM_OUT_BODY_INSPECTION"
      case symbol_kind::S_CONGIG_DIR_SEC_TMP_DIR: // "CONGIG_DIR_SEC_TMP_DIR"
      case symbol_kind::S_DIRECTIVE: // "DIRECTIVE"
      case symbol_kind::S_DIRECTIVE_SECRULESCRIPT: // "DIRECTIVE_SECRULESCRIPT"
      case symbol_kind::S_FREE_TEXT_QUOTE_MACRO_EXPANSION: // "FREE_TEXT_QUOTE_MACRO_EXPANSION"
      case symbol_kind::S_QUOTATION_MARK: // "QUOTATION_MARK"
      case symbol_kind::S_RUN_TIME_VAR_BLD: // "RUN_TIME_VAR_BLD"
      case symbol_kind::S_RUN_TIME_VAR_DUR: // "RUN_TIME_VAR_DUR"
      case symbol_kind::S_RUN_TIME_VAR_HSV: // "RUN_TIME_VAR_HSV"
      case symbol_kind::S_RUN_TIME_VAR_REMOTE_USER: // "RUN_TIME_VAR_REMOTE_USER"
      case symbol_kind::S_RUN_TIME_VAR_TIME: // "RUN_TIME_VAR_TIME"
      case symbol_kind::S_RUN_TIME_VAR_TIME_DAY: // "RUN_TIME_VAR_TIME_DAY"
      case symbol_kind::S_RUN_TIME_VAR_TIME_EPOCH: // "RUN_TIME_VAR_TIME_EPOCH"
      case symbol_kind::S_RUN_TIME_VAR_TIME_HOUR: // "RUN_TIME_VAR_TIME_HOUR"
      case symbol_kind::S_RUN_TIME_VAR_TIME_MIN: // "RUN_TIME_VAR_TIME_MIN"
      case symbol_kind::S_RUN_TIME_VAR_TIME_MON: // "RUN_TIME_VAR_TIME_MON"
      case symbol_kind::S_RUN_TIME_VAR_TIME_SEC: // "RUN_TIME_VAR_TIME_SEC"
      case symbol_kind::S_RUN_TIME_VAR_TIME_WDAY: // "RUN_TIME_VAR_TIME_WDAY"
      case symbol_kind::S_RUN_TIME_VAR_TIME_YEAR: // "RUN_TIME_VAR_TIME_YEAR"
      case symbol_kind::S_VARIABLE: // "VARIABLE"
      case symbol_kind::S_DICT_ELEMENT: // "Dictionary element"
      case symbol_kind::S_DICT_ELEMENT_WITH_EQUALS: // "Dictionary element, with equals"
      case symbol_kind::S_DICT_ELEMENT_REGEXP: // "Dictionary element, selected by regexp"
        value.move< std::string > (std::move (that.value));
        break;

      case symbol_kind::S_op: // op
      case symbol_kind::S_op_before_init: // op_before_init
        value.move< std::unique_ptr<Operator> > (std::move (that.value));
        break;

      case symbol_kind::S_run_time_string: // run_time_string
        value.move< std::unique_ptr<RunTimeString> > (std::move (that.value));
        break;

      case symbol_kind::S_var: // var
        value.move< std::unique_ptr<Variable> > (std::move (that.value));
        break;

      case symbol_kind::S_act: // act
      case symbol_kind::S_setvar_action: // setvar_action
        value.move< std::unique_ptr<actions::Action> > (std::move (that.value));
        break;

      case symbol_kind::S_variables: // variables
      case symbol_kind::S_variables_pre_process: // variables_pre_process
      case symbol_kind::S_variables_may_be_quoted: // variables_may_be_quoted
        value.move< std::unique_ptr<std::vector<std::unique_ptr<Variable> > >  > (std::move (that.value));
        break;

      case symbol_kind::S_actions: // actions
      case symbol_kind::S_actions_may_quoted: // actions_may_quoted
        value.move< std::unique_ptr<std::vector<std::unique_ptr<actions::Action> > >  > (std::move (that.value));
        break;

      default:
        break;
    }

      }
#endif

      /// Copy constructor.
      basic_symbol (const basic_symbol& that);

      /// Constructors for typed symbols.
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
      void clear () YY_NOEXCEPT
      {
        // User destructor.
        symbol_kind_type yykind = this->kind ();
        basic_symbol<Base>& yysym = *this;
        (void) yysym;
        switch (yykind)
        {
       default:
          break;
        }

        // Value type destructor.
switch (yykind)
    {
      case symbol_kind::S_ACTION_ACCURACY: // "Accuracy"
      case symbol_kind::S_ACTION_ALLOW: // "Allow"
      case symbol_kind::S_ACTION_APPEND: // "Append"
      case symbol_kind::S_ACTION_AUDIT_LOG: // "AuditLog"
      case symbol_kind::S_ACTION_BLOCK: // "Block"
      case symbol_kind::S_ACTION_CAPTURE: // "Capture"
      case symbol_kind::S_ACTION_CHAIN: // "Chain"
      case symbol_kind::S_ACTION_CTL_AUDIT_ENGINE: // "ACTION_CTL_AUDIT_ENGINE"
      case symbol_kind::S_ACTION_CTL_AUDIT_LOG_PARTS: // "ACTION_CTL_AUDIT_LOG_PARTS"
      case symbol_kind::S_ACTION_CTL_BDY_JSON: // "ACTION_CTL_BDY_JSON"
      case symbol_kind::S_ACTION_CTL_BDY_XML: // "ACTION_CTL_BDY_XML"
      case symbol_kind::S_ACTION_CTL_BDY_URLENCODED: // "ACTION_CTL_BDY_URLENCODED"
      case symbol_kind::S_ACTION_CTL_FORCE_REQ_BODY_VAR: // "ACTION_CTL_FORCE_REQ_BODY_VAR"
      case symbol_kind::S_ACTION_CTL_PARSE_XML_INTO_ARGS: // "ACTION_CTL_PARSE_XML_INTO_ARGS"
      case symbol_kind::S_ACTION_CTL_REQUEST_BODY_ACCESS: // "ACTION_CTL_REQUEST_BODY_ACCESS"
      case symbol_kind::S_ACTION_CTL_RULE_REMOVE_BY_ID: // "ACTION_CTL_RULE_REMOVE_BY_ID"
      case symbol_kind::S_ACTION_CTL_RULE_REMOVE_BY_TAG: // "ACTION_CTL_RULE_REMOVE_BY_TAG"
      case symbol_kind::S_ACTION_CTL_RULE_REMOVE_TARGET_BY_ID: // "ACTION_CTL_RULE_REMOVE_TARGET_BY_ID"
      case symbol_kind::S_ACTION_CTL_RULE_REMOVE_TARGET_BY_TAG: // "ACTION_CTL_RULE_REMOVE_TARGET_BY_TAG"
      case symbol_kind::S_ACTION_DENY: // "Deny"
      case symbol_kind::S_ACTION_DEPRECATE_VAR: // "DeprecateVar"
      case symbol_kind::S_ACTION_DROP: // "Drop"
      case symbol_kind::S_ACTION_EXEC: // "Exec"
      case symbol_kind::S_ACTION_EXPIRE_VAR: // "ExpireVar"
      case symbol_kind::S_ACTION_ID: // "Id"
      case symbol_kind::S_ACTION_INITCOL: // "InitCol"
      case symbol_kind::S_ACTION_LOG: // "Log"
      case symbol_kind::S_ACTION_LOG_DATA: // "LogData"
      case symbol_kind::S_ACTION_MATURITY: // "Maturity"
      case symbol_kind::S_ACTION_MSG: // "Msg"
      case symbol_kind::S_ACTION_MULTI_MATCH: // "MultiMatch"
      case symbol_kind::S_ACTION_NO_AUDIT_LOG: // "NoAuditLog"
      case symbol_kind::S_ACTION_NO_LOG: // "NoLog"
      case symbol_kind::S_ACTION_PASS: // "Pass"
      case symbol_kind::S_ACTION_PAUSE: // "Pause"
      case symbol_kind::S_ACTION_PHASE: // "Phase"
      case symbol_kind::S_ACTION_PREPEND: // "Prepend"
      case symbol_kind::S_ACTION_PROXY: // "Proxy"
      case symbol_kind::S_ACTION_REDIRECT: // "Redirect"
      case symbol_kind::S_ACTION_REV: // "Rev"
      case symbol_kind::S_ACTION_SANITISE_ARG: // "SanitiseArg"
      case symbol_kind::S_ACTION_SANITISE_MATCHED: // "SanitiseMatched"
      case symbol_kind::S_ACTION_SANITISE_MATCHED_BYTES: // "SanitiseMatchedBytes"
      case symbol_kind::S_ACTION_SANITISE_REQUEST_HEADER: // "SanitiseRequestHeader"
      case symbol_kind::S_ACTION_SANITISE_RESPONSE_HEADER: // "SanitiseResponseHeader"
      case symbol_kind::S_ACTION_SETENV: // "SetEnv"
      case symbol_kind::S_ACTION_SETRSC: // "SetRsc"
      case symbol_kind::S_ACTION_SETSID: // "SetSid"
      case symbol_kind::S_ACTION_SETUID: // "SetUID"
      case symbol_kind::S_ACTION_SEVERITY: // "Severity"
      case symbol_kind::S_ACTION_SKIP: // "Skip"
      case symbol_kind::S_ACTION_SKIP_AFTER: // "SkipAfter"
      case symbol_kind::S_ACTION_STATUS: // "Status"
      case symbol_kind::S_ACTION_TAG: // "Tag"
      case symbol_kind::S_ACTION_TRANSFORMATION_BASE_64_ENCODE: // "ACTION_TRANSFORMATION_BASE_64_ENCODE"
      case symbol_kind::S_ACTION_TRANSFORMATION_BASE_64_DECODE: // "ACTION_TRANSFORMATION_BASE_64_DECODE"
      case symbol_kind::S_ACTION_TRANSFORMATION_BASE_64_DECODE_EXT: // "ACTION_TRANSFORMATION_BASE_64_DECODE_EXT"
      case symbol_kind::S_ACTION_TRANSFORMATION_CMD_LINE: // "ACTION_TRANSFORMATION_CMD_LINE"
      case symbol_kind::S_ACTION_TRANSFORMATION_COMPRESS_WHITESPACE: // "ACTION_TRANSFORMATION_COMPRESS_WHITESPACE"
      case symbol_kind::S_ACTION_TRANSFORMATION_CSS_DECODE: // "ACTION_TRANSFORMATION_CSS_DECODE"
      case symbol_kind::S_ACTION_TRANSFORMATION_ESCAPE_SEQ_DECODE: // "ACTION_TRANSFORMATION_ESCAPE_SEQ_DECODE"
      case symbol_kind::S_ACTION_TRANSFORMATION_HEX_ENCODE: // "ACTION_TRANSFORMATION_HEX_ENCODE"
      case symbol_kind::S_ACTION_TRANSFORMATION_HEX_DECODE: // "ACTION_TRANSFORMATION_HEX_DECODE"
      case symbol_kind::S_ACTION_TRANSFORMATION_HTML_ENTITY_DECODE: // "ACTION_TRANSFORMATION_HTML_ENTITY_DECODE"
      case symbol_kind::S_ACTION_TRANSFORMATION_JS_DECODE: // "ACTION_TRANSFORMATION_JS_DECODE"
      case symbol_kind::S_ACTION_TRANSFORMATION_LENGTH: // "ACTION_TRANSFORMATION_LENGTH"
      case symbol_kind::S_ACTION_TRANSFORMATION_LOWERCASE: // "ACTION_TRANSFORMATION_LOWERCASE"
      case symbol_kind::S_ACTION_TRANSFORMATION_MD5: // "ACTION_TRANSFORMATION_MD5"
      case symbol_kind::S_ACTION_TRANSFORMATION_NONE: // "ACTION_TRANSFORMATION_NONE"
      case symbol_kind::S_ACTION_TRANSFORMATION_NORMALISE_PATH: // "ACTION_TRANSFORMATION_NORMALISE_PATH"
      case symbol_kind::S_ACTION_TRANSFORMATION_NORMALISE_PATH_WIN: // "ACTION_TRANSFORMATION_NORMALISE_PATH_WIN"
      case symbol_kind::S_ACTION_TRANSFORMATION_PARITY_EVEN_7_BIT: // "ACTION_TRANSFORMATION_PARITY_EVEN_7_BIT"
      case symbol_kind::S_ACTION_TRANSFORMATION_PARITY_ODD_7_BIT: // "ACTION_TRANSFORMATION_PARITY_ODD_7_BIT"
      case symbol_kind::S_ACTION_TRANSFORMATION_PARITY_ZERO_7_BIT: // "ACTION_TRANSFORMATION_PARITY_ZERO_7_BIT"
      case symbol_kind::S_ACTION_TRANSFORMATION_REMOVE_COMMENTS: // "ACTION_TRANSFORMATION_REMOVE_COMMENTS"
      case symbol_kind::S_ACTION_TRANSFORMATION_REMOVE_COMMENTS_CHAR: // "ACTION_TRANSFORMATION_REMOVE_COMMENTS_CHAR"
      case symbol_kind::S_ACTION_TRANSFORMATION_REMOVE_NULLS: // "ACTION_TRANSFORMATION_REMOVE_NULLS"
      case symbol_kind::S_ACTION_TRANSFORMATION_REMOVE_WHITESPACE: // "ACTION_TRANSFORMATION_REMOVE_WHITESPACE"
      case symbol_kind::S_ACTION_TRANSFORMATION_REPLACE_COMMENTS: // "ACTION_TRANSFORMATION_REPLACE_COMMENTS"
      case symbol_kind::S_ACTION_TRANSFORMATION_REPLACE_NULLS: // "ACTION_TRANSFORMATION_REPLACE_NULLS"
      case symbol_kind::S_ACTION_TRANSFORMATION_SHA1: // "ACTION_TRANSFORMATION_SHA1"
      case symbol_kind::S_ACTION_TRANSFORMATION_SQL_HEX_DECODE: // "ACTION_TRANSFORMATION_SQL_HEX_DECODE"
      case symbol_kind::S_ACTION_TRANSFORMATION_TRIM: // "ACTION_TRANSFORMATION_TRIM"
      case symbol_kind::S_ACTION_TRANSFORMATION_TRIM_LEFT: // "ACTION_TRANSFORMATION_TRIM_LEFT"
      case symbol_kind::S_ACTION_TRANSFORMATION_TRIM_RIGHT: // "ACTION_TRANSFORMATION_TRIM_RIGHT"
      case symbol_kind::S_ACTION_TRANSFORMATION_UPPERCASE: // "ACTION_TRANSFORMATION_UPPERCASE"
      case symbol_kind::S_ACTION_TRANSFORMATION_URL_ENCODE: // "ACTION_TRANSFORMATION_URL_ENCODE"
      case symbol_kind::S_ACTION_TRANSFORMATION_URL_DECODE: // "ACTION_TRANSFORMATION_URL_DECODE"
      case symbol_kind::S_ACTION_TRANSFORMATION_URL_DECODE_UNI: // "ACTION_TRANSFORMATION_URL_DECODE_UNI"
      case symbol_kind::S_ACTION_TRANSFORMATION_UTF8_TO_UNICODE: // "ACTION_TRANSFORMATION_UTF8_TO_UNICODE"
      case symbol_kind::S_ACTION_VER: // "Ver"
      case symbol_kind::S_ACTION_XMLNS: // "xmlns"
      case symbol_kind::S_CONFIG_COMPONENT_SIG: // "CONFIG_COMPONENT_SIG"
      case symbol_kind::S_CONFIG_CONN_ENGINE: // "CONFIG_CONN_ENGINE"
      case symbol_kind::S_CONFIG_SEC_ARGUMENT_SEPARATOR: // "CONFIG_SEC_ARGUMENT_SEPARATOR"
      case symbol_kind::S_CONFIG_SEC_WEB_APP_ID: // "CONFIG_SEC_WEB_APP_ID"
      case symbol_kind::S_CONFIG_SEC_SERVER_SIG: // "CONFIG_SEC_SERVER_SIG"
      case symbol_kind::S_CONFIG_DIR_AUDIT_DIR: // "CONFIG_DIR_AUDIT_DIR"
      case symbol_kind::S_CONFIG_DIR_AUDIT_DIR_MOD: // "CONFIG_DIR_AUDIT_DIR_MOD"
      case symbol_kind::S_CONFIG_DIR_AUDIT_ENG: // "CONFIG_DIR_AUDIT_ENG"
      case symbol_kind::S_CONFIG_DIR_AUDIT_FLE_MOD: // "CONFIG_DIR_AUDIT_FLE_MOD"
      case symbol_kind::S_CONFIG_DIR_AUDIT_LOG: // "CONFIG_DIR_AUDIT_LOG"
      case symbol_kind::S_CONFIG_DIR_AUDIT_LOG2: // "CONFIG_DIR_AUDIT_LOG2"
      case symbol_kind::S_CONFIG_DIR_AUDIT_LOG_P: // "CONFIG_DIR_AUDIT_LOG_P"
      case symbol_kind::S_CONFIG_DIR_AUDIT_STS: // "CONFIG_DIR_AUDIT_STS"
      case symbol_kind::S_CONFIG_DIR_AUDIT_PREFIX: // "CONFIG_DIR_AUDIT_PREFIX"
      case symbol_kind::S_CONFIG_DIR_AUDIT_TPE: // "CONFIG_DIR_AUDIT_TPE"
      case symbol_kind::S_CONFIG_DIR_DEBUG_LOG: // "CONFIG_DIR_DEBUG_LOG"
      case symbol_kind::S_CONFIG_DIR_DEBUG_LVL: // "CONFIG_DIR_DEBUG_LVL"
      case symbol_kind::S_CONFIG_SEC_CACHE_TRANSFORMATIONS: // "CONFIG_SEC_CACHE_TRANSFORMATIONS"
      case symbol_kind::S_CONFIG_SEC_DISABLE_BACKEND_COMPRESS: // "CONFIG_SEC_DISABLE_BACKEND_COMPRESS"
      case symbol_kind::S_CONFIG_SEC_HASH_ENGINE: // "CONFIG_SEC_HASH_ENGINE"
      case symbol_kind::S_CONFIG_SEC_HASH_KEY: // "CONFIG_SEC_HASH_KEY"
      case symbol_kind::S_CONFIG_SEC_HASH_PARAM: // "CONFIG_SEC_HASH_PARAM"
      case symbol_kind::S_CONFIG_SEC_HASH_METHOD_RX: // "CONFIG_SEC_HASH_METHOD_RX"
      case symbol_kind::S_CONFIG_SEC_HASH_METHOD_PM: // "CONFIG_SEC_HASH_METHOD_PM"
      case symbol_kind::S_CONFIG_SEC_CHROOT_DIR: // "CONFIG_SEC_CHROOT_DIR"
      case symbol_kind::S_CONFIG_DIR_GEO_DB: // "CONFIG_DIR_GEO_DB"
      case symbol_kind::S_CONFIG_DIR_GSB_DB: // "CONFIG_DIR_GSB_DB"
      case symbol_kind::S_CONFIG_SEC_GUARDIAN_LOG: // "CONFIG_SEC_GUARDIAN_LOG"
      case symbol_kind::S_CONFIG_DIR_PCRE_MATCH_LIMIT: // "CONFIG_DIR_PCRE_MATCH_LIMIT"
      case symbol_kind::S_CONFIG_DIR_PCRE_MATCH_LIMIT_RECURSION: // "CONFIG_DIR_PCRE_MATCH_LIMIT_RECURSION"
      case symbol_kind::S_CONFIG_SEC_CONN_R_STATE_LIMIT: // "CONFIG_SEC_CONN_R_STATE_LIMIT"
      case symbol_kind::S_CONFIG_SEC_CONN_W_STATE_LIMIT: // "CONFIG_SEC_CONN_W_STATE_LIMIT"
      case symbol_kind::S_CONFIG_SEC_SENSOR_ID: // "CONFIG_SEC_SENSOR_ID"
      case symbol_kind::S_CONFIG_DIR_ARGS_LIMIT: // "CONFIG_DIR_ARGS_LIMIT"
      case symbol_kind::S_CONFIG_DIR_REQ_BODY_JSON_DEPTH_LIMIT: // "CONFIG_DIR_REQ_BODY_JSON_DEPTH_LIMIT"
      case symbol_kind::S_CONFIG_DIR_REQ_BODY: // "CONFIG_DIR_REQ_BODY"
      case symbol_kind::S_CONFIG_DIR_REQ_BODY_IN_MEMORY_LIMIT: // "CONFIG_DIR_REQ_BODY_IN_MEMORY_LIMIT"
      case symbol_kind::S_CONFIG_DIR_REQ_BODY_LIMIT: // "CONFIG_DIR_REQ_BODY_LIMIT"
      case symbol_kind::S_CONFIG_DIR_REQ_BODY_LIMIT_ACTION: // "CONFIG_DIR_REQ_BODY_LIMIT_ACTION"
      case symbol_kind::S_CONFIG_DIR_REQ_BODY_NO_FILES_LIMIT: // "CONFIG_DIR_REQ_BODY_NO_FILES_LIMIT"
      case symbol_kind::S_CONFIG_DIR_RES_BODY: // "CONFIG_DIR_RES_BODY"
      case symbol_kind::S_CONFIG_DIR_RES_BODY_LIMIT: // "CONFIG_DIR_RES_BODY_LIMIT"
      case symbol_kind::S_CONFIG_DIR_RES_BODY_LIMIT_ACTION: // "CONFIG_DIR_RES_BODY_LIMIT_ACTION"
      case symbol_kind::S_CONFIG_SEC_RULE_INHERITANCE: // "CONFIG_SEC_RULE_INHERITANCE"
      case symbol_kind::S_CONFIG_SEC_RULE_PERF_TIME: // "CONFIG_SEC_RULE_PERF_TIME"
      case symbol_kind::S_CONFIG_DIR_RULE_ENG: // "CONFIG_DIR_RULE_ENG"
      case symbol_kind::S_CONFIG_DIR_SEC_ACTION: // "CONFIG_DIR_SEC_ACTION"
      case symbol_kind::S_CONFIG_DIR_SEC_DEFAULT_ACTION: // "CONFIG_DIR_SEC_DEFAULT_ACTION"
      case symbol_kind::S_CONFIG_DIR_SEC_MARKER: // "CONFIG_DIR_SEC_MARKER"
      case symbol_kind::S_CONFIG_DIR_UNICODE_MAP_FILE: // "CONFIG_DIR_UNICODE_MAP_FILE"
      case symbol_kind::S_CONFIG_DIR_UNICODE_CODE_PAGE: // "CONFIG_DIR_UNICODE_CODE_PAGE"
      case symbol_kind::S_CONFIG_SEC_COLLECTION_TIMEOUT: // "CONFIG_SEC_COLLECTION_TIMEOUT"
      case symbol_kind::S_CONFIG_SEC_HTTP_BLKEY: // "CONFIG_SEC_HTTP_BLKEY"
      case symbol_kind::S_CONFIG_SEC_INTERCEPT_ON_ERROR: // "CONFIG_SEC_INTERCEPT_ON_ERROR"
      case symbol_kind::S_CONFIG_SEC_REMOTE_RULES_FAIL_ACTION: // "CONFIG_SEC_REMOTE_RULES_FAIL_ACTION"
      case symbol_kind::S_CONFIG_SEC_RULE_REMOVE_BY_ID: // "CONFIG_SEC_RULE_REMOVE_BY_ID"
      case symbol_kind::S_CONFIG_SEC_RULE_REMOVE_BY_MSG: // "CONFIG_SEC_RULE_REMOVE_BY_MSG"
      case symbol_kind::S_CONFIG_SEC_RULE_REMOVE_BY_TAG: // "CONFIG_SEC_RULE_REMOVE_BY_TAG"
      case symbol_kind::S_CONFIG_SEC_RULE_UPDATE_TARGET_BY_TAG: // "CONFIG_SEC_RULE_UPDATE_TARGET_BY_TAG"
      case symbol_kind::S_CONFIG_SEC_RULE_UPDATE_TARGET_BY_MSG: // "CONFIG_SEC_RULE_UPDATE_TARGET_BY_MSG"
      case symbol_kind::S_CONFIG_SEC_RULE_UPDATE_TARGET_BY_ID: // "CONFIG_SEC_RULE_UPDATE_TARGET_BY_ID"
      case symbol_kind::S_CONFIG_SEC_RULE_UPDATE_ACTION_BY_ID: // "CONFIG_SEC_RULE_UPDATE_ACTION_BY_ID"
      case symbol_kind::S_CONFIG_UPDLOAD_KEEP_FILES: // "CONFIG_UPDLOAD_KEEP_FILES"
      case symbol_kind::S_CONFIG_UPDLOAD_SAVE_TMP_FILES: // "CONFIG_UPDLOAD_SAVE_TMP_FILES"
      case symbol_kind::S_CONFIG_UPLOAD_DIR: // "CONFIG_UPLOAD_DIR"
      case symbol_kind::S_CONFIG_UPLOAD_FILE_LIMIT: // "CONFIG_UPLOAD_FILE_LIMIT"
      case symbol_kind::S_CONFIG_UPLOAD_FILE_MODE: // "CONFIG_UPLOAD_FILE_MODE"
      case symbol_kind::S_CONFIG_VALUE_ABORT: // "CONFIG_VALUE_ABORT"
      case symbol_kind::S_CONFIG_VALUE_DETC: // "CONFIG_VALUE_DETC"
      case symbol_kind::S_CONFIG_VALUE_HTTPS: // "CONFIG_VALUE_HTTPS"
      case symbol_kind::S_CONFIG_VALUE_ONLYARGS: // "CONFIG_VALUE_ONLYARGS"
      case symbol_kind::S_CONFIG_VALUE_OFF: // "CONFIG_VALUE_OFF"
      case symbol_kind::S_CONFIG_VALUE_ON: // "CONFIG_VALUE_ON"
      case symbol_kind::S_CONFIG_VALUE_PARALLEL: // "CONFIG_VALUE_PARALLEL"
      case symbol_kind::S_CONFIG_VALUE_PROCESS_PARTIAL: // "CONFIG_VALUE_PROCESS_PARTIAL"
      case symbol_kind::S_CONFIG_VALUE_REJECT: // "CONFIG_VALUE_REJECT"
      case symbol_kind::S_CONFIG_VALUE_RELEVANT_ONLY: // "CONFIG_VALUE_RELEVANT_ONLY"
      case symbol_kind::S_CONFIG_VALUE_SERIAL: // "CONFIG_VALUE_SERIAL"
      case symbol_kind::S_CONFIG_VALUE_WARN: // "CONFIG_VALUE_WARN"
      case symbol_kind::S_CONFIG_XML_EXTERNAL_ENTITY: // "CONFIG_XML_EXTERNAL_ENTITY"
      case symbol_kind::S_CONFIG_XML_PARSE_XML_INTO_ARGS: // "CONFIG_XML_PARSE_XML_INTO_ARGS"
      case symbol_kind::S_CONGIG_DIR_RESPONSE_BODY_MP: // "CONGIG_DIR_RESPONSE_BODY_MP"
      case symbol_kind::S_CONGIG_DIR_SEC_ARG_SEP: // "CONGIG_DIR_SEC_ARG_SEP"
      case symbol_kind::S_CONGIG_DIR_SEC_COOKIE_FORMAT: // "CONGIG_DIR_SEC_COOKIE_FORMAT"
      case symbol_kind::S_CONFIG_SEC_COOKIEV0_SEPARATOR: // "CONFIG_SEC_COOKIEV0_SEPARATOR"
      case symbol_kind::S_CONGIG_DIR_SEC_DATA_DIR: // "CONGIG_DIR_SEC_DATA_DIR"
      case symbol_kind::S_CONGIG_DIR_SEC_STATUS_ENGINE: // "CONGIG_DIR_SEC_STATUS_ENGINE"
      case symbol_kind::S_CONFIG_SEC_STREAM_IN_BODY_INSPECTION: // "CONFIG_SEC_STREAM_IN_BODY_INSPECTION"
      case symbol_kind::S_CONFIG_SEC_STREAM_OUT_BODY_INSPECTION: // "CONFIG_SEC_STREAM_OUT_BODY_INSPECTION"
      case symbol_kind::S_CONGIG_DIR_SEC_TMP_DIR: // "CONGIG_DIR_SEC_TMP_DIR"
      case symbol_kind::S_DIRECTIVE: // "DIRECTIVE"
      case symbol_kind::S_DIRECTIVE_SECRULESCRIPT: // "DIRECTIVE_SECRULESCRIPT"
      case symbol_kind::S_FREE_TEXT_QUOTE_MACRO_EXPANSION: // "FREE_TEXT_QUOTE_MACRO_EXPANSION"
      case symbol_kind::S_QUOTATION_MARK: // "QUOTATION_MARK"
      case symbol_kind::S_RUN_TIME_VAR_BLD: // "RUN_TIME_VAR_BLD"
      case symbol_kind::S_RUN_TIME_VAR_DUR: // "RUN_TIME_VAR_DUR"
      case symbol_kind::S_RUN_TIME_VAR_HSV: // "RUN_TIME_VAR_HSV"
      case symbol_kind::S_RUN_TIME_VAR_REMOTE_USER: // "RUN_TIME_VAR_REMOTE_USER"
      case symbol_kind::S_RUN_TIME_VAR_TIME: // "RUN_TIME_VAR_TIME"
      case symbol_kind::S_RUN_TIME_VAR_TIME_DAY: // "RUN_TIME_VAR_TIME_DAY"
      case symbol_kind::S_RUN_TIME_VAR_TIME_EPOCH: // "RUN_TIME_VAR_TIME_EPOCH"
      case symbol_kind::S_RUN_TIME_VAR_TIME_HOUR: // "RUN_TIME_VAR_TIME_HOUR"
      case symbol_kind::S_RUN_TIME_VAR_TIME_MIN: // "RUN_TIME_VAR_TIME_MIN"
      case symbol_kind::S_RUN_TIME_VAR_TIME_MON: // "RUN_TIME_VAR_TIME_MON"
      case symbol_kind::S_RUN_TIME_VAR_TIME_SEC: // "RUN_TIME_VAR_TIME_SEC"
      case symbol_kind::S_RUN_TIME_VAR_TIME_WDAY: // "RUN_TIME_VAR_TIME_WDAY"
      case symbol_kind::S_RUN_TIME_VAR_TIME_YEAR: // "RUN_TIME_VAR_TIME_YEAR"
      case symbol_kind::S_VARIABLE: // "VARIABLE"
      case symbol_kind::S_DICT_ELEMENT: // "Dictionary element"
      case symbol_kind::S_DICT_ELEMENT_WITH_EQUALS: // "Dictionary element, with equals"
      case symbol_kind::S_DICT_ELEMENT_REGEXP: // "Dictionary element, selected by regexp"
        value.template destroy< std::string > ();
        break;

      case symbol_kind::S_op: // op
      case symbol_kind::S_op_before_init: // op_before_init
        value.template destroy< std::unique_ptr<Operator> > ();
        break;

      case symbol_kind::S_run_time_string: // run_time_string
        value.template destroy< std::unique_ptr<RunTimeString> > ();
        break;

      case symbol_kind::S_var: // var
        value.template destroy< std::unique_ptr<Variable> > ();
        break;

      case symbol_kind::S_act: // act
      case symbol_kind::S_setvar_action: // setvar_action
        value.template destroy< std::unique_ptr<actions::Action> > ();
        break;

      case symbol_kind::S_variables: // variables
      case symbol_kind::S_variables_pre_process: // variables_pre_process
      case symbol_kind::S_variables_may_be_quoted: // variables_may_be_quoted
        value.template destroy< std::unique_ptr<std::vector<std::unique_ptr<Variable> > >  > ();
        break;

      case symbol_kind::S_actions: // actions
      case symbol_kind::S_actions_may_quoted: // actions_may_quoted
        value.template destroy< std::unique_ptr<std::vector<std::unique_ptr<actions::Action> > >  > ();
        break;

      default:
        break;
    }

        Base::clear ();
      }

      /// The user-facing name of this symbol.
      std::string name () const YY_NOEXCEPT
      {
        return seclang_parser::symbol_name (this->kind ());
      }

      /// Backward compatibility (Bison 3.6).
      symbol_kind_type type_get () const YY_NOEXCEPT;

      /// Whether empty.
      bool empty () const YY_NOEXCEPT;

      /// Destructive move, \a s is emptied into this.
      void move (basic_symbol& s);

      /// The semantic value.
      value_type value;

      /// The location.
      location_type location;

    private:
#if YY_CPLUSPLUS < 201103L
      /// Assignment operator.
      basic_symbol& operator= (const basic_symbol& that);
#endif
    };

    /// Type access provider for token (enum) based symbols.
    struct by_kind
    {
      /// The symbol kind as needed by the constructor.
      typedef token_kind_type kind_type;

      /// Default constructor.
      by_kind () YY_NOEXCEPT;

#if 201103L <= YY_CPLUSPLUS
      /// Move constructor.
      by_kind (by_kind&& that) YY_NOEXCEPT;
#endif

      /// Copy constructor.
      by_kind (const by_kind& that) YY_NOEXCEPT;

      /// Constructor from (external) token numbers.
      by_kind (kind_type t) YY_NOEXCEPT;



      /// Record that this symbol is empty.
      void clear () YY_NOEXCEPT;

      /// Steal the symbol kind from \a that.
      void move (by_kind& that);

      /// The (internal) type number (corresponding to \a type).
      /// \a empty when empty.
      symbol_kind_type kind () const YY_NOEXCEPT;

      /// Backward compatibility (Bison 3.6).
      symbol_kind_type type_get () const YY_NOEXCEPT;

      /// The symbol kind.
      /// \a S_YYEMPTY when empty.
      symbol_kind_type kind_;
    };

    /// Backward compatibility for a private implementation detail (Bison 3.6).
    typedef by_kind by_type;

    /// "External" symbols: returned by the scanner.
    struct symbol_type : basic_symbol<by_kind>
    {
      /// Superclass.
      typedef basic_symbol<by_kind> super_type;

      /// Empty symbol.
      symbol_type () YY_NOEXCEPT {}

      /// Constructor for valueless symbols, and symbols from each type.
#if 201103L <= YY_CPLUSPLUS
      symbol_type (int tok, location_type l)
        : super_type (token_kind_type (tok), std::move (l))
#else
      symbol_type (int tok, const location_type& l)
        : super_type (token_kind_type (tok), l)
#endif
      {
#if !defined _MSC_VER || defined __clang__
        YY_ASSERT (tok == token::TOK_END
                   || (token::TOK_YYerror <= tok && tok <= token::TOK_ACTION_CTL_RULE_ENGINE));
#endif
      }
#if 201103L <= YY_CPLUSPLUS
      symbol_type (int tok, std::string v, location_type l)
        : super_type (token_kind_type (tok), std::move (v), std::move (l))
#else
      symbol_type (int tok, const std::string& v, const location_type& l)
        : super_type (token_kind_type (tok), v, l)
#endif
      {
#if !defined _MSC_VER || defined __clang__
        YY_ASSERT ((token::TOK_ACTION_ACCURACY <= tok && tok <= token::TOK_DICT_ELEMENT_REGEXP));
#endif
      }
    };

    /// Build a parser object.
    seclang_parser (modsecurity::Parser::Driver& driver_yyarg);
    virtual ~seclang_parser ();

#if 201103L <= YY_CPLUSPLUS
    /// Non copyable.
    seclang_parser (const seclang_parser&) = delete;
    /// Non copyable.
    seclang_parser& operator= (const seclang_parser&) = delete;
#endif

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

    /// The user-facing name of the symbol whose (internal) number is
    /// YYSYMBOL.  No bounds checking.
    static std::string symbol_name (symbol_kind_type yysymbol);

    // Implementation of make_symbol for each token kind.
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
      make_YYerror (location_type l)
      {
        return symbol_type (token::TOK_YYerror, std::move (l));
      }
#else
      static
      symbol_type
      make_YYerror (const location_type& l)
      {
        return symbol_type (token::TOK_YYerror, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_YYUNDEF (location_type l)
      {
        return symbol_type (token::TOK_YYUNDEF, std::move (l));
      }
#else
      static
      symbol_type
      make_YYUNDEF (const location_type& l)
      {
        return symbol_type (token::TOK_YYUNDEF, l);
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
      make_VARIABLE_MULTIPART_PART_HEADERS (location_type l)
      {
        return symbol_type (token::TOK_VARIABLE_MULTIPART_PART_HEADERS, std::move (l));
      }
#else
      static
      symbol_type
      make_VARIABLE_MULTIPART_PART_HEADERS (const location_type& l)
      {
        return symbol_type (token::TOK_VARIABLE_MULTIPART_PART_HEADERS, l);
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
      make_VARIABLE_MSC_PCRE_ERROR (location_type l)
      {
        return symbol_type (token::TOK_VARIABLE_MSC_PCRE_ERROR, std::move (l));
      }
#else
      static
      symbol_type
      make_VARIABLE_MSC_PCRE_ERROR (const location_type& l)
      {
        return symbol_type (token::TOK_VARIABLE_MSC_PCRE_ERROR, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_VARIABLE_MSC_PCRE_LIMITS_EXCEEDED (location_type l)
      {
        return symbol_type (token::TOK_VARIABLE_MSC_PCRE_LIMITS_EXCEEDED, std::move (l));
      }
#else
      static
      symbol_type
      make_VARIABLE_MSC_PCRE_LIMITS_EXCEEDED (const location_type& l)
      {
        return symbol_type (token::TOK_VARIABLE_MSC_PCRE_LIMITS_EXCEEDED, l);
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
      make_OPERATOR_RX_GLOBAL (location_type l)
      {
        return symbol_type (token::TOK_OPERATOR_RX_GLOBAL, std::move (l));
      }
#else
      static
      symbol_type
      make_OPERATOR_RX_GLOBAL (const location_type& l)
      {
        return symbol_type (token::TOK_OPERATOR_RX_GLOBAL, l);
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
      make_ACTION_CTL_PARSE_XML_INTO_ARGS (std::string v, location_type l)
      {
        return symbol_type (token::TOK_ACTION_CTL_PARSE_XML_INTO_ARGS, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_ACTION_CTL_PARSE_XML_INTO_ARGS (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_ACTION_CTL_PARSE_XML_INTO_ARGS, v, l);
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
      make_CONFIG_DIR_AUDIT_PREFIX (std::string v, location_type l)
      {
        return symbol_type (token::TOK_CONFIG_DIR_AUDIT_PREFIX, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_CONFIG_DIR_AUDIT_PREFIX (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_CONFIG_DIR_AUDIT_PREFIX, v, l);
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
      make_CONFIG_DIR_ARGS_LIMIT (std::string v, location_type l)
      {
        return symbol_type (token::TOK_CONFIG_DIR_ARGS_LIMIT, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_CONFIG_DIR_ARGS_LIMIT (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_CONFIG_DIR_ARGS_LIMIT, v, l);
      }
#endif
#if 201103L <= YY_CPLUSPLUS
      static
      symbol_type
      make_CONFIG_DIR_REQ_BODY_JSON_DEPTH_LIMIT (std::string v, location_type l)
      {
        return symbol_type (token::TOK_CONFIG_DIR_REQ_BODY_JSON_DEPTH_LIMIT, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_CONFIG_DIR_REQ_BODY_JSON_DEPTH_LIMIT (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_CONFIG_DIR_REQ_BODY_JSON_DEPTH_LIMIT, v, l);
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
      make_CONFIG_VALUE_ONLYARGS (std::string v, location_type l)
      {
        return symbol_type (token::TOK_CONFIG_VALUE_ONLYARGS, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_CONFIG_VALUE_ONLYARGS (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_CONFIG_VALUE_ONLYARGS, v, l);
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
      make_CONFIG_XML_PARSE_XML_INTO_ARGS (std::string v, location_type l)
      {
        return symbol_type (token::TOK_CONFIG_XML_PARSE_XML_INTO_ARGS, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_CONFIG_XML_PARSE_XML_INTO_ARGS (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_CONFIG_XML_PARSE_XML_INTO_ARGS, v, l);
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
      make_DICT_ELEMENT_WITH_EQUALS (std::string v, location_type l)
      {
        return symbol_type (token::TOK_DICT_ELEMENT_WITH_EQUALS, std::move (v), std::move (l));
      }
#else
      static
      symbol_type
      make_DICT_ELEMENT_WITH_EQUALS (const std::string& v, const location_type& l)
      {
        return symbol_type (token::TOK_DICT_ELEMENT_WITH_EQUALS, v, l);
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


    class context
    {
    public:
      context (const seclang_parser& yyparser, const symbol_type& yyla);
      const symbol_type& lookahead () const YY_NOEXCEPT { return yyla_; }
      symbol_kind_type token () const YY_NOEXCEPT { return yyla_.kind (); }
      const location_type& location () const YY_NOEXCEPT { return yyla_.location; }

      /// Put in YYARG at most YYARGN of the expected tokens, and return the
      /// number of tokens stored in YYARG.  If YYARG is null, return the
      /// number of expected tokens (guaranteed to be less than YYNTOKENS).
      int expected_tokens (symbol_kind_type yyarg[], int yyargn) const;

    private:
      const seclang_parser& yyparser_;
      const symbol_type& yyla_;
    };

  private:
#if YY_CPLUSPLUS < 201103L
    /// Non copyable.
    seclang_parser (const seclang_parser&);
    /// Non copyable.
    seclang_parser& operator= (const seclang_parser&);
#endif


    /// Stored state numbers (used for stacks).
    typedef short state_type;

    /// The arguments of the error message.
    int yy_syntax_error_arguments_ (const context& yyctx,
                                    symbol_kind_type yyarg[], int yyargn) const;

    /// Generate an error message.
    /// \param yyctx     the context in which the error occurred.
    virtual std::string yysyntax_error_ (const context& yyctx) const;
    /// Compute post-reduction state.
    /// \param yystate   the current state
    /// \param yysym     the nonterminal to push on the stack
    static state_type yy_lr_goto_state_ (state_type yystate, int yysym);

    /// Whether the given \c yypact_ value indicates a defaulted state.
    /// \param yyvalue   the value to check
    static bool yy_pact_value_is_default_ (int yyvalue) YY_NOEXCEPT;

    /// Whether the given \c yytable_ value indicates a syntax error.
    /// \param yyvalue   the value to check
    static bool yy_table_value_is_error_ (int yyvalue) YY_NOEXCEPT;

    static const short yypact_ninf_;
    static const signed char yytable_ninf_;

    /// Convert a scanner token kind \a t to a symbol kind.
    /// In theory \a t should be a token_kind_type, but character literals
    /// are valid, yet not members of the token_kind_type enum.
    static symbol_kind_type yytranslate_ (int t) YY_NOEXCEPT;

    /// Convert the symbol name \a n to a form suitable for a diagnostic.
    static std::string yytnamerr_ (const char *yystr);

    /// For a symbol, its name in clear.
    static const char* const yytname_[];


    // Tables.
    // YYPACT[STATE-NUM] -- Index in YYTABLE of the portion describing
    // STATE-NUM.
    static const short yypact_[];

    // YYDEFACT[STATE-NUM] -- Default reduction number in state STATE-NUM.
    // Performed when YYTABLE does not specify something else to do.  Zero
    // means the default is an error.
    static const short yydefact_[];

    // YYPGOTO[NTERM-NUM].
    static const short yypgoto_[];

    // YYDEFGOTO[NTERM-NUM].
    static const short yydefgoto_[];

    // YYTABLE[YYPACT[STATE-NUM]] -- What to do in state STATE-NUM.  If
    // positive, shift that token.  If negative, reduce the rule whose
    // number is the opposite.  If YYTABLE_NINF, syntax error.
    static const short yytable_[];

    static const short yycheck_[];

    // YYSTOS[STATE-NUM] -- The symbol kind of the accessing symbol of
    // state STATE-NUM.
    static const short yystos_[];

    // YYR1[RULE-NUM] -- Symbol kind of the left-hand side of rule RULE-NUM.
    static const short yyr1_[];

    // YYR2[RULE-NUM] -- Number of symbols on the right-hand side of rule RULE-NUM.
    static const signed char yyr2_[];


#if YYDEBUG
    // YYRLINE[YYN] -- Source line where rule number YYN was defined.
    static const short yyrline_[];
    /// Report on the debug stream that the rule \a r is going to be reduced.
    virtual void yy_reduce_print_ (int r) const;
    /// Print the state stack on the debug stream.
    virtual void yy_stack_print_ () const;

    /// Debugging level.
    int yydebug_;
    /// Debug stream.
    std::ostream* yycdebug_;

    /// \brief Display a symbol kind, value and location.
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

      /// The symbol kind as needed by the constructor.
      typedef state_type kind_type;

      /// Constructor.
      by_state (kind_type s) YY_NOEXCEPT;

      /// Copy constructor.
      by_state (const by_state& that) YY_NOEXCEPT;

      /// Record that this symbol is empty.
      void clear () YY_NOEXCEPT;

      /// Steal the symbol kind from \a that.
      void move (by_state& that);

      /// The symbol kind (corresponding to \a state).
      /// \a symbol_kind::S_YYEMPTY when empty.
      symbol_kind_type kind () const YY_NOEXCEPT;

      /// The state number used to denote an empty symbol.
      /// We use the initial state, as it does not have a value.
      enum { empty_state = 0 };

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

      /// Assignment, needed by push_back by other implementations.
      /// Needed by some other old implementations.
      stack_symbol_type& operator= (const stack_symbol_type& that);
#endif
    };

    /// A stack with random access from its top.
    template <typename T, typename S = std::vector<T> >
    class stack
    {
    public:
      // Hide our reversed order.
      typedef typename S::iterator iterator;
      typedef typename S::const_iterator const_iterator;
      typedef typename S::size_type size_type;
      typedef typename std::ptrdiff_t index_type;

      stack (size_type n = 200) YY_NOEXCEPT
        : seq_ (n)
      {}

#if 201103L <= YY_CPLUSPLUS
      /// Non copyable.
      stack (const stack&) = delete;
      /// Non copyable.
      stack& operator= (const stack&) = delete;
#endif

      /// Random access.
      ///
      /// Index 0 returns the topmost element.
      const T&
      operator[] (index_type i) const
      {
        return seq_[size_type (size () - 1 - i)];
      }

      /// Random access.
      ///
      /// Index 0 returns the topmost element.
      T&
      operator[] (index_type i)
      {
        return seq_[size_type (size () - 1 - i)];
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
      pop (std::ptrdiff_t n = 1) YY_NOEXCEPT
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
      index_type
      size () const YY_NOEXCEPT
      {
        return index_type (seq_.size ());
      }

      /// Iterator on top of the stack (going downwards).
      const_iterator
      begin () const YY_NOEXCEPT
      {
        return seq_.begin ();
      }

      /// Bottom of the stack.
      const_iterator
      end () const YY_NOEXCEPT
      {
        return seq_.end ();
      }

      /// Present a slice of the top of a stack.
      class slice
      {
      public:
        slice (const stack& stack, index_type range) YY_NOEXCEPT
          : stack_ (stack)
          , range_ (range)
        {}

        const T&
        operator[] (index_type i) const
        {
          return stack_[range_ - i];
        }

      private:
        const stack& stack_;
        index_type range_;
      };

    private:
#if YY_CPLUSPLUS < 201103L
      /// Non copyable.
      stack (const stack&);
      /// Non copyable.
      stack& operator= (const stack&);
#endif
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
    void yypop_ (int n = 1) YY_NOEXCEPT;

    /// Constants.
    enum
    {
      yylast_ = 3409,     ///< Last index in yytable_.
      yynnts_ = 16,  ///< Number of nonterminal symbols.
      yyfinal_ = 347 ///< Termination state number.
    };


    // User arguments.
    modsecurity::Parser::Driver& driver;

  };

  inline
  seclang_parser::symbol_kind_type
  seclang_parser::yytranslate_ (int t) YY_NOEXCEPT
  {
    // YYTRANSLATE[TOKEN-NUM] -- Symbol number corresponding to
    // TOKEN-NUM as returned by yylex.
    static
    const short
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
     335,   336,   337,   338,   339,   340,   341,   342,   343,   344,
     345,   346,   347,   348,   349,   350,   351
    };
    // Last valid token kind.
    const int code_max = 606;

    if (t <= 0)
      return symbol_kind::S_YYEOF;
    else if (t <= code_max)
      return static_cast <symbol_kind_type> (translate_table[t]);
    else
      return symbol_kind::S_YYUNDEF;
  }

  // basic_symbol.
  template <typename Base>
  seclang_parser::basic_symbol<Base>::basic_symbol (const basic_symbol& that)
    : Base (that)
    , value ()
    , location (that.location)
  {
    switch (this->kind ())
    {
      case symbol_kind::S_ACTION_ACCURACY: // "Accuracy"
      case symbol_kind::S_ACTION_ALLOW: // "Allow"
      case symbol_kind::S_ACTION_APPEND: // "Append"
      case symbol_kind::S_ACTION_AUDIT_LOG: // "AuditLog"
      case symbol_kind::S_ACTION_BLOCK: // "Block"
      case symbol_kind::S_ACTION_CAPTURE: // "Capture"
      case symbol_kind::S_ACTION_CHAIN: // "Chain"
      case symbol_kind::S_ACTION_CTL_AUDIT_ENGINE: // "ACTION_CTL_AUDIT_ENGINE"
      case symbol_kind::S_ACTION_CTL_AUDIT_LOG_PARTS: // "ACTION_CTL_AUDIT_LOG_PARTS"
      case symbol_kind::S_ACTION_CTL_BDY_JSON: // "ACTION_CTL_BDY_JSON"
      case symbol_kind::S_ACTION_CTL_BDY_XML: // "ACTION_CTL_BDY_XML"
      case symbol_kind::S_ACTION_CTL_BDY_URLENCODED: // "ACTION_CTL_BDY_URLENCODED"
      case symbol_kind::S_ACTION_CTL_FORCE_REQ_BODY_VAR: // "ACTION_CTL_FORCE_REQ_BODY_VAR"
      case symbol_kind::S_ACTION_CTL_PARSE_XML_INTO_ARGS: // "ACTION_CTL_PARSE_XML_INTO_ARGS"
      case symbol_kind::S_ACTION_CTL_REQUEST_BODY_ACCESS: // "ACTION_CTL_REQUEST_BODY_ACCESS"
      case symbol_kind::S_ACTION_CTL_RULE_REMOVE_BY_ID: // "ACTION_CTL_RULE_REMOVE_BY_ID"
      case symbol_kind::S_ACTION_CTL_RULE_REMOVE_BY_TAG: // "ACTION_CTL_RULE_REMOVE_BY_TAG"
      case symbol_kind::S_ACTION_CTL_RULE_REMOVE_TARGET_BY_ID: // "ACTION_CTL_RULE_REMOVE_TARGET_BY_ID"
      case symbol_kind::S_ACTION_CTL_RULE_REMOVE_TARGET_BY_TAG: // "ACTION_CTL_RULE_REMOVE_TARGET_BY_TAG"
      case symbol_kind::S_ACTION_DENY: // "Deny"
      case symbol_kind::S_ACTION_DEPRECATE_VAR: // "DeprecateVar"
      case symbol_kind::S_ACTION_DROP: // "Drop"
      case symbol_kind::S_ACTION_EXEC: // "Exec"
      case symbol_kind::S_ACTION_EXPIRE_VAR: // "ExpireVar"
      case symbol_kind::S_ACTION_ID: // "Id"
      case symbol_kind::S_ACTION_INITCOL: // "InitCol"
      case symbol_kind::S_ACTION_LOG: // "Log"
      case symbol_kind::S_ACTION_LOG_DATA: // "LogData"
      case symbol_kind::S_ACTION_MATURITY: // "Maturity"
      case symbol_kind::S_ACTION_MSG: // "Msg"
      case symbol_kind::S_ACTION_MULTI_MATCH: // "MultiMatch"
      case symbol_kind::S_ACTION_NO_AUDIT_LOG: // "NoAuditLog"
      case symbol_kind::S_ACTION_NO_LOG: // "NoLog"
      case symbol_kind::S_ACTION_PASS: // "Pass"
      case symbol_kind::S_ACTION_PAUSE: // "Pause"
      case symbol_kind::S_ACTION_PHASE: // "Phase"
      case symbol_kind::S_ACTION_PREPEND: // "Prepend"
      case symbol_kind::S_ACTION_PROXY: // "Proxy"
      case symbol_kind::S_ACTION_REDIRECT: // "Redirect"
      case symbol_kind::S_ACTION_REV: // "Rev"
      case symbol_kind::S_ACTION_SANITISE_ARG: // "SanitiseArg"
      case symbol_kind::S_ACTION_SANITISE_MATCHED: // "SanitiseMatched"
      case symbol_kind::S_ACTION_SANITISE_MATCHED_BYTES: // "SanitiseMatchedBytes"
      case symbol_kind::S_ACTION_SANITISE_REQUEST_HEADER: // "SanitiseRequestHeader"
      case symbol_kind::S_ACTION_SANITISE_RESPONSE_HEADER: // "SanitiseResponseHeader"
      case symbol_kind::S_ACTION_SETENV: // "SetEnv"
      case symbol_kind::S_ACTION_SETRSC: // "SetRsc"
      case symbol_kind::S_ACTION_SETSID: // "SetSid"
      case symbol_kind::S_ACTION_SETUID: // "SetUID"
      case symbol_kind::S_ACTION_SEVERITY: // "Severity"
      case symbol_kind::S_ACTION_SKIP: // "Skip"
      case symbol_kind::S_ACTION_SKIP_AFTER: // "SkipAfter"
      case symbol_kind::S_ACTION_STATUS: // "Status"
      case symbol_kind::S_ACTION_TAG: // "Tag"
      case symbol_kind::S_ACTION_TRANSFORMATION_BASE_64_ENCODE: // "ACTION_TRANSFORMATION_BASE_64_ENCODE"
      case symbol_kind::S_ACTION_TRANSFORMATION_BASE_64_DECODE: // "ACTION_TRANSFORMATION_BASE_64_DECODE"
      case symbol_kind::S_ACTION_TRANSFORMATION_BASE_64_DECODE_EXT: // "ACTION_TRANSFORMATION_BASE_64_DECODE_EXT"
      case symbol_kind::S_ACTION_TRANSFORMATION_CMD_LINE: // "ACTION_TRANSFORMATION_CMD_LINE"
      case symbol_kind::S_ACTION_TRANSFORMATION_COMPRESS_WHITESPACE: // "ACTION_TRANSFORMATION_COMPRESS_WHITESPACE"
      case symbol_kind::S_ACTION_TRANSFORMATION_CSS_DECODE: // "ACTION_TRANSFORMATION_CSS_DECODE"
      case symbol_kind::S_ACTION_TRANSFORMATION_ESCAPE_SEQ_DECODE: // "ACTION_TRANSFORMATION_ESCAPE_SEQ_DECODE"
      case symbol_kind::S_ACTION_TRANSFORMATION_HEX_ENCODE: // "ACTION_TRANSFORMATION_HEX_ENCODE"
      case symbol_kind::S_ACTION_TRANSFORMATION_HEX_DECODE: // "ACTION_TRANSFORMATION_HEX_DECODE"
      case symbol_kind::S_ACTION_TRANSFORMATION_HTML_ENTITY_DECODE: // "ACTION_TRANSFORMATION_HTML_ENTITY_DECODE"
      case symbol_kind::S_ACTION_TRANSFORMATION_JS_DECODE: // "ACTION_TRANSFORMATION_JS_DECODE"
      case symbol_kind::S_ACTION_TRANSFORMATION_LENGTH: // "ACTION_TRANSFORMATION_LENGTH"
      case symbol_kind::S_ACTION_TRANSFORMATION_LOWERCASE: // "ACTION_TRANSFORMATION_LOWERCASE"
      case symbol_kind::S_ACTION_TRANSFORMATION_MD5: // "ACTION_TRANSFORMATION_MD5"
      case symbol_kind::S_ACTION_TRANSFORMATION_NONE: // "ACTION_TRANSFORMATION_NONE"
      case symbol_kind::S_ACTION_TRANSFORMATION_NORMALISE_PATH: // "ACTION_TRANSFORMATION_NORMALISE_PATH"
      case symbol_kind::S_ACTION_TRANSFORMATION_NORMALISE_PATH_WIN: // "ACTION_TRANSFORMATION_NORMALISE_PATH_WIN"
      case symbol_kind::S_ACTION_TRANSFORMATION_PARITY_EVEN_7_BIT: // "ACTION_TRANSFORMATION_PARITY_EVEN_7_BIT"
      case symbol_kind::S_ACTION_TRANSFORMATION_PARITY_ODD_7_BIT: // "ACTION_TRANSFORMATION_PARITY_ODD_7_BIT"
      case symbol_kind::S_ACTION_TRANSFORMATION_PARITY_ZERO_7_BIT: // "ACTION_TRANSFORMATION_PARITY_ZERO_7_BIT"
      case symbol_kind::S_ACTION_TRANSFORMATION_REMOVE_COMMENTS: // "ACTION_TRANSFORMATION_REMOVE_COMMENTS"
      case symbol_kind::S_ACTION_TRANSFORMATION_REMOVE_COMMENTS_CHAR: // "ACTION_TRANSFORMATION_REMOVE_COMMENTS_CHAR"
      case symbol_kind::S_ACTION_TRANSFORMATION_REMOVE_NULLS: // "ACTION_TRANSFORMATION_REMOVE_NULLS"
      case symbol_kind::S_ACTION_TRANSFORMATION_REMOVE_WHITESPACE: // "ACTION_TRANSFORMATION_REMOVE_WHITESPACE"
      case symbol_kind::S_ACTION_TRANSFORMATION_REPLACE_COMMENTS: // "ACTION_TRANSFORMATION_REPLACE_COMMENTS"
      case symbol_kind::S_ACTION_TRANSFORMATION_REPLACE_NULLS: // "ACTION_TRANSFORMATION_REPLACE_NULLS"
      case symbol_kind::S_ACTION_TRANSFORMATION_SHA1: // "ACTION_TRANSFORMATION_SHA1"
      case symbol_kind::S_ACTION_TRANSFORMATION_SQL_HEX_DECODE: // "ACTION_TRANSFORMATION_SQL_HEX_DECODE"
      case symbol_kind::S_ACTION_TRANSFORMATION_TRIM: // "ACTION_TRANSFORMATION_TRIM"
      case symbol_kind::S_ACTION_TRANSFORMATION_TRIM_LEFT: // "ACTION_TRANSFORMATION_TRIM_LEFT"
      case symbol_kind::S_ACTION_TRANSFORMATION_TRIM_RIGHT: // "ACTION_TRANSFORMATION_TRIM_RIGHT"
      case symbol_kind::S_ACTION_TRANSFORMATION_UPPERCASE: // "ACTION_TRANSFORMATION_UPPERCASE"
      case symbol_kind::S_ACTION_TRANSFORMATION_URL_ENCODE: // "ACTION_TRANSFORMATION_URL_ENCODE"
      case symbol_kind::S_ACTION_TRANSFORMATION_URL_DECODE: // "ACTION_TRANSFORMATION_URL_DECODE"
      case symbol_kind::S_ACTION_TRANSFORMATION_URL_DECODE_UNI: // "ACTION_TRANSFORMATION_URL_DECODE_UNI"
      case symbol_kind::S_ACTION_TRANSFORMATION_UTF8_TO_UNICODE: // "ACTION_TRANSFORMATION_UTF8_TO_UNICODE"
      case symbol_kind::S_ACTION_VER: // "Ver"
      case symbol_kind::S_ACTION_XMLNS: // "xmlns"
      case symbol_kind::S_CONFIG_COMPONENT_SIG: // "CONFIG_COMPONENT_SIG"
      case symbol_kind::S_CONFIG_CONN_ENGINE: // "CONFIG_CONN_ENGINE"
      case symbol_kind::S_CONFIG_SEC_ARGUMENT_SEPARATOR: // "CONFIG_SEC_ARGUMENT_SEPARATOR"
      case symbol_kind::S_CONFIG_SEC_WEB_APP_ID: // "CONFIG_SEC_WEB_APP_ID"
      case symbol_kind::S_CONFIG_SEC_SERVER_SIG: // "CONFIG_SEC_SERVER_SIG"
      case symbol_kind::S_CONFIG_DIR_AUDIT_DIR: // "CONFIG_DIR_AUDIT_DIR"
      case symbol_kind::S_CONFIG_DIR_AUDIT_DIR_MOD: // "CONFIG_DIR_AUDIT_DIR_MOD"
      case symbol_kind::S_CONFIG_DIR_AUDIT_ENG: // "CONFIG_DIR_AUDIT_ENG"
      case symbol_kind::S_CONFIG_DIR_AUDIT_FLE_MOD: // "CONFIG_DIR_AUDIT_FLE_MOD"
      case symbol_kind::S_CONFIG_DIR_AUDIT_LOG: // "CONFIG_DIR_AUDIT_LOG"
      case symbol_kind::S_CONFIG_DIR_AUDIT_LOG2: // "CONFIG_DIR_AUDIT_LOG2"
      case symbol_kind::S_CONFIG_DIR_AUDIT_LOG_P: // "CONFIG_DIR_AUDIT_LOG_P"
      case symbol_kind::S_CONFIG_DIR_AUDIT_STS: // "CONFIG_DIR_AUDIT_STS"
      case symbol_kind::S_CONFIG_DIR_AUDIT_PREFIX: // "CONFIG_DIR_AUDIT_PREFIX"
      case symbol_kind::S_CONFIG_DIR_AUDIT_TPE: // "CONFIG_DIR_AUDIT_TPE"
      case symbol_kind::S_CONFIG_DIR_DEBUG_LOG: // "CONFIG_DIR_DEBUG_LOG"
      case symbol_kind::S_CONFIG_DIR_DEBUG_LVL: // "CONFIG_DIR_DEBUG_LVL"
      case symbol_kind::S_CONFIG_SEC_CACHE_TRANSFORMATIONS: // "CONFIG_SEC_CACHE_TRANSFORMATIONS"
      case symbol_kind::S_CONFIG_SEC_DISABLE_BACKEND_COMPRESS: // "CONFIG_SEC_DISABLE_BACKEND_COMPRESS"
      case symbol_kind::S_CONFIG_SEC_HASH_ENGINE: // "CONFIG_SEC_HASH_ENGINE"
      case symbol_kind::S_CONFIG_SEC_HASH_KEY: // "CONFIG_SEC_HASH_KEY"
      case symbol_kind::S_CONFIG_SEC_HASH_PARAM: // "CONFIG_SEC_HASH_PARAM"
      case symbol_kind::S_CONFIG_SEC_HASH_METHOD_RX: // "CONFIG_SEC_HASH_METHOD_RX"
      case symbol_kind::S_CONFIG_SEC_HASH_METHOD_PM: // "CONFIG_SEC_HASH_METHOD_PM"
      case symbol_kind::S_CONFIG_SEC_CHROOT_DIR: // "CONFIG_SEC_CHROOT_DIR"
      case symbol_kind::S_CONFIG_DIR_GEO_DB: // "CONFIG_DIR_GEO_DB"
      case symbol_kind::S_CONFIG_DIR_GSB_DB: // "CONFIG_DIR_GSB_DB"
      case symbol_kind::S_CONFIG_SEC_GUARDIAN_LOG: // "CONFIG_SEC_GUARDIAN_LOG"
      case symbol_kind::S_CONFIG_DIR_PCRE_MATCH_LIMIT: // "CONFIG_DIR_PCRE_MATCH_LIMIT"
      case symbol_kind::S_CONFIG_DIR_PCRE_MATCH_LIMIT_RECURSION: // "CONFIG_DIR_PCRE_MATCH_LIMIT_RECURSION"
      case symbol_kind::S_CONFIG_SEC_CONN_R_STATE_LIMIT: // "CONFIG_SEC_CONN_R_STATE_LIMIT"
      case symbol_kind::S_CONFIG_SEC_CONN_W_STATE_LIMIT: // "CONFIG_SEC_CONN_W_STATE_LIMIT"
      case symbol_kind::S_CONFIG_SEC_SENSOR_ID: // "CONFIG_SEC_SENSOR_ID"
      case symbol_kind::S_CONFIG_DIR_ARGS_LIMIT: // "CONFIG_DIR_ARGS_LIMIT"
      case symbol_kind::S_CONFIG_DIR_REQ_BODY_JSON_DEPTH_LIMIT: // "CONFIG_DIR_REQ_BODY_JSON_DEPTH_LIMIT"
      case symbol_kind::S_CONFIG_DIR_REQ_BODY: // "CONFIG_DIR_REQ_BODY"
      case symbol_kind::S_CONFIG_DIR_REQ_BODY_IN_MEMORY_LIMIT: // "CONFIG_DIR_REQ_BODY_IN_MEMORY_LIMIT"
      case symbol_kind::S_CONFIG_DIR_REQ_BODY_LIMIT: // "CONFIG_DIR_REQ_BODY_LIMIT"
      case symbol_kind::S_CONFIG_DIR_REQ_BODY_LIMIT_ACTION: // "CONFIG_DIR_REQ_BODY_LIMIT_ACTION"
      case symbol_kind::S_CONFIG_DIR_REQ_BODY_NO_FILES_LIMIT: // "CONFIG_DIR_REQ_BODY_NO_FILES_LIMIT"
      case symbol_kind::S_CONFIG_DIR_RES_BODY: // "CONFIG_DIR_RES_BODY"
      case symbol_kind::S_CONFIG_DIR_RES_BODY_LIMIT: // "CONFIG_DIR_RES_BODY_LIMIT"
      case symbol_kind::S_CONFIG_DIR_RES_BODY_LIMIT_ACTION: // "CONFIG_DIR_RES_BODY_LIMIT_ACTION"
      case symbol_kind::S_CONFIG_SEC_RULE_INHERITANCE: // "CONFIG_SEC_RULE_INHERITANCE"
      case symbol_kind::S_CONFIG_SEC_RULE_PERF_TIME: // "CONFIG_SEC_RULE_PERF_TIME"
      case symbol_kind::S_CONFIG_DIR_RULE_ENG: // "CONFIG_DIR_RULE_ENG"
      case symbol_kind::S_CONFIG_DIR_SEC_ACTION: // "CONFIG_DIR_SEC_ACTION"
      case symbol_kind::S_CONFIG_DIR_SEC_DEFAULT_ACTION: // "CONFIG_DIR_SEC_DEFAULT_ACTION"
      case symbol_kind::S_CONFIG_DIR_SEC_MARKER: // "CONFIG_DIR_SEC_MARKER"
      case symbol_kind::S_CONFIG_DIR_UNICODE_MAP_FILE: // "CONFIG_DIR_UNICODE_MAP_FILE"
      case symbol_kind::S_CONFIG_DIR_UNICODE_CODE_PAGE: // "CONFIG_DIR_UNICODE_CODE_PAGE"
      case symbol_kind::S_CONFIG_SEC_COLLECTION_TIMEOUT: // "CONFIG_SEC_COLLECTION_TIMEOUT"
      case symbol_kind::S_CONFIG_SEC_HTTP_BLKEY: // "CONFIG_SEC_HTTP_BLKEY"
      case symbol_kind::S_CONFIG_SEC_INTERCEPT_ON_ERROR: // "CONFIG_SEC_INTERCEPT_ON_ERROR"
      case symbol_kind::S_CONFIG_SEC_REMOTE_RULES_FAIL_ACTION: // "CONFIG_SEC_REMOTE_RULES_FAIL_ACTION"
      case symbol_kind::S_CONFIG_SEC_RULE_REMOVE_BY_ID: // "CONFIG_SEC_RULE_REMOVE_BY_ID"
      case symbol_kind::S_CONFIG_SEC_RULE_REMOVE_BY_MSG: // "CONFIG_SEC_RULE_REMOVE_BY_MSG"
      case symbol_kind::S_CONFIG_SEC_RULE_REMOVE_BY_TAG: // "CONFIG_SEC_RULE_REMOVE_BY_TAG"
      case symbol_kind::S_CONFIG_SEC_RULE_UPDATE_TARGET_BY_TAG: // "CONFIG_SEC_RULE_UPDATE_TARGET_BY_TAG"
      case symbol_kind::S_CONFIG_SEC_RULE_UPDATE_TARGET_BY_MSG: // "CONFIG_SEC_RULE_UPDATE_TARGET_BY_MSG"
      case symbol_kind::S_CONFIG_SEC_RULE_UPDATE_TARGET_BY_ID: // "CONFIG_SEC_RULE_UPDATE_TARGET_BY_ID"
      case symbol_kind::S_CONFIG_SEC_RULE_UPDATE_ACTION_BY_ID: // "CONFIG_SEC_RULE_UPDATE_ACTION_BY_ID"
      case symbol_kind::S_CONFIG_UPDLOAD_KEEP_FILES: // "CONFIG_UPDLOAD_KEEP_FILES"
      case symbol_kind::S_CONFIG_UPDLOAD_SAVE_TMP_FILES: // "CONFIG_UPDLOAD_SAVE_TMP_FILES"
      case symbol_kind::S_CONFIG_UPLOAD_DIR: // "CONFIG_UPLOAD_DIR"
      case symbol_kind::S_CONFIG_UPLOAD_FILE_LIMIT: // "CONFIG_UPLOAD_FILE_LIMIT"
      case symbol_kind::S_CONFIG_UPLOAD_FILE_MODE: // "CONFIG_UPLOAD_FILE_MODE"
      case symbol_kind::S_CONFIG_VALUE_ABORT: // "CONFIG_VALUE_ABORT"
      case symbol_kind::S_CONFIG_VALUE_DETC: // "CONFIG_VALUE_DETC"
      case symbol_kind::S_CONFIG_VALUE_HTTPS: // "CONFIG_VALUE_HTTPS"
      case symbol_kind::S_CONFIG_VALUE_ONLYARGS: // "CONFIG_VALUE_ONLYARGS"
      case symbol_kind::S_CONFIG_VALUE_OFF: // "CONFIG_VALUE_OFF"
      case symbol_kind::S_CONFIG_VALUE_ON: // "CONFIG_VALUE_ON"
      case symbol_kind::S_CONFIG_VALUE_PARALLEL: // "CONFIG_VALUE_PARALLEL"
      case symbol_kind::S_CONFIG_VALUE_PROCESS_PARTIAL: // "CONFIG_VALUE_PROCESS_PARTIAL"
      case symbol_kind::S_CONFIG_VALUE_REJECT: // "CONFIG_VALUE_REJECT"
      case symbol_kind::S_CONFIG_VALUE_RELEVANT_ONLY: // "CONFIG_VALUE_RELEVANT_ONLY"
      case symbol_kind::S_CONFIG_VALUE_SERIAL: // "CONFIG_VALUE_SERIAL"
      case symbol_kind::S_CONFIG_VALUE_WARN: // "CONFIG_VALUE_WARN"
      case symbol_kind::S_CONFIG_XML_EXTERNAL_ENTITY: // "CONFIG_XML_EXTERNAL_ENTITY"
      case symbol_kind::S_CONFIG_XML_PARSE_XML_INTO_ARGS: // "CONFIG_XML_PARSE_XML_INTO_ARGS"
      case symbol_kind::S_CONGIG_DIR_RESPONSE_BODY_MP: // "CONGIG_DIR_RESPONSE_BODY_MP"
      case symbol_kind::S_CONGIG_DIR_SEC_ARG_SEP: // "CONGIG_DIR_SEC_ARG_SEP"
      case symbol_kind::S_CONGIG_DIR_SEC_COOKIE_FORMAT: // "CONGIG_DIR_SEC_COOKIE_FORMAT"
      case symbol_kind::S_CONFIG_SEC_COOKIEV0_SEPARATOR: // "CONFIG_SEC_COOKIEV0_SEPARATOR"
      case symbol_kind::S_CONGIG_DIR_SEC_DATA_DIR: // "CONGIG_DIR_SEC_DATA_DIR"
      case symbol_kind::S_CONGIG_DIR_SEC_STATUS_ENGINE: // "CONGIG_DIR_SEC_STATUS_ENGINE"
      case symbol_kind::S_CONFIG_SEC_STREAM_IN_BODY_INSPECTION: // "CONFIG_SEC_STREAM_IN_BODY_INSPECTION"
      case symbol_kind::S_CONFIG_SEC_STREAM_OUT_BODY_INSPECTION: // "CONFIG_SEC_STREAM_OUT_BODY_INSPECTION"
      case symbol_kind::S_CONGIG_DIR_SEC_TMP_DIR: // "CONGIG_DIR_SEC_TMP_DIR"
      case symbol_kind::S_DIRECTIVE: // "DIRECTIVE"
      case symbol_kind::S_DIRECTIVE_SECRULESCRIPT: // "DIRECTIVE_SECRULESCRIPT"
      case symbol_kind::S_FREE_TEXT_QUOTE_MACRO_EXPANSION: // "FREE_TEXT_QUOTE_MACRO_EXPANSION"
      case symbol_kind::S_QUOTATION_MARK: // "QUOTATION_MARK"
      case symbol_kind::S_RUN_TIME_VAR_BLD: // "RUN_TIME_VAR_BLD"
      case symbol_kind::S_RUN_TIME_VAR_DUR: // "RUN_TIME_VAR_DUR"
      case symbol_kind::S_RUN_TIME_VAR_HSV: // "RUN_TIME_VAR_HSV"
      case symbol_kind::S_RUN_TIME_VAR_REMOTE_USER: // "RUN_TIME_VAR_REMOTE_USER"
      case symbol_kind::S_RUN_TIME_VAR_TIME: // "RUN_TIME_VAR_TIME"
      case symbol_kind::S_RUN_TIME_VAR_TIME_DAY: // "RUN_TIME_VAR_TIME_DAY"
      case symbol_kind::S_RUN_TIME_VAR_TIME_EPOCH: // "RUN_TIME_VAR_TIME_EPOCH"
      case symbol_kind::S_RUN_TIME_VAR_TIME_HOUR: // "RUN_TIME_VAR_TIME_HOUR"
      case symbol_kind::S_RUN_TIME_VAR_TIME_MIN: // "RUN_TIME_VAR_TIME_MIN"
      case symbol_kind::S_RUN_TIME_VAR_TIME_MON: // "RUN_TIME_VAR_TIME_MON"
      case symbol_kind::S_RUN_TIME_VAR_TIME_SEC: // "RUN_TIME_VAR_TIME_SEC"
      case symbol_kind::S_RUN_TIME_VAR_TIME_WDAY: // "RUN_TIME_VAR_TIME_WDAY"
      case symbol_kind::S_RUN_TIME_VAR_TIME_YEAR: // "RUN_TIME_VAR_TIME_YEAR"
      case symbol_kind::S_VARIABLE: // "VARIABLE"
      case symbol_kind::S_DICT_ELEMENT: // "Dictionary element"
      case symbol_kind::S_DICT_ELEMENT_WITH_EQUALS: // "Dictionary element, with equals"
      case symbol_kind::S_DICT_ELEMENT_REGEXP: // "Dictionary element, selected by regexp"
        value.copy< std::string > (YY_MOVE (that.value));
        break;

      case symbol_kind::S_op: // op
      case symbol_kind::S_op_before_init: // op_before_init
        value.copy< std::unique_ptr<Operator> > (YY_MOVE (that.value));
        break;

      case symbol_kind::S_run_time_string: // run_time_string
        value.copy< std::unique_ptr<RunTimeString> > (YY_MOVE (that.value));
        break;

      case symbol_kind::S_var: // var
        value.copy< std::unique_ptr<Variable> > (YY_MOVE (that.value));
        break;

      case symbol_kind::S_act: // act
      case symbol_kind::S_setvar_action: // setvar_action
        value.copy< std::unique_ptr<actions::Action> > (YY_MOVE (that.value));
        break;

      case symbol_kind::S_variables: // variables
      case symbol_kind::S_variables_pre_process: // variables_pre_process
      case symbol_kind::S_variables_may_be_quoted: // variables_may_be_quoted
        value.copy< std::unique_ptr<std::vector<std::unique_ptr<Variable> > >  > (YY_MOVE (that.value));
        break;

      case symbol_kind::S_actions: // actions
      case symbol_kind::S_actions_may_quoted: // actions_may_quoted
        value.copy< std::unique_ptr<std::vector<std::unique_ptr<actions::Action> > >  > (YY_MOVE (that.value));
        break;

      default:
        break;
    }

  }




  template <typename Base>
  seclang_parser::symbol_kind_type
  seclang_parser::basic_symbol<Base>::type_get () const YY_NOEXCEPT
  {
    return this->kind ();
  }


  template <typename Base>
  bool
  seclang_parser::basic_symbol<Base>::empty () const YY_NOEXCEPT
  {
    return this->kind () == symbol_kind::S_YYEMPTY;
  }

  template <typename Base>
  void
  seclang_parser::basic_symbol<Base>::move (basic_symbol& s)
  {
    super_type::move (s);
    switch (this->kind ())
    {
      case symbol_kind::S_ACTION_ACCURACY: // "Accuracy"
      case symbol_kind::S_ACTION_ALLOW: // "Allow"
      case symbol_kind::S_ACTION_APPEND: // "Append"
      case symbol_kind::S_ACTION_AUDIT_LOG: // "AuditLog"
      case symbol_kind::S_ACTION_BLOCK: // "Block"
      case symbol_kind::S_ACTION_CAPTURE: // "Capture"
      case symbol_kind::S_ACTION_CHAIN: // "Chain"
      case symbol_kind::S_ACTION_CTL_AUDIT_ENGINE: // "ACTION_CTL_AUDIT_ENGINE"
      case symbol_kind::S_ACTION_CTL_AUDIT_LOG_PARTS: // "ACTION_CTL_AUDIT_LOG_PARTS"
      case symbol_kind::S_ACTION_CTL_BDY_JSON: // "ACTION_CTL_BDY_JSON"
      case symbol_kind::S_ACTION_CTL_BDY_XML: // "ACTION_CTL_BDY_XML"
      case symbol_kind::S_ACTION_CTL_BDY_URLENCODED: // "ACTION_CTL_BDY_URLENCODED"
      case symbol_kind::S_ACTION_CTL_FORCE_REQ_BODY_VAR: // "ACTION_CTL_FORCE_REQ_BODY_VAR"
      case symbol_kind::S_ACTION_CTL_PARSE_XML_INTO_ARGS: // "ACTION_CTL_PARSE_XML_INTO_ARGS"
      case symbol_kind::S_ACTION_CTL_REQUEST_BODY_ACCESS: // "ACTION_CTL_REQUEST_BODY_ACCESS"
      case symbol_kind::S_ACTION_CTL_RULE_REMOVE_BY_ID: // "ACTION_CTL_RULE_REMOVE_BY_ID"
      case symbol_kind::S_ACTION_CTL_RULE_REMOVE_BY_TAG: // "ACTION_CTL_RULE_REMOVE_BY_TAG"
      case symbol_kind::S_ACTION_CTL_RULE_REMOVE_TARGET_BY_ID: // "ACTION_CTL_RULE_REMOVE_TARGET_BY_ID"
      case symbol_kind::S_ACTION_CTL_RULE_REMOVE_TARGET_BY_TAG: // "ACTION_CTL_RULE_REMOVE_TARGET_BY_TAG"
      case symbol_kind::S_ACTION_DENY: // "Deny"
      case symbol_kind::S_ACTION_DEPRECATE_VAR: // "DeprecateVar"
      case symbol_kind::S_ACTION_DROP: // "Drop"
      case symbol_kind::S_ACTION_EXEC: // "Exec"
      case symbol_kind::S_ACTION_EXPIRE_VAR: // "ExpireVar"
      case symbol_kind::S_ACTION_ID: // "Id"
      case symbol_kind::S_ACTION_INITCOL: // "InitCol"
      case symbol_kind::S_ACTION_LOG: // "Log"
      case symbol_kind::S_ACTION_LOG_DATA: // "LogData"
      case symbol_kind::S_ACTION_MATURITY: // "Maturity"
      case symbol_kind::S_ACTION_MSG: // "Msg"
      case symbol_kind::S_ACTION_MULTI_MATCH: // "MultiMatch"
      case symbol_kind::S_ACTION_NO_AUDIT_LOG: // "NoAuditLog"
      case symbol_kind::S_ACTION_NO_LOG: // "NoLog"
      case symbol_kind::S_ACTION_PASS: // "Pass"
      case symbol_kind::S_ACTION_PAUSE: // "Pause"
      case symbol_kind::S_ACTION_PHASE: // "Phase"
      case symbol_kind::S_ACTION_PREPEND: // "Prepend"
      case symbol_kind::S_ACTION_PROXY: // "Proxy"
      case symbol_kind::S_ACTION_REDIRECT: // "Redirect"
      case symbol_kind::S_ACTION_REV: // "Rev"
      case symbol_kind::S_ACTION_SANITISE_ARG: // "SanitiseArg"
      case symbol_kind::S_ACTION_SANITISE_MATCHED: // "SanitiseMatched"
      case symbol_kind::S_ACTION_SANITISE_MATCHED_BYTES: // "SanitiseMatchedBytes"
      case symbol_kind::S_ACTION_SANITISE_REQUEST_HEADER: // "SanitiseRequestHeader"
      case symbol_kind::S_ACTION_SANITISE_RESPONSE_HEADER: // "SanitiseResponseHeader"
      case symbol_kind::S_ACTION_SETENV: // "SetEnv"
      case symbol_kind::S_ACTION_SETRSC: // "SetRsc"
      case symbol_kind::S_ACTION_SETSID: // "SetSid"
      case symbol_kind::S_ACTION_SETUID: // "SetUID"
      case symbol_kind::S_ACTION_SEVERITY: // "Severity"
      case symbol_kind::S_ACTION_SKIP: // "Skip"
      case symbol_kind::S_ACTION_SKIP_AFTER: // "SkipAfter"
      case symbol_kind::S_ACTION_STATUS: // "Status"
      case symbol_kind::S_ACTION_TAG: // "Tag"
      case symbol_kind::S_ACTION_TRANSFORMATION_BASE_64_ENCODE: // "ACTION_TRANSFORMATION_BASE_64_ENCODE"
      case symbol_kind::S_ACTION_TRANSFORMATION_BASE_64_DECODE: // "ACTION_TRANSFORMATION_BASE_64_DECODE"
      case symbol_kind::S_ACTION_TRANSFORMATION_BASE_64_DECODE_EXT: // "ACTION_TRANSFORMATION_BASE_64_DECODE_EXT"
      case symbol_kind::S_ACTION_TRANSFORMATION_CMD_LINE: // "ACTION_TRANSFORMATION_CMD_LINE"
      case symbol_kind::S_ACTION_TRANSFORMATION_COMPRESS_WHITESPACE: // "ACTION_TRANSFORMATION_COMPRESS_WHITESPACE"
      case symbol_kind::S_ACTION_TRANSFORMATION_CSS_DECODE: // "ACTION_TRANSFORMATION_CSS_DECODE"
      case symbol_kind::S_ACTION_TRANSFORMATION_ESCAPE_SEQ_DECODE: // "ACTION_TRANSFORMATION_ESCAPE_SEQ_DECODE"
      case symbol_kind::S_ACTION_TRANSFORMATION_HEX_ENCODE: // "ACTION_TRANSFORMATION_HEX_ENCODE"
      case symbol_kind::S_ACTION_TRANSFORMATION_HEX_DECODE: // "ACTION_TRANSFORMATION_HEX_DECODE"
      case symbol_kind::S_ACTION_TRANSFORMATION_HTML_ENTITY_DECODE: // "ACTION_TRANSFORMATION_HTML_ENTITY_DECODE"
      case symbol_kind::S_ACTION_TRANSFORMATION_JS_DECODE: // "ACTION_TRANSFORMATION_JS_DECODE"
      case symbol_kind::S_ACTION_TRANSFORMATION_LENGTH: // "ACTION_TRANSFORMATION_LENGTH"
      case symbol_kind::S_ACTION_TRANSFORMATION_LOWERCASE: // "ACTION_TRANSFORMATION_LOWERCASE"
      case symbol_kind::S_ACTION_TRANSFORMATION_MD5: // "ACTION_TRANSFORMATION_MD5"
      case symbol_kind::S_ACTION_TRANSFORMATION_NONE: // "ACTION_TRANSFORMATION_NONE"
      case symbol_kind::S_ACTION_TRANSFORMATION_NORMALISE_PATH: // "ACTION_TRANSFORMATION_NORMALISE_PATH"
      case symbol_kind::S_ACTION_TRANSFORMATION_NORMALISE_PATH_WIN: // "ACTION_TRANSFORMATION_NORMALISE_PATH_WIN"
      case symbol_kind::S_ACTION_TRANSFORMATION_PARITY_EVEN_7_BIT: // "ACTION_TRANSFORMATION_PARITY_EVEN_7_BIT"
      case symbol_kind::S_ACTION_TRANSFORMATION_PARITY_ODD_7_BIT: // "ACTION_TRANSFORMATION_PARITY_ODD_7_BIT"
      case symbol_kind::S_ACTION_TRANSFORMATION_PARITY_ZERO_7_BIT: // "ACTION_TRANSFORMATION_PARITY_ZERO_7_BIT"
      case symbol_kind::S_ACTION_TRANSFORMATION_REMOVE_COMMENTS: // "ACTION_TRANSFORMATION_REMOVE_COMMENTS"
      case symbol_kind::S_ACTION_TRANSFORMATION_REMOVE_COMMENTS_CHAR: // "ACTION_TRANSFORMATION_REMOVE_COMMENTS_CHAR"
      case symbol_kind::S_ACTION_TRANSFORMATION_REMOVE_NULLS: // "ACTION_TRANSFORMATION_REMOVE_NULLS"
      case symbol_kind::S_ACTION_TRANSFORMATION_REMOVE_WHITESPACE: // "ACTION_TRANSFORMATION_REMOVE_WHITESPACE"
      case symbol_kind::S_ACTION_TRANSFORMATION_REPLACE_COMMENTS: // "ACTION_TRANSFORMATION_REPLACE_COMMENTS"
      case symbol_kind::S_ACTION_TRANSFORMATION_REPLACE_NULLS: // "ACTION_TRANSFORMATION_REPLACE_NULLS"
      case symbol_kind::S_ACTION_TRANSFORMATION_SHA1: // "ACTION_TRANSFORMATION_SHA1"
      case symbol_kind::S_ACTION_TRANSFORMATION_SQL_HEX_DECODE: // "ACTION_TRANSFORMATION_SQL_HEX_DECODE"
      case symbol_kind::S_ACTION_TRANSFORMATION_TRIM: // "ACTION_TRANSFORMATION_TRIM"
      case symbol_kind::S_ACTION_TRANSFORMATION_TRIM_LEFT: // "ACTION_TRANSFORMATION_TRIM_LEFT"
      case symbol_kind::S_ACTION_TRANSFORMATION_TRIM_RIGHT: // "ACTION_TRANSFORMATION_TRIM_RIGHT"
      case symbol_kind::S_ACTION_TRANSFORMATION_UPPERCASE: // "ACTION_TRANSFORMATION_UPPERCASE"
      case symbol_kind::S_ACTION_TRANSFORMATION_URL_ENCODE: // "ACTION_TRANSFORMATION_URL_ENCODE"
      case symbol_kind::S_ACTION_TRANSFORMATION_URL_DECODE: // "ACTION_TRANSFORMATION_URL_DECODE"
      case symbol_kind::S_ACTION_TRANSFORMATION_URL_DECODE_UNI: // "ACTION_TRANSFORMATION_URL_DECODE_UNI"
      case symbol_kind::S_ACTION_TRANSFORMATION_UTF8_TO_UNICODE: // "ACTION_TRANSFORMATION_UTF8_TO_UNICODE"
      case symbol_kind::S_ACTION_VER: // "Ver"
      case symbol_kind::S_ACTION_XMLNS: // "xmlns"
      case symbol_kind::S_CONFIG_COMPONENT_SIG: // "CONFIG_COMPONENT_SIG"
      case symbol_kind::S_CONFIG_CONN_ENGINE: // "CONFIG_CONN_ENGINE"
      case symbol_kind::S_CONFIG_SEC_ARGUMENT_SEPARATOR: // "CONFIG_SEC_ARGUMENT_SEPARATOR"
      case symbol_kind::S_CONFIG_SEC_WEB_APP_ID: // "CONFIG_SEC_WEB_APP_ID"
      case symbol_kind::S_CONFIG_SEC_SERVER_SIG: // "CONFIG_SEC_SERVER_SIG"
      case symbol_kind::S_CONFIG_DIR_AUDIT_DIR: // "CONFIG_DIR_AUDIT_DIR"
      case symbol_kind::S_CONFIG_DIR_AUDIT_DIR_MOD: // "CONFIG_DIR_AUDIT_DIR_MOD"
      case symbol_kind::S_CONFIG_DIR_AUDIT_ENG: // "CONFIG_DIR_AUDIT_ENG"
      case symbol_kind::S_CONFIG_DIR_AUDIT_FLE_MOD: // "CONFIG_DIR_AUDIT_FLE_MOD"
      case symbol_kind::S_CONFIG_DIR_AUDIT_LOG: // "CONFIG_DIR_AUDIT_LOG"
      case symbol_kind::S_CONFIG_DIR_AUDIT_LOG2: // "CONFIG_DIR_AUDIT_LOG2"
      case symbol_kind::S_CONFIG_DIR_AUDIT_LOG_P: // "CONFIG_DIR_AUDIT_LOG_P"
      case symbol_kind::S_CONFIG_DIR_AUDIT_STS: // "CONFIG_DIR_AUDIT_STS"
      case symbol_kind::S_CONFIG_DIR_AUDIT_PREFIX: // "CONFIG_DIR_AUDIT_PREFIX"
      case symbol_kind::S_CONFIG_DIR_AUDIT_TPE: // "CONFIG_DIR_AUDIT_TPE"
      case symbol_kind::S_CONFIG_DIR_DEBUG_LOG: // "CONFIG_DIR_DEBUG_LOG"
      case symbol_kind::S_CONFIG_DIR_DEBUG_LVL: // "CONFIG_DIR_DEBUG_LVL"
      case symbol_kind::S_CONFIG_SEC_CACHE_TRANSFORMATIONS: // "CONFIG_SEC_CACHE_TRANSFORMATIONS"
      case symbol_kind::S_CONFIG_SEC_DISABLE_BACKEND_COMPRESS: // "CONFIG_SEC_DISABLE_BACKEND_COMPRESS"
      case symbol_kind::S_CONFIG_SEC_HASH_ENGINE: // "CONFIG_SEC_HASH_ENGINE"
      case symbol_kind::S_CONFIG_SEC_HASH_KEY: // "CONFIG_SEC_HASH_KEY"
      case symbol_kind::S_CONFIG_SEC_HASH_PARAM: // "CONFIG_SEC_HASH_PARAM"
      case symbol_kind::S_CONFIG_SEC_HASH_METHOD_RX: // "CONFIG_SEC_HASH_METHOD_RX"
      case symbol_kind::S_CONFIG_SEC_HASH_METHOD_PM: // "CONFIG_SEC_HASH_METHOD_PM"
      case symbol_kind::S_CONFIG_SEC_CHROOT_DIR: // "CONFIG_SEC_CHROOT_DIR"
      case symbol_kind::S_CONFIG_DIR_GEO_DB: // "CONFIG_DIR_GEO_DB"
      case symbol_kind::S_CONFIG_DIR_GSB_DB: // "CONFIG_DIR_GSB_DB"
      case symbol_kind::S_CONFIG_SEC_GUARDIAN_LOG: // "CONFIG_SEC_GUARDIAN_LOG"
      case symbol_kind::S_CONFIG_DIR_PCRE_MATCH_LIMIT: // "CONFIG_DIR_PCRE_MATCH_LIMIT"
      case symbol_kind::S_CONFIG_DIR_PCRE_MATCH_LIMIT_RECURSION: // "CONFIG_DIR_PCRE_MATCH_LIMIT_RECURSION"
      case symbol_kind::S_CONFIG_SEC_CONN_R_STATE_LIMIT: // "CONFIG_SEC_CONN_R_STATE_LIMIT"
      case symbol_kind::S_CONFIG_SEC_CONN_W_STATE_LIMIT: // "CONFIG_SEC_CONN_W_STATE_LIMIT"
      case symbol_kind::S_CONFIG_SEC_SENSOR_ID: // "CONFIG_SEC_SENSOR_ID"
      case symbol_kind::S_CONFIG_DIR_ARGS_LIMIT: // "CONFIG_DIR_ARGS_LIMIT"
      case symbol_kind::S_CONFIG_DIR_REQ_BODY_JSON_DEPTH_LIMIT: // "CONFIG_DIR_REQ_BODY_JSON_DEPTH_LIMIT"
      case symbol_kind::S_CONFIG_DIR_REQ_BODY: // "CONFIG_DIR_REQ_BODY"
      case symbol_kind::S_CONFIG_DIR_REQ_BODY_IN_MEMORY_LIMIT: // "CONFIG_DIR_REQ_BODY_IN_MEMORY_LIMIT"
      case symbol_kind::S_CONFIG_DIR_REQ_BODY_LIMIT: // "CONFIG_DIR_REQ_BODY_LIMIT"
      case symbol_kind::S_CONFIG_DIR_REQ_BODY_LIMIT_ACTION: // "CONFIG_DIR_REQ_BODY_LIMIT_ACTION"
      case symbol_kind::S_CONFIG_DIR_REQ_BODY_NO_FILES_LIMIT: // "CONFIG_DIR_REQ_BODY_NO_FILES_LIMIT"
      case symbol_kind::S_CONFIG_DIR_RES_BODY: // "CONFIG_DIR_RES_BODY"
      case symbol_kind::S_CONFIG_DIR_RES_BODY_LIMIT: // "CONFIG_DIR_RES_BODY_LIMIT"
      case symbol_kind::S_CONFIG_DIR_RES_BODY_LIMIT_ACTION: // "CONFIG_DIR_RES_BODY_LIMIT_ACTION"
      case symbol_kind::S_CONFIG_SEC_RULE_INHERITANCE: // "CONFIG_SEC_RULE_INHERITANCE"
      case symbol_kind::S_CONFIG_SEC_RULE_PERF_TIME: // "CONFIG_SEC_RULE_PERF_TIME"
      case symbol_kind::S_CONFIG_DIR_RULE_ENG: // "CONFIG_DIR_RULE_ENG"
      case symbol_kind::S_CONFIG_DIR_SEC_ACTION: // "CONFIG_DIR_SEC_ACTION"
      case symbol_kind::S_CONFIG_DIR_SEC_DEFAULT_ACTION: // "CONFIG_DIR_SEC_DEFAULT_ACTION"
      case symbol_kind::S_CONFIG_DIR_SEC_MARKER: // "CONFIG_DIR_SEC_MARKER"
      case symbol_kind::S_CONFIG_DIR_UNICODE_MAP_FILE: // "CONFIG_DIR_UNICODE_MAP_FILE"
      case symbol_kind::S_CONFIG_DIR_UNICODE_CODE_PAGE: // "CONFIG_DIR_UNICODE_CODE_PAGE"
      case symbol_kind::S_CONFIG_SEC_COLLECTION_TIMEOUT: // "CONFIG_SEC_COLLECTION_TIMEOUT"
      case symbol_kind::S_CONFIG_SEC_HTTP_BLKEY: // "CONFIG_SEC_HTTP_BLKEY"
      case symbol_kind::S_CONFIG_SEC_INTERCEPT_ON_ERROR: // "CONFIG_SEC_INTERCEPT_ON_ERROR"
      case symbol_kind::S_CONFIG_SEC_REMOTE_RULES_FAIL_ACTION: // "CONFIG_SEC_REMOTE_RULES_FAIL_ACTION"
      case symbol_kind::S_CONFIG_SEC_RULE_REMOVE_BY_ID: // "CONFIG_SEC_RULE_REMOVE_BY_ID"
      case symbol_kind::S_CONFIG_SEC_RULE_REMOVE_BY_MSG: // "CONFIG_SEC_RULE_REMOVE_BY_MSG"
      case symbol_kind::S_CONFIG_SEC_RULE_REMOVE_BY_TAG: // "CONFIG_SEC_RULE_REMOVE_BY_TAG"
      case symbol_kind::S_CONFIG_SEC_RULE_UPDATE_TARGET_BY_TAG: // "CONFIG_SEC_RULE_UPDATE_TARGET_BY_TAG"
      case symbol_kind::S_CONFIG_SEC_RULE_UPDATE_TARGET_BY_MSG: // "CONFIG_SEC_RULE_UPDATE_TARGET_BY_MSG"
      case symbol_kind::S_CONFIG_SEC_RULE_UPDATE_TARGET_BY_ID: // "CONFIG_SEC_RULE_UPDATE_TARGET_BY_ID"
      case symbol_kind::S_CONFIG_SEC_RULE_UPDATE_ACTION_BY_ID: // "CONFIG_SEC_RULE_UPDATE_ACTION_BY_ID"
      case symbol_kind::S_CONFIG_UPDLOAD_KEEP_FILES: // "CONFIG_UPDLOAD_KEEP_FILES"
      case symbol_kind::S_CONFIG_UPDLOAD_SAVE_TMP_FILES: // "CONFIG_UPDLOAD_SAVE_TMP_FILES"
      case symbol_kind::S_CONFIG_UPLOAD_DIR: // "CONFIG_UPLOAD_DIR"
      case symbol_kind::S_CONFIG_UPLOAD_FILE_LIMIT: // "CONFIG_UPLOAD_FILE_LIMIT"
      case symbol_kind::S_CONFIG_UPLOAD_FILE_MODE: // "CONFIG_UPLOAD_FILE_MODE"
      case symbol_kind::S_CONFIG_VALUE_ABORT: // "CONFIG_VALUE_ABORT"
      case symbol_kind::S_CONFIG_VALUE_DETC: // "CONFIG_VALUE_DETC"
      case symbol_kind::S_CONFIG_VALUE_HTTPS: // "CONFIG_VALUE_HTTPS"
      case symbol_kind::S_CONFIG_VALUE_ONLYARGS: // "CONFIG_VALUE_ONLYARGS"
      case symbol_kind::S_CONFIG_VALUE_OFF: // "CONFIG_VALUE_OFF"
      case symbol_kind::S_CONFIG_VALUE_ON: // "CONFIG_VALUE_ON"
      case symbol_kind::S_CONFIG_VALUE_PARALLEL: // "CONFIG_VALUE_PARALLEL"
      case symbol_kind::S_CONFIG_VALUE_PROCESS_PARTIAL: // "CONFIG_VALUE_PROCESS_PARTIAL"
      case symbol_kind::S_CONFIG_VALUE_REJECT: // "CONFIG_VALUE_REJECT"
      case symbol_kind::S_CONFIG_VALUE_RELEVANT_ONLY: // "CONFIG_VALUE_RELEVANT_ONLY"
      case symbol_kind::S_CONFIG_VALUE_SERIAL: // "CONFIG_VALUE_SERIAL"
      case symbol_kind::S_CONFIG_VALUE_WARN: // "CONFIG_VALUE_WARN"
      case symbol_kind::S_CONFIG_XML_EXTERNAL_ENTITY: // "CONFIG_XML_EXTERNAL_ENTITY"
      case symbol_kind::S_CONFIG_XML_PARSE_XML_INTO_ARGS: // "CONFIG_XML_PARSE_XML_INTO_ARGS"
      case symbol_kind::S_CONGIG_DIR_RESPONSE_BODY_MP: // "CONGIG_DIR_RESPONSE_BODY_MP"
      case symbol_kind::S_CONGIG_DIR_SEC_ARG_SEP: // "CONGIG_DIR_SEC_ARG_SEP"
      case symbol_kind::S_CONGIG_DIR_SEC_COOKIE_FORMAT: // "CONGIG_DIR_SEC_COOKIE_FORMAT"
      case symbol_kind::S_CONFIG_SEC_COOKIEV0_SEPARATOR: // "CONFIG_SEC_COOKIEV0_SEPARATOR"
      case symbol_kind::S_CONGIG_DIR_SEC_DATA_DIR: // "CONGIG_DIR_SEC_DATA_DIR"
      case symbol_kind::S_CONGIG_DIR_SEC_STATUS_ENGINE: // "CONGIG_DIR_SEC_STATUS_ENGINE"
      case symbol_kind::S_CONFIG_SEC_STREAM_IN_BODY_INSPECTION: // "CONFIG_SEC_STREAM_IN_BODY_INSPECTION"
      case symbol_kind::S_CONFIG_SEC_STREAM_OUT_BODY_INSPECTION: // "CONFIG_SEC_STREAM_OUT_BODY_INSPECTION"
      case symbol_kind::S_CONGIG_DIR_SEC_TMP_DIR: // "CONGIG_DIR_SEC_TMP_DIR"
      case symbol_kind::S_DIRECTIVE: // "DIRECTIVE"
      case symbol_kind::S_DIRECTIVE_SECRULESCRIPT: // "DIRECTIVE_SECRULESCRIPT"
      case symbol_kind::S_FREE_TEXT_QUOTE_MACRO_EXPANSION: // "FREE_TEXT_QUOTE_MACRO_EXPANSION"
      case symbol_kind::S_QUOTATION_MARK: // "QUOTATION_MARK"
      case symbol_kind::S_RUN_TIME_VAR_BLD: // "RUN_TIME_VAR_BLD"
      case symbol_kind::S_RUN_TIME_VAR_DUR: // "RUN_TIME_VAR_DUR"
      case symbol_kind::S_RUN_TIME_VAR_HSV: // "RUN_TIME_VAR_HSV"
      case symbol_kind::S_RUN_TIME_VAR_REMOTE_USER: // "RUN_TIME_VAR_REMOTE_USER"
      case symbol_kind::S_RUN_TIME_VAR_TIME: // "RUN_TIME_VAR_TIME"
      case symbol_kind::S_RUN_TIME_VAR_TIME_DAY: // "RUN_TIME_VAR_TIME_DAY"
      case symbol_kind::S_RUN_TIME_VAR_TIME_EPOCH: // "RUN_TIME_VAR_TIME_EPOCH"
      case symbol_kind::S_RUN_TIME_VAR_TIME_HOUR: // "RUN_TIME_VAR_TIME_HOUR"
      case symbol_kind::S_RUN_TIME_VAR_TIME_MIN: // "RUN_TIME_VAR_TIME_MIN"
      case symbol_kind::S_RUN_TIME_VAR_TIME_MON: // "RUN_TIME_VAR_TIME_MON"
      case symbol_kind::S_RUN_TIME_VAR_TIME_SEC: // "RUN_TIME_VAR_TIME_SEC"
      case symbol_kind::S_RUN_TIME_VAR_TIME_WDAY: // "RUN_TIME_VAR_TIME_WDAY"
      case symbol_kind::S_RUN_TIME_VAR_TIME_YEAR: // "RUN_TIME_VAR_TIME_YEAR"
      case symbol_kind::S_VARIABLE: // "VARIABLE"
      case symbol_kind::S_DICT_ELEMENT: // "Dictionary element"
      case symbol_kind::S_DICT_ELEMENT_WITH_EQUALS: // "Dictionary element, with equals"
      case symbol_kind::S_DICT_ELEMENT_REGEXP: // "Dictionary element, selected by regexp"
        value.move< std::string > (YY_MOVE (s.value));
        break;

      case symbol_kind::S_op: // op
      case symbol_kind::S_op_before_init: // op_before_init
        value.move< std::unique_ptr<Operator> > (YY_MOVE (s.value));
        break;

      case symbol_kind::S_run_time_string: // run_time_string
        value.move< std::unique_ptr<RunTimeString> > (YY_MOVE (s.value));
        break;

      case symbol_kind::S_var: // var
        value.move< std::unique_ptr<Variable> > (YY_MOVE (s.value));
        break;

      case symbol_kind::S_act: // act
      case symbol_kind::S_setvar_action: // setvar_action
        value.move< std::unique_ptr<actions::Action> > (YY_MOVE (s.value));
        break;

      case symbol_kind::S_variables: // variables
      case symbol_kind::S_variables_pre_process: // variables_pre_process
      case symbol_kind::S_variables_may_be_quoted: // variables_may_be_quoted
        value.move< std::unique_ptr<std::vector<std::unique_ptr<Variable> > >  > (YY_MOVE (s.value));
        break;

      case symbol_kind::S_actions: // actions
      case symbol_kind::S_actions_may_quoted: // actions_may_quoted
        value.move< std::unique_ptr<std::vector<std::unique_ptr<actions::Action> > >  > (YY_MOVE (s.value));
        break;

      default:
        break;
    }

    location = YY_MOVE (s.location);
  }

  // by_kind.
  inline
  seclang_parser::by_kind::by_kind () YY_NOEXCEPT
    : kind_ (symbol_kind::S_YYEMPTY)
  {}

#if 201103L <= YY_CPLUSPLUS
  inline
  seclang_parser::by_kind::by_kind (by_kind&& that) YY_NOEXCEPT
    : kind_ (that.kind_)
  {
    that.clear ();
  }
#endif

  inline
  seclang_parser::by_kind::by_kind (const by_kind& that) YY_NOEXCEPT
    : kind_ (that.kind_)
  {}

  inline
  seclang_parser::by_kind::by_kind (token_kind_type t) YY_NOEXCEPT
    : kind_ (yytranslate_ (t))
  {}



  inline
  void
  seclang_parser::by_kind::clear () YY_NOEXCEPT
  {
    kind_ = symbol_kind::S_YYEMPTY;
  }

  inline
  void
  seclang_parser::by_kind::move (by_kind& that)
  {
    kind_ = that.kind_;
    that.clear ();
  }

  inline
  seclang_parser::symbol_kind_type
  seclang_parser::by_kind::kind () const YY_NOEXCEPT
  {
    return kind_;
  }


  inline
  seclang_parser::symbol_kind_type
  seclang_parser::by_kind::type_get () const YY_NOEXCEPT
  {
    return this->kind ();
  }


} // yy
#line 8825 "seclang-parser.hh"




#endif // !YY_YY_SECLANG_PARSER_HH_INCLUDED
