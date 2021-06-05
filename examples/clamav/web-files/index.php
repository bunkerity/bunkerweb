<!DOCTYPE html>
<html>
<body>

<?php
if (file_exists($_FILES['myfile']['tmp_name']) && is_uploaded_file($_FILES['myfile']['tmp_name'])) {
	echo 'File is clean !';
}
?>

<form action="index.php" method="post" enctype="multipart/form-data">
	Select file to scan :
	<input type="file" name="myfile">
	<input type="submit" value="Scan file" name="submit">
</form>

</body>
</html>

