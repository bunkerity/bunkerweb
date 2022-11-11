// A Bison parser, made by GNU Bison 3.3.2.

// Skeleton implementation for Bison LALR(1) parsers in C++

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

// Undocumented macros, especially those whose name start with YY_,
// are private implementation details.  Do not rely on them.





#include "seclang-parser.hh"


// Unqualified %code blocks.
#line 324 "seclang-parser.yy" // lalr1.cc:435

#include "src/parser/driver.h"

#line 49 "seclang-parser.cc" // lalr1.cc:435


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


// Suppress unused-variable warnings by "using" E.
#define YYUSE(E) ((void) (E))

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
      yystack_print_ ();                \
  } while (false)

#else // !YYDEBUG

# define YYCDEBUG if (false) std::cerr
# define YY_SYMBOL_PRINT(Title, Symbol)  YYUSE (Symbol)
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
#line 144 "seclang-parser.cc" // lalr1.cc:510

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


  /// Build a parser object.
  seclang_parser::seclang_parser (modsecurity::Parser::Driver& driver_yyarg)
    :
#if YYDEBUG
      yydebug_ (false),
      yycdebug_ (&std::cerr),
#endif
      driver (driver_yyarg)
  {}

  seclang_parser::~seclang_parser ()
  {}

  seclang_parser::syntax_error::~syntax_error () YY_NOEXCEPT YY_NOTHROW
  {}

  /*---------------.
  | Symbol types.  |
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

  seclang_parser::symbol_number_type
  seclang_parser::by_state::type_get () const YY_NOEXCEPT
  {
    if (state == empty_state)
      return empty_symbol;
    else
      return yystos_[state];
  }

  seclang_parser::stack_symbol_type::stack_symbol_type ()
  {}

  seclang_parser::stack_symbol_type::stack_symbol_type (YY_RVREF (stack_symbol_type) that)
    : super_type (YY_MOVE (that.state), YY_MOVE (that.location))
  {
    switch (that.type_get ())
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
        value.YY_MOVE_OR_COPY< std::string > (YY_MOVE (that.value));
        break;

      case 347: // op
      case 348: // op_before_init
        value.YY_MOVE_OR_COPY< std::unique_ptr<Operator> > (YY_MOVE (that.value));
        break;

      case 356: // run_time_string
        value.YY_MOVE_OR_COPY< std::unique_ptr<RunTimeString> > (YY_MOVE (that.value));
        break;

      case 353: // var
        value.YY_MOVE_OR_COPY< std::unique_ptr<Variable> > (YY_MOVE (that.value));
        break;

      case 354: // act
      case 355: // setvar_action
        value.YY_MOVE_OR_COPY< std::unique_ptr<actions::Action> > (YY_MOVE (that.value));
        break;

      case 350: // variables
      case 351: // variables_pre_process
      case 352: // variables_may_be_quoted
        value.YY_MOVE_OR_COPY< std::unique_ptr<std::vector<std::unique_ptr<Variable> > >  > (YY_MOVE (that.value));
        break;

      case 345: // actions
      case 346: // actions_may_quoted
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
    switch (that.type_get ())
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
        value.move< std::string > (YY_MOVE (that.value));
        break;

      case 347: // op
      case 348: // op_before_init
        value.move< std::unique_ptr<Operator> > (YY_MOVE (that.value));
        break;

      case 356: // run_time_string
        value.move< std::unique_ptr<RunTimeString> > (YY_MOVE (that.value));
        break;

      case 353: // var
        value.move< std::unique_ptr<Variable> > (YY_MOVE (that.value));
        break;

      case 354: // act
      case 355: // setvar_action
        value.move< std::unique_ptr<actions::Action> > (YY_MOVE (that.value));
        break;

      case 350: // variables
      case 351: // variables_pre_process
      case 352: // variables_may_be_quoted
        value.move< std::unique_ptr<std::vector<std::unique_ptr<Variable> > >  > (YY_MOVE (that.value));
        break;

      case 345: // actions
      case 346: // actions_may_quoted
        value.move< std::unique_ptr<std::vector<std::unique_ptr<actions::Action> > >  > (YY_MOVE (that.value));
        break;

      default:
        break;
    }

    // that is emptied.
    that.type = empty_symbol;
  }

#if YY_CPLUSPLUS < 201103L
  seclang_parser::stack_symbol_type&
  seclang_parser::stack_symbol_type::operator= (stack_symbol_type& that)
  {
    state = that.state;
    switch (that.type_get ())
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
        value.move< std::string > (that.value);
        break;

      case 347: // op
      case 348: // op_before_init
        value.move< std::unique_ptr<Operator> > (that.value);
        break;

      case 356: // run_time_string
        value.move< std::unique_ptr<RunTimeString> > (that.value);
        break;

      case 353: // var
        value.move< std::unique_ptr<Variable> > (that.value);
        break;

      case 354: // act
      case 355: // setvar_action
        value.move< std::unique_ptr<actions::Action> > (that.value);
        break;

      case 350: // variables
      case 351: // variables_pre_process
      case 352: // variables_may_be_quoted
        value.move< std::unique_ptr<std::vector<std::unique_ptr<Variable> > >  > (that.value);
        break;

      case 345: // actions
      case 346: // actions_may_quoted
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
  seclang_parser::yy_print_ (std::ostream& yyo,
                                     const basic_symbol<Base>& yysym) const
  {
    std::ostream& yyoutput = yyo;
    YYUSE (yyoutput);
    symbol_number_type yytype = yysym.type_get ();
#if defined __GNUC__ && ! defined __clang__ && ! defined __ICC && __GNUC__ * 100 + __GNUC_MINOR__ <= 408
    // Avoid a (spurious) G++ 4.8 warning about "array subscript is
    // below array bounds".
    if (yysym.empty ())
      std::abort ();
#endif
    yyo << (yytype < yyntokens_ ? "token" : "nterm")
        << ' ' << yytname_[yytype] << " ("
        << yysym.location << ": ";
    YYUSE (yytype);
    yyo << ')';
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
    int yyr = yypgoto_[yysym - yyntokens_] + yystate;
    if (0 <= yyr && yyr <= yylast_ && yycheck_[yyr] == yystate)
      return yytable_[yyr];
    else
      return yydefgoto_[yysym - yyntokens_];
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
    // State.
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
#line 317 "seclang-parser.yy" // lalr1.cc:788
{
  // Initialize the initial location.
  yyla.location.begin.filename = yyla.location.end.filename = new std::string(driver.file);
}

#line 1123 "seclang-parser.cc" // lalr1.cc:788

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
    YYCDEBUG << "Entering state " << yystack_[0].state << '\n';

    // Accept?
    if (yystack_[0].state == yyfinal_)
      YYACCEPT;

    goto yybackup;


  /*-----------.
  | yybackup.  |
  `-----------*/
  yybackup:
    // Try to take a decision without lookahead.
    yyn = yypact_[yystack_[0].state];
    if (yy_pact_value_is_default_ (yyn))
      goto yydefault;

    // Read a lookahead token.
    if (yyla.empty ())
      {
        YYCDEBUG << "Reading a token: ";
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

    /* If the proper action on seeing token YYLA.TYPE is to reduce or
       to detect an error, take that action.  */
    yyn += yyla.type_get ();
    if (yyn < 0 || yylast_ < yyn || yycheck_[yyn] != yyla.type_get ())
      goto yydefault;

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
    yypush_ ("Shifting", yyn, YY_MOVE (yyla));
    goto yynewstate;


  /*-----------------------------------------------------------.
  | yydefault -- do the default action for the current state.  |
  `-----------------------------------------------------------*/
  yydefault:
    yyn = yydefact_[yystack_[0].state];
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
        yylhs.value.emplace< std::string > ();
        break;

      case 347: // op
      case 348: // op_before_init
        yylhs.value.emplace< std::unique_ptr<Operator> > ();
        break;

      case 356: // run_time_string
        yylhs.value.emplace< std::unique_ptr<RunTimeString> > ();
        break;

      case 353: // var
        yylhs.value.emplace< std::unique_ptr<Variable> > ();
        break;

      case 354: // act
      case 355: // setvar_action
        yylhs.value.emplace< std::unique_ptr<actions::Action> > ();
        break;

      case 350: // variables
      case 351: // variables_pre_process
      case 352: // variables_may_be_quoted
        yylhs.value.emplace< std::unique_ptr<std::vector<std::unique_ptr<Variable> > >  > ();
        break;

      case 345: // actions
      case 346: // actions_may_quoted
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
  case 2:
#line 708 "seclang-parser.yy" // lalr1.cc:919
    {
        return 0;
      }
#line 1477 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 6:
#line 721 "seclang-parser.yy" // lalr1.cc:919
    {
        driver.m_auditLog->setStorageDirMode(strtol(yystack_[0].value.as < std::string > ().c_str(), NULL, 8));
      }
#line 1485 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 7:
#line 727 "seclang-parser.yy" // lalr1.cc:919
    {
        driver.m_auditLog->setStorageDir(yystack_[0].value.as < std::string > ());
      }
#line 1493 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 8:
#line 733 "seclang-parser.yy" // lalr1.cc:919
    {
        driver.m_auditLog->setStatus(modsecurity::audit_log::AuditLog::RelevantOnlyAuditLogStatus);
      }
#line 1501 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 9:
#line 737 "seclang-parser.yy" // lalr1.cc:919
    {
        driver.m_auditLog->setStatus(modsecurity::audit_log::AuditLog::OffAuditLogStatus);
      }
#line 1509 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 10:
#line 741 "seclang-parser.yy" // lalr1.cc:919
    {
        driver.m_auditLog->setStatus(modsecurity::audit_log::AuditLog::OnAuditLogStatus);
      }
#line 1517 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 11:
#line 747 "seclang-parser.yy" // lalr1.cc:919
    {
        driver.m_auditLog->setFileMode(strtol(yystack_[0].value.as < std::string > ().c_str(), NULL, 8));
      }
#line 1525 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 12:
#line 753 "seclang-parser.yy" // lalr1.cc:919
    {
        driver.m_auditLog->setFilePath2(yystack_[0].value.as < std::string > ());
      }
#line 1533 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 13:
#line 759 "seclang-parser.yy" // lalr1.cc:919
    {
        driver.m_auditLog->setParts(yystack_[0].value.as < std::string > ());
      }
#line 1541 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 14:
#line 765 "seclang-parser.yy" // lalr1.cc:919
    {
        driver.m_auditLog->setFilePath1(yystack_[0].value.as < std::string > ());
      }
#line 1549 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 15:
#line 770 "seclang-parser.yy" // lalr1.cc:919
    {
        driver.m_auditLog->setFormat(modsecurity::audit_log::AuditLog::JSONAuditLogFormat);
      }
#line 1557 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 16:
#line 775 "seclang-parser.yy" // lalr1.cc:919
    {
        driver.m_auditLog->setFormat(modsecurity::audit_log::AuditLog::NativeAuditLogFormat);
      }
#line 1565 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 17:
#line 781 "seclang-parser.yy" // lalr1.cc:919
    {
        std::string relevant_status(yystack_[0].value.as < std::string > ());
        driver.m_auditLog->setRelevantStatus(relevant_status);
      }
#line 1574 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 18:
#line 788 "seclang-parser.yy" // lalr1.cc:919
    {
        driver.m_auditLog->setType(modsecurity::audit_log::AuditLog::SerialAuditLogType);
      }
#line 1582 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 19:
#line 792 "seclang-parser.yy" // lalr1.cc:919
    {
        driver.m_auditLog->setType(modsecurity::audit_log::AuditLog::ParallelAuditLogType);
      }
#line 1590 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 20:
#line 796 "seclang-parser.yy" // lalr1.cc:919
    {
        driver.m_auditLog->setType(modsecurity::audit_log::AuditLog::HttpsAuditLogType);
      }
#line 1598 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 21:
#line 802 "seclang-parser.yy" // lalr1.cc:919
    {
        driver.m_uploadKeepFiles = modsecurity::RulesProperties::TrueConfigBoolean;
      }
#line 1606 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 22:
#line 806 "seclang-parser.yy" // lalr1.cc:919
    {
        driver.m_uploadKeepFiles = modsecurity::RulesProperties::FalseConfigBoolean;
      }
#line 1614 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 23:
#line 810 "seclang-parser.yy" // lalr1.cc:919
    {
        driver.error(yystack_[2].location, "SecUploadKeepFiles RelevantOnly is not currently supported. Accepted values are On or Off");
        YYERROR;
      }
#line 1623 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 24:
#line 815 "seclang-parser.yy" // lalr1.cc:919
    {
        driver.m_uploadFileLimit.m_set = true;
        driver.m_uploadFileLimit.m_value = strtol(yystack_[0].value.as < std::string > ().c_str(), NULL, 10);
      }
#line 1632 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 25:
#line 820 "seclang-parser.yy" // lalr1.cc:919
    {
        driver.m_uploadFileMode.m_set = true;
        driver.m_uploadFileMode.m_value = strtol(yystack_[0].value.as < std::string > ().c_str(), NULL, 8);
      }
#line 1641 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 26:
#line 825 "seclang-parser.yy" // lalr1.cc:919
    {
        driver.m_uploadDirectory.m_set = true;
        driver.m_uploadDirectory.m_value = yystack_[0].value.as < std::string > ();
      }
#line 1650 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 27:
#line 830 "seclang-parser.yy" // lalr1.cc:919
    {
        driver.m_tmpSaveUploadedFiles = modsecurity::RulesProperties::TrueConfigBoolean;
      }
#line 1658 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 28:
#line 834 "seclang-parser.yy" // lalr1.cc:919
    {
        driver.m_tmpSaveUploadedFiles = modsecurity::RulesProperties::FalseConfigBoolean;
      }
#line 1666 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 29:
#line 841 "seclang-parser.yy" // lalr1.cc:919
    {
        yylhs.value.as < std::unique_ptr<std::vector<std::unique_ptr<actions::Action> > >  > () = std::move(yystack_[1].value.as < std::unique_ptr<std::vector<std::unique_ptr<actions::Action> > >  > ());
      }
#line 1674 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 30:
#line 845 "seclang-parser.yy" // lalr1.cc:919
    {
        yylhs.value.as < std::unique_ptr<std::vector<std::unique_ptr<actions::Action> > >  > () = std::move(yystack_[0].value.as < std::unique_ptr<std::vector<std::unique_ptr<actions::Action> > >  > ());
      }
#line 1682 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 31:
#line 852 "seclang-parser.yy" // lalr1.cc:919
    {
        ACTION_INIT(yystack_[0].value.as < std::unique_ptr<actions::Action> > (), yystack_[3].location)
        yystack_[2].value.as < std::unique_ptr<std::vector<std::unique_ptr<actions::Action> > >  > ()->push_back(std::move(yystack_[0].value.as < std::unique_ptr<actions::Action> > ()));
        yylhs.value.as < std::unique_ptr<std::vector<std::unique_ptr<actions::Action> > >  > () = std::move(yystack_[2].value.as < std::unique_ptr<std::vector<std::unique_ptr<actions::Action> > >  > ());
      }
#line 1692 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 32:
#line 858 "seclang-parser.yy" // lalr1.cc:919
    {
        std::unique_ptr<std::vector<std::unique_ptr<actions::Action>>> b(new std::vector<std::unique_ptr<actions::Action>>());
        ACTION_INIT(yystack_[0].value.as < std::unique_ptr<actions::Action> > (), yystack_[1].location)
        b->push_back(std::move(yystack_[0].value.as < std::unique_ptr<actions::Action> > ()));
        yylhs.value.as < std::unique_ptr<std::vector<std::unique_ptr<actions::Action> > >  > () = std::move(b);
      }
#line 1703 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 33:
#line 868 "seclang-parser.yy" // lalr1.cc:919
    {
        yylhs.value.as < std::unique_ptr<Operator> > () = std::move(yystack_[0].value.as < std::unique_ptr<Operator> > ());
        std::string error;
        if (yylhs.value.as < std::unique_ptr<Operator> > ()->init(*yystack_[0].location.end.filename, &error) == false) {
            driver.error(yystack_[1].location, error);
            YYERROR;
        }
      }
#line 1716 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 34:
#line 877 "seclang-parser.yy" // lalr1.cc:919
    {
        yylhs.value.as < std::unique_ptr<Operator> > () = std::move(yystack_[0].value.as < std::unique_ptr<Operator> > ());
        yylhs.value.as < std::unique_ptr<Operator> > ()->m_negation = true;
        std::string error;
        if (yylhs.value.as < std::unique_ptr<Operator> > ()->init(*yystack_[1].location.end.filename, &error) == false) {
            driver.error(yystack_[2].location, error);
            YYERROR;
        }
      }
#line 1730 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 35:
#line 887 "seclang-parser.yy" // lalr1.cc:919
    {
        OPERATOR_CONTAINER(yylhs.value.as < std::unique_ptr<Operator> > (), new operators::Rx(std::move(yystack_[0].value.as < std::unique_ptr<RunTimeString> > ())));
        std::string error;
        if (yylhs.value.as < std::unique_ptr<Operator> > ()->init(*yystack_[0].location.end.filename, &error) == false) {
            driver.error(yystack_[1].location, error);
            YYERROR;
        }
      }
#line 1743 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 36:
#line 896 "seclang-parser.yy" // lalr1.cc:919
    {
        OPERATOR_CONTAINER(yylhs.value.as < std::unique_ptr<Operator> > (), new operators::Rx(std::move(yystack_[0].value.as < std::unique_ptr<RunTimeString> > ())));
        yylhs.value.as < std::unique_ptr<Operator> > ()->m_negation = true;
        std::string error;
        if (yylhs.value.as < std::unique_ptr<Operator> > ()->init(*yystack_[1].location.end.filename, &error) == false) {
            driver.error(yystack_[2].location, error);
            YYERROR;
        }
      }
#line 1757 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 37:
#line 909 "seclang-parser.yy" // lalr1.cc:919
    {
        OPERATOR_CONTAINER(yylhs.value.as < std::unique_ptr<Operator> > (), new operators::UnconditionalMatch());
      }
#line 1765 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 38:
#line 913 "seclang-parser.yy" // lalr1.cc:919
    {
        OPERATOR_CONTAINER(yylhs.value.as < std::unique_ptr<Operator> > (), new operators::DetectSQLi());
      }
#line 1773 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 39:
#line 917 "seclang-parser.yy" // lalr1.cc:919
    {
        OPERATOR_CONTAINER(yylhs.value.as < std::unique_ptr<Operator> > (), new operators::DetectXSS());
      }
#line 1781 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 40:
#line 921 "seclang-parser.yy" // lalr1.cc:919
    {
        OPERATOR_CONTAINER(yylhs.value.as < std::unique_ptr<Operator> > (), new operators::ValidateUrlEncoding());
      }
#line 1789 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 41:
#line 925 "seclang-parser.yy" // lalr1.cc:919
    {
        OPERATOR_CONTAINER(yylhs.value.as < std::unique_ptr<Operator> > (), new operators::ValidateUtf8Encoding());
      }
#line 1797 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 42:
#line 929 "seclang-parser.yy" // lalr1.cc:919
    {
        OPERATOR_CONTAINER(yylhs.value.as < std::unique_ptr<Operator> > (), new operators::InspectFile(std::move(yystack_[0].value.as < std::unique_ptr<RunTimeString> > ())));
      }
#line 1805 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 43:
#line 933 "seclang-parser.yy" // lalr1.cc:919
    {
        OPERATOR_CONTAINER(yylhs.value.as < std::unique_ptr<Operator> > (), new operators::FuzzyHash(std::move(yystack_[0].value.as < std::unique_ptr<RunTimeString> > ())));
      }
#line 1813 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 44:
#line 937 "seclang-parser.yy" // lalr1.cc:919
    {
        OPERATOR_CONTAINER(yylhs.value.as < std::unique_ptr<Operator> > (), new operators::ValidateByteRange(std::move(yystack_[0].value.as < std::unique_ptr<RunTimeString> > ())));
      }
#line 1821 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 45:
#line 941 "seclang-parser.yy" // lalr1.cc:919
    {
        OPERATOR_CONTAINER(yylhs.value.as < std::unique_ptr<Operator> > (), new operators::ValidateDTD(std::move(yystack_[0].value.as < std::unique_ptr<RunTimeString> > ())));
      }
#line 1829 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 46:
#line 945 "seclang-parser.yy" // lalr1.cc:919
    {
        /* $$ = new operators::ValidateHash($1); */
        OPERATOR_NOT_SUPPORTED("ValidateHash", yystack_[2].location);
      }
#line 1838 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 47:
#line 950 "seclang-parser.yy" // lalr1.cc:919
    {
        OPERATOR_CONTAINER(yylhs.value.as < std::unique_ptr<Operator> > (), new operators::ValidateSchema(std::move(yystack_[0].value.as < std::unique_ptr<RunTimeString> > ())));
      }
#line 1846 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 48:
#line 954 "seclang-parser.yy" // lalr1.cc:919
    {
        OPERATOR_CONTAINER(yylhs.value.as < std::unique_ptr<Operator> > (), new operators::VerifyCC(std::move(yystack_[0].value.as < std::unique_ptr<RunTimeString> > ())));
      }
#line 1854 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 49:
#line 958 "seclang-parser.yy" // lalr1.cc:919
    {
        OPERATOR_CONTAINER(yylhs.value.as < std::unique_ptr<Operator> > (), new operators::VerifyCPF(std::move(yystack_[0].value.as < std::unique_ptr<RunTimeString> > ())));
      }
#line 1862 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 50:
#line 962 "seclang-parser.yy" // lalr1.cc:919
    {
        OPERATOR_CONTAINER(yylhs.value.as < std::unique_ptr<Operator> > (), new operators::VerifySSN(std::move(yystack_[0].value.as < std::unique_ptr<RunTimeString> > ())));
      }
#line 1870 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 51:
#line 966 "seclang-parser.yy" // lalr1.cc:919
    {
        OPERATOR_CONTAINER(yylhs.value.as < std::unique_ptr<Operator> > (), new operators::VerifySVNR(std::move(yystack_[0].value.as < std::unique_ptr<RunTimeString> > ())));
      }
#line 1878 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 52:
#line 970 "seclang-parser.yy" // lalr1.cc:919
    {
        /* $$ = new operators::GsbLookup($1); */
        OPERATOR_NOT_SUPPORTED("GsbLookup", yystack_[2].location);
      }
#line 1887 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 53:
#line 975 "seclang-parser.yy" // lalr1.cc:919
    {
        /* $$ = new operators::Rsub($1); */
        OPERATOR_NOT_SUPPORTED("Rsub", yystack_[2].location);
      }
#line 1896 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 54:
#line 980 "seclang-parser.yy" // lalr1.cc:919
    {
        OPERATOR_CONTAINER(yylhs.value.as < std::unique_ptr<Operator> > (), new operators::Within(std::move(yystack_[0].value.as < std::unique_ptr<RunTimeString> > ())));
      }
#line 1904 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 55:
#line 984 "seclang-parser.yy" // lalr1.cc:919
    {
        OPERATOR_CONTAINER(yylhs.value.as < std::unique_ptr<Operator> > (), new operators::ContainsWord(std::move(yystack_[0].value.as < std::unique_ptr<RunTimeString> > ())));
      }
#line 1912 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 56:
#line 988 "seclang-parser.yy" // lalr1.cc:919
    {
        OPERATOR_CONTAINER(yylhs.value.as < std::unique_ptr<Operator> > (), new operators::Contains(std::move(yystack_[0].value.as < std::unique_ptr<RunTimeString> > ())));
      }
#line 1920 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 57:
#line 992 "seclang-parser.yy" // lalr1.cc:919
    {
        OPERATOR_CONTAINER(yylhs.value.as < std::unique_ptr<Operator> > (), new operators::EndsWith(std::move(yystack_[0].value.as < std::unique_ptr<RunTimeString> > ())));
      }
#line 1928 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 58:
#line 996 "seclang-parser.yy" // lalr1.cc:919
    {
        OPERATOR_CONTAINER(yylhs.value.as < std::unique_ptr<Operator> > (), new operators::Eq(std::move(yystack_[0].value.as < std::unique_ptr<RunTimeString> > ())));
      }
#line 1936 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 59:
#line 1000 "seclang-parser.yy" // lalr1.cc:919
    {
        OPERATOR_CONTAINER(yylhs.value.as < std::unique_ptr<Operator> > (), new operators::Ge(std::move(yystack_[0].value.as < std::unique_ptr<RunTimeString> > ())));
      }
#line 1944 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 60:
#line 1004 "seclang-parser.yy" // lalr1.cc:919
    {
        OPERATOR_CONTAINER(yylhs.value.as < std::unique_ptr<Operator> > (), new operators::Gt(std::move(yystack_[0].value.as < std::unique_ptr<RunTimeString> > ())));
      }
#line 1952 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 61:
#line 1008 "seclang-parser.yy" // lalr1.cc:919
    {
        OPERATOR_CONTAINER(yylhs.value.as < std::unique_ptr<Operator> > (), new operators::IpMatchF(std::move(yystack_[0].value.as < std::unique_ptr<RunTimeString> > ())));
      }
#line 1960 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 62:
#line 1012 "seclang-parser.yy" // lalr1.cc:919
    {
        OPERATOR_CONTAINER(yylhs.value.as < std::unique_ptr<Operator> > (), new operators::IpMatch(std::move(yystack_[0].value.as < std::unique_ptr<RunTimeString> > ())));
      }
#line 1968 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 63:
#line 1016 "seclang-parser.yy" // lalr1.cc:919
    {
        OPERATOR_CONTAINER(yylhs.value.as < std::unique_ptr<Operator> > (), new operators::Le(std::move(yystack_[0].value.as < std::unique_ptr<RunTimeString> > ())));
      }
#line 1976 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 64:
#line 1020 "seclang-parser.yy" // lalr1.cc:919
    {
        OPERATOR_CONTAINER(yylhs.value.as < std::unique_ptr<Operator> > (), new operators::Lt(std::move(yystack_[0].value.as < std::unique_ptr<RunTimeString> > ())));
      }
#line 1984 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 65:
#line 1024 "seclang-parser.yy" // lalr1.cc:919
    {
        OPERATOR_CONTAINER(yylhs.value.as < std::unique_ptr<Operator> > (), new operators::PmFromFile(std::move(yystack_[0].value.as < std::unique_ptr<RunTimeString> > ())));
      }
#line 1992 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 66:
#line 1028 "seclang-parser.yy" // lalr1.cc:919
    {
        OPERATOR_CONTAINER(yylhs.value.as < std::unique_ptr<Operator> > (), new operators::Pm(std::move(yystack_[0].value.as < std::unique_ptr<RunTimeString> > ())));
      }
#line 2000 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 67:
#line 1032 "seclang-parser.yy" // lalr1.cc:919
    {
        OPERATOR_CONTAINER(yylhs.value.as < std::unique_ptr<Operator> > (), new operators::Rbl(std::move(yystack_[0].value.as < std::unique_ptr<RunTimeString> > ())));
      }
#line 2008 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 68:
#line 1036 "seclang-parser.yy" // lalr1.cc:919
    {
        OPERATOR_CONTAINER(yylhs.value.as < std::unique_ptr<Operator> > (), new operators::Rx(std::move(yystack_[0].value.as < std::unique_ptr<RunTimeString> > ())));
      }
#line 2016 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 69:
#line 1040 "seclang-parser.yy" // lalr1.cc:919
    {
        OPERATOR_CONTAINER(yylhs.value.as < std::unique_ptr<Operator> > (), new operators::StrEq(std::move(yystack_[0].value.as < std::unique_ptr<RunTimeString> > ())));
      }
#line 2024 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 70:
#line 1044 "seclang-parser.yy" // lalr1.cc:919
    {
        OPERATOR_CONTAINER(yylhs.value.as < std::unique_ptr<Operator> > (), new operators::StrMatch(std::move(yystack_[0].value.as < std::unique_ptr<RunTimeString> > ())));
      }
#line 2032 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 71:
#line 1048 "seclang-parser.yy" // lalr1.cc:919
    {
        OPERATOR_CONTAINER(yylhs.value.as < std::unique_ptr<Operator> > (), new operators::BeginsWith(std::move(yystack_[0].value.as < std::unique_ptr<RunTimeString> > ())));
      }
#line 2040 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 72:
#line 1052 "seclang-parser.yy" // lalr1.cc:919
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
#line 2055 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 74:
#line 1067 "seclang-parser.yy" // lalr1.cc:919
    {
        std::vector<actions::Action *> *a = new std::vector<actions::Action *>();
        for (auto &i : *yystack_[0].value.as < std::unique_ptr<std::vector<std::unique_ptr<actions::Action> > >  > ().get()) {
            a->push_back(i.release());
        }
        variables::Variables *v = new variables::Variables();
        for (auto &i : *yystack_[2].value.as < std::unique_ptr<std::vector<std::unique_ptr<Variable> > >  > ().get()) {
            v->push_back(i.release());
        }

        Operator *op = yystack_[1].value.as < std::unique_ptr<Operator> > ().release();
        Rule *rule = new Rule(
            /* op */ op,
            /* variables */ v,
            /* actions */ a,
            /* file name */ *yystack_[3].location.end.filename,
            /* line number */ yystack_[3].location.end.line
            );

        if (driver.addSecRule(rule) == false) {
            delete rule;
            YYERROR;
        }
      }
#line 2084 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 75:
#line 1092 "seclang-parser.yy" // lalr1.cc:919
    {
        variables::Variables *v = new variables::Variables();
        for (auto &i : *yystack_[1].value.as < std::unique_ptr<std::vector<std::unique_ptr<Variable> > >  > ().get()) {
            v->push_back(i.release());
        }

        Rule *rule = new Rule(
            /* op */ yystack_[0].value.as < std::unique_ptr<Operator> > ().release(),
            /* variables */ v,
            /* actions */ NULL,
            /* file name */ *yystack_[2].location.end.filename,
            /* line number */ yystack_[2].location.end.line
            );
        if (driver.addSecRule(rule) == false) {
            delete rule;
            YYERROR;
        }
      }
#line 2107 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 76:
#line 1111 "seclang-parser.yy" // lalr1.cc:919
    {
        std::vector<actions::Action *> *a = new std::vector<actions::Action *>();
        for (auto &i : *yystack_[0].value.as < std::unique_ptr<std::vector<std::unique_ptr<actions::Action> > >  > ().get()) {
            a->push_back(i.release());
        }
        Rule *rule = new Rule(
            /* op */ NULL,
            /* variables */ NULL,
            /* actions */ a,
            /* file name */ *yystack_[1].location.end.filename,
            /* line number */ yystack_[1].location.end.line
            );
        driver.addSecAction(rule);
      }
#line 2126 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 77:
#line 1126 "seclang-parser.yy" // lalr1.cc:919
    {
        std::string err;
        std::vector<actions::Action *> *a = new std::vector<actions::Action *>();
        for (auto &i : *yystack_[0].value.as < std::unique_ptr<std::vector<std::unique_ptr<actions::Action> > >  > ().get()) {
            a->push_back(i.release());
        }
        RuleScript *r = new RuleScript(
            /* path to script */ yystack_[1].value.as < std::string > (),
            /* actions */ a,
            /* file name */ *yystack_[1].location.end.filename,
            /* line number */ yystack_[1].location.end.line
            );

        if (r->init(&err) == false) {
            driver.error(yystack_[2].location, "Failed to load script: " + err);
            delete r;
            YYERROR;
        }
        if (driver.addSecRuleScript(r) == false) {
            delete r;
            YYERROR;
        }
      }
#line 2154 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 78:
#line 1150 "seclang-parser.yy" // lalr1.cc:919
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
                driver.error(yystack_[2].location, "The action '" + a->m_name + "' is not suitable to be part of the SecDefaultActions");
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
            driver.m_defaultActions[definedPhase].push_back(a);
        }

        delete actions;
      }
#line 2214 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 79:
#line 1206 "seclang-parser.yy" // lalr1.cc:919
    {
        driver.addSecMarker(modsecurity::utils::string::removeBracketsIfNeeded(yystack_[0].value.as < std::string > ()));
      }
#line 2222 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 80:
#line 1210 "seclang-parser.yy" // lalr1.cc:919
    {
        driver.m_secRuleEngine = modsecurity::Rules::DisabledRuleEngine;
      }
#line 2230 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 81:
#line 1214 "seclang-parser.yy" // lalr1.cc:919
    {
        driver.m_secRuleEngine = modsecurity::Rules::EnabledRuleEngine;
      }
#line 2238 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 82:
#line 1218 "seclang-parser.yy" // lalr1.cc:919
    {
        driver.m_secRuleEngine = modsecurity::Rules::DetectionOnlyRuleEngine;
      }
#line 2246 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 83:
#line 1222 "seclang-parser.yy" // lalr1.cc:919
    {
        driver.m_secRequestBodyAccess = modsecurity::RulesProperties::TrueConfigBoolean;
      }
#line 2254 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 84:
#line 1226 "seclang-parser.yy" // lalr1.cc:919
    {
        driver.m_secRequestBodyAccess = modsecurity::RulesProperties::FalseConfigBoolean;
      }
#line 2262 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 85:
#line 1230 "seclang-parser.yy" // lalr1.cc:919
    {
        driver.m_secResponseBodyAccess = modsecurity::RulesProperties::TrueConfigBoolean;
      }
#line 2270 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 86:
#line 1234 "seclang-parser.yy" // lalr1.cc:919
    {
        driver.m_secResponseBodyAccess = modsecurity::RulesProperties::FalseConfigBoolean;
      }
#line 2278 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 87:
#line 1238 "seclang-parser.yy" // lalr1.cc:919
    {
        if (yystack_[0].value.as < std::string > ().length() != 1) {
          driver.error(yystack_[1].location, "Argument separator should be set to a single character.");
          YYERROR;
        }
        driver.m_secArgumentSeparator.m_value = yystack_[0].value.as < std::string > ();
        driver.m_secArgumentSeparator.m_set = true;
      }
#line 2291 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 88:
#line 1247 "seclang-parser.yy" // lalr1.cc:919
    {
        driver.m_components.push_back(yystack_[0].value.as < std::string > ());
      }
#line 2299 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 89:
#line 1251 "seclang-parser.yy" // lalr1.cc:919
    {
        driver.error(yystack_[2].location, "SecConnEngine is not yet supported.");
        YYERROR;
      }
#line 2308 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 90:
#line 1256 "seclang-parser.yy" // lalr1.cc:919
    {
      }
#line 2315 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 91:
#line 1259 "seclang-parser.yy" // lalr1.cc:919
    {
        driver.m_secWebAppId.m_value = yystack_[0].value.as < std::string > ();
        driver.m_secWebAppId.m_set = true;
      }
#line 2324 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 92:
#line 1264 "seclang-parser.yy" // lalr1.cc:919
    {
        driver.error(yystack_[1].location, "SecServerSignature is not supported.");
        YYERROR;
      }
#line 2333 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 93:
#line 1269 "seclang-parser.yy" // lalr1.cc:919
    {
        driver.error(yystack_[1].location, "SecCacheTransformations is not supported.");
        YYERROR;
      }
#line 2342 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 94:
#line 1274 "seclang-parser.yy" // lalr1.cc:919
    {
        driver.error(yystack_[2].location, "SecDisableBackendCompression is not supported.");
        YYERROR;
      }
#line 2351 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 95:
#line 1279 "seclang-parser.yy" // lalr1.cc:919
    {
      }
#line 2358 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 96:
#line 1282 "seclang-parser.yy" // lalr1.cc:919
    {
        driver.error(yystack_[2].location, "SecContentInjection is not yet supported.");
        YYERROR;
      }
#line 2367 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 97:
#line 1287 "seclang-parser.yy" // lalr1.cc:919
    {
      }
#line 2374 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 98:
#line 1290 "seclang-parser.yy" // lalr1.cc:919
    {
        driver.error(yystack_[1].location, "SecChrootDir is not supported.");
        YYERROR;
      }
#line 2383 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 99:
#line 1295 "seclang-parser.yy" // lalr1.cc:919
    {
        driver.error(yystack_[2].location, "SecHashEngine is not yet supported.");
        YYERROR;
      }
#line 2392 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 100:
#line 1300 "seclang-parser.yy" // lalr1.cc:919
    {
      }
#line 2399 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 101:
#line 1303 "seclang-parser.yy" // lalr1.cc:919
    {
        driver.error(yystack_[1].location, "SecHashKey is not yet supported.");
        YYERROR;
      }
#line 2408 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 102:
#line 1308 "seclang-parser.yy" // lalr1.cc:919
    {
        driver.error(yystack_[1].location, "SecHashParam is not yet supported.");
        YYERROR;
      }
#line 2417 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 103:
#line 1313 "seclang-parser.yy" // lalr1.cc:919
    {
        driver.error(yystack_[1].location, "SecHashMethodRx is not yet supported.");
        YYERROR;
      }
#line 2426 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 104:
#line 1318 "seclang-parser.yy" // lalr1.cc:919
    {
        driver.error(yystack_[1].location, "SecHashMethodPm is not yet supported.");
        YYERROR;
      }
#line 2435 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 105:
#line 1323 "seclang-parser.yy" // lalr1.cc:919
    {
        driver.error(yystack_[1].location, "SecGsbLookupDb is not supported.");
        YYERROR;
      }
#line 2444 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 106:
#line 1328 "seclang-parser.yy" // lalr1.cc:919
    {
        driver.error(yystack_[1].location, "SecGuardianLog is not supported.");
        YYERROR;
      }
#line 2453 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 107:
#line 1333 "seclang-parser.yy" // lalr1.cc:919
    {
        driver.error(yystack_[2].location, "SecInterceptOnError is not yet supported.");
        YYERROR;
      }
#line 2462 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 108:
#line 1338 "seclang-parser.yy" // lalr1.cc:919
    {
      }
#line 2469 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 109:
#line 1341 "seclang-parser.yy" // lalr1.cc:919
    {
        driver.error(yystack_[1].location, "SecConnReadStateLimit is not yet supported.");
        YYERROR;
      }
#line 2478 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 110:
#line 1346 "seclang-parser.yy" // lalr1.cc:919
    {
        driver.error(yystack_[1].location, "SecConnWriteStateLimit is not yet supported.");
        YYERROR;
      }
#line 2487 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 111:
#line 1351 "seclang-parser.yy" // lalr1.cc:919
    {
        driver.error(yystack_[1].location, "SecSensorId is not yet supported.");
        YYERROR;
      }
#line 2496 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 112:
#line 1356 "seclang-parser.yy" // lalr1.cc:919
    {
        driver.error(yystack_[2].location, "SecRuleInheritance is not yet supported.");
        YYERROR;
      }
#line 2505 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 113:
#line 1361 "seclang-parser.yy" // lalr1.cc:919
    {
      }
#line 2512 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 114:
#line 1364 "seclang-parser.yy" // lalr1.cc:919
    {
        driver.error(yystack_[1].location, "SecRulePerfTime is not yet supported.");
        YYERROR;
      }
#line 2521 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 115:
#line 1369 "seclang-parser.yy" // lalr1.cc:919
    {
        driver.error(yystack_[1].location, "SecStreamInBodyInspection is not supported.");
        YYERROR;
      }
#line 2530 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 116:
#line 1374 "seclang-parser.yy" // lalr1.cc:919
    {
        driver.error(yystack_[1].location, "SecStreamOutBodyInspection is not supported.");
        YYERROR;
      }
#line 2539 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 117:
#line 1379 "seclang-parser.yy" // lalr1.cc:919
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
#line 2556 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 118:
#line 1392 "seclang-parser.yy" // lalr1.cc:919
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
#line 2573 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 119:
#line 1405 "seclang-parser.yy" // lalr1.cc:919
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
#line 2590 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 120:
#line 1418 "seclang-parser.yy" // lalr1.cc:919
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
#line 2607 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 121:
#line 1431 "seclang-parser.yy" // lalr1.cc:919
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
#line 2624 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 122:
#line 1444 "seclang-parser.yy" // lalr1.cc:919
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
#line 2654 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 123:
#line 1470 "seclang-parser.yy" // lalr1.cc:919
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
#line 2685 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 124:
#line 1498 "seclang-parser.yy" // lalr1.cc:919
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
#line 2701 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 125:
#line 1510 "seclang-parser.yy" // lalr1.cc:919
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
#line 2724 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 126:
#line 1530 "seclang-parser.yy" // lalr1.cc:919
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
#line 2755 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 127:
#line 1558 "seclang-parser.yy" // lalr1.cc:919
    {
        driver.m_requestBodyLimit.m_set = true;
        driver.m_requestBodyLimit.m_value = atoi(yystack_[0].value.as < std::string > ().c_str());
      }
#line 2764 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 128:
#line 1563 "seclang-parser.yy" // lalr1.cc:919
    {
        driver.m_requestBodyNoFilesLimit.m_set = true;
        driver.m_requestBodyNoFilesLimit.m_value = atoi(yystack_[0].value.as < std::string > ().c_str());
      }
#line 2773 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 129:
#line 1568 "seclang-parser.yy" // lalr1.cc:919
    {
        std::stringstream ss;
        ss << "As of ModSecurity version 3.0, SecRequestBodyInMemoryLimit is no longer ";
        ss << "supported. Instead, you can use your web server configurations to control ";
        ss << "those values. ModSecurity will follow the web server decision.";
        driver.error(yystack_[1].location, ss.str());
        YYERROR;
      }
#line 2786 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 130:
#line 1577 "seclang-parser.yy" // lalr1.cc:919
    {
        driver.m_responseBodyLimit.m_set = true;
        driver.m_responseBodyLimit.m_value = atoi(yystack_[0].value.as < std::string > ().c_str());
      }
#line 2795 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 131:
#line 1582 "seclang-parser.yy" // lalr1.cc:919
    {
        driver.m_requestBodyLimitAction = modsecurity::Rules::BodyLimitAction::ProcessPartialBodyLimitAction;
      }
#line 2803 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 132:
#line 1586 "seclang-parser.yy" // lalr1.cc:919
    {
        driver.m_requestBodyLimitAction = modsecurity::Rules::BodyLimitAction::RejectBodyLimitAction;
      }
#line 2811 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 133:
#line 1590 "seclang-parser.yy" // lalr1.cc:919
    {
        driver.m_responseBodyLimitAction = modsecurity::Rules::BodyLimitAction::ProcessPartialBodyLimitAction;
      }
#line 2819 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 134:
#line 1594 "seclang-parser.yy" // lalr1.cc:919
    {
        driver.m_responseBodyLimitAction = modsecurity::Rules::BodyLimitAction::RejectBodyLimitAction;
      }
#line 2827 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 135:
#line 1598 "seclang-parser.yy" // lalr1.cc:919
    {
        driver.m_remoteRulesActionOnFailed = Rules::OnFailedRemoteRulesAction::AbortOnFailedRemoteRulesAction;
      }
#line 2835 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 136:
#line 1602 "seclang-parser.yy" // lalr1.cc:919
    {
        driver.m_remoteRulesActionOnFailed = Rules::OnFailedRemoteRulesAction::WarnOnFailedRemoteRulesAction;
      }
#line 2843 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 139:
#line 1616 "seclang-parser.yy" // lalr1.cc:919
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
#line 2859 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 140:
#line 1628 "seclang-parser.yy" // lalr1.cc:919
    {
        driver.m_responseBodyTypeToBeInspected.m_set = true;
        driver.m_responseBodyTypeToBeInspected.m_clear = true;
        driver.m_responseBodyTypeToBeInspected.m_value.clear();
      }
#line 2869 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 141:
#line 1634 "seclang-parser.yy" // lalr1.cc:919
    {
        driver.m_secXMLExternalEntity = modsecurity::RulesProperties::FalseConfigBoolean;
      }
#line 2877 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 142:
#line 1638 "seclang-parser.yy" // lalr1.cc:919
    {
        driver.m_secXMLExternalEntity = modsecurity::RulesProperties::TrueConfigBoolean;
      }
#line 2885 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 143:
#line 1642 "seclang-parser.yy" // lalr1.cc:919
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
#line 2900 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 146:
#line 1663 "seclang-parser.yy" // lalr1.cc:919
    {
        if (atoi(yystack_[0].value.as < std::string > ().c_str()) == 1) {
          driver.error(yystack_[1].location, "SecCookieFormat 1 is not yet supported.");
          YYERROR;
        }
      }
#line 2911 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 147:
#line 1670 "seclang-parser.yy" // lalr1.cc:919
    {
        driver.error(yystack_[1].location, "SecCookieV0Separator is not yet supported.");
        YYERROR;
      }
#line 2920 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 149:
#line 1680 "seclang-parser.yy" // lalr1.cc:919
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
#line 2978 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 150:
#line 1734 "seclang-parser.yy" // lalr1.cc:919
    {
/* Parser error disabled to avoid breaking default CRS installations with crs-setup.conf-recommended
        driver.error(@0, "SecCollectionTimeout is not yet supported.");
        YYERROR;
*/
      }
#line 2989 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 151:
#line 1741 "seclang-parser.yy" // lalr1.cc:919
    {
        driver.m_httpblKey.m_set = true;
        driver.m_httpblKey.m_value = yystack_[0].value.as < std::string > ();
      }
#line 2998 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 152:
#line 1749 "seclang-parser.yy" // lalr1.cc:919
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
#line 3036 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 153:
#line 1786 "seclang-parser.yy" // lalr1.cc:919
    {
        yylhs.value.as < std::unique_ptr<std::vector<std::unique_ptr<Variable> > >  > () = std::move(yystack_[0].value.as < std::unique_ptr<std::vector<std::unique_ptr<Variable> > >  > ());
      }
#line 3044 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 154:
#line 1790 "seclang-parser.yy" // lalr1.cc:919
    {
        yylhs.value.as < std::unique_ptr<std::vector<std::unique_ptr<Variable> > >  > () = std::move(yystack_[1].value.as < std::unique_ptr<std::vector<std::unique_ptr<Variable> > >  > ());
      }
#line 3052 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 155:
#line 1797 "seclang-parser.yy" // lalr1.cc:919
    {
        yystack_[2].value.as < std::unique_ptr<std::vector<std::unique_ptr<Variable> > >  > ()->push_back(std::move(yystack_[0].value.as < std::unique_ptr<Variable> > ()));
        yylhs.value.as < std::unique_ptr<std::vector<std::unique_ptr<Variable> > >  > () = std::move(yystack_[2].value.as < std::unique_ptr<std::vector<std::unique_ptr<Variable> > >  > ());
      }
#line 3061 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 156:
#line 1802 "seclang-parser.yy" // lalr1.cc:919
    {
        std::unique_ptr<Variable> c(new VariableModificatorExclusion(std::move(yystack_[0].value.as < std::unique_ptr<Variable> > ())));
        yystack_[3].value.as < std::unique_ptr<std::vector<std::unique_ptr<Variable> > >  > ()->push_back(std::move(c));
        yylhs.value.as < std::unique_ptr<std::vector<std::unique_ptr<Variable> > >  > () = std::move(yystack_[3].value.as < std::unique_ptr<std::vector<std::unique_ptr<Variable> > >  > ());
      }
#line 3071 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 157:
#line 1808 "seclang-parser.yy" // lalr1.cc:919
    {
        std::unique_ptr<Variable> c(new VariableModificatorCount(std::move(yystack_[0].value.as < std::unique_ptr<Variable> > ())));
        yystack_[3].value.as < std::unique_ptr<std::vector<std::unique_ptr<Variable> > >  > ()->push_back(std::move(c));
        yylhs.value.as < std::unique_ptr<std::vector<std::unique_ptr<Variable> > >  > () = std::move(yystack_[3].value.as < std::unique_ptr<std::vector<std::unique_ptr<Variable> > >  > ());
      }
#line 3081 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 158:
#line 1814 "seclang-parser.yy" // lalr1.cc:919
    {
        std::unique_ptr<std::vector<std::unique_ptr<Variable>>> b(new std::vector<std::unique_ptr<Variable>>());
        b->push_back(std::move(yystack_[0].value.as < std::unique_ptr<Variable> > ()));
        yylhs.value.as < std::unique_ptr<std::vector<std::unique_ptr<Variable> > >  > () = std::move(b);
      }
#line 3091 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 159:
#line 1820 "seclang-parser.yy" // lalr1.cc:919
    {
        std::unique_ptr<std::vector<std::unique_ptr<Variable>>> b(new std::vector<std::unique_ptr<Variable>>());
        std::unique_ptr<Variable> c(new VariableModificatorExclusion(std::move(yystack_[0].value.as < std::unique_ptr<Variable> > ())));
        b->push_back(std::move(c));
        yylhs.value.as < std::unique_ptr<std::vector<std::unique_ptr<Variable> > >  > () = std::move(b);
      }
#line 3102 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 160:
#line 1827 "seclang-parser.yy" // lalr1.cc:919
    {
        std::unique_ptr<std::vector<std::unique_ptr<Variable>>> b(new std::vector<std::unique_ptr<Variable>>());
        std::unique_ptr<Variable> c(new VariableModificatorCount(std::move(yystack_[0].value.as < std::unique_ptr<Variable> > ())));
        b->push_back(std::move(c));
        yylhs.value.as < std::unique_ptr<std::vector<std::unique_ptr<Variable> > >  > () = std::move(b);
      }
#line 3113 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 161:
#line 1837 "seclang-parser.yy" // lalr1.cc:919
    {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::Args_DictElement(yystack_[0].value.as < std::string > ()));
      }
#line 3121 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 162:
#line 1841 "seclang-parser.yy" // lalr1.cc:919
    {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::Args_DictElementRegexp(yystack_[0].value.as < std::string > ()));
      }
#line 3129 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 163:
#line 1845 "seclang-parser.yy" // lalr1.cc:919
    {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::Args_NoDictElement());
      }
#line 3137 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 164:
#line 1849 "seclang-parser.yy" // lalr1.cc:919
    {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::ArgsPost_DictElement(yystack_[0].value.as < std::string > ()));
      }
#line 3145 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 165:
#line 1853 "seclang-parser.yy" // lalr1.cc:919
    {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::ArgsPost_DictElementRegexp(yystack_[0].value.as < std::string > ()));
      }
#line 3153 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 166:
#line 1857 "seclang-parser.yy" // lalr1.cc:919
    {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::ArgsPost_NoDictElement());
      }
#line 3161 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 167:
#line 1861 "seclang-parser.yy" // lalr1.cc:919
    {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::ArgsGet_DictElement(yystack_[0].value.as < std::string > ()));
      }
#line 3169 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 168:
#line 1865 "seclang-parser.yy" // lalr1.cc:919
    {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::ArgsGet_DictElementRegexp(yystack_[0].value.as < std::string > ()));
      }
#line 3177 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 169:
#line 1869 "seclang-parser.yy" // lalr1.cc:919
    {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::ArgsGet_NoDictElement());
      }
#line 3185 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 170:
#line 1873 "seclang-parser.yy" // lalr1.cc:919
    {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::FilesSizes_DictElement(yystack_[0].value.as < std::string > ()));
      }
#line 3193 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 171:
#line 1877 "seclang-parser.yy" // lalr1.cc:919
    {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::FilesSizes_DictElementRegexp(yystack_[0].value.as < std::string > ()));
      }
#line 3201 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 172:
#line 1881 "seclang-parser.yy" // lalr1.cc:919
    {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::FilesSizes_NoDictElement());
      }
#line 3209 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 173:
#line 1885 "seclang-parser.yy" // lalr1.cc:919
    {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::FilesNames_DictElement(yystack_[0].value.as < std::string > ()));
      }
#line 3217 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 174:
#line 1889 "seclang-parser.yy" // lalr1.cc:919
    {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::FilesNames_DictElementRegexp(yystack_[0].value.as < std::string > ()));
      }
#line 3225 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 175:
#line 1893 "seclang-parser.yy" // lalr1.cc:919
    {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::FilesNames_NoDictElement());
      }
#line 3233 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 176:
#line 1897 "seclang-parser.yy" // lalr1.cc:919
    {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::FilesTmpContent_DictElement(yystack_[0].value.as < std::string > ()));
      }
#line 3241 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 177:
#line 1901 "seclang-parser.yy" // lalr1.cc:919
    {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::FilesTmpContent_DictElementRegexp(yystack_[0].value.as < std::string > ()));
      }
#line 3249 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 178:
#line 1905 "seclang-parser.yy" // lalr1.cc:919
    {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::FilesTmpContent_NoDictElement());
      }
#line 3257 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 179:
#line 1909 "seclang-parser.yy" // lalr1.cc:919
    {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::MultiPartFileName_DictElement(yystack_[0].value.as < std::string > ()));
      }
#line 3265 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 180:
#line 1913 "seclang-parser.yy" // lalr1.cc:919
    {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::MultiPartFileName_DictElementRegexp(yystack_[0].value.as < std::string > ()));
      }
#line 3273 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 181:
#line 1917 "seclang-parser.yy" // lalr1.cc:919
    {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::MultiPartFileName_NoDictElement());
      }
#line 3281 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 182:
#line 1921 "seclang-parser.yy" // lalr1.cc:919
    {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::MultiPartName_DictElement(yystack_[0].value.as < std::string > ()));
      }
#line 3289 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 183:
#line 1925 "seclang-parser.yy" // lalr1.cc:919
    {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::MultiPartName_DictElementRegexp(yystack_[0].value.as < std::string > ()));
      }
#line 3297 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 184:
#line 1929 "seclang-parser.yy" // lalr1.cc:919
    {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::MultiPartName_NoDictElement());
      }
#line 3305 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 185:
#line 1933 "seclang-parser.yy" // lalr1.cc:919
    {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::MatchedVarsNames_DictElement(yystack_[0].value.as < std::string > ()));
      }
#line 3313 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 186:
#line 1937 "seclang-parser.yy" // lalr1.cc:919
    {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::MatchedVarsNames_DictElementRegexp(yystack_[0].value.as < std::string > ()));
      }
#line 3321 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 187:
#line 1941 "seclang-parser.yy" // lalr1.cc:919
    {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::MatchedVarsNames_NoDictElement());
      }
#line 3329 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 188:
#line 1945 "seclang-parser.yy" // lalr1.cc:919
    {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::MatchedVars_DictElement(yystack_[0].value.as < std::string > ()));
      }
#line 3337 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 189:
#line 1949 "seclang-parser.yy" // lalr1.cc:919
    {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::MatchedVars_DictElementRegexp(yystack_[0].value.as < std::string > ()));
      }
#line 3345 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 190:
#line 1953 "seclang-parser.yy" // lalr1.cc:919
    {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::MatchedVars_NoDictElement());
      }
#line 3353 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 191:
#line 1957 "seclang-parser.yy" // lalr1.cc:919
    {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::Files_DictElement(yystack_[0].value.as < std::string > ()));
      }
#line 3361 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 192:
#line 1961 "seclang-parser.yy" // lalr1.cc:919
    {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::Files_DictElementRegexp(yystack_[0].value.as < std::string > ()));
      }
#line 3369 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 193:
#line 1965 "seclang-parser.yy" // lalr1.cc:919
    {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::Files_NoDictElement());
      }
#line 3377 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 194:
#line 1969 "seclang-parser.yy" // lalr1.cc:919
    {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::RequestCookies_DictElement(yystack_[0].value.as < std::string > ()));
      }
#line 3385 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 195:
#line 1973 "seclang-parser.yy" // lalr1.cc:919
    {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::RequestCookies_DictElementRegexp(yystack_[0].value.as < std::string > ()));
      }
#line 3393 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 196:
#line 1977 "seclang-parser.yy" // lalr1.cc:919
    {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::RequestCookies_NoDictElement());
      }
#line 3401 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 197:
#line 1981 "seclang-parser.yy" // lalr1.cc:919
    {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::RequestHeaders_DictElement(yystack_[0].value.as < std::string > ()));
      }
#line 3409 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 198:
#line 1985 "seclang-parser.yy" // lalr1.cc:919
    {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::RequestHeaders_DictElementRegexp(yystack_[0].value.as < std::string > ()));
      }
#line 3417 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 199:
#line 1989 "seclang-parser.yy" // lalr1.cc:919
    {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::RequestHeaders_NoDictElement());
      }
#line 3425 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 200:
#line 1993 "seclang-parser.yy" // lalr1.cc:919
    {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::ResponseHeaders_DictElement(yystack_[0].value.as < std::string > ()));
      }
#line 3433 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 201:
#line 1997 "seclang-parser.yy" // lalr1.cc:919
    {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::ResponseHeaders_DictElementRegexp(yystack_[0].value.as < std::string > ()));
      }
#line 3441 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 202:
#line 2001 "seclang-parser.yy" // lalr1.cc:919
    {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::ResponseHeaders_NoDictElement());
      }
#line 3449 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 203:
#line 2005 "seclang-parser.yy" // lalr1.cc:919
    {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::Geo_DictElement(yystack_[0].value.as < std::string > ()));
      }
#line 3457 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 204:
#line 2009 "seclang-parser.yy" // lalr1.cc:919
    {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::Geo_DictElementRegexp(yystack_[0].value.as < std::string > ()));
      }
#line 3465 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 205:
#line 2013 "seclang-parser.yy" // lalr1.cc:919
    {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::Geo_NoDictElement());
      }
#line 3473 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 206:
#line 2017 "seclang-parser.yy" // lalr1.cc:919
    {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::RequestCookiesNames_DictElement(yystack_[0].value.as < std::string > ()));
      }
#line 3481 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 207:
#line 2021 "seclang-parser.yy" // lalr1.cc:919
    {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::RequestCookiesNames_DictElementRegexp(yystack_[0].value.as < std::string > ()));
      }
#line 3489 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 208:
#line 2025 "seclang-parser.yy" // lalr1.cc:919
    {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::RequestCookiesNames_NoDictElement());
      }
#line 3497 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 209:
#line 2029 "seclang-parser.yy" // lalr1.cc:919
    {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::Rule_DictElement(yystack_[0].value.as < std::string > ()));
      }
#line 3505 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 210:
#line 2033 "seclang-parser.yy" // lalr1.cc:919
    {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::Rule_DictElementRegexp(yystack_[0].value.as < std::string > ()));
      }
#line 3513 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 211:
#line 2037 "seclang-parser.yy" // lalr1.cc:919
    {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::Rule_NoDictElement());
      }
#line 3521 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 212:
#line 2041 "seclang-parser.yy" // lalr1.cc:919
    {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::Env("ENV:" + yystack_[0].value.as < std::string > ()));
      }
#line 3529 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 213:
#line 2045 "seclang-parser.yy" // lalr1.cc:919
    {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::Env("ENV:" + yystack_[0].value.as < std::string > ()));
      }
#line 3537 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 214:
#line 2049 "seclang-parser.yy" // lalr1.cc:919
    {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::Env("ENV"));
      }
#line 3545 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 215:
#line 2053 "seclang-parser.yy" // lalr1.cc:919
    {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::XML("XML:" + yystack_[0].value.as < std::string > ()));
      }
#line 3553 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 216:
#line 2057 "seclang-parser.yy" // lalr1.cc:919
    {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::XML("XML:" + yystack_[0].value.as < std::string > ()));
      }
#line 3561 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 217:
#line 2061 "seclang-parser.yy" // lalr1.cc:919
    {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::XML_NoDictElement());
      }
#line 3569 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 218:
#line 2065 "seclang-parser.yy" // lalr1.cc:919
    {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::FilesTmpNames_DictElement(yystack_[0].value.as < std::string > ()));
      }
#line 3577 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 219:
#line 2069 "seclang-parser.yy" // lalr1.cc:919
    {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::FilesTmpNames_DictElementRegexp(yystack_[0].value.as < std::string > ()));
      }
#line 3585 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 220:
#line 2073 "seclang-parser.yy" // lalr1.cc:919
    {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::FilesTmpNames_NoDictElement());
      }
#line 3593 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 221:
#line 2077 "seclang-parser.yy" // lalr1.cc:919
    {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::Resource_DynamicElement(std::move(yystack_[0].value.as < std::unique_ptr<RunTimeString> > ())));
      }
#line 3601 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 222:
#line 2081 "seclang-parser.yy" // lalr1.cc:919
    {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::Resource_DictElement(yystack_[0].value.as < std::string > ()));
      }
#line 3609 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 223:
#line 2085 "seclang-parser.yy" // lalr1.cc:919
    {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::Resource_DictElementRegexp(yystack_[0].value.as < std::string > ()));
      }
#line 3617 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 224:
#line 2089 "seclang-parser.yy" // lalr1.cc:919
    {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::Resource_NoDictElement());
      }
#line 3625 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 225:
#line 2093 "seclang-parser.yy" // lalr1.cc:919
    {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::Ip_DynamicElement(std::move(yystack_[0].value.as < std::unique_ptr<RunTimeString> > ())));
      }
#line 3633 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 226:
#line 2097 "seclang-parser.yy" // lalr1.cc:919
    {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::Ip_DictElement(yystack_[0].value.as < std::string > ()));
      }
#line 3641 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 227:
#line 2101 "seclang-parser.yy" // lalr1.cc:919
    {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::Ip_DictElementRegexp(yystack_[0].value.as < std::string > ()));
      }
#line 3649 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 228:
#line 2105 "seclang-parser.yy" // lalr1.cc:919
    {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::Ip_NoDictElement());
      }
#line 3657 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 229:
#line 2109 "seclang-parser.yy" // lalr1.cc:919
    {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::Global_DynamicElement(std::move(yystack_[0].value.as < std::unique_ptr<RunTimeString> > ())));
      }
#line 3665 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 230:
#line 2113 "seclang-parser.yy" // lalr1.cc:919
    {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::Global_DictElement(yystack_[0].value.as < std::string > ()));
      }
#line 3673 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 231:
#line 2117 "seclang-parser.yy" // lalr1.cc:919
    {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::Global_DictElementRegexp(yystack_[0].value.as < std::string > ()));
      }
#line 3681 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 232:
#line 2121 "seclang-parser.yy" // lalr1.cc:919
    {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::Global_NoDictElement());
      }
#line 3689 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 233:
#line 2125 "seclang-parser.yy" // lalr1.cc:919
    {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::User_DynamicElement(std::move(yystack_[0].value.as < std::unique_ptr<RunTimeString> > ())));
      }
#line 3697 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 234:
#line 2129 "seclang-parser.yy" // lalr1.cc:919
    {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::User_DictElement(yystack_[0].value.as < std::string > ()));
      }
#line 3705 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 235:
#line 2133 "seclang-parser.yy" // lalr1.cc:919
    {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::User_DictElementRegexp(yystack_[0].value.as < std::string > ()));
      }
#line 3713 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 236:
#line 2137 "seclang-parser.yy" // lalr1.cc:919
    {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::User_NoDictElement());
      }
#line 3721 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 237:
#line 2141 "seclang-parser.yy" // lalr1.cc:919
    {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::Tx_DynamicElement(std::move(yystack_[0].value.as < std::unique_ptr<RunTimeString> > ())));
      }
#line 3729 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 238:
#line 2145 "seclang-parser.yy" // lalr1.cc:919
    {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::Tx_DictElement(yystack_[0].value.as < std::string > ()));
      }
#line 3737 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 239:
#line 2149 "seclang-parser.yy" // lalr1.cc:919
    {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::Tx_DictElementRegexp(yystack_[0].value.as < std::string > ()));
      }
#line 3745 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 240:
#line 2153 "seclang-parser.yy" // lalr1.cc:919
    {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::Tx_NoDictElement());
      }
#line 3753 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 241:
#line 2157 "seclang-parser.yy" // lalr1.cc:919
    {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::Session_DynamicElement(std::move(yystack_[0].value.as < std::unique_ptr<RunTimeString> > ())));
      }
#line 3761 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 242:
#line 2161 "seclang-parser.yy" // lalr1.cc:919
    {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::Session_DictElement(yystack_[0].value.as < std::string > ()));
      }
#line 3769 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 243:
#line 2165 "seclang-parser.yy" // lalr1.cc:919
    {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::Session_DictElementRegexp(yystack_[0].value.as < std::string > ()));
      }
#line 3777 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 244:
#line 2169 "seclang-parser.yy" // lalr1.cc:919
    {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::Session_NoDictElement());
      }
#line 3785 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 245:
#line 2173 "seclang-parser.yy" // lalr1.cc:919
    {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::ArgsNames_DictElement(yystack_[0].value.as < std::string > ()));
      }
#line 3793 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 246:
#line 2177 "seclang-parser.yy" // lalr1.cc:919
    {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::ArgsNames_DictElementRegexp(yystack_[0].value.as < std::string > ()));
      }
#line 3801 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 247:
#line 2181 "seclang-parser.yy" // lalr1.cc:919
    {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::ArgsNames_NoDictElement());
      }
#line 3809 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 248:
#line 2185 "seclang-parser.yy" // lalr1.cc:919
    {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::ArgsGetNames_DictElement(yystack_[0].value.as < std::string > ()));
      }
#line 3817 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 249:
#line 2189 "seclang-parser.yy" // lalr1.cc:919
    {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::ArgsGetNames_DictElementRegexp(yystack_[0].value.as < std::string > ()));
      }
#line 3825 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 250:
#line 2193 "seclang-parser.yy" // lalr1.cc:919
    {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::ArgsGetNames_NoDictElement());
      }
#line 3833 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 251:
#line 2198 "seclang-parser.yy" // lalr1.cc:919
    {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::ArgsPostNames_DictElement(yystack_[0].value.as < std::string > ()));
      }
#line 3841 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 252:
#line 2202 "seclang-parser.yy" // lalr1.cc:919
    {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::ArgsPostNames_DictElementRegexp(yystack_[0].value.as < std::string > ()));
      }
#line 3849 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 253:
#line 2206 "seclang-parser.yy" // lalr1.cc:919
    {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::ArgsPostNames_NoDictElement());
      }
#line 3857 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 254:
#line 2211 "seclang-parser.yy" // lalr1.cc:919
    {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::RequestHeadersNames_DictElement(yystack_[0].value.as < std::string > ()));
      }
#line 3865 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 255:
#line 2215 "seclang-parser.yy" // lalr1.cc:919
    {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::RequestHeadersNames_DictElementRegexp(yystack_[0].value.as < std::string > ()));
      }
#line 3873 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 256:
#line 2219 "seclang-parser.yy" // lalr1.cc:919
    {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::RequestHeadersNames_NoDictElement());
      }
#line 3881 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 257:
#line 2224 "seclang-parser.yy" // lalr1.cc:919
    {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::ResponseContentType());
      }
#line 3889 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 258:
#line 2229 "seclang-parser.yy" // lalr1.cc:919
    {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::ResponseHeadersNames_DictElement(yystack_[0].value.as < std::string > ()));
      }
#line 3897 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 259:
#line 2233 "seclang-parser.yy" // lalr1.cc:919
    {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::ResponseHeadersNames_DictElementRegexp(yystack_[0].value.as < std::string > ()));
      }
#line 3905 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 260:
#line 2237 "seclang-parser.yy" // lalr1.cc:919
    {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::ResponseHeadersNames_NoDictElement());
      }
#line 3913 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 261:
#line 2241 "seclang-parser.yy" // lalr1.cc:919
    {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::ArgsCombinedSize());
      }
#line 3921 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 262:
#line 2245 "seclang-parser.yy" // lalr1.cc:919
    {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::AuthType());
      }
#line 3929 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 263:
#line 2249 "seclang-parser.yy" // lalr1.cc:919
    {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::FilesCombinedSize());
      }
#line 3937 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 264:
#line 2253 "seclang-parser.yy" // lalr1.cc:919
    {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::FullRequest());
      }
#line 3945 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 265:
#line 2257 "seclang-parser.yy" // lalr1.cc:919
    {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::FullRequestLength());
      }
#line 3953 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 266:
#line 2261 "seclang-parser.yy" // lalr1.cc:919
    {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::InboundDataError());
      }
#line 3961 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 267:
#line 2265 "seclang-parser.yy" // lalr1.cc:919
    {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::MatchedVar());
      }
#line 3969 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 268:
#line 2269 "seclang-parser.yy" // lalr1.cc:919
    {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::MatchedVarName());
      }
#line 3977 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 269:
#line 2273 "seclang-parser.yy" // lalr1.cc:919
    {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::MultipartBoundaryQuoted());
      }
#line 3985 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 270:
#line 2277 "seclang-parser.yy" // lalr1.cc:919
    {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::MultipartBoundaryWhiteSpace());
      }
#line 3993 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 271:
#line 2281 "seclang-parser.yy" // lalr1.cc:919
    {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::MultipartCrlfLFLines());
      }
#line 4001 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 272:
#line 2285 "seclang-parser.yy" // lalr1.cc:919
    {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::MultipartDateAfter());
      }
#line 4009 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 273:
#line 2289 "seclang-parser.yy" // lalr1.cc:919
    {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::MultipartDateBefore());
      }
#line 4017 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 274:
#line 2293 "seclang-parser.yy" // lalr1.cc:919
    {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::MultipartFileLimitExceeded());
      }
#line 4025 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 275:
#line 2297 "seclang-parser.yy" // lalr1.cc:919
    {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::MultipartHeaderFolding());
      }
#line 4033 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 276:
#line 2301 "seclang-parser.yy" // lalr1.cc:919
    {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::MultipartInvalidHeaderFolding());
      }
#line 4041 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 277:
#line 2305 "seclang-parser.yy" // lalr1.cc:919
    {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::MultipartInvalidPart());
      }
#line 4049 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 278:
#line 2309 "seclang-parser.yy" // lalr1.cc:919
    {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::MultipartInvalidQuoting());
      }
#line 4057 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 279:
#line 2313 "seclang-parser.yy" // lalr1.cc:919
    {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::MultipartLFLine());
      }
#line 4065 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 280:
#line 2317 "seclang-parser.yy" // lalr1.cc:919
    {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::MultipartMissingSemicolon());
      }
#line 4073 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 281:
#line 2321 "seclang-parser.yy" // lalr1.cc:919
    {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::MultipartMissingSemicolon());
      }
#line 4081 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 282:
#line 2325 "seclang-parser.yy" // lalr1.cc:919
    {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::MultipartStrictError());
      }
#line 4089 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 283:
#line 2329 "seclang-parser.yy" // lalr1.cc:919
    {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::MultipartUnmatchedBoundary());
      }
#line 4097 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 284:
#line 2333 "seclang-parser.yy" // lalr1.cc:919
    {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::OutboundDataError());
      }
#line 4105 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 285:
#line 2337 "seclang-parser.yy" // lalr1.cc:919
    {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::PathInfo());
      }
#line 4113 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 286:
#line 2341 "seclang-parser.yy" // lalr1.cc:919
    {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::QueryString());
      }
#line 4121 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 287:
#line 2345 "seclang-parser.yy" // lalr1.cc:919
    {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::RemoteAddr());
      }
#line 4129 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 288:
#line 2349 "seclang-parser.yy" // lalr1.cc:919
    {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::RemoteHost());
      }
#line 4137 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 289:
#line 2353 "seclang-parser.yy" // lalr1.cc:919
    {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::RemotePort());
      }
#line 4145 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 290:
#line 2357 "seclang-parser.yy" // lalr1.cc:919
    {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::ReqbodyError());
      }
#line 4153 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 291:
#line 2361 "seclang-parser.yy" // lalr1.cc:919
    {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::ReqbodyErrorMsg());
      }
#line 4161 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 292:
#line 2365 "seclang-parser.yy" // lalr1.cc:919
    {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::ReqbodyProcessor());
      }
#line 4169 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 293:
#line 2369 "seclang-parser.yy" // lalr1.cc:919
    {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::ReqbodyProcessorError());
      }
#line 4177 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 294:
#line 2373 "seclang-parser.yy" // lalr1.cc:919
    {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::ReqbodyProcessorErrorMsg());
      }
#line 4185 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 295:
#line 2377 "seclang-parser.yy" // lalr1.cc:919
    {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::RequestBasename());
      }
#line 4193 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 296:
#line 2381 "seclang-parser.yy" // lalr1.cc:919
    {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::RequestBody());
      }
#line 4201 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 297:
#line 2385 "seclang-parser.yy" // lalr1.cc:919
    {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::RequestBodyLength());
      }
#line 4209 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 298:
#line 2389 "seclang-parser.yy" // lalr1.cc:919
    {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::RequestFilename());
      }
#line 4217 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 299:
#line 2393 "seclang-parser.yy" // lalr1.cc:919
    {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::RequestLine());
      }
#line 4225 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 300:
#line 2397 "seclang-parser.yy" // lalr1.cc:919
    {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::RequestMethod());
      }
#line 4233 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 301:
#line 2401 "seclang-parser.yy" // lalr1.cc:919
    {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::RequestProtocol());
      }
#line 4241 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 302:
#line 2405 "seclang-parser.yy" // lalr1.cc:919
    {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::RequestURI());
      }
#line 4249 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 303:
#line 2409 "seclang-parser.yy" // lalr1.cc:919
    {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::RequestURIRaw());
      }
#line 4257 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 304:
#line 2413 "seclang-parser.yy" // lalr1.cc:919
    {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::ResponseBody());
      }
#line 4265 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 305:
#line 2417 "seclang-parser.yy" // lalr1.cc:919
    {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::ResponseContentLength());
      }
#line 4273 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 306:
#line 2421 "seclang-parser.yy" // lalr1.cc:919
    {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::ResponseProtocol());
      }
#line 4281 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 307:
#line 2425 "seclang-parser.yy" // lalr1.cc:919
    {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::ResponseStatus());
      }
#line 4289 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 308:
#line 2429 "seclang-parser.yy" // lalr1.cc:919
    {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::ServerAddr());
      }
#line 4297 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 309:
#line 2433 "seclang-parser.yy" // lalr1.cc:919
    {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::ServerName());
      }
#line 4305 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 310:
#line 2437 "seclang-parser.yy" // lalr1.cc:919
    {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::ServerPort());
      }
#line 4313 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 311:
#line 2441 "seclang-parser.yy" // lalr1.cc:919
    {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::SessionID());
      }
#line 4321 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 312:
#line 2445 "seclang-parser.yy" // lalr1.cc:919
    {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::UniqueID());
      }
#line 4329 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 313:
#line 2449 "seclang-parser.yy" // lalr1.cc:919
    {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::UrlEncodedError());
      }
#line 4337 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 314:
#line 2453 "seclang-parser.yy" // lalr1.cc:919
    {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::UserID());
      }
#line 4345 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 315:
#line 2457 "seclang-parser.yy" // lalr1.cc:919
    {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::Status());
      }
#line 4353 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 316:
#line 2461 "seclang-parser.yy" // lalr1.cc:919
    {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::Status());
      }
#line 4361 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 317:
#line 2465 "seclang-parser.yy" // lalr1.cc:919
    {
        VARIABLE_CONTAINER(yylhs.value.as < std::unique_ptr<Variable> > (), new variables::WebAppId());
      }
#line 4369 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 318:
#line 2469 "seclang-parser.yy" // lalr1.cc:919
    {
        std::string name(yystack_[0].value.as < std::string > ());
        char z = name.at(0);
        std::unique_ptr<Variable> c(new Duration(name));
        yylhs.value.as < std::unique_ptr<Variable> > () = std::move(c);
      }
#line 4380 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 319:
#line 2477 "seclang-parser.yy" // lalr1.cc:919
    {
        std::string name(yystack_[0].value.as < std::string > ());
        char z = name.at(0);
        std::unique_ptr<Variable> c(new ModsecBuild(name));
        yylhs.value.as < std::unique_ptr<Variable> > () = std::move(c);
      }
#line 4391 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 320:
#line 2484 "seclang-parser.yy" // lalr1.cc:919
    {
        std::string name(yystack_[0].value.as < std::string > ());
        char z = name.at(0);
        std::unique_ptr<Variable> c(new HighestSeverity(name));
        yylhs.value.as < std::unique_ptr<Variable> > () = std::move(c);
      }
#line 4402 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 321:
#line 2491 "seclang-parser.yy" // lalr1.cc:919
    {
        std::string name(yystack_[0].value.as < std::string > ());
        char z = name.at(0);
        std::unique_ptr<Variable> c(new RemoteUser(name));
        yylhs.value.as < std::unique_ptr<Variable> > () = std::move(c);
      }
#line 4413 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 322:
#line 2498 "seclang-parser.yy" // lalr1.cc:919
    {
        std::string name(yystack_[0].value.as < std::string > ());
        char z = name.at(0);
        std::unique_ptr<Variable> c(new Time(name));
        yylhs.value.as < std::unique_ptr<Variable> > () = std::move(c);
      }
#line 4424 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 323:
#line 2505 "seclang-parser.yy" // lalr1.cc:919
    {
        std::string name(yystack_[0].value.as < std::string > ());
        char z = name.at(0);
        std::unique_ptr<Variable> c(new TimeDay(name));
        yylhs.value.as < std::unique_ptr<Variable> > () = std::move(c);
      }
#line 4435 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 324:
#line 2512 "seclang-parser.yy" // lalr1.cc:919
    {
        std::string name(yystack_[0].value.as < std::string > ());
        char z = name.at(0);
        std::unique_ptr<Variable> c(new TimeEpoch(name));
        yylhs.value.as < std::unique_ptr<Variable> > () = std::move(c);
      }
#line 4446 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 325:
#line 2519 "seclang-parser.yy" // lalr1.cc:919
    {
        std::string name(yystack_[0].value.as < std::string > ());
        char z = name.at(0);
        std::unique_ptr<Variable> c(new TimeHour(name));
        yylhs.value.as < std::unique_ptr<Variable> > () = std::move(c);
      }
#line 4457 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 326:
#line 2526 "seclang-parser.yy" // lalr1.cc:919
    {
        std::string name(yystack_[0].value.as < std::string > ());
        char z = name.at(0);
        std::unique_ptr<Variable> c(new TimeMin(name));
        yylhs.value.as < std::unique_ptr<Variable> > () = std::move(c);
      }
#line 4468 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 327:
#line 2533 "seclang-parser.yy" // lalr1.cc:919
    {
        std::string name(yystack_[0].value.as < std::string > ());
        char z = name.at(0);
        std::unique_ptr<Variable> c(new TimeMon(name));
        yylhs.value.as < std::unique_ptr<Variable> > () = std::move(c);
      }
#line 4479 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 328:
#line 2540 "seclang-parser.yy" // lalr1.cc:919
    {
        std::string name(yystack_[0].value.as < std::string > ());
        char z = name.at(0);
            std::unique_ptr<Variable> c(new TimeSec(name));
            yylhs.value.as < std::unique_ptr<Variable> > () = std::move(c);
      }
#line 4490 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 329:
#line 2547 "seclang-parser.yy" // lalr1.cc:919
    {
        std::string name(yystack_[0].value.as < std::string > ());
        char z = name.at(0);
        std::unique_ptr<Variable> c(new TimeWDay(name));
        yylhs.value.as < std::unique_ptr<Variable> > () = std::move(c);
      }
#line 4501 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 330:
#line 2554 "seclang-parser.yy" // lalr1.cc:919
    {
        std::string name(yystack_[0].value.as < std::string > ());
        char z = name.at(0);
        std::unique_ptr<Variable> c(new TimeYear(name));
        yylhs.value.as < std::unique_ptr<Variable> > () = std::move(c);
      }
#line 4512 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 331:
#line 2564 "seclang-parser.yy" // lalr1.cc:919
    {
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::Accuracy(yystack_[0].value.as < std::string > ()));
      }
#line 4520 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 332:
#line 2568 "seclang-parser.yy" // lalr1.cc:919
    {
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::disruptive::Allow(yystack_[0].value.as < std::string > ()));
      }
#line 4528 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 333:
#line 2572 "seclang-parser.yy" // lalr1.cc:919
    {
        ACTION_NOT_SUPPORTED("Append", yystack_[1].location);
      }
#line 4536 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 334:
#line 2576 "seclang-parser.yy" // lalr1.cc:919
    {
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::AuditLog(yystack_[0].value.as < std::string > ()));
      }
#line 4544 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 335:
#line 2580 "seclang-parser.yy" // lalr1.cc:919
    {
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::Block(yystack_[0].value.as < std::string > ()));
      }
#line 4552 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 336:
#line 2584 "seclang-parser.yy" // lalr1.cc:919
    {
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::Capture(yystack_[0].value.as < std::string > ()));
      }
#line 4560 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 337:
#line 2588 "seclang-parser.yy" // lalr1.cc:919
    {
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::Chain(yystack_[0].value.as < std::string > ()));
      }
#line 4568 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 338:
#line 2592 "seclang-parser.yy" // lalr1.cc:919
    {
        //ACTION_NOT_SUPPORTED("CtlAuditEngine", @0);
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::Action(yystack_[1].value.as < std::string > ()));
      }
#line 4577 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 339:
#line 2597 "seclang-parser.yy" // lalr1.cc:919
    {
        //ACTION_NOT_SUPPORTED("CtlAuditEngine", @0);
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::Action(yystack_[1].value.as < std::string > ()));
      }
#line 4586 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 340:
#line 2602 "seclang-parser.yy" // lalr1.cc:919
    {
        //ACTION_NOT_SUPPORTED("CtlAuditEngine", @0);
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::Action(yystack_[1].value.as < std::string > ()));
      }
#line 4595 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 341:
#line 2607 "seclang-parser.yy" // lalr1.cc:919
    {
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::ctl::AuditLogParts(yystack_[0].value.as < std::string > ()));
      }
#line 4603 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 342:
#line 2611 "seclang-parser.yy" // lalr1.cc:919
    {
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::ctl::RequestBodyProcessorJSON(yystack_[0].value.as < std::string > ()));
      }
#line 4611 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 343:
#line 2615 "seclang-parser.yy" // lalr1.cc:919
    {
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::ctl::RequestBodyProcessorXML(yystack_[0].value.as < std::string > ()));
      }
#line 4619 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 344:
#line 2619 "seclang-parser.yy" // lalr1.cc:919
    {
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::ctl::RequestBodyProcessorURLENCODED(yystack_[0].value.as < std::string > ()));
      }
#line 4627 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 345:
#line 2623 "seclang-parser.yy" // lalr1.cc:919
    {
        //ACTION_NOT_SUPPORTED("CtlForceReequestBody", @0);
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::Action(yystack_[1].value.as < std::string > ()));
      }
#line 4636 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 346:
#line 2628 "seclang-parser.yy" // lalr1.cc:919
    {
        //ACTION_NOT_SUPPORTED("CtlForceReequestBody", @0);
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::Action(yystack_[1].value.as < std::string > ()));
      }
#line 4645 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 347:
#line 2633 "seclang-parser.yy" // lalr1.cc:919
    {
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::ctl::RequestBodyAccess(yystack_[1].value.as < std::string > () + "true"));
      }
#line 4653 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 348:
#line 2637 "seclang-parser.yy" // lalr1.cc:919
    {
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::ctl::RequestBodyAccess(yystack_[1].value.as < std::string > () + "false"));
      }
#line 4661 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 349:
#line 2641 "seclang-parser.yy" // lalr1.cc:919
    {
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::ctl::RuleEngine("ctl:RuleEngine=on"));
      }
#line 4669 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 350:
#line 2645 "seclang-parser.yy" // lalr1.cc:919
    {
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::ctl::RuleEngine("ctl:RuleEngine=off"));
      }
#line 4677 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 351:
#line 2649 "seclang-parser.yy" // lalr1.cc:919
    {
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::ctl::RuleEngine("ctl:RuleEngine=detectiononly"));
      }
#line 4685 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 352:
#line 2653 "seclang-parser.yy" // lalr1.cc:919
    {
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::ctl::RuleRemoveById(yystack_[0].value.as < std::string > ()));
      }
#line 4693 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 353:
#line 2657 "seclang-parser.yy" // lalr1.cc:919
    {
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::ctl::RuleRemoveByTag(yystack_[0].value.as < std::string > ()));
      }
#line 4701 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 354:
#line 2661 "seclang-parser.yy" // lalr1.cc:919
    {
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::ctl::RuleRemoveTargetById(yystack_[0].value.as < std::string > ()));
      }
#line 4709 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 355:
#line 2665 "seclang-parser.yy" // lalr1.cc:919
    {
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::ctl::RuleRemoveTargetByTag(yystack_[0].value.as < std::string > ()));
      }
#line 4717 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 356:
#line 2669 "seclang-parser.yy" // lalr1.cc:919
    {
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::disruptive::Deny(yystack_[0].value.as < std::string > ()));
      }
#line 4725 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 357:
#line 2673 "seclang-parser.yy" // lalr1.cc:919
    {
        ACTION_NOT_SUPPORTED("DeprecateVar", yystack_[1].location);
      }
#line 4733 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 358:
#line 2677 "seclang-parser.yy" // lalr1.cc:919
    {
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::disruptive::Drop(yystack_[0].value.as < std::string > ()));
      }
#line 4741 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 359:
#line 2681 "seclang-parser.yy" // lalr1.cc:919
    {
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::Exec(yystack_[0].value.as < std::string > ()));
      }
#line 4749 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 360:
#line 2685 "seclang-parser.yy" // lalr1.cc:919
    {
        //ACTION_NOT_SUPPORTED("ExpireVar", @0);
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::Action(yystack_[0].value.as < std::string > ()));
      }
#line 4758 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 361:
#line 2690 "seclang-parser.yy" // lalr1.cc:919
    {
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::RuleId(yystack_[0].value.as < std::string > ()));
      }
#line 4766 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 362:
#line 2694 "seclang-parser.yy" // lalr1.cc:919
    {
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::InitCol(yystack_[1].value.as < std::string > (), std::move(yystack_[0].value.as < std::unique_ptr<RunTimeString> > ())));
      }
#line 4774 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 363:
#line 2698 "seclang-parser.yy" // lalr1.cc:919
    {
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::LogData(std::move(yystack_[0].value.as < std::unique_ptr<RunTimeString> > ())));
      }
#line 4782 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 364:
#line 2702 "seclang-parser.yy" // lalr1.cc:919
    {
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::Log(yystack_[0].value.as < std::string > ()));
      }
#line 4790 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 365:
#line 2706 "seclang-parser.yy" // lalr1.cc:919
    {
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::Maturity(yystack_[0].value.as < std::string > ()));
      }
#line 4798 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 366:
#line 2710 "seclang-parser.yy" // lalr1.cc:919
    {
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::Msg(std::move(yystack_[0].value.as < std::unique_ptr<RunTimeString> > ())));
      }
#line 4806 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 367:
#line 2714 "seclang-parser.yy" // lalr1.cc:919
    {
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::MultiMatch(yystack_[0].value.as < std::string > ()));
      }
#line 4814 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 368:
#line 2718 "seclang-parser.yy" // lalr1.cc:919
    {
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::NoAuditLog(yystack_[0].value.as < std::string > ()));
      }
#line 4822 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 369:
#line 2722 "seclang-parser.yy" // lalr1.cc:919
    {
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::NoLog(yystack_[0].value.as < std::string > ()));
      }
#line 4830 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 370:
#line 2726 "seclang-parser.yy" // lalr1.cc:919
    {
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::disruptive::Pass(yystack_[0].value.as < std::string > ()));
      }
#line 4838 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 371:
#line 2730 "seclang-parser.yy" // lalr1.cc:919
    {
        ACTION_NOT_SUPPORTED("Pause", yystack_[1].location);
      }
#line 4846 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 372:
#line 2734 "seclang-parser.yy" // lalr1.cc:919
    {
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::Phase(yystack_[0].value.as < std::string > ()));
      }
#line 4854 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 373:
#line 2738 "seclang-parser.yy" // lalr1.cc:919
    {
        ACTION_NOT_SUPPORTED("Prepend", yystack_[1].location);
      }
#line 4862 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 374:
#line 2742 "seclang-parser.yy" // lalr1.cc:919
    {
        ACTION_NOT_SUPPORTED("Proxy", yystack_[1].location);
      }
#line 4870 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 375:
#line 2746 "seclang-parser.yy" // lalr1.cc:919
    {
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::disruptive::Redirect(std::move(yystack_[0].value.as < std::unique_ptr<RunTimeString> > ())));
      }
#line 4878 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 376:
#line 2750 "seclang-parser.yy" // lalr1.cc:919
    {
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::Rev(yystack_[0].value.as < std::string > ()));
      }
#line 4886 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 377:
#line 2754 "seclang-parser.yy" // lalr1.cc:919
    {
        ACTION_NOT_SUPPORTED("SanitiseArg", yystack_[1].location);
      }
#line 4894 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 378:
#line 2758 "seclang-parser.yy" // lalr1.cc:919
    {
        ACTION_NOT_SUPPORTED("SanitiseMatched", yystack_[1].location);
      }
#line 4902 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 379:
#line 2762 "seclang-parser.yy" // lalr1.cc:919
    {
        ACTION_NOT_SUPPORTED("SanitiseMatchedBytes", yystack_[1].location);
      }
#line 4910 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 380:
#line 2766 "seclang-parser.yy" // lalr1.cc:919
    {
        ACTION_NOT_SUPPORTED("SanitiseRequestHeader", yystack_[1].location);
      }
#line 4918 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 381:
#line 2770 "seclang-parser.yy" // lalr1.cc:919
    {
        ACTION_NOT_SUPPORTED("SanitiseResponseHeader", yystack_[1].location);
      }
#line 4926 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 382:
#line 2774 "seclang-parser.yy" // lalr1.cc:919
    {
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::SetENV(std::move(yystack_[0].value.as < std::unique_ptr<RunTimeString> > ())));
      }
#line 4934 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 383:
#line 2778 "seclang-parser.yy" // lalr1.cc:919
    {
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::SetRSC(std::move(yystack_[0].value.as < std::unique_ptr<RunTimeString> > ())));
      }
#line 4942 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 384:
#line 2782 "seclang-parser.yy" // lalr1.cc:919
    {
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::SetSID(std::move(yystack_[0].value.as < std::unique_ptr<RunTimeString> > ())));
      }
#line 4950 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 385:
#line 2786 "seclang-parser.yy" // lalr1.cc:919
    {
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::SetUID(std::move(yystack_[0].value.as < std::unique_ptr<RunTimeString> > ())));
      }
#line 4958 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 386:
#line 2790 "seclang-parser.yy" // lalr1.cc:919
    {
        yylhs.value.as < std::unique_ptr<actions::Action> > () = std::move(yystack_[0].value.as < std::unique_ptr<actions::Action> > ());
      }
#line 4966 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 387:
#line 2794 "seclang-parser.yy" // lalr1.cc:919
    {
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::Severity(yystack_[0].value.as < std::string > ()));
      }
#line 4974 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 388:
#line 2798 "seclang-parser.yy" // lalr1.cc:919
    {
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::Skip(yystack_[0].value.as < std::string > ()));
      }
#line 4982 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 389:
#line 2802 "seclang-parser.yy" // lalr1.cc:919
    {
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::SkipAfter(yystack_[0].value.as < std::string > ()));
      }
#line 4990 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 390:
#line 2806 "seclang-parser.yy" // lalr1.cc:919
    {
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::data::Status(yystack_[0].value.as < std::string > ()));
      }
#line 4998 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 391:
#line 2810 "seclang-parser.yy" // lalr1.cc:919
    {
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::Tag(std::move(yystack_[0].value.as < std::unique_ptr<RunTimeString> > ())));
      }
#line 5006 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 392:
#line 2814 "seclang-parser.yy" // lalr1.cc:919
    {
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::Ver(yystack_[0].value.as < std::string > ()));
      }
#line 5014 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 393:
#line 2818 "seclang-parser.yy" // lalr1.cc:919
    {
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::XmlNS(yystack_[0].value.as < std::string > ()));
      }
#line 5022 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 394:
#line 2822 "seclang-parser.yy" // lalr1.cc:919
    {
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::transformations::ParityZero7bit(yystack_[0].value.as < std::string > ()));
      }
#line 5030 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 395:
#line 2826 "seclang-parser.yy" // lalr1.cc:919
    {
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::transformations::ParityOdd7bit(yystack_[0].value.as < std::string > ()));
      }
#line 5038 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 396:
#line 2830 "seclang-parser.yy" // lalr1.cc:919
    {
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::transformations::ParityEven7bit(yystack_[0].value.as < std::string > ()));
      }
#line 5046 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 397:
#line 2834 "seclang-parser.yy" // lalr1.cc:919
    {
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::transformations::SqlHexDecode(yystack_[0].value.as < std::string > ()));
      }
#line 5054 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 398:
#line 2838 "seclang-parser.yy" // lalr1.cc:919
    {
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::transformations::Base64Encode(yystack_[0].value.as < std::string > ()));
      }
#line 5062 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 399:
#line 2842 "seclang-parser.yy" // lalr1.cc:919
    {
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::transformations::Base64Decode(yystack_[0].value.as < std::string > ()));
      }
#line 5070 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 400:
#line 2846 "seclang-parser.yy" // lalr1.cc:919
    {
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::transformations::Base64DecodeExt(yystack_[0].value.as < std::string > ()));
      }
#line 5078 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 401:
#line 2850 "seclang-parser.yy" // lalr1.cc:919
    {
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::transformations::CmdLine(yystack_[0].value.as < std::string > ()));
      }
#line 5086 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 402:
#line 2854 "seclang-parser.yy" // lalr1.cc:919
    {
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::transformations::Sha1(yystack_[0].value.as < std::string > ()));
      }
#line 5094 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 403:
#line 2858 "seclang-parser.yy" // lalr1.cc:919
    {
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::transformations::Md5(yystack_[0].value.as < std::string > ()));
      }
#line 5102 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 404:
#line 2862 "seclang-parser.yy" // lalr1.cc:919
    {
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::transformations::EscapeSeqDecode(yystack_[0].value.as < std::string > ()));
      }
#line 5110 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 405:
#line 2866 "seclang-parser.yy" // lalr1.cc:919
    {
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::transformations::HexEncode(yystack_[0].value.as < std::string > ()));
      }
#line 5118 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 406:
#line 2870 "seclang-parser.yy" // lalr1.cc:919
    {
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::transformations::HexDecode(yystack_[0].value.as < std::string > ()));
      }
#line 5126 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 407:
#line 2874 "seclang-parser.yy" // lalr1.cc:919
    {
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::transformations::LowerCase(yystack_[0].value.as < std::string > ()));
      }
#line 5134 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 408:
#line 2878 "seclang-parser.yy" // lalr1.cc:919
    {
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::transformations::UpperCase(yystack_[0].value.as < std::string > ()));
      }
#line 5142 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 409:
#line 2882 "seclang-parser.yy" // lalr1.cc:919
    {
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::transformations::UrlDecodeUni(yystack_[0].value.as < std::string > ()));
      }
#line 5150 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 410:
#line 2886 "seclang-parser.yy" // lalr1.cc:919
    {
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::transformations::UrlDecode(yystack_[0].value.as < std::string > ()));
      }
#line 5158 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 411:
#line 2890 "seclang-parser.yy" // lalr1.cc:919
    {
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::transformations::UrlEncode(yystack_[0].value.as < std::string > ()));
      }
#line 5166 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 412:
#line 2894 "seclang-parser.yy" // lalr1.cc:919
    {
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::transformations::None(yystack_[0].value.as < std::string > ()));
      }
#line 5174 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 413:
#line 2898 "seclang-parser.yy" // lalr1.cc:919
    {
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::transformations::CompressWhitespace(yystack_[0].value.as < std::string > ()));
      }
#line 5182 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 414:
#line 2902 "seclang-parser.yy" // lalr1.cc:919
    {
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::transformations::RemoveWhitespace(yystack_[0].value.as < std::string > ()));
      }
#line 5190 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 415:
#line 2906 "seclang-parser.yy" // lalr1.cc:919
    {
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::transformations::ReplaceNulls(yystack_[0].value.as < std::string > ()));
      }
#line 5198 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 416:
#line 2910 "seclang-parser.yy" // lalr1.cc:919
    {
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::transformations::RemoveNulls(yystack_[0].value.as < std::string > ()));
      }
#line 5206 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 417:
#line 2914 "seclang-parser.yy" // lalr1.cc:919
    {
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::transformations::HtmlEntityDecode(yystack_[0].value.as < std::string > ()));
      }
#line 5214 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 418:
#line 2918 "seclang-parser.yy" // lalr1.cc:919
    {
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::transformations::JsDecode(yystack_[0].value.as < std::string > ()));
      }
#line 5222 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 419:
#line 2922 "seclang-parser.yy" // lalr1.cc:919
    {
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::transformations::CssDecode(yystack_[0].value.as < std::string > ()));
      }
#line 5230 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 420:
#line 2926 "seclang-parser.yy" // lalr1.cc:919
    {
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::transformations::Trim(yystack_[0].value.as < std::string > ()));
      }
#line 5238 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 421:
#line 2930 "seclang-parser.yy" // lalr1.cc:919
    {
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::transformations::TrimLeft(yystack_[0].value.as < std::string > ()));
      }
#line 5246 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 422:
#line 2934 "seclang-parser.yy" // lalr1.cc:919
    {
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::transformations::TrimRight(yystack_[0].value.as < std::string > ()));
      }
#line 5254 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 423:
#line 2938 "seclang-parser.yy" // lalr1.cc:919
    {
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::transformations::NormalisePathWin(yystack_[0].value.as < std::string > ()));
      }
#line 5262 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 424:
#line 2942 "seclang-parser.yy" // lalr1.cc:919
    {
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::transformations::NormalisePath(yystack_[0].value.as < std::string > ()));
      }
#line 5270 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 425:
#line 2946 "seclang-parser.yy" // lalr1.cc:919
    {
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::transformations::Length(yystack_[0].value.as < std::string > ()));
      }
#line 5278 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 426:
#line 2950 "seclang-parser.yy" // lalr1.cc:919
    {
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::transformations::Utf8ToUnicode(yystack_[0].value.as < std::string > ()));
      }
#line 5286 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 427:
#line 2954 "seclang-parser.yy" // lalr1.cc:919
    {
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::transformations::RemoveCommentsChar(yystack_[0].value.as < std::string > ()));
      }
#line 5294 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 428:
#line 2958 "seclang-parser.yy" // lalr1.cc:919
    {
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::transformations::RemoveComments(yystack_[0].value.as < std::string > ()));
      }
#line 5302 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 429:
#line 2962 "seclang-parser.yy" // lalr1.cc:919
    {
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::transformations::ReplaceComments(yystack_[0].value.as < std::string > ()));
      }
#line 5310 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 430:
#line 2969 "seclang-parser.yy" // lalr1.cc:919
    {
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::SetVar(actions::SetVarOperation::unsetOperation, std::move(yystack_[0].value.as < std::unique_ptr<Variable> > ())));
      }
#line 5318 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 431:
#line 2973 "seclang-parser.yy" // lalr1.cc:919
    {
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::SetVar(actions::SetVarOperation::setToOneOperation, std::move(yystack_[0].value.as < std::unique_ptr<Variable> > ())));
      }
#line 5326 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 432:
#line 2977 "seclang-parser.yy" // lalr1.cc:919
    {
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::SetVar(actions::SetVarOperation::setOperation, std::move(yystack_[2].value.as < std::unique_ptr<Variable> > ()), std::move(yystack_[0].value.as < std::unique_ptr<RunTimeString> > ())));
      }
#line 5334 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 433:
#line 2981 "seclang-parser.yy" // lalr1.cc:919
    {
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::SetVar(actions::SetVarOperation::sumAndSetOperation, std::move(yystack_[2].value.as < std::unique_ptr<Variable> > ()), std::move(yystack_[0].value.as < std::unique_ptr<RunTimeString> > ())));
      }
#line 5342 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 434:
#line 2985 "seclang-parser.yy" // lalr1.cc:919
    {
        ACTION_CONTAINER(yylhs.value.as < std::unique_ptr<actions::Action> > (), new actions::SetVar(actions::SetVarOperation::substractAndSetOperation, std::move(yystack_[2].value.as < std::unique_ptr<Variable> > ()), std::move(yystack_[0].value.as < std::unique_ptr<RunTimeString> > ())));
      }
#line 5350 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 435:
#line 2992 "seclang-parser.yy" // lalr1.cc:919
    {
        yystack_[1].value.as < std::unique_ptr<RunTimeString> > ()->appendText(yystack_[0].value.as < std::string > ());
        yylhs.value.as < std::unique_ptr<RunTimeString> > () = std::move(yystack_[1].value.as < std::unique_ptr<RunTimeString> > ());
      }
#line 5359 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 436:
#line 2997 "seclang-parser.yy" // lalr1.cc:919
    {
        yystack_[1].value.as < std::unique_ptr<RunTimeString> > ()->appendVar(std::move(yystack_[0].value.as < std::unique_ptr<Variable> > ()));
        yylhs.value.as < std::unique_ptr<RunTimeString> > () = std::move(yystack_[1].value.as < std::unique_ptr<RunTimeString> > ());
      }
#line 5368 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 437:
#line 3002 "seclang-parser.yy" // lalr1.cc:919
    {
        std::unique_ptr<RunTimeString> r(new RunTimeString());
        r->appendText(yystack_[0].value.as < std::string > ());
        yylhs.value.as < std::unique_ptr<RunTimeString> > () = std::move(r);
      }
#line 5378 "seclang-parser.cc" // lalr1.cc:919
    break;

  case 438:
#line 3008 "seclang-parser.yy" // lalr1.cc:919
    {
        std::unique_ptr<RunTimeString> r(new RunTimeString());
        r->appendVar(std::move(yystack_[0].value.as < std::unique_ptr<Variable> > ()));
        yylhs.value.as < std::unique_ptr<RunTimeString> > () = std::move(r);
      }
#line 5388 "seclang-parser.cc" // lalr1.cc:919
    break;


#line 5392 "seclang-parser.cc" // lalr1.cc:919
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
      YY_STACK_PRINT ();

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
        error (yyla.location, yysyntax_error_ (yystack_[0].state, yyla));
      }


    yyerror_range[1].location = yyla.location;
    if (yyerrstatus_ == 3)
      {
        /* If just tried and failed to reuse lookahead token after an
           error, discard it.  */

        // Return failure if at end of input.
        if (yyla.type_get () == yyeof_)
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
    goto yyerrlab1;


  /*-------------------------------------------------------------.
  | yyerrlab1 -- common code for both syntax error and YYERROR.  |
  `-------------------------------------------------------------*/
  yyerrlab1:
    yyerrstatus_ = 3;   // Each real token shifted decrements this.
    {
      stack_symbol_type error_token;
      for (;;)
        {
          yyn = yypact_[yystack_[0].state];
          if (!yy_pact_value_is_default_ (yyn))
            {
              yyn += yyterror_;
              if (0 <= yyn && yyn <= yylast_ && yycheck_[yyn] == yyterror_)
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

      yyerror_range[2].location = yyla.location;
      YYLLOC_DEFAULT (error_token.location, yyerror_range, 2);

      // Shift the error token.
      error_token.state = yyn;
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

  // Generate an error message.
  std::string
  seclang_parser::yysyntax_error_ (state_type yystate, const symbol_type& yyla) const
  {
    // Number of reported tokens (one for the "unexpected", one per
    // "expected").
    size_t yycount = 0;
    // Its maximum.
    enum { YYERROR_VERBOSE_ARGS_MAXIMUM = 5 };
    // Arguments of yyformat.
    char const *yyarg[YYERROR_VERBOSE_ARGS_MAXIMUM];

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
         scanner and before detecting a syntax error.  Thus, state
         merging (from LALR or IELR) and default reductions corrupt the
         expected token list.  However, the list is correct for
         canonical LR with one exception: it will still contain any
         token that will not be accepted due to an error action in a
         later state.
    */
    if (!yyla.empty ())
      {
        int yytoken = yyla.type_get ();
        yyarg[yycount++] = yytname_[yytoken];
        int yyn = yypact_[yystate];
        if (!yy_pact_value_is_default_ (yyn))
          {
            /* Start YYX at -YYN if negative to avoid negative indexes in
               YYCHECK.  In other words, skip the first -YYN actions for
               this state because they are default actions.  */
            int yyxbegin = yyn < 0 ? -yyn : 0;
            // Stay within bounds of both yycheck and yytname.
            int yychecklim = yylast_ - yyn + 1;
            int yyxend = yychecklim < yyntokens_ ? yychecklim : yyntokens_;
            for (int yyx = yyxbegin; yyx < yyxend; ++yyx)
              if (yycheck_[yyx + yyn] == yyx && yyx != yyterror_
                  && !yy_table_value_is_error_ (yytable_[yyx + yyn]))
                {
                  if (yycount == YYERROR_VERBOSE_ARGS_MAXIMUM)
                    {
                      yycount = 1;
                      break;
                    }
                  else
                    yyarg[yycount++] = yytname_[yyx];
                }
          }
      }

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
    size_t yyi = 0;
    for (char const* yyp = yyformat; *yyp; ++yyp)
      if (yyp[0] == '%' && yyp[1] == 's' && yyi < yycount)
        {
          yyres += yytnamerr_ (yyarg[yyi++]);
          ++yyp;
        }
      else
        yyres += *yyp;
    return yyres;
  }


  const short seclang_parser::yypact_ninf_ = -404;

  const signed char seclang_parser::yytable_ninf_ = -1;

  const short
  seclang_parser::yypact_[] =
  {
    2743,  -404,  -252,  -404,     6,  -404,  -152,  -404,  -404,  -404,
    -404,  -404,  -272,  -404,  -404,  -404,  -404,  -404,  -287,  -404,
    -404,  -404,  -150,  -145,  -404,  -404,  -404,  -404,  -404,  -404,
    -404,  -404,  -404,  -404,  -404,  -404,  -404,  -143,  -404,  -404,
    -144,  -404,  -139,  -404,  -134,  -129,  -404,  -258,   -89,   -89,
    -404,  -404,  -404,  -404,  -127,  -297,  -404,  -404,  -404,  1475,
    1475,  1475,   -89,  -266,  -125,  -404,  -404,  -404,  -123,  -404,
    -404,  -404,  -404,  -404,  -404,  -404,  -404,  -404,  1475,   -89,
    2885,  -404,  -404,  -404,  -404,  -404,  -404,  -404,  -404,  -404,
    -404,  -404,  -404,  -404,  -404,  -404,  -404,  -404,  -404,  -404,
    -404,  -404,  -404,  -404,  -404,  -404,  -404,  -404,  -404,  -404,
    -404,  -404,  -404,  2313,  -254,  -404,  -404,  -404,  -404,  -404,
    -404,  -404,  -264,  -404,  -404,  -404,  -404,  -121,  -119,  -404,
    -404,  -404,  -404,  -404,  -404,  -404,  -404,  -404,  -404,  2444,
    -404,  2444,  -404,  2444,  -404,  -404,  -404,  -404,  -404,  -404,
    -404,  -404,  2444,  -404,  -404,  -404,  -404,  -404,  -404,  2444,
    2444,  2444,  2444,  -404,  -404,  -404,  -404,  2444,  -404,  -404,
    -404,  -404,  -404,  -404,  -404,  -404,  -404,  -404,  -404,  -404,
    -404,  -404,  -404,  -404,  -404,  -404,  -404,  -404,  -404,  -404,
    -404,  -404,  -404,  -404,  -404,  -404,  -404,  -404,  -404,  -404,
    -404,  -404,  -404,  -404,  -404,  -404,  3069,  -404,     4,  -404,
    -404,  -404,  -404,  -404,  -404,  2641,  2641,  -153,  -151,  -149,
    -147,  -142,  -140,  -137,  -135,  -133,  -131,  -128,  -126,  -124,
    -122,  -120,  -118,  -404,  -116,  -114,  -112,  -110,  -404,  -404,
    -108,  -404,  -404,  -404,  -404,  -404,  -404,  -404,  -404,  -404,
    -404,  -404,  -404,  -404,  -404,  -404,  -404,  -404,  -404,  -404,
    -404,  -404,  -404,  -404,  -404,  -404,  -404,  -404,  -404,  -404,
    -404,  -404,  -404,  -404,  -404,  -404,  -106,  -404,  -404,  -404,
    -404,  -404,   455,  -404,  -404,  -404,  -103,  -404,  -404,  -404,
    -404,  -404,  -404,  -404,  -404,  -404,  -404,  -404,  -404,   544,
     633,   964,  1053,  1142,  -101,   -99,  1566,  -404,  -404,  -404,
    -404,  -404,  -404,  -404,  -404,  -404,  -404,  -404,  -404,  -404,
    -404,     8,  -404,  -404,  -404,  -404,  -404,  -404,  -404,  -404,
    -404,  -404,  -404,  1985,  -404,  -404,  -404,  -404,  2641,   -76,
    -404,  -404,  -404,  -404,  -404,  -404,  -404,  -404,  -404,  -404,
    -404,  -404,  -404,  2533,  2533,  2533,  2533,  2533,  2533,  2533,
    2533,  2533,     5,  3069,  -404,  -404,  -404,  -404,  -404,  -404,
    -404,  -404,  -404,  -404,  -404,  -404,  -404,  -404,  -404,  -404,
    -404,  -404,  -404,  -404,  -404,  -404,  -404,  -404,  -404,  -404,
    -404,  -404,  -404,  -404,  -404,  -404,  -404,  -404,  -404,  -404,
    -404,  -404,  -404,  -404,  -404,  -404,  -404,  -404,  -404,  -404,
    -404,  -404,  2533,  -404,  -404,  -404,  -404,  2533,  -404,  -404,
    2533,  -404,  -404,  2533,  -404,  -404,  2533,  -404,  -404,  2533,
    -404,  -404,  -404,  -404,    10,  1657,  2116,  2444,  2444,  2444,
    -404,  -404,  2444,  2444,  2444,  -404,  2444,  2444,  2444,  2444,
    2444,  2444,  2444,  2444,  2444,  2444,  2444,  2444,  2444,  2444,
    2444,  -404,  2444,  2444,  2444,  2444,  -404,  -404,  2444,  2444,
    2444,  2444,  2444,   -89,  -404,  2533,  -404,  2444,  2444,  2444,
    -404,  -404,  -404,  -404,  -404,  2641,  2641,  -404,  -404,  2533,
    2533,  2533,  2533,  2533,  2533,  2533,  2533,  2533,  2533,  2533,
    2533,  2533,  2533,  2533,  2533,  2533,  2533,  2533,  2533,  2533,
    2533,  2533,  2533,  2533,  2533,  2533,  2533,  2533,  2533,  2533,
    -404,  2533,  2533,  2533,  -404,  -404
  };

  const unsigned short
  seclang_parser::yydefact_[] =
  {
       0,     2,     0,   140,     0,    88,     0,    87,    91,    92,
       7,     6,     0,    11,    14,    12,    13,    17,     0,   125,
     124,    93,     0,     0,   101,   102,   103,   104,    98,   126,
     105,   106,   138,   137,   109,   110,   111,     0,   129,   127,
       0,   128,     0,   130,     0,     0,   114,     0,     0,     0,
      79,   149,   150,   151,     0,     0,   117,   119,   118,     0,
       0,     0,     0,     0,     0,    26,    24,    25,     0,   139,
     145,   146,   147,   144,   148,   115,   116,   143,     0,     0,
       0,     4,    73,     5,    97,    96,    15,    16,    90,    89,
       9,    10,     8,    20,    19,    18,    95,    94,   100,    99,
      84,    83,   131,   132,    86,    85,   133,   134,   113,   112,
      82,    80,    81,     0,     0,   331,   332,   333,   334,   335,
     336,   337,     0,   341,   342,   343,   344,     0,     0,   352,
     353,   354,   355,   356,   357,   358,   359,   360,   361,     0,
     364,     0,   365,     0,   367,   368,   369,   370,   371,   372,
     373,   374,     0,   376,   377,   378,   379,   380,   381,     0,
       0,     0,     0,   387,   388,   389,   390,     0,   398,   399,
     400,   401,   413,   419,   404,   405,   406,   417,   418,   425,
     407,   403,   412,   424,   423,   396,   395,   394,   428,   427,
     416,   414,   429,   415,   402,   397,   420,   421,   422,   408,
     411,   410,   409,   426,   392,   393,     0,    76,    30,    32,
      78,   108,   107,   135,   136,     0,     0,   163,   166,   169,
     172,   175,   178,   181,   184,   187,   190,   193,   196,   199,
     202,   205,   208,   261,   250,   211,   247,   253,   262,   263,
     220,   264,   265,   266,   267,   268,   269,   270,   271,   272,
     273,   274,   275,   276,   277,   278,   279,   280,   281,   282,
     283,   284,   285,   286,   287,   288,   289,   291,   290,   294,
     293,   292,   295,   297,   296,   298,   256,   299,   300,   301,
     303,   302,   224,   304,   305,   257,   260,   306,   307,   308,
     309,   310,   311,   312,   313,   314,   317,   315,   316,   228,
     232,   240,   244,   236,   214,   217,     0,   319,   318,   320,
     321,   322,   323,   324,   325,   326,   327,   328,   329,   330,
     120,   153,   158,   121,   122,   123,    22,    21,    23,    28,
      27,   141,   142,     0,   152,    77,     1,     3,     0,   431,
     386,   351,   350,   349,   339,   338,   340,   346,   345,   348,
     347,   437,   438,   362,   363,   366,   375,   382,   383,   384,
     385,   391,     0,     0,   160,   159,   161,   162,   164,   165,
     167,   168,   170,   171,   173,   174,   176,   177,   179,   180,
     182,   183,   185,   186,   188,   189,   191,   192,   194,   195,
     197,   198,   200,   201,   203,   204,   206,   207,   248,   249,
     209,   210,   245,   246,   251,   252,   218,   219,   254,   255,
     222,   223,   221,   258,   259,   226,   227,   225,   230,   231,
     229,   238,   239,   237,   242,   243,   241,   234,   235,   233,
     212,   213,   215,   216,     0,     0,     0,     0,     0,     0,
      38,    39,     0,     0,     0,    72,     0,     0,     0,     0,
       0,     0,     0,     0,     0,     0,     0,     0,     0,     0,
       0,    37,     0,     0,     0,     0,    40,    41,     0,     0,
       0,     0,     0,    75,    33,    35,   430,     0,     0,     0,
     435,   436,    29,    31,   154,     0,     0,   155,    34,    36,
      71,    56,    55,    57,    58,    43,    59,    52,    60,    42,
      61,    62,    63,    64,    65,    66,    67,    53,    68,    69,
      70,    44,    45,    46,    47,    48,    49,    50,    51,    54,
      74,   432,   433,   434,   157,   156
  };

  const short
  seclang_parser::yypgoto_[] =
  {
    -404,  -404,   -68,  -404,   -45,  -185,  -404,  -403,  -404,  -404,
     -55,  -265,   -59,  -315,  -404,  -132
  };

  const short
  seclang_parser::yydefgoto_[] =
  {
      -1,    80,    81,    82,   207,   208,   473,   474,    83,   333,
     320,   321,   352,   209,   340,   353
  };

  const unsigned short
  seclang_parser::yytable_[] =
  {
     322,   322,   322,   213,   210,   323,   324,   363,   363,   354,
     113,   355,   337,   214,   435,    93,   435,   325,    94,   322,
     356,   362,    95,   334,   477,   478,   479,   357,   358,   359,
     360,    90,    91,   488,   335,   361,    92,   326,   327,   344,
     345,   434,   328,   110,   346,   111,   112,   341,   483,   342,
     343,    84,    85,     0,   339,   114,   115,   116,   117,   118,
     119,   120,   121,   122,   123,   124,   125,   126,   127,   128,
     129,   130,   131,   132,   133,   134,   135,   136,   137,   138,
     139,   140,   141,   142,   143,   144,   145,   146,   147,   148,
     149,   150,   151,   152,   153,   154,   155,   156,   157,   158,
     159,   160,   161,   162,   163,   164,   165,   166,   167,   168,
     169,   170,   171,   172,   173,   174,   175,   176,   177,   178,
     179,   180,   181,   182,   183,   184,   185,   186,   187,   188,
     189,   190,   191,   192,   193,   194,   195,   196,   197,   198,
     199,   200,   201,   202,   203,   204,   205,     0,    86,    87,
     412,    88,    89,    96,    97,     0,   364,   365,    98,    99,
     100,   101,   102,   103,   104,   105,     0,   417,   420,   423,
     426,   429,   106,   107,   108,   109,   211,   212,   329,   330,
     331,   332,   347,   348,   349,   350,   366,   367,   368,   369,
     370,   371,   372,   373,     0,     0,     0,   374,   375,   376,
     377,   475,   378,   379,   380,   381,   382,   383,   384,   385,
       0,   386,   387,   388,   389,   390,   391,   392,   393,   394,
     395,   396,   397,   398,   399,   400,   401,   402,   403,   404,
     405,   406,   407,   408,   409,   206,   413,   414,   430,   431,
     432,   433,     0,     0,     0,     0,     0,   322,     0,     0,
       0,     0,     0,     0,     0,     0,     0,     0,     0,     0,
       0,     0,     0,     0,     0,     0,     0,     0,     0,     0,
       0,     0,     0,     0,     0,     0,     0,     0,     0,   476,
       0,     0,     0,     0,     0,     0,     0,     0,     0,     0,
       0,     0,     0,     0,   481,   481,   481,   481,   481,   481,
     481,   481,   481,     0,   489,   490,   491,   492,     0,     0,
     493,   494,   495,     0,   496,   497,   498,   499,   500,   501,
     502,   503,   504,   505,   506,   507,   508,   509,   510,   482,
     511,   512,   513,   514,   484,     0,   515,   516,   517,   518,
     519,     0,     0,     0,     0,   521,   522,   523,     0,     0,
       0,     0,     0,   481,     0,     0,     0,     0,   481,     0,
       0,   481,     0,     0,   481,     0,     0,   481,     0,     0,
     481,     0,     0,     0,     0,     0,   487,     0,     0,     0,
       0,     0,     0,     0,     0,     0,     0,     0,     0,     0,
       0,     0,     0,     0,     0,     0,     0,     0,     0,     0,
       0,     0,     0,     0,     0,     0,     0,     0,     0,     0,
       0,     0,     0,     0,     0,     0,   481,     0,     0,     0,
       0,     0,     0,     0,     0,     0,   524,   525,   520,     0,
     481,   481,   481,   481,   481,   481,   481,   481,   481,   481,
     481,   481,   481,   481,   481,   481,   481,   481,   481,   481,
     481,   481,   481,   481,   481,   481,   481,   481,   481,   481,
     481,     0,   481,   481,   481,   217,   218,   219,   220,   221,
     222,   223,   224,   225,   226,   227,   228,   229,   230,   231,
     232,   233,   234,   235,   236,   237,   238,   239,   240,   241,
     242,   243,   244,   245,   246,   247,   248,   249,   250,   251,
     252,   253,   254,   255,   256,   257,   258,   259,   260,   261,
     262,   263,   264,   265,   266,   267,   268,   269,   270,   271,
     272,   273,   274,   275,   276,   277,   278,   279,   280,   281,
     282,   283,   284,   285,   286,   287,   288,   289,   290,   291,
     292,   293,   294,   295,   296,   297,   298,   299,   300,   301,
     302,   303,   304,   305,   217,   218,   219,   220,   221,   222,
     223,   224,   225,   226,   227,   228,   229,   230,   231,   232,
     233,   234,   235,   236,   237,   238,   239,   240,   241,   242,
     243,   244,   245,   246,   247,   248,   249,   250,   251,   252,
     253,   254,   255,   256,   257,   258,   259,   260,   261,   262,
     263,   264,   265,   266,   267,   268,   269,   270,   271,   272,
     273,   274,   275,   276,   277,   278,   279,   280,   281,   282,
     283,   284,   285,   286,   287,   288,   289,   290,   291,   292,
     293,   294,   295,   296,   297,   298,   299,   300,   301,   302,
     303,   304,   305,   217,   218,   219,   220,   221,   222,   223,
     224,   225,   226,   227,   228,   229,   230,   231,   232,   233,
     234,   235,   236,   237,   238,   239,   240,   241,   242,   243,
     244,   245,   246,   247,   248,   249,   250,   251,   252,   253,
     254,   255,   256,   257,   258,   259,   260,   261,   262,   263,
     264,   265,   266,   267,   268,   269,   270,   271,   272,   273,
     274,   275,   276,   277,   278,   279,   280,   281,   282,   283,
     284,   285,   286,   287,   288,   289,   290,   291,   292,   293,
     294,   295,   296,   297,   298,   299,   300,   301,   302,   303,
     304,   305,     0,     0,     0,     0,     0,     0,     0,     0,
       0,     0,     0,     0,     0,     0,     0,     0,     0,     0,
       0,     0,     0,     0,     0,     0,     0,     0,     0,     0,
       0,     0,     0,     0,     0,     0,     0,     0,     0,     0,
       0,     0,     0,     0,     0,     0,     0,     0,   351,     0,
     307,   308,   309,   310,   311,   312,   313,   314,   315,   316,
     317,   318,   319,     0,   410,   411,     0,     0,     0,     0,
       0,     0,     0,     0,     0,     0,     0,     0,     0,     0,
       0,     0,     0,     0,     0,     0,     0,     0,     0,     0,
       0,     0,     0,     0,     0,     0,     0,     0,     0,     0,
       0,     0,     0,     0,     0,     0,     0,     0,     0,     0,
       0,     0,     0,     0,     0,     0,     0,     0,     0,     0,
       0,     0,     0,     0,     0,     0,     0,     0,     0,     0,
       0,     0,     0,     0,     0,     0,     0,   351,     0,   307,
     308,   309,   310,   311,   312,   313,   314,   315,   316,   317,
     318,   319,     0,   415,   416,     0,     0,     0,     0,     0,
       0,     0,     0,     0,     0,     0,     0,     0,     0,     0,
       0,     0,     0,     0,     0,     0,     0,     0,     0,     0,
       0,     0,     0,     0,     0,     0,     0,     0,     0,     0,
       0,     0,     0,     0,     0,     0,     0,     0,     0,     0,
       0,     0,     0,     0,     0,     0,     0,     0,     0,     0,
       0,     0,     0,     0,     0,     0,     0,     0,     0,     0,
       0,     0,     0,     0,     0,     0,   351,     0,   307,   308,
     309,   310,   311,   312,   313,   314,   315,   316,   317,   318,
     319,     0,   418,   419,   217,   218,   219,   220,   221,   222,
     223,   224,   225,   226,   227,   228,   229,   230,   231,   232,
     233,   234,   235,   236,   237,   238,   239,   240,   241,   242,
     243,   244,   245,   246,   247,   248,   249,   250,   251,   252,
     253,   254,   255,   256,   257,   258,   259,   260,   261,   262,
     263,   264,   265,   266,   267,   268,   269,   270,   271,   272,
     273,   274,   275,   276,   277,   278,   279,   280,   281,   282,
     283,   284,   285,   286,   287,   288,   289,   290,   291,   292,
     293,   294,   295,   296,   297,   298,   299,   300,   301,   302,
     303,   304,   305,   217,   218,   219,   220,   221,   222,   223,
     224,   225,   226,   227,   228,   229,   230,   231,   232,   233,
     234,   235,   236,   237,   238,   239,   240,   241,   242,   243,
     244,   245,   246,   247,   248,   249,   250,   251,   252,   253,
     254,   255,   256,   257,   258,   259,   260,   261,   262,   263,
     264,   265,   266,   267,   268,   269,   270,   271,   272,   273,
     274,   275,   276,   277,   278,   279,   280,   281,   282,   283,
     284,   285,   286,   287,   288,   289,   290,   291,   292,   293,
     294,   295,   296,   297,   298,   299,   300,   301,   302,   303,
     304,   305,   217,   218,   219,   220,   221,   222,   223,   224,
     225,   226,   227,   228,   229,   230,   231,   232,   233,   234,
     235,   236,   237,   238,   239,   240,   241,   242,   243,   244,
     245,   246,   247,   248,   249,   250,   251,   252,   253,   254,
     255,   256,   257,   258,   259,   260,   261,   262,   263,   264,
     265,   266,   267,   268,   269,   270,   271,   272,   273,   274,
     275,   276,   277,   278,   279,   280,   281,   282,   283,   284,
     285,   286,   287,   288,   289,   290,   291,   292,   293,   294,
     295,   296,   297,   298,   299,   300,   301,   302,   303,   304,
     305,     0,     0,     0,     0,     0,     0,     0,     0,     0,
       0,     0,     0,     0,     0,     0,     0,     0,     0,     0,
       0,     0,     0,     0,     0,     0,     0,     0,     0,     0,
       0,     0,     0,     0,     0,     0,     0,     0,     0,     0,
       0,     0,     0,     0,     0,     0,     0,   351,     0,   307,
     308,   309,   310,   311,   312,   313,   314,   315,   316,   317,
     318,   319,     0,   421,   422,     0,     0,     0,     0,     0,
       0,     0,     0,     0,     0,     0,     0,     0,     0,     0,
       0,     0,     0,     0,     0,     0,     0,     0,     0,     0,
       0,     0,     0,     0,     0,     0,     0,     0,     0,     0,
       0,     0,     0,     0,     0,     0,     0,     0,     0,     0,
       0,     0,     0,     0,     0,     0,     0,     0,     0,     0,
       0,     0,     0,     0,     0,     0,     0,     0,     0,     0,
       0,     0,     0,     0,     0,     0,   351,     0,   307,   308,
     309,   310,   311,   312,   313,   314,   315,   316,   317,   318,
     319,     0,   424,   425,     0,     0,     0,     0,     0,     0,
       0,     0,     0,     0,     0,     0,     0,     0,     0,     0,
       0,     0,     0,     0,     0,     0,     0,     0,     0,     0,
       0,     0,     0,     0,     0,     0,     0,     0,     0,     0,
       0,     0,     0,     0,     0,     0,     0,     0,     0,     0,
       0,     0,     0,     0,     0,     0,     0,     0,     0,     0,
       0,     0,     0,     0,     0,     0,     0,     0,     0,     0,
       0,     0,     0,     0,     0,   351,     0,   307,   308,   309,
     310,   311,   312,   313,   314,   315,   316,   317,   318,   319,
       0,   427,   428,   215,   216,   217,   218,   219,   220,   221,
     222,   223,   224,   225,   226,   227,   228,   229,   230,   231,
     232,   233,   234,   235,   236,   237,   238,   239,   240,   241,
     242,   243,   244,   245,   246,   247,   248,   249,   250,   251,
     252,   253,   254,   255,   256,   257,   258,   259,   260,   261,
     262,   263,   264,   265,   266,   267,   268,   269,   270,   271,
     272,   273,   274,   275,   276,   277,   278,   279,   280,   281,
     282,   283,   284,   285,   286,   287,   288,   289,   290,   291,
     292,   293,   294,   295,   296,   297,   298,   299,   300,   301,
     302,   303,   304,   305,   215,   216,   217,   218,   219,   220,
     221,   222,   223,   224,   225,   226,   227,   228,   229,   230,
     231,   232,   233,   234,   235,   236,   237,   238,   239,   240,
     241,   242,   243,   244,   245,   246,   247,   248,   249,   250,
     251,   252,   253,   254,   255,   256,   257,   258,   259,   260,
     261,   262,   263,   264,   265,   266,   267,   268,   269,   270,
     271,   272,   273,   274,   275,   276,   277,   278,   279,   280,
     281,   282,   283,   284,   285,   286,   287,   288,   289,   290,
     291,   292,   293,   294,   295,   296,   297,   298,   299,   300,
     301,   302,   303,   304,   305,   485,   486,   217,   218,   219,
     220,   221,   222,   223,   224,   225,   226,   227,   228,   229,
     230,   231,   232,   233,   234,   235,   236,   237,   238,   239,
     240,   241,   242,   243,   244,   245,   246,   247,   248,   249,
     250,   251,   252,   253,   254,   255,   256,   257,   258,   259,
     260,   261,   262,   263,   264,   265,   266,   267,   268,   269,
     270,   271,   272,   273,   274,   275,   276,   277,   278,   279,
     280,   281,   282,   283,   284,   285,   286,   287,   288,   289,
     290,   291,   292,   293,   294,   295,   296,   297,   298,   299,
     300,   301,   302,   303,   304,   305,     0,     0,     0,     0,
       0,     0,     0,     0,     0,     0,     0,     0,     0,     0,
       0,     0,     0,     0,     0,     0,     0,     0,     0,     0,
       0,     0,     0,     0,     0,     0,     0,     0,     0,     0,
       0,     0,     0,     0,     0,     0,     0,     0,     0,   306,
     307,   308,   309,   310,   311,   312,   313,   314,   315,   316,
     317,   318,   319,     0,     0,     0,     0,     0,     0,     0,
       0,     0,     0,     0,     0,     0,     0,     0,     0,     0,
       0,     0,     0,     0,     0,     0,     0,     0,     0,     0,
       0,     0,     0,     0,     0,     0,     0,     0,     0,     0,
       0,     0,     0,     0,     0,     0,     0,     0,     0,     0,
       0,     0,     0,     0,     0,     0,     0,     0,     0,     0,
       0,     0,     0,     0,     0,     0,     0,     0,     0,     0,
       0,     0,     0,     0,     0,     0,     0,     0,     0,     0,
       0,   307,   308,   309,   310,   311,   312,   313,   314,   315,
     316,   317,   318,   319,     0,     0,     0,     0,     0,     0,
       0,     0,     0,     0,     0,     0,     0,     0,     0,     0,
       0,     0,     0,     0,     0,     0,     0,     0,     0,     0,
       0,     0,     0,     0,     0,     0,     0,     0,     0,     0,
       0,     0,     0,     0,     0,     0,     0,     0,     0,     0,
       0,     0,     0,     0,     0,     0,     0,     0,     0,     0,
       0,     0,     0,     0,     0,     0,     0,     0,     0,     0,
       0,     0,     0,     0,     0,     0,     0,     0,     0,     0,
       0,     0,   307,   308,   309,   310,   311,   312,   313,   314,
     315,   316,   317,   318,   319,   217,   218,   219,   220,   221,
     222,   223,   224,   225,   226,   227,   228,   229,   230,   231,
     232,   233,   234,   235,   236,   237,   238,   239,   240,   241,
     242,   243,   244,   245,   246,   247,   248,   249,   250,   251,
     252,   253,   254,   255,   256,   257,   258,   259,   260,   261,
     262,   263,   264,   265,   266,   267,   268,   269,   270,   271,
     272,   273,   274,   275,   276,   277,   278,   279,   280,   281,
     282,   283,   284,   285,   286,   287,   288,   289,   290,   291,
     292,   293,   294,   295,   296,   297,   298,   299,   300,   301,
     302,   303,   304,   305,     0,     0,     0,     0,   436,   437,
     438,   439,   440,   441,   442,   443,   444,   445,   446,   447,
     448,   449,   450,   451,   452,   453,   454,   455,   456,   457,
       0,   458,   459,   460,   461,   462,   463,   464,   465,   466,
     467,   468,   469,   470,   471,   472,   217,   218,   219,   220,
     221,   222,   223,   224,   225,   226,   227,   228,   229,   230,
     231,   232,   233,   234,   235,   236,   237,   238,   239,   240,
     241,   242,   243,   244,   245,   246,   247,   248,   249,   250,
     251,   252,   253,   254,   255,   256,   257,   258,   259,   260,
     261,   262,   263,   264,   265,   266,   267,   268,   269,   270,
     271,   272,   273,   274,   275,   276,   277,   278,   279,   280,
     281,   282,   283,   284,   285,   286,   287,   288,   289,   290,
     291,   292,   293,   294,   295,   296,   297,   298,   299,   300,
     301,   302,   303,   304,   305,     0,     0,     0,     0,     0,
     437,   438,   439,   440,   441,   442,   443,   444,   445,   446,
     447,   448,   449,   450,   451,   452,   453,   454,   455,   456,
     457,     0,   458,   459,   460,   461,   462,   463,   464,   465,
     466,   467,   468,   469,   470,   471,   472,     0,     0,     0,
       0,     0,     0,     0,     0,     0,     0,     0,     0,     0,
       0,     0,     0,     0,     0,     0,     0,     0,     0,     0,
       0,     0,     0,     0,     0,     0,     0,     0,     0,     0,
       0,     0,     0,     0,     0,     0,     0,     0,     0,     0,
       0,     0,     0,     0,     0,     0,     0,     0,   351,     0,
     307,   308,   309,   310,   311,   312,   313,   314,   315,   316,
     317,   318,   319,   217,   218,   219,   220,   221,   222,   223,
     224,   225,   226,   227,   228,   229,   230,   231,   232,   233,
     234,   235,   236,   237,   238,   239,   240,   241,   242,   243,
     244,   245,   246,   247,   248,   249,   250,   251,   252,   253,
     254,   255,   256,   257,   258,   259,   260,   261,   262,   263,
     264,   265,   266,   267,   268,   269,   270,   271,   272,   273,
     274,   275,   276,   277,   278,   279,   280,   281,   282,   283,
     284,   285,   286,   287,   288,   289,   290,   291,   292,   293,
     294,   295,   296,   297,   298,   299,   300,   301,   302,   303,
     304,   305,     0,     0,     0,     0,   338,     0,     0,     0,
       0,     0,     0,     0,     0,     0,     0,     0,     0,     0,
       0,     0,     0,     0,     0,     0,     0,     0,     0,   351,
       0,   307,   308,   309,   310,   311,   312,   313,   314,   315,
     316,   317,   318,   319,   217,   218,   219,   220,   221,   222,
     223,   224,   225,   226,   227,   228,   229,   230,   231,   232,
     233,   234,   235,   236,   237,   238,   239,   240,   241,   242,
     243,   244,   245,   246,   247,   248,   249,   250,   251,   252,
     253,   254,   255,   256,   257,   258,   259,   260,   261,   262,
     263,   264,   265,   266,   267,   268,   269,   270,   271,   272,
     273,   274,   275,   276,   277,   278,   279,   280,   281,   282,
     283,   284,   285,   286,   287,   288,   289,   290,   291,   292,
     293,   294,   295,   296,   297,   298,   299,   300,   301,   302,
     303,   304,   305,   217,   218,   219,   220,   221,   222,   223,
     224,   225,   226,   227,   228,   229,   230,   231,   232,   233,
     234,   235,   236,   237,   238,   239,   240,   241,   242,   243,
     244,   245,   246,   247,   248,   249,   250,   251,   252,   253,
     254,   255,   256,   257,   258,   259,   260,   261,   262,   263,
     264,   265,   266,   267,   268,   269,   270,   271,   272,   273,
     274,   275,   276,   277,   278,   279,   280,   281,   282,   283,
     284,   285,   286,   287,   288,   289,   290,   291,   292,   293,
     294,   295,   296,   297,   298,   299,   300,   301,   302,   303,
     304,   305,     0,     0,     0,     0,     0,     0,   307,   308,
     309,   310,   311,   312,   313,   314,   315,   316,   317,   318,
     319,   217,   218,   219,   220,   221,   222,   223,   224,   225,
     226,   227,   228,   229,   230,   231,   232,   233,   234,   235,
     236,   237,   238,   239,   240,   241,   242,   243,   244,   245,
     246,   247,   248,   249,   250,   251,   252,   253,   254,   255,
     256,   257,   258,   259,   260,   261,   262,   263,   264,   265,
     266,   267,   268,   269,   270,   271,   272,   273,   274,   275,
     276,   277,   278,   279,   280,   281,   282,   283,   284,   285,
     286,   287,   288,   289,   290,   291,   292,   293,   294,   295,
     296,   297,   298,   299,   300,   301,   302,   303,   304,   305,
       0,     0,     0,     1,     0,     0,     0,     2,     3,     0,
       0,     0,     0,     0,     0,     0,     0,     0,     0,     0,
       0,     0,     0,     0,     0,     0,     0,   351,     0,   307,
     308,   309,   310,   311,   312,   313,   314,   315,   316,   317,
     318,   319,     0,     0,     0,     0,     0,     0,     0,     0,
       0,     0,     0,     0,     0,     0,     0,     0,     0,     0,
       0,     0,     0,     0,     0,     0,     0,     0,     0,     0,
       0,     0,     0,     0,     0,     0,     0,     0,     0,     0,
       0,     0,     0,     0,     0,     0,     0,     0,     0,     0,
       0,     0,     0,     0,     0,     0,     0,     0,     0,     0,
       0,     0,     0,     0,     0,     0,     0,     0,     0,     0,
       0,     0,     0,     0,     0,     0,   480,     0,   307,   308,
     309,   310,   311,   312,   313,   314,   315,   316,   317,   318,
     319,     0,     0,     0,     0,     0,     0,     0,     0,     0,
       0,     0,     0,     0,     4,   336,     0,     0,     0,     2,
       3,     0,     0,     0,     0,     0,     0,     0,     0,     0,
       0,     0,     0,     0,     0,     0,     0,     0,     0,     0,
       0,     0,     0,     0,     0,     0,     0,     0,     0,     0,
       0,     0,     0,     0,     0,     0,     0,     0,     0,     0,
       0,     0,     0,     0,     0,     0,     0,     0,     0,     0,
       0,     0,     0,     0,     0,     0,     0,     0,     0,     0,
       0,     0,     0,     0,     0,     0,     0,     0,     0,     0,
       0,     0,     0,     0,     0,     0,   307,   308,   309,   310,
     311,   312,   313,   314,   315,   316,   317,   318,   319,     5,
       6,     7,     8,     9,    10,    11,    12,    13,    14,    15,
      16,    17,    18,    19,    20,    21,    22,    23,    24,    25,
      26,    27,    28,    29,    30,    31,    32,    33,    34,    35,
      36,    37,    38,    39,    40,    41,    42,    43,    44,    45,
      46,    47,    48,    49,    50,    51,     4,    52,    53,    54,
      55,    56,    57,    58,    59,    60,    61,    62,    63,    64,
      65,    66,    67,     0,     0,     0,     0,     0,     0,     0,
       0,     0,     0,     0,    68,    69,    70,    71,    72,    73,
      74,    75,    76,    77,    78,    79,     0,     0,     0,     0,
       0,     0,     0,     0,     0,     0,     0,     0,     0,     0,
       0,     0,     0,     0,     0,     0,     0,     0,     0,     0,
       0,     0,     0,     0,     0,     0,     0,     0,     0,     0,
       0,     0,     0,     0,     0,     0,     0,     0,     0,     0,
       0,     0,     0,     0,     0,     0,     0,     0,     0,     0,
       0,     5,     6,     7,     8,     9,    10,    11,    12,    13,
      14,    15,    16,    17,    18,    19,    20,    21,    22,    23,
      24,    25,    26,    27,    28,    29,    30,    31,    32,    33,
      34,    35,    36,    37,    38,    39,    40,    41,    42,    43,
      44,    45,    46,    47,    48,    49,    50,    51,   113,    52,
      53,    54,    55,    56,    57,    58,    59,    60,    61,    62,
      63,    64,    65,    66,    67,     0,     0,     0,     0,     0,
       0,     0,     0,     0,     0,     0,    68,    69,    70,    71,
      72,    73,    74,    75,    76,    77,    78,    79,     0,     0,
       0,     0,     0,   114,   115,   116,   117,   118,   119,   120,
     121,   122,   123,   124,   125,   126,   127,   128,   129,   130,
     131,   132,   133,   134,   135,   136,   137,   138,   139,   140,
     141,   142,   143,   144,   145,   146,   147,   148,   149,   150,
     151,   152,   153,   154,   155,   156,   157,   158,   159,   160,
     161,   162,   163,   164,   165,   166,   167,   168,   169,   170,
     171,   172,   173,   174,   175,   176,   177,   178,   179,   180,
     181,   182,   183,   184,   185,   186,   187,   188,   189,   190,
     191,   192,   193,   194,   195,   196,   197,   198,   199,   200,
     201,   202,   203,   204,   205
  };

  const short
  seclang_parser::yycheck_[] =
  {
      59,    60,    61,   300,    49,    60,    61,     3,     3,   141,
      99,   143,    80,   310,     6,   302,     6,    62,   305,    78,
     152,   206,   309,    78,   100,   101,   102,   159,   160,   161,
     162,   303,   304,   436,    79,   167,   308,   303,   304,   303,
     304,   306,   308,   301,   308,   303,   304,   301,   363,   303,
     304,   303,   304,    -1,   113,   144,   145,   146,   147,   148,
     149,   150,   151,   152,   153,   154,   155,   156,   157,   158,
     159,   160,   161,   162,   163,   164,   165,   166,   167,   168,
     169,   170,   171,   172,   173,   174,   175,   176,   177,   178,
     179,   180,   181,   182,   183,   184,   185,   186,   187,   188,
     189,   190,   191,   192,   193,   194,   195,   196,   197,   198,
     199,   200,   201,   202,   203,   204,   205,   206,   207,   208,
     209,   210,   211,   212,   213,   214,   215,   216,   217,   218,
     219,   220,   221,   222,   223,   224,   225,   226,   227,   228,
     229,   230,   231,   232,   233,   234,   235,    -1,   142,   143,
     282,   303,   304,   303,   304,    -1,   215,   216,   303,   304,
     303,   304,   306,   307,   303,   304,    -1,   299,   300,   301,
     302,   303,   306,   307,   303,   304,   303,   304,   303,   304,
     303,   304,   303,   304,   303,   304,   339,   340,   339,   340,
     339,   340,   339,   340,    -1,    -1,    -1,   339,   340,   339,
     340,   333,   339,   340,   339,   340,   339,   340,   339,   340,
      -1,   339,   340,   339,   340,   339,   340,   339,   340,   339,
     340,   339,   340,   339,   340,   339,   340,   339,   340,   339,
     340,   339,   340,   339,   340,   324,   339,   340,   339,   340,
     339,   340,    -1,    -1,    -1,    -1,    -1,   306,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,   338,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,   353,   354,   355,   356,   357,   358,
     359,   360,   361,    -1,   436,   437,   438,   439,    -1,    -1,
     442,   443,   444,    -1,   446,   447,   448,   449,   450,   451,
     452,   453,   454,   455,   456,   457,   458,   459,   460,   324,
     462,   463,   464,   465,   324,    -1,   468,   469,   470,   471,
     472,    -1,    -1,    -1,    -1,   477,   478,   479,    -1,    -1,
      -1,    -1,    -1,   412,    -1,    -1,    -1,    -1,   417,    -1,
      -1,   420,    -1,    -1,   423,    -1,    -1,   426,    -1,    -1,
     429,    -1,    -1,    -1,    -1,    -1,   435,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,   475,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,   485,   486,   473,    -1,
     489,   490,   491,   492,   493,   494,   495,   496,   497,   498,
     499,   500,   501,   502,   503,   504,   505,   506,   507,   508,
     509,   510,   511,   512,   513,   514,   515,   516,   517,   518,
     519,    -1,   521,   522,   523,    10,    11,    12,    13,    14,
      15,    16,    17,    18,    19,    20,    21,    22,    23,    24,
      25,    26,    27,    28,    29,    30,    31,    32,    33,    34,
      35,    36,    37,    38,    39,    40,    41,    42,    43,    44,
      45,    46,    47,    48,    49,    50,    51,    52,    53,    54,
      55,    56,    57,    58,    59,    60,    61,    62,    63,    64,
      65,    66,    67,    68,    69,    70,    71,    72,    73,    74,
      75,    76,    77,    78,    79,    80,    81,    82,    83,    84,
      85,    86,    87,    88,    89,    90,    91,    92,    93,    94,
      95,    96,    97,    98,    10,    11,    12,    13,    14,    15,
      16,    17,    18,    19,    20,    21,    22,    23,    24,    25,
      26,    27,    28,    29,    30,    31,    32,    33,    34,    35,
      36,    37,    38,    39,    40,    41,    42,    43,    44,    45,
      46,    47,    48,    49,    50,    51,    52,    53,    54,    55,
      56,    57,    58,    59,    60,    61,    62,    63,    64,    65,
      66,    67,    68,    69,    70,    71,    72,    73,    74,    75,
      76,    77,    78,    79,    80,    81,    82,    83,    84,    85,
      86,    87,    88,    89,    90,    91,    92,    93,    94,    95,
      96,    97,    98,    10,    11,    12,    13,    14,    15,    16,
      17,    18,    19,    20,    21,    22,    23,    24,    25,    26,
      27,    28,    29,    30,    31,    32,    33,    34,    35,    36,
      37,    38,    39,    40,    41,    42,    43,    44,    45,    46,
      47,    48,    49,    50,    51,    52,    53,    54,    55,    56,
      57,    58,    59,    60,    61,    62,    63,    64,    65,    66,
      67,    68,    69,    70,    71,    72,    73,    74,    75,    76,
      77,    78,    79,    80,    81,    82,    83,    84,    85,    86,
      87,    88,    89,    90,    91,    92,    93,    94,    95,    96,
      97,    98,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,   323,    -1,
     325,   326,   327,   328,   329,   330,   331,   332,   333,   334,
     335,   336,   337,    -1,   339,   340,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,   323,    -1,   325,
     326,   327,   328,   329,   330,   331,   332,   333,   334,   335,
     336,   337,    -1,   339,   340,    -1,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,   323,    -1,   325,   326,
     327,   328,   329,   330,   331,   332,   333,   334,   335,   336,
     337,    -1,   339,   340,    10,    11,    12,    13,    14,    15,
      16,    17,    18,    19,    20,    21,    22,    23,    24,    25,
      26,    27,    28,    29,    30,    31,    32,    33,    34,    35,
      36,    37,    38,    39,    40,    41,    42,    43,    44,    45,
      46,    47,    48,    49,    50,    51,    52,    53,    54,    55,
      56,    57,    58,    59,    60,    61,    62,    63,    64,    65,
      66,    67,    68,    69,    70,    71,    72,    73,    74,    75,
      76,    77,    78,    79,    80,    81,    82,    83,    84,    85,
      86,    87,    88,    89,    90,    91,    92,    93,    94,    95,
      96,    97,    98,    10,    11,    12,    13,    14,    15,    16,
      17,    18,    19,    20,    21,    22,    23,    24,    25,    26,
      27,    28,    29,    30,    31,    32,    33,    34,    35,    36,
      37,    38,    39,    40,    41,    42,    43,    44,    45,    46,
      47,    48,    49,    50,    51,    52,    53,    54,    55,    56,
      57,    58,    59,    60,    61,    62,    63,    64,    65,    66,
      67,    68,    69,    70,    71,    72,    73,    74,    75,    76,
      77,    78,    79,    80,    81,    82,    83,    84,    85,    86,
      87,    88,    89,    90,    91,    92,    93,    94,    95,    96,
      97,    98,    10,    11,    12,    13,    14,    15,    16,    17,
      18,    19,    20,    21,    22,    23,    24,    25,    26,    27,
      28,    29,    30,    31,    32,    33,    34,    35,    36,    37,
      38,    39,    40,    41,    42,    43,    44,    45,    46,    47,
      48,    49,    50,    51,    52,    53,    54,    55,    56,    57,
      58,    59,    60,    61,    62,    63,    64,    65,    66,    67,
      68,    69,    70,    71,    72,    73,    74,    75,    76,    77,
      78,    79,    80,    81,    82,    83,    84,    85,    86,    87,
      88,    89,    90,    91,    92,    93,    94,    95,    96,    97,
      98,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,   323,    -1,   325,
     326,   327,   328,   329,   330,   331,   332,   333,   334,   335,
     336,   337,    -1,   339,   340,    -1,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,   323,    -1,   325,   326,
     327,   328,   329,   330,   331,   332,   333,   334,   335,   336,
     337,    -1,   339,   340,    -1,    -1,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,   323,    -1,   325,   326,   327,
     328,   329,   330,   331,   332,   333,   334,   335,   336,   337,
      -1,   339,   340,     8,     9,    10,    11,    12,    13,    14,
      15,    16,    17,    18,    19,    20,    21,    22,    23,    24,
      25,    26,    27,    28,    29,    30,    31,    32,    33,    34,
      35,    36,    37,    38,    39,    40,    41,    42,    43,    44,
      45,    46,    47,    48,    49,    50,    51,    52,    53,    54,
      55,    56,    57,    58,    59,    60,    61,    62,    63,    64,
      65,    66,    67,    68,    69,    70,    71,    72,    73,    74,
      75,    76,    77,    78,    79,    80,    81,    82,    83,    84,
      85,    86,    87,    88,    89,    90,    91,    92,    93,    94,
      95,    96,    97,    98,     8,     9,    10,    11,    12,    13,
      14,    15,    16,    17,    18,    19,    20,    21,    22,    23,
      24,    25,    26,    27,    28,    29,    30,    31,    32,    33,
      34,    35,    36,    37,    38,    39,    40,    41,    42,    43,
      44,    45,    46,    47,    48,    49,    50,    51,    52,    53,
      54,    55,    56,    57,    58,    59,    60,    61,    62,    63,
      64,    65,    66,    67,    68,    69,    70,    71,    72,    73,
      74,    75,    76,    77,    78,    79,    80,    81,    82,    83,
      84,    85,    86,    87,    88,    89,    90,    91,    92,    93,
      94,    95,    96,    97,    98,     8,     9,    10,    11,    12,
      13,    14,    15,    16,    17,    18,    19,    20,    21,    22,
      23,    24,    25,    26,    27,    28,    29,    30,    31,    32,
      33,    34,    35,    36,    37,    38,    39,    40,    41,    42,
      43,    44,    45,    46,    47,    48,    49,    50,    51,    52,
      53,    54,    55,    56,    57,    58,    59,    60,    61,    62,
      63,    64,    65,    66,    67,    68,    69,    70,    71,    72,
      73,    74,    75,    76,    77,    78,    79,    80,    81,    82,
      83,    84,    85,    86,    87,    88,    89,    90,    91,    92,
      93,    94,    95,    96,    97,    98,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,   324,
     325,   326,   327,   328,   329,   330,   331,   332,   333,   334,
     335,   336,   337,    -1,    -1,    -1,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,
      -1,   325,   326,   327,   328,   329,   330,   331,   332,   333,
     334,   335,   336,   337,    -1,    -1,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,
      -1,    -1,   325,   326,   327,   328,   329,   330,   331,   332,
     333,   334,   335,   336,   337,    10,    11,    12,    13,    14,
      15,    16,    17,    18,    19,    20,    21,    22,    23,    24,
      25,    26,    27,    28,    29,    30,    31,    32,    33,    34,
      35,    36,    37,    38,    39,    40,    41,    42,    43,    44,
      45,    46,    47,    48,    49,    50,    51,    52,    53,    54,
      55,    56,    57,    58,    59,    60,    61,    62,    63,    64,
      65,    66,    67,    68,    69,    70,    71,    72,    73,    74,
      75,    76,    77,    78,    79,    80,    81,    82,    83,    84,
      85,    86,    87,    88,    89,    90,    91,    92,    93,    94,
      95,    96,    97,    98,    -1,    -1,    -1,    -1,   103,   104,
     105,   106,   107,   108,   109,   110,   111,   112,   113,   114,
     115,   116,   117,   118,   119,   120,   121,   122,   123,   124,
      -1,   126,   127,   128,   129,   130,   131,   132,   133,   134,
     135,   136,   137,   138,   139,   140,    10,    11,    12,    13,
      14,    15,    16,    17,    18,    19,    20,    21,    22,    23,
      24,    25,    26,    27,    28,    29,    30,    31,    32,    33,
      34,    35,    36,    37,    38,    39,    40,    41,    42,    43,
      44,    45,    46,    47,    48,    49,    50,    51,    52,    53,
      54,    55,    56,    57,    58,    59,    60,    61,    62,    63,
      64,    65,    66,    67,    68,    69,    70,    71,    72,    73,
      74,    75,    76,    77,    78,    79,    80,    81,    82,    83,
      84,    85,    86,    87,    88,    89,    90,    91,    92,    93,
      94,    95,    96,    97,    98,    -1,    -1,    -1,    -1,    -1,
     104,   105,   106,   107,   108,   109,   110,   111,   112,   113,
     114,   115,   116,   117,   118,   119,   120,   121,   122,   123,
     124,    -1,   126,   127,   128,   129,   130,   131,   132,   133,
     134,   135,   136,   137,   138,   139,   140,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,   323,    -1,
     325,   326,   327,   328,   329,   330,   331,   332,   333,   334,
     335,   336,   337,    10,    11,    12,    13,    14,    15,    16,
      17,    18,    19,    20,    21,    22,    23,    24,    25,    26,
      27,    28,    29,    30,    31,    32,    33,    34,    35,    36,
      37,    38,    39,    40,    41,    42,    43,    44,    45,    46,
      47,    48,    49,    50,    51,    52,    53,    54,    55,    56,
      57,    58,    59,    60,    61,    62,    63,    64,    65,    66,
      67,    68,    69,    70,    71,    72,    73,    74,    75,    76,
      77,    78,    79,    80,    81,    82,    83,    84,    85,    86,
      87,    88,    89,    90,    91,    92,    93,    94,    95,    96,
      97,    98,    -1,    -1,    -1,    -1,   103,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,   323,
      -1,   325,   326,   327,   328,   329,   330,   331,   332,   333,
     334,   335,   336,   337,    10,    11,    12,    13,    14,    15,
      16,    17,    18,    19,    20,    21,    22,    23,    24,    25,
      26,    27,    28,    29,    30,    31,    32,    33,    34,    35,
      36,    37,    38,    39,    40,    41,    42,    43,    44,    45,
      46,    47,    48,    49,    50,    51,    52,    53,    54,    55,
      56,    57,    58,    59,    60,    61,    62,    63,    64,    65,
      66,    67,    68,    69,    70,    71,    72,    73,    74,    75,
      76,    77,    78,    79,    80,    81,    82,    83,    84,    85,
      86,    87,    88,    89,    90,    91,    92,    93,    94,    95,
      96,    97,    98,    10,    11,    12,    13,    14,    15,    16,
      17,    18,    19,    20,    21,    22,    23,    24,    25,    26,
      27,    28,    29,    30,    31,    32,    33,    34,    35,    36,
      37,    38,    39,    40,    41,    42,    43,    44,    45,    46,
      47,    48,    49,    50,    51,    52,    53,    54,    55,    56,
      57,    58,    59,    60,    61,    62,    63,    64,    65,    66,
      67,    68,    69,    70,    71,    72,    73,    74,    75,    76,
      77,    78,    79,    80,    81,    82,    83,    84,    85,    86,
      87,    88,    89,    90,    91,    92,    93,    94,    95,    96,
      97,    98,    -1,    -1,    -1,    -1,    -1,    -1,   325,   326,
     327,   328,   329,   330,   331,   332,   333,   334,   335,   336,
     337,    10,    11,    12,    13,    14,    15,    16,    17,    18,
      19,    20,    21,    22,    23,    24,    25,    26,    27,    28,
      29,    30,    31,    32,    33,    34,    35,    36,    37,    38,
      39,    40,    41,    42,    43,    44,    45,    46,    47,    48,
      49,    50,    51,    52,    53,    54,    55,    56,    57,    58,
      59,    60,    61,    62,    63,    64,    65,    66,    67,    68,
      69,    70,    71,    72,    73,    74,    75,    76,    77,    78,
      79,    80,    81,    82,    83,    84,    85,    86,    87,    88,
      89,    90,    91,    92,    93,    94,    95,    96,    97,    98,
      -1,    -1,    -1,     0,    -1,    -1,    -1,     4,     5,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,   323,    -1,   325,
     326,   327,   328,   329,   330,   331,   332,   333,   334,   335,
     336,   337,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,   323,    -1,   325,   326,
     327,   328,   329,   330,   331,   332,   333,   334,   335,   336,
     337,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,   141,     0,    -1,    -1,    -1,     4,
       5,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,   325,   326,   327,   328,
     329,   330,   331,   332,   333,   334,   335,   336,   337,   236,
     237,   238,   239,   240,   241,   242,   243,   244,   245,   246,
     247,   248,   249,   250,   251,   252,   253,   254,   255,   256,
     257,   258,   259,   260,   261,   262,   263,   264,   265,   266,
     267,   268,   269,   270,   271,   272,   273,   274,   275,   276,
     277,   278,   279,   280,   281,   282,   141,   284,   285,   286,
     287,   288,   289,   290,   291,   292,   293,   294,   295,   296,
     297,   298,   299,    -1,    -1,    -1,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,   311,   312,   313,   314,   315,   316,
     317,   318,   319,   320,   321,   322,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,    -1,
      -1,   236,   237,   238,   239,   240,   241,   242,   243,   244,
     245,   246,   247,   248,   249,   250,   251,   252,   253,   254,
     255,   256,   257,   258,   259,   260,   261,   262,   263,   264,
     265,   266,   267,   268,   269,   270,   271,   272,   273,   274,
     275,   276,   277,   278,   279,   280,   281,   282,    99,   284,
     285,   286,   287,   288,   289,   290,   291,   292,   293,   294,
     295,   296,   297,   298,   299,    -1,    -1,    -1,    -1,    -1,
      -1,    -1,    -1,    -1,    -1,    -1,   311,   312,   313,   314,
     315,   316,   317,   318,   319,   320,   321,   322,    -1,    -1,
      -1,    -1,    -1,   144,   145,   146,   147,   148,   149,   150,
     151,   152,   153,   154,   155,   156,   157,   158,   159,   160,
     161,   162,   163,   164,   165,   166,   167,   168,   169,   170,
     171,   172,   173,   174,   175,   176,   177,   178,   179,   180,
     181,   182,   183,   184,   185,   186,   187,   188,   189,   190,
     191,   192,   193,   194,   195,   196,   197,   198,   199,   200,
     201,   202,   203,   204,   205,   206,   207,   208,   209,   210,
     211,   212,   213,   214,   215,   216,   217,   218,   219,   220,
     221,   222,   223,   224,   225,   226,   227,   228,   229,   230,
     231,   232,   233,   234,   235
  };

  const unsigned short
  seclang_parser::yystos_[] =
  {
       0,     0,     4,     5,   141,   236,   237,   238,   239,   240,
     241,   242,   243,   244,   245,   246,   247,   248,   249,   250,
     251,   252,   253,   254,   255,   256,   257,   258,   259,   260,
     261,   262,   263,   264,   265,   266,   267,   268,   269,   270,
     271,   272,   273,   274,   275,   276,   277,   278,   279,   280,
     281,   282,   284,   285,   286,   287,   288,   289,   290,   291,
     292,   293,   294,   295,   296,   297,   298,   299,   311,   312,
     313,   314,   315,   316,   317,   318,   319,   320,   321,   322,
     342,   343,   344,   349,   303,   304,   142,   143,   303,   304,
     303,   304,   308,   302,   305,   309,   303,   304,   303,   304,
     303,   304,   306,   307,   303,   304,   306,   307,   303,   304,
     301,   303,   304,    99,   144,   145,   146,   147,   148,   149,
     150,   151,   152,   153,   154,   155,   156,   157,   158,   159,
     160,   161,   162,   163,   164,   165,   166,   167,   168,   169,
     170,   171,   172,   173,   174,   175,   176,   177,   178,   179,
     180,   181,   182,   183,   184,   185,   186,   187,   188,   189,
     190,   191,   192,   193,   194,   195,   196,   197,   198,   199,
     200,   201,   202,   203,   204,   205,   206,   207,   208,   209,
     210,   211,   212,   213,   214,   215,   216,   217,   218,   219,
     220,   221,   222,   223,   224,   225,   226,   227,   228,   229,
     230,   231,   232,   233,   234,   235,   324,   345,   346,   354,
     345,   303,   304,   300,   310,     8,     9,    10,    11,    12,
      13,    14,    15,    16,    17,    18,    19,    20,    21,    22,
      23,    24,    25,    26,    27,    28,    29,    30,    31,    32,
      33,    34,    35,    36,    37,    38,    39,    40,    41,    42,
      43,    44,    45,    46,    47,    48,    49,    50,    51,    52,
      53,    54,    55,    56,    57,    58,    59,    60,    61,    62,
      63,    64,    65,    66,    67,    68,    69,    70,    71,    72,
      73,    74,    75,    76,    77,    78,    79,    80,    81,    82,
      83,    84,    85,    86,    87,    88,    89,    90,    91,    92,
      93,    94,    95,    96,    97,    98,   324,   325,   326,   327,
     328,   329,   330,   331,   332,   333,   334,   335,   336,   337,
     351,   352,   353,   351,   351,   345,   303,   304,   308,   303,
     304,   303,   304,   350,   351,   345,     0,   343,   103,   353,
     355,   301,   303,   304,   303,   304,   308,   303,   304,   303,
     304,   323,   353,   356,   356,   356,   356,   356,   356,   356,
     356,   356,   346,     3,   353,   353,   339,   340,   339,   340,
     339,   340,   339,   340,   339,   340,   339,   340,   339,   340,
     339,   340,   339,   340,   339,   340,   339,   340,   339,   340,
     339,   340,   339,   340,   339,   340,   339,   340,   339,   340,
     339,   340,   339,   340,   339,   340,   339,   340,   339,   340,
     339,   340,   356,   339,   340,   339,   340,   356,   339,   340,
     356,   339,   340,   356,   339,   340,   356,   339,   340,   356,
     339,   340,   339,   340,   352,     6,   103,   104,   105,   106,
     107,   108,   109,   110,   111,   112,   113,   114,   115,   116,
     117,   118,   119,   120,   121,   122,   123,   124,   126,   127,
     128,   129,   130,   131,   132,   133,   134,   135,   136,   137,
     138,   139,   140,   347,   348,   356,   353,   100,   101,   102,
     323,   353,   324,   354,   324,     8,     9,   353,   348,   356,
     356,   356,   356,   356,   356,   356,   356,   356,   356,   356,
     356,   356,   356,   356,   356,   356,   356,   356,   356,   356,
     356,   356,   356,   356,   356,   356,   356,   356,   356,   356,
     345,   356,   356,   356,   353,   353
  };

  const unsigned short
  seclang_parser::yyr1_[] =
  {
       0,   341,   342,   342,   342,   343,   344,   344,   344,   344,
     344,   344,   344,   344,   344,   344,   344,   344,   344,   344,
     344,   344,   344,   344,   344,   344,   344,   344,   344,   345,
     345,   346,   346,   347,   347,   347,   347,   348,   348,   348,
     348,   348,   348,   348,   348,   348,   348,   348,   348,   348,
     348,   348,   348,   348,   348,   348,   348,   348,   348,   348,
     348,   348,   348,   348,   348,   348,   348,   348,   348,   348,
     348,   348,   348,   349,   349,   349,   349,   349,   349,   349,
     349,   349,   349,   349,   349,   349,   349,   349,   349,   349,
     349,   349,   349,   349,   349,   349,   349,   349,   349,   349,
     349,   349,   349,   349,   349,   349,   349,   349,   349,   349,
     349,   349,   349,   349,   349,   349,   349,   349,   349,   349,
     349,   349,   349,   349,   349,   349,   349,   349,   349,   349,
     349,   349,   349,   349,   349,   349,   349,   349,   349,   349,
     349,   349,   349,   349,   349,   349,   349,   349,   349,   349,
     349,   349,   350,   351,   351,   352,   352,   352,   352,   352,
     352,   353,   353,   353,   353,   353,   353,   353,   353,   353,
     353,   353,   353,   353,   353,   353,   353,   353,   353,   353,
     353,   353,   353,   353,   353,   353,   353,   353,   353,   353,
     353,   353,   353,   353,   353,   353,   353,   353,   353,   353,
     353,   353,   353,   353,   353,   353,   353,   353,   353,   353,
     353,   353,   353,   353,   353,   353,   353,   353,   353,   353,
     353,   353,   353,   353,   353,   353,   353,   353,   353,   353,
     353,   353,   353,   353,   353,   353,   353,   353,   353,   353,
     353,   353,   353,   353,   353,   353,   353,   353,   353,   353,
     353,   353,   353,   353,   353,   353,   353,   353,   353,   353,
     353,   353,   353,   353,   353,   353,   353,   353,   353,   353,
     353,   353,   353,   353,   353,   353,   353,   353,   353,   353,
     353,   353,   353,   353,   353,   353,   353,   353,   353,   353,
     353,   353,   353,   353,   353,   353,   353,   353,   353,   353,
     353,   353,   353,   353,   353,   353,   353,   353,   353,   353,
     353,   353,   353,   353,   353,   353,   353,   353,   353,   353,
     353,   353,   353,   353,   353,   353,   353,   353,   353,   353,
     353,   354,   354,   354,   354,   354,   354,   354,   354,   354,
     354,   354,   354,   354,   354,   354,   354,   354,   354,   354,
     354,   354,   354,   354,   354,   354,   354,   354,   354,   354,
     354,   354,   354,   354,   354,   354,   354,   354,   354,   354,
     354,   354,   354,   354,   354,   354,   354,   354,   354,   354,
     354,   354,   354,   354,   354,   354,   354,   354,   354,   354,
     354,   354,   354,   354,   354,   354,   354,   354,   354,   354,
     354,   354,   354,   354,   354,   354,   354,   354,   354,   354,
     354,   354,   354,   354,   354,   354,   354,   354,   354,   354,
     354,   354,   354,   354,   354,   354,   354,   354,   354,   354,
     355,   355,   355,   355,   355,   356,   356,   356,   356
  };

  const unsigned char
  seclang_parser::yyr2_[] =
  {
       0,     2,     1,     2,     1,     1,     1,     1,     2,     2,
       2,     1,     1,     1,     1,     2,     2,     1,     2,     2,
       2,     2,     2,     2,     1,     1,     1,     2,     2,     3,
       1,     3,     1,     1,     2,     1,     2,     1,     1,     1,
       1,     1,     2,     2,     2,     2,     2,     2,     2,     2,
       2,     2,     2,     2,     2,     2,     2,     2,     2,     2,
       2,     2,     2,     2,     2,     2,     2,     2,     2,     2,
       2,     2,     1,     1,     4,     3,     2,     2,     2,     1,
       2,     2,     2,     2,     2,     2,     2,     1,     1,     2,
       2,     1,     1,     1,     2,     2,     2,     2,     1,     2,
       2,     1,     1,     1,     1,     1,     1,     2,     2,     1,
       1,     1,     2,     2,     1,     1,     1,     1,     1,     1,
       2,     2,     2,     2,     1,     1,     1,     1,     1,     1,
       1,     2,     2,     2,     2,     2,     2,     1,     1,     1,
       1,     2,     2,     1,     1,     1,     1,     1,     1,     1,
       1,     1,     1,     1,     3,     3,     4,     4,     1,     2,
       2,     2,     2,     1,     2,     2,     1,     2,     2,     1,
       2,     2,     1,     2,     2,     1,     2,     2,     1,     2,
       2,     1,     2,     2,     1,     2,     2,     1,     2,     2,
       1,     2,     2,     1,     2,     2,     1,     2,     2,     1,
       2,     2,     1,     2,     2,     1,     2,     2,     1,     2,
       2,     1,     2,     2,     1,     2,     2,     1,     2,     2,
       1,     2,     2,     2,     1,     2,     2,     2,     1,     2,
       2,     2,     1,     2,     2,     2,     1,     2,     2,     2,
       1,     2,     2,     2,     1,     2,     2,     1,     2,     2,
       1,     2,     2,     1,     2,     2,     1,     1,     2,     2,
       1,     1,     1,     1,     1,     1,     1,     1,     1,     1,
       1,     1,     1,     1,     1,     1,     1,     1,     1,     1,
       1,     1,     1,     1,     1,     1,     1,     1,     1,     1,
       1,     1,     1,     1,     1,     1,     1,     1,     1,     1,
       1,     1,     1,     1,     1,     1,     1,     1,     1,     1,
       1,     1,     1,     1,     1,     1,     1,     1,     1,     1,
       1,     1,     1,     1,     1,     1,     1,     1,     1,     1,
       1,     1,     1,     1,     1,     1,     1,     1,     2,     2,
       2,     1,     1,     1,     1,     2,     2,     2,     2,     2,
       2,     2,     1,     1,     1,     1,     1,     1,     1,     1,
       1,     1,     2,     2,     1,     1,     2,     1,     1,     1,
       1,     1,     1,     1,     1,     2,     1,     1,     1,     1,
       1,     1,     2,     2,     2,     2,     2,     1,     1,     1,
       1,     2,     1,     1,     1,     1,     1,     1,     1,     1,
       1,     1,     1,     1,     1,     1,     1,     1,     1,     1,
       1,     1,     1,     1,     1,     1,     1,     1,     1,     1,
       1,     1,     1,     1,     1,     1,     1,     1,     1,     1,
       2,     1,     3,     3,     3,     2,     2,     1,     1
  };



  // YYTNAME[SYMBOL-NUM] -- String name of the symbol SYMBOL-NUM.
  // First, the terminals, then, starting at \a yyntokens_, nonterminals.
  const char*
  const seclang_parser::yytname_[] =
  {
  "\"end of file\"", "error", "$undefined", "\",\"",
  "\"CONFIG_CONTENT_INJECTION\"", "\"CONGIG_DIR_RESPONSE_BODY_MP_CLEAR\"",
  "PIPE", "NEW_LINE", "VAR_COUNT", "VAR_EXCLUSION", "VARIABLE_ARGS",
  "VARIABLE_ARGS_POST", "VARIABLE_ARGS_GET", "VARIABLE_FILES_SIZES",
  "VARIABLE_FILES_NAMES", "VARIABLE_FILES_TMP_CONTENT",
  "VARIABLE_MULTIPART_FILENAME", "VARIABLE_MULTIPART_NAME",
  "VARIABLE_MATCHED_VARS_NAMES", "VARIABLE_MATCHED_VARS", "VARIABLE_FILES",
  "VARIABLE_REQUEST_COOKIES", "VARIABLE_REQUEST_HEADERS",
  "VARIABLE_RESPONSE_HEADERS", "VARIABLE_GEO",
  "VARIABLE_REQUEST_COOKIES_NAMES", "VARIABLE_ARGS_COMBINED_SIZE",
  "VARIABLE_ARGS_GET_NAMES", "VARIABLE_RULE", "\"Variable ARGS_NAMES\"",
  "VARIABLE_ARGS_POST_NAMES", "\"AUTH_TYPE\"", "\"FILES_COMBINED_SIZE\"",
  "\"FILES_TMPNAMES\"", "\"FULL_REQUEST\"", "\"FULL_REQUEST_LENGTH\"",
  "\"INBOUND_DATA_ERROR\"", "\"MATCHED_VAR\"", "\"MATCHED_VAR_NAME\"",
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
  "\"OPERATOR_STR_EQ\"", "\"OPERATOR_STR_MATCH\"",
  "\"OPERATOR_UNCONDITIONAL_MATCH\"", "\"OPERATOR_VALIDATE_BYTE_RANGE\"",
  "\"OPERATOR_VALIDATE_DTD\"", "\"OPERATOR_VALIDATE_HASH\"",
  "\"OPERATOR_VALIDATE_SCHEMA\"", "\"OPERATOR_VALIDATE_URL_ENCODING\"",
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
  "\"CONFIG_SEC_SENSOR_ID\"", "\"CONFIG_DIR_REQ_BODY\"",
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
  "\"Dictionary element, selected by regexp\"", "$accept", "input", "line",
  "audit_log", "actions", "actions_may_quoted", "op", "op_before_init",
  "expression", "variables", "variables_pre_process",
  "variables_may_be_quoted", "var", "act", "setvar_action",
  "run_time_string", YY_NULLPTR
  };

#if YYDEBUG
  const unsigned short
  seclang_parser::yyrline_[] =
  {
       0,   707,   707,   711,   712,   715,   720,   726,   732,   736,
     740,   746,   752,   758,   764,   769,   774,   780,   787,   791,
     795,   801,   805,   809,   814,   819,   824,   829,   833,   840,
     844,   851,   857,   867,   876,   886,   895,   908,   912,   916,
     920,   924,   928,   932,   936,   940,   944,   949,   953,   957,
     961,   965,   969,   974,   979,   983,   987,   991,   995,   999,
    1003,  1007,  1011,  1015,  1019,  1023,  1027,  1031,  1035,  1039,
    1043,  1047,  1051,  1065,  1066,  1091,  1110,  1125,  1149,  1205,
    1209,  1213,  1217,  1221,  1225,  1229,  1233,  1237,  1246,  1250,
    1255,  1258,  1263,  1268,  1273,  1278,  1281,  1286,  1289,  1294,
    1299,  1302,  1307,  1312,  1317,  1322,  1327,  1332,  1337,  1340,
    1345,  1350,  1355,  1360,  1363,  1368,  1373,  1378,  1391,  1404,
    1417,  1430,  1443,  1469,  1497,  1509,  1529,  1557,  1562,  1567,
    1576,  1581,  1585,  1589,  1593,  1597,  1601,  1605,  1610,  1615,
    1627,  1633,  1637,  1641,  1652,  1661,  1662,  1669,  1674,  1679,
    1733,  1740,  1748,  1785,  1789,  1796,  1801,  1807,  1813,  1819,
    1826,  1836,  1840,  1844,  1848,  1852,  1856,  1860,  1864,  1868,
    1872,  1876,  1880,  1884,  1888,  1892,  1896,  1900,  1904,  1908,
    1912,  1916,  1920,  1924,  1928,  1932,  1936,  1940,  1944,  1948,
    1952,  1956,  1960,  1964,  1968,  1972,  1976,  1980,  1984,  1988,
    1992,  1996,  2000,  2004,  2008,  2012,  2016,  2020,  2024,  2028,
    2032,  2036,  2040,  2044,  2048,  2052,  2056,  2060,  2064,  2068,
    2072,  2076,  2080,  2084,  2088,  2092,  2096,  2100,  2104,  2108,
    2112,  2116,  2120,  2124,  2128,  2132,  2136,  2140,  2144,  2148,
    2152,  2156,  2160,  2164,  2168,  2172,  2176,  2180,  2184,  2188,
    2192,  2197,  2201,  2205,  2210,  2214,  2218,  2223,  2228,  2232,
    2236,  2240,  2244,  2248,  2252,  2256,  2260,  2264,  2268,  2272,
    2276,  2280,  2284,  2288,  2292,  2296,  2300,  2304,  2308,  2312,
    2316,  2320,  2324,  2328,  2332,  2336,  2340,  2344,  2348,  2352,
    2356,  2360,  2364,  2368,  2372,  2376,  2380,  2384,  2388,  2392,
    2396,  2400,  2404,  2408,  2412,  2416,  2420,  2424,  2428,  2432,
    2436,  2440,  2444,  2448,  2452,  2456,  2460,  2464,  2468,  2476,
    2483,  2490,  2497,  2504,  2511,  2518,  2525,  2532,  2539,  2546,
    2553,  2563,  2567,  2571,  2575,  2579,  2583,  2587,  2591,  2596,
    2601,  2606,  2610,  2614,  2618,  2622,  2627,  2632,  2636,  2640,
    2644,  2648,  2652,  2656,  2660,  2664,  2668,  2672,  2676,  2680,
    2684,  2689,  2693,  2697,  2701,  2705,  2709,  2713,  2717,  2721,
    2725,  2729,  2733,  2737,  2741,  2745,  2749,  2753,  2757,  2761,
    2765,  2769,  2773,  2777,  2781,  2785,  2789,  2793,  2797,  2801,
    2805,  2809,  2813,  2817,  2821,  2825,  2829,  2833,  2837,  2841,
    2845,  2849,  2853,  2857,  2861,  2865,  2869,  2873,  2877,  2881,
    2885,  2889,  2893,  2897,  2901,  2905,  2909,  2913,  2917,  2921,
    2925,  2929,  2933,  2937,  2941,  2945,  2949,  2953,  2957,  2961,
    2968,  2972,  2976,  2980,  2984,  2991,  2996,  3001,  3007
  };

  // Print the state stack on the debug stream.
  void
  seclang_parser::yystack_print_ ()
  {
    *yycdebug_ << "Stack now";
    for (stack_type::const_iterator
           i = yystack_.begin (),
           i_end = yystack_.end ();
         i != i_end; ++i)
      *yycdebug_ << ' ' << i->state;
    *yycdebug_ << '\n';
  }

  // Report on the debug stream that the rule \a yyrule is going to be reduced.
  void
  seclang_parser::yy_reduce_print_ (int yyrule)
  {
    unsigned yylno = yyrline_[yyrule];
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
#line 6887 "seclang-parser.cc" // lalr1.cc:1242
#line 3014 "seclang-parser.yy" // lalr1.cc:1243


void yy::seclang_parser::error (const location_type& l, const std::string& m) {
    driver.error (l, m);
}
