def dnsbl():
    return {
        "message": "ok",
        "data": {
            "info": "test",
            "items": [{"server_name": "www.example.com", "status": "ok"}, {"server_name": "app1.com", "status": "ok"}, {"server_name": "test.2.fr", "status": "ko"}],
        },
    }
