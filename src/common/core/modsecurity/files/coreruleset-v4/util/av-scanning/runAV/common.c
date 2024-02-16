#include "common.h"

int lock_file(char *filename)
{
	int fd;

	if (!filename)
		return -1;

	if ((fd = open(filename,O_RDONLY | O_CREAT , S_IRWXU)) < 0) {
		print_error("lock_file","open",modsec_rpc_log_file,errno);
		return -1;
	}

	flock(fd,LOCK_EX);

	return fd;
}

int unlock_file(int fd)
{
	flock(fd,LOCK_UN);
	return 0;
}

int print_request(char* url,char *command,parameter_t *parameters, int num_of_parameters, int mask)
{
	char time_str[64], line[1024*1024];
	time_t t;
	int fd;
	int i;

	switch (atoi(modsec_rpc_log_level)) {
	case DEBUG:
			time(&t);
			ctime_r(&t,time_str);
			time_str[strlen(time_str)-1] = '\0';
			if ((fd = open(modsec_rpc_log_file,O_WRONLY | O_CREAT | O_APPEND | O_SYNC , S_IRWXU)) < 0) {
				print_error("print_request","open",modsec_rpc_log_file,errno);
				fd=2;
			}
			flock(fd,LOCK_EX);
			sprintf(line,"%s:REQUEST-BEGIN:======================================\n",time_str);
			line[1024*1024-1]='\0';
			write(fd,line,strlen(line));
			snprintf(line,1024*1024,"URL:%s\nCommand:%s\n",url,command);
			line[1024*1024-1]='\0';
			write(fd,line,strlen(line));
			for (i=0; i<num_of_parameters; i++) {
				snprintf(line,1024*1024,"%s=",parameters[i].name);
				line[1024*1024-1]='\0';
				write(fd,line,strlen(line));
				if (i == mask) {
					sprintf(line,"XXXXXXX\n");
					write(fd,line,strlen(line));
				} else {
					if (parameters[i].value) {
						snprintf(line,1024*1024,"%s\n",parameters[i].value);
						line[1024*1024-1]='\0';
					}
					else sprintf(line,"\n");
					write(fd,line,strlen(line));
				}

			}
			sprintf(line,"%s:REQUEST-END:========================================\n",time_str);
			write(fd,line,strlen(line));
			flock(fd,LOCK_UN);
			if (fd!=2) close(fd);
			break;
	}
	return 0;
}

int print_request_force(char* url,char *command,parameter_t *parameters, int num_of_parameters, int mask)
{
	char real_level[1024];

	strcpy(real_level,modsec_rpc_log_level);
	strcpy(modsec_rpc_log_level,"1");
	print_request(url,command,parameters,num_of_parameters,mask);
	strcpy(modsec_rpc_log_level,real_level);
	return 0;
}

int print_reply(char *reply)
{
	char time_str[64];
	time_t t;
	int fd;

	printf("%s",reply);
	switch (atoi(modsec_rpc_log_level)) {
	case DEBUG:
			time(&t);
			ctime_r(&t,time_str);
			time_str[strlen(time_str)-1] = '\0';
			if ((fd = open(modsec_rpc_log_file,O_WRONLY | O_CREAT | O_APPEND | O_SYNC , S_IRWXU)) < 0) {
				print_error("print_request","open",modsec_rpc_log_file,errno);
				fd=2;
			}
			flock(fd,LOCK_EX);
			write(fd,reply,strlen(reply));
			flock(fd,LOCK_UN);
			if (fd!=2) close(fd);
			break;
	}
	return 0;
}

int print_error(char *func1, char* func2, char* str, int err)
{
	char out[1024], time_str[64], line[1024*1024];
	char str1[1024], str2[1024], str3[1024];
	time_t t;
	int fd;

	time(&t);
	ctime_r(&t,time_str);
	time_str[strlen(time_str)-1] = '\0';
	if (err)
		strcpy(out,strerror(err));
	else
		strcpy(out,"");
	if (!func1)
		strcpy(str1,"");
	else {
		strncpy(str1,func1,1024);
		str1[1023]='\0';
	}
	if (!func2)
		strcpy(str2,"");
	else {
		strncpy(str2,func2,1024);
		str2[1023]='\0';
	}
	if (!str)
		strcpy(str3,"");
	else {
		strncpy(str3,str,1024);
		str3[1023]='\0';
	}

	if ((fd = open(modsec_rpc_log_file,O_WRONLY | O_CREAT | O_APPEND | O_SYNC , S_IRWXU)) < 0) {
		fprintf(stderr,"%s:ERROR:print_error:open:%s:%s\n",time_str,strerror(errno),modsec_rpc_log_file);
		fd=2;
	}
	snprintf(line,1024*1024,"%s:ERROR:%s:%s:%s:%s\n",time_str,str1,str2,out,str3);
	line[1024*1024-1]='\0';
	flock(fd,LOCK_EX);
	write(fd,line,strlen(line));
	flock(fd,LOCK_UN);
	if (fd!=2) close(fd);
	return 0;
}

int is_proxy_up()
{
	int pid;
	FILE *fp;

	if ((fp = fopen(modsec_proxy_pid,"r")) == NULL )
		return 0;

	if (fscanf(fp,"%d",&pid) == 0) {
		print_error("is_proxy_up","fscanf","missing PID",0);
		fclose(fp);
		return 0;
	}
	fclose(fp);

        if (!pid || kill(pid,0))
                return 0;

	return 1;
}

int run_cmd(char *command, char *output, int output_size)
{
	char line[1024];
	FILE *fp;

	if (output_size > 0 && output) output[0]='\0';
	if (!(fp=popen(command,"r"))) {
		print_error("run_cmd","popen",command,errno);
		return -1;
	}

	while (output_size && fgets(line,output_size>1024?1024:output_size,fp)) {
		strcat(output, line);
		output_size -= strlen(line);
	}

	if (!output_size)
		while (fgets(line,1024,fp));

	pclose(fp);
	return 0;
}

int find_param_idx(char *parameter_name, parameter_t *parameters, int max_parameters)
{
	int i, idx=-1;

	for (i = 0; (i < max_parameters) && (idx < 0); i++)
		if ( strstr(parameters[i].name,parameter_name) )
			idx=i;
	return idx;
}

int parse_file(char *filename, parameter_t *parameters, int max_parameters)
{
        char line[1024], *ptr;
	int i;
        FILE *fp;

	if (!max_parameters || (parameters == NULL) || (filename == NULL)) {
		print_error("parse_file","invalid input parameters","none",0);
		return 0;
	}

	if ((fp = fopen(filename,"r")) == NULL ) {
		print_error("parse_file","fopen",filename,errno);
		return 0;
	}

	i=0;
	while ( i < max_parameters && fgets(line,1024,fp)) {
		if (ptr = strstr(line,"#"))
			*ptr='\0';
		if (sscanf(line,"%[^=]=%s",parameters[i].name,parameters[i].value) != 2)
			continue;
		i++;
	}

	fclose(fp);

	return i;
}

int change_file(char *filename, parameter_t parameter)
{
        char line[1024], *name, *value;
	int i, found=0;
        FILE *fp;

	if (filename == NULL)
		return 0;

	if ((fp = fopen(filename,"r+")) == NULL )
		return 0;

	i=0;
	while ( fgets(line,1024,fp)) {
		sscanf(line,"%[^=]=%s",name,value);
		if (name && !strcmp(name,parameter.name)) {
			fprintf(fp,"%s=%s\n",name,parameter.value);
			found=1;
			continue;
		} else fprintf(fp,"%s",line);
	}

	fclose(fp);
	return found;
}

int copy_file(char *src_file, char *dst_file)
{
        char line[1024];
        FILE *sfp, *dfp;

	if (src_file == NULL || dst_file == NULL)
		return 0;

	if ((sfp = fopen(src_file,"r")) == NULL )
		return 0;

	if ((dfp = fopen(dst_file,"w")) == NULL ) {
		fclose(sfp);
		return 0;
	}

	while ( fgets(line,1024,sfp))
		fprintf(dfp,"%s",line);

	fclose(sfp);
	fclose(dfp);
	return 1;
}

int parse_query(char *query, parameter_t *parameters, int max_parameters)
{
	char *ptr, *dst_ptr, num[3];
	int i, len;

	if (!max_parameters || (parameters == NULL) || (query == NULL))
		return 0;

	ptr=query;
	i=0;
	while ((i < max_parameters) && *ptr) {
		parameters[i].name[0] = '\0';
		dst_ptr = parameters[i].name;
		len=0;
		while (*ptr && (*ptr != '=') && (len++ < MAX_NAME_LENGTH)) {
			if (*ptr == '%' && *(ptr+1) && *(ptr+2)) {
					num[0]=*(ptr+1);
					num[1]=*(ptr+2);
					num[2]='\0';
					ptr += 3;
					*dst_ptr=(char)strtol(num,NULL,16);
					if (*dst_ptr) dst_ptr++;
			} else *dst_ptr++ = *ptr++;
		}
		if (len >= MAX_NAME_LENGTH)
			while (*ptr && (*ptr != '='))
				*ptr++;
		if (*ptr) ptr++;
		*dst_ptr = '\0';
		parameters[i].value[0] = '\0';
		dst_ptr = parameters[i].value;
		len=0;
		while (*ptr && (*ptr != '&') && (len++ < MAX_VALUE_LENGTH)) {
			if (*ptr == '%' && *(ptr+1) && *(ptr+2)) {
					num[0]=*(ptr+1);
					num[1]=*(ptr+2);
					num[2]='\0';
					ptr += 3;
					*dst_ptr=(char)strtol(num,NULL,16);
					if (*dst_ptr) dst_ptr++;
			} else *dst_ptr++ = *ptr++;
		}
		if (len >= MAX_VALUE_LENGTH)
			while (*ptr && (*ptr != '&'))
				*ptr++;
		if (*ptr) ptr++;
		*dst_ptr = '\0';
		i++;
	}

	return i;
}

int parse_query_and_body (parameter_t *parameters, int max_parameters)
{
	char *query, *content_length_env;
	int i, num_of_params, body_len, content_length;

	query = getenv("QUERY_STRING");
	if (query && *query)
		return(parse_query(query,parameters,max_parameters));
	else {
		content_length_env = getenv("CONTENT_LENGTH");
		if (!content_length_env)
			return 0;
		if (! *content_length_env)
			return 0;
		content_length=atol(content_length_env);
		if (!(query=malloc(content_length+1)))
			return 0;
	        i = 1; body_len=0;
		while ( (body_len < content_length) && (i>0) ) {
			i = read(0,query+body_len,(content_length-body_len)<1024?(content_length-body_len):1024);
			if (i > 0 ) body_len+=i;
		}
		query[body_len] = '\0';
		num_of_params = parse_query(query,parameters,max_parameters);
		free(query);
		return num_of_params;
	}
}

int parse_cli (parameter_t *parameters, int max_parameters, int num_of_args, char *args[])
{
	char name[MAX_NAME_LENGTH], value[MAX_VALUE_LENGTH];
	int i, num_of_params=0;

	if (num_of_args > 0)
		for (i=0; i<num_of_args && i<max_parameters; i++) {
			if (sscanf(args[i],"%[^=]=%s",name,value) < 2)
				continue;
			if (strlen(name) < MAX_NAME_LENGTH)
				strcpy(parameters[num_of_params].name,name);
			else continue;
			if (strlen(value) < MAX_VALUE_LENGTH) {
				strcpy(parameters[num_of_params].value,value);
				num_of_params++;
			}
		}
	return num_of_params;
}

int send_request(char *request,char *ip,char *port,char *reply,int max_reply_size)
{
	int sock, i, reply_len;
	struct  sockaddr_in servaddr;

	reply[0]='\0';
	reply_len=0;
	if (!request || !*request || !ip || !port || !reply || !max_reply_size)
		return -1;

	memset(&servaddr, 0, sizeof(servaddr));
	servaddr.sin_family = AF_INET;
	servaddr.sin_port = htons((short)atol(port));
	if ( inet_aton(ip, &servaddr.sin_addr) <= 0 )
		return -1;

	if ( (sock = socket(AF_INET, SOCK_STREAM, 0)) <  0 ) {
		print_error("send_request","socket",ip,errno);
		return -1;
	}
	if ( connect(sock, (struct sockaddr *) &servaddr, sizeof(servaddr) ) < 0 ) {
		print_error("send_request","connect",ip,errno);
		close(sock);
		return -1;
	}

	i = strlen(request);
	if ( write(sock,request,i) < i ) {
		print_error("send_request","write",ip,errno);
		shutdown(sock,SHUT_RDWR);
		close(sock);
		return -1;
	}

	i = 1; reply_len=0;
	while ( (reply_len < max_reply_size) && (i>0) ) {
		i = read(sock,reply+reply_len,(max_reply_size-reply_len)<1024?(max_reply_size-reply_len):1024);
		if (i > 0 ) reply_len+=i;
	}
	reply[reply_len] = '\0';

	shutdown(sock,SHUT_RDWR);
	close(sock);
	return reply_len;
}

int find_ip_idx(char *ip, blocklist_t *blocklist, int num_of_ips)
{
	int i, idx=-1;

	for (i = 0; (i < num_of_ips) && (idx < 0); i++)
		if ( strstr(blocklist[i].ip,ip) )
			idx=i;
	return idx;
}

int remove_ip_idx(char *ip, blocklist_t *blocklist, int num_of_ips)
{
	int i, j, idx=-1;
	time_t t;

	time(&t);
	for (i = 0; i < num_of_ips; i++)
		if ( (ip && strstr(blocklist[i].ip,ip)) || (!ip && (t > blocklist[i].end)) ) {
			idx=i;
			for (j=i; j<(num_of_ips-1); j++) {
				strcpy(blocklist[j].ip,blocklist[j+1].ip);
				blocklist[j].start = blocklist[j+1].start;
				blocklist[j].duration = blocklist[j+1].duration;
				blocklist[j].end = blocklist[j+1].end;
				strcpy(blocklist[j].token,blocklist[j+1].token);
			}
			num_of_ips--;
		}
	return idx;
}

int read_conf_file (char *filename)
{
	int idx, num_of_params;
	parameter_t parameters[MAX_PARAMS];

	num_of_params=parse_file(filename,parameters,MAX_PARAMS);

	if ((idx = find_param_idx("MODSEC_CLI_HOME",parameters,num_of_params)) >= 0)
		strcpy(modsec_cli_home,parameters[idx].value);
	if ((idx = find_param_idx("MODSEC_RPC_HOME",parameters,num_of_params)) >= 0)
		strcpy(modsec_rpc_home,parameters[idx].value);

	if ((idx = find_param_idx("MODSEC_RPC_LOG_FILE",parameters,num_of_params)) >= 0)
		strcpy(modsec_rpc_log_file,parameters[idx].value);

	if ((idx = find_param_idx("MODSEC_RPC_LOG_LEVEL",parameters,num_of_params)) >= 0)
		strcpy(modsec_rpc_log_level,parameters[idx].value);

	if ((idx = find_param_idx("MODSEC_RPC_SSL_LOCKFILE",parameters,num_of_params)) >= 0)
		strcpy(modsec_rpc_ssl_lockfile,parameters[idx].value);

	if ((idx = find_param_idx("MODSEC_RPC_SENSOR_LOCKFILE",parameters,num_of_params)) >= 0)
		strcpy(modsec_rpc_sensor_lockfile,parameters[idx].value);

	if ((idx = find_param_idx("MODSEC_RPC_REVERSEPROXY_LOCKFILE",parameters,num_of_params)) >= 0)
		strcpy(modsec_rpc_reverseproxy_lockfile,parameters[idx].value);

	if ((idx = find_param_idx("MODSEC_RPC_EXTERNALNIC_LOCKFILE",parameters,num_of_params)) >= 0)
		strcpy(modsec_rpc_externalnic_lockfile,parameters[idx].value);

	if ((idx = find_param_idx("MODSEC_RPC_MUI_LOCKFILE",parameters,num_of_params)) >= 0)
		strcpy(modsec_rpc_mui_lockfile,parameters[idx].value);

	if ((idx = find_param_idx("MODSEC_RPC_LOG_LEVEL",parameters,num_of_params)) >= 0)
		strcpy(modsec_rpc_log_level,parameters[idx].value);

	if ((idx = find_param_idx("MODSEC_PROXY_HOME",parameters,num_of_params)) >= 0)
		strcpy(modsec_proxy_home,parameters[idx].value);

	if ((idx = find_param_idx("MODSEC_PROXY_IP",parameters,num_of_params)) >= 0)
		strcpy(modsec_proxy_ip,parameters[idx].value);

	if ((idx = find_param_idx("MODSEC_PROXY_PORT",parameters,num_of_params)) >= 0)
		strcpy(modsec_proxy_port,parameters[idx].value);

	if ((idx = find_param_idx("MODSEC_PROXY_NETWORK_PREFIX",parameters,num_of_params)) >= 0)
		strcpy(modsec_proxy_network_prefix,parameters[idx].value);

	if ((idx = find_param_idx("MODSEC_PROXY_BIN",parameters,num_of_params)) >= 0)
		strcpy(modsec_proxy_bin,parameters[idx].value);

	if ((idx = find_param_idx("MODSEC_PROXY_CONF",parameters,num_of_params)) >= 0)
		strcpy(modsec_proxy_conf,parameters[idx].value);

	if ((idx = find_param_idx("MODSEC_PROXY_EXT_NIC",parameters,num_of_params)) >= 0)
		strcpy(modsec_proxy_ext_nic,parameters[idx].value);

	if ((idx = find_param_idx("MODSEC_PROXY_PID",parameters,num_of_params)) >= 0)
		strcpy(modsec_proxy_pid,parameters[idx].value);

	if ((idx = find_param_idx("MODSEC_PROXY_WHITELIST",parameters,num_of_params)) >= 0)
		strcpy(modsec_proxy_whitelist,parameters[idx].value);

	if ((idx = find_param_idx("MODSEC_PROXY_BLACKLIST",parameters,num_of_params)) >= 0)
		strcpy(modsec_proxy_blacklist,parameters[idx].value);

	if ((idx = find_param_idx("MODSEC_PROXY_TIMEOUT",parameters,num_of_params)) >= 0)
		strcpy(modsec_proxy_timeout,parameters[idx].value);

	if ((idx = find_param_idx("MODSEC_PROXY_EXCHANGE",parameters,num_of_params)) >= 0)
		strcpy(modsec_proxy_exchange,parameters[idx].value);

	if ((idx = find_param_idx("MODSEC_PROXY_EXT_IPS",parameters,num_of_params)) >= 0)
		strcpy(modsec_proxy_ext_ips,parameters[idx].value);

	if ((idx = find_param_idx("MODSEC_MUI_UI_ADMIN",parameters,num_of_params)) >= 0)
		strcpy(modsec_mui_ui_admin,parameters[idx].value);

	if ((idx = find_param_idx("MODSEC_RPC_PASSWORD_FILE",parameters,num_of_params)) >= 0)
		strcpy(modsec_rpc_password_file,parameters[idx].value);

	if ((idx = find_param_idx("MODSEC_MUI_UI_IPADDRESS",parameters,num_of_params)) >= 0)
		strcpy(modsec_mui_ui_ipaddress,parameters[idx].value);

	if ((idx = find_param_idx("MODSEC_MUI_UI_PORT",parameters,num_of_params)) >= 0)
		strcpy(modsec_mui_ui_port,parameters[idx].value);

	if ((idx = find_param_idx("SENSOR_ID",parameters,num_of_params)) >= 0)
		strcpy(sensor_id,parameters[idx].value);

	if ((idx = find_param_idx("SERIAL",parameters,num_of_params)) >= 0)
		strcpy(serial,parameters[idx].value);

	if ((idx = find_param_idx("VERSION_NUMBER",parameters,num_of_params)) >= 0)
		strcpy(version_number,parameters[idx].value);

	if ((idx = find_param_idx("RELEASE_DATE",parameters,num_of_params)) >= 0)
		strcpy(release_date,parameters[idx].value);

	if ((idx = find_param_idx("BRIDGE_MODE",parameters,num_of_params)) >= 0)
		strcpy(bridge_mode,parameters[idx].value);

	if ((idx = find_param_idx("DATA_DISK_SPACE",parameters,num_of_params)) >= 0)
		strcpy(data_disk_space,parameters[idx].value);

	if ((idx = find_param_idx("CONN_RATE",parameters,num_of_params)) >= 0)
		strcpy(conn_rate,parameters[idx].value);

	if ((idx = find_param_idx("CONN_RATE_PER_ADDR",parameters,num_of_params)) >= 0)
		strcpy(conn_rate_per_addr,parameters[idx].value);

	if ((idx = find_param_idx("CONNS",parameters,num_of_params)) >= 0)
		strcpy(conns,parameters[idx].value);

	if ((idx = find_param_idx("CONNS_PER_ADDR",parameters,num_of_params)) >= 0)
		strcpy(conns_per_addr,parameters[idx].value);

	if ((idx = find_param_idx("MODSEC_RPC",parameters,num_of_params)) >= 0)
		strcpy(modsec_rpc,parameters[idx].value);

	if ((idx = find_param_idx("MODSEC_PROXY",parameters,num_of_params)) >= 0)
		strcpy(modsec_proxy,parameters[idx].value);

	if ((idx = find_param_idx("MODSEC_PROXY_SCRIPT",parameters,num_of_params)) >= 0)
		strcpy(modsec_proxy_script,parameters[idx].value);

	return num_of_params;
}

int init_cgi()
{
	char *modsec;

	setresuid(0,0,0);
	setresgid(0,0,0);

	strcpy(modsec_cli_home,"/opt/modsecurity-cli");
	strcpy(modsec_rpc_home,"/opt/modsecurity-rpc");
	strcpy(modsec_rpc_log_file,"/opt/modsecurity-rpc/var/logs/rpc.log");
	strcpy(modsec_rpc_log_level,"0");
	strcpy(modsec_rpc_ssl_lockfile,"/opt/modsecurity-rpc/var/run/ssl.lock");
	strcpy(modsec_rpc_sensor_lockfile,"/opt/modsecurity-rpc/var/run/sensor.lock");
	strcpy(modsec_rpc_externalnic_lockfile,"/opt/modsecurity-rpc/var/run/externalnic.lock");
	strcpy(modsec_rpc_reverseproxy_lockfile,"/opt/modsecurity-rpc/var/run/reverseproxy.lock");
	strcpy(modsec_rpc_mui_lockfile,"/opt/modsecurity-rpc/var/run/mui.lock");
	strcpy(modsec_proxy_home,"/opt/modsecurity-proxy");
	strcpy(modsec_proxy_ip,"127.0.0.2");
	strcpy(modsec_proxy_port,"80");
	strcpy(modsec_proxy_bin,"/bin/modsec-proxyd");
	strcpy(modsec_proxy_script,"/etc/init.d/modsec-proxy");
	strcpy(modsec_proxy_conf,"/etc/httpd.conf");
	strcpy(modsec_proxy_ext_nic,"eth0");
	strcpy(modsec_proxy_network_prefix,"172.16.0.0/12");
	strcpy(modsec_proxy_pid,"/opt/modsecurity-proxy/var/run/httpd.pid");
	strcpy(modsec_proxy_whitelist,"/opt/breach/etc/modsec_whitelist.conf");
	strcpy(modsec_proxy_blacklist,"/opt/breach/etc/modsec_blacklist.conf");
	strcpy(modsec_proxy_timeout,"120");
	strcpy(modsec_proxy_exchange,"/opt/modsecurity-proxy/var/exchange");
	strcpy(modsec_proxy_ext_ips,"/opt/breach/etc/modsec_ips.conf");
	strcpy(modsec_mui_ui_ipaddress,"127.0.0.1");
	strcpy(modsec_mui_ui_port,"443");
	strcpy(modsec_rpc_password_file,"/opt/modsecurity-rpc/etc/.htpasswd");
	strcpy(modsec_mui_ui_admin,"admin");
	strcpy(sensor_id,"1");
	strcpy(serial,"1");
	strcpy(version_number,"2.0");
	strcpy(bridge_mode,"off");
	strcpy(data_disk_space,"60");
	strcpy(release_date,"11-15-2006");
	strcpy(conn_rate,"0");
	strcpy(conn_rate_per_addr,"0");
	strcpy(conns,"0");
	strcpy(conns_per_addr,"0");

	if (modsec = getenv("MODSEC"))
		read_conf_file(modsec);
	else {
		if (!read_conf_file("/opt/breach/etc/modsec.conf"))
			read_conf_file("/etc/modsec.conf");
	}

	return 0;
}
