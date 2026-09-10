"""``Templator.__init__``'s single-site strip now calls `strip_default_server_unless_alone`
(wave 19, lane N18 -- port of note #10) instead of hand-rolling the "unless alone" rule with a bare
list comprehension. The existing coverage (`test_default_server_multisite_only.py`,
`test_default_server_single_site_keep.py`) already proves the two edge inputs the helper's contract
names: the reserved id ALONE is kept, the reserved id WITH another name is stripped. Neither exercises
a `SERVER_NAME` that repeats the reserved id with nothing else -- the shape that would silently break
if the refactor compared list LENGTHS instead of the lists themselves (`len(names) != len(declared)`,
the old branch condition, treats two entries stripped down to zero same as one entry stripped down to
zero, so it happens to still work -- but a `names != declared` regression that instead diffed identity
or a naive membership check could not tell "collapsed to zero" from "one of two removed" apart without
this case pinning it down).
"""

from default_server import DEFAULT_SERVER_ID  # type: ignore


class TestDuplicateReservedIdOnly:
    def test_two_copies_of_the_reserved_id_alone_are_still_kept(self, render_tree, monkeypatch):
        import Templator as T  # type: ignore
        from types import SimpleNamespace

        said = []
        monkeypatch.setattr(T, "logger", SimpleNamespace(warning=said.append, error=said.append, info=lambda *a: None, debug=lambda *a: None))

        tree = render_tree(SERVER_NAME=f"{DEFAULT_SERVER_ID} {DEFAULT_SERVER_ID}", MULTISITE="no")
        assert [message for message in said if DEFAULT_SERVER_ID in message and "is KEPT" in message], said
        server_conf = next(content for path, content in tree.items() if path.endswith("server.conf"))
        assert f"server_name {DEFAULT_SERVER_ID} {DEFAULT_SERVER_ID};" in server_conf
