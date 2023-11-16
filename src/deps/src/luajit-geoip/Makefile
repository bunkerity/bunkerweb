
.PHONY: test local build valgrind

test:
	busted

local: build
	luarocks make --lua-version=5.1 --local geoip-dev-1.rockspec

build:
	moonc geoip

valgrind_geoip:
	valgrind --leak-check=yes --trace-children=yes busted spec/geoip_spec.moon

valgrind_mmdb:
	valgrind --leak-check=yes --trace-children=yes busted spec/mmdb_spec.moon

lint::
	git ls-files | grep '\.moon$$' | xargs -n 100 moonc -l
