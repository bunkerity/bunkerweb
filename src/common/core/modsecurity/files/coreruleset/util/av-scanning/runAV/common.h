#include <stdio.h>
#include <stdlib.h>
#include <errno.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <arpa/inet.h>
#include <unistd.h>
#include <dirent.h>
#include <time.h>
#include <fcntl.h>
#include <crypt.h>

#define MAX_PARAMS 256
#define MAX_IPS 256
#define MAX_NAME_LENGTH 256
#define MAX_VALUE_LENGTH 1024
#define MAX_CMD_LENGTH 1024
#define MAX_TOKEN_LENGTH 1024
#define MAX_OUTPUT_LINE_LEN (1024)
#define MAX_OUTPUT_SIZE (MAX_OUTPUT_LINE_LEN*1024)
#define WHITE 1
#define BLACK 0
#define NONE 0
#define DEBUG 1

typedef struct {
	char name[MAX_NAME_LENGTH];
	char value[MAX_VALUE_LENGTH];
} parameter_t;

typedef struct {
	char ip[16];
	time_t start;
	long duration;
	time_t end;
	char token[MAX_TOKEN_LENGTH];
} blocklist_t;

EXTERN int lock_file(char *filename);
EXTERN int unlock_file(int fd);
EXTERN int print_reply(char *reply);
EXTERN int print_error(char *func1, char* func2, char* str, int err);
EXTERN int print_request(char* url,char *command,parameter_t *parameters, int num_of_parameters, int mask);
EXTERN int print_request_force(char* url,char *command,parameter_t *parameters, int num_of_parameters, int mask);
EXTERN int is_proxy_up();
EXTERN int run_cmd(char *command, char *output, int output_size);
EXTERN int parse_cli (parameter_t *parameters, int max_parameters, int num_of_args, char *args[]);
EXTERN int parse_query_and_body(parameter_t *parameters, int max_parameters);
EXTERN int parse_query(char *query, parameter_t *parameters, int max_parameters);
EXTERN int parse_file(char *filename, parameter_t *parameters, int max_parameters);
EXTERN int copy_file(char *src_file, char *dst_file);
EXTERN int change_file(char *filename, parameter_t parameter);
EXTERN int find_param_idx(char *parameter_name, parameter_t *parameters, int max_parameters);
EXTERN int init_cgi();
EXTERN int send_request(char *request,char *ip,char *port,char *reply,int max_reply_size);
EXTERN int find_ip_idx(char *ip, blocklist_t *blocklist, int num_of_ips);
EXTERN int remove_ip_idx(char *ip, blocklist_t *blocklist, int num_of_ips);

EXTERN char modsec_rpc[1024];
EXTERN char modsec_rpc_home[1024];
EXTERN char modsec_rpc_log_file[1024];
EXTERN char modsec_rpc_log_level[1024];
EXTERN char modsec_rpc_ssl_lockfile[1024];
EXTERN char modsec_rpc_externalnic_lockfile[1024];
EXTERN char modsec_rpc_sensor_lockfile[1024];
EXTERN char modsec_rpc_reverseproxy_lockfile[1024];
EXTERN char modsec_rpc_mui_lockfile[1024];
EXTERN char modsec_proxy[1024];
EXTERN char modsec_proxy_home[1024];
EXTERN char modsec_proxy_script[1024];
EXTERN char modsec_proxy_ip[1024];
EXTERN char modsec_proxy_port[1024];
EXTERN char modsec_proxy_bin[1024];
EXTERN char modsec_proxy_conf[1024];
EXTERN char modsec_proxy_ext_nic[1024];
EXTERN char modsec_proxy_pid[1024];
EXTERN char modsec_proxy_whitelist[1024];
EXTERN char modsec_proxy_blacklist[1024];
EXTERN char modsec_proxy_network_prefix[1024];
EXTERN char modsec_proxy_timeout[1024];
EXTERN char modsec_proxy_exchange[1024];
EXTERN char modsec_proxy_ext_ips[1024];
EXTERN char modsec_rpc_password_file[1024];
EXTERN char modsec_mui_ui_admin[1024];
EXTERN char modsec_mui_ui_ipaddress[1024];
EXTERN char modsec_mui_ui_port[1024];
EXTERN char modsec_cli_home[1024];
EXTERN char sensor_id[1024];
EXTERN char serial[1024];
EXTERN char version_number[1024];
EXTERN char bridge_mode[1024];
EXTERN char data_disk_space[1024];
EXTERN char release_date[1024];
EXTERN char conn_rate[1024];
EXTERN char conn_rate_per_addr[1024];
EXTERN char conns[1024];
EXTERN char conns_per_addr[1024];
