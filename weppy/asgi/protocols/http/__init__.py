# -*- coding: utf-8 -*-

from .. import ProtocolWrapperRegistry, ProtocolWrapper


# class Protocol(object):
#     def __init__(self, packages={}, *args, **kwargs):
#         for key, val in packages.items():
#             setattr(self, key, val)
#         self._init(*args, **kwargs)
#         self.init()

#     def _init(
#         self, app, loop=None, connections=None, tasks=None, state=None,
#         logger=None, access_log=True, ws_protocol_class=None, root_path='',
#         limit_concurrency=None, keep_alive_timeout=5
#     ):
#         self.app = app
#         self.loop = loop or asyncio.get_event_loop()
#         self.connections = set() if connections is None else connections
#         self.tasks = set() if tasks is None else tasks
#         self.state = {'total_requests': 0} if state is None else state
#         # self.logger = logger or logging.getLogger("uvicorn")
#         # self.access_log = access_log and (self.logger.level <= logging.INFO)
#         self.ws_protocol_class = ws_protocol_class
#         self.root_path = root_path
#         self.limit_concurrency = limit_concurrency

#         # Timeouts
#         self.keep_alive_timeout_task = None
#         self.keep_alive_timeout = keep_alive_timeout

#         # Per-connection state
#         self.transport = None
#         self.flow = None
#         self.server = None
#         self.client = None
#         self.scheme = None
#         self.pipeline = []

#         # Per-request state
#         self.url = None
#         self.scope = None
#         self.headers = None
#         self.expect_100_continue = False
#         self.cycle = None
#         self.message_event = asyncio.Event()

#     def init(self):
#         pass


protocols = ProtocolWrapperRegistry()

from . import (
    auto,
    h11,
    httptools
)
