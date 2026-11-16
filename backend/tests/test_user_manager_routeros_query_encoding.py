from routeros_api.query import AndQuery, IsGreaterQuery, IsLessQuery


def test_routeros_api_library_encodes_exclusive_username_range_queries():
    query = AndQuery(
        IsGreaterQuery("username", "voucher-100"),
        IsLessQuery("username", "voucher-900"),
    )

    assert query.get_api_format() == [
        b"?>username=voucher-100",
        b"?<username=voucher-900",
        b"?#&",
    ]


def test_routeros_api_library_keeps_query_bounds_as_separate_words():
    lower = IsGreaterQuery("username", "A").get_api_format()
    upper = IsLessQuery("username", "z").get_api_format()

    assert lower == [b"?>username=A"]
    assert upper == [b"?<username=z"]
