from emmett_core.protocols.rsgi.test_client.client import (
    ClientContext as _ClientContext,
    ClientHTTPHandlerMixin,
    EmmettTestClient as _EmmettTestClient,
)

from .ctx import current
from .rsgi.handlers import HTTPHandler
from .wrappers.response import Response


class ClientContextResponse(Response):
    def __init__(self, original_response: Response):
        super().__init__()
        self.status = original_response.status
        self.headers._data.update(original_response.headers._data)
        self.cookies.update(original_response.cookies.copy())
        self.__dict__.update(original_response.__dict__)


class ClientContext(_ClientContext):
    _response_wrap_cls = ClientContextResponse

    def __init__(self, ctx):
        super().__init__(ctx)
        self.T = current.T


class ClientHTTPHandler(ClientHTTPHandlerMixin, HTTPHandler):
    _client_ctx_cls = ClientContext


class EmmettTestClient(_EmmettTestClient):
    _current = current
    _handler_cls = ClientHTTPHandler
