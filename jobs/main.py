#!/usr/bin/python3

import argparse, sys

sys.path.append("/opt/bunkerized-nginx/jobs")

import Abusers, CertbotNew, CertbotRenew, ExitNodes, GeoIP, Proxies, Referrers, SelfSignedCert, UserAgents

from reload import reload

JOBS = {
	"abusers": Abusers.Abusers,
	"certbot-new": CertbotNew.CertbotNew,
	"certbot-renew": CertbotRenew.CertbotRenew,
	"exit-nodes": ExitNodes.ExitNodes,
	"geoip": GeoIP.GeoIP,
	"proxies": Proxies.Proxies,
	"referrers": Referrers.Referrers,
	"self-signed-cert": SelfSignedCert.SelfSignedCert,
	"user-agents": UserAgents.UserAgents
}

if __name__ == "__main__" :

	# Parse arguments
	parser = argparse.ArgumentParser(description="job runner for bunkerized-nginx")
	parser.add_argument("--name", default="", type=str, help="job to run (e.g : abusers or certbot-new or certbot-renew ...)")
	parser.add_argument("--redis", default=None, type=str, help="hostname of the redis server if any")
	parser.add_argument("--cache", action="store_true", help="copy data from cache if available")
	parser.add_argument("--domain", default="", type=str, help="domain(s) for certbot-new job (e.g. : www.example.com or app1.example.com,app2.example.com)")
	parser.add_argument("--email", default="", type=str, help="email for certbot-new job (e.g. : contact@example.com)")
	parser.add_argument("--dst_cert", default="", type=str, help="certificate path for self-signed-cert job (e.g. : /etc/nginx/default-cert.pem)")
	parser.add_argument("--dst_key", default="", type=str, help="key path for self-signed-cert job (e.g. : /etc/nginx/default-key.pem)")
	parser.add_argument("--expiry", default="", type=str, help="number of validity days for self-signed-cert job (e.g. : 365)")
	parser.add_argument("--subj", default="", type=str, help="certificate subject for self-signed-cert job (e.g. : OU=X/CN=Y...)")
	args = parser.parse_args()

	# Check job name
	if not args.name in JOBS :
		print("[!] unknown job " + args.name)
		sys.exit(1)
	job = args.name

	# Run job
	print("[*] Executing job " + job)
	ret = 0
	if job == "certbot-new" :
		instance = JOBS[job](redis_host=args.redis, copy_cache=args.cache, domain=args.domain, email=args.email)
	elif job == "self-signed-cert" :
		instance = JOBS[job](redis_host=args.redis, copy_cache=args.cache, dst_cert=args.dst_cert, dst_key=args.dst_key, expiry=args.expiry, subj=args.subj)
	else :
		instance = JOBS[job](redis_host=args.redis, copy_cache=args.cache)
	if not instance.run() :
		print("[!] Error while running job " + job)
		sys.exit(1)
	print("[*] Job " + job + " successfully executed")

	# Reload
	# TODO : only reload if needed
	do_reload = True
	if do_reload :
		if not reload() :
			print("[!] Error while doing reload operation")
			sys.exit(1)
		print("[*] Reload operation successfully executed")

	# Done
	sys.exit(0)
