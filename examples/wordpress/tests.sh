{
	"name": "tomcat",
	"kinds": [
		"docker",
        "autoconf",
        "swarm",
        "kubernetes"
	],
	"timeout": 60,
	"tests": [
		{
			"type": "string",
			"url": "https://www.example.com",
			"string": "wordpress"
		}
	]
}