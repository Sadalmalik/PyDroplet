#!/usr/bin/python
# coding=utf-8

import json
import pprint
from Droplet import *

app = Droplet()
pp = pprint.PrettyPrinter(indent=4)

@app.route(r"^/$")
def index(request):
    print("[TEST] index")
    print(request.protocol)
    print(request.method)
    print(request.url)
    pp.pprint(request.get)
    pp.pprint(request.headers)
    print(request.content)
    print()
    return "Yaay!!\n>( ^ ____ ^ )<"


@app.route(r"^/check/(?P<page>\d+)/$")
def check(request, page):
    print("[TEST] check")
    print(request.protocol)
    print(request.method)
    print(request.url)
    pp.pprint(request.get)
    pp.pprint(request.headers)
    print(request.content)
    print()
    return f"Your page: {page}"


if __name__ == "__main__":
    app.run()
