import pytest

from util.proxy.ProxyApiProvider import (
    ProxyApiError,
    build_proxy_api_url,
    fetch_proxy_api,
    parse_proxy_api_response,
)


def _proxy_url(scheme: str, username: str, password: str, host: str, port: int) -> str:
    return f"{scheme}://" + f"{username}:{password}@" + f"{host}:{port}"


def test_build_proxy_api_url_keeps_original_query_params():
    url = build_proxy_api_url(
        "  http://api.example.com/get?app_key=abc&count=&format=text&protocol=1  ",
    )

    assert url == "http://api.example.com/get?app_key=abc&count=&format=text&protocol=1"


def test_fetch_proxy_api_rejects_invalid_json_response(monkeypatch):
    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            raise ValueError("Expecting value")

    def fake_request(method, url, headers, data, timeout):
        assert url == "http://api.example.com/get?count=1&format=json&protocol=1"
        return FakeResponse()

    monkeypatch.setattr("util.proxy.ProxyApiProvider.requests.request", fake_request)

    with pytest.raises(ProxyApiError, match="代理 API 未返回合法 JSON"):
        fetch_proxy_api(
            "http://api.example.com/get?count=1&format=json&protocol=1",
            protocol="socks5",
        )


def test_fetch_proxy_api_rejects_invalid_json_before_http_status(monkeypatch):
    class FakeResponse:
        def raise_for_status(self):
            raise RuntimeError("HTTP 500")

        def json(self):
            raise ValueError("Expecting value")

    def fake_request(method, url, headers, data, timeout):
        return FakeResponse()

    monkeypatch.setattr("util.proxy.ProxyApiProvider.requests.request", fake_request)

    with pytest.raises(ProxyApiError, match="代理 API 未返回合法 JSON"):
        fetch_proxy_api(
            "http://api.example.com/get?count=1&format=json&protocol=1",
            protocol="http",
        )


def test_parse_youdaili_success_response_as_http_proxy():
    payload = {
        "code": 0,
        "msg": "OK",
        "data": {
            "count": 1,
            "proxy_list": [
                {
                    "ip": "8.8.8.8",
                    "port": 12234,
                }
            ],
        },
    }

    assert parse_proxy_api_response(payload, protocol="http") == [
        "http://8.8.8.8:12234"
    ]


def test_parse_youdaili_success_response_as_socks_proxy():
    payload = {
        "code": 0,
        "msg": "OK",
        "data": {
            "proxy_list": [
                {
                    "ip": "8.8.8.8",
                    "port": 12234,
                }
            ],
        },
    }

    assert parse_proxy_api_response(payload, protocol="socks5") == [
        "socks5://8.8.8.8:12234"
    ]


def test_parse_proxy_api_keeps_auth_from_standard_url():
    proxy = _proxy_url("http", "proxy_user", "proxy_pass", "192.0.2.10", 15674)
    payload = {
        "code": 0,
        "data": [proxy],
    }

    assert parse_proxy_api_response(payload, protocol="http") == [proxy]


def test_parse_proxy_api_keeps_auth_from_host_port_user_pass():
    payload = {
        "code": 0,
        "proxies": [
            "192.0.2.20:15115:proxy_user:proxy_pass",
        ],
    }

    assert parse_proxy_api_response(payload, protocol="http") == [
        _proxy_url("http", "proxy_user", "proxy_pass", "192.0.2.20", 15115)
    ]


def test_parse_proxy_api_keeps_auth_from_object_fields():
    payload = {
        "code": 0,
        "data": [
            {
                "host": "192.0.2.30",
                "port": 15115,
                "Authkey": "proxy_user",
                "Authpwd": "proxy_pass",
                "protocol": "http",
            }
        ],
    }

    assert parse_proxy_api_response(payload, protocol="http") == [
        _proxy_url("http", "proxy_user", "proxy_pass", "192.0.2.30", 15115)
    ]


def test_parse_proxy_api_keeps_auth_from_http_user_and_http_pass_fields():
    payload = {
        "code": 0,
        "msg": "OK",
        "data": {
            "count": 1,
            "filter_count": 0,
            "surplus_quantity": 0,
            "proxy_list": [
                {
                    "expire_time": "2026-07-08 00:59:33",
                    "http_pass": "proxy_pass",
                    "http_user": "proxy_user",
                    "ip": "192.0.2.60",
                    "port": 35772,
                }
            ],
        },
    }

    assert parse_proxy_api_response(payload, protocol="http") == [
        _proxy_url("http", "proxy_user", "proxy_pass", "192.0.2.60", 35772)
    ]


def test_parse_proxy_api_merges_auth_fields_with_proxy_field():
    payload = {
        "code": 0,
        "data": [
            {
                "proxy": "192.0.2.40:15115",
                "Username": "proxy_user",
                "Password": "proxy_pass",
                "protocol": "http",
            }
        ],
    }

    assert parse_proxy_api_response(payload, protocol="http") == [
        _proxy_url("http", "proxy_user", "proxy_pass", "192.0.2.40", 15115)
    ]


def test_parse_proxy_api_merges_data_level_auth_fields_with_proxy_list():
    payload = {
        "code": 0,
        "data": {
            "proxy_list": ["192.0.2.50:15115"],
            "Username": "proxy_user",
            "Password": "proxy_pass",
        },
    }

    assert parse_proxy_api_response(payload, protocol="http") == [
        _proxy_url("http", "proxy_user", "proxy_pass", "192.0.2.50", 15115)
    ]


def test_parse_proxy_api_keeps_auth_for_socks5_url():
    proxy = _proxy_url("socks5", "user", "pass", "127.0.0.1", 1080)
    payload = {
        "code": 0,
        "data": [proxy],
    }

    assert parse_proxy_api_response(payload, protocol="socks5") == [proxy]


def test_parse_youdaili_failure_response_raises():
    payload = {
        "code": 104,
        "msg": "未检索到满足要求的代理IP，请调整筛选条件后再试，或联系客服处理！",
        "data": None,
    }

    with pytest.raises(ProxyApiError):
        parse_proxy_api_response(payload, protocol="http")
