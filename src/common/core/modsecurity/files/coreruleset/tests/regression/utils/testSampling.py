from ftw import ruleset, http, errors

"""
This script assumes that default blocking action is 403
and sampling is one. It will send a know bad request 
that is expected to be blocked. If sampling is on it
will only block a certain percentage. We send 1000 
requests to verify this. In order to do this we must
also turn off IP Reputation blocking.
SecAction "id:900005,phase:1,nolog,pass,ctl:ruleEngine=on,ctl:ruleRemoveById=910000"
"""
def send_requests(input_data,subiters,result,index):
	http_ua = http.HttpUA()
	for i in range(0,subiters):
		new_index = str(index)+str(i)
		http_ua.send_request(input_data)
		result[new_index] = http_ua.response_object.status
def run_requests(iterations):
	"""Post request with no content-type AND no content-length"""
	x = ruleset.Input(method="GET", protocol="http",port=80,uri='/?X="><script>alert(1);</script>',dest_addr="localhost",headers={"Host":"localhost","User-Agent":"ModSecurity CRS 3 test"})
	import threading
	returns = {}
	threads = []
	for i in range(5):
		t = threading.Thread(target=send_requests,args=(x,100, returns,i,))
		threads.append(t)
		t.start()
	for t in threads:
		t.join()
	status_not_403 = 0
	status_403 = 0
	for status in returns.values():
		if status == 403:	
			status_403 += 1
		else:
			status_not_403 += 1
	x = (status_403/(len(returns)*1.0))*100
	y = (status_not_403/(len(returns)*1.0))*100
	print "403s =", x
	print "not 403s =", y
	return (x,y)
		
def test_sampling():
	print "running"
	block,passed = run_requests(100)
	assert block < 55 and block > 45
