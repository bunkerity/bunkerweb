.PHONY: lint test docs

lint:
	@luacheck -q ./lib

unit:
	busted --exclude-tags=noci --coverage

unit-all:
	busted --coverage

prove:
	prove

docs:
	ldoc .
