#!/usr/bin/python
# coding=utf-8

import re
import json
import socket
from io import BytesIO

http_methods = [
    "OPTIONS",
    "GET",
    "HEAD",
    "POST",
    "PUT",
    "PATCH",
    "DELETE",
    "TRACE",
    "CONNECT"
]

http_status_text = {
    "100": "Continue",
    "101": "Switching Protocols",
    "102": "Processing",
    "103": "Early Hints",
    "200": "OK",
    "201": "Created",
    "202": "Accepted",
    "203": "Non-Authoritative Information",
    "204": "No Content",
    "205": "Reset Content",
    "206": "Partial Content",
    "207": "Multi-Status",
    "208": "Already Reported",
    "226": "IM Used",
    "300": "Multiple Choices",
    "301": "Moved Permanently",
    "302": "Moved Temporarily",
    "303": "See Other",
    "304": "Not Modified",
    "305": "Use Proxy",
    "306": "— зарезервировано",
    "307": "Temporary Redirect",
    "308": "Permanent Redirect",
    "400": "Bad Request",
    "401": "Unauthorized",
    "402": "Payment Required",
    "403": "Forbidden",
    "404": "Not Found",
    "405": "Method Not Allowed",
    "406": "Not Acceptable",
    "407": "Proxy Authentication Required",
    "408": "Request Timeout",
    "409": "Conflict",
    "410": "Gone",
    "411": "Length Required",
    "412": "Precondition Failed",
    "413": "Payload Too Large",
    "414": "URI Too Long",
    "415": "Unsupported Media Type",
    "416": "Range Not Satisfiable",
    "417": "Expectation Failed",
    "418": "I’m a teapot",
    "419": "Authentication Timeout",
    "421": "Misdirected Request",
    "424": "Failed Dependency",
    "425": "Too Early",
    "426": "Upgrade Required",
    "428": "Precondition Required",
    "429": "Too Many Requests",
    "431": "Request Header Fields Too Large",
    "449": "Retry With",
    "451": "Unavailable For Legal Reasons",
    "499": "Client Closed Request",
    "500": "Internal Server Error",
    "501": "Not Implemented",
    "502": "Bad Gateway",
    "503": "Service Unavailable",
    "504": "Gateway Timeout",
    "505": "HTTP Version Not Supported",
    "506": "Variant Also Negotiates",
    "507": "Insufficient Storage",
    "508": "Loop Detected",
    "509": "Bandwidth Limit Exceeded",
    "510": "Not Extended",
    "511": "Network Authentication Required",
    "520": "Unknown Error",
    "521": "Web Server Is Down",
    "522": "Connection Timed Out",
    "523": "Origin Is Unreachable",
    "524": "A Timeout Occurred",
    "525": "SSL Handshake Failed",
    "526": "Invalid SSL Certificate"
}


class Request:
    def __init__(self):
        self.url = None
        self.protocol = None
        self.method = None
        self.get = {}
        self.headers = {}
        self.content = None

    def json(self):
        return json.loads(self.content, encoding="utf8")


class Response:
    def __init__(self, content="", status=200, headers=None):
        self.content = content
        self.status = status
        self.headers = headers


class Droplet:
    def __init__(self, ip="localhost", **kwargs):
        self._ip = ip
        self._port = kwargs.get("port", 80)
        self._name = kwargs.get("name", "Droplet")
        self._connections = kwargs.get("connections", 10)
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._socket.bind((self._ip, self._port))
        self._socket.listen(self._connections)
        self._buf_size = kwargs.get("buf_size", 4096)
        self._routs = {}

    def route(self, path, methods=None):
        if methods is None:
            methods = ['GET']
        if path in self._routs:
            raise Exception("Path duplication!")
        container = {
            "route": path,
            "methods": methods,
            "call": None
        }
        self._routs[path] = container

        def wrap(func):
            container["call"] = func

        return wrap

    def run(self):
        while True:
            con, address = self._socket.accept()
            request: Request = self.read_http(con)
            response: Response = self.handle_request(request)
            self.write_http(con, response)

    def read_http(self, con):
        request = Request()
        with BytesIO() as buffer:
            headers_done = False
            # Цикл чтения из входящего потока
            while True:
                # Читаем входящее сообщение в буфер
                data = con.recv(self._buf_size)
                buffer.write(data)
                buffer.seek(0)
                offset = 0

                # Пока мы не закончили читать заголовки
                if not headers_done:
                    # Читаем из буффера построчно
                    for line in buffer:
                        offset += len(line)
                        line = line.decode("utf-8").strip()
                        if not request.method:
                            # Если нет первого заголовка - то первая же строка - это заголовок запроса
                            parts = line.split(' ', 2)
                            request.url = parts[1]
                            request.protocol = parts[2]
                            request.method = parts[0]
                            if '?' in request.url:
                                # Если в запросе есть GET аргументы - нужно их вынуть
                                # Они выглядят так:
                                # http://site.com/some/page?name1=arg1&name2=arg2 ...
                                parts = request.url.split('?', 1)
                                request.url = parts[0]
                                for item in parts[1].split("&"):
                                    parts = item.split('=', 1)
                                    if len(parts) > 1:
                                        request.get[parts[0]] = parts[1]
                            continue
                        if len(line) == 0:
                            # Пустая линия в HTTP означает конец заголовка и начало тела запроса
                            headers_done = True
                            break
                        # разбираем заголовки вида
                        # name: value
                        # name: value-1, value-2, value-3
                        parts = line.split(':', 1)
                        name = parts[0].strip()
                        value = parts[1].strip()
                        request.headers[name] = value

                # убираем из буффера все прочитанные строки
                if offset:
                    buffer.seek(offset)
                    remaining = buffer.read()
                    buffer.truncate(0)
                    buffer.seek(0)
                    buffer.write(remaining)
                else:
                    buffer.seek(0, 2)

                # Когда все заголовки прочитаны
                if headers_done:
                    if 'Content-Length' not in request.headers:
                        request.headers['Content-Length'] = 0
                    length = buffer.seek(0, 2)
                    required = int(request.headers['Content-Length'])
                    if length < required:
                        # Если мы получили не все данные - продолжаем цикл чтения из сокета
                        continue
                    else:
                        # Если получили - кладём в реквест
                        buffer.seek(0)
                        request.content = buffer.read(required)
                        break
        # Иии мы выходим вот сюда
        return request

    def handle_request(self, request: Request):
        response = None
        # Пробегаемся по всем существующим путям и ищем в них тот, который совпадёт
        for path in self._routs:
            m = re.match(path, request.url)
            if m:
                container = self._routs[path]
                # Проверяем что метод применим
                if request.method in container['methods']:
                    # достаём из пути аргументы
                    kwargs = dict(m.groupdict())
                    kwargs['request'] = request
                    response = container['call'](**kwargs)
                    if not isinstance(response, Response):
                        # Если метод вернул не Response - пробуем завернуть в респонс самостоятельно
                        if isinstance(response, str):
                            response = Response(response)
                        elif isinstance(response, dict):
                            response = Response(json.dumps(response),
                                                headers={"Content-Type": "application/json; charset=utf-8"})
                        else:
                            # если непойми что - возвращаем как ошибку
                            response = Response(str(response), 500)
                    break
        if not response:
            # Ни один обработчик не сработал
            response = Response("Not Found", 404)
        return response

    def write_http(self, con, response: Response):
        global http_methods
        global http_status_text

        # Собираем базовые заголовки
        content = bytes(response.content, encoding="utf8")
        headers = {
            "Server": self._name,
            "Allow": ', '.join(http_methods),
            "Content-Length": len(content),
            "Content-Type": "text/html; charset=utf-8"
        }

        # Добавляем заголовки, определённые методом ответа
        if response.headers:
            headers.update(response.headers)

        # И всё пишем в исходящий поток
        status = str(response.status)
        status_line = http_status_text[status] if status in http_status_text else ""
        con.send(bytes(f"HTTP/1.1 {status} {status_line}\n", encoding="utf8"))
        for k, v in headers.items():
            con.send(bytes(f"{k}: {v}\n", encoding="utf8"))
        con.send(bytes(f"\n", encoding="utf8"))
        con.send(content)

        con.close()
