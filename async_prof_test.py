import asyncio
from weppy import App, response


app = App(__name__)


@app.route()
def plain():
    response.headers['Content-Type'] = 'text/plain'
    return 'foobar'


async def fake_send(*args, **kwargs):
    return


async def fake_receive():
    return {'type': 'http.disconnect'}


async def main():
    scope = {
        'type': 'http', 'http_version': '1.1',
        'server': ('127.0.0.1', 8000),
        'client': ('127.0.0.1', 54689),
        'scheme': 'http', 'method': 'GET',
        'root_path': '', 'path': '/plain', 'query_string': b'',
        'headers': [
            (b'host', b'localhost:8000')
        ]
    }
    for _ in range(0, 10000):
        await app(scope)(fake_receive, fake_send)

if __name__ == '__main__':
    asyncio.run(main())
