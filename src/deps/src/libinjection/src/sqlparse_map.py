#!/usr/bin/env python3
# pylint: disable=C0301,C0302
# Turn off line-too-long, and too-many-lines warnings
#
#  Copyright 2012, 2013 Nick Galbreath
#  nickg@client9.com
#  BSD License -- see COPYING.txt for details
#

"""
Data for libinjection.   These are simple data structures
which are exported to JSON.  This is done so comments can be
added to the data directly (JSON doesn't support comments).
"""

KEYWORDS = {
'_BIG5': 't',
'_DEC8': 't',
'_CP850': 't',
'_HP8': 't',
'_KOI8R': 't',
'_LATIN1': 't',
'_LATIN2': 't',
'_SWE7': 't',
'_ASCII': 't',
'_UJIS': 't',
'_SJIS': 't',
'_HEBREW': 't',
'_TIS620': 't',
'_EUCKR': 't',
'_KOI8U': 't',
'_GB2312': 't',
'_GREEK': 't',
'_CP1250': 't',
'_GBK': 't',
'_LATIN5': 't',
'_ARMSCII8': 't',
'_UTF8': 't',
'_USC2': 't',
'_CP866': 't',
'_KEYBCS2': 't',
'_MACCE': 't',
'_MACROMAN': 't',
'_CP852': 't',
'_LATIN7': 't',
'_CP1251': 't',
'_CP1257': 't',
'_BINARY': 't',
'_GEOSTD8': 't',
'_CP932': 't',
'_EUCJPMS': 't',

'AUTOINCREMENT'              : 'k',
'UTL_INADDR.GET_HOST_ADDRESS': 'f',
'UTL_INADDR.GET_HOST_NAME'   : 'f',
'UTL_HTTP.REQUEST'           : 'f',
# ORACLE
# http://blog.red-database-security.com/
#  /2009/01/17/tutorial-oracle-sql-injection-in-webapps-part-i/print/
'DBMS_PIPE.RECEIVE_MESSAGE':   'f',
'CTXSYS.DRITHSX.SN': 'f',
'SYS.STRAGG': 'f',
'SYS.FN_BUILTIN_PERMISSIONS'  : 'f',
'SYS.FN_GET_AUDIT_FILE'       : 'f',
'SYS.FN_MY_PERMISSIONS'       : 'f',
'SYS.DATABASE_NAME'           : 'n',
'ABORT'                       : 'k',
'ABS'                         : 'f',
'ACCESSIBLE'                  : 'k',
'ACOS'                        : 'f',
'ADDDATE'                     : 'f',
'ADDTIME'                     : 'f',
'AES_DECRYPT'                 : 'f',
'AES_ENCRYPT'                 : 'f',
'AGAINST'                     : 'k',
'AGE'                         : 'f',
'ALTER'                       : 'k',

# 'ALL_USERS' - oracle
'ALL_USERS'                   : 'k',

'ANALYZE'                     : 'k',
'AND'                         : '&',

# ANY -- acts like a function
# http://dev.mysql.com/doc/refman/5.0/en/any-in-some-subqueries.html
'ANY'                         : 'f',

# pgsql
'ANYELEMENT'                  : 't',
'ANYARRAY'                    : 't',
'ANYNONARRY'                  : 't',
'CSTRING'                     : 't',

# array_... pgsql
'ARRAY_AGG'                   : 'f',
'ARRAY_CAT'                   : 'f',
'ARRAY_NDIMS'                 : 'f',
'ARRAY_DIM'                   : 'f',
'ARRAY_FILL'                  : 'f',
'ARRAY_LENGTH'                : 'f',
'ARRAY_LOWER'                 : 'f',
'ARRAY_UPPER'                 : 'f',
'ARRAY_PREPEND'               : 'f',
'ARRAY_TO_STRING'             : 'f',
'ARRAY_TO_JSON'               : 'f',
'APP_NAME'                    : 'f',
'APPLOCK_MODE'                : 'f',
'APPLOCK_TEST'                : 'f',
'ASSEMBLYPROPERTY'            : 'f',
'AS'                          : 'k',
'ASC'                         : 'k',
'ASCII'                       : 'f',
'ASENSITIVE'                  : 'k',
'ASIN'                        : 'f',
'ASYMKEY_ID'                  : 'f',
'ATAN'                        : 'f',
'ATAN2'                       : 'f',
'AVG'                         : 'f',
'BEFORE'                      : 'k',
'BEGIN'                       : 'T',
'BEGIN GOTO'                  : 'T',
'BEGIN TRY'                   : 'T',
'BEGIN TRY DECLARE'           : 'T',
'BEGIN DECLARE'               : 'T',
'BENCHMARK'                   : 'f',
'BETWEEN'                     : 'o',
'BIGINT'                      : 't',
'BIGSERIAL'                   : 't',
'BIN'                         : 'f',
# "select binary 1"  forward type operator
'BINARY'                      : 't',
'BINARY_DOUBLE_INFINITY'      : '1',
'BINARY_DOUBLE_NAN'           : '1',
'BINARY_FLOAT_INFINITY'       : '1',
'BINARY_FLOAT_NAN'            : '1',
'BINBINARY'                   : 'f',
'BIT_AND'                     : 'f',
'BIT_COUNT'                   : 'f',
'BIT_LENGTH'                  : 'f',
'BIT_OR'                      : 'f',
'BIT_XOR'                     : 'f',
'BLOB'                        : 'k',
# pgsql
'BOOL_AND'                    : 'f',
# pgsql
'BOOL_OR'                     : 'f',
'BOOLEAN'                     : 't',
'BOTH'                        : 'k',
# pgsql
'BTRIM'                       : 'f',
'BY'                          : 'n',
'BYTEA'                       : 't',

# MS ACCESS
#
#
'CBOOL'                       : 'f',
'CBYTE'                       : 'f',
'CCUR'                        : 'f',
'CDATE'                       : 'f',
'CDBL'                        : 'f',
'CINT'                        : 'f',
'CLNG'                        : 'f',
'CSNG'                        : 'f',
'CVAR'                        : 'f',
# CHANGES: sqlite3
'CHANGES'                     : 'f',
'CHDIR'                       : 'f',
'CHDRIVE'                     : 'f',
'CURDIR'                      : 'f',
'FILEDATETIME'                : 'f',
'FILELEN'                     : 'f',
'GETATTR'                     : 'f',
'MKDIR'                       : 'f',
'SETATTR'                     : 'f',
'DAVG'                        : 'f',
'DCOUNT'                      : 'f',
'DFIRST'                      : 'f',
'DLAST'                       : 'f',
'DLOOKUP'                     : 'f',
'DMAX'                        : 'f',
'DMIN'                        : 'f',
'DSUM'                        : 'f',

# TBD
'DO'                          : 'n',

'CALL'                        : 'T',
'CASCADE'                     : 'k',
'CASE'                        : 'E',
'CAST'                        : 'f',
# pgsql 'cube root' lol
'CBRT'                        : 'f',
'CEIL'                        : 'f',
'CEILING'                     : 'f',
'CERTENCODED'                 : 'f',
'CERTPRIVATEKEY'              : 'f',
'CERT_ID'                     : 'f',
'CERT_PROPERTY'               : 'f',
'CHANGE'                      : 'k',

# 'CHAR'
# sometimes a function too
# TBD
'CHAR'                        : 'f',

'CHARACTER'                   : 't',
'CHARACTER_LENGTH'            : 'f',
'CHARINDEX'                   : 'f',
'CHARSET'                     : 'f',
'CHAR_LENGTH'                 : 'f',

# mysql keyword but not clear how used
'CHECK'                       : 'n',

'CHECKSUM_AGG'                : 'f',
'CHOOSE'                      : 'f',
'CHR'                         : 'f',
'CLOCK_TIMESTAMP'             : 'f',
'COALESCE'                    : 'f',
'COERCIBILITY'                : 'f',
'COL_LENGTH'                  : 'f',
'COL_NAME'                    : 'f',
'COLLATE'                     : 'A',
'COLLATION'                   : 'f',
'COLLATIONPROPERTY'           : 'f',

# TBD
'COLUMN'                      : 'k',

'COLUMNPROPERTY'              : 'f',
'COLUMNS_UPDATED'             : 'f',
'COMPRESS'                    : 'f',
'CONCAT'                      : 'f',
'CONCAT_WS'                   : 'f',
'CONDITION'                   : 'k',
'CONNECTION_ID'               : 'f',
'CONSTRAINT'                  : 'k',
'CONTINUE'                    : 'k',
'CONV'                        : 'f',
'CONVERT'                     : 'f',
# pgsql
'CONVERT_FROM'                : 'f',
# pgsql
'CONVERT_TO'                  : 'f',
'CONVERT_TZ'                  : 'f',
'COS'                         : 'f',
'COT'                         : 'f',
'COUNT'                       : 'f',
'COUNT_BIG'                   : 'k',
'CRC32'                       : 'f',
'CREATE'                      : 'E',
'CREATE OR'                   : 'n',
'CREATE OR REPLACE'           : 'T',
'CROSS'                       : 'n',
'CUME_DIST'                   : 'f',
'CURDATE'                     : 'f',
'CURRENT_DATABASE'            : 'f',


# MYSQL Dual, function or variable-like
# And IBM
# http://publib.boulder.ibm.com/infocenter/iseries/v5r4/index.jsp?topic=%2Fsqlp%2Frbafykeyu.htm
'CURRENT_DATE'                : 'v',
'CURRENT_TIME'                : 'v',
'CURRENT_TIMESTAMP'           : 'v',

'CURRENT_QUERY'               : 'f',
'CURRENT_SCHEMA'              : 'f',
'CURRENT_SCHEMAS'             : 'f',
'CURRENT_SETTING'             : 'f',
# current_user sometimes acts like a variable
# other times it acts like a function depending
# on database.  This is converted in the right
# type in the folding code
# mysql = function
# ??    = variable
'CURRENT_USER'                : 'v',
'CURRENTUSER'                 : 'f',

#
# DB2 'Special Registers'
# These act like variables
# http://publib.boulder.ibm.com/infocenter/iseries/v5r4/index.jsp?topic=%2Fsqlp%2Frbafykeyu.htm
'CURRENT DATE'         : 'v',
'CURRENT DEGREE'       : 'v',
'CURRENT_PATH'         : 'v',
'CURRENT PATH'         : 'v',
'CURRENT FUNCTION'     : 'v',
'CURRENT SCHEMA'       : 'v',
'CURRENT_SERVER'       : 'v',
'CURRENT SERVER'       : 'v',
'CURRENT TIME'         : 'v',
'CURRENT_TIMEZONE'     : 'v',
'CURRENT TIMEZONE'     : 'v',
'CURRENT FUNCTION PATH': 'v',

# pgsql
'CURRVAL'                     : 'f',
'CURSOR'                      : 'k',
'CURSOR_STATUS'               : 'f',
'CURTIME'                     : 'f',

# this might be a function
'DATABASE'                    : 'n',
'DATABASE_PRINCIPAL_ID'       : 'f',
'DATABASEPROPERTYEX'          : 'f',
'DATABASES'                   : 'k',
'DATALENGTH'                  : 'f',
'DATE'                        : 'f',
'DATEDIFF'                    : 'f',
# sqlserver
'DATENAME'                    : 'f',
#sqlserver
'DATEPART'                    : 'f',
'DATEADD'                     : 'f',
'DATESERIAL'                  : 'f',
'DATEVALUE'                   : 'f',
'DATEFROMPARTS'               : 'f',
'DATETIME2FROMPARTS'          : 'f',
'DATETIMEFROMPARTS'           : 'f',
# sqlserver
'DATETIMEOFFSETFROMPARTS'     : 'f',
'DATE_ADD'                    : 'f',
'DATE_FORMAT'                 : 'f',
'DATE_PART'                   : 'f',
'DATE_SUB'                    : 'f',
'DATE_TRUNC'                  : 'f',
'DAY'                         : 'f',
'DAYNAME'                     : 'f',
'DAYOFMONTH'                  : 'f',
'DAYOFWEEK'                   : 'f',
'DAYOFYEAR'                   : 'f',
'DAY_HOUR'                    : 'k',
'DAY_MICROSECOND'             : 'k',
'DAY_MINUTE'                  : 'k',
'DAY_SECOND'                  : 'k',
'DB_ID'                       : 'f',
'DB_NAME'                     : 'f',
'DEC'                         : 'k',
'DECIMAL'                     : 't',
# can only be used after a ';'
'DECLARE'                     : 'T',
'DECODE'                      : 'f',
'DECRYPTBYASMKEY'             : 'f',
'DECRYPTBYCERT'               : 'f',
'DECRYPTBYKEY'                : 'f',
'DECRYPTBYKEYAUTOCERT'        : 'f',
'DECRYPTBYPASSPHRASE'         : 'f',
'DEFAULT'                     : 'k',
'DEGREES'                     : 'f',
'DELAY'                       : 'k',
'DELAYED'                     : 'k',
'DELETE'                      : 'T',
'DENSE_RANK'                  : 'f',
'DESC'                        : 'k',
'DESCRIBE'                    : 'k',
'DES_DECRYPT'                 : 'f',
'DES_ENCRYPT'                 : 'f',
'DETERMINISTIC'               : 'k',
'DIFFERENCE'                  : 'f',
'DISTINCTROW'                  : 'k',
'DISTINCT'                    : 'k',
'DIV'                         : 'o',
'DOUBLE'                      : 't',
'DROP'                        : 'T',
'DUAL'                        : 'n',
'EACH'                        : 'k',
'ELSE'                        : 'k',
'ELSEIF'                      : 'k',
'ELT'                         : 'f',
'ENCLOSED'                    : 'k',
'ENCODE'                      : 'f',
'ENCRYPT'                     : 'f',
'ENCRYPTBYASMKEY'             : 'f',
'ENCRYPTBYCERT'               : 'f',
'ENCRYPTBYKEY'                : 'f',
'ENCRYPTBYPASSPHRASE'         : 'f',

#
# sqlserver
'EOMONTH'                     : 'f',

# pgsql
'ENUM_FIRST'                  : 'f',
'ENUM_LAST'                   : 'f',
'ENUM_RANGE'                  : 'f',

# special MS-ACCESS operator
# http://office.microsoft.com/en-001/access-help/table-of-operators-HA010235862.aspx
'EQV'                         : 'o',

'ESCAPED'                     : 'k',

# DB2, others..
# http://publib.boulder.ibm.com/infocenter/iseries/v5r4/index.jsp?topic=%2Fsqlp%2Frbafykeyu.htm
'EXCEPT'                       : 'U',

# TBD
#'END'                         : 'k',

# 'EXEC', 'EXECUTE' - MSSQL
#  http://msdn.microsoft.com/en-us/library/ms175046.aspx
'EXEC'                        : 'T',
'EXECUTE'                     : 'T',
'EXISTS'                      : 'f',
'EXIT'                        : 'k',
'EXP'                         : 'f',
'EXPLAIN'                     : 'k',
'EXPORT_SET'                  : 'f',
'EXTRACT'                     : 'f',
'EXTRACTVALUE'                : 'f',
'EXTRACT_VALUE'               : 'f',
'EVENTDATA'                   : 'f',
'FALSE'                       : '1',
'FETCH'                       : 'k',
'FIELD'                       : 'f',
'FILE_ID'                     : 'f',
'FILE_IDEX'                   : 'f',
'FILE_NAME'                   : 'f',
'FILEGROUP_ID'                : 'f',
'FILEGROUP_NAME'              : 'f',
'FILEGROUPPROPERTY'           : 'f',
'FILEPROPERTY'                : 'f',

# http://www-01.ibm.com/support/knowledgecenter/#!/SSGU8G_11.50.0/com.ibm.sqls.doc/ids_sqs_1526.htm
'FILETOBLOB'                  : 'f',
'FILETOCLOB'                  : 'f',
'FIND_IN_SET'                 : 'f',
'FIRST_VALUE'                 : 'f',
'FLOAT'                       : 't',
'FLOAT4'                       : 't',
'FLOAT8'                       : 't',
'FLOOR'                       : 'f',
'FN_VIRTUALFILESTATS'         : 'f',
'FORCE'                       : 'k',
'FOREIGN'                     : 'k',
'FOR'                         : 'n',
'FORMAT'                      : 'f',
'FOUND_ROWS'                  : 'f',
'FROM'                        : 'k',
# MySQL 5.6
'FROM_BASE64'                 : 'f',
'FROM_DAYS'                   : 'f',
'FROM_UNIXTIME'               : 'f',
'FUNCTION'                    : 'k',
'FULLTEXT'                    : 'k',
'FULLTEXTCATALOGPROPERTY'     : 'f',
'FULLTEXTSERVICEPROPERTY'     : 'f',
# pgsql
'GENERATE_SERIES'             : 'f',
# pgsql
'GENERATE_SUBSCRIPTS'         : 'f',
# sqlserver
'GETDATE'                     : 'f',
# sqlserver
'GETUTCDATE'                  : 'f',
# pgsql
'GET_BIT'                     : 'f',
# pgsql
'GET_BYTE'                    : 'f',
'GET_FORMAT'                  : 'f',
'GET_LOCK'                    : 'f',
'GO'                          : 'T',
'GOTO'                        : 'T',
'GRANT'                       : 'k',
'GREATEST'                    : 'f',
'GROUP'                       : 'n',
'GROUPING'                    : 'f',
'GROUPING_ID'                 : 'f',
'GROUP_CONCAT'                : 'f',

# MYSQL http://dev.mysql.com/doc/refman/5.6/en/handler.html
'HANDLER'                     : 'T',

'HAS_PERMS_BY_NAME'           : 'f',
'HASHBYTES'                   : 'f',
#
# 'HAVING' - MSSQL
'HAVING'                      : 'B',

'HEX'                         : 'f',
'HIGH_PRIORITY'               : 'k',
'HOUR'                        : 'f',
'HOUR_MICROSECOND'            : 'k',
'HOUR_MINUTE'                 : 'k',
'HOUR_SECOND'                 : 'k',

# 'HOST_NAME' -- transact-sql
'HOST_NAME'                   : 'f',

'IDENT_CURRENT'               : 'f',
'IDENT_INCR'                  : 'f',
'IDENT_SEED'                  : 'f',
'IDENTIFY'                    : 'f',

# 'IF - if is normally a function, except in TSQL
# http://msdn.microsoft.com/en-us/library/ms182717.aspx
'IF'                          : 'f',

'IF EXISTS'                   : 'f',
'IF NOT'                      : 'f',
'IF NOT EXISTS'               : 'f',

'IFF'                         : 'f',
'IFNULL'                      : 'f',
'IGNORE'                      : 'k',
'IIF'                         : 'f',

# IN is a special case.. sometimes a function, sometimes a keyword
# corrected inside the folding code
'IN'                          : 'k',

'INDEX'                       : 'k',
'INDEX_COL'                   : 'f',
'INDEXKEY_PROPERTY'           : 'f',
'INDEXPROPERTY'               : 'f',
'INET_ATON'                   : 'f',
'INET_NTOA'                   : 'f',
'INFILE'                      : 'k',
# pgsql
'INITCAP'                     : 'f',
'INNER'                       : 'k',
'INOUT'                       : 'k',
'INSENSITIVE'                 : 'k',
'INSERT'                      : 'E',
'INSERT INTO'                 : 'T',
'INSERT IGNORE'               : 'E',
'INSERT LOW_PRIORITY INTO'    : 'T',
'INSERT LOW_PRIORITY'         : 'E',
'INSERT DELAYED INTO'         : 'T',
'INSERT DELAYED'              : 'E',
'INSERT HIGH_PRIORITY INTO'   : 'T',
'INSERT HIGH_PRIORITY'        : 'E',
'INSERT IGNORE INTO'          : 'T',
'INSTR'                       : 'f',
'INSTRREV'                    : 'f',
'INT'                         : 't',
'INT1'                        : 't',
'INT2'                        : 't',
'INT3'                        : 't',
'INT4'                        : 't',
'INT8'                        : 't',
'INTEGER'                     : 't',
# INTERSECT - IBM DB2, others
# http://publib.boulder.ibm.com/infocenter/iseries/v5r4/index.jsp?topic=%2Fsqlp%2Frbafykeyu.htm
'INTERSECT'                   : 'U',
'INTERVAL'                    : 'k',
'INTO'                        : 'k',
'IS'                          : 'o',
 #sqlserver
'ISDATE'                      : 'f',
'ISEMPTY'                     : 'f',
# pgsql
'ISFINITE'                    : 'f',
'ISNULL'                      : 'f',
'ISNUMERIC'                   : 'f',
'IS_FREE_LOCK'                : 'f',
#
# 'IS_MEMBER' - MSSQL
'IS_MEMBER'                   : 'f',
'IS_ROLEMEMBER'               : 'f',
'IS_OBJECTSIGNED'             : 'f',
# 'IS_SRV...' MSSQL
'IS_SRVROLEMEMBER'            : 'f',
'IS_USED_LOCK'                : 'f',
'ITERATE'                     : 'k',
'JOIN'                        : 'k',
'JSON_KEYS'                   : 'f',
'JULIANDAY'                   : 'f',
# pgsql
'JUSTIFY_DAYS'                : 'f',
'JUSTIFY_HOURS'               : 'f',
'JUSTIFY_INTERVAL'            : 'f',
'KEY_ID'                      : 'f',
'KEY_GUID'                    : 'f',
'KEYS'                        : 'k',
'KILL'                        : 'k',
'LAG'                         : 'f',
'LAST_INSERT_ID'              : 'f',
'LAST_INSERT_ROWID'           : 'f',
'LAST_VALUE'                  : 'f',
'LASTVAL'                     : 'f',
'LCASE'                       : 'f',
'LEAD'                        : 'f',
'LEADING'                     : 'k',
'LEAST'                       : 'f',
'LEAVE'                       : 'k',
'LEFT'                        : 'f',
'LENGTH'                      : 'f',
'LIKE'                        : 'o',
'LIMIT'                       : 'B',
'LINEAR'                      : 'k',
'LINES'                       : 'k',
'LN'                          : 'f',
'LOAD'                        : 'k',
'LOAD_EXTENSION'              : 'f',
'LOAD_FILE'                   : 'f',

# MYSQL http://dev.mysql.com/doc/refman/5.6/en/load-data.html
'LOAD DATA'                   : 'T',
'LOAD XML'                    : 'T',
# MYSQL function vs. variable
'LOCALTIME'                   : 'v',
'LOCALTIMESTAMP'              : 'v',

'LOCATE'                      : 'f',
'LOCK'                        : 'n',
'LOG'                         : 'f',
'LOG10'                       : 'f',
'LOG2'                        : 'f',
'LONGBLOB'                    : 'k',
'LONGTEXT'                    : 'k',
'LOOP'                        : 'k',
'LOWER'                       : 'f',
'LOWER_INC'                   : 'f',
'LOWER_INF'                   : 'f',
'LOW_PRIORITY'                : 'k',
'LPAD'                        : 'f',
'LTRIM'                       : 'f',
'MAKEDATE'                    : 'f',
'MAKE_SET'                    : 'f',
'MASKLEN'                     : 'f',
'MASTER_BIND'                 : 'k',
'MASTER_POS_WAIT'             : 'f',
'MASTER_SSL_VERIFY_SERVER_CERT': 'k',
'MATCH'                       : 'k',
'MAX'                         : 'f',
'MAXVALUE'                    : 'k',
'MD5'                         : 'f',
'MEDIUMBLOB'                  : 'k',
'MEDIUMINT'                   : 'k',
'MEDIUMTEXT'                  : 'k',
'MERGE'                       : 'k',
'MICROSECOND'                 : 'f',
'MID'                         : 'f',
'MIDDLEINT'                   : 'k',
'MIN'                         : 'f',
'MINUTE'                      : 'f',
'MINUTE_MICROSECOND'          : 'k',
'MINUTE_SECOND'               : 'k',
'MOD'                         : 'o',
'MODE'                        : 'n',
'MODIFIES'                    : 'k',
'MONEY'                       : 't',
'MONTH'                       : 'f',
'MONTHNAME'                   : 'f',
'NAME_CONST'                  : 'f',
'NATURAL'                     : 'n',
'NETMASK'                     : 'f',
'NEXTVAL'                     : 'f',
'NOT'                         : 'o', # UNARY OPERATOR
'NOTNULL'                     : 'k',
'NOW'                         : 'f',
# oracle http://www.shift-the-oracle.com/sql/select-for-update.html
'NOWAIT'                      : 'k',
'NO_WRITE_TO_BINLOG'          : 'k',
'NTH_VALUE'                   : 'f',
'NTILE'                       : 'f',

# NULL is treated as "variable" type
# Sure it's a keyword, but it's really more
# like a number or value.
# but we don't want it folded away
# since it's a good indicator of SQL
# ('true' and 'false' are also similar)
'NULL'                        : 'v',
# unknown is mysql keyword, again treat
# as 'v' type
'UNKNOWN'                     : 'v',

'NULLIF'                      : 'f',
'NUMERIC'                     : 't',
# MSACCESS
'NZ'                          : 'f',
'OBJECT_DEFINITION'           : 'f',
'OBJECT_ID'                   : 'f',
'OBJECT_NAME'                 : 'f',
'OBJECT_SCHEMA_NAME'          : 'f',
'OBJECTPROPERTY'              : 'f',
'OBJECTPROPERTYEX'            : 'f',
'OCT'                         : 'f',
'OCTET_LENGTH'                : 'f',
'OFFSET'                      : 'k',
'OID'                         : 't',
'OLD_PASSWORD'                : 'f',

# need to investigate how used
#'ON'                          : 'k',
'ONE_SHOT'                    : 'k',

# obviously not SQL but used in attacks
'OWN3D'                       : 'k',

# 'OPEN'
# http://msdn.microsoft.com/en-us/library/ms190500.aspx
'OPEN'                        : 'k',
# 'OPENDATASOURCE'
# http://msdn.microsoft.com/en-us/library/ms179856.aspx
'OPENDATASOURCE'              : 'f',
'OPENXML'                     : 'f',
'OPENQUERY'                   : 'f',
'OPENROWSET'                  : 'f',
'OPTIMIZE'                    : 'k',
'OPTION'                      : 'k',
'OPTIONALLY'                  : 'k',
'OR'                          : '&',
'ORD'                         : 'f',
'ORDER'                       : 'n',
'ORIGINAL_DB_NAME'            : 'f',
'ORIGINAL_LOGIN'              : 'f',
# is a mysql reserved word but not really used
'OUT'                         : 'n',
'OUTER'                       : 'n',
'OUTFILE'                     : 'k',
# unusual PGSQL operator that looks like a function
'OVERLAPS'                    : 'f',
# pgsql
'OVERLAY'                     : 'f',
'PARSENAME'                   : 'f',
'PARTITION'                   : 'k',
# 'PARTITION BY' IBM DB2
# http://publib.boulder.ibm.com/infocenter/iseries/v5r4/index.jsp?topic=%2Fsqlp%2Frbafykeyu.htm
'PARTITION BY'                : 'B',
# keyword "SET PASSWORD", and a function
'PASSWORD'                    : 'n',
'PATINDEX'                    : 'f',
'PATHINDEX'                   : 'f',
'PERCENT_RANK'                : 'f',
'PERCENTILE_COUNT'            : 'f',
'PERCENTILE_DISC'             : 'f',
'PERCENTILE_RANK'             : 'f',
'PERIOD_ADD'                  : 'f',
'PERIOD_DIFF'                 : 'f',
'PERMISSIONS'                 : 'f',
'PG_ADVISORY_LOCK'            : 'f',
'PG_BACKEND_PID'              : 'f',
'PG_CANCEL_BACKEND'           : 'f',
'PG_CREATE_RESTORE_POINT'     : 'f',
'PG_RELOAD_CONF'              : 'f',
'PG_CLIENT_ENCODING'          : 'f',
'PG_CONF_LOAD_TIME'           : 'f',
'PG_LISTENING_CHANNELS'       : 'f',
'PG_HAS_ROLE'                 : 'f',
'PG_IS_IN_RECOVERY'           : 'f',
'PG_IS_OTHER_TEMP_SCHEMA'     : 'f',
'PG_LS_DIR'                   : 'f',
'PG_MY_TEMP_SCHEMA'           : 'f',
'PG_POSTMASTER_START_TIME'    : 'f',
'PG_READ_FILE'                : 'f',
'PG_READ_BINARY_FILE'         : 'f',
'PG_ROTATE_LOGFILE'           : 'f',
'PG_STAT_FILE'                : 'f',
'PG_SLEEP'                    : 'f',
'PG_START_BACKUP'             : 'f',
'PG_STOP_BACKUP'              : 'f',
'PG_SWITCH_XLOG'              : 'f',
'PG_TERMINATE_BACKEND'        : 'f',
'PG_TRIGGER_DEPTH'            : 'f',
'PI'                          : 'f',
'POSITION'                    : 'f',
'POW'                         : 'f',
'POWER'                       : 'f',
'PRECISION'                   : 'k',
# http://msdn.microsoft.com/en-us/library/ms176047.aspx
'PRINT'                       : 'T',

'PRIMARY'                     : 'k',
'PROCEDURE'                   : 'k',
'PROCEDURE ANALYSE'           : 'f',
'PUBLISHINGSERVERNAME'        : 'f',
'PURGE'                       : 'k',
'PWDCOMPARE'                  : 'f',
'PWDENCRYPT'                  : 'f',
'QUARTER'                     : 'f',
'QUOTE'                       : 'f',
# pgsql
'QUOTE_IDENT'                 : 'f',
'QUOTENAME'                   : 'f',
# pgsql
'QUOTE_LITERAL'               : 'f',
# pgsql
'QUOTE_NULLABLE'              : 'f',
'RADIANS'                     : 'f',
'RAND'                        : 'f',
'RANDOM'                      : 'f',
# http://msdn.microsoft.com/en-us/library/ms178592.aspx
'RAISEERROR'                  : 'E',
# 'RANDOMBLOB' - sqlite3
'RANDOMBLOB'                  : 'f',
'RANGE'                       : 'k',
'RANK'                        : 'f',
'READ'                        : 'k',
'READS'                       : 'k',
'READ_WRITE'                  : 'k',

# 'REAL' only used in data definition
'REAL'                        : 't',
'REFERENCES'                  : 'k',
# pgsql, mariadb
'REGEXP'                      : 'o',
'REGEXP_INSTR'                : 'f',
'REGEXP_REPLACE'              : 'f',
'REGEXP_MATCHES'              : 'f',
'REGEXP_SUBSTR'               : 'f',
'REGEXP_SPLIT_TO_TABLE'       : 'f',
'REGEXP_SPLIT_TO_ARRAY'       : 'f',
'REGPROC'                     : 't',
'REGPROCEDURE'                : 't',
'REGOPER'                     : 't',
'REGOPERATOR'                 : 't',
'REGCLASS'                    : 't',
'REGTYPE'                     : 't',
'REGCONFIG'                   : 't',
'REGDICTIONARY'               : 't',
'RELEASE'                     : 'k',
'RELEASE_LOCK'                : 'f',
'RENAME'                      : 'k',
'REPEAT'                      : 'k',

# keyword and function
'REPLACE'                     : 'k',
'REPLICATE'                   : 'f',
'REQUIRE'                     : 'k',
'RESIGNAL'                    : 'k',
'RESTRICT'                    : 'k',
'RETURN'                      : 'k',
'REVERSE'                     : 'f',
'REVOKE'                      : 'k',
# RIGHT JOIN vs. RIGHT()
# tricky since it's a function in pgsql
# needs review
'RIGHT'                       : 'n',
'RLIKE'                       : 'o',
'ROUND'                       : 'f',
'ROW'                        : 'f',
'ROW_COUNT'                   : 'f',
'ROW_NUMBER'                  : 'f',
'ROW_TO_JSON'                 : 'f',
'RPAD'                        : 'f',
'RTRIM'                       : 'f',
'SCHEMA'                      : 'k',
'SCHEMA_ID'                   : 'f',
'SCHAMA_NAME'                 : 'f',
'SCHEMAS'                     : 'k',
'SCOPE_IDENTITY'              : 'f',
'SECOND_MICROSECOND'          : 'k',
'SEC_TO_TIME'                 : 'f',
'SELECT'                      : 'E',
'SENSITIVE'                   : 'k',
'SEPARATOR'                   : 'k',
'SERIAL'                      : 't',
'SERIAL2'                     : 't',
'SERIAL4'                     : 't',
'SERIAL8'                     : 't',
'SERVERPROPERTY'              : 'f',
'SESSION_USER'                : 'f',
'SET'                         : 'E',
'SETSEED'                     : 'f',
'SETVAL'                      : 'f',
'SET_BIT'                     : 'f',
'SET_BYTE'                    : 'f',
'SET_CONFIG'                  : 'f',
'SET_MASKLEN'                 : 'f',
'SHA'                         : 'f',
'SHA1'                        : 'f',
'SHA2'                        : 'f',
'SHOW'                        : 'n',
'SHUTDOWN'                    : 'T',
'SIGN'                        : 'f',
'SIGNBYASMKEY'                : 'f',
'SIGNBYCERT'                  : 'f',
'SIGNAL'                      : 'k',
'SIMILAR'                     : 'k',
'SIN'                         : 'f',
'SLEEP'                       : 'f',
#
# sqlserver
'SMALLDATETIMEFROMPARTS'      : 'f',
'SMALLINT'                    : 't',
'SMALLSERIAL'                 : 't',
# SOME -- acts like a function
# http://dev.mysql.com/doc/refman/5.0/en/any-in-some-subqueries.html
'SOME'                        : 'f',
'SOUNDEX'                     : 'f',
'SOUNDS'                      : 'o',
'SPACE'                       : 'f',
'SPATIAL'                     : 'k',
'SPECIFIC'                    : 'k',
'SPLIT_PART'                  : 'f',
'SQL'                         : 'k',
'SQLEXCEPTION'                : 'k',
'SQLSTATE'                    : 'k',
'SQLWARNING'                  : 'k',
'SQL_BIG_RESULT'              : 'k',
'SQL_BUFFER_RESULT'           : 'k',
'SQL_CACHE'                   : 'k',
'SQL_CALC_FOUND_ROWS'         : 'k',
'SQL_NO_CACHE'                : 'k',
'SQL_SMALL_RESULT'            : 'k',
'SQL_VARIANT_PROPERTY'        : 'f',
'SQLITE_VERSION'              : 'f',
'SQRT'                        : 'f',
'SSL'                         : 'k',
'STARTING'                    : 'k',
#pgsql
'STATEMENT_TIMESTAMP'         : 'f',
'STATS_DATE'                  : 'f',
'STDDEV'                      : 'f',
'STDDEV_POP'                  : 'f',
'STDDEV_SAMP'                 : 'f',
'STRAIGHT_JOIN'               : 'k',
'STRCMP'                      : 'f',
# STRCOMP: MS ACCESS
'STRCOMP'                     : 'f',
'STRCONV'                     : 'f',
# pgsql
'STRING_AGG'                  : 'f',
'STRING_TO_ARRAY'             : 'f',
'STRPOS'                      : 'f',
'STR_TO_DATE'                 : 'f',
'STUFF'                       : 'f',
'SUBDATE'                     : 'f',
'SUBSTR'                      : 'f',
'SUBSTRING'                   : 'f',
'SUBSTRING_INDEX'             : 'f',
'SUBTIME'                     : 'f',
'SUM'                         : 'f',
'SUSER_ID'                    : 'f',
'SUSER_SID'                   : 'f',
'SUSER_SNAME'                 : 'f',
'SUSER_NAME'                  : 'f',
'SYSDATE'                     : 'f',
# sql server
'SYSDATETIME'                 : 'f',
# sql server
'SYSDATETIMEOFFSET'           : 'f',
# 'SYSCOLUMNS'
# http://msdn.microsoft.com/en-us/library/aa26039s8(v=sql.80).aspx
'SYSCOLUMNS'                  : 'k',

# 'SYSOBJECTS'
# http://msdn.microsoft.com/en-us/library/aa260447(v=sql.80).aspx
'SYSOBJECTS'                  : 'k',

# 'SYSUSERS' - MSSQL
# TBD
'SYSUSERS'                    : 'k',
# sqlserver
'SYSUTCDATETME'               : 'f',
'SYSTEM_USER'                 : 'f',
'SWITCHOFFET'                 : 'f',

# 'TABLE'
# because SQLi really can't use 'TABLE'
#  change from keyword to none
'TABLE'                       : 'n',
'TAN'                         : 'f',
'TERMINATED'                  : 'k',
'TERTIARY_WEIGHTS'            : 'f',
'TEXT'                        : 't',
# TEXTPOS PGSQL 6.0
# remnamed to strpos in 7.0
# http://www.postgresql.org/message-id/20000601091055.A20245@rice.edu
'TEXTPOS'                     : 'f',
'TEXTPTR'                     : 'f',
'TEXTVALID'                   : 'f',
'THEN'                        : 'k',
# TBD
'TIME'                        : 'k',
'TIMEDIFF'                    : 'f',
'TIMEFROMPARTS'               : 'f',
# pgsql
'TIMEOFDAY'                   : 'f',
# ms access
'TIMESERIAL'                  : 'f',
'TIMEVALUE'                   : 'f',
'TIMESTAMP'                   : 't',
'TIMESTAMPADD'                : 'f',
'TIME_FORMAT'                 : 'f',
'TIME_TO_SEC'                 : 'f',
'TINYBLOB'                    : 'k',
'TINYINT'                     : 'k',
'TINYTEXT'                    : 'k',
#
# sqlserver
'TODATETIMEOFFSET'            : 'f',
# pgsql
'TO_ASCII'                    : 'f',
# MySQL 5.6
'TO_BASE64'                   : 'f',
# 'TO_CHAR' -- oracle, pgsql
'TO_CHAR'                     : 'f',
# pgsql
'TO_HEX'                      : 'f',
'TO_DAYS'                     : 'f',
'TO_DATE'                     : 'f',
'TO_NUMBER'                   : 'f',
'TO_SECONDS'                  : 'f',
'TO_TIMESTAMP'                : 'f',
# sqlite3
'TOTAL'                       : 'f',
'TOTAL_CHANGES'               : 'f',
'TOP'                         : 'k',

# 'TRAILING' -- only used in TRIM(TRAILING
# http://www.w3resource.com/sql/character-functions/trim.php
'TRAILING'                    : 'n',
# pgsql
'TRANSACTION_TIMESTAMP'       : 'f',
'TRANSLATE'                   : 'f',
'TRIGGER'                     : 'k',
'TRIGGER_NESTLEVEL'           : 'f',
'TRIM'                        : 'f',
'TRUE'                        : '1',
'TRUNC'                       : 'f',
'TRUNCATE'                    : 'f',
# sqlserver
'TRY'                         : 'T',
'TRY_CAST'                    : 'f',
'TRY_CONVERT'                 : 'f',
'TRY_PARSE'                   : 'f',
'TYPE_ID'                     : 'f',
'TYPE_NAME'                   : 'f',
'TYPEOF'                      : 'f',
'TYPEPROPERTY'                : 'f',
'UCASE'                       : 'f',

# pgsql -- used in weird unicode string
# it's an operator so its' gets folded away
'UESCAPE'                     : 'o',
'UNCOMPRESS'                  : 'f',
'UNCOMPRESS_LENGTH'           : 'f',
'UNDO'                        : 'k',
'UNHEX'                       : 'f',
'UNICODE'                     : 'f',
'UNION'                       : 'U',

# 'UNI_ON' -- odd variation that comes up
'UNI_ON'                      : 'U',

# 'UNIQUE'
# only used as a function (DB2) or as "CREATE UNIQUE"
'UNIQUE'                      : 'n',

'UNIX_TIMESTAMP'              : 'f',
'UNLOCK'                      : 'k',
'UNNEST'                      : 'f',
'UNSIGNED'                    : 'k',
'UPDATE'                      : 'E',
'UPDATEXML'                   : 'f',
'UPPER'                       : 'f',
'UPPER_INC'                   : 'f',
'UPPER_INF'                   : 'f',
'USAGE'                       : 'k',
'USE'                         : 'T',

# transact-sql function
# however treating as a 'none' type
# since 'user_id' is such a common column name
# TBD
'USER_ID'                     : 'n',
'USER_NAME'                   : 'n',
# 'USER' -- a MySQL function
# handled in folding step
'USER'                       : 'n',

'USING'                       : 'f',
# next 3 TBD
'UTC_DATE'                    : 'k',
'UTC_TIME'                    : 'k',
'UTC_TIMESTAMP'               : 'k',
'UUID'                        : 'f',
'UUID_SHORT'                  : 'f',
'VALUES'                      : 'k',
'VARBINARY'                   : 'k',
'VARCHAR'                     : 't',
'VARCHARACTER'                : 'k',
'VARIANCE'                    : 'f',
'VAR'                         : 'f',
'VARP'                        : 'f',
'VARYING'                     : 'k',
'VAR_POP'                     : 'f',
'VAR_SAMP'                    : 'f',
'VERIFYSIGNEDBYASMKEY'        : 'f',
'VERIFYSIGNEDBYCERT'          : 'f',
'VERSION'                     : 'f',
'VOID'                        : 't',
# oracle http://www.shift-the-oracle.com/sql/select-for-update.html
'WAIT'                        : 'k',
'WAITFOR'                     : 'n',
'WEEK'                        : 'f',
'WEEKDAY'                     : 'f',
'WEEKDAYNAME'                 : 'f',
'WEEKOFYEAR'                  : 'f',
'WHEN'                        : 'k',
'WHERE'                       : 'k',
'WHILE'                       : 'T',
# pgsql
'WIDTH_BUCKET'                : 'f',

# it's a keyword, but it's too ordinary in English
'WITH'                        : 'n',

# XML... oracle, pgsql
'XMLAGG'                      : 'f',
'XMLELEMENT'                  : 'f',
'XMLCOMMENT'                  : 'f',
'XMLCONCAT'                   : 'f',
'XMLFOREST'                   : 'f',
'XMLFORMAT'                   : 'f',
'XMLTYPE'                     : 'f',
'XMLPI'                       : 'f',
'XMLROOT'                     : 'f',
'XMLEXISTS'                   : 'f',
'XML_IS_WELL_FORMED'          : 'f',
'XPATH'                       : 'f',
'XPATH_EXISTS'                : 'f',
'XOR'                         : '&',
'XP_EXECRESULTSET'            : 'k',
'YEAR'                        : 'f',
'YEARWEEK'                    : 'f',
'YEAR_MONTH'                  : 'k',
'ZEROBLOB'                    : 'f',
'ZEROFILL'                    : 'k',
'DBMS_LOCK.SLEEP'             : 'f',
'DBMS_UTILITY.SQLID_TO_SQLHASH': 'f',
'USER_LOCK.SLEEP'             : 'f',

#
    '!=': 'o',   # oracle
    '||': '&',
    '&&': '&',
    '>=': 'o',
    '>>': 'o',
    '<=': 'o',
    '<>': 'o',
    ':=': 'o',
    '::': 'o',
    '<<': 'o',
    '!<': 'o',  # http://msdn.microsoft.com/en-us/library/ms188074.aspx
    '!>': 'o',  # http://msdn.microsoft.com/en-us/library/ms188074.aspx
    '+=': 'o',
    '-=': 'o',
    '*=': 'o',
    '/=': 'o',
    '%=': 'o',
    '|=': 'o',
    '&=': 'o',
    '^=': 'o',
    '|/': 'o',  # http://www.postgresql.org/docs/9.1/static/functions-math.html
    '!!': 'o',  # http://www.postgresql.org/docs/9.1/static/functions-math.html
    '~*': 'o',  # http://www.postgresql.org/docs/9.1/static/functions-matching.html

# problematic since ! and ~ are both unary operators in other db engines
# converting to one unary operator is probably ok
#    '!~', # http://www.postgresql.org/docs/9.1/static/functions-matching.html

    '@>': 'o',
    '<@': 'o',
    # '!~*'

    # pgsql "AT TIME ZONE"
    'AT TIME'           : 'n',
    'AT TIME ZONE'      : 'k',
    'IN BOOLEAN'        : 'n',
    'IN BOOLEAN MODE'   : 'k',
# IS DISTINCT - IBM DB2
# http://publib.boulder.ibm.com/infocenter/iseries/v5r4/index.jsp?topic=%2Fsqlp%2Frbafykeyu.htm
    'IS DISTINCT FROM'     : 'o',
    'IS DISTINCT'          : 'n',
    'IS NOT DISTINCT FROM' : 'o',
    'IS NOT DISTINCT'      : 'n',
    'CROSS JOIN'        : 'k',
    'INNER JOIN'        : 'k',
    'ALTER DOMAIN'      : 'k',
    'ALTER TABLE'       : 'k',
    'GROUP BY'          : 'B',
    'ORDER BY'          : 'B',
    'OWN3D BY'          : 'B',
    'READ WRITE'        : 'k',

    # 'LOCAL TABLE' pgsql/oracle
    # http://www.postgresql.org/docs/current/static/sql-lock.html
    'LOCK TABLE'        : 'k',

    # 'LOCK TABLES' MYSQL
    #  http://dev.mysql.com/doc/refman/4.1/en/lock-tables.html
    'LOCK TABLES'       : 'k',
    'LEFT OUTER'        : 'k',
    'LEFT OUTER JOIN'   : 'k',
    'LEFT JOIN'         : 'k',
    'RIGHT OUTER'       : 'k',
    'RIGHT OUTER JOIN'  : 'k',
    'RIGHT JOIN'        : 'k',

# http://technet.microsoft.com/en-us/library/ms187518(v=sql.105).aspx
    'FULL JOIN'         : 'k',
    'FULL OUTER'        : 'k',
    'FULL OUTER JOIN'   : 'k',
    'NATURAL JOIN'      : 'k',
    'NATURAL INNER'     : 'k',
    'NATURAL OUTER'     : 'k',
    'NATURAL LEFT'      : 'k',
    'NATURAL LEFT OUTER': 'k',
    'NATURAL LEFT OUTER JOIN': 'k',
    'NATURAL RIGHT OUTER JOIN': 'k',
    'NATURAL FULL OUTER JOIN': 'k',
    'NATURAL RIGHT'     : 'k',
    'NATURAL FULL'      : 'k',
    'SOUNDS LIKE'       : 'o',
    'IS NOT'            : 'o',
# IBM DB2
# http://publib.boulder.ibm.com/infocenter/iseries/v5r4/index.jsp?topic=%2Fsqlp%2Frbafykeyu.htm
    'NEXT VALUE'            : 'n',
    'NEXT VALUE FOR'        : 'k',
    'PREVIOUS VALUE'        : 'n',
    'PREVIOUS VALUE FOR'    : 'k',
    'NOT LIKE'          : 'o',
    'NOT BETWEEN'       : 'o',
    'NOT SIMILAR'       : 'o',

    # 'NOT RLIKE' -- MySQL
    'NOT RLIKE'         : 'o',

    'NOT REGEXP'        : 'o',
    'NOT IN'            : 'k',
    'SIMILAR TO'        : 'o',
    'NOT SIMILAR TO'    : 'o',
    'SELECT DISTINCT'   : 'E',
    'UNION ALL'         : 'U',
    'UNION DISTINCT'    : 'U',
    'UNION DISTINCT ALL'  : 'U',
    'UNION ALL DISTINCT'  : 'U',
# INTO..
# http://dev.mysql.com/doc/refman/5.0/en/select.html
    'INTO OUTFILE'      : 'k',
    'INTO DUMPFILE'     : 'k',
    'WAITFOR DELAY'     : 'E',
    'WAITFOR TIME'      : 'E',
    'WAITFOR RECEIVE'   : 'E',
    'WITH ROLLUP'       : 'k',
    # 'INTERSECT ALL' -- ORACLE
    'INTERSECT ALL'     : 'U',

    # hacker mistake
    'SELECT ALL' : 'E',

    # types
    'DOUBLE PRECISION': 't',
    'CHARACTER VARYING': 't',

    # MYSQL
    # http://dev.mysql.com/doc/refman/5.1/en/innodb-locking-reads.html
    'LOCK IN': 'n',
    'LOCK IN SHARE': 'n',
    'LOCK IN SHARE MODE': 'k',

    # MYSQL
    # http://dev.mysql.com/doc/refman/5.1/en/innodb-locking-reads.html
    'FOR UPDATE': 'k',

    # TSQL (MS)
    # http://msdn.microsoft.com/en-us/library/ms175046.aspx
    'EXECUTE AS': 'E',
    'EXECUTE AS LOGIN': 'E',

    # ORACLE
    # http://www.shift-the-oracle.com/sql/select-for-update.html
    'FOR UPDATE OF': 'k',
    'FOR UPDATE WAIT': 'k',
    'FOR UPDATE NOWAIT': 'k',
    'FOR UPDATE SKIP': 'k',
    'FOR UPDATE SKIP LOCKED': 'k'

}

CHARMAP = [
    'CHAR_WHITE', # 0
    'CHAR_WHITE', # 1
    'CHAR_WHITE', # 2
    'CHAR_WHITE', # 3
    'CHAR_WHITE', # 4
    'CHAR_WHITE', # 5
    'CHAR_WHITE', # 6
    'CHAR_WHITE', # 7
    'CHAR_WHITE', # 8
    'CHAR_WHITE', # 9
    'CHAR_WHITE', # 10
    'CHAR_WHITE',
    'CHAR_WHITE',
    'CHAR_WHITE',
    'CHAR_WHITE',
    'CHAR_WHITE',
    'CHAR_WHITE',
    'CHAR_WHITE',
    'CHAR_WHITE',
    'CHAR_WHITE',
    'CHAR_WHITE', # 20
    'CHAR_WHITE',
    'CHAR_WHITE',
    'CHAR_WHITE',
    'CHAR_WHITE',
    'CHAR_WHITE',
    'CHAR_WHITE',
    'CHAR_WHITE',
    'CHAR_WHITE',
    'CHAR_WHITE',
    'CHAR_WHITE', # 30
    'CHAR_WHITE', # 31
    'CHAR_WHITE', # 32
    'CHAR_BANG',  # 33 !
    'CHAR_STR',   # 34 "
    'CHAR_HASH',  # 35 "#"
    'CHAR_MONEY', # 36 $
    'CHAR_OP1',   # 37 %
    'CHAR_OP2',   # 38 &
    'CHAR_STR',   # 39 '
    'CHAR_LEFTPARENS',  # 40 (
    'CHAR_RIGHTPARENS',  # 41 )
    'CHAR_OP2',   # 42 *
    'CHAR_UNARY', # 43 +
    'CHAR_COMMA', # 44 ,
    'CHAR_DASH',  # 45 -
    'CHAR_NUM',   # 46 .
    'CHAR_SLASH', # 47 /
    'CHAR_NUM',   # 48 0
    'CHAR_NUM',   # 49 1
    'CHAR_NUM',   # 50 2
    'CHAR_NUM',   # 51 3
    'CHAR_NUM',   # 52 4
    'CHAR_NUM',   # 53 5
    'CHAR_NUM',   # 54 6
    'CHAR_NUM',   # 55 7
    'CHAR_NUM',   # 56 8
    'CHAR_NUM',   # 57 9
    'CHAR_OP2',   # 58 : colon
    'CHAR_SEMICOLON',  # 59 ; semiclon
    'CHAR_OP2',   # 60 <
    'CHAR_OP2',   # 61 =
    'CHAR_OP2',   # 62 >
    'CHAR_OTHER', # 63 ?   BEEP BEEP
    'CHAR_VAR',             # 64  @
    'CHAR_WORD',            # 65  A
    'CHAR_BSTRING',         # 66  B
    'CHAR_WORD',            # 67  C
    'CHAR_WORD',            # 68  D
    'CHAR_ESTRING',         # 69  E
    'CHAR_WORD',            # 70  F
    'CHAR_WORD',            # 71  G
    'CHAR_WORD',            # 72  H
    'CHAR_WORD',            # 73  I
    'CHAR_WORD',            # 74  J
    'CHAR_WORD',            # 75  K
    'CHAR_WORD',            # 76  L
    'CHAR_WORD',            # 77  M
    'CHAR_NQSTRING',        # 78  N
    'CHAR_WORD',            # 79  O
    'CHAR_WORD',            # 80  P
    'CHAR_QSTRING',         # 81  Q
    'CHAR_WORD',            # 82  R
    'CHAR_WORD',            # 83  S
    'CHAR_WORD',            # 84  T
    'CHAR_USTRING',         # 85  U special pgsql unicode
    'CHAR_WORD',            # 86  V
    'CHAR_WORD',            # 87  W
    'CHAR_XSTRING',         # 88  X
    'CHAR_WORD',            # 89  Y
    'CHAR_WORD',            # 90  Z
    'CHAR_BWORD',           # 91  [  B for Bracket,  for Microsoft SQL SERVER
    'CHAR_BACK',            # 92  \\
    'CHAR_OTHER',           # 93  ]
    'CHAR_OP1',             # 94  ^
    'CHAR_WORD',            # 95  _ underscore
    'CHAR_TICK',            # 96  ` backtick
    'CHAR_WORD',            # 97  a
    'CHAR_BSTRING',         # 98  b
    'CHAR_WORD',            # 99  c
    'CHAR_WORD',            # 100 d
    'CHAR_ESTRING',         # 101 e
    'CHAR_WORD',            # 102 f
    'CHAR_WORD',            # 103 g
    'CHAR_WORD',            # 104 h
    'CHAR_WORD',            # 105 i
    'CHAR_WORD',            # 106 j
    'CHAR_WORD',            # 107 k
    'CHAR_WORD',            # 108 l
    'CHAR_WORD',            # 109 m
    'CHAR_NQSTRING',        # 110 n special oracle code
    'CHAR_WORD',            # 111 o
    'CHAR_WORD',            # 112 p
    'CHAR_QSTRING',         # 113 q special oracle code
    'CHAR_WORD',            # 114 r
    'CHAR_WORD',            # 115 s
    'CHAR_WORD',            # 116 t
    'CHAR_USTRING',         # 117 u  special pgsql unicode
    'CHAR_WORD',            # 118 v
    'CHAR_WORD',            # 119 w
    'CHAR_XSTRING',         # 120 x
    'CHAR_WORD',            # 121 y
    'CHAR_WORD',            # 122 z
    'CHAR_LEFTBRACE',            # 123 { left brace
    'CHAR_OP2',             # 124 | pipe
    'CHAR_RIGHTBRACE',            # 125 } right brace
    'CHAR_UNARY',             # 126 ~
    'CHAR_WHITE',            # 127
    'CHAR_WORD',
    'CHAR_WORD',
    'CHAR_WORD', # 130
    'CHAR_WORD',
    'CHAR_WORD',
    'CHAR_WORD',
    'CHAR_WORD',
    'CHAR_WORD',
    'CHAR_WORD',
    'CHAR_WORD',
    'CHAR_WORD',
    'CHAR_WORD',
    'CHAR_WORD', #140
    'CHAR_WORD',
    'CHAR_WORD',
    'CHAR_WORD',
    'CHAR_WORD',
    'CHAR_WORD',
    'CHAR_WORD',
    'CHAR_WORD',
    'CHAR_WORD',
    'CHAR_WORD',
    'CHAR_WORD', #150
    'CHAR_WORD',
    'CHAR_WORD',
    'CHAR_WORD',
    'CHAR_WORD',
    'CHAR_WORD',
    'CHAR_WORD',
    'CHAR_WORD',
    'CHAR_WORD',
    'CHAR_WORD',
    'CHAR_WHITE', #160 0xA0 latin1 whitespace
    'CHAR_WORD',
    'CHAR_WORD',
    'CHAR_WORD',
    'CHAR_WORD',
    'CHAR_WORD',
    'CHAR_WORD',
    'CHAR_WORD',
    'CHAR_WORD',
    'CHAR_WORD',
    'CHAR_WORD', #170
    'CHAR_WORD',
    'CHAR_WORD',
    'CHAR_WORD',
    'CHAR_WORD',
    'CHAR_WORD',
    'CHAR_WORD',
    'CHAR_WORD',
		'CHAR_WORD',
		'CHAR_WORD',
    'CHAR_WORD', #180
    'CHAR_WORD',
    'CHAR_WORD',
    'CHAR_WORD',
    'CHAR_WORD',
    'CHAR_WORD',
    'CHAR_WORD',
    'CHAR_WORD',
    'CHAR_WORD',
    'CHAR_WORD',
    'CHAR_WORD', #190
    'CHAR_WORD',
    'CHAR_WORD',
    'CHAR_WORD',
    'CHAR_WORD',
    'CHAR_WORD',
    'CHAR_WORD',
    'CHAR_WORD',
    'CHAR_WORD',
    'CHAR_WORD',
    'CHAR_WORD', #200
    'CHAR_WORD',
    'CHAR_WORD',
    'CHAR_WORD',
    'CHAR_WORD',
    'CHAR_WORD',
    'CHAR_WORD',
    'CHAR_WORD',
    'CHAR_WORD',
    'CHAR_WORD',
    'CHAR_WORD', #210
    'CHAR_WORD',
    'CHAR_WORD',
    'CHAR_WORD',
    'CHAR_WORD',
    'CHAR_WORD',
    'CHAR_WORD',
    'CHAR_WORD',
    'CHAR_WORD',
    'CHAR_WORD',
    'CHAR_WORD', #220
    'CHAR_WORD',
    'CHAR_WORD',
    'CHAR_WORD',
    'CHAR_WORD',
    'CHAR_WORD',
    'CHAR_WORD',
    'CHAR_WORD',
    'CHAR_WORD',
    'CHAR_WORD',
    'CHAR_WORD', #230
    'CHAR_WORD',
    'CHAR_WORD',
    'CHAR_WORD',
    'CHAR_WORD',
    'CHAR_WORD',
    'CHAR_WORD',
    'CHAR_WORD',
    'CHAR_WORD',
    'CHAR_WORD',
    'CHAR_WORD', #240
    'CHAR_WORD',
    'CHAR_WORD',
    'CHAR_WORD',
    'CHAR_WORD',
    'CHAR_WORD',
    'CHAR_WORD',
    'CHAR_WORD',
    'CHAR_WORD',
    'CHAR_WORD',
    'CHAR_WORD', #250
    'CHAR_WORD',
    'CHAR_WORD',
    'CHAR_WORD',
    'CHAR_WORD',
    'CHAR_WORD'
]

import json

def get_fingerprints():
    """
    fingerprints are stored in plain text file, one fingerprint per file
    the result is sorted
    """

    with open('fingerprints.txt', 'r') as lines:
        sqlipat = [line.strip() for line in lines]

    return sorted(sqlipat)

def dump():
    """
    generates a JSON file, sorted keys
    """
    objs = {
        'keywords': KEYWORDS,
        'charmap': CHARMAP,
        'fingerprints': get_fingerprints()
        }
    return json.dumps(objs, sort_keys=True, indent=4)

if __name__ == '__main__':
    import sys
    if len(CHARMAP) != 256:
        sys.stderr.write("Assert failed: charmap is %d characters\n" % len(CHARMAP))
        sys.exit(1)
    print(dump())

# pylint: disable=C0301,C0302
