"""One identity per client address, the Python twin of src/bw/lua/bunkerweb/ipaddr.lua.

Bans, unbans and their lookups are keyed on the text of the address, and NGINX prints an IPv6 `$remote_addr` in its
canonical form (lowercase, compressed). An operator may type the same address expanded or in upper case, and an
IPv4-mapped IPv6 address (::ffff:a.b.c.d) is the IPv4 address a.b.c.d, so every writer converts what it receives to
that one spelling before it stores, looks up or forwards it.
"""

from ipaddress import IPv6Address, ip_address


def normalize_ip(value: str) -> str:
    """Canonical text of a bare IPv4 or IPv6 address. Raises ValueError for anything else.

    Brackets, a prefix length and a zone id (`fe80::1%eth0`) are refused: none of them names one client address.
    """
    if not isinstance(value, str):
        raise ValueError("IP address must be a string")
    text = value.strip()
    if any(char in text for char in "%[]/"):
        raise ValueError(f"{value!r} is not a bare IP address")
    address = ip_address(text)
    if isinstance(address, IPv6Address):
        if address.ipv4_mapped is not None:
            return str(address.ipv4_mapped)
        # ngx_inet6_ntop writes the last 32 bits in dotted form after a leading run of 6 zero words (::a.b.c.d), or of 7
        # when the last word is neither 0 nor 1 in its bytes. It is the spelling of $remote_addr, so it is the identity.
        packed = address.packed
        leading = next((i for i in range(8) if packed[2 * i] or packed[2 * i + 1]), 8)
        if leading == 6 or (leading == 7 and packed[14] and packed[15] != 1):
            return "::" + ".".join(str(octet) for octet in packed[12:])
    return str(address)
