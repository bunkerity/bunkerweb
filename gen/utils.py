def load_variables(path) :
	variables = {}
	with open(path) as f :
		lines = f.read().splitlines()
	for line in lines :
		if line.startswith("#") or line == "" or not "=" in line :
			continue
		var = line.split("=")[0]
		value = line[len(var)+1:]
		variables[var] = value
	return variables

