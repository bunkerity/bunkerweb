import sys, traceback

from Job import JobManagement, ReloadRet
from logger import log

if __name__ == "__main__" :
	try :
		management = JobManagement()
		ret = management.reload()
		if ret == ReloadRet.OK or ret == ReloadRet.NO :
			sys.exit(0)
		sys.exit(1)
	except :
		log("reload", "ERROR", "can't reload nginx (exception)")
		log("reload", "ERROR", traceback.format_exc())
		sys.exit(2)
