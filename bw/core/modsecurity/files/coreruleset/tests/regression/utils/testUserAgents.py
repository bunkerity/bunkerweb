from ftw import ruleset, http, errors

"""
This script reads in a list of popular Useragents and checks to see if it triggers
It expects 403's to be returned for a rule firing
"""

def read_useragents(filename):
    f = open(filename,'r')
    useragents = [agent.strip() for agent in f.readlines()]
    return useragents

def run_requests(useragent_list):
    status_not_403 = 0
    status_403 = 0
    for useragent in useragent_list:
        # get me a counter while i'm waiting
        if (status_not_403 + status_403)%15 == 0:
            print("Send",status_not_403 + status_403, "Out of",len(useragent_list))
        input_data = ruleset.Input(method="GET", protocol="http",port=80,uri='/',dest_addr="localhost",headers={"Host":"localhost","User-Agent":useragent})
        http_ua = http.HttpUA()
        http_ua.send_request(input_data)
        status = http_ua.response_object.status
        if status == 403:	
            status_403 += 1
        else:
            status_not_403 += 1        
    x = (status_403/(len(useragent_list)*1.0))*100
    y = (status_not_403/(len(useragent_list)*1.0))*100
    print "403s =", x
    print "not 403s =", y

	
def main():
    uas = read_useragents('./data/popularUAs.data')
    run_requests(uas)
main()	
