tests = {
    "types":
{
    "bn": {
        "new_from": "new(math.random(1, 2333333))",
        "print": "to_hex():upper",
    },
    "number": {
        "new_from": "ngx.time()",
    },
    "pkey": {
        "new_from": "new()",
        "print": "to_PEM"
    },
    "x509.name": {
        "new_from": "new():add('CN', 'earth.galaxy')",
        "print": "tostring",
    },
    "x509.altname": {
        "new_from": "new():add('DNS', 'earth.galaxy')",
        "print": "tostring",
    },

},
}