<?php
setcookie("bw_cookie", "test", time() + (86400 * 30), "/"); // 86400 = 1 day
header("Permission-Policy: geolocation=()")
?>
