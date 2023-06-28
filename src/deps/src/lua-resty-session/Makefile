.PHONY: lint test docs

lint:
	@luacheck -q ./lib

unit:
	busted --exclude-tags=noci

unit-all:
	busted

prove:
	prove

docs:
	ldoc .
