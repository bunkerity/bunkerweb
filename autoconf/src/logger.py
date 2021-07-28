import datetime

def log(title, severity, msg) :
	when = datetime.datetime.today().strftime("[%Y-%m-%d %H:%M:%S]")
	what = title + " - " + severity + " - " + msg
	print(when + " " + what, flush=True)
