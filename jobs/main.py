#!/usr/bin/python3

import argparse, sys, re

sys.path.append("/opt/bunkerized-nginx/jobs")

import Abusers, CertbotNew, CertbotRenew, ExitNodes, GeoIP, Proxies, Referrers, SelfSignedCert, UserAgents
from Job import JobRet, JobManagement, ReloadRet

from logger import log

JOBS = {
	"abusers": Abusers.Abusers,
	"certbot-new": CertbotNew.CertbotNew,
	"certbot-renew": CertbotRenew.CertbotRenew,
	"exit-nodes": ExitNodes.ExitNodes,
	"geoip": GeoIP.GeoIP,
	"proxies": Proxies.Proxies,
	"referrers": Referrers.Referrers,
	"remote-api-database": RemoteApiDatabase.RemoteApiDatabase,
	"remote-api-register": RemoteApiRegister.RemoteApiRegister,
	"self-signed-cert": SelfSignedCert.SelfSignedCert,
	"user-agents": UserAgents.UserAgents

}

if __name__ == "__main__" :

	# Parse arguments
	parser = argparse.ArgumentParser(description="job runner for bunkerized-nginx")
	parser.add_argument("--name", default="", type=str, help="job to run (e.g : abusers or certbot-new or certbot-renew ...)")
	parser.add_argument("--cache", action="store_true", help="copy data from cache if available")
	parser.add_argument("--lock", action="store_true", help="lock access to the configuration")
	parser.add_argument("--reload", action="store_true", help="reload nginx if necessary and the job is successful")
	parser.add_argument("--domain", default="", type=str, help="domain(s) for certbot-new job (e.g. : www.example.com or app1.example.com,app2.example.com)")
	parser.add_argument("--email", default="", type=str, help="email for certbot-new job (e.g. : contact@example.com)")
	parser.add_argument("--staging", action="store_true", help="use staging server for let's encrypt instead of the production one")
	parser.add_argument("--dst_cert", default="", type=str, help="certificate path for self-signed-cert job (e.g. : /etc/nginx/default-cert.pem)")
	parser.add_argument("--dst_key", default="", type=str, help="key path for self-signed-cert job (e.g. : /etc/nginx/default-key.pem)")
	parser.add_argument("--expiry", default="", type=str, help="number of validity days for self-signed-cert job (e.g. : 365)")
	parser.add_argument("--subj", default="", type=str, help="certificate subject for self-signed-cert job (e.g. : OU=X/CN=Y...)")
	parser.add_argument("--server", default="", type=str, help="address of the server for remote-api jobs")
	parser.add_argument("--id", default="", type=str, help="machine id for remote-api jobs")
	parser.add_argument("--version", default="", type=str, help="bunkerized-nginx version for remote-api jobs")
	args = parser.parse_args()

	# Check job name
	if not args.name in JOBS :
		log("job", "ERROR", "unknown job " + args.name)
		sys.exit(1)
	job = args.name

	# Acquire the lock before
	management = JobManagement()
	if args.lock :
		management.lock()

	# Check if we are using redis or not
	redis_host = None
	try :
		with open("/etc/nginx/global.env", "r") as f :
			data = f.read()
		if re.search(r"^USE_REDIS=yes$", data, re.MULTILINE) :
			re_match = re.search(r"^REDIS_HOST=(.+)$", data, re.MULTILINE)
			if re_match :
				redis_host = re_match.group(1)
	except :
		log("job", "ERROR", "can't check if redis is used")

	# Run job
	log("job", "INFO", "executing job " + job)
	ret = 0
	if job == "certbot-new" :
		instance = JOBS[job](redis_host=redis_host, copy_cache=args.cache, domain=args.domain, email=args.email, staging=args.staging)
	elif job == "self-signed-cert" :
		instance = JOBS[job](redis_host=redis_host, copy_cache=args.cache, dst_cert=args.dst_cert, dst_key=args.dst_key, expiry=args.expiry, subj=args.subj)
	elif job == "remote-api-database" :
		instance = JOBS[job](server=args.server, version=args.version, id=args.id, redis_host=redis_host, copy_cache=args.cache)
	elif job == "remote-api-register" :
		instance = JOBS[job](server=args.server, version=args.version)
	else :
		instance = JOBS[job](redis_host=redis_host, copy_cache=args.cache)
	ret = instance.run()
	if ret == JobRet.KO :
		log("job", "ERROR", "error while running job " + job)
		if args.lock :
			management.unlock()
		sys.exit(1)
	log("job", "INFO", "job " + job + " successfully executed")

	# Reload
	if ret == JobRet.OK_RELOAD and args.reload :
		ret = management.reload()
		if ret == ReloadRet.KO :
			log("job", "ERROR", "error while doing reload operation (job = " + job + ")")
			if args.lock :
				management.unlock()
			sys.exit(1)
		elif ret == ReloadRet.OK :
			log("job", "INFO", "reload operation successfully executed (job = " + job + ")")
		elif ret == ReloadRet.NO :
			log("job", "INFO", "skipped reload operation because nginx is not running (job = " + job + ")")
	else :
		log("job", "INFO", "skipped reload operation because it's not needed (job = " + job + ")")

	# Release the lock
	if args.lock :
		management.unlock()

	# Done
	sys.exit(0)
