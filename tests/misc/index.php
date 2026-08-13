<?php
setcookie("bw_cookie", "test", time() + (86400 * 30), "/"); // 86400 = 1 day
setcookie("bw_cookie_1", "test1", time() + (86400 * 30), "/"); // 86400 = 1 day
header("Content-Security-Policy: default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self'; font-src 'self'; connect-src 'self'; frame-src 'self'; object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none';");
?>
<html>
  <head>
    <title>BunkerWeb - Hello World!</title>
  </head>
  <body>
    <h1>Hello World!</h1>
  </body>
</html>
