// A Bison parser, made by GNU Bison 3.7.6.

// Skeleton implementation for Bison LALR(1) parsers in C++

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

// DO NOT RELY ON FEATURES THAT ARE NOT DOCUMENTED in the manual,
// especially those whose name start with YY_ or yy_.  They are
// private implementation details that can be changed or removed.





#include "seclang-parser.hh"


// Unqualified %code blocks.
#line 328 "seclang-parser.yy"

#include "src/parser/driver.h"

#line 50 "seclang-parser.cc"


#ifndef YY_
# if defined YYENABLE_NLS && YYENABLE_NLS
#  if ENABLE_NLS
#   include <libintl.h> // FIXME: INFRINGES ON USER NAME SPACE.
#   define YY_(msgid) dgettext ("bison-runtime", msgid)
#  endif
# endif
# ifndef YY_
#  define YY_(msgid) msgid
# endif
#endif


// Whether we are compiled with exception support.
#ifndef YY_EXCEPTIONS
# if defined __GNUC__ && !defined __EXCEPTIONS
#  define YY_EXCEPTIONS 0
# else
#  define YY_EXCEPTIONS 1
# endif
#endif

#define YYRHSLOC(Rhs, K) ((Rhs)[K].location)
/* YYLLOC_DEFAULT -- Set CURRENT to span from RHS[1] to RHS[N].
   If N is 0, then set CURRENT to the empty location which ends
   the previous symbol: RHS[0] (always defined).  */

# ifndef YYLLOC_DEFAULT
#  define YYLLOC_DEFAULT(Current, Rhs, N)                               \
    do                                                                  \
      if (N)                                                            \
        {                                                               \
          (Current).begin  = YYRHSLOC (Rhs, 1).begin;                   \
          (Current).end    = YYRHSLOC (Rhs, N).end;                     \
        }                                                               \
      else                                                              \
        {                                                               \
          (Current).begin = (Current).end = YYRHSLOC (Rhs, 0).end;      \
        }                                                               \
    while (false)
# endif


// Enable debugging if requested.
#if YYDEBUG

// A pseudo ostream that takes yydebug_ into account.
# define YYCDEBUG if (yydebug_) (*yycdebug_)

# define YY_SYMBOL_PRINT(Title, Symbol)         \
  do {                                          \
    if (yydebug_)                               \
    {                                           \
      *yycdebug_ << Title << ' ';               \
      yy_print_ (*yycdebug_, Symbol);           \
      *yycdebug_ << '\n';                       \
    }                                           \
  } while (false)

# define YY_REDUCE_PRINT(Rule)          \
  do {                                  \
    if (yydebug_)                       \
      yy_reduce_print_ (Rule);          \
  } while (false)

# define YY_STACK_PRINT()               \
  do {                                  \
    if (yydebug_)                       \
      yy_stack_print_ ();                \
  } while (false)

#else // !YYDEBUG

# define YYCDEBUG if (false) std::cerr
# define YY_SYMBOL_PRINT(Title, Symbol)  YY_USE (Symbol)
# define YY_REDUCE_PRINT(Rule)           static_cast<void> (0)
# define YY_STACK_PRINT()                static_cast<void> (0)

#endif // !YYDEBUG

#define yyerrok         (yyerrstatus_ = 0)
#define yyclearin       (yyla.clear ())

#define YYACCEPT        goto yyacceptlab
#define YYABORT         goto yyabortlab
#define YYERROR         goto yyerrorlab
#define YYRECOVERING()  (!!yyerrstatus_)

namespace yy {
#line 142 "seclang-parser.cc"

  /// Build a parser object.
  seclang_parser::seclang_parser (modsecurity::Parser::Driver& driver_yyarg)
#if YYDEBUG
    : yydebug_ (false),
      yycdebug_ (&std::cerr),
#else
    :
#endif
      driver (driver_yyarg)
  {}

  seclang_parser::~seclang_parser ()
  {}

  seclang_parser::syntax_error::~syntax_error () YY_NOEXCEPT YY_NOTHROW
  {}

  /*---------------.
  | symbol kinds.  |
  `---------------*/



  // by_state.
  seclang_parser::by_state::by_state () YY_NOEXCEPT
    : state (empty_state)
  {}

  seclang_parser::by_state::by_state (const by_state& that) YY_NOEXCEPT
    : state (that.state)
  {}

  void
  seclang_parser::by_state::clear () YY_NOEXCEPT
  {
    state = empty_state;
  }

  void
  seclang_parser::by_state::move (by_state& that)
  {
    state = that.state;
    that.clear ();
  }

  seclang_parser::by_state::by_state (state_type s) YY_NOEXCEPT
    : state (s)
  {}

  seclang_parser::symbol_kind_type
  seclang_parser::by_state::kind () const YY_NOEXCEPT
  {
    if (state == empty_state)
      return symbol_kind::S_YYEMPTY;
    else
      return YY_CAST (symbol_kind_type, yystos_[+state]);
  }

  seclang_parser::stack_symbol_type::stack_symbol_type ()
  {}

  seclang_parser::stack_symbol_type::stack_symbol_type (YY_RVREF (stack_symbol_type) that)
    : super_type (YY_MOVE (that.state), YY_MOVE (that.location))
  {
    switch (that.kind ())
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
      case symbol_kind::S_CONFIG_VALUE_OFF: // "CONFIG_VALUE_OFF"
      case symbol_kind::S_CONFIG_VALUE_ON: // "CONFIG_VALUE_ON"
      case symbol_kind::S_CONFIG_VALUE_PARALLEL: // "CONFIG_VALUE_PARALLEL"
      case symbol_kind::S_CONFIG_VALUE_PROCESS_PARTIAL: // "CONFIG_VALUE_PROCESS_PARTIAL"
      case symbol_kind::S_CONFIG_VALUE_REJECT: // "CONFIG_VALUE_REJECT"
      case symbol_kind::S_CONFIG_VALUE_RELEVANT_ONLY: // "CONFIG_VALUE_RELEVANT_ONLY"
      case symbol_kind::S_CONFIG_VALUE_SERIAL: // "CONFIG_VALUE_SERIAL"
      case symbol_kind::S_CONFIG_VALUE_WARN: // "CONFIG_VALUE_WARN"
      case symbol_kind::S_CONFIG_XML_EXTERNAL_ENTITY: // "CONFIG_XML_EXTERNAL_ENTITY"
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
        value.YY_MOVE_OR_COPY< std::string > (YY_MOVE (that.value));
        break;

      case symbol_kind::S_op: // op
      case symbol_kind::S_op_before_init: // op_before_init
        value.YY_MOVE_OR_COPY< std::unique_ptr<Operator> > (YY_MOVE (that.value));
        break;

      case symbol_kind::S_run_time_string: // run_time_string
        value.YY_MOVE_OR_COPY< std::unique_ptr<RunTimeString> > (YY_MOVE (that.value));
        break;

      case symbol_kind::S_var: // var
        value.YY_MOVE_OR_COPY< std::unique_ptr<Variable> > (YY_MOVE (that.value));
        break;

      case symbol_kind::S_act: // act
      case symbol_kind::S_setvar_action: // setvar_action
        value.YY_MOVE_OR_COPY< std::unique_ptr<actions::Action> > (YY_MOVE (that.value));
        break;

      case symbol_kind::S_variables: // variables
      case symbol_kind::S_variables_pre_process: // variables_pre_process
      case symbol_kind::S_variables_may_be_quoted: // variables_may_be_quoted
        value.YY_MOVE_OR_COPY< std::unique_ptr<std::vector<std::unique_ptr<Variable> > >  > (YY_MOVE (that.value));
        break;

      case symbol_kind::S_actions: // actions
      case symbol_kind::S_actions_may_quoted: // actions_may_quoted
        value.YY_MOVE_OR_COPY< std::unique_ptr<std::vector<std::unique_ptr<actions::Action> > >  > (YY_MOVE (that.value));
        break;

      default:
        break;
    }

#if 201103L <= YY_CPLUSPLUS
    // that is emptied.
    that.state = empty_state;
#endif
  }

  seclang_parser::stack_symbol_type::stack_symbol_type (state_type s, YY_MOVE_REF (symbol_type) that)
    : super_type (s, YY_MOVE (that.location))
  {
    switch (that.kind ())
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
      case symbol_kind::S_CONFIG_VALUE_OFF: // "CONFIG_VALUE_OFF"
      case symbol_kind::S_CONFIG_VALUE_ON: // "CONFIG_VALUE_ON"
      case symbol_kind::S_CONFIG_VALUE_PARALLEL: // "CONFIG_VALUE_PARALLEL"
      case symbol_kind::S_CONFIG_VALUE_PROCESS_PARTIAL: // "CONFIG_VALUE_PROCESS_PARTIAL"
      case symbol_kind::S_CONFIG_VALUE_REJECT: // "CONFIG_VALUE_REJECT"
      case symbol_kind::S_CONFIG_VALUE_RELEVANT_ONLY: // "CONFIG_VALUE_RELEVANT_ONLY"
      case symbol_kind::S_CONFIG_VALUE_SERIAL: // "CONFIG_VALUE_SERIAL"
      case symbol_kind::S_CONFIG_VALUE_WARN: // "CONFIG_VALUE_WARN"
      case symbol_kind::S_CONFIG_XML_EXTERNAL_ENTITY: // "CONFIG_XML_EXTERNAL_ENTITY"
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
        value.move< std::string > (YY_MOVE (that.value));
        break;

      case symbol_kind::S_op: // op
      case symbol_kind::S_op_before_init: // op_before_init
        value.move< std::unique_ptr<Operator> > (YY_MOVE (that.value));
        break;

      case symbol_kind::S_run_time_string: // run_time_string
        value.move< std::unique_ptr<RunTimeString> > (YY_MOVE (that.value));
        break;

      case symbol_kind::S_var: // var
        value.move< std::unique_ptr<Variable> > (YY_MOVE (that.value));
        break;

      case symbol_kind::S_act: // act
      case symbol_kind::S_setvar_action: // setvar_action
        value.move< std::unique_ptr<actions::Action> > (YY_MOVE (that.value));
        break;

      case symbol_kind::S_variables: // variables
      case symbol_kind::S_variables_pre_process: // variables_pre_process
      case symbol_kind::S_variables_may_be_quoted: // variables_may_be_quoted
        value.move< std::unique_ptr<std::vector<std::unique_ptr<Variable> > >  > (YY_MOVE (that.value));
        break;

      case symbol_kind::S_actions: // actions
      case symbol_kind::S_actions_may_quoted: // actions_may_quoted
        value.move< std::unique_ptr<std::vector<std::unique_ptr<actions::Action> > >  > (YY_MOVE (that.value));
        break;

      default:
        break;
    }

    // that is emptied.
    that.kind_ = symbol_kind::S_YYEMPTY;
  }

#if YY_CPLUSPLUS < 201103L
  seclang_parser::stack_symbol_type&
  seclang_parser::stack_symbol_type::operator= (const stack_symbol_type& that)
  {
    state = that.state;
    switch (that.kind ())
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
      case symbol_kind::S_CONFIG_VALUE_OFF: // "CONFIG_VALUE_OFF"
      case symbol_kind::S_CONFIG_VALUE_ON: // "CONFIG_VALUE_ON"
      case symbol_kind::S_CONFIG_VALUE_PARALLEL: // "CONFIG_VALUE_PARALLEL"
      case symbol_kind::S_CONFIG_VALUE_PROCESS_PARTIAL: // "CONFIG_VALUE_PROCESS_PARTIAL"
      case symbol_kind::S_CONFIG_VALUE_REJECT: // "CONFIG_VALUE_REJECT"
      case symbol_kind::S_CONFIG_VALUE_RELEVANT_ONLY: // "CONFIG_VALUE_RELEVANT_ONLY"
      case symbol_kind::S_CONFIG_VALUE_SERIAL: // "CONFIG_VALUE_SERIAL"
      case symbol_kind::S_CONFIG_VALUE_WARN: // "CONFIG_VALUE_WARN"
      case symbol_kind::S_CONFIG_XML_EXTERNAL_ENTITY: // "CONFIG_XML_EXTERNAL_ENTITY"
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
        value.copy< std::string > (that.value);
        break;

      case symbol_kind::S_op: // op
      case symbol_kind::S_op_before_init: // op_before_init
        value.copy< std::unique_ptr<Operator> > (that.value);
        break;

      case symbol_kind::S_run_time_string: // run_time_string
        value.copy< std::unique_ptr<RunTimeString> > (that.value);
        break;

      case symbol_kind::S_var: // var
        value.copy< std::unique_ptr<Variable> > (that.value);
        break;

      case symbol_kind::S_act: // act
      case symbol_kind::S_setvar_action: // setvar_action
        value.copy< std::unique_ptr<actions::Action> > (that.value);
        break;

      case symbol_kind::S_variables: // variables
      case symbol_kind::S_variables_pre_process: // variables_pre_process
      case symbol_kind::S_variables_may_be_quoted: // variables_may_be_quoted
        value.copy< std::unique_ptr<std::vector<std::unique_ptr<Variable> > >  > (that.value);
        break;

      case symbol_kind::S_actions: // actions
      case symbol_kind::S_actions_may_quoted: // actions_may_quoted
        value.copy< std::unique_ptr<std::vector<std::unique_ptr<actions::Action> > >  > (that.value);
        break;

      default:
        break;
    }

    location = that.location;
    return *this;
  }

  seclang_parser::stack_symbol_type&
  seclang_parser::stack_symbol_type::operator= (stack_symbol_type& that)
  {
    state = that.state;
    switch (that.kind ())
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
      case symbol_kind::S_CONFIG_VALUE_OFF: // "CONFIG_VALUE_OFF"
      case symbol_kind::S_CONFIG_VALUE_ON: // "CONFIG_VALUE_ON"
      case symbol_kind::S_CONFIG_VALUE_PARALLEL: // "CONFIG_VALUE_PARALLEL"
      case symbol_kind::S_CONFIG_VALUE_PROCESS_PARTIAL: // "CONFIG_VALUE_PROCESS_PARTIAL"
      case symbol_kind::S_CONFIG_VALUE_REJECT: // "CONFIG_VALUE_REJECT"
      case symbol_kind::S_CONFIG_VALUE_RELEVANT_ONLY: // "CONFIG_VALUE_RELEVANT_ONLY"
      case symbol_kind::S_CONFIG_VALUE_SERIAL: // "CONFIG_VALUE_SERIAL"
      case symbol_kind::S_CONFIG_VALUE_WARN: // "CONFIG_VALUE_WARN"
      case symbol_kind::S_CONFIG_XML_EXTERNAL_ENTITY: // "CONFIG_XML_EXTERNAL_ENTITY"
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
        value.move< std::string > (that.value);
        break;

      case symbol_kind::S_op: // op
      case symbol_kind::S_op_before_init: // op_before_init
        value.move< std::unique_ptr<Operator> > (that.value);
        break;

      case symbol_kind::S_run_time_string: // run_time_string
        value.move< std::unique_ptr<RunTimeString> > (that.value);
        break;

      case symbol_kind::S_var: // var
        value.move< std::unique_ptr<Variable> > (that.value);
        break;

      case symbol_kind::S_act: // act
      case symbol_kind::S_setvar_action: // setvar_action
        value.move< std::unique_ptr<actions::Action> > (that.value);
        break;

      case symbol_kind::S_variables: // variables
      case symbol_kind::S_variables_pre_process: // variables_pre_process
      case symbol_kind::S_variables_may_be_quoted: // variables_may_be_quoted
        value.move< std::unique_ptr<std::vector<std::unique_ptr<Variable> > >  > (that.value);
        break;

      case symbol_kind::S_actions: // actions
      case symbol_kind::S_actions_may_quoted: // actions_may_quoted
        value.move< std::unique_ptr<std::vector<std::unique_ptr<actions::Action> > >  > (that.value);
        break;

      default:
        break;
    }

    location = that.location;
    // that is emptied.
    that.state = empty_state;
    return *this;
  }
#endif

  template <typename Base>
  void
  seclang_parser::yy_destroy_ (const char* yymsg, basic_symbol<Base>& yysym) const
  {
    if (yymsg)
      YY_SYMBOL_PRINT (yymsg, yysym);
  }

#if YYDEBUG
  template <typename Base>
  void
  seclang_parser::yy_print_ (std::ostream& yyo, const basic_symbol<Base>& yysym) const
  {
    std::ostream& yyoutput = yyo;
    YY_USE (yyoutput);
    if (yysym.empty ())
      yyo << "empty symbol";
    else
      {
        symbol_kind_type yykind = yysym.kind ();
        yyo << (yykind < YYNTOKENS ? "token" : "nterm")
            << ' ' << yysym.name () << " ("
            << yysym.location << ": ";
        YY_USE (yykind);
        yyo << ')';
      }
  }
#endif

  void
  seclang_parser::yypush_ (const char* m, YY_MOVE_REF (stack_symbol_type) sym)
  {
    if (m)
      YY_SYMBOL_PRINT (m, sym);
    yystack_.push (YY_MOVE (sym));
  }

  void
  seclang_parser::yypush_ (const char* m, state_type s, YY_MOVE_REF (symbol_type) sym)
  {
#if 201103L <= YY_CPLUSPLUS
    yypush_ (m, stack_symbol_type (s, std::move (sym)));
#else
    stack_symbol_type ss (s, sym);
    yypush_ (m, ss);
#endif
  }

  void
  seclang_parser::yypop_ (int n)
  {
    yystack_.pop (n);
  }

#if YYDEBUG
  std::ostream&
  seclang_parser::debug_stream () const
  {
    return *yycdebug_;
  }

  void
  seclang_parser::set_debug_stream (std::ostream& o)
  {
    yycdebug_ = &o;
  }


  seclang_parser::debug_level_type
  seclang_parser::debug_level () const
  {
    return yydebug_;
  }

  void
  seclang_parser::set_debug_level (debug_level_type l)
  {
    yydebug_ = l;
  }
#endif // YYDEBUG

  seclang_parser::state_type
  seclang_parser::yy_lr_goto_state_ (state_type yystate, int yysym)
  {
    int yyr = yypgoto_[yysym - YYNTOKENS] + yystate;
    if (0 <= yyr && yyr <= yylast_ && yycheck_[yyr] == yystate)
      return yytable_[yyr];
    else
      return yydefgoto_[yysym - YYNTOKENS];
  }

  bool
  seclang_parser::yy_pact_value_is_default_ (int yyvalue)
  {
    return yyvalue == yypact_ninf_;
  }

  bool
  seclang_parser::yy_table_value_is_error_ (int yyvalue)
  {
    return yyvalue == yytable_ninf_;
  }

  int
  seclang_parser::operator() ()
  {
    return parse ();
  }

  int
  seclang_parser::parse ()
  {
    int yyn;
    /// Length of the RHS of the rule being reduced.
    int yylen = 0;

    // Error handling.
    int yynerrs_ = 0;
    int yyerrstatus_ = 0;

    /// The lookahead symbol.
    symbol_type yyla;

    /// The locations where the error started and ended.
    stack_symbol_type yyerror_range[3];

    /// The return value of parse ().
    int yyresult;

#if YY_EXCEPTIONS
    try
#endif // YY_EXCEPTIONS
      {
    YYCDEBUG << "Starting parse\n";


    // User initialization code.
#line 320 "seclang-parser.yy"
{
  // Initialize the initial location.
  driver.m_filenames.push_back(driver.file);
  yyla.location.begin.filename = yyla.location.end.filename = &(driver.m_filenames.back());
}

#line 1333 "seclang-parser.cc"


    /* Initialize the stack.  The initial state will be set in
       yynewstate, since the latter expects the semantical and the
       location values to have been already stored, initialize these
       stacks with a primary value.  */
    yystack_.clear ();
    yypush_ (YY_NULLPTR, 0, YY_MOVE (yyla));

  /*-----------------------------------------------.
  | yynewstate -- push a new symbol on the stack.  |
  `-----------------------------------------------*/
  yynewstate:
    YYCDEBUG << "Entering state " << int (yystack_[0].state) << '\n';
    YY_STACK_PRINT ();

    // Accept?
    if (yystack_[0].state == yyfinal_)
      YYACCEPT;

    goto yybackup;


  /*-----------.
  | yybackup.  |
  `-----------*/
  yybackup:
    // Try to take a decision without lookahead.
    yyn = yypact_[+yystack_[0].state];
    if (yy_pact_value_is_default_ (yyn))
      goto yydefault;

    // Read a lookahead token.
    if (yyla.empty ())
      {
        YYCDEBUG << "Reading a token\n";
#if YY_EXCEPTIONS
        try
#endif // YY_EXCEPTIONS
          {
            symbol_type yylookahead (yylex (driver));
            yyla.move (yylookahead);
          }
#if YY_EXCEPTIONS
        catch (const syntax_error& yyexc)
          {
            YYCDEBUG << "Caught exception: " << yyexc.what() << '\n';
            error (yyexc);
            goto yyerrlab1;
          }
#endif // YY_EXCEPTIONS
      }
    YY_SYMBOL_PRINT ("Next token is", yyla);

    if (yyla.kind () == symbol_kind::S_YYerror)
    {
      // The scanner already issued an error message, process directly
      // to error recovery.  But do not keep the error token as
      // lookahead, it is too special and may lead us to an endless
      // loop in error recovery. */
      yyla.kind_ = symbol_kind::S_YYUNDEF;
      goto yyerrlab1;
    }

    /* If the proper action on seeing token YYLA.TYPE is to reduce or
       to detect an error, take that action.  */
    yyn += yyla.kind ();
    if (yyn < 0 || yylast_ < yyn || yycheck_[yyn] != yyla.kind ())
      {
        goto yydefault;
      }

    // Reduce or error.
    yyn = yytable_[yyn];
    if (yyn <= 0)
      {
        if (yy_table_value_is_error_ (yyn))
          goto yyerrlab;
        yyn = -yyn;
        goto yyreduce;
      }

    // Count tokens shifted since error; after three, turn off error status.
    if (yyerrstatus_)
      --yyerrstatus_;

    // Shift the lookahead token.
    yypush_ ("Shifting", state_type (yyn), YY_MOVE (yyla));
    goto yynewstate;


  /*-----------------------------------------------------------.
  | yydefault -- do the default action for the current state.  |
  `-----------------------------------------------------------*/
  yydefault:
    yyn = yydefact_[+yystack_[0].state];
    if (yyn == 0)
      goto yyerrlab;
    goto yyreduce;


  /*-----------------------------.
  | yyreduce -- do a reduction.  |
  `-----------------------------*/
  yyreduce:
    yylen = yyr2_[yyn];
    {
      stack_symbol_type yylhs;
      yylhs.state = yy_lr_goto_state_ (yystack_[yylen].state, yyr1_[yyn]);
      /* Variants are always initialized to an empty instance of the
         correct type. The default '$$ = $1' action is NOT applied
         when using variants.  */
      switch (yyr1_[yyn])
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
      case symbol_kind::S_CONFIG_VALUE_OFF: // "CONFIG_VALUE_OFF"
      case symbol_kind::S_CONFIG_VALUE_ON: // "CONFIG_VALUE_ON"
      case symbol_kind::S_CONFIG_VALUE_PARALLEL: // "CONFIG_VALUE_PARALLEL"
      case symbol_kind::S_CONFIG_VALUE_PROCESS_PARTIAL: // "CONFIG_VALUE_PROCESS_PARTIAL"
      case symbol_kind::S_CONFIG_VALUE_REJECT: // "CONFIG_VALUE_REJECT"
      case symbol_kind::S_CONFIG_VALUE_RELEVANT_ONLY: // "CONFIG_VALUE_RELEVANT_ONLY"
      case symbol_kind::S_CONFIG_VALUE_SERIAL: // "CONFIG_VALUE_SERIAL"
      case symbol_kind::S_CONFIG_VALUE_WARN: // "CONFIG_VALUE_WARN"
      case symbol_kind::S_CONFIG_XML_EXTERNAL_ENTITY: // "CONFIG_XML_EXTERNAL_ENTITY"
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
        yylhs.value.emplace< std::string > ();
        break;

      case symbol_kind::S_op: // op
      case symbol_kind::S_op_before_init: // op_before_init
        yylhs.value.emplace< std::unique_ptr<Operator> > ();
        break;

      case symbol_kind::S_run_time_string: // run_time_string
        yylhs.value.emplace< std::unique_ptr<RunTimeString> > ();
        break;

      case symbol_kind::S_var: // var
        yylhs.value.emplace< std::unique_ptr<Variable> > ();
        break;

      case symbol_kind::S_act: // act
      case symbol_kind::S_setvar_action: // setvar_action
        yylhs.value.emplace< std::unique_ptr<actions::Action> > ();
        break;

      case symbol_kind::S_variables: // variables
      case symbol_kind::S_variables_pre_process: // variables_pre_process
      case symbol_kind::S_variables_may_be_quoted: // variables_may_be_quoted
        yylhs.value.emplace< std::unique_ptr<std::vector<std::unique_ptr<Variable> > >  > ();
        break;

      case symbol_kind::S_actions: // actions
      case symbol_kind::S_actions_may_quoted: // actions_may_quoted
        yylhs.value.emplace< std::unique_ptr<std::vector<std::unique_ptr<actions::Action> > >  > ();
        break;

      default:
        break;
    }


      // Default location.
      {
        stack_type::slice range (yystack_, yylen);
        YYLLOC_DEFAULT (yylhs.location, range, yylen);
        yyerror_range[1].location = yylhs.location;
      }

      // Perform the reduction.
      YY_REDUCE_PRINT (yyn);
#if YY_EXCEPTIONS
      try
#endif // YY_EXCEPTIONS
        {
          switch (yyn)
            {
  case 2: // input: "end of file"
#line 717 "seclang-parser.yy"
      {
        return 0;
      }
#line 1704 "seclang-parser.cc"
    break;

  case 6: // audit_log: "CONFIG_DIR_AUDIT_DIR_MOD"
#line 730 "seclang-parser.yy"
      {
        driver.m_auditLog->setStorageDirMode(strtol(yystack_[0].value.as < std::string > ().c_str(), NULL, 8));
      }
#line 1712 "seclang-parser.cc"
    break;

  case 7: // audit_log: "CONFIG_DIR_AUDIT_DIR"
#line 736 "seclang-parser.yy"
      {
        driver.m_auditLog->setStorageDir(yystack_[0].value.as < std::string > ());
      }
#line 1720 "seclang-parser.cc"
    break;

  case 8: // audit_log: "CONFIG_DIR_AUDIT_ENG" "CONFIG_VALUE_RELEVANT_ONLY"
#line 742 "seclang-parser.yy"
      {
        driver.m_auditLog->setStatus(modsecurity::audit_log::AuditLog::RelevantOnlyAuditLogStatus);
      }
#line 1728 "seclang-parser.cc"
    break;

  case 9: // audit_log: "CONFIG_DIR_AUDIT_ENG" "CONFIG_VALUE_OFF"
#line 746 "seclang-parser.yy"
      {
        driver.m_auditLog->setStatus(modsecurity::audit_log::AuditLog::OffAuditLogStatus);
      }
#line 1736 "seclang-parser.cc"
    break;

  case 10: // audit_log: "CONFIG_DIR_AUDIT_ENG" "CONFIG_VALUE_ON"
#line 750 "seclang-parser.yy"
      {
        driver.m_auditLog->setStatus(modsecurity::audit_log::AuditLog::OnAuditLogStatus);
      }
#line 1744 "seclang-parser.cc"
    break;

  case 11: // audit_log: "CONFIG_DIR_AUDIT_FLE_MOD"
#line 756 "seclang-parser.yy"
      {
        driver.m_auditLog->setFileMode(strtol(yystack_[0].value.as < std::string > ().c_str(), NULL, 8));
      }
#line 1752 "seclang-parser.cc"
    break;

  case 12: // audit_log: "CONFIG_DIR_AUDIT_LOG2"
#line 762 "seclang-parser.yy"
      {
        driver.m_auditLog->setFilePath2(yystack_[0].value.as < std::string > ());
      }
#line 1760 "seclang-parser.cc"
    break;

  case 13: // audit_log: "CONFIG_DIR_AUDIT_LOG_P"
#line 768 "seclang-parser.yy"
      {
        driver.m_auditLog->setParts(yystack_[0].value.as < std::string > ());
      }
#line 1768 "seclang-parser.cc"
    break;

  case 14: // audit_log: "CONFIG_DIR_AUDIT_LOG"
#line 774 "seclang-parser.yy"
      {
        driver.m_auditLog->setFilePath1(yystack_[0].value.as < std::string > ());
      }
#line 1776 "seclang-parser.cc"
    break;

  case 15: // audit_log: CONFIG_DIR_AUDIT_LOG_FMT JSON
#line 779 "seclang-parser.yy"
      {
        driver.m_auditLog->setFormat(modsecurity::audit_log::AuditLog::JSONAuditLogFormat);
      }
#line 1784 "seclang-parser.cc"
    break;

  case 16: // audit_log: CONFIG_DIR_AUDIT_LOG_FMT NATIVE
#line 784 "seclang-parser.yy"
      {
        driver.m_auditLog->setFormat(modsecurity::audit_log::AuditLog::NativeAuditLogFormat);
      }
#line 1792 "seclang-parser.cc"
    break;

  case 17: // audit_log: "CONFIG_DIR_AUDIT_STS"
#line 790 "seclang-parser.yy"
      {
        std::string relevant_status(yystack_[0].value.as < std::string > ());
        driver.m_auditLog->setRelevantStatus(relevant_status);
      }
#line 1801 "seclang-parser.cc"
    break;

  case 18: // audit_log: "CONFIG_DIR_AUDIT_TPE" "CONFIG_VALUE_SERIAL"
#line 797 "seclang-parser.yy"
      {
        driver.m_auditLog->setType(modsecurity::audit_log::AuditLog::SerialAuditLogType);
      }
#line 1809 "seclang-parser.cc"
    break;

  case 19: // audit_log: "CONFIG_DIR_AUDIT_TPE" "CONFIG_VALUE_PARALLEL"
#line 801 "seclang-parser.yy"
      {
        driver.m_auditLog->setType(modsecurity::audit_log::AuditLog::ParallelAuditLogType);
      }
#line 1817 "seclang-parser.cc"
    break;

  case 20: // audit_log: "CONFIG_DIR_AUDIT_TPE" "CONFIG_VALUE_HTTPS"
#line 805 "seclang-parser.yy"
      {
        driver.m_auditLog->setType(modsecurity::audit_log::AuditLog::HttpsAuditLogType);
      }
#line 1825 "seclang-parser.cc"
    break;

  case 21: // audit_log: "CONFIG_UPDLOAD_KEEP_FILES" "CONFIG_VALUE_ON"
#line 811 "seclang-parser.yy"
      {
        driver.m_uploadKeepFiles = modsecurity::RulesSetProperties::TrueConfigBoolean;
      }
#line 1833 "seclang-parser.cc"
    break;

  case 22: // audit_log: "CONFIG_UPDLOAD_KEEP_FILES" "CONFIG_VALUE_OFF"
#line 815 "seclang-parser.yy"
      {
        driver.m_uploadKeepFiles = modsecurity::RulesSetProperties::FalseConfigBoolean;
      }
#line 1841 "seclang-parser.cc"
    break;

  case 23: // audit_log: "CONFIG_UPDLOAD_KEEP_FILES" "CONFIG_VALUE_RELEVANT_ONLY"
#line 819 "seclang-parser.yy"
      {
        driver.error(yystack_[2].location, "SecUploadKeepFiles RelevantOnly is not currently supported. Accepted values are On or Off");
        YYERROR;
      }
#line 1850 "seclang-parser.cc"
    break;

  case 24: // audit_log: "CONFIG_UPLOAD_FILE_LIMIT"
#line 824 "seclang-parser.yy"
      {
        driver.m_uploadFileLimit.m_set = true;
        driver.m_uploadFileLimit.m_value = strtol(yystack_[0].value.as < std::string > ().c_str(), NULL, 10);
      }
#line 1859 "seclang-parser.cc"
    break;

  case 25: // audit_log: "CONFIG_UPLOAD_FILE_MODE"
#line 829 "seclang-parser.yy"
      {
        driver.m_uploadFileMode.m_set = true;
        driver.m_uploadFileMode.m_value = strtol(yystack_[0].value.as < std::string > ().c_str(), NULL, 8);
      }
#line 1868 "seclang-parser.cc"
    break;

  case 26: // audit_log: "CONFIG_UPLOAD_DIR"
#line 834 "seclang-parser.yy"
      {
        driver.m_uploadDirectory.m_set = true;
        driver.m_uploadDirectory.m_value = yystack_[0].value.as < std::string > ();
      }
#line 1877 "seclang-parser.cc"
    break;

  case 27: // audit_log: "CONFIG_UPDLOAD_SAVE_TMP_FILES" "CONFIG_VALUE_ON"
#line 839 "seclang-parser.yy"
      {
        driver.m_tmpSaveUploadedFiles = modsecurity::RulesSetProperties::TrueConfigBoolean;
      }
#line 1885 "seclang-parser.cc"
    break;

  case 28: // audit_log: "CONFIG_UPDLOAD_SAVE_TMP_FILES" "CONFIG_VALUE_OFF"
#line 843 "seclang-parser.yy"
      {
        driver.m_tmpSaveUploadedFiles = modsecurity::RulesSetProperties::FalseConfigBoolean;
      }
#line 1893 "seclang-parser.cc"
    break;

  case 29: // actions: "QUOTATION_MARK" actions_may_quoted "QUOTATION_MARK"
#line 850 "seclang-parser.yy"
      {
        yylhs.value.as < std::unique_ptr<std::vector<std::unique_ptr<actions::Action> > >  > () = std::move(yystack_[1].value.as < std::unique_ptr<std::vector<std::unique_ptr<actions::Action> > >  > ());
      }
#line 1901 "seclang-parser.cc"
    break;

  case 30: // actions: actions_may_quoted
#line 854 "seclang-parser.yy"
      {
        yylhs.value.as < std::unique_ptr<std::vector<std::unique_ptr<actions::Action> > >  > () = std::move(yystack_[0].value.as < std::unique_ptr<std::vector<std::unique_ptr<actions::Action> > >  > ());
      }
#line 1909 "seclang-parser.cc"
    break;

  case 31: // actions_may_quoted: actions_may_quoted "," act
#line 861 "seclang-parser.yy"
      {
        ACTION_INIT(yystack_[0].value.as < std::unique_ptr<actions::Action> > (), yystack_[3].location)
        yystack_[2].value.as < std::unique_ptr<std::vector<std::unique_ptr<actions::Action> > >  > ()->push_back(std::move(yystack_[0].value.as < std::unique_ptr<actions::Action> > ()));
        yylhs.value.as < std::unique_ptr<std::vector<std::unique_ptr<actions::Action> > >  > () = std::move(yystack_[2].value.as < std::unique_ptr<std::vector<std::unique_ptr<actions::Action> > >  > ());
      }
#line 1919 "seclang-parser.cc"
    break;

  case 32: // actions_may_quoted: act
#line 867 "seclang-parser.yy"
      {
        std::unique_ptr<std::vector<std::unique_ptr<actions::Action>>> b(new std::vector<std::unique_ptr<actions::Action>>());
        ACTION_INIT(yystack_[0].value.as < std::unique_ptr<actions::Action> > (), yystack_[1].location)
        b->push_back(std::move(yystack_[0].value.as < std::unique_ptr<actions::Action> > ()));
        yylhs.value.as < std::unique_ptr<std::vector<std::unique_ptr<actions::Action> > >  > () = std::move(b);
      }
#line 1930 "seclang-parser.cc"
    break;

  case 33: // op: op_before_init
#line 877 "seclang-parser.yy"
      {
        yylhs.value.as < std::unique_ptr<Operator> > () = std::move(yystack_[0].value.as < std::unique_ptr<Operator> > ());
        std::string error;
        if (yylhs.value.as < std::unique_ptr<Operator> > ()->init(*yystack_[0].location.end.filename, &error) == false) {
            driver.error(yystack_[1].location, error);
            YYERROR;
        }
      }
#line 1943 "seclang-parser.cc"
    break;

  case 34: // op: "NOT" op_before_init
#line 886 "seclang-parser.yy"
      {
        yylhs.value.as < std::unique_ptr<Operator> > () = std::move(yystack_[0].value.as < std::unique_ptr<Operator> > ());
        yylhs.value.as < std::unique_ptr<Operator> > ()->m_negation = true;
        std::string error;
        if (yylhs.value.as < std::unique_ptr<Operator> > ()->init(*yystack_[1].location.end.filename, &error) == false) {
            driver.error(yystack_[2].location, error);
            YYERROR;
        }
      }
#line 1957 "seclang-parser.cc"
    break;

  case 35: // op: run_time_string
#line 896 "seclang-parser.yy"
      {
        OPERATOR_CONTAINER(yylhs.value.as < std::unique_ptr<Operator> > (), new operators::Rx(std::move(yystack_[0].value.as < std::unique_ptr<RunTimeString> > ())));
        std::string error;
        if (yylhs.value.as < std::unique_ptr<Operator> > ()->init(*yystack_[0].location.end.filename, &error) == false) {
            driver.error(yystack_[1].location, error);
            YYERROR;
        }
      }
#line 1970 "seclang-parser.cc"
    break;

  case 36: // op: "NOT" run_time_string
#line 905 "seclang-parser.yy"
      {
        OPERATOR_CONTAINER(yylhs.value.as < std::unique_ptr<Operator> > (), new operators::Rx(std::move(yystack_[0].value.as < std::unique_ptr<RunTimeString> > ())));
        yylhs.value.as < std::unique_ptr<Operator> > ()->m_negation = true;
        std::string error;
        if (yylhs.value.as < std::unique_ptr<Operator> > ()->init(*yystack_[1].location.end.filename, &error) == false) {
            driver.error(yystack_[2].location, error);
            YYERROR;
        }
      }
#line 1984 "seclang-parser.cc"
    break;

  case 37: // op_before_init: "OPERATOR_UNCONDITIONAL_MATCH"
#line 918 "seclang-parser.yy"
      {
        OPERATOR_CONTAINER(yylhs.value.as < std::unique_ptr<Operator> > (), new operators::UnconditionalMatch());
      }
#line 1992 "seclang-parser.cc"
    break;

  case 38: // op_before_init: "OPERATOR_DETECT_SQLI"
#line 922 "seclang-parser.yy"
      {
        OPERATOR_CONTAINER(yylhs.value.as < std::unique_ptr<Operator> > (), new operators::DetectSQLi());
      }
#line 2000 "seclang-parser.cc"
    break;

  case 39: // op_before_init: "OPERATOR_DETECT_XSS"
#line 926 "seclang-parser.yy"
      {
        OPERATOR_CONTAINER(yylhs.value.as < std::unique_ptr<Operator> > (), new operators::DetectXSS());
      }
#line 2008 "seclang-parser.cc"
    break;

  case 40: // op_before_init: "OPERATOR_VALIDATE_URL_ENCODING"
#line 930 "seclang-parser.yy"
      {
        OPERATOR_CONTAINER(yylhs.value.as < std::unique_ptr<Operator> > (), new operators::ValidateUrlEncoding());
      }
#line 2016 "seclang-parser.cc"
    break;

  case 41: // op_before_init: "OPERATOR_VALIDATE_UTF8_ENCODING"
#line 934 "seclang-parser.yy"
      {
        OPERATOR_CONTAINER(yylhs.value.as < std::unique_ptr<Operator> > (), new operators::ValidateUtf8Encoding());
      }
#line 2024 "seclang-parser.cc"
    break;

  case 42: // op_before_init: "OPERATOR_INSPECT_FILE" run_time_string
#line 938 "seclang-parser.yy"
      {
        OPERATOR_CONTAINER(yylhs.value.as < std::unique_ptr<Operator> > (), new operators::InspectFile(std::move(yystack_[0].value.as < std::unique_ptr<RunTimeString> > ())));
      }
#line 2032 "seclang-parser.cc"
    break;

  case 43: // op_before_init: "OPERATOR_FUZZY_HASH" run_time_string
#line 942 "seclang-parser.yy"
      {
        OPERATOR_CONTAINER(yylhs.value.as < std::unique_ptr<Operator> > (), new operators::FuzzyHash(std::move(yystack_[0].value.as < std::unique_ptr<RunTimeString> > ())));
      }
#line 2040 "seclang-parser.cc"
    break;

  case 44: // op_before_init: "OPERATOR_VALIDATE_BYTE_RANGE" run_time_string
#line 946 "seclang-parser.yy"
      {
        OPERATOR_CONTAINER(yylhs.value.as < std::unique_ptr<Operator> > (), new operators::ValidateByteRange(std::move(yystack_[0].value.as < std::unique_ptr<RunTimeString> > ())));
      }
#line 2048 "seclang-parser.cc"
    break;

  case 45: // op_before_init: "OPERATOR_VALIDATE_DTD" run_time_string
#line 950 "seclang-parser.yy"
      {
        OPERATOR_CONTAINER(yylhs.value.as < std::unique_ptr<Operator> > (), new operators::ValidateDTD(std::move(yystack_[0].value.as < std::unique_ptr<RunTimeString> > ())));
      }
#line 2056 "seclang-parser.cc"
    break;

  case 46: // op_before_init: "OPERATOR_VALIDATE_HASH" run_time_string
#line 954 "seclang-parser.yy"
      {
        /* $$ = new operators::ValidateHash($1); */
        OPERATOR_NOT_SUPPORTED("ValidateHash", yystack_[2].location);
      }
#line 2065 "seclang-parser.cc"
    break;

  case 47: // op_before_init: "OPERATOR_VALIDATE_SCHEMA" run_time_string
#line 959 "seclang-parser.yy"
      {
        OPERATOR_CONTAINER(yylhs.value.as < std::unique_ptr<Operator> > (), new operators::ValidateSchema(std::move(yystack_[0].value.as < std::unique_ptr<RunTimeString> > ())));
      }
#line 2073 "seclang-parser.cc"
    break;

  case 48: // op_before_init: "OPERATOR_VERIFY_CC" run_time_string
#line 963 "seclang-parser.yy"
      {
        OPERATOR_CONTAINER(yylhs.value.as < std::unique_ptr<Operator> > (), new operators::VerifyCC(std::move(yystack_[0].value.as < std::unique_ptr<RunTimeString> > ())));
      }
#line 2081 "seclang-parser.cc"
    break;

  case 49: // op_before_init: "OPERATOR_VERIFY_CPF" run_time_string
#line 967 "seclang-parser.yy"
      {
        OPERATOR_CONTAINER(yylhs.value.as < std::unique_ptr<Operator> > (), new operators::VerifyCPF(std::move(yystack_[0].value.as < std::unique_ptr<RunTimeString> > ())));
      }
#line 2089 "seclang-parser.cc"
    break;

  case 50: // op_before_init: "OPERATOR_VERIFY_SSN" run_time_string
#line 971 "seclang-parser.yy"
      {
        OPERATOR_CONTAINER(yylhs.value.as < std::unique_ptr<Operator> > (), new operators::VerifySSN(std::move(yystack_[0].value.as < std::unique_ptr<RunTimeString> > ())));
      }
#line 2097 "seclang-parser.cc"
    break;

  case 51: // op_before_init: "OPERATOR_VERIFY_SVNR" run_time_string
#line 975 "seclang-parser.yy"
      {
        OPERATOR_CONTAINER(yylhs.value.as < std::unique_ptr<Operator> > (), new operators::VerifySVNR(std::move(yystack_[0].value.as < std::unique_ptr<RunTimeString> > ())));
      }
#line 2105 "seclang-parser.cc"
    break;

  case 52: // op_before_init: "OPERATOR_GSB_LOOKUP" run_time_string
#line 979 "seclang-parser.yy"
      {
        /* $$ = new operators::GsbLookup($1); */
        OPERATOR_NOT_SUPPORTED("GsbLookup", yystack_[2].location);
      }
#line 2114 "seclang-parser.cc"
    break;

  case 53: // op_before_init: "OPERATOR_RSUB" run_time_string
#line 984 "seclang-parser.yy"
      {
        /* $$ = new operators::Rsub($1); */
        OPERATOR_NOT_SUPPORTED("Rsub", yystack_[2].location);
      }
#line 2123 "seclang-parser.cc"
    break;

  case 54: // op_before_init: "OPERATOR_WITHIN" run_time_string
#line 989 "seclang-parser.yy"
      {
        OPERATOR_CONTAINER(yylhs.value.as < std::unique_ptr<Operator> > (), new operators::Within(std::move(yystack_[0].value.as < std::unique_ptr<RunTimeString> > ())));
      }
#line 2131 "seclang-parser.cc"
    break;

  case 55: // op_before_init: "OPERATOR_CONTAINS_WORD" run_time_string
#line 993 "seclang-parser.yy"
      {
        OPERATOR_CONTAINER(yylhs.value.as < std::unique_ptr<Operator> > (), new operators::ContainsWord(std::move(yystack_[0].value.as < std::unique_ptr<RunTimeString> > ())));
      }
#line 2139 "seclang-parser.cc"
    break;

  case 56: // op_before_init: "OPERATOR_CONTAINS" run_time_string
#line 997 "seclang-parser.yy"
      {
        OPERATOR_CONTAINER(yylhs.value.as < std::unique_ptr<Operator> > (), new operators::Contains(std::move(yystack_[0].value.as < std::unique_ptr<RunTimeString> > ())));
      }
#line 2147 "seclang-parser.cc"
    break;

  case 57: // op_before_init: "OPERATOR_ENDS_WITH" run_time_string
#line 1001 "seclang-parser.yy"
      {
        OPERATOR_CONTAINER(yylhs.value.as < std::unique_ptr<Operator> > (), new operators::EndsWith(std::move(yystack_[0].value.as < std::unique_ptr<RunTimeString> > ())));
      }
#line 2155 "seclang-parser.cc"
    break;

  case 58: // op_before_init: "OPERATOR_EQ" run_time_string
#line 1005 "seclang-parser.yy"
      {
        OPERATOR_CONTAINER(yylhs.value.as < std::unique_ptr<Operator> > (), new operators::Eq(std::move(yystack_[0].value.as < std::unique_ptr<RunTimeString> > ())));
      }
#line 2163 "seclang-parser.cc"
    break;

  case 59: // op_before_init: "OPERATOR_GE" run_time_string
#line 1009 "seclang-parser.yy"
      {
        OPERATOR_CONTAINER(yylhs.value.as < std::unique_ptr<Operator> > (), new operators::Ge(std::move(yystack_[0].value.as < std::unique_ptr<RunTimeString> > ())));
      }
#line 2171 "seclang-parser.cc"
    break;

  case 60: // op_before_init: "OPERATOR_GT" run_time_string
#line 1013 "seclang-parser.yy"
      {
        OPERATOR_CONTAINER(yylhs.value.as < std::unique_ptr<Operator> > (), new operators::Gt(std::move(yystack_[0].value.as < std::unique_ptr<RunTimeString> > ())));
      }
#line 2179 "seclang-parser.cc"
    break;

  case 61: // op_before_init: "OPERATOR_IP_MATCH_FROM_FILE" run_time_string
#line 1017 "seclang-parser.yy"
      {
        OPERATOR_CONTAINER(yylhs.value.as < std::unique_ptr<Operator> > (), new operators::IpMatchF(std::move(yystack_[0].value.as < std::unique_ptr<RunTimeString> > ())));
      }
#line 2187 "seclang-parser.cc"
    break;

  case 62: // op_before_init: "OPERATOR_IP_MATCH" run_time_string
#line 1021 "seclang-parser.yy"
      {
        OPERATOR_CONTAINER(yylhs.value.as < std::unique_ptr<Operator> > (), new operators::IpMatch(std::move(yystack_[0].value.as < std::unique_ptr<RunTimeString> > ())));
      }
#line 2195 "seclang-parser.cc"
    break;

  case 63: // op_before_init: "OPERATOR_LE" run_time_string
#line 1025 "seclang-parser.yy"
      {
        OPERATOR_CONTAINER(yylhs.value.as < std::unique_ptr<Operator> > (), new operators::Le(std::move(yystack_[0].value.as < std::unique_ptr<RunTimeString> > ())));
      }
#line 2203 "seclang-parser.cc"
    break;

  case 64: // op_before_init: "OPERATOR_LT" run_time_string
#line 1029 "seclang-parser.yy"
      {
        OPERATOR_CONTAINER(yylhs.value.as < std::unique_ptr<Operator> > (), new operators::Lt(std::move(yystack_[0].value.as < std::unique_ptr<RunTimeString> > ())));
      }
#line 2211 "seclang-parser.cc"
    break;

  case 65: // op_before_init: "OPERATOR_PM_FROM_FILE" run_time_string
#line 1033 "seclang-parser.yy"
      {
        OPERATOR_CONTAINER(yylhs.value.as < std::unique_ptr<Operator> > (), new operators::PmFromFile(std::move(yystack_[0].value.as < std::unique_ptr<RunTimeString> > ())));
      }
#line 2219 "seclang-parser.cc"
    break;

  case 66: // op_before_init: "OPERATOR_PM" run_time_string
#line 1037 "seclang-parser.yy"
      {
        OPERATOR_CONTAINER(yylhs.value.as < std::unique_ptr<Operator> > (), new operators::Pm(std::move(yystack_[0].value.as < std::unique_ptr<RunTimeString> > ())));
      }
#line 2227 "seclang-parser.cc"
    break;

  case 67: // op_before_init: "OPERATOR_RBL" run_time_string
#line 1041 "seclang-parser.yy"
      {
        OPERATOR_CONTAINER(yylhs.value.as < std::unique_ptr<Operator> > (), new operators::Rbl(std::move(yystack_[0].value.as < std::unique_ptr<RunTimeString> > ())));
      }
#line 2235 "seclang-parser.cc"
    break;

  case 68: // op_before_init: "OPERATOR_RX" run_time_string
#line 1045 "seclang-parser.yy"
      {
        OPERATOR_CONTAINER(yylhs.value.as < std::unique_ptr<Operator> > (), new operators::Rx(std::move(yystack_[0].value.as < std::unique_ptr<RunTimeString> > ())));
      }
#line 2243 "seclang-parser.cc"
    break;

  case 69: // op_before_init: "OPERATOR_RX_GLOBAL" run_time_string
#line 1049 "seclang-parser.yy"
      {
        OPERATOR_CONTAINER(yylhs.value.as < std::unique_ptr<Operator> > (), new operators::RxGlobal(std::move(yystack_[0].value.as < std::unique_ptr<RunTimeString> > ())));
      }
#line 2251 "seclang-parser.cc"
    break;

  case 70: // op_before_init: "OPERATOR_STR_EQ" run_time_string
#line 1053 "seclang-parser.yy"
      {
        OPERATOR_CONTAINER(yylhs.value.as < std::unique_ptr<Operator> > (), new operators::StrEq(std::move(yystack_[0].value.as < std::unique_ptr<RunTimeString> > ())));
      }
#line 2259 "seclang-parser.cc"
    break;

  case 71: // op_before_init: "OPERATOR_STR_MATCH" run_time_string
#line 1057 "seclang-parser.yy"
      {
        OPERATOR_CONTAINER(yylhs.value.as < std::unique_ptr<Operator> > (), new operators::StrMatch(std::move(yystack_[0].value.as < std::unique_ptr<RunTimeString> > ())));
      }
#line 2267 "seclang-parser.cc"
    break;

  case 72: // op_before_init: "OPERATOR_BEGINS_WITH" run_time_string
#line 1061 "seclang-parser.yy"
      {
        OPERATOR_CONTAINER(yylhs.value.as < std::unique_ptr<Operator> > (), new operators::BeginsWith(std::move(yystack_[0].value.as < std::unique_ptr<RunTimeString> > ())));
      }
#line 2275 "seclang-parser.cc"
    break;

  case 73: // op_before_init: "OPERATOR_GEOLOOKUP"
#line 1065 "seclang-parser.yy"
      {
#if defined(WITH_GEOIP) or defined(WITH_MAXMIND)
        OPERATOR_CONTAINER(yylhs.value.as < std::unique_ptr<Operator> > (), new operators::GeoLookup());
#else
        std::stringstream ss;
            ss << "This version of ModSecurity was not compiled with GeoIP or MaxMind support.";
            driver.error(yystack_[1].location, ss.str());
            YYERROR;
#endif  // WITH_GEOIP
      }
#line 2290 "seclang-parser.cc"
    break;

  case 75: // expression: "DIRECTIVE" variables op actions
#line 1080 "seclang-parser.yy"
      {
        std::vector<actions::Action *> *a = new std::vector<actions::Action *>();
        std::vector<actions::transformations::Transformation *> *t = new std::vector<actions::transformations::Transformation *>();
        for (auto &i : *yystack_[0].value.as < std::unique_ptr<std::vector<std::unique_ptr<actions::Action> > >  > ().get()) {
            if (dynamic_cast<actions::transformations::Transformation *>(i.get())) {
              t->push_back(dynamic_cast<actions::transformations::Transformation *>(i.release()));
            } else {
              a->push_back(i.release());
            }
        }
        variables::Variables *v = new variables::Variables();
        for (auto &i : *yystack_[2].value.as < std::unique_ptr<std::vector<std::unique_ptr<Variable> > >  > ().get()) {
            v->push_back(i.release());
        }

        Operator *op = yystack_[1].value.as < std::unique_ptr<Operator> > ().release();
        std::unique_ptr<RuleWithOperator> rule(new RuleWithOperator(
            /* op */ op,
            /* variables */ v,
            /* actions */ a,
            /* transformations */ t,
            /* file name */ std::unique_ptr<std::string>(new std::string(*yystack_[3].location.end.filename)),
            /* line number */ yystack_[3].location.end.line
            ));

        if (driver.addSecRule(std::move(rule)) == false) {
            YYERROR;
        }
      }
#line 2324 "seclang-parser.cc"
    break;

  case 76: // expression: "DIRECTIVE" variables op
#line 1110 "seclang-parser.yy"
      {
        variables::Variables *v = new variables::Variables();
        for (auto &i : *yystack_[1].value.as < std::unique_ptr<std::vector<std::unique_ptr<Variable> > >  > ().get()) {
            v->push_back(i.release());
        }

        std::unique_ptr<RuleWithOperator> rule(new RuleWithOperator(
            /* op */ yystack_[0].value.as < std::unique_ptr<Operator> > ().release(),
            /* variables */ v,
            /* actions */ NULL,
            /* transformations */ NULL,
            /* file name */ std::unique_ptr<std::string>(new std::string(*yystack_[2].location.end.filename)),
            /* line number */ yystack_[2].location.end.line
            ));
        if (driver.addSecRule(std::move(rule)) == false) {
            YYERROR;
        }
      }
#line 2347 "seclang-parser.cc"
    break;

  case 77: // expression: "CONFIG_DIR_SEC_ACTION" actions
#line 1129 "seclang-parser.yy"
      {
        std::vector<actions::Action *> *a = new std::vector<actions::Action *>();
        std::vector<actions::transformations::Transformation *> *t = new std::vector<actions::transformations::Transformation *>();
        for (auto &i : *yystack_[0].value.as < std::unique_ptr<std::vector<std::unique_ptr<actions::Action> > >  > ().get()) {
            if (dynamic_cast<actions::transformations::Transformation *>(i.get())) {
              t->push_back(dynamic_cast<actions::transformations::Transformation *>(i.release()));
            } else {
              a->push_back(i.release());
            }
        }
        std::unique_ptr<RuleUnconditional> rule(new RuleUnconditional(
            /* actions */ a,
            /* transformations */ t,
            /* file name */ std::unique_ptr<std::string>(new std::string(*yystack_[1].location.end.filename)),
            /* line number */ yystack_[1].location.end.line
            ));
        driver.addSecAction(std::move(rule));
      }
#line 2370 "seclang-parser.cc"
    break;

  case 78: // expression: "DIRECTIVE_SECRULESCRIPT" actions
#line 1148 "seclang-parser.yy"
      {
        std::string err;
        std::vector<actions::Action *> *a = new std::vector<actions::Action *>();
        std::vector<actions::transformations::Transformation *> *t = new std::vector<actions::transformations::Transformation *>();
        for (auto &i : *yystack_[0].value.as < std::unique_ptr<std::vector<std::unique_ptr<actions::Action> > >  > ().get()) {
            if (dynamic_cast<actions::transformations::Transformation *>(i.get())) {
              t->push_back(dynamic_cast<actions::transformations::Transformation *>(i.release()));
            } else {
              a->push_back(i.release());
            }
        }
        std::unique_ptr<RuleScript> r(new RuleScript(
            /* path to script */ yystack_[1].value.as < std::string > (),
            /* actions */ a,
            /* transformations */ t,
            /* file name */ std::unique_ptr<std::string>(new std::string(*yystack_[1].location.end.filename)),
            /* line number */ yystack_[1].location.end.line
            ));

        if (r->init(&err) == false) {
            driver.error(yystack_[2].location, "Failed to load script: " + err);
            YYERROR;
        }
        if (driver.addSecRuleScript(std::move(r)) == false) {
            YYERROR;
        }
      }
#line 2402 "seclang-parser.cc"
    break;

  case 79: // expression: "CONFIG_DIR_SEC_DEFAULT_ACTION" actions
#line 1176 "seclang-parser.yy"
      {
        bool hasDisruptive = false;
        std::vector<actions::Action *> *actions = new std::vector<actions::Action *>();
        for (auto &i : *yystack_[0].value.as < std::unique_ptr<std::vector<std::unique_ptr<actions::Action> > >  > ().get()) {
            actions->push_back(i.release());
        }
        std::vector<actions::Action *> checkedActions;
        int definedPhase = -1;
        int secRuleDefinedPhase = -1;
        for (actions::Action *a : *actions) {
            actions::Phase *phase = dynamic_cast<actions::Phase *>(a);
            if (a->isDisruptive() == true && dynamic_cast<actions::Block *>(a) == NULL) {
                hasDisruptive = true;
            }
            if (phase != NULL) {
                definedPhase = phase->m_phase;
                secRuleDefinedPhase = phase->m_secRulesPhase;
                delete phase;
            } else if (a->action_kind == actions::Action::RunTimeOnlyIfMatchKind ||
                a->action_kind == actions::Action::RunTimeBeforeMatchAttemptKind) {
                                actions::transformations::None *none = dynamic_cast<actions::transformations::None *>(a);
                if (none != NULL) {
                    driver.error(yystack_[2].location, "The transformation none is not suitable to be part of the SecDefaultActions");
                    YYERROR;
                }
                checkedActions.push_back(a);
            } else {
                driver.error(yystack_[2].location, "The action '" + *a->m_name.get() + "' is not suitable to be part of the SecDefaultActions");
                YYERROR;
            }
        }
        if (definedPhase == -1) {
            definedPhase = modsecurity::Phases::RequestHeadersPhase;
        }

        if (hasDisruptive == false) {
            driver.error(yystack_[2].location, "SecDefaultAction must specify a disruptive action.");
            YYERROR;
        }

        if (!driver.m_defaultActions[definedPhase].empty()) {
            std::stringstream ss;
            ss << "SecDefaultActions can only be placed once per phase and configuration context. Phase ";
            ss << secRuleDefinedPhase;
            ss << " was informed already.";
            driver.error(yystack_[2].location, ss.str());
            YYERROR;
        }

        for (actions::Action *a : checkedActions) {
            driver.m_defaultActions[definedPhase].push_back(
                std::unique_ptr<actions::Action>(a));
        }

        delete actions;
      }
#line 2463 "seclang-parser.cc"
    break;

  case 80: // expression: "CONFIG_DIR_SEC_MARKER"
#line 1233 "seclang-parser.yy"
      {
        driver.addSecMarker(modsecurity::utils::string::removeBracketsIfNeeded(yystack_[0].value.as < std::string > ()),
            /* file name */ std::unique_ptr<std::string>(new std::string(*yystack_[0].location.end.filename)),
            /* line number */ yystack_[0].location.end.line
        );
      }
#line 2474 "seclang-parser.cc"
    break;

  case 81: // expression: "CONFIG_DIR_RULE_ENG" "CONFIG_VALUE_OFF"
#line 1240 "seclang-parser.yy"
      {
        driver.m_secRuleEngine = modsecurity::RulesSet::DisabledRuleEngine;
      }
#line 2482 "seclang-parser.cc"
    break;

  case 82: // expression: "CONFIG_DIR_RULE_ENG" "CONFIG_VALUE_ON"
#line 1244 "seclang-parser.yy"
      {
        driver.m_secRuleEngine = modsecurity::RulesSet::EnabledRuleEngine;
      }
#line 2490 "seclang-parser.cc"
    break;

  case 83: // expression: "CONFIG_DIR_RULE_ENG" "CONFIG_VALUE_DETC"
#line 1248 "seclang-parser.yy"
      {
        driver.m_secRuleEngine = modsecurity::RulesSet::DetectionOnlyRuleEngine;
      }
#line 2498 "seclang-parser.cc"
    break;

  case 84: // expression: "CONFIG_DIR_REQ_BODY" "CONFIG_VALUE_ON"
#line 1252 "seclang-parser.yy"
      {
        driver.m_secRequestBodyAccess = modsecurity::RulesSetProperties::TrueConfigBoolean;
      }
#line 2506 "seclang-parser.cc"
    break;

  case 85: // expression: "CONFIG_DIR_REQ_BODY" "CONFIG_VALUE_OFF"
#line 1256 "seclang-parser.yy"
      {
        driver.m_secRequestBodyAccess = modsecurity::RulesSetProperties::FalseConfigBoolean;
      }
#line 2514 "seclang-parser.cc"
    break;

  case 86: // expression: "CONFIG_DIR_RES_BODY" "CONFIG_VALUE_ON"
#line 1260 "seclang-parser.yy"
      {
        driver.m_secResponseBodyAccess = modsecurity::RulesSetProperties::TrueConfigBoolean;
      }
#line 2522 "seclang-parser.cc"
    break;

  case 87: // expression: "CONFIG_DIR_RES_BODY" "CONFIG_VALUE_OFF"
#line 1264 "seclang-parser.yy"
      {
        driver.m_secResponseBodyAccess = modsecurity::RulesSetProperties::FalseConfigBoolean;
      }
#line 2530 "seclang-parser.cc"
    break;

  case 88: // expression: "CONFIG_SEC_ARGUMENT_SEPARATOR"
#line 1268 "seclang-parser.yy"
      {
        if (yystack_[0].value.as < std::string > ().length() != 1) {
          driver.error(yystack_[1].location, "Argument separator should be set to a single character.");
          YYERROR;
        }
        driver.m_secArgumentSeparator.m_value = yystack_[0].value.as < std::string > ();
        driver.m_secArgumentSeparator.m_set = true;
      }
#line 2543 "seclang-parser.cc"
    break;

  case 89: // expression: "CONFIG_COMPONENT_SIG"
#line 1277 "seclang-parser.yy"
      {
        driver.m_components.push_back(yystack_[0].value.as < std::string > ());
      }
#line 2551 "seclang-parser.cc"
    break;

  case 90: // expression: "CONFIG_CONN_ENGINE" "CONFIG_VALUE_ON"
#line 1281 "seclang-parser.yy"
      {
        driver.error(yystack_[2].location, "SecConnEngine is not yet supported.");
        YYERROR;
      }
#line 2560 "seclang-parser.cc"
    break;

  case 91: // expression: "CONFIG_CONN_ENGINE" "CONFIG_VALUE_OFF"
#line 1286 "seclang-parser.yy"
      {
      }
#line 2567 "seclang-parser.cc"
    break;

  case 92: // expression: "CONFIG_SEC_WEB_APP_ID"
#line 1289 "seclang-parser.yy"
      {
        driver.m_secWebAppId.m_value = yystack_[0].value.as < std::string > ();
        driver.m_secWebAppId.m_set = true;
      }
#line 2576 "seclang-parser.cc"
    break;

  case 93: // expression: "CONFIG_SEC_SERVER_SIG"
#line 1294 "seclang-parser.yy"
      {
        driver.error(yystack_[1].location, "SecServerSignature is not supported.");
        YYERROR;
      }
#line 2585 "seclang-parser.cc"
    break;

  case 94: // expression: "CONFIG_SEC_CACHE_TRANSFORMATIONS"
#line 1299 "seclang-parser.yy"
      {
        driver.error(yystack_[1].location, "SecCacheTransformations is not supported.");
        YYERROR;
      }
#line 2594 "seclang-parser.cc"
    break;

  case 95: // expression: "CONFIG_SEC_DISABLE_BACKEND_COMPRESS" "CONFIG_VALUE_ON"
#line 1304 "seclang-parser.yy"
      {
        driver.error(yystack_[2].location, "SecDisableBackendCompression is not supported.");
        YYERROR;
      }
#line 2603 "seclang-parser.cc"
    break;

  case 96: // expression: "CONFIG_SEC_DISABLE_BACKEND_COMPRESS" "CONFIG_VALUE_OFF"
#line 1309 "seclang-parser.yy"
      {
      }
#line 2610 "seclang-parser.cc"
    break;

  case 97: // expression: "CONFIG_CONTENT_INJECTION" "CONFIG_VALUE_ON"
#line 1312 "seclang-parser.yy"
      {
        driver.error(yystack_[2].location, "SecContentInjection is not yet supported.");
        YYERROR;
      }
#line 2619 "seclang-parser.cc"
    break;

  case 98: // expression: "CONFIG_CONTENT_INJECTION" "CONFIG_VALUE_OFF"
#line 1317 "seclang-parser.yy"
      {
      }
#line 2626 "seclang-parser.cc"
    break;

  case 99: // expression: "CONFIG_SEC_CHROOT_DIR"
#line 1320 "seclang-parser.yy"
      {
        driver.error(yystack_[1].location, "SecChrootDir is not supported.");
        YYERROR;
      }
#line 2635 "seclang-parser.cc"
    break;

  case 100: // expression: "CONFIG_SEC_HASH_ENGINE" "CONFIG_VALUE_ON"
#line 1325 "seclang-parser.yy"
      {
        driver.error(yystack_[2].location, "SecHashEngine is not yet supported.");
        YYERROR;
      }
#line 2644 "seclang-parser.cc"
    break;

  case 101: // expression: "CONFIG_SEC_HASH_ENGINE" "CONFIG_VALUE_OFF"
#line 1330 "seclang-parser.yy"
      {
      }
#line 2651 "seclang-parser.cc"
    break;

  case 102: // expression: "CONFIG_SEC_HASH_KEY"
#line 1333 "seclang-parser.yy"
      {
        driver.error(yystack_[1].location, "SecHashKey is not yet supported.");
        YYERROR;
      }
#line 2660 "seclang-parser.cc"
    break;

  case 103: // expression: "CONFIG_SEC_HASH_PARAM"
#line 1338 "seclang-parser.yy"
      {
        driver.error(yystack_[1].location, "SecHashParam is not yet supported.");
        YYERROR;
      }
#line 2669 "seclang-parser.cc"
    break;

  case 104: // expression: "CONFIG_SEC_HASH_METHOD_RX"
#line 1343 "seclang-parser.yy"
      {
        driver.error(yystack_[1].location, "SecHashMethodRx is not yet supported.");
        YYERROR;
      }
#line 2678 "seclang-parser.cc"
    break;

  case 105: // expression: "CONFIG_SEC_HASH_METHOD_PM"
#line 1348 "seclang-parser.yy"
      {
        driver.error(yystack_[1].location, "SecHashMethodPm is not yet supported.");
        YYERROR;
      }
#line 2687 "seclang-parser.cc"
    break;

  case 106: // expression: "CONFIG_DIR_GSB_DB"
#line 1353 "seclang-parser.yy"
      {
        driver.error(yystack_[1].location, "SecGsbLookupDb is not supported.");
        YYERROR;
      }
#line 2696 "seclang-parser.cc"
    break;

  case 107: // expression: "CONFIG_SEC_GUARDIAN_LOG"
#line 1358 "seclang-parser.yy"
      {
        driver.error(yystack_[1].location, "SecGuardianLog is not supported.");
        YYERROR;
      }
#line 2705 "seclang-parser.cc"
    break;

  case 108: // expression: "CONFIG_SEC_INTERCEPT_ON_ERROR" "CONFIG_VALUE_ON"
#line 1363 "seclang-parser.yy"
      {
        driver.error(yystack_[2].location, "SecInterceptOnError is not yet supported.");
        YYERROR;
      }
#line 2714 "seclang-parser.cc"
    break;

  case 109: // expression: "CONFIG_SEC_INTERCEPT_ON_ERROR" "CONFIG_VALUE_OFF"
#line 1368 "seclang-parser.yy"
      {
      }
#line 2721 "seclang-parser.cc"
    break;

  case 110: // expression: "CONFIG_SEC_CONN_R_STATE_LIMIT"
#line 1371 "seclang-parser.yy"
      {
        driver.error(yystack_[1].location, "SecConnReadStateLimit is not yet supported.");
        YYERROR;
      }
#line 2730 "seclang-parser.cc"
    break;

  case 111: // expression: "CONFIG_SEC_CONN_W_STATE_LIMIT"
#line 1376 "seclang-parser.yy"
      {
        driver.error(yystack_[1].location, "SecConnWriteStateLimit is not yet supported.");
        YYERROR;
      }
#line 2739 "seclang-parser.cc"
    break;

  case 112: // expression: "CONFIG_SEC_SENSOR_ID"
#line 1381 "seclang-parser.yy"
      {
        driver.error(yystack_[1].location, "SecSensorId is not yet supported.");
        YYERROR;
      }
#line 2748 "seclang-parser.cc"
    break;

  case 113: // expression: "CONFIG_SEC_RULE_INHERITANCE" "CONFIG_VALUE_ON"
#line 1386 "seclang-parser.yy"
      {
        driver.error(yystack_[2].location, "SecRuleInheritance is not yet supported.");
        YYERROR;
      }
#line 2757 "seclang-parser.cc"
    break;

  case 114: // expression: "CONFIG_SEC_RULE_INHERITANCE" "CONFIG_VALUE_OFF"
#line 1391 "seclang-parser.yy"
      {
      }
#line 2764 "seclang-parser.cc"
    break;

  case 115: // expression: "CONFIG_SEC_RULE_PERF_TIME"
#line 1394 "seclang-parser.yy"
      {
        driver.error(yystack_[1].location, "SecRulePerfTime is not yet supported.");
        YYERROR;
      }
#line 2773 "seclang-parser.cc"
    break;

  case 116: // expression: "CONFIG_SEC_STREAM_IN_BODY_INSPECTION"
#line 1399 "seclang-parser.yy"
      {
        driver.error(yystack_[1].location, "SecStreamInBodyInspection is not supported.");
        YYERROR;
      }
#line 2782 "seclang-parser.cc"
    break;

  case 117: // expression: "CONFIG_SEC_STREAM_OUT_BODY_INSPECTION"
#line 1404 "seclang-parser.yy"
      {
        driver.error(yystack_[1].location, "SecStreamOutBodyInspection is not supported.");
        YYERROR;
      }
#line 2791 "seclang-parser.cc"
    break;

  case 118: // expression: "CONFIG_SEC_RULE_REMOVE_BY_ID"
#line 1409 "seclang-parser.yy"
      {
        std::string error;
        if (driver.m_exceptions.load(yystack_[0].value.as < std::string > (), &error) == false) {
            std::stringstream ss;
            ss << "SecRuleRemoveById: failed to load:";
            ss << yystack_[0].value.as < std::string > ();
            ss << ". ";
            ss << error;
            driver.error(yystack_[1].location, ss.str());
            YYERROR;
        }
      }
#line 2808 "seclang-parser.cc"
    break;

  case 119: // expression: "CONFIG_SEC_RULE_REMOVE_BY_TAG"
#line 1422 "seclang-parser.yy"
      {
        std::string error;
        if (driver.m_exceptions.loadRemoveRuleByTag(yystack_[0].value.as < std::string > (), &error) == false) {
            std::stringstream ss;
            ss << "SecRuleRemoveByTag: failed to load:";
            ss << yystack_[0].value.as < std::string > ();
            ss << ". ";
            ss << error;
            driver.error(yystack_[1].location, ss.str());
            YYERROR;
        }
      }
#line 2825 "seclang-parser.cc"
    break;

  case 120: // expression: "CONFIG_SEC_RULE_REMOVE_BY_MSG"
#line 1435 "seclang-parser.yy"
      {
        std::string error;
        if (driver.m_exceptions.loadRemoveRuleByMsg(yystack_[0].value.as < std::string > (), &error) == false) {
            std::stringstream ss;
            ss << "SecRuleRemoveByMsg: failed to load:";
            ss << yystack_[0].value.as < std::string > ();
            ss << ". ";
            ss << error;
            driver.error(yystack_[1].location, ss.str());
            YYERROR;
        }
      }
#line 2842 "seclang-parser.cc"
    break;

  case 121: // expression: "CONFIG_SEC_RULE_UPDATE_TARGET_BY_TAG" variables_pre_process
#line 1448 "seclang-parser.yy"
      {
        std::string error;
        if (driver.m_exceptions.loadUpdateTargetByTag(yystack_[1].value.as < std::string > (), std::move(yystack_[0].value.as < std::unique_ptr<std::vector<std::unique_ptr<Variable> > >  > ()), &error) == false) {
            std::stringstream ss;
            ss << "SecRuleUpdateTargetByTag: failed to load:";
            ss << yystack_[1].value.as < std::string > ();
            ss << ". ";
            ss << error;
            driver.error(yystack_[2].location, ss.str());
            YYERROR;
        }
      }
#line 2859 "seclang-parser.cc"
    break;

  case 122: // expression: "CONFIG_SEC_RULE_UPDATE_TARGET_BY_MSG" variables_pre_process
#line 1461 "seclang-parser.yy"
      {
        std::string error;
        if (driver.m_exceptions.loadUpdateTargetByMsg(yystack_[1].value.as < std::string > (), std::move(yystack_[0].value.as < std::unique_ptr<std::vector<std::unique_ptr<Variable> > >  > ()), &error) == false) {
            std::stringstream ss;
            ss << "SecRuleUpdateTargetByMsg: failed to load:";
            ss << yystack_[1].value.as < std::string > ();
            ss << ". ";
            ss << error;
            driver.error(yystack_[2].location, ss.str());
            YYERROR;
        }
      }
#line 2876 "seclang-parser.cc"
    break;

  case 123: // expression: "CONFIG_SEC_RULE_UPDATE_TARGET_BY_ID" variables_pre_process
#line 1474 "seclang-parser.yy"
      {
        std::string error;
        double ruleId;
        try {
            ruleId = std::stod(yystack_[1].value.as < std::string > ());
        } catch (...) {
            std::stringstream ss;
            ss << "SecRuleUpdateTargetById: failed to load:";
            ss << "The input \"" + yystack_[1].value.as < std::string > () + "\" does not ";
            ss << "seems to be a valid rule id.";
            ss << ". ";
            driver.error(yystack_[2].location, ss.str());
            YYERROR;
        }

        if (driver.m_exceptions.loadUpdateTargetById(ruleId, std::move(yystack_[0].value.as < std::unique_ptr<std::vector<std::unique_ptr<Variable> > >  > ()), &error) == false) {
            std::stringstream ss;
            ss << "SecRuleUpdateTargetById: failed to load:";
            ss << yystack_[1].value.as < std::string > ();
            ss << ". ";
            ss << error;
            driver.error(yystack_[2].location, ss.str());
            YYERROR;
        }
      }
#line 2906 "seclang-parser.cc"
    break;

  case 124: // expression: "CONFIG_SEC_RULE_UPDATE_ACTION_BY_ID" actions
#line 1500 "seclang-parser.yy"
      {
        std::string error;
        double ruleId;
        try {
            ruleId = std::stod(yystack_[1].value.as < std::string > ());
        } catch (...) {
            std::stringstream ss;
            ss << "SecRuleUpdateActionById: failed to load:";
            ss << "The input \"" + yystack_[1].value.as < std::string > () + "\" does not ";
            ss << "seems to be a valid rule id.";
            ss << ". ";
            driver.error(yystack_[2].location, ss.str());
            YYERROR;
        }


        if (driver.m_exceptions.loadUpdateActionById(ruleId, std::move(yystack_[0].value.as < std::unique_ptr<std::vector<std::unique_ptr<actions::Action> > >  > ()), &error) == false) {
            std::stringstream ss;
            ss << "SecRuleUpdateActionById: failed to load:";
            ss << yystack_[1].value.as < std::string > ();
            ss << ". ";
            ss << error;
            driver.error(yystack_[2].location, ss.str());
            YYERROR;
        }
      }
#line 2937 "seclang-parser.cc"
    break;

  case 125: // expression: "CONFIG_DIR_DEBUG_LVL"
#line 1528 "seclang-parser.yy"
      {
        if (driver.m_debugLog != NULL) {
          driver.m_debugLog->setDebugLogLevel(atoi(yystack_[0].value.as < std::string > ().c_str()));
        } else {
            std::stringstream ss;
            ss << "Internal error, there is no DebugLog ";
            ss << "object associated with the driver class";
            driver.error(yystack_[1].location, ss.str());
            YYERROR;
        }
      }
#line 2953 "seclang-parser.cc"
    break;

  case 126: // expression: "CONFIG_DIR_DEBUG_LOG"
#line 1540 "seclang-parser.yy"
      {
        if (driver.m_debugLog != NULL) {
            std::string error;
            driver.m_debugLog->setDebugLogFile(yystack_[0].value.as < std::string > (), &error);
            if (error.size() > 0) {
                std::stringstream ss;
                ss << "Failed to start DebugLog: " << error;
                driver.error(yystack_[1].location, ss.str());
                YYERROR;
            }
        } else {
            std::stringstream ss;
            ss << "Internal error, there is no DebugLog ";
            ss << "object associated with the driver class";
            driver.error(yystack_[1].location, ss.str());
            YYERROR;
        }
      }
#line 2976 "seclang-parser.cc"
    break;

  case 127: // expression: "CONFIG_DIR_GEO_DB"
#line 1560 "seclang-parser.yy"
      {
#if defined(WITH_GEOIP) or defined(WITH_MAXMIND)
        std::string err;
        std::string file = modsecurity::utils::find_resource(yystack_[0].value.as < std::string > (),
            *yystack_[0].location.end.filename, &err);
        if (file.empty()) {
            std::stringstream ss;
            ss << "Failed to load locate the GeoDB file from: " << yystack_[0].value.as < std::string > () << " ";
            ss << err;
            driver.error(yystack_[1].location, ss.str());
            YYERROR;
        }
        if (Utils::GeoLookup::getInstance().setDataBase(file, &err) == false) {
            std::stringstream ss;
            ss << "Failed to load the GeoDB from: ";
            ss << file << ". " << err;
            driver.error(yystack_[1].location, ss.str());
            YYERROR;
        }
#else
        std::stringstream ss;
        ss << "This version of ModSecurity was not compiled with GeoIP or MaxMind support.";
        driver.error(yystack_[1].location, ss.str());
        YYERROR;
#endif  // WITH_GEOIP
      }
#line 3007 "seclang-parser.cc"
    break;

  case 128: // expression: "CONFIG_DIR_ARGS_LIMIT"
#line 1587 "seclang-parser.yy"
      {
        driver.m_argumentsLimit.m_set = true;
        driver.m_argumentsLimit.m_value = atoi(yystack_[0].value.as < std::string > ().c_str());
      }
#line 3016 "seclang-parser.cc"
    break;

  case 129: // expression: "CONFIG_DIR_REQ_BODY_JSON_DEPTH_LIMIT"
#line 1592 "seclang-parser.yy"
      {
        driver.m_requestBodyJsonDepthLimit.m_set = true;
        driver.m_requestBodyJsonDepthLimit.m_value = atoi(yystack_[0].value.as < std::string > ().c_str());
      }
#line 3025 "seclang-parser.cc"
    break;

  case 130: // expression: "CONFIG_DIR_REQ_BODY_LIMIT"
#line 1598 "seclang-parser.yy"
      {
        driver.m_requestBodyLimit.m_set = true;
        driver.m_requestBodyLimit.m_value = atoi(yystack_[0].value.as < std::string > ().c_str());
      }
#line 3034 "seclang-parser.cc"
    break;

  case 131: // expression: "CONFIG_DIR_REQ_BODY_NO_FILES_LIMIT"
#line 1603 "seclang-parser.yy"
      {
        driver.m_requestBodyNoFilesLimit.m_set = true;
        driver.m_requestBodyNoFilesLimit.m_value = atoi(yystack_[0].value.as < std::string > ().c_str());
      }
#line 3043 "seclang-parser.cc"
    break;

  case 132: // expression: "CONFIG_DIR_REQ_BODY_IN_MEMORY_LIMIT"
#line 1608 "seclang-parser.yy"
      {
        std::stringstream ss;
        ss << "As of ModSecurity version 3.0, SecRequestBodyInMemoryLimit is no longer ";
        ss << "supported. Instead, you can use your web server configurations to control ";
        ss << "those values. ModSecurity will follow the web server decision.";
        driver.error(yystack_[1].location, ss.str());
        YYERROR;
      }
#line 3056 "seclang-parser.cc"
    break;

  case 133: // expression: "CONFIG_DIR_RES_BODY_LIMIT"
#line 1617 "seclang-parser.yy"
      {
        driver.m_responseBodyLimit.m_set = true;
        driver.m_responseBodyLimit.m_value = atoi(yystack_[0].value.as < std::string > ().c_str());
      }
#line 3065 "seclang-parser.cc"
    break;

  case 134: // expression: "CONFIG_DIR_REQ_BODY_LIMIT_ACTION" "CONFIG_VALUE_PROCESS_PARTIAL"
#line 1622 "seclang-parser.yy"
      {
        driver.m_requestBodyLimitAction = modsecurity::RulesSet::BodyLimitAction::ProcessPartialBodyLimitAction;
      }
#line 3073 "seclang-parser.cc"
    break;

  case 135: // expression: "CONFIG_DIR_REQ_BODY_LIMIT_ACTION" "CONFIG_VALUE_REJECT"
#line 1626 "seclang-parser.yy"
      {
        driver.m_requestBodyLimitAction = modsecurity::RulesSet::BodyLimitAction::RejectBodyLimitAction;
      }
#line 3081 "seclang-parser.cc"
    break;

  case 136: // expression: "CONFIG_DIR_RES_BODY_LIMIT_ACTION" "CONFIG_VALUE_PROCESS_PARTIAL"
#line 1630 "seclang-parser.yy"
      {
        driver.m_responseBodyLimitAction = modsecurity::RulesSet::BodyLimitAction::ProcessPartialBodyLimitAction;
      }
#line 3089 "seclang-parser.cc"
    break;

  case 137: // expression: "CONFIG_DIR_RES_BODY_LIMIT_ACTION" "CONFIG_VALUE_REJECT"
#line 1634 "seclang-parser.yy"
      {
        driver.m_responseBodyLimitAction = modsecurity::RulesSet::BodyLimitAction::RejectBodyLimitAction;
      }
#line 3097 "seclang-parser.cc"
    break;

  case 138: // expression: "CONFIG_SEC_REMOTE_RULES_FAIL_ACTION" "CONFIG_VALUE_ABORT"
#line 1638 "seclang-parser.yy"
      {
        driver.m_remoteRulesActionOnFailed = RulesSet::OnFailedRemoteRulesAction::AbortOnFailedRemoteRulesAction;
      }
#line 3105 "seclang-parser.cc"
    break;

  case 139: // expression: "CONFIG_SEC_REMOTE_RULES_FAIL_ACTION" "CONFIG_VALUE_WARN"
#line 1642 "seclang-parser.yy"
      {
        driver.m_remoteRulesActionOnFailed = RulesSet::OnFailedRemoteRulesAction::WarnOnFailedRemoteRulesAction;
      }
#line 3113 "seclang-parser.cc"
    break;

  case 142: // expression: "CONGIG_DIR_RESPONSE_BODY_MP"
#line 1656 "seclang-parser.yy"
      {
        std::istringstream buf(yystack_[0].value.as < std::string > ());
        std::istream_iterator<std::string> beg(buf), end;
        std::set<std::string> tokens(beg, end);
        driver.m_responseBodyTypeToBeInspected.m_set = true;
        for (std::set<std::string>::iterator it=tokens.begin();
            it!=tokens.end(); ++it)
        {
            driver.m_responseBodyTypeToBeInspected.m_value.insert(*it);
        }
      }
#line 3129 "seclang-parser.cc"
    break;

  case 143: // expression: "CONGIG_DIR_RESPONSE_BODY_MP_CLEAR"
#line 1668 "seclang-parser.yy"
      {
        driver.m_responseBodyTypeToBeInspected.m_set = true;
        driver.m_responseBodyTypeToBeInspected.m_clear = true;
        driver.m_responseBodyTypeToBeInspected.m_value.clear();
      }
#line 3139 "seclang-parser.cc"
    break;

  case 144: // expression: "CONFIG_XML_EXTERNAL_ENTITY" "CONFIG_VALUE_OFF"
#line 1674 "seclang-parser.yy"
      {
        driver.m_secXMLExternalEntity = modsecurity::RulesSetProperties::FalseConfigBoolean;
      }
#line 3147 "seclang-parser.cc"
    break;

  case 145: // expression: "CONFIG_XML_EXTERNAL_ENTITY" "CONFIG_VALUE_ON"
#line 1678 "seclang-parser.yy"
      {
        driver.m_secXMLExternalEntity = modsecurity::RulesSetProperties::TrueConfigBoolean;
      }
#line 3155 "seclang-parser.cc"
    break;

  case 146: // expression: "CONGIG_DIR_SEC_TMP_DIR"
#line 1682 "seclang-parser.yy"
      {
/* Parser error disabled to avoid breaking default installations with modsecurity.conf-recommended
        std::stringstream ss;
        ss << "As of ModSecurity version 3.0, SecTmpDir is no longer supported.";
        ss << " Instead, you can use your web server configurations to control when";
        ss << "and where to swap. ModSecurity will follow the web server decision.";
        driver.error(@0, ss.str());
        YYERROR;
*/
      }
#line 3170 "seclang-parser.cc"
    break;

  case 149: // expression: "CONGIG_DIR_SEC_COOKIE_FORMAT"
#line 1703 "seclang-parser.yy"
      {
        if (atoi(yystack_[0].value.as < std::string > ().c_str()) == 1) {
          driver.error(yystack_[1].location, "SecCookieFormat 1 is not yet supported.");
          YYERROR;
        }
      }
#line 3181 "seclang-parser.cc"
    break;

  case 150: // expression: "CONFIG_SEC_COOKIEV0_SEPARATOR"
#line 1710 "seclang-parser.yy"
      {
        driver.error(yystack_[1].location, "SecCookieV0Separator is not yet supported.");
        YYERROR;
      }
#line 3190 "seclang-parser.cc"
    break;

  case 152: // expression: "CONFIG_DIR_UNICODE_MAP_FILE"
#line 1720 "seclang-parser.yy"
      {
        std::string error;
        std::vector<std::string> param;
        double num = 0;
        std::string f;
        std::string file;
        std::string err;
        param = utils::string::ssplit(yystack_[0].value.as < std::string > (), ' ');
        if (param.size() <= 1) {
            std::stringstream ss;
            ss << "Failed to process unicode map, missing ";
            ss << "parameter: " << yystack_[0].value.as < std::string > () << " ";
            driver.error(yystack_[1].location, ss.str());
            YYERROR;
        }

        try {
            num = std::stod(param.back());
        } catch (...) {
            std::stringstream ss;
            ss << "Failed to process unicode map, last parameter is ";
            ss << "expected to be a number: " << param.back() << " ";
            driver.error(yystack_[1].location, ss.str());
            YYERROR;
        }
        param.pop_back();

        while (param.size() > 0) {
            if (f.empty()) {
                f = param.back();
            } else {
                f = param.back() + " " + f;
            }
            param.pop_back();
        }

        file = modsecurity::utils::find_resource(f, *yystack_[0].location.end.filename, &err);
        if (file.empty()) {
            std::stringstream ss;
            ss << "Failed to locate the unicode map file from: " << f << " ";
            ss << err;
            driver.error(yystack_[1].location, ss.str());
            YYERROR;
        }

        ConfigUnicodeMap::loadConfig(file, num, &driver, &error);

        if (!error.empty()) {
            driver.error(yystack_[1].location, error);
            YYERROR;
        }

      }
#line 3248 "seclang-parser.cc"
    break;

  case 153: // expression: "CONFIG_SEC_COLLECTION_TIMEOUT"
#line 1774 "seclang-parser.yy"
      {
/* Parser error disabled to avoid breaking default CRS installations with crs-setup.conf-recommended
        driver.error(@0, "SecCollectionTimeout is not yet supported.");
        YYERROR;
*/
      }
#line 3259 "seclang-parser.cc"
    break;

  case 154: // expression: "CONFIG_SEC_HTTP_BLKEY"
#line 1781 "seclang-parser.yy"
      {
        driver.m_httpblKey.m_set = true;
        driver.m_httpblKey.m_value = yystack_[0].value.as < std::string > ();
      }
#line 3268 "seclang-parser.cc"
    break;

  case 155: // variables: variables_pre_process
#line 1789 "seclang-parser.yy"
      {
        std::unique_ptr<std::vector<std::unique_ptr<Variable> > > originalList = std::move(yystack_[0].value.as < std::unique_ptr<std::vector<std::unique_ptr<Variable> > >  > ());
        std::unique_ptr<std::vector<std::unique_ptr<Variable>>> newList(new std::vector<std::unique_ptr<Variable>>());
        std::unique_ptr<std::vector<std::unique_ptr<Variable>>> newNewList(new std::vector<std::unique_ptr<Variable>>());
        std::unique_ptr<std::vector<std::unique_ptr<Variable>>> exclusionVars(new std::vector<std::unique_ptr<Variable>>());
        while (!originalList->empty()) {
            std::unique_ptr<Variable> var = std::move(originalList->back());
            originalList->pop_back();
            if (dynamic_cast<VariableModificatorExclusion*>(var.get())) {
                exclusionVars->push_back(std::move(var));
            } else {
                newList->push_back(std::move(var));
            }
        }

        while (!newList->empty()) {
            bool doNotAdd = false;
            std::unique_ptr<Variable> var = std::move(newList->back());
            newList->pop_back();
            for (auto &i : *exclusionVars) {
                if (*var == *i) {
                    doNotAdd = true;
                }
                if (i->belongsToCollection(var.get())) {
                    var->addsKeyExclusion(i.get());
                }
            }
            if (!doNotAdd) {
                newNewList->push_back(std::move(var));
            }
        }
        yylhs.value.as < std::unique_ptr<std::vector<std::unique_ptr<Variable> > >  > () = std::move(newNewList);
      }
#line 3306 "seclang-parser.cc"
    break;

  case 156: // variables_pre_process: variables_may_be_quoted
#line 1826 "seclang-parser.yy"
      {
        yylhs.value.as < std::unique_ptr<std::vector<std::unique_ptr<Variable> > >  > () = std::move(yystack_[0].value.as < std::unique_ptr<std::vector<std::unique_ptr<Variable> > >  > ());
      }
#line 3314 "seclang-parser.cc"
    break;

  case 157: // variables_pre_process: "QUOTATION_MARK" variables_may_be_quoted "QUOTATION_MARK"
#line 1830 "seclang-parser.yy"
      {
        yylhs.value.as < std::unique_ptr<std::vector<std::unique_ptr<Variable> > >  > () = std::move(yystack_[1].value.as < std::unique_ptr<std::vector<std::unique_ptr<Variable> > >  > ());
      }
#line 3322 "seclang-parser.cc"
    break;

  case 158: // variables_may_be_quoted: variables_may_be_quoted PIPE var
#line 1837 "seclang-parser.yy"
      {
        yystack_[2].value.as < std::unique_ptr<std::vector<std::unique_ptr<Variable> > >  > ()->push_back(std::move(yystack_[0].value.as < std::unique_ptr<Variable> > ()));
        yylhs.value.as < std::unique_ptr<std::vector<std::unique_ptr<Variable> > >  > () = std::move(yystack_[2].value.as < std::unique_ptr<std::vector<std::unique_ptr<Variable> > >  > ());
      }
#line 3331 "seclang-parser.cc"
    break;

  case 159: // variables_may_be_quoted: variables_may_be_quoted PIPE VAR_EXCLUSION var
#line 1842 "seclang-parser.yy"
      {
        std::unique_ptr<Variable> c(new VariableModificatorExclusion(std::move(yystack_[0].value.as < std::unique_ptr<Variable> > ())));
        yystack_[3].value.as < std::unique_ptr<std::vector<std::unique_ptr<Variable> > >  > ()->push_back(std::move(c));
        yylhs.value.as < std::unique_ptr<std::vector<std::unique_ptr<Variable> > >  > () = std::move(yystack_[3].value.as < std::unique_ptr<std::vector<std::unique_ptr<Variable> > >  > ());
      }
#line 3341 "seclang-parser.cc"
    break;

  case 160: // variables_may_be_quoted: variables_may_be_quoted PIPE VAR_COUNT var
#line 1848 "seclang-parser.yy"
      {
        std::unique_ptr<Variable> c(new VariableModificatorCount(std::move(yystack_[0].value.as < std::unique_ptr<Variable> > ())));
        yystack_[3].value.as < std::unique_ptr<std::vector<std::unique_ptr<Variable> > >  > ()->push_back(std::move(c));
        yylhs.value.as < std::unique_ptr<std::vector<std::unique_ptr<Variable> > >  > () = std::move(yystack_[3].value.as < std::unique_ptr<std::vector<std::unique_ptr<Variable> > >  > ());
      }
#line 3351 "seclang-parser.cc"
    break;

  case 161: // variables_may_be_quoted: var
#line 1854 "seclang-parser.yy"
      {
        std::unique_ptr<std::vector<std::unique_ptr<Variable>>> b(new std::vector<std::unique_ptr<Variable>>());
        b->push_back(std::move(yystack_[0].value.as < std::unique_ptr<Variable> > ()));
        yylhs.value.as < std::unique_ptr<std::vector<std::unique_ptr<Variable> > >  > () = std::move(b);
      }
#line 3361 "seclang-parser.cc"
    break;

  case 162: // variables_may_be_quoted: VAR_EXCLUSION var
#line 1860 "seclang-parser.yy"
      {
        std::unique_ptr<std::vector<std::unique_ptr<Variable>>> b(new std::vector<std::unique_ptr<Variable>>());
        std::unique_ptr<Variable> c(new VariableModificatorExclusion(std::move(yystack_[0].value.as < std::unique_ptr<Variable> > ())));
        b->push_back(std::move(c));
        yylhs.value.as < std::unique_ptr<std::vector<std::unique_ptr<Variable> > >  > () = std::move(b);
      }
#line 3372 "seclang-parser.cc"
    break;

  case 163: // variables_may_be_quoted: VAR_COUNT var
#line 1867 "seclang-parser.yy"
      {
        std::unique_ptr<std::vector<std::unique_ptr<Variable>>> b(new std::vector<std::unique_ptr<Variable>>());
        std::unique_ptr<Variable> c(new VariableModificatorCount(std::move(yystack_[0].value.as < std::unique_ptr<Variable> > ())));
        b->push_back(std::move(c));
        yylhs.value.as < std::unique_ptr<std::vector<std::unique_ptr<Variable> > >  > () = std::move(b);
      }
#line 3383 "seclang-parser.cc"
    break;

  case 164: // var: VARIABLE_ARGS "Dictionary element"
#line 1877 "seclang-parser.yy"
      {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::Args_DictElement(yystack_[0].value.as < std::string > ()));
      }
#line 3391 "seclang-parser.cc"
    break;

  case 165: // var: VARIABLE_ARGS "Dictionary element, selected by regexp"
#line 1881 "seclang-parser.yy"
      {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::Args_DictElementRegexp(yystack_[0].value.as < std::string > ()));
      }
#line 3399 "seclang-parser.cc"
    break;

  case 166: // var: VARIABLE_ARGS
#line 1885 "seclang-parser.yy"
      {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::Args_NoDictElement());
      }
#line 3407 "seclang-parser.cc"
    break;

  case 167: // var: VARIABLE_ARGS_POST "Dictionary element"
#line 1889 "seclang-parser.yy"
      {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::ArgsPost_DictElement(yystack_[0].value.as < std::string > ()));
      }
#line 3415 "seclang-parser.cc"
    break;

  case 168: // var: VARIABLE_ARGS_POST "Dictionary element, selected by regexp"
#line 1893 "seclang-parser.yy"
      {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::ArgsPost_DictElementRegexp(yystack_[0].value.as < std::string > ()));
      }
#line 3423 "seclang-parser.cc"
    break;

  case 169: // var: VARIABLE_ARGS_POST
#line 1897 "seclang-parser.yy"
      {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::ArgsPost_NoDictElement());
      }
#line 3431 "seclang-parser.cc"
    break;

  case 170: // var: VARIABLE_ARGS_GET "Dictionary element"
#line 1901 "seclang-parser.yy"
      {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::ArgsGet_DictElement(yystack_[0].value.as < std::string > ()));
      }
#line 3439 "seclang-parser.cc"
    break;

  case 171: // var: VARIABLE_ARGS_GET "Dictionary element, selected by regexp"
#line 1905 "seclang-parser.yy"
      {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::ArgsGet_DictElementRegexp(yystack_[0].value.as < std::string > ()));
      }
#line 3447 "seclang-parser.cc"
    break;

  case 172: // var: VARIABLE_ARGS_GET
#line 1909 "seclang-parser.yy"
      {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::ArgsGet_NoDictElement());
      }
#line 3455 "seclang-parser.cc"
    break;

  case 173: // var: VARIABLE_FILES_SIZES "Dictionary element"
#line 1913 "seclang-parser.yy"
      {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::FilesSizes_DictElement(yystack_[0].value.as < std::string > ()));
      }
#line 3463 "seclang-parser.cc"
    break;

  case 174: // var: VARIABLE_FILES_SIZES "Dictionary element, selected by regexp"
#line 1917 "seclang-parser.yy"
      {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::FilesSizes_DictElementRegexp(yystack_[0].value.as < std::string > ()));
      }
#line 3471 "seclang-parser.cc"
    break;

  case 175: // var: VARIABLE_FILES_SIZES
#line 1921 "seclang-parser.yy"
      {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::FilesSizes_NoDictElement());
      }
#line 3479 "seclang-parser.cc"
    break;

  case 176: // var: VARIABLE_FILES_NAMES "Dictionary element"
#line 1925 "seclang-parser.yy"
      {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::FilesNames_DictElement(yystack_[0].value.as < std::string > ()));
      }
#line 3487 "seclang-parser.cc"
    break;

  case 177: // var: VARIABLE_FILES_NAMES "Dictionary element, selected by regexp"
#line 1929 "seclang-parser.yy"
      {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::FilesNames_DictElementRegexp(yystack_[0].value.as < std::string > ()));
      }
#line 3495 "seclang-parser.cc"
    break;

  case 178: // var: VARIABLE_FILES_NAMES
#line 1933 "seclang-parser.yy"
      {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::FilesNames_NoDictElement());
      }
#line 3503 "seclang-parser.cc"
    break;

  case 179: // var: VARIABLE_FILES_TMP_CONTENT "Dictionary element"
#line 1937 "seclang-parser.yy"
      {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::FilesTmpContent_DictElement(yystack_[0].value.as < std::string > ()));
      }
#line 3511 "seclang-parser.cc"
    break;

  case 180: // var: VARIABLE_FILES_TMP_CONTENT "Dictionary element, selected by regexp"
#line 1941 "seclang-parser.yy"
      {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::FilesTmpContent_DictElementRegexp(yystack_[0].value.as < std::string > ()));
      }
#line 3519 "seclang-parser.cc"
    break;

  case 181: // var: VARIABLE_FILES_TMP_CONTENT
#line 1945 "seclang-parser.yy"
      {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::FilesTmpContent_NoDictElement());
      }
#line 3527 "seclang-parser.cc"
    break;

  case 182: // var: VARIABLE_MULTIPART_FILENAME "Dictionary element"
#line 1949 "seclang-parser.yy"
      {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::MultiPartFileName_DictElement(yystack_[0].value.as < std::string > ()));
      }
#line 3535 "seclang-parser.cc"
    break;

  case 183: // var: VARIABLE_MULTIPART_FILENAME "Dictionary element, selected by regexp"
#line 1953 "seclang-parser.yy"
      {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::MultiPartFileName_DictElementRegexp(yystack_[0].value.as < std::string > ()));
      }
#line 3543 "seclang-parser.cc"
    break;

  case 184: // var: VARIABLE_MULTIPART_FILENAME
#line 1957 "seclang-parser.yy"
      {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::MultiPartFileName_NoDictElement());
      }
#line 3551 "seclang-parser.cc"
    break;

  case 185: // var: VARIABLE_MULTIPART_NAME "Dictionary element"
#line 1961 "seclang-parser.yy"
      {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::MultiPartName_DictElement(yystack_[0].value.as < std::string > ()));
      }
#line 3559 "seclang-parser.cc"
    break;

  case 186: // var: VARIABLE_MULTIPART_NAME "Dictionary element, selected by regexp"
#line 1965 "seclang-parser.yy"
      {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::MultiPartName_DictElementRegexp(yystack_[0].value.as < std::string > ()));
      }
#line 3567 "seclang-parser.cc"
    break;

  case 187: // var: VARIABLE_MULTIPART_NAME
#line 1969 "seclang-parser.yy"
      {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::MultiPartName_NoDictElement());
      }
#line 3575 "seclang-parser.cc"
    break;

  case 188: // var: VARIABLE_MATCHED_VARS_NAMES "Dictionary element"
#line 1973 "seclang-parser.yy"
      {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::MatchedVarsNames_DictElement(yystack_[0].value.as < std::string > ()));
      }
#line 3583 "seclang-parser.cc"
    break;

  case 189: // var: VARIABLE_MATCHED_VARS_NAMES "Dictionary element, selected by regexp"
#line 1977 "seclang-parser.yy"
      {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::MatchedVarsNames_DictElementRegexp(yystack_[0].value.as < std::string > ()));
      }
#line 3591 "seclang-parser.cc"
    break;

  case 190: // var: VARIABLE_MATCHED_VARS_NAMES
#line 1981 "seclang-parser.yy"
      {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::MatchedVarsNames_NoDictElement());
      }
#line 3599 "seclang-parser.cc"
    break;

  case 191: // var: VARIABLE_MATCHED_VARS "Dictionary element"
#line 1985 "seclang-parser.yy"
      {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::MatchedVars_DictElement(yystack_[0].value.as < std::string > ()));
      }
#line 3607 "seclang-parser.cc"
    break;

  case 192: // var: VARIABLE_MATCHED_VARS "Dictionary element, selected by regexp"
#line 1989 "seclang-parser.yy"
      {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::MatchedVars_DictElementRegexp(yystack_[0].value.as < std::string > ()));
      }
#line 3615 "seclang-parser.cc"
    break;

  case 193: // var: VARIABLE_MATCHED_VARS
#line 1993 "seclang-parser.yy"
      {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::MatchedVars_NoDictElement());
      }
#line 3623 "seclang-parser.cc"
    break;

  case 194: // var: VARIABLE_FILES "Dictionary element"
#line 1997 "seclang-parser.yy"
      {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::Files_DictElement(yystack_[0].value.as < std::string > ()));
      }
#line 3631 "seclang-parser.cc"
    break;

  case 195: // var: VARIABLE_FILES "Dictionary element, selected by regexp"
#line 2001 "seclang-parser.yy"
      {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::Files_DictElementRegexp(yystack_[0].value.as < std::string > ()));
      }
#line 3639 "seclang-parser.cc"
    break;

  case 196: // var: VARIABLE_FILES
#line 2005 "seclang-parser.yy"
      {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::Files_NoDictElement());
      }
#line 3647 "seclang-parser.cc"
    break;

  case 197: // var: VARIABLE_REQUEST_COOKIES "Dictionary element"
#line 2009 "seclang-parser.yy"
      {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::RequestCookies_DictElement(yystack_[0].value.as < std::string > ()));
      }
#line 3655 "seclang-parser.cc"
    break;

  case 198: // var: VARIABLE_REQUEST_COOKIES "Dictionary element, selected by regexp"
#line 2013 "seclang-parser.yy"
      {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::RequestCookies_DictElementRegexp(yystack_[0].value.as < std::string > ()));
      }
#line 3663 "seclang-parser.cc"
    break;

  case 199: // var: VARIABLE_REQUEST_COOKIES
#line 2017 "seclang-parser.yy"
      {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::RequestCookies_NoDictElement());
      }
#line 3671 "seclang-parser.cc"
    break;

  case 200: // var: VARIABLE_REQUEST_HEADERS "Dictionary element"
#line 2021 "seclang-parser.yy"
      {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::RequestHeaders_DictElement(yystack_[0].value.as < std::string > ()));
      }
#line 3679 "seclang-parser.cc"
    break;

  case 201: // var: VARIABLE_REQUEST_HEADERS "Dictionary element, selected by regexp"
#line 2025 "seclang-parser.yy"
      {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::RequestHeaders_DictElementRegexp(yystack_[0].value.as < std::string > ()));
      }
#line 3687 "seclang-parser.cc"
    break;

  case 202: // var: VARIABLE_REQUEST_HEADERS
#line 2029 "seclang-parser.yy"
      {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::RequestHeaders_NoDictElement());
      }
#line 3695 "seclang-parser.cc"
    break;

  case 203: // var: VARIABLE_RESPONSE_HEADERS "Dictionary element"
#line 2033 "seclang-parser.yy"
      {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::ResponseHeaders_DictElement(yystack_[0].value.as < std::string > ()));
      }
#line 3703 "seclang-parser.cc"
    break;

  case 204: // var: VARIABLE_RESPONSE_HEADERS "Dictionary element, selected by regexp"
#line 2037 "seclang-parser.yy"
      {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::ResponseHeaders_DictElementRegexp(yystack_[0].value.as < std::string > ()));
      }
#line 3711 "seclang-parser.cc"
    break;

  case 205: // var: VARIABLE_RESPONSE_HEADERS
#line 2041 "seclang-parser.yy"
      {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::ResponseHeaders_NoDictElement());
      }
#line 3719 "seclang-parser.cc"
    break;

  case 206: // var: VARIABLE_GEO "Dictionary element"
#line 2045 "seclang-parser.yy"
      {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::Geo_DictElement(yystack_[0].value.as < std::string > ()));
      }
#line 3727 "seclang-parser.cc"
    break;

  case 207: // var: VARIABLE_GEO "Dictionary element, selected by regexp"
#line 2049 "seclang-parser.yy"
      {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::Geo_DictElementRegexp(yystack_[0].value.as < std::string > ()));
      }
#line 3735 "seclang-parser.cc"
    break;

  case 208: // var: VARIABLE_GEO
#line 2053 "seclang-parser.yy"
      {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::Geo_NoDictElement());
      }
#line 3743 "seclang-parser.cc"
    break;

  case 209: // var: VARIABLE_REQUEST_COOKIES_NAMES "Dictionary element"
#line 2057 "seclang-parser.yy"
      {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::RequestCookiesNames_DictElement(yystack_[0].value.as < std::string > ()));
      }
#line 3751 "seclang-parser.cc"
    break;

  case 210: // var: VARIABLE_REQUEST_COOKIES_NAMES "Dictionary element, selected by regexp"
#line 2061 "seclang-parser.yy"
      {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::RequestCookiesNames_DictElementRegexp(yystack_[0].value.as < std::string > ()));
      }
#line 3759 "seclang-parser.cc"
    break;

  case 211: // var: VARIABLE_REQUEST_COOKIES_NAMES
#line 2065 "seclang-parser.yy"
      {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::RequestCookiesNames_NoDictElement());
      }
#line 3767 "seclang-parser.cc"
    break;

  case 212: // var: VARIABLE_MULTIPART_PART_HEADERS "Dictionary element"
#line 2069 "seclang-parser.yy"
      {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::MultipartPartHeaders_DictElement(yystack_[0].value.as < std::string > ()));
      }
#line 3775 "seclang-parser.cc"
    break;

  case 213: // var: VARIABLE_MULTIPART_PART_HEADERS "Dictionary element, selected by regexp"
#line 2073 "seclang-parser.yy"
      {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::MultipartPartHeaders_DictElementRegexp(yystack_[0].value.as < std::string > ()));
      }
#line 3783 "seclang-parser.cc"
    break;

  case 214: // var: VARIABLE_MULTIPART_PART_HEADERS
#line 2077 "seclang-parser.yy"
      {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::MultipartPartHeaders_NoDictElement());
      }
#line 3791 "seclang-parser.cc"
    break;

  case 215: // var: VARIABLE_RULE "Dictionary element"
#line 2081 "seclang-parser.yy"
      {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::Rule_DictElement(yystack_[0].value.as < std::string > ()));
      }
#line 3799 "seclang-parser.cc"
    break;

  case 216: // var: VARIABLE_RULE "Dictionary element, selected by regexp"
#line 2085 "seclang-parser.yy"
      {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::Rule_DictElementRegexp(yystack_[0].value.as < std::string > ()));
      }
#line 3807 "seclang-parser.cc"
    break;

  case 217: // var: VARIABLE_RULE
#line 2089 "seclang-parser.yy"
      {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::Rule_NoDictElement());
      }
#line 3815 "seclang-parser.cc"
    break;

  case 218: // var: "RUN_TIME_VAR_ENV" "Dictionary element"
#line 2093 "seclang-parser.yy"
      {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::Env("ENV:" + yystack_[0].value.as < std::string > ()));
      }
#line 3823 "seclang-parser.cc"
    break;

  case 219: // var: "RUN_TIME_VAR_ENV" "Dictionary element, selected by regexp"
#line 2097 "seclang-parser.yy"
      {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::Env("ENV:" + yystack_[0].value.as < std::string > ()));
      }
#line 3831 "seclang-parser.cc"
    break;

  case 220: // var: "RUN_TIME_VAR_ENV"
#line 2101 "seclang-parser.yy"
      {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::Env("ENV"));
      }
#line 3839 "seclang-parser.cc"
    break;

  case 221: // var: "RUN_TIME_VAR_XML" "Dictionary element"
#line 2105 "seclang-parser.yy"
      {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::XML("XML:" + yystack_[0].value.as < std::string > ()));
      }
#line 3847 "seclang-parser.cc"
    break;

  case 222: // var: "RUN_TIME_VAR_XML" "Dictionary element, selected by regexp"
#line 2109 "seclang-parser.yy"
      {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::XML("XML:" + yystack_[0].value.as < std::string > ()));
      }
#line 3855 "seclang-parser.cc"
    break;

  case 223: // var: "RUN_TIME_VAR_XML"
#line 2113 "seclang-parser.yy"
      {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::XML_NoDictElement());
      }
#line 3863 "seclang-parser.cc"
    break;

  case 224: // var: "FILES_TMPNAMES" "Dictionary element"
#line 2117 "seclang-parser.yy"
      {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::FilesTmpNames_DictElement(yystack_[0].value.as < std::string > ()));
      }
#line 3871 "seclang-parser.cc"
    break;

  case 225: // var: "FILES_TMPNAMES" "Dictionary element, selected by regexp"
#line 2121 "seclang-parser.yy"
      {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::FilesTmpNames_DictElementRegexp(yystack_[0].value.as < std::string > ()));
      }
#line 3879 "seclang-parser.cc"
    break;

  case 226: // var: "FILES_TMPNAMES"
#line 2125 "seclang-parser.yy"
      {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::FilesTmpNames_NoDictElement());
      }
#line 3887 "seclang-parser.cc"
    break;

  case 227: // var: "RESOURCE" run_time_string
#line 2129 "seclang-parser.yy"
      {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::Resource_DynamicElement(std::move(yystack_[0].value.as < std::unique_ptr<RunTimeString> > ())));
      }
#line 3895 "seclang-parser.cc"
    break;

  case 228: // var: "RESOURCE" "Dictionary element"
#line 2133 "seclang-parser.yy"
      {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::Resource_DictElement(yystack_[0].value.as < std::string > ()));
      }
#line 3903 "seclang-parser.cc"
    break;

  case 229: // var: "RESOURCE" "Dictionary element, selected by regexp"
#line 2137 "seclang-parser.yy"
      {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::Resource_DictElementRegexp(yystack_[0].value.as < std::string > ()));
      }
#line 3911 "seclang-parser.cc"
    break;

  case 230: // var: "RESOURCE"
#line 2141 "seclang-parser.yy"
      {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::Resource_NoDictElement());
      }
#line 3919 "seclang-parser.cc"
    break;

  case 231: // var: "VARIABLE_IP" run_time_string
#line 2145 "seclang-parser.yy"
      {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::Ip_DynamicElement(std::move(yystack_[0].value.as < std::unique_ptr<RunTimeString> > ())));
      }
#line 3927 "seclang-parser.cc"
    break;

  case 232: // var: "VARIABLE_IP" "Dictionary element"
#line 2149 "seclang-parser.yy"
      {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::Ip_DictElement(yystack_[0].value.as < std::string > ()));
      }
#line 3935 "seclang-parser.cc"
    break;

  case 233: // var: "VARIABLE_IP" "Dictionary element, selected by regexp"
#line 2153 "seclang-parser.yy"
      {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::Ip_DictElementRegexp(yystack_[0].value.as < std::string > ()));
      }
#line 3943 "seclang-parser.cc"
    break;

  case 234: // var: "VARIABLE_IP"
#line 2157 "seclang-parser.yy"
      {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::Ip_NoDictElement());
      }
#line 3951 "seclang-parser.cc"
    break;

  case 235: // var: "VARIABLE_GLOBAL" run_time_string
#line 2161 "seclang-parser.yy"
      {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::Global_DynamicElement(std::move(yystack_[0].value.as < std::unique_ptr<RunTimeString> > ())));
      }
#line 3959 "seclang-parser.cc"
    break;

  case 236: // var: "VARIABLE_GLOBAL" "Dictionary element"
#line 2165 "seclang-parser.yy"
      {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::Global_DictElement(yystack_[0].value.as < std::string > ()));
      }
#line 3967 "seclang-parser.cc"
    break;

  case 237: // var: "VARIABLE_GLOBAL" "Dictionary element, selected by regexp"
#line 2169 "seclang-parser.yy"
      {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::Global_DictElementRegexp(yystack_[0].value.as < std::string > ()));
      }
#line 3975 "seclang-parser.cc"
    break;

  case 238: // var: "VARIABLE_GLOBAL"
#line 2173 "seclang-parser.yy"
      {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::Global_NoDictElement());
      }
#line 3983 "seclang-parser.cc"
    break;

  case 239: // var: "VARIABLE_USER" run_time_string
#line 2177 "seclang-parser.yy"
      {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::User_DynamicElement(std::move(yystack_[0].value.as < std::unique_ptr<RunTimeString> > ())));
      }
#line 3991 "seclang-parser.cc"
    break;

  case 240: // var: "VARIABLE_USER" "Dictionary element"
#line 2181 "seclang-parser.yy"
      {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::User_DictElement(yystack_[0].value.as < std::string > ()));
      }
#line 3999 "seclang-parser.cc"
    break;

  case 241: // var: "VARIABLE_USER" "Dictionary element, selected by regexp"
#line 2185 "seclang-parser.yy"
      {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::User_DictElementRegexp(yystack_[0].value.as < std::string > ()));
      }
#line 4007 "seclang-parser.cc"
    break;

  case 242: // var: "VARIABLE_USER"
#line 2189 "seclang-parser.yy"
      {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::User_NoDictElement());
      }
#line 4015 "seclang-parser.cc"
    break;

  case 243: // var: "VARIABLE_TX" run_time_string
#line 2193 "seclang-parser.yy"
      {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::Tx_DynamicElement(std::move(yystack_[0].value.as < std::unique_ptr<RunTimeString> > ())));
      }
#line 4023 "seclang-parser.cc"
    break;

  case 244: // var: "VARIABLE_TX" "Dictionary element"
#line 2197 "seclang-parser.yy"
      {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::Tx_DictElement(yystack_[0].value.as < std::string > ()));
      }
#line 4031 "seclang-parser.cc"
    break;

  case 245: // var: "VARIABLE_TX" "Dictionary element, selected by regexp"
#line 2201 "seclang-parser.yy"
      {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::Tx_DictElementRegexp(yystack_[0].value.as < std::string > ()));
      }
#line 4039 "seclang-parser.cc"
    break;

  case 246: // var: "VARIABLE_TX"
#line 2205 "seclang-parser.yy"
      {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::Tx_NoDictElement());
      }
#line 4047 "seclang-parser.cc"
    break;

  case 247: // var: "VARIABLE_SESSION" run_time_string
#line 2209 "seclang-parser.yy"
      {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::Session_DynamicElement(std::move(yystack_[0].value.as < std::unique_ptr<RunTimeString> > ())));
      }
#line 4055 "seclang-parser.cc"
    break;

  case 248: // var: "VARIABLE_SESSION" "Dictionary element"
#line 2213 "seclang-parser.yy"
      {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::Session_DictElement(yystack_[0].value.as < std::string > ()));
      }
#line 4063 "seclang-parser.cc"
    break;

  case 249: // var: "VARIABLE_SESSION" "Dictionary element, selected by regexp"
#line 2217 "seclang-parser.yy"
      {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::Session_DictElementRegexp(yystack_[0].value.as < std::string > ()));
      }
#line 4071 "seclang-parser.cc"
    break;

  case 250: // var: "VARIABLE_SESSION"
#line 2221 "seclang-parser.yy"
      {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::Session_NoDictElement());
      }
#line 4079 "seclang-parser.cc"
    break;

  case 251: // var: "Variable ARGS_NAMES" "Dictionary element"
#line 2225 "seclang-parser.yy"
      {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::ArgsNames_DictElement(yystack_[0].value.as < std::string > ()));
      }
#line 4087 "seclang-parser.cc"
    break;

  case 252: // var: "Variable ARGS_NAMES" "Dictionary element, selected by regexp"
#line 2229 "seclang-parser.yy"
      {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::ArgsNames_DictElementRegexp(yystack_[0].value.as < std::string > ()));
      }
#line 4095 "seclang-parser.cc"
    break;

  case 253: // var: "Variable ARGS_NAMES"
#line 2233 "seclang-parser.yy"
      {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::ArgsNames_NoDictElement());
      }
#line 4103 "seclang-parser.cc"
    break;

  case 254: // var: VARIABLE_ARGS_GET_NAMES "Dictionary element"
#line 2237 "seclang-parser.yy"
      {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::ArgsGetNames_DictElement(yystack_[0].value.as < std::string > ()));
      }
#line 4111 "seclang-parser.cc"
    break;

  case 255: // var: VARIABLE_ARGS_GET_NAMES "Dictionary element, selected by regexp"
#line 2241 "seclang-parser.yy"
      {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::ArgsGetNames_DictElementRegexp(yystack_[0].value.as < std::string > ()));
      }
#line 4119 "seclang-parser.cc"
    break;

  case 256: // var: VARIABLE_ARGS_GET_NAMES
#line 2245 "seclang-parser.yy"
      {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::ArgsGetNames_NoDictElement());
      }
#line 4127 "seclang-parser.cc"
    break;

  case 257: // var: VARIABLE_ARGS_POST_NAMES "Dictionary element"
#line 2250 "seclang-parser.yy"
      {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::ArgsPostNames_DictElement(yystack_[0].value.as < std::string > ()));
      }
#line 4135 "seclang-parser.cc"
    break;

  case 258: // var: VARIABLE_ARGS_POST_NAMES "Dictionary element, selected by regexp"
#line 2254 "seclang-parser.yy"
      {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::ArgsPostNames_DictElementRegexp(yystack_[0].value.as < std::string > ()));
      }
#line 4143 "seclang-parser.cc"
    break;

  case 259: // var: VARIABLE_ARGS_POST_NAMES
#line 2258 "seclang-parser.yy"
      {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::ArgsPostNames_NoDictElement());
      }
#line 4151 "seclang-parser.cc"
    break;

  case 260: // var: VARIABLE_REQUEST_HEADERS_NAMES "Dictionary element"
#line 2263 "seclang-parser.yy"
      {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::RequestHeadersNames_DictElement(yystack_[0].value.as < std::string > ()));
      }
#line 4159 "seclang-parser.cc"
    break;

  case 261: // var: VARIABLE_REQUEST_HEADERS_NAMES "Dictionary element, selected by regexp"
#line 2267 "seclang-parser.yy"
      {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::RequestHeadersNames_DictElementRegexp(yystack_[0].value.as < std::string > ()));
      }
#line 4167 "seclang-parser.cc"
    break;

  case 262: // var: VARIABLE_REQUEST_HEADERS_NAMES
#line 2271 "seclang-parser.yy"
      {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::RequestHeadersNames_NoDictElement());
      }
#line 4175 "seclang-parser.cc"
    break;

  case 263: // var: VARIABLE_RESPONSE_CONTENT_TYPE
#line 2276 "seclang-parser.yy"
      {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::ResponseContentType());
      }
#line 4183 "seclang-parser.cc"
    break;

  case 264: // var: VARIABLE_RESPONSE_HEADERS_NAMES "Dictionary element"
#line 2281 "seclang-parser.yy"
      {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::ResponseHeadersNames_DictElement(yystack_[0].value.as < std::string > ()));
      }
#line 4191 "seclang-parser.cc"
    break;

  case 265: // var: VARIABLE_RESPONSE_HEADERS_NAMES "Dictionary element, selected by regexp"
#line 2285 "seclang-parser.yy"
      {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::ResponseHeadersNames_DictElementRegexp(yystack_[0].value.as < std::string > ()));
      }
#line 4199 "seclang-parser.cc"
    break;

  case 266: // var: VARIABLE_RESPONSE_HEADERS_NAMES
#line 2289 "seclang-parser.yy"
      {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::ResponseHeadersNames_NoDictElement());
      }
#line 4207 "seclang-parser.cc"
    break;

  case 267: // var: VARIABLE_ARGS_COMBINED_SIZE
#line 2293 "seclang-parser.yy"
      {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::ArgsCombinedSize());
      }
#line 4215 "seclang-parser.cc"
    break;

  case 268: // var: "AUTH_TYPE"
#line 2297 "seclang-parser.yy"
      {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::AuthType());
      }
#line 4223 "seclang-parser.cc"
    break;

  case 269: // var: "FILES_COMBINED_SIZE"
#line 2301 "seclang-parser.yy"
      {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::FilesCombinedSize());
      }
#line 4231 "seclang-parser.cc"
    break;

  case 270: // var: "FULL_REQUEST"
#line 2305 "seclang-parser.yy"
      {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::FullRequest());
      }
#line 4239 "seclang-parser.cc"
    break;

  case 271: // var: "FULL_REQUEST_LENGTH"
#line 2309 "seclang-parser.yy"
      {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::FullRequestLength());
      }
#line 4247 "seclang-parser.cc"
    break;

  case 272: // var: "INBOUND_DATA_ERROR"
#line 2313 "seclang-parser.yy"
      {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::InboundDataError());
      }
#line 4255 "seclang-parser.cc"
    break;

  case 273: // var: "MATCHED_VAR"
#line 2317 "seclang-parser.yy"
      {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::MatchedVar());
      }
#line 4263 "seclang-parser.cc"
    break;

  case 274: // var: "MATCHED_VAR_NAME"
#line 2321 "seclang-parser.yy"
      {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::MatchedVarName());
      }
#line 4271 "seclang-parser.cc"
    break;

  case 275: // var: VARIABLE_MULTIPART_BOUNDARY_QUOTED
#line 2325 "seclang-parser.yy"
      {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::MultipartBoundaryQuoted());
      }
#line 4279 "seclang-parser.cc"
    break;

  case 276: // var: VARIABLE_MULTIPART_BOUNDARY_WHITESPACE
#line 2329 "seclang-parser.yy"
      {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::MultipartBoundaryWhiteSpace());
      }
#line 4287 "seclang-parser.cc"
    break;

  case 277: // var: "MULTIPART_CRLF_LF_LINES"
#line 2333 "seclang-parser.yy"
      {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::MultipartCrlfLFLines());
      }
#line 4295 "seclang-parser.cc"
    break;

  case 278: // var: "MULTIPART_DATA_AFTER"
#line 2337 "seclang-parser.yy"
      {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::MultipartDateAfter());
      }
#line 4303 "seclang-parser.cc"
    break;

  case 279: // var: VARIABLE_MULTIPART_DATA_BEFORE
#line 2341 "seclang-parser.yy"
      {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::MultipartDateBefore());
      }
#line 4311 "seclang-parser.cc"
    break;

  case 280: // var: "MULTIPART_FILE_LIMIT_EXCEEDED"
#line 2345 "seclang-parser.yy"
      {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::MultipartFileLimitExceeded());
      }
#line 4319 "seclang-parser.cc"
    break;

  case 281: // var: "MULTIPART_HEADER_FOLDING"
#line 2349 "seclang-parser.yy"
      {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::MultipartHeaderFolding());
      }
#line 4327 "seclang-parser.cc"
    break;

  case 282: // var: "MULTIPART_INVALID_HEADER_FOLDING"
#line 2353 "seclang-parser.yy"
      {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::MultipartInvalidHeaderFolding());
      }
#line 4335 "seclang-parser.cc"
    break;

  case 283: // var: VARIABLE_MULTIPART_INVALID_PART
#line 2357 "seclang-parser.yy"
      {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::MultipartInvalidPart());
      }
#line 4343 "seclang-parser.cc"
    break;

  case 284: // var: "MULTIPART_INVALID_QUOTING"
#line 2361 "seclang-parser.yy"
      {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::MultipartInvalidQuoting());
      }
#line 4351 "seclang-parser.cc"
    break;

  case 285: // var: VARIABLE_MULTIPART_LF_LINE
#line 2365 "seclang-parser.yy"
      {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::MultipartLFLine());
      }
#line 4359 "seclang-parser.cc"
    break;

  case 286: // var: VARIABLE_MULTIPART_MISSING_SEMICOLON
#line 2369 "seclang-parser.yy"
      {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::MultipartMissingSemicolon());
      }
#line 4367 "seclang-parser.cc"
    break;

  case 287: // var: VARIABLE_MULTIPART_SEMICOLON_MISSING
#line 2373 "seclang-parser.yy"
      {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::MultipartMissingSemicolon());
      }
#line 4375 "seclang-parser.cc"
    break;

  case 288: // var: "MULTIPART_STRICT_ERROR"
#line 2377 "seclang-parser.yy"
      {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::MultipartStrictError());
      }
#line 4383 "seclang-parser.cc"
    break;

  case 289: // var: "MULTIPART_UNMATCHED_BOUNDARY"
#line 2381 "seclang-parser.yy"
      {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::MultipartUnmatchedBoundary());
      }
#line 4391 "seclang-parser.cc"
    break;

  case 290: // var: "OUTBOUND_DATA_ERROR"
#line 2385 "seclang-parser.yy"
      {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::OutboundDataError());
      }
#line 4399 "seclang-parser.cc"
    break;

  case 291: // var: "PATH_INFO"
#line 2389 "seclang-parser.yy"
      {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::PathInfo());
      }
#line 4407 "seclang-parser.cc"
    break;

  case 292: // var: "QUERY_STRING"
#line 2393 "seclang-parser.yy"
      {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::QueryString());
      }
#line 4415 "seclang-parser.cc"
    break;

  case 293: // var: "REMOTE_ADDR"
#line 2397 "seclang-parser.yy"
      {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::RemoteAddr());
      }
#line 4423 "seclang-parser.cc"
    break;

  case 294: // var: "REMOTE_HOST"
#line 2401 "seclang-parser.yy"
      {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::RemoteHost());
      }
#line 4431 "seclang-parser.cc"
    break;

  case 295: // var: "REMOTE_PORT"
#line 2405 "seclang-parser.yy"
      {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::RemotePort());
      }
#line 4439 "seclang-parser.cc"
    break;

  case 296: // var: "REQBODY_ERROR"
#line 2409 "seclang-parser.yy"
      {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::ReqbodyError());
      }
#line 4447 "seclang-parser.cc"
    break;

  case 297: // var: "REQBODY_ERROR_MSG"
#line 2413 "seclang-parser.yy"
      {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::ReqbodyErrorMsg());
      }
#line 4455 "seclang-parser.cc"
    break;

  case 298: // var: "REQBODY_PROCESSOR"
#line 2417 "seclang-parser.yy"
      {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::ReqbodyProcessor());
      }
#line 4463 "seclang-parser.cc"
    break;

  case 299: // var: "REQBODY_PROCESSOR_ERROR"
#line 2421 "seclang-parser.yy"
      {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::ReqbodyProcessorError());
      }
#line 4471 "seclang-parser.cc"
    break;

  case 300: // var: "REQBODY_PROCESSOR_ERROR_MSG"
#line 2425 "seclang-parser.yy"
      {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::ReqbodyProcessorErrorMsg());
      }
#line 4479 "seclang-parser.cc"
    break;

  case 301: // var: "REQUEST_BASENAME"
#line 2429 "seclang-parser.yy"
      {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::RequestBasename());
      }
#line 4487 "seclang-parser.cc"
    break;

  case 302: // var: "REQUEST_BODY"
#line 2433 "seclang-parser.yy"
      {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::RequestBody());
      }
#line 4495 "seclang-parser.cc"
    break;

  case 303: // var: "REQUEST_BODY_LENGTH"
#line 2437 "seclang-parser.yy"
      {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::RequestBodyLength());
      }
#line 4503 "seclang-parser.cc"
    break;

  case 304: // var: "REQUEST_FILENAME"
#line 2441 "seclang-parser.yy"
      {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::RequestFilename());
      }
#line 4511 "seclang-parser.cc"
    break;

  case 305: // var: "REQUEST_LINE"
#line 2445 "seclang-parser.yy"
      {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::RequestLine());
      }
#line 4519 "seclang-parser.cc"
    break;

  case 306: // var: "REQUEST_METHOD"
#line 2449 "seclang-parser.yy"
      {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::RequestMethod());
      }
#line 4527 "seclang-parser.cc"
    break;

  case 307: // var: "REQUEST_PROTOCOL"
#line 2453 "seclang-parser.yy"
      {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::RequestProtocol());
      }
#line 4535 "seclang-parser.cc"
    break;

  case 308: // var: "REQUEST_URI"
#line 2457 "seclang-parser.yy"
      {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::RequestURI());
      }
#line 4543 "seclang-parser.cc"
    break;

  case 309: // var: "REQUEST_URI_RAW"
#line 2461 "seclang-parser.yy"
      {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::RequestURIRaw());
      }
#line 4551 "seclang-parser.cc"
    break;

  case 310: // var: "RESPONSE_BODY"
#line 2465 "seclang-parser.yy"
      {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::ResponseBody());
      }
#line 4559 "seclang-parser.cc"
    break;

  case 311: // var: "RESPONSE_CONTENT_LENGTH"
#line 2469 "seclang-parser.yy"
      {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::ResponseContentLength());
      }
#line 4567 "seclang-parser.cc"
    break;

  case 312: // var: "RESPONSE_PROTOCOL"
#line 2473 "seclang-parser.yy"
      {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::ResponseProtocol());
      }
#line 4575 "seclang-parser.cc"
    break;

  case 313: // var: "RESPONSE_STATUS"
#line 2477 "seclang-parser.yy"
      {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::ResponseStatus());
      }
#line 4583 "seclang-parser.cc"
    break;

  case 314: // var: "SERVER_ADDR"
#line 2481 "seclang-parser.yy"
      {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::ServerAddr());
      }
#line 4591 "seclang-parser.cc"
    break;

  case 315: // var: "SERVER_NAME"
#line 2485 "seclang-parser.yy"
      {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::ServerName());
      }
#line 4599 "seclang-parser.cc"
    break;

  case 316: // var: "SERVER_PORT"
#line 2489 "seclang-parser.yy"
      {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::ServerPort());
      }
#line 4607 "seclang-parser.cc"
    break;

  case 317: // var: "SESSIONID"
#line 2493 "seclang-parser.yy"
      {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::SessionID());
      }
#line 4615 "seclang-parser.cc"
    break;

  case 318: // var: "UNIQUE_ID"
#line 2497 "seclang-parser.yy"
      {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::UniqueID());
      }
#line 4623 "seclang-parser.cc"
    break;

  case 319: // var: "URLENCODED_ERROR"
#line 2501 "seclang-parser.yy"
      {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::UrlEncodedError());
      }
#line 4631 "seclang-parser.cc"
    break;

  case 320: // var: "USERID"
#line 2505 "seclang-parser.yy"
      {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::UserID());
      }
#line 4639 "seclang-parser.cc"
    break;

  case 321: // var: "VARIABLE_STATUS"
#line 2509 "seclang-parser.yy"
      {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::Status());
      }
#line 4647 "seclang-parser.cc"
    break;

  case 322: // var: "VARIABLE_STATUS_LINE"
#line 2513 "seclang-parser.yy"
      {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::Status());
      }
#line 4655 "seclang-parser.cc"
    break;

  case 323: // var: "WEBAPPID"
#line 2517 "seclang-parser.yy"
      {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::WebAppId());
      }
#line 4663 "seclang-parser.cc"
    break;

  case 324: // var: "RUN_TIME_VAR_DUR"
#line 2521 "seclang-parser.yy"
      {
        std::string name(yystack_[0].value.as < std::string > ());
        char z = name.at(0);
        std::unique_ptr<Variable> c(new Duration(name));
        yylhs.value.as < std::unique_ptr<Variable> > () = std::move(c);
      }
#line 4674 "seclang-parser.cc"
    break;

  case 325: // var: "RUN_TIME_VAR_BLD"
#line 2529 "seclang-parser.yy"
      {
        std::string name(yystack_[0].value.as < std::string > ());
        char z = name.at(0);
        std::unique_ptr<Variable> c(new ModsecBuild(name));
        yylhs.value.as < std::unique_ptr<Variable> > () = std::move(c);
      }
#line 4685 "seclang-parser.cc"
    break;

  case 326: // var: "RUN_TIME_VAR_HSV"
#line 2536 "seclang-parser.yy"
      {
        std::string name(yystack_[0].value.as < std::string > ());
        char z = name.at(0);
        std::unique_ptr<Variable> c(new HighestSeverity(name));
        yylhs.value.as < std::unique_ptr<Variable> > () = std::move(c);
      }
#line 4696 "seclang-parser.cc"
    break;

  case 327: // var: "RUN_TIME_VAR_REMOTE_USER"
#line 2543 "seclang-parser.yy"
      {
        std::string name(yystack_[0].value.as < std::string > ());
        char z = name.at(0);
        std::unique_ptr<Variable> c(new RemoteUser(name));
        yylhs.value.as < std::unique_ptr<Variable> > () = std::move(c);
      }
#line 4707 "seclang-parser.cc"
    break;

  case 328: // var: "RUN_TIME_VAR_TIME"
#line 2550 "seclang-parser.yy"
      {
        std::string name(yystack_[0].value.as < std::string > ());
        char z = name.at(0);
        std::unique_ptr<Variable> c(new Time(name));
        yylhs.value.as < std::unique_ptr<Variable> > () = std::move(c);
      }
#line 4718 "seclang-parser.cc"
    break;

  case 329: // var: "RUN_TIME_VAR_TIME_DAY"
#line 2557 "seclang-parser.yy"
      {
        std::string name(yystack_[0].value.as < std::string > ());
        char z = name.at(0);
        std::unique_ptr<Variable> c(new TimeDay(name));
        yylhs.value.as < std::unique_ptr<Variable> > () = std::move(c);
      }
#line 4729 "seclang-parser.cc"
    break;

  case 330: // var: "RUN_TIME_VAR_TIME_EPOCH"
#line 2564 "seclang-parser.yy"
      {
        std::string name(yystack_[0].value.as < std::string > ());
        char z = name.at(0);
        std::unique_ptr<Variable> c(new TimeEpoch(name));
        yylhs.value.as < std::unique_ptr<Variable> > () = std::move(c);
      }
#line 4740 "seclang-parser.cc"
    break;

  case 331: // var: "RUN_TIME_VAR_TIME_HOUR"
#line 2571 "seclang-parser.yy"
      {
        std::string name(yystack_[0].value.as < std::string > ());
        char z = name.at(0);
        std::unique_ptr<Variable> c(new TimeHour(name));
        yylhs.value.as < std::unique_ptr<Variable> > () = std::move(c);
      }
#line 4751 "seclang-parser.cc"
    break;

  case 332: // var: "RUN_TIME_VAR_TIME_MIN"
#line 2578 "seclang-parser.yy"
      {
        std::string name(yystack_[0].value.as < std::string > ());
        char z = name.at(0);
        std::unique_ptr<Variable> c(new TimeMin(name));
        yylhs.value.as < std::unique_ptr<Variable> > () = std::move(c);
      }
#line 4762 "seclang-parser.cc"
    break;

  case 333: // var: "RUN_TIME_VAR_TIME_MON"
#line 2585 "seclang-parser.yy"
      {
        std::string name(yystack_[0].value.as < std::string > ());
        char z = name.at(0);
        std::unique_ptr<Variable> c(new TimeMon(name));
        yylhs.value.as < std::unique_ptr<Variable> > () = std::move(c);
      }
#line 4773 "seclang-parser.cc"
    break;

  case 334: // var: "RUN_TIME_VAR_TIME_SEC"
#line 2592 "seclang-parser.yy"
      {
        std::string name(yystack_[0].value.as < std::string > ());
        char z = name.at(0);
            std::unique_ptr<Variable> c(new TimeSec(name));
            yylhs.value.as < std::unique_ptr<Variable> > () = std::move(c);
      }
#line 4784 "seclang-parser.cc"
    break;

  case 335: // var: "RUN_TIME_VAR_TIME_WDAY"
#line 2599 "seclang-parser.yy"
      {
        std::string name(yystack_[0].value.as < std::string > ());
        char z = name.at(0);
        std::unique_ptr<Variable> c(new TimeWDay(name));
        yylhs.value.as < std::unique_ptr<Variable> > () = std::move(c);
      }
#line 4795 "seclang-parser.cc"
    break;

  case 336: // var: "RUN_TIME_VAR_TIME_YEAR"
#line 2606 "seclang-parser.yy"
      {
        std::string name(yystack_[0].value.as < std::string > ());
        char z = name.at(0);
        std::unique_ptr<Variable> c(new TimeYear(name));
        yylhs.value.as < std::unique_ptr<Variable> > () = std::move(c);
      }
#line 4806 "seclang-parser.cc"
    break;

  case 337: // act: "Accuracy"
#line 2616 "seclang-parser.yy"
      {
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::Accuracy(yystack_[0].value.as < std::string > ()));
      }
#line 4814 "seclang-parser.cc"
    break;

  case 338: // act: "Allow"
#line 2620 "seclang-parser.yy"
      {
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::disruptive::Allow(yystack_[0].value.as < std::string > ()));
      }
#line 4822 "seclang-parser.cc"
    break;

  case 339: // act: "Append"
#line 2624 "seclang-parser.yy"
      {
        ACTION_NOT_SUPPORTED("Append", yystack_[1].location);
      }
#line 4830 "seclang-parser.cc"
    break;

  case 340: // act: "AuditLog"
#line 2628 "seclang-parser.yy"
      {
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::AuditLog(yystack_[0].value.as < std::string > ()));
      }
#line 4838 "seclang-parser.cc"
    break;

  case 341: // act: "Block"
#line 2632 "seclang-parser.yy"
      {
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::Block(yystack_[0].value.as < std::string > ()));
      }
#line 4846 "seclang-parser.cc"
    break;

  case 342: // act: "Capture"
#line 2636 "seclang-parser.yy"
      {
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::Capture(yystack_[0].value.as < std::string > ()));
      }
#line 4854 "seclang-parser.cc"
    break;

  case 343: // act: "Chain"
#line 2640 "seclang-parser.yy"
      {
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::Chain(yystack_[0].value.as < std::string > ()));
      }
#line 4862 "seclang-parser.cc"
    break;

  case 344: // act: "ACTION_CTL_AUDIT_ENGINE" "CONFIG_VALUE_ON"
#line 2644 "seclang-parser.yy"
      {
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::ctl::AuditEngine("ctl:auditengine=on"));
        driver.m_auditLog->setCtlAuditEngineActive();
      }
#line 4871 "seclang-parser.cc"
    break;

  case 345: // act: "ACTION_CTL_AUDIT_ENGINE" "CONFIG_VALUE_OFF"
#line 2649 "seclang-parser.yy"
      {
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::ctl::AuditEngine("ctl:auditengine=off"));
      }
#line 4879 "seclang-parser.cc"
    break;

  case 346: // act: "ACTION_CTL_AUDIT_ENGINE" "CONFIG_VALUE_RELEVANT_ONLY"
#line 2653 "seclang-parser.yy"
      {
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::ctl::AuditEngine("ctl:auditengine=relevantonly"));
        driver.m_auditLog->setCtlAuditEngineActive();
      }
#line 4888 "seclang-parser.cc"
    break;

  case 347: // act: "ACTION_CTL_AUDIT_LOG_PARTS"
#line 2658 "seclang-parser.yy"
      {
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::ctl::AuditLogParts(yystack_[0].value.as < std::string > ()));
      }
#line 4896 "seclang-parser.cc"
    break;

  case 348: // act: "ACTION_CTL_BDY_JSON"
#line 2662 "seclang-parser.yy"
      {
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::ctl::RequestBodyProcessorJSON(yystack_[0].value.as < std::string > ()));
      }
#line 4904 "seclang-parser.cc"
    break;

  case 349: // act: "ACTION_CTL_BDY_XML"
#line 2666 "seclang-parser.yy"
      {
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::ctl::RequestBodyProcessorXML(yystack_[0].value.as < std::string > ()));
      }
#line 4912 "seclang-parser.cc"
    break;

  case 350: // act: "ACTION_CTL_BDY_URLENCODED"
#line 2670 "seclang-parser.yy"
      {
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::ctl::RequestBodyProcessorURLENCODED(yystack_[0].value.as < std::string > ()));
      }
#line 4920 "seclang-parser.cc"
    break;

  case 351: // act: "ACTION_CTL_FORCE_REQ_BODY_VAR" "CONFIG_VALUE_ON"
#line 2674 "seclang-parser.yy"
      {
        //ACTION_NOT_SUPPORTED("CtlForceReequestBody", @0);
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::Action(yystack_[1].value.as < std::string > ()));
      }
#line 4929 "seclang-parser.cc"
    break;

  case 352: // act: "ACTION_CTL_FORCE_REQ_BODY_VAR" "CONFIG_VALUE_OFF"
#line 2679 "seclang-parser.yy"
      {
        //ACTION_NOT_SUPPORTED("CtlForceReequestBody", @0);
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::Action(yystack_[1].value.as < std::string > ()));
      }
#line 4938 "seclang-parser.cc"
    break;

  case 353: // act: "ACTION_CTL_REQUEST_BODY_ACCESS" "CONFIG_VALUE_ON"
#line 2684 "seclang-parser.yy"
      {
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::ctl::RequestBodyAccess(yystack_[1].value.as < std::string > () + "true"));
      }
#line 4946 "seclang-parser.cc"
    break;

  case 354: // act: "ACTION_CTL_REQUEST_BODY_ACCESS" "CONFIG_VALUE_OFF"
#line 2688 "seclang-parser.yy"
      {
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::ctl::RequestBodyAccess(yystack_[1].value.as < std::string > () + "false"));
      }
#line 4954 "seclang-parser.cc"
    break;

  case 355: // act: "ACTION_CTL_RULE_ENGINE" "CONFIG_VALUE_ON"
#line 2692 "seclang-parser.yy"
      {
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::ctl::RuleEngine("ctl:RuleEngine=on"));
      }
#line 4962 "seclang-parser.cc"
    break;

  case 356: // act: "ACTION_CTL_RULE_ENGINE" "CONFIG_VALUE_OFF"
#line 2696 "seclang-parser.yy"
      {
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::ctl::RuleEngine("ctl:RuleEngine=off"));
      }
#line 4970 "seclang-parser.cc"
    break;

  case 357: // act: "ACTION_CTL_RULE_ENGINE" "CONFIG_VALUE_DETC"
#line 2700 "seclang-parser.yy"
      {
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::ctl::RuleEngine("ctl:RuleEngine=detectiononly"));
      }
#line 4978 "seclang-parser.cc"
    break;

  case 358: // act: "ACTION_CTL_RULE_REMOVE_BY_ID"
#line 2704 "seclang-parser.yy"
      {
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::ctl::RuleRemoveById(yystack_[0].value.as < std::string > ()));
      }
#line 4986 "seclang-parser.cc"
    break;

  case 359: // act: "ACTION_CTL_RULE_REMOVE_BY_TAG"
#line 2708 "seclang-parser.yy"
      {
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::ctl::RuleRemoveByTag(yystack_[0].value.as < std::string > ()));
      }
#line 4994 "seclang-parser.cc"
    break;

  case 360: // act: "ACTION_CTL_RULE_REMOVE_TARGET_BY_ID"
#line 2712 "seclang-parser.yy"
      {
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::ctl::RuleRemoveTargetById(yystack_[0].value.as < std::string > ()));
      }
#line 5002 "seclang-parser.cc"
    break;

  case 361: // act: "ACTION_CTL_RULE_REMOVE_TARGET_BY_TAG"
#line 2716 "seclang-parser.yy"
      {
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::ctl::RuleRemoveTargetByTag(yystack_[0].value.as < std::string > ()));
      }
#line 5010 "seclang-parser.cc"
    break;

  case 362: // act: "Deny"
#line 2720 "seclang-parser.yy"
      {
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::disruptive::Deny(yystack_[0].value.as < std::string > ()));
      }
#line 5018 "seclang-parser.cc"
    break;

  case 363: // act: "DeprecateVar"
#line 2724 "seclang-parser.yy"
      {
        ACTION_NOT_SUPPORTED("DeprecateVar", yystack_[1].location);
      }
#line 5026 "seclang-parser.cc"
    break;

  case 364: // act: "Drop"
#line 2728 "seclang-parser.yy"
      {
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::disruptive::Drop(yystack_[0].value.as < std::string > ()));
      }
#line 5034 "seclang-parser.cc"
    break;

  case 365: // act: "Exec"
#line 2732 "seclang-parser.yy"
      {
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::Exec(yystack_[0].value.as < std::string > ()));
      }
#line 5042 "seclang-parser.cc"
    break;

  case 366: // act: "ExpireVar"
#line 2736 "seclang-parser.yy"
      {
        //ACTION_NOT_SUPPORTED("ExpireVar", @0);
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::Action(yystack_[0].value.as < std::string > ()));
      }
#line 5051 "seclang-parser.cc"
    break;

  case 367: // act: "Id"
#line 2741 "seclang-parser.yy"
      {
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::RuleId(yystack_[0].value.as < std::string > ()));
      }
#line 5059 "seclang-parser.cc"
    break;

  case 368: // act: "InitCol" run_time_string
#line 2745 "seclang-parser.yy"
      {
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::InitCol(yystack_[1].value.as < std::string > (), std::move(yystack_[0].value.as < std::unique_ptr<RunTimeString> > ())));
      }
#line 5067 "seclang-parser.cc"
    break;

  case 369: // act: "LogData" run_time_string
#line 2749 "seclang-parser.yy"
      {
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::LogData(std::move(yystack_[0].value.as < std::unique_ptr<RunTimeString> > ())));
      }
#line 5075 "seclang-parser.cc"
    break;

  case 370: // act: "Log"
#line 2753 "seclang-parser.yy"
      {
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::Log(yystack_[0].value.as < std::string > ()));
      }
#line 5083 "seclang-parser.cc"
    break;

  case 371: // act: "Maturity"
#line 2757 "seclang-parser.yy"
      {
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::Maturity(yystack_[0].value.as < std::string > ()));
      }
#line 5091 "seclang-parser.cc"
    break;

  case 372: // act: "Msg" run_time_string
#line 2761 "seclang-parser.yy"
      {
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::Msg(std::move(yystack_[0].value.as < std::unique_ptr<RunTimeString> > ())));
      }
#line 5099 "seclang-parser.cc"
    break;

  case 373: // act: "MultiMatch"
#line 2765 "seclang-parser.yy"
      {
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::MultiMatch(yystack_[0].value.as < std::string > ()));
      }
#line 5107 "seclang-parser.cc"
    break;

  case 374: // act: "NoAuditLog"
#line 2769 "seclang-parser.yy"
      {
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::NoAuditLog(yystack_[0].value.as < std::string > ()));
      }
#line 5115 "seclang-parser.cc"
    break;

  case 375: // act: "NoLog"
#line 2773 "seclang-parser.yy"
      {
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::NoLog(yystack_[0].value.as < std::string > ()));
      }
#line 5123 "seclang-parser.cc"
    break;

  case 376: // act: "Pass"
#line 2777 "seclang-parser.yy"
      {
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::disruptive::Pass(yystack_[0].value.as < std::string > ()));
      }
#line 5131 "seclang-parser.cc"
    break;

  case 377: // act: "Pause"
#line 2781 "seclang-parser.yy"
      {
        ACTION_NOT_SUPPORTED("Pause", yystack_[1].location);
      }
#line 5139 "seclang-parser.cc"
    break;

  case 378: // act: "Phase"
#line 2785 "seclang-parser.yy"
      {
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::Phase(yystack_[0].value.as < std::string > ()));
      }
#line 5147 "seclang-parser.cc"
    break;

  case 379: // act: "Prepend"
#line 2789 "seclang-parser.yy"
      {
        ACTION_NOT_SUPPORTED("Prepend", yystack_[1].location);
      }
#line 5155 "seclang-parser.cc"
    break;

  case 380: // act: "Proxy"
#line 2793 "seclang-parser.yy"
      {
        ACTION_NOT_SUPPORTED("Proxy", yystack_[1].location);
      }
#line 5163 "seclang-parser.cc"
    break;

  case 381: // act: "Redirect" run_time_string
#line 2797 "seclang-parser.yy"
      {
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::disruptive::Redirect(std::move(yystack_[0].value.as < std::unique_ptr<RunTimeString> > ())));
      }
#line 5171 "seclang-parser.cc"
    break;

  case 382: // act: "Rev"
#line 2801 "seclang-parser.yy"
      {
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::Rev(yystack_[0].value.as < std::string > ()));
      }
#line 5179 "seclang-parser.cc"
    break;

  case 383: // act: "SanitiseArg"
#line 2805 "seclang-parser.yy"
      {
        ACTION_NOT_SUPPORTED("SanitiseArg", yystack_[1].location);
      }
#line 5187 "seclang-parser.cc"
    break;

  case 384: // act: "SanitiseMatched"
#line 2809 "seclang-parser.yy"
      {
        ACTION_NOT_SUPPORTED("SanitiseMatched", yystack_[1].location);
      }
#line 5195 "seclang-parser.cc"
    break;

  case 385: // act: "SanitiseMatchedBytes"
#line 2813 "seclang-parser.yy"
      {
        ACTION_NOT_SUPPORTED("SanitiseMatchedBytes", yystack_[1].location);
      }
#line 5203 "seclang-parser.cc"
    break;

  case 386: // act: "SanitiseRequestHeader"
#line 2817 "seclang-parser.yy"
      {
        ACTION_NOT_SUPPORTED("SanitiseRequestHeader", yystack_[1].location);
      }
#line 5211 "seclang-parser.cc"
    break;

  case 387: // act: "SanitiseResponseHeader"
#line 2821 "seclang-parser.yy"
      {
        ACTION_NOT_SUPPORTED("SanitiseResponseHeader", yystack_[1].location);
      }
#line 5219 "seclang-parser.cc"
    break;

  case 388: // act: "SetEnv" run_time_string
#line 2825 "seclang-parser.yy"
      {
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::SetENV(std::move(yystack_[0].value.as < std::unique_ptr<RunTimeString> > ())));
      }
#line 5227 "seclang-parser.cc"
    break;

  case 389: // act: "SetRsc" run_time_string
#line 2829 "seclang-parser.yy"
      {
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::SetRSC(std::move(yystack_[0].value.as < std::unique_ptr<RunTimeString> > ())));
      }
#line 5235 "seclang-parser.cc"
    break;

  case 390: // act: "SetSid" run_time_string
#line 2833 "seclang-parser.yy"
      {
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::SetSID(std::move(yystack_[0].value.as < std::unique_ptr<RunTimeString> > ())));
      }
#line 5243 "seclang-parser.cc"
    break;

  case 391: // act: "SetUID" run_time_string
#line 2837 "seclang-parser.yy"
      {
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::SetUID(std::move(yystack_[0].value.as < std::unique_ptr<RunTimeString> > ())));
      }
#line 5251 "seclang-parser.cc"
    break;

  case 392: // act: "SetVar" setvar_action
#line 2841 "seclang-parser.yy"
      {
        yylhs.value.as < std::unique_ptr<actions::Action> > () = std::move(yystack_[0].value.as < std::unique_ptr<actions::Action> > ());
      }
#line 5259 "seclang-parser.cc"
    break;

  case 393: // act: "Severity"
#line 2845 "seclang-parser.yy"
      {
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::Severity(yystack_[0].value.as < std::string > ()));
      }
#line 5267 "seclang-parser.cc"
    break;

  case 394: // act: "Skip"
#line 2849 "seclang-parser.yy"
      {
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::Skip(yystack_[0].value.as < std::string > ()));
      }
#line 5275 "seclang-parser.cc"
    break;

  case 395: // act: "SkipAfter"
#line 2853 "seclang-parser.yy"
      {
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::SkipAfter(yystack_[0].value.as < std::string > ()));
      }
#line 5283 "seclang-parser.cc"
    break;

  case 396: // act: "Status"
#line 2857 "seclang-parser.yy"
      {
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::data::Status(yystack_[0].value.as < std::string > ()));
      }
#line 5291 "seclang-parser.cc"
    break;

  case 397: // act: "Tag" run_time_string
#line 2861 "seclang-parser.yy"
      {
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::Tag(std::move(yystack_[0].value.as < std::unique_ptr<RunTimeString> > ())));
      }
#line 5299 "seclang-parser.cc"
    break;

  case 398: // act: "Ver"
#line 2865 "seclang-parser.yy"
      {
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::Ver(yystack_[0].value.as < std::string > ()));
      }
#line 5307 "seclang-parser.cc"
    break;

  case 399: // act: "xmlns"
#line 2869 "seclang-parser.yy"
      {
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::XmlNS(yystack_[0].value.as < std::string > ()));
      }
#line 5315 "seclang-parser.cc"
    break;

  case 400: // act: "ACTION_TRANSFORMATION_PARITY_ZERO_7_BIT"
#line 2873 "seclang-parser.yy"
      {
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::transformations::ParityZero7bit(yystack_[0].value.as < std::string > ()));
      }
#line 5323 "seclang-parser.cc"
    break;

  case 401: // act: "ACTION_TRANSFORMATION_PARITY_ODD_7_BIT"
#line 2877 "seclang-parser.yy"
      {
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::transformations::ParityOdd7bit(yystack_[0].value.as < std::string > ()));
      }
#line 5331 "seclang-parser.cc"
    break;

  case 402: // act: "ACTION_TRANSFORMATION_PARITY_EVEN_7_BIT"
#line 2881 "seclang-parser.yy"
      {
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::transformations::ParityEven7bit(yystack_[0].value.as < std::string > ()));
      }
#line 5339 "seclang-parser.cc"
    break;

  case 403: // act: "ACTION_TRANSFORMATION_SQL_HEX_DECODE"
#line 2885 "seclang-parser.yy"
      {
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::transformations::SqlHexDecode(yystack_[0].value.as < std::string > ()));
      }
#line 5347 "seclang-parser.cc"
    break;

  case 404: // act: "ACTION_TRANSFORMATION_BASE_64_ENCODE"
#line 2889 "seclang-parser.yy"
      {
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::transformations::Base64Encode(yystack_[0].value.as < std::string > ()));
      }
#line 5355 "seclang-parser.cc"
    break;

  case 405: // act: "ACTION_TRANSFORMATION_BASE_64_DECODE"
#line 2893 "seclang-parser.yy"
      {
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::transformations::Base64Decode(yystack_[0].value.as < std::string > ()));
      }
#line 5363 "seclang-parser.cc"
    break;

  case 406: // act: "ACTION_TRANSFORMATION_BASE_64_DECODE_EXT"
#line 2897 "seclang-parser.yy"
      {
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::transformations::Base64DecodeExt(yystack_[0].value.as < std::string > ()));
      }
#line 5371 "seclang-parser.cc"
    break;

  case 407: // act: "ACTION_TRANSFORMATION_CMD_LINE"
#line 2901 "seclang-parser.yy"
      {
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::transformations::CmdLine(yystack_[0].value.as < std::string > ()));
      }
#line 5379 "seclang-parser.cc"
    break;

  case 408: // act: "ACTION_TRANSFORMATION_SHA1"
#line 2905 "seclang-parser.yy"
      {
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::transformations::Sha1(yystack_[0].value.as < std::string > ()));
      }
#line 5387 "seclang-parser.cc"
    break;

  case 409: // act: "ACTION_TRANSFORMATION_MD5"
#line 2909 "seclang-parser.yy"
      {
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::transformations::Md5(yystack_[0].value.as < std::string > ()));
      }
#line 5395 "seclang-parser.cc"
    break;

  case 410: // act: "ACTION_TRANSFORMATION_ESCAPE_SEQ_DECODE"
#line 2913 "seclang-parser.yy"
      {
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::transformations::EscapeSeqDecode(yystack_[0].value.as < std::string > ()));
      }
#line 5403 "seclang-parser.cc"
    break;

  case 411: // act: "ACTION_TRANSFORMATION_HEX_ENCODE"
#line 2917 "seclang-parser.yy"
      {
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::transformations::HexEncode(yystack_[0].value.as < std::string > ()));
      }
#line 5411 "seclang-parser.cc"
    break;

  case 412: // act: "ACTION_TRANSFORMATION_HEX_DECODE"
#line 2921 "seclang-parser.yy"
      {
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::transformations::HexDecode(yystack_[0].value.as < std::string > ()));
      }
#line 5419 "seclang-parser.cc"
    break;

  case 413: // act: "ACTION_TRANSFORMATION_LOWERCASE"
#line 2925 "seclang-parser.yy"
      {
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::transformations::LowerCase(yystack_[0].value.as < std::string > ()));
      }
#line 5427 "seclang-parser.cc"
    break;

  case 414: // act: "ACTION_TRANSFORMATION_UPPERCASE"
#line 2929 "seclang-parser.yy"
      {
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::transformations::UpperCase(yystack_[0].value.as < std::string > ()));
      }
#line 5435 "seclang-parser.cc"
    break;

  case 415: // act: "ACTION_TRANSFORMATION_URL_DECODE_UNI"
#line 2933 "seclang-parser.yy"
      {
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::transformations::UrlDecodeUni(yystack_[0].value.as < std::string > ()));
      }
#line 5443 "seclang-parser.cc"
    break;

  case 416: // act: "ACTION_TRANSFORMATION_URL_DECODE"
#line 2937 "seclang-parser.yy"
      {
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::transformations::UrlDecode(yystack_[0].value.as < std::string > ()));
      }
#line 5451 "seclang-parser.cc"
    break;

  case 417: // act: "ACTION_TRANSFORMATION_URL_ENCODE"
#line 2941 "seclang-parser.yy"
      {
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::transformations::UrlEncode(yystack_[0].value.as < std::string > ()));
      }
#line 5459 "seclang-parser.cc"
    break;

  case 418: // act: "ACTION_TRANSFORMATION_NONE"
#line 2945 "seclang-parser.yy"
      {
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::transformations::None(yystack_[0].value.as < std::string > ()));
      }
#line 5467 "seclang-parser.cc"
    break;

  case 419: // act: "ACTION_TRANSFORMATION_COMPRESS_WHITESPACE"
#line 2949 "seclang-parser.yy"
      {
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::transformations::CompressWhitespace(yystack_[0].value.as < std::string > ()));
      }
#line 5475 "seclang-parser.cc"
    break;

  case 420: // act: "ACTION_TRANSFORMATION_REMOVE_WHITESPACE"
#line 2953 "seclang-parser.yy"
      {
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::transformations::RemoveWhitespace(yystack_[0].value.as < std::string > ()));
      }
#line 5483 "seclang-parser.cc"
    break;

  case 421: // act: "ACTION_TRANSFORMATION_REPLACE_NULLS"
#line 2957 "seclang-parser.yy"
      {
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::transformations::ReplaceNulls(yystack_[0].value.as < std::string > ()));
      }
#line 5491 "seclang-parser.cc"
    break;

  case 422: // act: "ACTION_TRANSFORMATION_REMOVE_NULLS"
#line 2961 "seclang-parser.yy"
      {
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::transformations::RemoveNulls(yystack_[0].value.as < std::string > ()));
      }
#line 5499 "seclang-parser.cc"
    break;

  case 423: // act: "ACTION_TRANSFORMATION_HTML_ENTITY_DECODE"
#line 2965 "seclang-parser.yy"
      {
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::transformations::HtmlEntityDecode(yystack_[0].value.as < std::string > ()));
      }
#line 5507 "seclang-parser.cc"
    break;

  case 424: // act: "ACTION_TRANSFORMATION_JS_DECODE"
#line 2969 "seclang-parser.yy"
      {
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::transformations::JsDecode(yystack_[0].value.as < std::string > ()));
      }
#line 5515 "seclang-parser.cc"
    break;

  case 425: // act: "ACTION_TRANSFORMATION_CSS_DECODE"
#line 2973 "seclang-parser.yy"
      {
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::transformations::CssDecode(yystack_[0].value.as < std::string > ()));
      }
#line 5523 "seclang-parser.cc"
    break;

  case 426: // act: "ACTION_TRANSFORMATION_TRIM"
#line 2977 "seclang-parser.yy"
      {
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::transformations::Trim(yystack_[0].value.as < std::string > ()));
      }
#line 5531 "seclang-parser.cc"
    break;

  case 427: // act: "ACTION_TRANSFORMATION_TRIM_LEFT"
#line 2981 "seclang-parser.yy"
      {
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::transformations::TrimLeft(yystack_[0].value.as < std::string > ()));
      }
#line 5539 "seclang-parser.cc"
    break;

  case 428: // act: "ACTION_TRANSFORMATION_TRIM_RIGHT"
#line 2985 "seclang-parser.yy"
      {
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::transformations::TrimRight(yystack_[0].value.as < std::string > ()));
      }
#line 5547 "seclang-parser.cc"
    break;

  case 429: // act: "ACTION_TRANSFORMATION_NORMALISE_PATH_WIN"
#line 2989 "seclang-parser.yy"
      {
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::transformations::NormalisePathWin(yystack_[0].value.as < std::string > ()));
      }
#line 5555 "seclang-parser.cc"
    break;

  case 430: // act: "ACTION_TRANSFORMATION_NORMALISE_PATH"
#line 2993 "seclang-parser.yy"
      {
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::transformations::NormalisePath(yystack_[0].value.as < std::string > ()));
      }
#line 5563 "seclang-parser.cc"
    break;

  case 431: // act: "ACTION_TRANSFORMATION_LENGTH"
#line 2997 "seclang-parser.yy"
      {
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::transformations::Length(yystack_[0].value.as < std::string > ()));
      }
#line 5571 "seclang-parser.cc"
    break;

  case 432: // act: "ACTION_TRANSFORMATION_UTF8_TO_UNICODE"
#line 3001 "seclang-parser.yy"
      {
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::transformations::Utf8ToUnicode(yystack_[0].value.as < std::string > ()));
      }
#line 5579 "seclang-parser.cc"
    break;

  case 433: // act: "ACTION_TRANSFORMATION_REMOVE_COMMENTS_CHAR"
#line 3005 "seclang-parser.yy"
      {
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::transformations::RemoveCommentsChar(yystack_[0].value.as < std::string > ()));
      }
#line 5587 "seclang-parser.cc"
    break;

  case 434: // act: "ACTION_TRANSFORMATION_REMOVE_COMMENTS"
#line 3009 "seclang-parser.yy"
      {
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::transformations::RemoveComments(yystack_[0].value.as < std::string > ()));
      }
#line 5595 "seclang-parser.cc"
    break;

  case 435: // act: "ACTION_TRANSFORMATION_REPLACE_COMMENTS"
#line 3013 "seclang-parser.yy"
      {
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::transformations::ReplaceComments(yystack_[0].value.as < std::string > ()));
      }
#line 5603 "seclang-parser.cc"
    break;

  case 436: // setvar_action: "NOT" var
#line 3020 "seclang-parser.yy"
      {
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::SetVar(actions::SetVarOperation::unsetOperation, std::move(yystack_[0].value.as < std::unique_ptr<Variable> > ())));
      }
#line 5611 "seclang-parser.cc"
    break;

  case 437: // setvar_action: var
#line 3024 "seclang-parser.yy"
      {
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::SetVar(actions::SetVarOperation::setToOneOperation, std::move(yystack_[0].value.as < std::unique_ptr<Variable> > ())));
      }
#line 5619 "seclang-parser.cc"
    break;

  case 438: // setvar_action: var SETVAR_OPERATION_EQUALS run_time_string
#line 3028 "seclang-parser.yy"
      {
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::SetVar(actions::SetVarOperation::setOperation, std::move(yystack_[2].value.as < std::unique_ptr<Variable> > ()), std::move(yystack_[0].value.as < std::unique_ptr<RunTimeString> > ())));
      }
#line 5627 "seclang-parser.cc"
    break;

  case 439: // setvar_action: var SETVAR_OPERATION_EQUALS_PLUS run_time_string
#line 3032 "seclang-parser.yy"
      {
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::SetVar(actions::SetVarOperation::sumAndSetOperation, std::move(yystack_[2].value.as < std::unique_ptr<Variable> > ()), std::move(yystack_[0].value.as < std::unique_ptr<RunTimeString> > ())));
      }
#line 5635 "seclang-parser.cc"
    break;

  case 440: // setvar_action: var SETVAR_OPERATION_EQUALS_MINUS run_time_string
#line 3036 "seclang-parser.yy"
      {
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::SetVar(actions::SetVarOperation::substractAndSetOperation, std::move(yystack_[2].value.as < std::unique_ptr<Variable> > ()), std::move(yystack_[0].value.as < std::unique_ptr<RunTimeString> > ())));
      }
#line 5643 "seclang-parser.cc"
    break;

  case 441: // run_time_string: run_time_string "FREE_TEXT_QUOTE_MACRO_EXPANSION"
#line 3043 "seclang-parser.yy"
      {
        yystack_[1].value.as < std::unique_ptr<RunTimeString> > ()->appendText(yystack_[0].value.as < std::string > ());
        yylhs.value.as < std::unique_ptr<RunTimeString> > () = std::move(yystack_[1].value.as < std::unique_ptr<RunTimeString> > ());
      }
#line 5652 "seclang-parser.cc"
    break;

  case 442: // run_time_string: run_time_string var
#line 3048 "seclang-parser.yy"
      {
        yystack_[1].value.as < std::unique_ptr<RunTimeString> > ()->appendVar(std::move(yystack_[0].value.as < std::unique_ptr<Variable> > ()));
        yylhs.value.as < std::unique_ptr<RunTimeString> > () = std::move(yystack_[1].value.as < std::unique_ptr<RunTimeString> > ());
      }
#line 5661 "seclang-parser.cc"
    break;

  case 443: // run_time_string: "FREE_TEXT_QUOTE_MACRO_EXPANSION"
#line 3053 "seclang-parser.yy"
      {
        std::unique_ptr<RunTimeString> r(new RunTimeString());
        r->appendText(yystack_[0].value.as < std::string > ());
        yylhs.value.as < std::unique_ptr<RunTimeString> > () = std::move(r);
      }
#line 5671 "seclang-parser.cc"
    break;

  case 444: // run_time_string: var
#line 3059 "seclang-parser.yy"
      {
        std::unique_ptr<RunTimeString> r(new RunTimeString());
        r->appendVar(std::move(yystack_[0].value.as < std::unique_ptr<Variable> > ()));
        yylhs.value.as < std::unique_ptr<RunTimeString> > () = std::move(r);
      }
#line 5681 "seclang-parser.cc"
    break;


#line 5685 "seclang-parser.cc"

            default:
              break;
            }
        }
#if YY_EXCEPTIONS
      catch (const syntax_error& yyexc)
        {
          YYCDEBUG << "Caught exception: " << yyexc.what() << '\n';
          error (yyexc);
          YYERROR;
        }
#endif // YY_EXCEPTIONS
      YY_SYMBOL_PRINT ("-> $$ =", yylhs);
      yypop_ (yylen);
      yylen = 0;

      // Shift the result of the reduction.
      yypush_ (YY_NULLPTR, YY_MOVE (yylhs));
    }
    goto yynewstate;


  /*--------------------------------------.
  | yyerrlab -- here on detecting error.  |
  `--------------------------------------*/
  yyerrlab:
    // If not already recovering from an error, report this error.
    if (!yyerrstatus_)
      {
        ++yynerrs_;
        context yyctx (*this, yyla);
        std::string msg = yysyntax_error_ (yyctx);
        error (yyla.location, YY_MOVE (msg));
      }


    yyerror_range[1].location = yyla.location;
    if (yyerrstatus_ == 3)
      {
        /* If just tried and failed to reuse lookahead token after an
           error, discard it.  */

        // Return failure if at end of input.
        if (yyla.kind () == symbol_kind::S_YYEOF)
          YYABORT;
        else if (!yyla.empty ())
          {
            yy_destroy_ ("Error: discarding", yyla);
            yyla.clear ();
          }
      }

    // Else will try to reuse lookahead token after shifting the error token.
    goto yyerrlab1;


  /*---------------------------------------------------.
  | yyerrorlab -- error raised explicitly by YYERROR.  |
  `---------------------------------------------------*/
  yyerrorlab:
    /* Pacify compilers when the user code never invokes YYERROR and
       the label yyerrorlab therefore never appears in user code.  */
    if (false)
      YYERROR;

    /* Do not reclaim the symbols of the rule whose action triggered
       this YYERROR.  */
    yypop_ (yylen);
    yylen = 0;
    YY_STACK_PRINT ();
    goto yyerrlab1;


  /*-------------------------------------------------------------.
  | yyerrlab1 -- common code for both syntax error and YYERROR.  |
  `-------------------------------------------------------------*/
  yyerrlab1:
    yyerrstatus_ = 3;   // Each real token shifted decrements this.
    // Pop stack until we find a state that shifts the error token.
    for (;;)
      {
        yyn = yypact_[+yystack_[0].state];
        if (!yy_pact_value_is_default_ (yyn))
          {
            yyn += symbol_kind::S_YYerror;
            if (0 <= yyn && yyn <= yylast_
                && yycheck_[yyn] == symbol_kind::S_YYerror)
              {
                yyn = yytable_[yyn];
                if (0 < yyn)
                  break;
              }
          }

        // Pop the current state because it cannot handle the error token.
        if (yystack_.size () == 1)
          YYABORT;

        yyerror_range[1].location = yystack_[0].location;
        yy_destroy_ ("Error: popping", yystack_[0]);
        yypop_ ();
        YY_STACK_PRINT ();
      }
    {
      stack_symbol_type error_token;

      yyerror_range[2].location = yyla.location;
      YYLLOC_DEFAULT (error_token.location, yyerror_range, 2);

      // Shift the error token.
      error_token.state = state_type (yyn);
      yypush_ ("Shifting", YY_MOVE (error_token));
    }
    goto yynewstate;


  /*-------------------------------------.
  | yyacceptlab -- YYACCEPT comes here.  |
  `-------------------------------------*/
  yyacceptlab:
    yyresult = 0;
    goto yyreturn;


  /*-----------------------------------.
  | yyabortlab -- YYABORT comes here.  |
  `-----------------------------------*/
  yyabortlab:
    yyresult = 1;
    goto yyreturn;


  /*-----------------------------------------------------.
  | yyreturn -- parsing is finished, return the result.  |
  `-----------------------------------------------------*/
  yyreturn:
    if (!yyla.empty ())
      yy_destroy_ ("Cleanup: discarding lookahead", yyla);

    /* Do not reclaim the symbols of the rule whose action triggered
       this YYABORT or YYACCEPT.  */
    yypop_ (yylen);
    YY_STACK_PRINT ();
    while (1 < yystack_.size ())
      {
        yy_destroy_ ("Cleanup: popping", yystack_[0]);
        yypop_ ();
      }

    return yyresult;
  }
#if YY_EXCEPTIONS
    catch (...)
      {
        YYCDEBUG << "Exception caught: cleaning lookahead and stack\n";
        // Do not try to display the values of the reclaimed symbols,
        // as their printers might throw an exception.
        if (!yyla.empty ())
          yy_destroy_ (YY_NULLPTR, yyla);

        while (1 < yystack_.size ())
          {
            yy_destroy_ (YY_NULLPTR, yystack_[0]);
            yypop_ ();
          }
        throw;
      }
#endif // YY_EXCEPTIONS
  }

  void
  seclang_parser::error (const syntax_error& yyexc)
  {
    error (yyexc.location, yyexc.what ());
  }

  /* Return YYSTR after stripping away unnecessary quotes and
     backslashes, so that it's suitable for yyerror.  The heuristic is
     that double-quoting is unnecessary unless the string contains an
     apostrophe, a comma, or backslash (other than backslash-backslash).
     YYSTR is taken from yytname.  */
  std::string
  seclang_parser::yytnamerr_ (const char *yystr)
  {
    if (*yystr == '"')
      {
        std::string yyr;
        char const *yyp = yystr;

        for (;;)
          switch (*++yyp)
            {
            case '\'':
            case ',':
              goto do_not_strip_quotes;

            case '\\':
              if (*++yyp != '\\')
                goto do_not_strip_quotes;
              else
                goto append;

            append:
            default:
              yyr += *yyp;
              break;

            case '"':
              return yyr;
            }
      do_not_strip_quotes: ;
      }

    return yystr;
  }

  std::string
  seclang_parser::symbol_name (symbol_kind_type yysymbol)
  {
    return yytnamerr_ (yytname_[yysymbol]);
  }



  // seclang_parser::context.
  seclang_parser::context::context (const seclang_parser& yyparser, const symbol_type& yyla)
    : yyparser_ (yyparser)
    , yyla_ (yyla)
  {}

  int
  seclang_parser::context::expected_tokens (symbol_kind_type yyarg[], int yyargn) const
  {
    // Actual number of expected tokens
    int yycount = 0;

    int yyn = yypact_[+yyparser_.yystack_[0].state];
    if (!yy_pact_value_is_default_ (yyn))
      {
        /* Start YYX at -YYN if negative to avoid negative indexes in
           YYCHECK.  In other words, skip the first -YYN actions for
           this state because they are default actions.  */
        int yyxbegin = yyn < 0 ? -yyn : 0;
        // Stay within bounds of both yycheck and yytname.
        int yychecklim = yylast_ - yyn + 1;
        int yyxend = yychecklim < YYNTOKENS ? yychecklim : YYNTOKENS;
        for (int yyx = yyxbegin; yyx < yyxend; ++yyx)
          if (yycheck_[yyx + yyn] == yyx && yyx != symbol_kind::S_YYerror
              && !yy_table_value_is_error_ (yytable_[yyx + yyn]))
            {
              if (!yyarg)
                ++yycount;
              else if (yycount == yyargn)
                return 0;
              else
                yyarg[yycount++] = YY_CAST (symbol_kind_type, yyx);
            }
      }

    if (yyarg && yycount == 0 && 0 < yyargn)
      yyarg[0] = symbol_kind::S_YYEMPTY;
    return yycount;
  }



  int
  seclang_parser::yy_syntax_error_arguments_ (const context& yyctx,
                                                 symbol_kind_type yyarg[], int yyargn) const
  {
    /* There are many possibilities here to consider:
       - If this state is a consistent state with a default action, then
         the only way this function was invoked is if the default action
         is an error action.  In that case, don't check for expected
         tokens because there are none.
       - The only way there can be no lookahead present (in yyla) is
         if this state is a consistent state with a default action.
         Thus, detecting the absence of a lookahead is sufficient to
         determine that there is no unexpected or expected token to
         report.  In that case, just report a simple "syntax error".
       - Don't assume there isn't a lookahead just because this state is
         a consistent state with a default action.  There might have
         been a previous inconsistent state, consistent state with a
         non-default action, or user semantic action that manipulated
         yyla.  (However, yyla is currently not documented for users.)
       - Of course, the expected token list depends on states to have
         correct lookahead information, and it depends on the parser not
         to perform extra reductions after fetching a lookahead from the
         scanner and before detecting a syntax error.  Thus, state merging
         (from LALR or IELR) and default reductions corrupt the expected
         token list.  However, the list is correct for canonical LR with
         one exception: it will still contain any token that will not be
         accepted due to an error action in a later state.
    */

    if (!yyctx.lookahead ().empty ())
      {
        if (yyarg)
          yyarg[0] = yyctx.token ();
        int yyn = yyctx.expected_tokens (yyarg ? yyarg + 1 : yyarg, yyargn - 1);
        return yyn + 1;
      }
    return 0;
  }

  // Generate an error message.
  std::string
  seclang_parser::yysyntax_error_ (const context& yyctx) const
  {
    // Its maximum.
    enum { YYARGS_MAX = 5 };
    // Arguments of yyformat.
    symbol_kind_type yyarg[YYARGS_MAX];
    int yycount = yy_syntax_error_arguments_ (yyctx, yyarg, YYARGS_MAX);

    char const* yyformat = YY_NULLPTR;
    switch (yycount)
      {
#define YYCASE_(N, S)                         \
        case N:                               \
          yyformat = S;                       \
        break
      default: // Avoid compiler warnings.
        YYCASE_ (0, YY_("syntax error"));
        YYCASE_ (1, YY_("syntax error, unexpected %s"));
        YYCASE_ (2, YY_("syntax error, unexpected %s, expecting %s"));
        YYCASE_ (3, YY_("syntax error, unexpected %s, expecting %s or %s"));
        YYCASE_ (4, YY_("syntax error, unexpected %s, expecting %s or %s or %s"));
        YYCASE_ (5, YY_("syntax error, unexpected %s, expecting %s or %s or %s or %s"));
#undef YYCASE_
      }

    std::string yyres;
    // Argument number.
    std::ptrdiff_t yyi = 0;
    for (char const* yyp = yyformat; *yyp; ++yyp)
      if (yyp[0] == '%' && yyp[1] == 's' && yyi < yycount)
        {
          yyres += symbol_name (yyarg[yyi++]);
          ++yyp;
        }
      else
        yyres += *yyp;
    return yyres;
  }


  const short seclang_parser::yypact_ninf_ = -387;

  const signed char seclang_parser::yytable_ninf_ = -1;

  const short
  seclang_parser::yypact_[] =
  {
    2778,  -387,  -277,  -387,  -100,  -387,   -98,  -387,  -387,  -387,
    -387,  -387,  -292,  -387,  -387,  -387,  -387,  -387,  -274,  -387,
    -387,  -387,   -96,   -94,  -387,  -387,  -387,  -387,  -387,  -387,
    -387,  -387,  -387,  -387,  -387,  -387,  -387,  -387,  -387,   -92,
    -387,  -387,   -93,  -387,   -88,  -387,   -89,   -84,  -387,  -284,
     -90,   -90,  -387,  -387,  -387,  -387,   -82,  -301,  -387,  -387,
    -387,  1494,  1494,  1494,   -90,  -271,   -80,  -387,  -387,  -387,
     -78,  -387,  -387,  -387,  -387,  -387,  -387,  -387,  -387,  -387,
    1494,   -90,  2922,  -387,  -387,  -387,  -387,  -387,  -387,  -387,
    -387,  -387,  -387,  -387,  -387,  -387,  -387,  -387,  -387,  -387,
    -387,  -387,  -387,  -387,  -387,  -387,  -387,  -387,  -387,  -387,
    -387,  -387,  -387,  -387,  -387,  2342,  -259,  -387,  -387,  -387,
    -387,  -387,  -387,  -387,  -265,  -387,  -387,  -387,  -387,   -76,
     -74,  -387,  -387,  -387,  -387,  -387,  -387,  -387,  -387,  -387,
    -387,  2475,  -387,  2475,  -387,  2475,  -387,  -387,  -387,  -387,
    -387,  -387,  -387,  -387,  2475,  -387,  -387,  -387,  -387,  -387,
    -387,  2475,  2475,  2475,  2475,  -387,  -387,  -387,  -387,  2475,
    -387,  -387,  -387,  -387,  -387,  -387,  -387,  -387,  -387,  -387,
    -387,  -387,  -387,  -387,  -387,  -387,  -387,  -387,  -387,  -387,
    -387,  -387,  -387,  -387,  -387,  -387,  -387,  -387,  -387,  -387,
    -387,  -387,  -387,  -387,  -387,  -387,  -387,  -387,  3109,  -387,
       2,  -387,  -387,  -387,  -387,  -387,  -387,  2674,  2674,  -305,
    -195,  -192,  -191,  -185,  -184,  -181,  -180,  -172,  -171,  -168,
    -167,  -164,  -163,  -160,  -159,  -156,  -387,  -155,  -152,  -151,
    -148,  -387,  -387,  -147,  -387,  -387,  -387,  -387,  -387,  -387,
    -387,  -387,  -387,  -387,  -387,  -387,  -387,  -387,  -387,  -387,
    -387,  -387,  -387,  -387,  -387,  -387,  -387,  -387,  -387,  -387,
    -387,  -387,  -387,  -387,  -387,  -387,  -387,  -387,  -387,  -144,
    -387,  -387,  -387,  -387,  -387,   460,  -387,  -387,  -387,  -141,
    -387,  -387,  -387,  -387,  -387,  -387,  -387,  -387,  -387,  -387,
    -387,  -387,   550,   640,   976,  1066,  1156,  -140,  -137,  1586,
    -387,  -387,  -387,  -387,  -387,  -387,  -387,  -387,  -387,  -387,
    -387,  -387,  -387,  -387,    16,  -387,  -387,  -387,  -387,  -387,
    -387,  -387,  -387,  -387,  -387,  -387,  2010,  -387,  -387,  -387,
    -387,  2674,   -50,  -387,  -387,  -387,  -387,  -387,  -387,  -387,
    -387,  -387,  -387,  -387,  -387,  -387,  2565,  2565,  2565,  2565,
    2565,  2565,  2565,  2565,  2565,     3,  3109,  -387,  -387,  -387,
    -387,  -387,  -387,  -387,  -387,  -387,  -387,  -387,  -387,  -387,
    -387,  -387,  -387,  -387,  -387,  -387,  -387,  -387,  -387,  -387,
    -387,  -387,  -387,  -387,  -387,  -387,  -387,  -387,  -387,  -387,
    -387,  -387,  -387,  -387,  -387,  -387,  -387,  -387,  -387,  -387,
    -387,  -387,  -387,  -387,  -387,  -387,  -387,  2565,  -387,  -387,
    -387,  -387,  2565,  -387,  -387,  2565,  -387,  -387,  2565,  -387,
    -387,  2565,  -387,  -387,  2565,  -387,  -387,  -387,  -387,     8,
    1678,  2143,  2475,  2475,  2475,  -387,  -387,  2475,  2475,  2475,
    -387,  2475,  2475,  2475,  2475,  2475,  2475,  2475,  2475,  2475,
    2475,  2475,  2475,  2475,  2475,  2475,  2475,  -387,  2475,  2475,
    2475,  2475,  -387,  -387,  2475,  2475,  2475,  2475,  2475,   -90,
    -387,  2565,  -387,  2475,  2475,  2475,  -387,  -387,  -387,  -387,
    -387,  2674,  2674,  -387,  -387,  2565,  2565,  2565,  2565,  2565,
    2565,  2565,  2565,  2565,  2565,  2565,  2565,  2565,  2565,  2565,
    2565,  2565,  2565,  2565,  2565,  2565,  2565,  2565,  2565,  2565,
    2565,  2565,  2565,  2565,  2565,  2565,  2565,  -387,  2565,  2565,
    2565,  -387,  -387
  };

  const short
  seclang_parser::yydefact_[] =
  {
       0,     2,     0,   143,     0,    89,     0,    88,    92,    93,
       7,     6,     0,    11,    14,    12,    13,    17,     0,   126,
     125,    94,     0,     0,   102,   103,   104,   105,    99,   127,
     106,   107,   141,   140,   110,   111,   112,   128,   129,     0,
     132,   130,     0,   131,     0,   133,     0,     0,   115,     0,
       0,     0,    80,   152,   153,   154,     0,     0,   118,   120,
     119,     0,     0,     0,     0,     0,     0,    26,    24,    25,
       0,   142,   148,   149,   150,   147,   151,   116,   117,   146,
       0,     0,     0,     4,    74,     5,    98,    97,    15,    16,
      91,    90,     9,    10,     8,    20,    19,    18,    96,    95,
     101,   100,    85,    84,   134,   135,    87,    86,   136,   137,
     114,   113,    83,    81,    82,     0,     0,   337,   338,   339,
     340,   341,   342,   343,     0,   347,   348,   349,   350,     0,
       0,   358,   359,   360,   361,   362,   363,   364,   365,   366,
     367,     0,   370,     0,   371,     0,   373,   374,   375,   376,
     377,   378,   379,   380,     0,   382,   383,   384,   385,   386,
     387,     0,     0,     0,     0,   393,   394,   395,   396,     0,
     404,   405,   406,   407,   419,   425,   410,   411,   412,   423,
     424,   431,   413,   409,   418,   430,   429,   402,   401,   400,
     434,   433,   422,   420,   435,   421,   408,   403,   426,   427,
     428,   414,   417,   416,   415,   432,   398,   399,     0,    77,
      30,    32,    79,   109,   108,   138,   139,     0,     0,   166,
     169,   172,   175,   178,   181,   184,   187,   190,   193,   196,
     199,   202,   205,   208,   211,   214,   267,   256,   217,   253,
     259,   268,   269,   226,   270,   271,   272,   273,   274,   275,
     276,   277,   278,   279,   280,   281,   282,   283,   284,   285,
     286,   287,   288,   289,   290,   291,   292,   293,   294,   295,
     297,   296,   300,   299,   298,   301,   303,   302,   304,   262,
     305,   306,   307,   309,   308,   230,   310,   311,   263,   266,
     312,   313,   314,   315,   316,   317,   318,   319,   320,   323,
     321,   322,   234,   238,   246,   250,   242,   220,   223,     0,
     325,   324,   326,   327,   328,   329,   330,   331,   332,   333,
     334,   335,   336,   121,   156,   161,   122,   123,   124,    22,
      21,    23,    28,    27,   144,   145,     0,   155,    78,     1,
       3,     0,   437,   392,   357,   356,   355,   345,   344,   346,
     352,   351,   354,   353,   443,   444,   368,   369,   372,   381,
     388,   389,   390,   391,   397,     0,     0,   163,   162,   164,
     165,   167,   168,   170,   171,   173,   174,   176,   177,   179,
     180,   182,   183,   185,   186,   188,   189,   191,   192,   194,
     195,   197,   198,   200,   201,   203,   204,   206,   207,   209,
     210,   212,   213,   254,   255,   215,   216,   251,   252,   257,
     258,   224,   225,   260,   261,   228,   229,   227,   264,   265,
     232,   233,   231,   236,   237,   235,   244,   245,   243,   248,
     249,   247,   240,   241,   239,   218,   219,   221,   222,     0,
       0,     0,     0,     0,     0,    38,    39,     0,     0,     0,
      73,     0,     0,     0,     0,     0,     0,     0,     0,     0,
       0,     0,     0,     0,     0,     0,     0,    37,     0,     0,
       0,     0,    40,    41,     0,     0,     0,     0,     0,    76,
      33,    35,   436,     0,     0,     0,   441,   442,    29,    31,
     157,     0,     0,   158,    34,    36,    72,    56,    55,    57,
      58,    43,    59,    52,    60,    42,    61,    62,    63,    64,
      65,    66,    67,    53,    68,    69,    70,    71,    44,    45,
      46,    47,    48,    49,    50,    51,    54,    75,   438,   439,
     440,   160,   159
  };

  const short
  seclang_parser::yypgoto_[] =
  {
    -387,  -387,   -32,  -387,   -47,  -200,  -387,  -386,  -387,  -387,
     -51,  -154,   -61,  -131,  -387,  -136
  };

  const short
  seclang_parser::yydefgoto_[] =
  {
       0,    82,    83,    84,   209,   210,   479,   480,    85,   336,
     323,   324,   355,   211,   343,   356
  };

  const short
  seclang_parser::yytable_[] =
  {
     325,   325,   325,   215,   212,   366,   366,   357,   365,   358,
     115,   326,   327,   216,   440,    92,    93,   328,   359,   325,
      94,   112,   440,   113,   114,   360,   361,   362,   363,   337,
      86,    87,    95,   364,   338,    96,   329,   330,   369,    97,
     370,   331,   347,   348,    88,    89,   344,   349,   345,   346,
     340,   483,   484,   485,   342,   494,   116,   117,   118,   119,
     120,   121,   122,   123,   124,   125,   126,   127,   128,   129,
     130,   131,   132,   133,   134,   135,   136,   137,   138,   139,
     140,   141,   142,   143,   144,   145,   146,   147,   148,   149,
     150,   151,   152,   153,   154,   155,   156,   157,   158,   159,
     160,   161,   162,   163,   164,   165,   166,   167,   168,   169,
     170,   171,   172,   173,   174,   175,   176,   177,   178,   179,
     180,   181,   182,   183,   184,   185,   186,   187,   188,   189,
     190,   191,   192,   193,   194,   195,   196,   197,   198,   199,
     200,   201,   202,   203,   204,   205,   206,   207,   371,   417,
     372,   373,   375,   374,   376,   439,   367,   368,   377,   379,
     378,   380,   381,   383,   382,   384,   422,   425,   428,   431,
     434,   385,   387,   386,   388,   389,   391,   390,   392,   393,
     395,   394,   396,   397,   399,   398,   400,   401,   403,   402,
     404,   405,   407,   406,   408,   409,   411,   410,   412,   413,
     481,   414,   418,   435,   419,   436,   437,     0,   438,    90,
      91,    98,    99,   100,   101,   102,   103,   104,   105,   106,
     107,   108,   109,   110,   111,   213,   214,   332,   333,   334,
     335,   350,   351,   352,   353,   489,     0,     0,   208,     0,
       0,     0,     0,     0,     0,     0,     0,     0,   325,     0,
       0,     0,     0,     0,     0,     0,     0,     0,     0,     0,
       0,     0,     0,     0,     0,     0,     0,     0,     0,     0,
       0,     0,     0,     0,     0,     0,     0,     0,     0,     0,
     482,     0,     0,     0,     0,     0,     0,     0,     0,     0,
       0,     0,     0,     0,     0,   487,   487,   487,   487,   487,
     487,   487,   487,   487,     0,   495,   496,   497,   498,     0,
       0,   499,   500,   501,     0,   502,   503,   504,   505,   506,
     507,   508,   509,   510,   511,   512,   513,   514,   515,   516,
     517,   488,   518,   519,   520,   521,   490,     0,   522,   523,
     524,   525,   526,     0,     0,     0,     0,   528,   529,   530,
       0,     0,     0,     0,     0,     0,   487,     0,     0,     0,
       0,   487,     0,     0,   487,     0,     0,   487,     0,     0,
     487,     0,     0,   487,     0,     0,     0,     0,     0,   493,
       0,     0,     0,     0,     0,     0,     0,     0,     0,     0,
       0,     0,     0,     0,     0,     0,     0,     0,     0,     0,
       0,     0,     0,     0,     0,     0,     0,     0,     0,     0,
       0,     0,     0,     0,     0,     0,     0,     0,     0,     0,
     487,     0,     0,     0,     0,     0,     0,     0,     0,     0,
     531,   532,   527,     0,   487,   487,   487,   487,   487,   487,
     487,   487,   487,   487,   487,   487,   487,   487,   487,   487,
     487,   487,   487,   487,   487,   487,   487,   487,   487,   487,
     487,   487,   487,   487,   487,   487,     0,   487,   487,   487,
     219,   220,   221,   222,   223,   224,   225,   226,   227,   228,
     229,   230,   231,   232,   233,   234,   235,   236,   237,   238,
     239,   240,   241,   242,   243,   244,   245,   246,   247,   248,
     249,   250,   251,   252,   253,   254,   255,   256,   257,   258,
     259,   260,   261,   262,   263,   264,   265,   266,   267,   268,
     269,   270,   271,   272,   273,   274,   275,   276,   277,   278,
     279,   280,   281,   282,   283,   284,   285,   286,   287,   288,
     289,   290,   291,   292,   293,   294,   295,   296,   297,   298,
     299,   300,   301,   302,   303,   304,   305,   306,   307,   308,
     219,   220,   221,   222,   223,   224,   225,   226,   227,   228,
     229,   230,   231,   232,   233,   234,   235,   236,   237,   238,
     239,   240,   241,   242,   243,   244,   245,   246,   247,   248,
     249,   250,   251,   252,   253,   254,   255,   256,   257,   258,
     259,   260,   261,   262,   263,   264,   265,   266,   267,   268,
     269,   270,   271,   272,   273,   274,   275,   276,   277,   278,
     279,   280,   281,   282,   283,   284,   285,   286,   287,   288,
     289,   290,   291,   292,   293,   294,   295,   296,   297,   298,
     299,   300,   301,   302,   303,   304,   305,   306,   307,   308,
     219,   220,   221,   222,   223,   224,   225,   226,   227,   228,
     229,   230,   231,   232,   233,   234,   235,   236,   237,   238,
     239,   240,   241,   242,   243,   244,   245,   246,   247,   248,
     249,   250,   251,   252,   253,   254,   255,   256,   257,   258,
     259,   260,   261,   262,   263,   264,   265,   266,   267,   268,
     269,   270,   271,   272,   273,   274,   275,   276,   277,   278,
     279,   280,   281,   282,   283,   284,   285,   286,   287,   288,
     289,   290,   291,   292,   293,   294,   295,   296,   297,   298,
     299,   300,   301,   302,   303,   304,   305,   306,   307,   308,
       0,     0,     0,     0,     0,     0,     0,     0,     0,     0,
       0,     0,     0,     0,     0,     0,     0,     0,     0,     0,
       0,     0,     0,     0,     0,     0,     0,     0,     0,     0,
       0,     0,     0,     0,     0,     0,     0,     0,     0,     0,
       0,     0,     0,     0,     0,     0,     0,   354,     0,   310,
     311,   312,   313,   314,   315,   316,   317,   318,   319,   320,
     321,   322,     0,   415,     0,   416,     0,     0,     0,     0,
       0,     0,     0,     0,     0,     0,     0,     0,     0,     0,
       0,     0,     0,     0,     0,     0,     0,     0,     0,     0,
       0,     0,     0,     0,     0,     0,     0,     0,     0,     0,
       0,     0,     0,     0,     0,     0,     0,     0,     0,     0,
       0,     0,     0,     0,     0,     0,     0,     0,     0,     0,
       0,     0,     0,     0,     0,     0,     0,     0,     0,     0,
       0,     0,     0,     0,     0,     0,     0,   354,     0,   310,
     311,   312,   313,   314,   315,   316,   317,   318,   319,   320,
     321,   322,     0,   420,     0,   421,     0,     0,     0,     0,
       0,     0,     0,     0,     0,     0,     0,     0,     0,     0,
       0,     0,     0,     0,     0,     0,     0,     0,     0,     0,
       0,     0,     0,     0,     0,     0,     0,     0,     0,     0,
       0,     0,     0,     0,     0,     0,     0,     0,     0,     0,
       0,     0,     0,     0,     0,     0,     0,     0,     0,     0,
       0,     0,     0,     0,     0,     0,     0,     0,     0,     0,
       0,     0,     0,     0,     0,     0,     0,   354,     0,   310,
     311,   312,   313,   314,   315,   316,   317,   318,   319,   320,
     321,   322,     0,   423,     0,   424,   219,   220,   221,   222,
     223,   224,   225,   226,   227,   228,   229,   230,   231,   232,
     233,   234,   235,   236,   237,   238,   239,   240,   241,   242,
     243,   244,   245,   246,   247,   248,   249,   250,   251,   252,
     253,   254,   255,   256,   257,   258,   259,   260,   261,   262,
     263,   264,   265,   266,   267,   268,   269,   270,   271,   272,
     273,   274,   275,   276,   277,   278,   279,   280,   281,   282,
     283,   284,   285,   286,   287,   288,   289,   290,   291,   292,
     293,   294,   295,   296,   297,   298,   299,   300,   301,   302,
     303,   304,   305,   306,   307,   308,   219,   220,   221,   222,
     223,   224,   225,   226,   227,   228,   229,   230,   231,   232,
     233,   234,   235,   236,   237,   238,   239,   240,   241,   242,
     243,   244,   245,   246,   247,   248,   249,   250,   251,   252,
     253,   254,   255,   256,   257,   258,   259,   260,   261,   262,
     263,   264,   265,   266,   267,   268,   269,   270,   271,   272,
     273,   274,   275,   276,   277,   278,   279,   280,   281,   282,
     283,   284,   285,   286,   287,   288,   289,   290,   291,   292,
     293,   294,   295,   296,   297,   298,   299,   300,   301,   302,
     303,   304,   305,   306,   307,   308,   219,   220,   221,   222,
     223,   224,   225,   226,   227,   228,   229,   230,   231,   232,
     233,   234,   235,   236,   237,   238,   239,   240,   241,   242,
     243,   244,   245,   246,   247,   248,   249,   250,   251,   252,
     253,   254,   255,   256,   257,   258,   259,   260,   261,   262,
     263,   264,   265,   266,   267,   268,   269,   270,   271,   272,
     273,   274,   275,   276,   277,   278,   279,   280,   281,   282,
     283,   284,   285,   286,   287,   288,   289,   290,   291,   292,
     293,   294,   295,   296,   297,   298,   299,   300,   301,   302,
     303,   304,   305,   306,   307,   308,     0,     0,     0,     0,
       0,     0,     0,     0,     0,     0,     0,     0,     0,     0,
       0,     0,     0,     0,     0,     0,     0,     0,     0,     0,
       0,     0,     0,     0,     0,     0,     0,     0,     0,     0,
       0,     0,     0,     0,     0,     0,     0,     0,     0,     0,
       0,     0,     0,   354,     0,   310,   311,   312,   313,   314,
     315,   316,   317,   318,   319,   320,   321,   322,     0,   426,
       0,   427,     0,     0,     0,     0,     0,     0,     0,     0,
       0,     0,     0,     0,     0,     0,     0,     0,     0,     0,
       0,     0,     0,     0,     0,     0,     0,     0,     0,     0,
       0,     0,     0,     0,     0,     0,     0,     0,     0,     0,
       0,     0,     0,     0,     0,     0,     0,     0,     0,     0,
       0,     0,     0,     0,     0,     0,     0,     0,     0,     0,
       0,     0,     0,     0,     0,     0,     0,     0,     0,     0,
       0,     0,     0,   354,     0,   310,   311,   312,   313,   314,
     315,   316,   317,   318,   319,   320,   321,   322,     0,   429,
       0,   430,     0,     0,     0,     0,     0,     0,     0,     0,
       0,     0,     0,     0,     0,     0,     0,     0,     0,     0,
       0,     0,     0,     0,     0,     0,     0,     0,     0,     0,
       0,     0,     0,     0,     0,     0,     0,     0,     0,     0,
       0,     0,     0,     0,     0,     0,     0,     0,     0,     0,
       0,     0,     0,     0,     0,     0,     0,     0,     0,     0,
       0,     0,     0,     0,     0,     0,     0,     0,     0,     0,
       0,     0,     0,   354,     0,   310,   311,   312,   313,   314,
     315,   316,   317,   318,   319,   320,   321,   322,     0,   432,
       0,   433,   217,   218,   219,   220,   221,   222,   223,   224,
     225,   226,   227,   228,   229,   230,   231,   232,   233,   234,
     235,   236,   237,   238,   239,   240,   241,   242,   243,   244,
     245,   246,   247,   248,   249,   250,   251,   252,   253,   254,
     255,   256,   257,   258,   259,   260,   261,   262,   263,   264,
     265,   266,   267,   268,   269,   270,   271,   272,   273,   274,
     275,   276,   277,   278,   279,   280,   281,   282,   283,   284,
     285,   286,   287,   288,   289,   290,   291,   292,   293,   294,
     295,   296,   297,   298,   299,   300,   301,   302,   303,   304,
     305,   306,   307,   308,   217,   218,   219,   220,   221,   222,
     223,   224,   225,   226,   227,   228,   229,   230,   231,   232,
     233,   234,   235,   236,   237,   238,   239,   240,   241,   242,
     243,   244,   245,   246,   247,   248,   249,   250,   251,   252,
     253,   254,   255,   256,   257,   258,   259,   260,   261,   262,
     263,   264,   265,   266,   267,   268,   269,   270,   271,   272,
     273,   274,   275,   276,   277,   278,   279,   280,   281,   282,
     283,   284,   285,   286,   287,   288,   289,   290,   291,   292,
     293,   294,   295,   296,   297,   298,   299,   300,   301,   302,
     303,   304,   305,   306,   307,   308,   491,   492,   219,   220,
     221,   222,   223,   224,   225,   226,   227,   228,   229,   230,
     231,   232,   233,   234,   235,   236,   237,   238,   239,   240,
     241,   242,   243,   244,   245,   246,   247,   248,   249,   250,
     251,   252,   253,   254,   255,   256,   257,   258,   259,   260,
     261,   262,   263,   264,   265,   266,   267,   268,   269,   270,
     271,   272,   273,   274,   275,   276,   277,   278,   279,   280,
     281,   282,   283,   284,   285,   286,   287,   288,   289,   290,
     291,   292,   293,   294,   295,   296,   297,   298,   299,   300,
     301,   302,   303,   304,   305,   306,   307,   308,     0,     0,
       0,     0,     0,     0,     0,     0,     0,     0,     0,     0,
       0,     0,     0,     0,     0,     0,     0,     0,     0,     0,
       0,     0,     0,     0,     0,     0,     0,     0,     0,     0,
       0,     0,     0,     0,     0,     0,     0,     0,     0,     0,
       0,     0,   309,   310,   311,   312,   313,   314,   315,   316,
     317,   318,   319,   320,   321,   322,     0,     0,     0,     0,
       0,     0,     0,     0,     0,     0,     0,     0,     0,     0,
       0,     0,     0,     0,     0,     0,     0,     0,     0,     0,
       0,     0,     0,     0,     0,     0,     0,     0,     0,     0,
       0,     0,     0,     0,     0,     0,     0,     0,     0,     0,
       0,     0,     0,     0,     0,     0,     0,     0,     0,     0,
       0,     0,     0,     0,     0,     0,     0,     0,     0,     0,
       0,     0,     0,     0,     0,     0,     0,     0,     0,     0,
       0,     0,     0,     0,     0,   310,   311,   312,   313,   314,
     315,   316,   317,   318,   319,   320,   321,   322,     0,     0,
       0,     0,     0,     0,     0,     0,     0,     0,     0,     0,
       0,     0,     0,     0,     0,     0,     0,     0,     0,     0,
       0,     0,     0,     0,     0,     0,     0,     0,     0,     0,
       0,     0,     0,     0,     0,     0,     0,     0,     0,     0,
       0,     0,     0,     0,     0,     0,     0,     0,     0,     0,
       0,     0,     0,     0,     0,     0,     0,     0,     0,     0,
       0,     0,     0,     0,     0,     0,     0,     0,     0,     0,
       0,     0,     0,     0,     0,     0,     0,   310,   311,   312,
     313,   314,   315,   316,   317,   318,   319,   320,   321,   322,
     219,   220,   221,   222,   223,   224,   225,   226,   227,   228,
     229,   230,   231,   232,   233,   234,   235,   236,   237,   238,
     239,   240,   241,   242,   243,   244,   245,   246,   247,   248,
     249,   250,   251,   252,   253,   254,   255,   256,   257,   258,
     259,   260,   261,   262,   263,   264,   265,   266,   267,   268,
     269,   270,   271,   272,   273,   274,   275,   276,   277,   278,
     279,   280,   281,   282,   283,   284,   285,   286,   287,   288,
     289,   290,   291,   292,   293,   294,   295,   296,   297,   298,
     299,   300,   301,   302,   303,   304,   305,   306,   307,   308,
       0,     0,     0,     0,   441,   442,   443,   444,   445,   446,
     447,   448,   449,   450,   451,   452,   453,   454,   455,   456,
     457,   458,   459,   460,   461,   462,     0,   463,   464,   465,
     466,   467,   468,   469,   470,   471,   472,   473,   474,   475,
     476,   477,   478,   219,   220,   221,   222,   223,   224,   225,
     226,   227,   228,   229,   230,   231,   232,   233,   234,   235,
     236,   237,   238,   239,   240,   241,   242,   243,   244,   245,
     246,   247,   248,   249,   250,   251,   252,   253,   254,   255,
     256,   257,   258,   259,   260,   261,   262,   263,   264,   265,
     266,   267,   268,   269,   270,   271,   272,   273,   274,   275,
     276,   277,   278,   279,   280,   281,   282,   283,   284,   285,
     286,   287,   288,   289,   290,   291,   292,   293,   294,   295,
     296,   297,   298,   299,   300,   301,   302,   303,   304,   305,
     306,   307,   308,     0,     0,     0,     0,     0,   442,   443,
     444,   445,   446,   447,   448,   449,   450,   451,   452,   453,
     454,   455,   456,   457,   458,   459,   460,   461,   462,     0,
     463,   464,   465,   466,   467,   468,   469,   470,   471,   472,
     473,   474,   475,   476,   477,   478,     0,     0,     0,     0,
       0,     0,     0,     0,     0,     0,     0,     0,     0,     0,
       0,     0,     0,     0,     0,     0,     0,     0,     0,     0,
       0,     0,     0,     0,     0,     0,     0,     0,     0,     0,
       0,     0,     0,     0,     0,     0,     0,     0,     0,     0,
       0,     0,     0,     0,     0,     0,     0,   354,     0,   310,
     311,   312,   313,   314,   315,   316,   317,   318,   319,   320,
     321,   322,   219,   220,   221,   222,   223,   224,   225,   226,
     227,   228,   229,   230,   231,   232,   233,   234,   235,   236,
     237,   238,   239,   240,   241,   242,   243,   244,   245,   246,
     247,   248,   249,   250,   251,   252,   253,   254,   255,   256,
     257,   258,   259,   260,   261,   262,   263,   264,   265,   266,
     267,   268,   269,   270,   271,   272,   273,   274,   275,   276,
     277,   278,   279,   280,   281,   282,   283,   284,   285,   286,
     287,   288,   289,   290,   291,   292,   293,   294,   295,   296,
     297,   298,   299,   300,   301,   302,   303,   304,   305,   306,
     307,   308,     0,     0,     0,     0,   341,     0,     0,     0,
       0,     0,     0,     0,     0,     0,     0,     0,     0,     0,
       0,     0,     0,     0,     0,     0,     0,     0,     0,     0,
     354,     0,   310,   311,   312,   313,   314,   315,   316,   317,
     318,   319,   320,   321,   322,   219,   220,   221,   222,   223,
     224,   225,   226,   227,   228,   229,   230,   231,   232,   233,
     234,   235,   236,   237,   238,   239,   240,   241,   242,   243,
     244,   245,   246,   247,   248,   249,   250,   251,   252,   253,
     254,   255,   256,   257,   258,   259,   260,   261,   262,   263,
     264,   265,   266,   267,   268,   269,   270,   271,   272,   273,
     274,   275,   276,   277,   278,   279,   280,   281,   282,   283,
     284,   285,   286,   287,   288,   289,   290,   291,   292,   293,
     294,   295,   296,   297,   298,   299,   300,   301,   302,   303,
     304,   305,   306,   307,   308,   219,   220,   221,   222,   223,
     224,   225,   226,   227,   228,   229,   230,   231,   232,   233,
     234,   235,   236,   237,   238,   239,   240,   241,   242,   243,
     244,   245,   246,   247,   248,   249,   250,   251,   252,   253,
     254,   255,   256,   257,   258,   259,   260,   261,   262,   263,
     264,   265,   266,   267,   268,   269,   270,   271,   272,   273,
     274,   275,   276,   277,   278,   279,   280,   281,   282,   283,
     284,   285,   286,   287,   288,   289,   290,   291,   292,   293,
     294,   295,   296,   297,   298,   299,   300,   301,   302,   303,
     304,   305,   306,   307,   308,     0,     0,     0,     0,     0,
       0,   310,   311,   312,   313,   314,   315,   316,   317,   318,
     319,   320,   321,   322,   219,   220,   221,   222,   223,   224,
     225,   226,   227,   228,   229,   230,   231,   232,   233,   234,
     235,   236,   237,   238,   239,   240,   241,   242,   243,   244,
     245,   246,   247,   248,   249,   250,   251,   252,   253,   254,
     255,   256,   257,   258,   259,   260,   261,   262,   263,   264,
     265,   266,   267,   268,   269,   270,   271,   272,   273,   274,
     275,   276,   277,   278,   279,   280,   281,   282,   283,   284,
     285,   286,   287,   288,   289,   290,   291,   292,   293,   294,
     295,   296,   297,   298,   299,   300,   301,   302,   303,   304,
     305,   306,   307,   308,     0,     0,     0,     0,     1,     0,
       0,     0,     2,     3,     0,     0,     0,     0,     0,     0,
       0,     0,     0,     0,     0,     0,     0,     0,     0,     0,
       0,     0,   354,     0,   310,   311,   312,   313,   314,   315,
     316,   317,   318,   319,   320,   321,   322,     0,     0,     0,
       0,     0,     0,     0,     0,     0,     0,     0,     0,     0,
       0,     0,     0,     0,     0,     0,     0,     0,     0,     0,
       0,     0,     0,     0,     0,     0,     0,     0,     0,     0,
       0,     0,     0,     0,     0,     0,     0,     0,     0,     0,
       0,     0,     0,     0,     0,     0,     0,     0,     0,     0,
       0,     0,     0,     0,     0,     0,     0,     0,     0,     0,
       0,     0,     0,     0,     0,     0,     0,     0,     0,     0,
       0,     0,   486,     0,   310,   311,   312,   313,   314,   315,
     316,   317,   318,   319,   320,   321,   322,     0,     0,     0,
       0,     0,     0,     0,     0,     0,     0,     0,     0,     0,
       0,     4,   339,     0,     0,     0,     2,     3,     0,     0,
       0,     0,     0,     0,     0,     0,     0,     0,     0,     0,
       0,     0,     0,     0,     0,     0,     0,     0,     0,     0,
       0,     0,     0,     0,     0,     0,     0,     0,     0,     0,
       0,     0,     0,     0,     0,     0,     0,     0,     0,     0,
       0,     0,     0,     0,     0,     0,     0,     0,     0,     0,
       0,     0,     0,     0,     0,     0,     0,     0,     0,     0,
       0,     0,     0,     0,     0,     0,     0,     0,     0,     0,
       0,     0,     0,   310,   311,   312,   313,   314,   315,   316,
     317,   318,   319,   320,   321,   322,     5,     6,     7,     8,
       9,    10,    11,    12,    13,    14,    15,    16,    17,    18,
      19,    20,    21,    22,    23,    24,    25,    26,    27,    28,
      29,    30,    31,    32,    33,    34,    35,    36,    37,    38,
      39,    40,    41,    42,    43,    44,    45,    46,    47,    48,
      49,    50,    51,    52,    53,     4,    54,    55,    56,    57,
      58,    59,    60,    61,    62,    63,    64,    65,    66,    67,
      68,    69,     0,     0,     0,     0,     0,     0,     0,     0,
       0,     0,     0,    70,    71,    72,    73,    74,    75,    76,
      77,    78,    79,    80,    81,     0,     0,     0,     0,     0,
       0,     0,     0,     0,     0,     0,     0,     0,     0,     0,
       0,     0,     0,     0,     0,     0,     0,     0,     0,     0,
       0,     0,     0,     0,     0,     0,     0,     0,     0,     0,
       0,     0,     0,     0,     0,     0,     0,     0,     0,     0,
       0,     0,     0,     0,     0,     0,     0,     0,     0,     0,
       5,     6,     7,     8,     9,    10,    11,    12,    13,    14,
      15,    16,    17,    18,    19,    20,    21,    22,    23,    24,
      25,    26,    27,    28,    29,    30,    31,    32,    33,    34,
      35,    36,    37,    38,    39,    40,    41,    42,    43,    44,
      45,    46,    47,    48,    49,    50,    51,    52,    53,   115,
      54,    55,    56,    57,    58,    59,    60,    61,    62,    63,
      64,    65,    66,    67,    68,    69,     0,     0,     0,     0,
       0,     0,     0,     0,     0,     0,     0,    70,    71,    72,
      73,    74,    75,    76,    77,    78,    79,    80,    81,     0,
       0,     0,     0,     0,     0,   116,   117,   118,   119,   120,
     121,   122,   123,   124,   125,   126,   127,   128,   129,   130,
     131,   132,   133,   134,   135,   136,   137,   138,   139,   140,
     141,   142,   143,   144,   145,   146,   147,   148,   149,   150,
     151,   152,   153,   154,   155,   156,   157,   158,   159,   160,
     161,   162,   163,   164,   165,   166,   167,   168,   169,   170,
     171,   172,   173,   174,   175,   176,   177,   178,   179,   180,
     181,   182,   183,   184,   185,   186,   187,   188,   189,   190,
     191,   192,   193,   194,   195,   196,   197,   198,   199,   200,
     201,   202,   203,   204,   205,   206,   207
  };

  const short
  seclang_parser::yycheck_[] =
  {
      61,    62,    63,   304,    51,     3,     3,   143,   208,   145,
     100,    62,    63,   314,     6,   307,   308,    64,   154,    80,
     312,   305,     6,   307,   308,   161,   162,   163,   164,    80,
     307,   308,   306,   169,    81,   309,   307,   308,   343,   313,
     345,   312,   307,   308,   144,   145,   305,   312,   307,   308,
      82,   101,   102,   103,   115,   441,   146,   147,   148,   149,
     150,   151,   152,   153,   154,   155,   156,   157,   158,   159,
     160,   161,   162,   163,   164,   165,   166,   167,   168,   169,
     170,   171,   172,   173,   174,   175,   176,   177,   178,   179,
     180,   181,   182,   183,   184,   185,   186,   187,   188,   189,
     190,   191,   192,   193,   194,   195,   196,   197,   198,   199,
     200,   201,   202,   203,   204,   205,   206,   207,   208,   209,
     210,   211,   212,   213,   214,   215,   216,   217,   218,   219,
     220,   221,   222,   223,   224,   225,   226,   227,   228,   229,
     230,   231,   232,   233,   234,   235,   236,   237,   343,   285,
     345,   343,   343,   345,   345,   309,   217,   218,   343,   343,
     345,   345,   343,   343,   345,   345,   302,   303,   304,   305,
     306,   343,   343,   345,   345,   343,   343,   345,   345,   343,
     343,   345,   345,   343,   343,   345,   345,   343,   343,   345,
     345,   343,   343,   345,   345,   343,   343,   345,   345,   343,
     336,   345,   343,   343,   345,   345,   343,    -1,   345,   307,
     308,   307,   308,   307,   308,   307,   308,   310,   311,   307,
     308,   310,   311,   307,   308,   307,   308,   307,   308,   307,
     308,   307,   308,   307,   308,   366,    -1,    -1,   328,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,   309,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,
     341,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,   356,   357,   358,   359,   360,
     361,   362,   363,   364,    -1,   441,   442,   443,   444,    -1,
      -1,   447,   448,   449,    -1,   451,   452,   453,   454,   455,
     456,   457,   458,   459,   460,   461,   462,   463,   464,   465,
     466,   328,   468,   469,   470,   471,   328,    -1,   474,   475,
     476,   477,   478,    -1,    -1,    -1,    -1,   483,   484,   485,
      -1,    -1,    -1,    -1,    -1,    -1,   417,    -1,    -1,    -1,
      -1,   422,    -1,    -1,   425,    -1,    -1,   428,    -1,    -1,
     431,    -1,    -1,   434,    -1,    -1,    -1,    -1,    -1,   440,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,
     481,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,
     491,   492,   479,    -1,   495,   496,   497,   498,   499,   500,
     501,   502,   503,   504,   505,   506,   507,   508,   509,   510,
     511,   512,   513,   514,   515,   516,   517,   518,   519,   520,
     521,   522,   523,   524,   525,   526,    -1,   528,   529,   530,
      10,    11,    12,    13,    14,    15,    16,    17,    18,    19,
      20,    21,    22,    23,    24,    25,    26,    27,    28,    29,
      30,    31,    32,    33,    34,    35,    36,    37,    38,    39,
      40,    41,    42,    43,    44,    45,    46,    47,    48,    49,
      50,    51,    52,    53,    54,    55,    56,    57,    58,    59,
      60,    61,    62,    63,    64,    65,    66,    67,    68,    69,
      70,    71,    72,    73,    74,    75,    76,    77,    78,    79,
      80,    81,    82,    83,    84,    85,    86,    87,    88,    89,
      90,    91,    92,    93,    94,    95,    96,    97,    98,    99,
      10,    11,    12,    13,    14,    15,    16,    17,    18,    19,
      20,    21,    22,    23,    24,    25,    26,    27,    28,    29,
      30,    31,    32,    33,    34,    35,    36,    37,    38,    39,
      40,    41,    42,    43,    44,    45,    46,    47,    48,    49,
      50,    51,    52,    53,    54,    55,    56,    57,    58,    59,
      60,    61,    62,    63,    64,    65,    66,    67,    68,    69,
      70,    71,    72,    73,    74,    75,    76,    77,    78,    79,
      80,    81,    82,    83,    84,    85,    86,    87,    88,    89,
      90,    91,    92,    93,    94,    95,    96,    97,    98,    99,
      10,    11,    12,    13,    14,    15,    16,    17,    18,    19,
      20,    21,    22,    23,    24,    25,    26,    27,    28,    29,
      30,    31,    32,    33,    34,    35,    36,    37,    38,    39,
      40,    41,    42,    43,    44,    45,    46,    47,    48,    49,
      50,    51,    52,    53,    54,    55,    56,    57,    58,    59,
      60,    61,    62,    63,    64,    65,    66,    67,    68,    69,
      70,    71,    72,    73,    74,    75,    76,    77,    78,    79,
      80,    81,    82,    83,    84,    85,    86,    87,    88,    89,
      90,    91,    92,    93,    94,    95,    96,    97,    98,    99,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,   327,    -1,   329,
     330,   331,   332,   333,   334,   335,   336,   337,   338,   339,
     340,   341,    -1,   343,    -1,   345,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,   327,    -1,   329,
     330,   331,   332,   333,   334,   335,   336,   337,   338,   339,
     340,   341,    -1,   343,    -1,   345,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,   327,    -1,   329,
     330,   331,   332,   333,   334,   335,   336,   337,   338,   339,
     340,   341,    -1,   343,    -1,   345,    10,    11,    12,    13,
      14,    15,    16,    17,    18,    19,    20,    21,    22,    23,
      24,    25,    26,    27,    28,    29,    30,    31,    32,    33,
      34,    35,    36,    37,    38,    39,    40,    41,    42,    43,
      44,    45,    46,    47,    48,    49,    50,    51,    52,    53,
      54,    55,    56,    57,    58,    59,    60,    61,    62,    63,
      64,    65,    66,    67,    68,    69,    70,    71,    72,    73,
      74,    75,    76,    77,    78,    79,    80,    81,    82,    83,
      84,    85,    86,    87,    88,    89,    90,    91,    92,    93,
      94,    95,    96,    97,    98,    99,    10,    11,    12,    13,
      14,    15,    16,    17,    18,    19,    20,    21,    22,    23,
      24,    25,    26,    27,    28,    29,    30,    31,    32,    33,
      34,    35,    36,    37,    38,    39,    40,    41,    42,    43,
      44,    45,    46,    47,    48,    49,    50,    51,    52,    53,
      54,    55,    56,    57,    58,    59,    60,    61,    62,    63,
      64,    65,    66,    67,    68,    69,    70,    71,    72,    73,
      74,    75,    76,    77,    78,    79,    80,    81,    82,    83,
      84,    85,    86,    87,    88,    89,    90,    91,    92,    93,
      94,    95,    96,    97,    98,    99,    10,    11,    12,    13,
      14,    15,    16,    17,    18,    19,    20,    21,    22,    23,
      24,    25,    26,    27,    28,    29,    30,    31,    32,    33,
      34,    35,    36,    37,    38,    39,    40,    41,    42,    43,
      44,    45,    46,    47,    48,    49,    50,    51,    52,    53,
      54,    55,    56,    57,    58,    59,    60,    61,    62,    63,
      64,    65,    66,    67,    68,    69,    70,    71,    72,    73,
      74,    75,    76,    77,    78,    79,    80,    81,    82,    83,
      84,    85,    86,    87,    88,    89,    90,    91,    92,    93,
      94,    95,    96,    97,    98,    99,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,   327,    -1,   329,   330,   331,   332,   333,
     334,   335,   336,   337,   338,   339,   340,   341,    -1,   343,
      -1,   345,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,   327,    -1,   329,   330,   331,   332,   333,
     334,   335,   336,   337,   338,   339,   340,   341,    -1,   343,
      -1,   345,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,   327,    -1,   329,   330,   331,   332,   333,
     334,   335,   336,   337,   338,   339,   340,   341,    -1,   343,
      -1,   345,     8,     9,    10,    11,    12,    13,    14,    15,
      16,    17,    18,    19,    20,    21,    22,    23,    24,    25,
      26,    27,    28,    29,    30,    31,    32,    33,    34,    35,
      36,    37,    38,    39,    40,    41,    42,    43,    44,    45,
      46,    47,    48,    49,    50,    51,    52,    53,    54,    55,
      56,    57,    58,    59,    60,    61,    62,    63,    64,    65,
      66,    67,    68,    69,    70,    71,    72,    73,    74,    75,
      76,    77,    78,    79,    80,    81,    82,    83,    84,    85,
      86,    87,    88,    89,    90,    91,    92,    93,    94,    95,
      96,    97,    98,    99,     8,     9,    10,    11,    12,    13,
      14,    15,    16,    17,    18,    19,    20,    21,    22,    23,
      24,    25,    26,    27,    28,    29,    30,    31,    32,    33,
      34,    35,    36,    37,    38,    39,    40,    41,    42,    43,
      44,    45,    46,    47,    48,    49,    50,    51,    52,    53,
      54,    55,    56,    57,    58,    59,    60,    61,    62,    63,
      64,    65,    66,    67,    68,    69,    70,    71,    72,    73,
      74,    75,    76,    77,    78,    79,    80,    81,    82,    83,
      84,    85,    86,    87,    88,    89,    90,    91,    92,    93,
      94,    95,    96,    97,    98,    99,     8,     9,    10,    11,
      12,    13,    14,    15,    16,    17,    18,    19,    20,    21,
      22,    23,    24,    25,    26,    27,    28,    29,    30,    31,
      32,    33,    34,    35,    36,    37,    38,    39,    40,    41,
      42,    43,    44,    45,    46,    47,    48,    49,    50,    51,
      52,    53,    54,    55,    56,    57,    58,    59,    60,    61,
      62,    63,    64,    65,    66,    67,    68,    69,    70,    71,
      72,    73,    74,    75,    76,    77,    78,    79,    80,    81,
      82,    83,    84,    85,    86,    87,    88,    89,    90,    91,
      92,    93,    94,    95,    96,    97,    98,    99,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,
      -1,    -1,   328,   329,   330,   331,   332,   333,   334,   335,
     336,   337,   338,   339,   340,   341,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,   329,   330,   331,   332,   333,
     334,   335,   336,   337,   338,   339,   340,   341,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,   329,   330,   331,
     332,   333,   334,   335,   336,   337,   338,   339,   340,   341,
      10,    11,    12,    13,    14,    15,    16,    17,    18,    19,
      20,    21,    22,    23,    24,    25,    26,    27,    28,    29,
      30,    31,    32,    33,    34,    35,    36,    37,    38,    39,
      40,    41,    42,    43,    44,    45,    46,    47,    48,    49,
      50,    51,    52,    53,    54,    55,    56,    57,    58,    59,
      60,    61,    62,    63,    64,    65,    66,    67,    68,    69,
      70,    71,    72,    73,    74,    75,    76,    77,    78,    79,
      80,    81,    82,    83,    84,    85,    86,    87,    88,    89,
      90,    91,    92,    93,    94,    95,    96,    97,    98,    99,
      -1,    -1,    -1,    -1,   104,   105,   106,   107,   108,   109,
     110,   111,   112,   113,   114,   115,   116,   117,   118,   119,
     120,   121,   122,   123,   124,   125,    -1,   127,   128,   129,
     130,   131,   132,   133,   134,   135,   136,   137,   138,   139,
     140,   141,   142,    10,    11,    12,    13,    14,    15,    16,
      17,    18,    19,    20,    21,    22,    23,    24,    25,    26,
      27,    28,    29,    30,    31,    32,    33,    34,    35,    36,
      37,    38,    39,    40,    41,    42,    43,    44,    45,    46,
      47,    48,    49,    50,    51,    52,    53,    54,    55,    56,
      57,    58,    59,    60,    61,    62,    63,    64,    65,    66,
      67,    68,    69,    70,    71,    72,    73,    74,    75,    76,
      77,    78,    79,    80,    81,    82,    83,    84,    85,    86,
      87,    88,    89,    90,    91,    92,    93,    94,    95,    96,
      97,    98,    99,    -1,    -1,    -1,    -1,    -1,   105,   106,
     107,   108,   109,   110,   111,   112,   113,   114,   115,   116,
     117,   118,   119,   120,   121,   122,   123,   124,   125,    -1,
     127,   128,   129,   130,   131,   132,   133,   134,   135,   136,
     137,   138,   139,   140,   141,   142,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,   327,    -1,   329,
     330,   331,   332,   333,   334,   335,   336,   337,   338,   339,
     340,   341,    10,    11,    12,    13,    14,    15,    16,    17,
      18,    19,    20,    21,    22,    23,    24,    25,    26,    27,
      28,    29,    30,    31,    32,    33,    34,    35,    36,    37,
      38,    39,    40,    41,    42,    43,    44,    45,    46,    47,
      48,    49,    50,    51,    52,    53,    54,    55,    56,    57,
      58,    59,    60,    61,    62,    63,    64,    65,    66,    67,
      68,    69,    70,    71,    72,    73,    74,    75,    76,    77,
      78,    79,    80,    81,    82,    83,    84,    85,    86,    87,
      88,    89,    90,    91,    92,    93,    94,    95,    96,    97,
      98,    99,    -1,    -1,    -1,    -1,   104,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,
     327,    -1,   329,   330,   331,   332,   333,   334,   335,   336,
     337,   338,   339,   340,   341,    10,    11,    12,    13,    14,
      15,    16,    17,    18,    19,    20,    21,    22,    23,    24,
      25,    26,    27,    28,    29,    30,    31,    32,    33,    34,
      35,    36,    37,    38,    39,    40,    41,    42,    43,    44,
      45,    46,    47,    48,    49,    50,    51,    52,    53,    54,
      55,    56,    57,    58,    59,    60,    61,    62,    63,    64,
      65,    66,    67,    68,    69,    70,    71,    72,    73,    74,
      75,    76,    77,    78,    79,    80,    81,    82,    83,    84,
      85,    86,    87,    88,    89,    90,    91,    92,    93,    94,
      95,    96,    97,    98,    99,    10,    11,    12,    13,    14,
      15,    16,    17,    18,    19,    20,    21,    22,    23,    24,
      25,    26,    27,    28,    29,    30,    31,    32,    33,    34,
      35,    36,    37,    38,    39,    40,    41,    42,    43,    44,
      45,    46,    47,    48,    49,    50,    51,    52,    53,    54,
      55,    56,    57,    58,    59,    60,    61,    62,    63,    64,
      65,    66,    67,    68,    69,    70,    71,    72,    73,    74,
      75,    76,    77,    78,    79,    80,    81,    82,    83,    84,
      85,    86,    87,    88,    89,    90,    91,    92,    93,    94,
      95,    96,    97,    98,    99,    -1,    -1,    -1,    -1,    -1,
      -1,   329,   330,   331,   332,   333,   334,   335,   336,   337,
     338,   339,   340,   341,    10,    11,    12,    13,    14,    15,
      16,    17,    18,    19,    20,    21,    22,    23,    24,    25,
      26,    27,    28,    29,    30,    31,    32,    33,    34,    35,
      36,    37,    38,    39,    40,    41,    42,    43,    44,    45,
      46,    47,    48,    49,    50,    51,    52,    53,    54,    55,
      56,    57,    58,    59,    60,    61,    62,    63,    64,    65,
      66,    67,    68,    69,    70,    71,    72,    73,    74,    75,
      76,    77,    78,    79,    80,    81,    82,    83,    84,    85,
      86,    87,    88,    89,    90,    91,    92,    93,    94,    95,
      96,    97,    98,    99,    -1,    -1,    -1,    -1,     0,    -1,
      -1,    -1,     4,     5,    -1,    -1,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,
      -1,    -1,   327,    -1,   329,   330,   331,   332,   333,   334,
     335,   336,   337,   338,   339,   340,   341,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,
      -1,    -1,   327,    -1,   329,   330,   331,   332,   333,   334,
     335,   336,   337,   338,   339,   340,   341,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,
      -1,   143,     0,    -1,    -1,    -1,     4,     5,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,   329,   330,   331,   332,   333,   334,   335,
     336,   337,   338,   339,   340,   341,   238,   239,   240,   241,
     242,   243,   244,   245,   246,   247,   248,   249,   250,   251,
     252,   253,   254,   255,   256,   257,   258,   259,   260,   261,
     262,   263,   264,   265,   266,   267,   268,   269,   270,   271,
     272,   273,   274,   275,   276,   277,   278,   279,   280,   281,
     282,   283,   284,   285,   286,   143,   288,   289,   290,   291,
     292,   293,   294,   295,   296,   297,   298,   299,   300,   301,
     302,   303,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,   315,   316,   317,   318,   319,   320,   321,
     322,   323,   324,   325,   326,    -1,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,
     238,   239,   240,   241,   242,   243,   244,   245,   246,   247,
     248,   249,   250,   251,   252,   253,   254,   255,   256,   257,
     258,   259,   260,   261,   262,   263,   264,   265,   266,   267,
     268,   269,   270,   271,   272,   273,   274,   275,   276,   277,
     278,   279,   280,   281,   282,   283,   284,   285,   286,   100,
     288,   289,   290,   291,   292,   293,   294,   295,   296,   297,
     298,   299,   300,   301,   302,   303,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,   315,   316,   317,
     318,   319,   320,   321,   322,   323,   324,   325,   326,    -1,
      -1,    -1,    -1,    -1,    -1,   146,   147,   148,   149,   150,
     151,   152,   153,   154,   155,   156,   157,   158,   159,   160,
     161,   162,   163,   164,   165,   166,   167,   168,   169,   170,
     171,   172,   173,   174,   175,   176,   177,   178,   179,   180,
     181,   182,   183,   184,   185,   186,   187,   188,   189,   190,
     191,   192,   193,   194,   195,   196,   197,   198,   199,   200,
     201,   202,   203,   204,   205,   206,   207,   208,   209,   210,
     211,   212,   213,   214,   215,   216,   217,   218,   219,   220,
     221,   222,   223,   224,   225,   226,   227,   228,   229,   230,
     231,   232,   233,   234,   235,   236,   237
  };

  const short
  seclang_parser::yystos_[] =
  {
       0,     0,     4,     5,   143,   238,   239,   240,   241,   242,
     243,   244,   245,   246,   247,   248,   249,   250,   251,   252,
     253,   254,   255,   256,   257,   258,   259,   260,   261,   262,
     263,   264,   265,   266,   267,   268,   269,   270,   271,   272,
     273,   274,   275,   276,   277,   278,   279,   280,   281,   282,
     283,   284,   285,   286,   288,   289,   290,   291,   292,   293,
     294,   295,   296,   297,   298,   299,   300,   301,   302,   303,
     315,   316,   317,   318,   319,   320,   321,   322,   323,   324,
     325,   326,   347,   348,   349,   354,   307,   308,   144,   145,
     307,   308,   307,   308,   312,   306,   309,   313,   307,   308,
     307,   308,   307,   308,   310,   311,   307,   308,   310,   311,
     307,   308,   305,   307,   308,   100,   146,   147,   148,   149,
     150,   151,   152,   153,   154,   155,   156,   157,   158,   159,
     160,   161,   162,   163,   164,   165,   166,   167,   168,   169,
     170,   171,   172,   173,   174,   175,   176,   177,   178,   179,
     180,   181,   182,   183,   184,   185,   186,   187,   188,   189,
     190,   191,   192,   193,   194,   195,   196,   197,   198,   199,
     200,   201,   202,   203,   204,   205,   206,   207,   208,   209,
     210,   211,   212,   213,   214,   215,   216,   217,   218,   219,
     220,   221,   222,   223,   224,   225,   226,   227,   228,   229,
     230,   231,   232,   233,   234,   235,   236,   237,   328,   350,
     351,   359,   350,   307,   308,   304,   314,     8,     9,    10,
      11,    12,    13,    14,    15,    16,    17,    18,    19,    20,
      21,    22,    23,    24,    25,    26,    27,    28,    29,    30,
      31,    32,    33,    34,    35,    36,    37,    38,    39,    40,
      41,    42,    43,    44,    45,    46,    47,    48,    49,    50,
      51,    52,    53,    54,    55,    56,    57,    58,    59,    60,
      61,    62,    63,    64,    65,    66,    67,    68,    69,    70,
      71,    72,    73,    74,    75,    76,    77,    78,    79,    80,
      81,    82,    83,    84,    85,    86,    87,    88,    89,    90,
      91,    92,    93,    94,    95,    96,    97,    98,    99,   328,
     329,   330,   331,   332,   333,   334,   335,   336,   337,   338,
     339,   340,   341,   356,   357,   358,   356,   356,   350,   307,
     308,   312,   307,   308,   307,   308,   355,   356,   350,     0,
     348,   104,   358,   360,   305,   307,   308,   307,   308,   312,
     307,   308,   307,   308,   327,   358,   361,   361,   361,   361,
     361,   361,   361,   361,   361,   351,     3,   358,   358,   343,
     345,   343,   345,   343,   345,   343,   345,   343,   345,   343,
     345,   343,   345,   343,   345,   343,   345,   343,   345,   343,
     345,   343,   345,   343,   345,   343,   345,   343,   345,   343,
     345,   343,   345,   343,   345,   343,   345,   343,   345,   343,
     345,   343,   345,   343,   345,   343,   345,   361,   343,   345,
     343,   345,   361,   343,   345,   361,   343,   345,   361,   343,
     345,   361,   343,   345,   361,   343,   345,   343,   345,   357,
       6,   104,   105,   106,   107,   108,   109,   110,   111,   112,
     113,   114,   115,   116,   117,   118,   119,   120,   121,   122,
     123,   124,   125,   127,   128,   129,   130,   131,   132,   133,
     134,   135,   136,   137,   138,   139,   140,   141,   142,   352,
     353,   361,   358,   101,   102,   103,   327,   358,   328,   359,
     328,     8,     9,   358,   353,   361,   361,   361,   361,   361,
     361,   361,   361,   361,   361,   361,   361,   361,   361,   361,
     361,   361,   361,   361,   361,   361,   361,   361,   361,   361,
     361,   361,   361,   361,   361,   361,   361,   350,   361,   361,
     361,   358,   358
  };

  const short
  seclang_parser::yyr1_[] =
  {
       0,   346,   347,   347,   347,   348,   349,   349,   349,   349,
     349,   349,   349,   349,   349,   349,   349,   349,   349,   349,
     349,   349,   349,   349,   349,   349,   349,   349,   349,   350,
     350,   351,   351,   352,   352,   352,   352,   353,   353,   353,
     353,   353,   353,   353,   353,   353,   353,   353,   353,   353,
     353,   353,   353,   353,   353,   353,   353,   353,   353,   353,
     353,   353,   353,   353,   353,   353,   353,   353,   353,   353,
     353,   353,   353,   353,   354,   354,   354,   354,   354,   354,
     354,   354,   354,   354,   354,   354,   354,   354,   354,   354,
     354,   354,   354,   354,   354,   354,   354,   354,   354,   354,
     354,   354,   354,   354,   354,   354,   354,   354,   354,   354,
     354,   354,   354,   354,   354,   354,   354,   354,   354,   354,
     354,   354,   354,   354,   354,   354,   354,   354,   354,   354,
     354,   354,   354,   354,   354,   354,   354,   354,   354,   354,
     354,   354,   354,   354,   354,   354,   354,   354,   354,   354,
     354,   354,   354,   354,   354,   355,   356,   356,   357,   357,
     357,   357,   357,   357,   358,   358,   358,   358,   358,   358,
     358,   358,   358,   358,   358,   358,   358,   358,   358,   358,
     358,   358,   358,   358,   358,   358,   358,   358,   358,   358,
     358,   358,   358,   358,   358,   358,   358,   358,   358,   358,
     358,   358,   358,   358,   358,   358,   358,   358,   358,   358,
     358,   358,   358,   358,   358,   358,   358,   358,   358,   358,
     358,   358,   358,   358,   358,   358,   358,   358,   358,   358,
     358,   358,   358,   358,   358,   358,   358,   358,   358,   358,
     358,   358,   358,   358,   358,   358,   358,   358,   358,   358,
     358,   358,   358,   358,   358,   358,   358,   358,   358,   358,
     358,   358,   358,   358,   358,   358,   358,   358,   358,   358,
     358,   358,   358,   358,   358,   358,   358,   358,   358,   358,
     358,   358,   358,   358,   358,   358,   358,   358,   358,   358,
     358,   358,   358,   358,   358,   358,   358,   358,   358,   358,
     358,   358,   358,   358,   358,   358,   358,   358,   358,   358,
     358,   358,   358,   358,   358,   358,   358,   358,   358,   358,
     358,   358,   358,   358,   358,   358,   358,   358,   358,   358,
     358,   358,   358,   358,   358,   358,   358,   359,   359,   359,
     359,   359,   359,   359,   359,   359,   359,   359,   359,   359,
     359,   359,   359,   359,   359,   359,   359,   359,   359,   359,
     359,   359,   359,   359,   359,   359,   359,   359,   359,   359,
     359,   359,   359,   359,   359,   359,   359,   359,   359,   359,
     359,   359,   359,   359,   359,   359,   359,   359,   359,   359,
     359,   359,   359,   359,   359,   359,   359,   359,   359,   359,
     359,   359,   359,   359,   359,   359,   359,   359,   359,   359,
     359,   359,   359,   359,   359,   359,   359,   359,   359,   359,
     359,   359,   359,   359,   359,   359,   359,   359,   359,   359,
     359,   359,   359,   359,   359,   359,   360,   360,   360,   360,
     360,   361,   361,   361,   361
  };

  const signed char
  seclang_parser::yyr2_[] =
  {
       0,     2,     1,     2,     1,     1,     1,     1,     2,     2,
       2,     1,     1,     1,     1,     2,     2,     1,     2,     2,
       2,     2,     2,     2,     1,     1,     1,     2,     2,     3,
       1,     3,     1,     1,     2,     1,     2,     1,     1,     1,
       1,     1,     2,     2,     2,     2,     2,     2,     2,     2,
       2,     2,     2,     2,     2,     2,     2,     2,     2,     2,
       2,     2,     2,     2,     2,     2,     2,     2,     2,     2,
       2,     2,     2,     1,     1,     4,     3,     2,     2,     2,
       1,     2,     2,     2,     2,     2,     2,     2,     1,     1,
       2,     2,     1,     1,     1,     2,     2,     2,     2,     1,
       2,     2,     1,     1,     1,     1,     1,     1,     2,     2,
       1,     1,     1,     2,     2,     1,     1,     1,     1,     1,
       1,     2,     2,     2,     2,     1,     1,     1,     1,     1,
       1,     1,     1,     1,     2,     2,     2,     2,     2,     2,
       1,     1,     1,     1,     2,     2,     1,     1,     1,     1,
       1,     1,     1,     1,     1,     1,     1,     3,     3,     4,
       4,     1,     2,     2,     2,     2,     1,     2,     2,     1,
       2,     2,     1,     2,     2,     1,     2,     2,     1,     2,
       2,     1,     2,     2,     1,     2,     2,     1,     2,     2,
       1,     2,     2,     1,     2,     2,     1,     2,     2,     1,
       2,     2,     1,     2,     2,     1,     2,     2,     1,     2,
       2,     1,     2,     2,     1,     2,     2,     1,     2,     2,
       1,     2,     2,     1,     2,     2,     1,     2,     2,     2,
       1,     2,     2,     2,     1,     2,     2,     2,     1,     2,
       2,     2,     1,     2,     2,     2,     1,     2,     2,     2,
       1,     2,     2,     1,     2,     2,     1,     2,     2,     1,
       2,     2,     1,     1,     2,     2,     1,     1,     1,     1,
       1,     1,     1,     1,     1,     1,     1,     1,     1,     1,
       1,     1,     1,     1,     1,     1,     1,     1,     1,     1,
       1,     1,     1,     1,     1,     1,     1,     1,     1,     1,
       1,     1,     1,     1,     1,     1,     1,     1,     1,     1,
       1,     1,     1,     1,     1,     1,     1,     1,     1,     1,
       1,     1,     1,     1,     1,     1,     1,     1,     1,     1,
       1,     1,     1,     1,     1,     1,     1,     1,     1,     1,
       1,     1,     1,     1,     2,     2,     2,     1,     1,     1,
       1,     2,     2,     2,     2,     2,     2,     2,     1,     1,
       1,     1,     1,     1,     1,     1,     1,     1,     2,     2,
       1,     1,     2,     1,     1,     1,     1,     1,     1,     1,
       1,     2,     1,     1,     1,     1,     1,     1,     2,     2,
       2,     2,     2,     1,     1,     1,     1,     2,     1,     1,
       1,     1,     1,     1,     1,     1,     1,     1,     1,     1,
       1,     1,     1,     1,     1,     1,     1,     1,     1,     1,
       1,     1,     1,     1,     1,     1,     1,     1,     1,     1,
       1,     1,     1,     1,     1,     1,     2,     1,     3,     3,
       3,     2,     2,     1,     1
  };


#if YYDEBUG || 1
  // YYTNAME[SYMBOL-NUM] -- String name of the symbol SYMBOL-NUM.
  // First, the terminals, then, starting at \a YYNTOKENS, nonterminals.
  const char*
  const seclang_parser::yytname_[] =
  {
  "\"end of file\"", "error", "\"invalid token\"", "\",\"",
  "\"CONFIG_CONTENT_INJECTION\"", "\"CONGIG_DIR_RESPONSE_BODY_MP_CLEAR\"",
  "PIPE", "NEW_LINE", "VAR_COUNT", "VAR_EXCLUSION", "VARIABLE_ARGS",
  "VARIABLE_ARGS_POST", "VARIABLE_ARGS_GET", "VARIABLE_FILES_SIZES",
  "VARIABLE_FILES_NAMES", "VARIABLE_FILES_TMP_CONTENT",
  "VARIABLE_MULTIPART_FILENAME", "VARIABLE_MULTIPART_NAME",
  "VARIABLE_MATCHED_VARS_NAMES", "VARIABLE_MATCHED_VARS", "VARIABLE_FILES",
  "VARIABLE_REQUEST_COOKIES", "VARIABLE_REQUEST_HEADERS",
  "VARIABLE_RESPONSE_HEADERS", "VARIABLE_GEO",
  "VARIABLE_REQUEST_COOKIES_NAMES", "VARIABLE_MULTIPART_PART_HEADERS",
  "VARIABLE_ARGS_COMBINED_SIZE", "VARIABLE_ARGS_GET_NAMES",
  "VARIABLE_RULE", "\"Variable ARGS_NAMES\"", "VARIABLE_ARGS_POST_NAMES",
  "\"AUTH_TYPE\"", "\"FILES_COMBINED_SIZE\"", "\"FILES_TMPNAMES\"",
  "\"FULL_REQUEST\"", "\"FULL_REQUEST_LENGTH\"", "\"INBOUND_DATA_ERROR\"",
  "\"MATCHED_VAR\"", "\"MATCHED_VAR_NAME\"",
  "VARIABLE_MULTIPART_BOUNDARY_QUOTED",
  "VARIABLE_MULTIPART_BOUNDARY_WHITESPACE", "\"MULTIPART_CRLF_LF_LINES\"",
  "\"MULTIPART_DATA_AFTER\"", "VARIABLE_MULTIPART_DATA_BEFORE",
  "\"MULTIPART_FILE_LIMIT_EXCEEDED\"", "\"MULTIPART_HEADER_FOLDING\"",
  "\"MULTIPART_INVALID_HEADER_FOLDING\"",
  "VARIABLE_MULTIPART_INVALID_PART", "\"MULTIPART_INVALID_QUOTING\"",
  "VARIABLE_MULTIPART_LF_LINE", "VARIABLE_MULTIPART_MISSING_SEMICOLON",
  "VARIABLE_MULTIPART_SEMICOLON_MISSING", "\"MULTIPART_STRICT_ERROR\"",
  "\"MULTIPART_UNMATCHED_BOUNDARY\"", "\"OUTBOUND_DATA_ERROR\"",
  "\"PATH_INFO\"", "\"QUERY_STRING\"", "\"REMOTE_ADDR\"",
  "\"REMOTE_HOST\"", "\"REMOTE_PORT\"", "\"REQBODY_ERROR_MSG\"",
  "\"REQBODY_ERROR\"", "\"REQBODY_PROCESSOR_ERROR_MSG\"",
  "\"REQBODY_PROCESSOR_ERROR\"", "\"REQBODY_PROCESSOR\"",
  "\"REQUEST_BASENAME\"", "\"REQUEST_BODY_LENGTH\"", "\"REQUEST_BODY\"",
  "\"REQUEST_FILENAME\"", "VARIABLE_REQUEST_HEADERS_NAMES",
  "\"REQUEST_LINE\"", "\"REQUEST_METHOD\"", "\"REQUEST_PROTOCOL\"",
  "\"REQUEST_URI_RAW\"", "\"REQUEST_URI\"", "\"RESOURCE\"",
  "\"RESPONSE_BODY\"", "\"RESPONSE_CONTENT_LENGTH\"",
  "VARIABLE_RESPONSE_CONTENT_TYPE", "VARIABLE_RESPONSE_HEADERS_NAMES",
  "\"RESPONSE_PROTOCOL\"", "\"RESPONSE_STATUS\"", "\"SERVER_ADDR\"",
  "\"SERVER_NAME\"", "\"SERVER_PORT\"", "\"SESSIONID\"", "\"UNIQUE_ID\"",
  "\"URLENCODED_ERROR\"", "\"USERID\"", "\"WEBAPPID\"",
  "\"VARIABLE_STATUS\"", "\"VARIABLE_STATUS_LINE\"", "\"VARIABLE_IP\"",
  "\"VARIABLE_GLOBAL\"", "\"VARIABLE_TX\"", "\"VARIABLE_SESSION\"",
  "\"VARIABLE_USER\"", "\"RUN_TIME_VAR_ENV\"", "\"RUN_TIME_VAR_XML\"",
  "\"SetVar\"", "SETVAR_OPERATION_EQUALS", "SETVAR_OPERATION_EQUALS_PLUS",
  "SETVAR_OPERATION_EQUALS_MINUS", "\"NOT\"", "\"OPERATOR_BEGINS_WITH\"",
  "\"OPERATOR_CONTAINS\"", "\"OPERATOR_CONTAINS_WORD\"",
  "\"OPERATOR_DETECT_SQLI\"", "\"OPERATOR_DETECT_XSS\"",
  "\"OPERATOR_ENDS_WITH\"", "\"OPERATOR_EQ\"", "\"OPERATOR_FUZZY_HASH\"",
  "\"OPERATOR_GEOLOOKUP\"", "\"OPERATOR_GE\"", "\"OPERATOR_GSB_LOOKUP\"",
  "\"OPERATOR_GT\"", "\"OPERATOR_INSPECT_FILE\"",
  "\"OPERATOR_IP_MATCH_FROM_FILE\"", "\"OPERATOR_IP_MATCH\"",
  "\"OPERATOR_LE\"", "\"OPERATOR_LT\"", "\"OPERATOR_PM_FROM_FILE\"",
  "\"OPERATOR_PM\"", "\"OPERATOR_RBL\"", "\"OPERATOR_RSUB\"",
  "\"Operator RX (content only)\"", "\"OPERATOR_RX\"",
  "\"OPERATOR_RX_GLOBAL\"", "\"OPERATOR_STR_EQ\"",
  "\"OPERATOR_STR_MATCH\"", "\"OPERATOR_UNCONDITIONAL_MATCH\"",
  "\"OPERATOR_VALIDATE_BYTE_RANGE\"", "\"OPERATOR_VALIDATE_DTD\"",
  "\"OPERATOR_VALIDATE_HASH\"", "\"OPERATOR_VALIDATE_SCHEMA\"",
  "\"OPERATOR_VALIDATE_URL_ENCODING\"",
  "\"OPERATOR_VALIDATE_UTF8_ENCODING\"", "\"OPERATOR_VERIFY_CC\"",
  "\"OPERATOR_VERIFY_CPF\"", "\"OPERATOR_VERIFY_SSN\"",
  "\"OPERATOR_VERIFY_SVNR\"", "\"OPERATOR_WITHIN\"",
  "CONFIG_DIR_AUDIT_LOG_FMT", "JSON", "NATIVE",
  "\"ACTION_CTL_RULE_ENGINE\"", "\"Accuracy\"", "\"Allow\"", "\"Append\"",
  "\"AuditLog\"", "\"Block\"", "\"Capture\"", "\"Chain\"",
  "\"ACTION_CTL_AUDIT_ENGINE\"", "\"ACTION_CTL_AUDIT_LOG_PARTS\"",
  "\"ACTION_CTL_BDY_JSON\"", "\"ACTION_CTL_BDY_XML\"",
  "\"ACTION_CTL_BDY_URLENCODED\"", "\"ACTION_CTL_FORCE_REQ_BODY_VAR\"",
  "\"ACTION_CTL_REQUEST_BODY_ACCESS\"", "\"ACTION_CTL_RULE_REMOVE_BY_ID\"",
  "\"ACTION_CTL_RULE_REMOVE_BY_TAG\"",
  "\"ACTION_CTL_RULE_REMOVE_TARGET_BY_ID\"",
  "\"ACTION_CTL_RULE_REMOVE_TARGET_BY_TAG\"", "\"Deny\"",
  "\"DeprecateVar\"", "\"Drop\"", "\"Exec\"", "\"ExpireVar\"", "\"Id\"",
  "\"InitCol\"", "\"Log\"", "\"LogData\"", "\"Maturity\"", "\"Msg\"",
  "\"MultiMatch\"", "\"NoAuditLog\"", "\"NoLog\"", "\"Pass\"", "\"Pause\"",
  "\"Phase\"", "\"Prepend\"", "\"Proxy\"", "\"Redirect\"", "\"Rev\"",
  "\"SanitiseArg\"", "\"SanitiseMatched\"", "\"SanitiseMatchedBytes\"",
  "\"SanitiseRequestHeader\"", "\"SanitiseResponseHeader\"", "\"SetEnv\"",
  "\"SetRsc\"", "\"SetSid\"", "\"SetUID\"", "\"Severity\"", "\"Skip\"",
  "\"SkipAfter\"", "\"Status\"", "\"Tag\"",
  "\"ACTION_TRANSFORMATION_BASE_64_ENCODE\"",
  "\"ACTION_TRANSFORMATION_BASE_64_DECODE\"",
  "\"ACTION_TRANSFORMATION_BASE_64_DECODE_EXT\"",
  "\"ACTION_TRANSFORMATION_CMD_LINE\"",
  "\"ACTION_TRANSFORMATION_COMPRESS_WHITESPACE\"",
  "\"ACTION_TRANSFORMATION_CSS_DECODE\"",
  "\"ACTION_TRANSFORMATION_ESCAPE_SEQ_DECODE\"",
  "\"ACTION_TRANSFORMATION_HEX_ENCODE\"",
  "\"ACTION_TRANSFORMATION_HEX_DECODE\"",
  "\"ACTION_TRANSFORMATION_HTML_ENTITY_DECODE\"",
  "\"ACTION_TRANSFORMATION_JS_DECODE\"",
  "\"ACTION_TRANSFORMATION_LENGTH\"",
  "\"ACTION_TRANSFORMATION_LOWERCASE\"", "\"ACTION_TRANSFORMATION_MD5\"",
  "\"ACTION_TRANSFORMATION_NONE\"",
  "\"ACTION_TRANSFORMATION_NORMALISE_PATH\"",
  "\"ACTION_TRANSFORMATION_NORMALISE_PATH_WIN\"",
  "\"ACTION_TRANSFORMATION_PARITY_EVEN_7_BIT\"",
  "\"ACTION_TRANSFORMATION_PARITY_ODD_7_BIT\"",
  "\"ACTION_TRANSFORMATION_PARITY_ZERO_7_BIT\"",
  "\"ACTION_TRANSFORMATION_REMOVE_COMMENTS\"",
  "\"ACTION_TRANSFORMATION_REMOVE_COMMENTS_CHAR\"",
  "\"ACTION_TRANSFORMATION_REMOVE_NULLS\"",
  "\"ACTION_TRANSFORMATION_REMOVE_WHITESPACE\"",
  "\"ACTION_TRANSFORMATION_REPLACE_COMMENTS\"",
  "\"ACTION_TRANSFORMATION_REPLACE_NULLS\"",
  "\"ACTION_TRANSFORMATION_SHA1\"",
  "\"ACTION_TRANSFORMATION_SQL_HEX_DECODE\"",
  "\"ACTION_TRANSFORMATION_TRIM\"", "\"ACTION_TRANSFORMATION_TRIM_LEFT\"",
  "\"ACTION_TRANSFORMATION_TRIM_RIGHT\"",
  "\"ACTION_TRANSFORMATION_UPPERCASE\"",
  "\"ACTION_TRANSFORMATION_URL_ENCODE\"",
  "\"ACTION_TRANSFORMATION_URL_DECODE\"",
  "\"ACTION_TRANSFORMATION_URL_DECODE_UNI\"",
  "\"ACTION_TRANSFORMATION_UTF8_TO_UNICODE\"", "\"Ver\"", "\"xmlns\"",
  "\"CONFIG_COMPONENT_SIG\"", "\"CONFIG_CONN_ENGINE\"",
  "\"CONFIG_SEC_ARGUMENT_SEPARATOR\"", "\"CONFIG_SEC_WEB_APP_ID\"",
  "\"CONFIG_SEC_SERVER_SIG\"", "\"CONFIG_DIR_AUDIT_DIR\"",
  "\"CONFIG_DIR_AUDIT_DIR_MOD\"", "\"CONFIG_DIR_AUDIT_ENG\"",
  "\"CONFIG_DIR_AUDIT_FLE_MOD\"", "\"CONFIG_DIR_AUDIT_LOG\"",
  "\"CONFIG_DIR_AUDIT_LOG2\"", "\"CONFIG_DIR_AUDIT_LOG_P\"",
  "\"CONFIG_DIR_AUDIT_STS\"", "\"CONFIG_DIR_AUDIT_TPE\"",
  "\"CONFIG_DIR_DEBUG_LOG\"", "\"CONFIG_DIR_DEBUG_LVL\"",
  "\"CONFIG_SEC_CACHE_TRANSFORMATIONS\"",
  "\"CONFIG_SEC_DISABLE_BACKEND_COMPRESS\"", "\"CONFIG_SEC_HASH_ENGINE\"",
  "\"CONFIG_SEC_HASH_KEY\"", "\"CONFIG_SEC_HASH_PARAM\"",
  "\"CONFIG_SEC_HASH_METHOD_RX\"", "\"CONFIG_SEC_HASH_METHOD_PM\"",
  "\"CONFIG_SEC_CHROOT_DIR\"", "\"CONFIG_DIR_GEO_DB\"",
  "\"CONFIG_DIR_GSB_DB\"", "\"CONFIG_SEC_GUARDIAN_LOG\"",
  "\"CONFIG_DIR_PCRE_MATCH_LIMIT\"",
  "\"CONFIG_DIR_PCRE_MATCH_LIMIT_RECURSION\"",
  "\"CONFIG_SEC_CONN_R_STATE_LIMIT\"", "\"CONFIG_SEC_CONN_W_STATE_LIMIT\"",
  "\"CONFIG_SEC_SENSOR_ID\"", "\"CONFIG_DIR_ARGS_LIMIT\"",
  "\"CONFIG_DIR_REQ_BODY_JSON_DEPTH_LIMIT\"", "\"CONFIG_DIR_REQ_BODY\"",
  "\"CONFIG_DIR_REQ_BODY_IN_MEMORY_LIMIT\"",
  "\"CONFIG_DIR_REQ_BODY_LIMIT\"", "\"CONFIG_DIR_REQ_BODY_LIMIT_ACTION\"",
  "\"CONFIG_DIR_REQ_BODY_NO_FILES_LIMIT\"", "\"CONFIG_DIR_RES_BODY\"",
  "\"CONFIG_DIR_RES_BODY_LIMIT\"", "\"CONFIG_DIR_RES_BODY_LIMIT_ACTION\"",
  "\"CONFIG_SEC_RULE_INHERITANCE\"", "\"CONFIG_SEC_RULE_PERF_TIME\"",
  "\"CONFIG_DIR_RULE_ENG\"", "\"CONFIG_DIR_SEC_ACTION\"",
  "\"CONFIG_DIR_SEC_DEFAULT_ACTION\"", "\"CONFIG_DIR_SEC_MARKER\"",
  "\"CONFIG_DIR_UNICODE_MAP_FILE\"", "\"CONFIG_DIR_UNICODE_CODE_PAGE\"",
  "\"CONFIG_SEC_COLLECTION_TIMEOUT\"", "\"CONFIG_SEC_HTTP_BLKEY\"",
  "\"CONFIG_SEC_INTERCEPT_ON_ERROR\"",
  "\"CONFIG_SEC_REMOTE_RULES_FAIL_ACTION\"",
  "\"CONFIG_SEC_RULE_REMOVE_BY_ID\"", "\"CONFIG_SEC_RULE_REMOVE_BY_MSG\"",
  "\"CONFIG_SEC_RULE_REMOVE_BY_TAG\"",
  "\"CONFIG_SEC_RULE_UPDATE_TARGET_BY_TAG\"",
  "\"CONFIG_SEC_RULE_UPDATE_TARGET_BY_MSG\"",
  "\"CONFIG_SEC_RULE_UPDATE_TARGET_BY_ID\"",
  "\"CONFIG_SEC_RULE_UPDATE_ACTION_BY_ID\"",
  "\"CONFIG_UPDLOAD_KEEP_FILES\"", "\"CONFIG_UPDLOAD_SAVE_TMP_FILES\"",
  "\"CONFIG_UPLOAD_DIR\"", "\"CONFIG_UPLOAD_FILE_LIMIT\"",
  "\"CONFIG_UPLOAD_FILE_MODE\"", "\"CONFIG_VALUE_ABORT\"",
  "\"CONFIG_VALUE_DETC\"", "\"CONFIG_VALUE_HTTPS\"",
  "\"CONFIG_VALUE_OFF\"", "\"CONFIG_VALUE_ON\"",
  "\"CONFIG_VALUE_PARALLEL\"", "\"CONFIG_VALUE_PROCESS_PARTIAL\"",
  "\"CONFIG_VALUE_REJECT\"", "\"CONFIG_VALUE_RELEVANT_ONLY\"",
  "\"CONFIG_VALUE_SERIAL\"", "\"CONFIG_VALUE_WARN\"",
  "\"CONFIG_XML_EXTERNAL_ENTITY\"", "\"CONGIG_DIR_RESPONSE_BODY_MP\"",
  "\"CONGIG_DIR_SEC_ARG_SEP\"", "\"CONGIG_DIR_SEC_COOKIE_FORMAT\"",
  "\"CONFIG_SEC_COOKIEV0_SEPARATOR\"", "\"CONGIG_DIR_SEC_DATA_DIR\"",
  "\"CONGIG_DIR_SEC_STATUS_ENGINE\"",
  "\"CONFIG_SEC_STREAM_IN_BODY_INSPECTION\"",
  "\"CONFIG_SEC_STREAM_OUT_BODY_INSPECTION\"",
  "\"CONGIG_DIR_SEC_TMP_DIR\"", "\"DIRECTIVE\"",
  "\"DIRECTIVE_SECRULESCRIPT\"", "\"FREE_TEXT_QUOTE_MACRO_EXPANSION\"",
  "\"QUOTATION_MARK\"", "\"RUN_TIME_VAR_BLD\"", "\"RUN_TIME_VAR_DUR\"",
  "\"RUN_TIME_VAR_HSV\"", "\"RUN_TIME_VAR_REMOTE_USER\"",
  "\"RUN_TIME_VAR_TIME\"", "\"RUN_TIME_VAR_TIME_DAY\"",
  "\"RUN_TIME_VAR_TIME_EPOCH\"", "\"RUN_TIME_VAR_TIME_HOUR\"",
  "\"RUN_TIME_VAR_TIME_MIN\"", "\"RUN_TIME_VAR_TIME_MON\"",
  "\"RUN_TIME_VAR_TIME_SEC\"", "\"RUN_TIME_VAR_TIME_WDAY\"",
  "\"RUN_TIME_VAR_TIME_YEAR\"", "\"VARIABLE\"", "\"Dictionary element\"",
  "\"Dictionary element, with equals\"",
  "\"Dictionary element, selected by regexp\"", "$accept", "input", "line",
  "audit_log", "actions", "actions_may_quoted", "op", "op_before_init",
  "expression", "variables", "variables_pre_process",
  "variables_may_be_quoted", "var", "act", "setvar_action",
  "run_time_string", YY_NULLPTR
  };
#endif


#if YYDEBUG
  const short
  seclang_parser::yyrline_[] =
  {
       0,   716,   716,   720,   721,   724,   729,   735,   741,   745,
     749,   755,   761,   767,   773,   778,   783,   789,   796,   800,
     804,   810,   814,   818,   823,   828,   833,   838,   842,   849,
     853,   860,   866,   876,   885,   895,   904,   917,   921,   925,
     929,   933,   937,   941,   945,   949,   953,   958,   962,   966,
     970,   974,   978,   983,   988,   992,   996,  1000,  1004,  1008,
    1012,  1016,  1020,  1024,  1028,  1032,  1036,  1040,  1044,  1048,
    1052,  1056,  1060,  1064,  1078,  1079,  1109,  1128,  1147,  1175,
    1232,  1239,  1243,  1247,  1251,  1255,  1259,  1263,  1267,  1276,
    1280,  1285,  1288,  1293,  1298,  1303,  1308,  1311,  1316,  1319,
    1324,  1329,  1332,  1337,  1342,  1347,  1352,  1357,  1362,  1367,
    1370,  1375,  1380,  1385,  1390,  1393,  1398,  1403,  1408,  1421,
    1434,  1447,  1460,  1473,  1499,  1527,  1539,  1559,  1586,  1591,
    1597,  1602,  1607,  1616,  1621,  1625,  1629,  1633,  1637,  1641,
    1645,  1650,  1655,  1667,  1673,  1677,  1681,  1692,  1701,  1702,
    1709,  1714,  1719,  1773,  1780,  1788,  1825,  1829,  1836,  1841,
    1847,  1853,  1859,  1866,  1876,  1880,  1884,  1888,  1892,  1896,
    1900,  1904,  1908,  1912,  1916,  1920,  1924,  1928,  1932,  1936,
    1940,  1944,  1948,  1952,  1956,  1960,  1964,  1968,  1972,  1976,
    1980,  1984,  1988,  1992,  1996,  2000,  2004,  2008,  2012,  2016,
    2020,  2024,  2028,  2032,  2036,  2040,  2044,  2048,  2052,  2056,
    2060,  2064,  2068,  2072,  2076,  2080,  2084,  2088,  2092,  2096,
    2100,  2104,  2108,  2112,  2116,  2120,  2124,  2128,  2132,  2136,
    2140,  2144,  2148,  2152,  2156,  2160,  2164,  2168,  2172,  2176,
    2180,  2184,  2188,  2192,  2196,  2200,  2204,  2208,  2212,  2216,
    2220,  2224,  2228,  2232,  2236,  2240,  2244,  2249,  2253,  2257,
    2262,  2266,  2270,  2275,  2280,  2284,  2288,  2292,  2296,  2300,
    2304,  2308,  2312,  2316,  2320,  2324,  2328,  2332,  2336,  2340,
    2344,  2348,  2352,  2356,  2360,  2364,  2368,  2372,  2376,  2380,
    2384,  2388,  2392,  2396,  2400,  2404,  2408,  2412,  2416,  2420,
    2424,  2428,  2432,  2436,  2440,  2444,  2448,  2452,  2456,  2460,
    2464,  2468,  2472,  2476,  2480,  2484,  2488,  2492,  2496,  2500,
    2504,  2508,  2512,  2516,  2520,  2528,  2535,  2542,  2549,  2556,
    2563,  2570,  2577,  2584,  2591,  2598,  2605,  2615,  2619,  2623,
    2627,  2631,  2635,  2639,  2643,  2648,  2652,  2657,  2661,  2665,
    2669,  2673,  2678,  2683,  2687,  2691,  2695,  2699,  2703,  2707,
    2711,  2715,  2719,  2723,  2727,  2731,  2735,  2740,  2744,  2748,
    2752,  2756,  2760,  2764,  2768,  2772,  2776,  2780,  2784,  2788,
    2792,  2796,  2800,  2804,  2808,  2812,  2816,  2820,  2824,  2828,
    2832,  2836,  2840,  2844,  2848,  2852,  2856,  2860,  2864,  2868,
    2872,  2876,  2880,  2884,  2888,  2892,  2896,  2900,  2904,  2908,
    2912,  2916,  2920,  2924,  2928,  2932,  2936,  2940,  2944,  2948,
    2952,  2956,  2960,  2964,  2968,  2972,  2976,  2980,  2984,  2988,
    2992,  2996,  3000,  3004,  3008,  3012,  3019,  3023,  3027,  3031,
    3035,  3042,  3047,  3052,  3058
  };

  void
  seclang_parser::yy_stack_print_ () const
  {
    *yycdebug_ << "Stack now";
    for (stack_type::const_iterator
           i = yystack_.begin (),
           i_end = yystack_.end ();
         i != i_end; ++i)
      *yycdebug_ << ' ' << int (i->state);
    *yycdebug_ << '\n';
  }

  void
  seclang_parser::yy_reduce_print_ (int yyrule) const
  {
    int yylno = yyrline_[yyrule];
    int yynrhs = yyr2_[yyrule];
    // Print the symbols being reduced, and their result.
    *yycdebug_ << "Reducing stack by rule " << yyrule - 1
               << " (line " << yylno << "):\n";
    // The symbols being reduced.
    for (int yyi = 0; yyi < yynrhs; yyi++)
      YY_SYMBOL_PRINT ("   $" << yyi + 1 << " =",
                       yystack_[(yynrhs) - (yyi + 1)]);
  }
#endif // YYDEBUG


} // yy
#line 7276 "seclang-parser.cc"

#line 3065 "seclang-parser.yy"


void yy::seclang_parser::error (const location_type& l, const std::string& m) {
    driver.error (l, m);
}
