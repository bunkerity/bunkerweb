<?php

echo "Hello from app2 (calling external authorized resource) !";

?>

<script>
var xhttp = new XMLHttpRequest();
xhttp.onreadystatechange = function() {
	if (this.readyState == 4 && this.status == 200) {
		alert("HTTP request is ok !");
	}
};
xhttp.open("GET", "https://app1.example.com", true);
xhttp.send();
</script>
