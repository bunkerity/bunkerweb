def customcert():
    return {
        "message": "ok",
        "data": {
            "info": "test",
            "items": [{"server_name": "www.example.com", "cn": "Let's encrypt", "expire": "15/11/2024"}, {"server_name": "app1.com", "cn": "Self signed", "expire": "11/01/2028"}, {"server_name": "test.2.fr", "cn": "Default", "expire": "31/08/2035"}],
        },
    }
