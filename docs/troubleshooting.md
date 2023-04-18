# Troubleshooting

## Logs

When troubleshooting, logs are your best friends. We try our best to provide user-friendly logs to help you understand what's happening.

Please note that you can set `LOG_LEVEL` setting to `info` (default : `notice`) to increase the verbosity of BunkerWeb.

Here is how you can access the logs, depending on your integration :

=== "Docker"

    !!! tip "List containers"
    	To list the running containers, you can use the following command :
    	```shell
    	docker ps
    	```

    You can use the `docker logs` command (replace `mybunker` with the name of your container) :
    ```shell
    docker logs mybunker
    ```

    Here is the docker-compose equivalent (replace `mybunker` with the name of the services declared in the docker-compose.yml file) :
    ```shell
    docker-compose logs mybunker
    ```

=== "Docker autoconf"

    !!! tip "List containers"
    	To list the running containers, you can use the following command :
    	```shell
    	docker ps
    	```

    You can use the `docker logs` command (replace `mybunker` and `myautoconf` with the name of your containers) :
    ```shell
    docker logs mybunker
    docker logs myautoconf
    ```

    Here is the docker-compose equivalent (replace `mybunker` and `myautoconf` with the name of the services declared in the docker-compose.yml file) :
    ```shell
    docker-compose logs mybunker
    docker-compose logs myautoconf
    ```

=== "Swarm"

    !!! tip "List services"
    	To list the services, you can use the following command :
    	```shell
    	docker service ls
    	```

    You can use the `docker service logs` command (replace `mybunker` and `myautoconf` with the name of your services) :
    ```shell
    docker service logs mybunker
    docker service logs myautoconf
    ```

=== "Kubernetes"

    !!! tip "List pods"
    	To list the pods, you can use the following command :
    	```shell
    	kubectl get pods
    	```
    You can use the `kubectl logs` command (replace `mybunker` and `myautoconf` with the name of your pods) :
    ```shell
    kubectl logs mybunker
    kubectl logs myautoconf
    ```

=== "Linux"

    For errors related to BunkerWeb services (e.g. not starting), you can use `journalctl` :
    ```shell
    journalctl -u bunkerweb --no-pager
    ```

    Common logs are located inside the `/var/log/nginx` directory :
    ```shell
    cat /var/log/nginx/error.log
    cat /var/log/nginx/access.log
    ```

=== "Ansible"

    For errors related to BunkerWeb services (e.g. not starting), you can use `journalctl` :
    ```shell
    ansible -i inventory.yml all -a "journalctl -u bunkerweb --no-pager" --become
    ```

    Common logs are located inside the `/var/log/nginx` directory :
    ```shell
    ansible -i inventory.yml all -a "cat /var/log/nginx/error.log" --become
    ansible -i inventory.yml all -a "cat /var/log/nginx/access.log" --become
    ```

=== "Vagrant"

    For errors related to BunkerWeb services (e.g. not starting), you can use `journalctl` :
    ```shell
    journalctl -u bunkerweb --no-pager
    ```

    Common logs are located inside the `/var/log/nginx` directory :
    ```shell
    cat /var/log/nginx/error.log
    cat /var/log/nginx/access.log
    ```

## Permissions

Don't forget that BunkerWeb runs as an unprivileged user for obvious security reasons. Double-check the permissions of files and folders used by BunkerWeb, especially if you use custom configurations (more info [here](/1.4/quickstart-guide/#custom-configurations)). You will need to set at least **RW** rights on files and **_RWX_** on folders.

## ModSecurity

The default BunkerWeb configuration of ModSecurity is to load the Core Rule Set in anomaly scoring mode with a paranoia level (PL) of 1 :

- Each matched rule will increase an anomaly score (so many rules can match a single request)
- PL1 includes rules with fewer chances of false positives (but less security than PL4)
- the default threshold for anomaly score is 5 for requests and 4 for responses

Let's take the following logs as an example of ModSecurity detection using default configuration (formatted for better readability) :

```log
2022/04/26 12:01:10 [warn] 85#85: *11 ModSecurity: Warning. Matched "Operator `PmFromFile' with parameter `lfi-os-files.data' against variable `ARGS:id' (Value: `/etc/passwd' )
	[file "/usr/share/bunkerweb/core/modsecurity/files/coreruleset/rules/REQUEST-930-APPLICATION-ATTACK-LFI.conf"]
	[line "78"]
	[id "930120"]
	[rev ""]
	[msg "OS File Access Attempt"]
	[data "Matched Data: etc/passwd found within ARGS:id: /etc/passwd"]
	[severity "2"]
	[ver "OWASP_CRS/3.3.2"]
	[maturity "0"]
	[accuracy "0"]
	[tag "application-multi"]
	[tag "language-multi"]
	[tag "platform-multi"]
	[tag "attack-lfi"]
	[tag "paranoia-level/1"]
	[tag "OWASP_CRS"]
	[tag "capec/1000/255/153/126"]
	[tag "PCI/6.5.4"]
	[hostname "172.17.0.2"]
	[uri "/"]
	[unique_id "165097447014.179282"]
	[ref "o1,10v9,11t:utf8toUnicode,t:urlDecodeUni,t:normalizePathWin,t:lowercase"],
	client: 172.17.0.1, server: localhost, request: "GET /?id=/etc/passwd HTTP/1.1", host: "localhost"
2022/04/26 12:01:10 [warn] 85#85: *11 ModSecurity: Warning. Matched "Operator `PmFromFile' with parameter `unix-shell.data' against variable `ARGS:id' (Value: `/etc/passwd' )
	[file "/usr/share/bunkerweb/core/modsecurity/files/coreruleset/rules/REQUEST-932-APPLICATION-ATTACK-RCE.conf"]
	[line "480"]
	[id "932160"]
	[rev ""]
	[msg "Remote Command Execution: Unix Shell Code Found"]
	[data "Matched Data: etc/passwd found within ARGS:id: /etc/passwd"]
	[severity "2"]
	[ver "OWASP_CRS/3.3.2"]
	[maturity "0"]
	[accuracy "0"]
	[tag "application-multi"]
	[tag "language-shell"]
	[tag "platform-unix"]
	[tag "attack-rce"]
	[tag "paranoia-level/1"]
	[tag "OWASP_CRS"]
	[tag "capec/1000/152/248/88"]
	[tag "PCI/6.5.2"]
	[hostname "172.17.0.2"]
	[uri "/"]
	[unique_id "165097447014.179282"]
	[ref "o1,10v9,11t:urlDecodeUni,t:cmdLine,t:normalizePath,t:lowercase"],
	client: 172.17.0.1, server: localhost, request: "GET /?id=/etc/passwd HTTP/1.1", host: "localhost"
2022/04/26 12:01:10 [error] 85#85: *11 [client 172.17.0.1] ModSecurity: Access denied with code 403 (phase 2). Matched "Operator `Ge' with parameter `5' against variable `TX:ANOMALY_SCORE' (Value: `10' )
	[file "/usr/share/bunkerweb/core/modsecurity/files/coreruleset/rules/REQUEST-949-BLOCKING-EVALUATION.conf"]
	[line "80"]
	[id "949110"]
	[rev ""]
	[msg "Inbound Anomaly Score Exceeded (Total Score: 10)"]
	[data ""]
	[severity "2"]
	[ver "OWASP_CRS/3.3.2"]
	[maturity "0"]
	[accuracy "0"]
	[tag "application-multi"]
	[tag "language-multi"]
	[tag "platform-multi"]
	[tag "attack-generic"]
	[hostname "172.17.0.2"]
	[uri "/"]
	[unique_id "165097447014.179282"]
	[ref ""],
	client: 172.17.0.1, server: localhost, request: "GET /?id=/etc/passwd HTTP/1.1", host: "localhost"
```

As we can see, there are 3 different logs :

1. Rule **930120** matched
2. Rule **932160** matched
3. Access denied (rule **949110**)

One important thing to understand is that rule **949110** is not a "real" one : it's the one that will deny the request because the anomaly threshold is reached (which is **10** in this example). You should never remove the **949110** rule !

If it's a false-positive, you should then focus on both **930120** and **932160** rules. ModSecurity and/or CRS tuning is out of the scope of this documentation but don't forget that you can apply custom configurations before and after the CRS is loaded (more info [here](/1.4/quickstart-guide/#custom-configurations)).

## Bad Behavior

A common false-positive case is when the client is banned because of the "bad behavior" feature which means that too many suspicious HTTP status codes were generated within a time period (more info [here](/1.4/security-tuning/#bad-behavior)). You should start by reviewing the settings and then edit them according to your web application(s) like removing a suspicious HTTP code, decreasing the count time, increasing the threshold, ...

## IP unban

You can manually unban an IP which can be useful when doing some tests but it needs the setting `USE_API` set to `yes` (which is not the default) so you can contact the internal API of BunkerWeb (replace `1.2.3.4` with the IP address to unban) :

=== "Docker"

    You can use the `docker exec` command (replace `mybunker` with the name of your container) :
    ```shell
    docker exec mybunker bwcli unban 1.2.3.4
    ```

    Here is the docker-compose equivalent (replace `mybunker` with the name of the services declared in the docker-compose.yml file) :
    ```shell
    docker-compose exec mybunker bwcli unban 1.2.3.4
    ```

=== "Docker autoconf"

    You can use the `docker exec` command (replace `myautoconf` with the name of your container) :
    ```shell
    docker exec myautoconf bwcli unban 1.2.3.4
    ```

    Here is the docker-compose equivalent (replace `myautoconf` with the name of the services declared in the docker-compose.yml file) :
    ```shell
    docker-compose exec myautoconf bwcli unban 1.2.3.4
    ```

=== "Swarm"

    You can use the `docker exec` command (replace `myautoconf` with the name of your service) :
    ```shell
    docker exec $(docker ps -q -f name=myautoconf) bwcli unban 1.2.3.4
    ```

=== "Kubernetes"

    You can use the `kubectl exec` command (replace `myautoconf` with the name of your pod) :
    ```shell
    kubectl exec myautoconf bwcli unban 1.2.3.4
    ```

=== "Linux"

    You can use the `bwcli` command (as root) :
    ```shell
    sudo bwcli unban 1.2.3.4
    ```

=== "Ansible"

    You can use the `bwcli` command :
    ```shell
	ansible -i inventory.yml all -a "bwcli unban 1.2.3.4" --become
    ```

=== "Vagrant"

    You can use the `bwcli` command (as root) :
    ```shell
    sudo bwcli unban 1.2.3.4
    ```
	
## Whitelisting

If you have bots that need to access your website, the recommended way to avoid any false positive is to whitelist them using the [whitelisting feature](/1.4/security-tuning/#blacklisting-and-whitelisting). We don't recommend using the `WHITELIST_URI*` or `WHITELIST_USER_AGENT*` settings unless they are set to secret and unpredictable values. Common use cases are :

- Healthcheck / status bot
- Callback like IPN or webhook
- Social media crawler