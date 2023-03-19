# -*- coding: utf-8 -*-
"""
    tests.pipeline
    --------------

    Test Emmett pipeline
"""

import asyncio
import pytest

from contextlib import contextmanager

from helpers import current_ctx as _current_ctx, ws_ctx as _ws_ctx
from emmett import App, request, websocket, abort
from emmett.ctx import current
from emmett.http import HTTP
from emmett.pipeline import Pipe, Injector
from emmett.parsers import Parsers
from emmett.serializers import Serializers, _json_type

json_load = Parsers.get_for('json')
json_dump = Serializers.get_for('json')


class PipeException(Exception):
    def __init__(self, pipe):
        self.pipe = pipe


class FlowStorePipe(Pipe):
    @property
    def linear_storage(self):
        return current._pipeline_linear_storage

    @property
    def parallel_storage(self):
        return current._pipeline_parallel_storage

    def store_linear(self, status):
        self.linear_storage.append(self.__class__.__name__ + "." + status)

    def store_parallel(self, status):
        self.parallel_storage.append(self.__class__.__name__ + "." + status)

    async def on_pipe_success(self):
        self.store_linear('success')

    async def on_pipe_failure(self):
        self.store_linear('failure')


class FlowStorePipeCommon(FlowStorePipe):
    async def open(self):
        self.store_parallel('open')

    async def close(self):
        self.store_parallel('close')

    async def pipe(self, next_pipe, **kwargs):
        self.store_linear('pipe')
        return await next_pipe(**kwargs)


class FlowStorePipeSplit(FlowStorePipe):
    async def open_request(self):
        self.store_parallel('open_request')

    async def open_ws(self):
        self.store_parallel('open_ws')

    async def close_request(self):
        self.store_parallel('close_request')

    async def close_ws(self):
        self.store_parallel('close_ws')

    async def pipe_request(self, next_pipe, **kwargs):
        self.store_linear('pipe_request')
        return await next_pipe(**kwargs)

    async def pipe_ws(self, next_pipe, **kwargs):
        self.store_linear('pipe_ws')
        return await next_pipe(**kwargs)


class Pipe1(FlowStorePipeCommon):
    pass


class Pipe2(FlowStorePipeSplit):
    async def pipe_request(self, next_pipe, **kwargs):
        self.store_linear('pipe_request')
        if request.query_params.skip:
            return "block"
        return await next_pipe(**kwargs)

    async def pipe_ws(self, next_pipe, **kwargs):
        self.store_linear('pipe_ws')
        if websocket.query_params.skip:
            return
        await next_pipe(**kwargs)


class Pipe3(FlowStorePipeCommon):
    async def open(self):
        await asyncio.sleep(0.05)
        await super().open()


class Pipe4(FlowStorePipeCommon):
    async def close(self):
        await asyncio.sleep(0.05)
        await super().close()


class Pipe5(FlowStorePipeCommon):
    pass


class Pipe6(FlowStorePipeCommon):
    pass


class Pipe7(FlowStorePipeCommon):
    pass


class ExcPipeOpen(FlowStorePipeCommon):
    async def open(self):
        raise PipeException(self)


class ExcPipeClose(FlowStorePipeCommon):
    async def close(self):
        raise PipeException(self)


class PipeSR1(FlowStorePipeSplit):
    def on_receive(self, data):
        data = json_load(data)
        return dict(pipe1r='receive_inject', **data)

    def on_send(self, data):
        return json_dump(dict(pipe1s='send_inject', **data))


class PipeSR2(FlowStorePipeSplit):
    def on_receive(self, data):
        return dict(pipe2r='receive_inject', **data)

    def on_send(self, data):
        return dict(pipe2s='send_inject', **data)


class CTXInjector(Injector):
    async def pipe_request(self, next_pipe, **kwargs):
        rv = await super().pipe_request(next_pipe, **kwargs)
        current._pipeline_generic_storage.append(rv)
        return rv


class GlobalInjector(CTXInjector):
    foo = "bar"

    def __init__(self):
        self.bar = "baz"
        super().__init__()

    @staticmethod
    def staticm(val):
        return val

    def boundm(self, val):
        return self.foo, val

    @property
    def prop(self):
        return self.bar


class ScopedInjector(CTXInjector):
    namespace = "scoped"
    foo = "bar"

    def __init__(self):
        self.bar = "baz"
        super().__init__()

    @staticmethod
    def staticm(val):
        return val

    def boundm(self, val):
        return self.foo, val

    @property
    def prop(self):
        return self.bar


class CTXWrapper:
    def __init__(self, ctx, router):
        self.ctx = ctx
        self.router = router

    def dispatch(self):
        return self.router.dispatch()


class ReqCTXWrapper(CTXWrapper):
    def dispatch(self):
        return self.router.dispatch(self.ctx.request, self.ctx.response)


class WSCTXWrapper(CTXWrapper):
    def dispatch(self):
        return self.router.dispatch(self.ctx.websocket)


@contextmanager
def request_ctx(app, path):
    with _current_ctx(path) as ctx:
        ctx._pipeline_generic_storage = []
        ctx._pipeline_linear_storage = []
        ctx._pipeline_parallel_storage = []
        yield ReqCTXWrapper(ctx, app._router_http)


@contextmanager
def ws_ctx(app, path):
    with _ws_ctx(path) as ctx:
        ctx._pipeline_generic_storage = []
        ctx._pipeline_linear_storage = []
        ctx._pipeline_parallel_storage = []
        yield WSCTXWrapper(ctx, app._router_ws)


def linear_flows_are_equal(flow, ctx):
    try:
        for index, value in enumerate(flow):
            if ctx._pipeline_linear_storage[index] != value:
                return False
    except Exception:
        return False
    return True


def parallel_flows_are_equal(flow, ctx):
    return set(flow) == set(ctx._pipeline_parallel_storage)


@pytest.fixture(scope='module')
def app():
    app = App(__name__)
    app.pipeline = [Pipe1(), Pipe2(), Pipe3()]

    @app.route()
    def ok():
        return "ok"

    @app.route()
    def http_error():
        abort(422)

    @app.route()
    def error():
        raise Exception

    @app.route(pipeline=[ExcPipeOpen(), Pipe4()])
    def open_error():
        return ''

    @app.route(pipeline=[ExcPipeClose(), Pipe4()])
    def close_error():
        return ''

    @app.route(pipeline=[Pipe4()])
    def pipe4():
        return "4"

    @app.websocket()
    async def ws_ok():
        await websocket.send('ok')

    @app.websocket()
    def ws_error():
        raise Exception

    @app.websocket(pipeline=[ExcPipeOpen(), Pipe4()])
    def ws_open_error():
        return

    @app.websocket(pipeline=[ExcPipeClose(), Pipe4()])
    def ws_close_error():
        return

    @app.websocket(pipeline=[Pipe4()])
    def ws_pipe4():
        return

    @app.websocket(pipeline=[PipeSR1(), PipeSR2()])
    async def ws_inject():
        data = await websocket.receive()
        current._receive_storage.append(data)
        await websocket.send(data)

    mod = app.module(__name__, 'mod', url_prefix='mod')
    mod.pipeline = [Pipe5()]

    @mod.route()
    def pipe5():
        return "5"

    @mod.route(pipeline=[Pipe6()])
    def pipe6():
        return "6"

    @mod.websocket()
    def ws_pipe5():
        return

    @mod.websocket(pipeline=[Pipe6()])
    def ws_pipe6():
        return

    inj = app.module(__name__, 'inj', url_prefix='inj')
    inj.pipeline = [GlobalInjector(), ScopedInjector()]

    @inj.route(template='test.html')
    def injpipe():
        return {'posts': []}

    mg1 = app.module(__name__, 'mg1', url_prefix='mg1')
    mg2 = app.module(__name__, 'mg2', url_prefix='mg2')
    mg1.pipeline = [Pipe5()]
    mg2.pipeline = [Pipe6()]
    mg = app.module_group(mg1, mg2)

    @mg.route()
    async def pipe_mg():
        return "mg"

    mgc = mg.module(__name__, 'mgc', url_prefix='mgc')
    mgc.pipeline = [Pipe7()]

    @mgc.route()
    async def pipe_mgc():
        return "mgc"

    return app


@pytest.mark.asyncio
async def test_ok_flow(app):
    with request_ctx(app, '/ok') as ctx:
        parallel_flow = [
            'Pipe1.open', 'Pipe2.open_request', 'Pipe3.open',
            'Pipe3.close', 'Pipe2.close_request', 'Pipe1.close']
        linear_flow = [
            'Pipe1.pipe', 'Pipe2.pipe_request', 'Pipe3.pipe',
            'Pipe3.success', 'Pipe2.success', 'Pipe1.success']
        await ctx.dispatch()
        assert linear_flows_are_equal(linear_flow, ctx.ctx)
        assert parallel_flows_are_equal(parallel_flow, ctx.ctx)

    with ws_ctx(app, '/ws_ok') as ctx:
        parallel_flow = [
            'Pipe1.open', 'Pipe2.open_ws', 'Pipe3.open',
            'Pipe3.close', 'Pipe2.close_ws', 'Pipe1.close']
        linear_flow = [
            'Pipe1.pipe', 'Pipe2.pipe_ws', 'Pipe3.pipe',
            'Pipe3.success', 'Pipe2.success', 'Pipe1.success']
        await ctx.dispatch()
        assert linear_flows_are_equal(linear_flow, ctx.ctx)
        assert parallel_flows_are_equal(parallel_flow, ctx.ctx)


@pytest.mark.asyncio
async def test_httperror_flow(app):
    with request_ctx(app, '/http_error') as ctx:
        parallel_flow = [
            'Pipe1.open', 'Pipe2.open_request', 'Pipe3.open',
            'Pipe3.close', 'Pipe2.close_request', 'Pipe1.close']
        linear_flow = [
            'Pipe1.pipe', 'Pipe2.pipe_request', 'Pipe3.pipe',
            'Pipe3.success', 'Pipe2.success', 'Pipe1.success']
        try:
            await ctx.dispatch()
        except HTTP:
            pass
        assert linear_flows_are_equal(linear_flow, ctx.ctx)
        assert parallel_flows_are_equal(parallel_flow, ctx.ctx)


@pytest.mark.asyncio
async def test_error_flow(app):
    with request_ctx(app, '/error') as ctx:
        parallel_flow = [
            'Pipe1.open', 'Pipe2.open_request', 'Pipe3.open',
            'Pipe3.close', 'Pipe2.close_request', 'Pipe1.close']
        linear_flow = [
            'Pipe1.pipe', 'Pipe2.pipe_request', 'Pipe3.pipe',
            'Pipe3.failure', 'Pipe2.failure', 'Pipe1.failure']
        try:
            await ctx.dispatch()
        except Exception:
            pass
        assert linear_flows_are_equal(linear_flow, ctx.ctx)
        assert parallel_flows_are_equal(parallel_flow, ctx.ctx)

    with ws_ctx(app, '/ws_error') as ctx:
        parallel_flow = [
            'Pipe1.open', 'Pipe2.open_ws', 'Pipe3.open',
            'Pipe3.close', 'Pipe2.close_ws', 'Pipe1.close']
        linear_flow = [
            'Pipe1.pipe', 'Pipe2.pipe_ws', 'Pipe3.pipe',
            'Pipe3.failure', 'Pipe2.failure', 'Pipe1.failure']
        try:
            await ctx.dispatch()
        except Exception:
            pass
        assert linear_flows_are_equal(linear_flow, ctx.ctx)
        assert parallel_flows_are_equal(parallel_flow, ctx.ctx)


@pytest.mark.asyncio
async def test_open_error(app):
    with request_ctx(app, '/open_error') as ctx:
        parallel_flow = [
            'Pipe1.open', 'Pipe2.open_request', 'Pipe3.open', 'Pipe4.open']
        linear_flow = []
        try:
            await ctx.dispatch()
        except PipeException as e:
            assert isinstance(e.pipe, ExcPipeOpen)
        assert linear_flows_are_equal(linear_flow, ctx.ctx)
        assert parallel_flows_are_equal(parallel_flow, ctx.ctx)

    with ws_ctx(app, '/ws_open_error') as ctx:
        parallel_flow = [
            'Pipe1.open', 'Pipe2.open_ws', 'Pipe3.open', 'Pipe4.open']
        linear_flow = []
        try:
            await ctx.dispatch()
        except PipeException as e:
            assert isinstance(e.pipe, ExcPipeOpen)
        assert linear_flows_are_equal(linear_flow, ctx.ctx)
        assert parallel_flows_are_equal(parallel_flow, ctx.ctx)


@pytest.mark.asyncio
async def test_close_error(app):
    with request_ctx(app, '/close_error') as ctx:
        parallel_flow = [
            'Pipe1.open', 'Pipe2.open_request', 'Pipe3.open',
            'ExcPipeClose.open', 'Pipe4.open',
            'Pipe4.close', 'Pipe3.close', 'Pipe2.close_request', 'Pipe1.close']
        linear_flow = [
            'Pipe1.pipe', 'Pipe2.pipe_request', 'Pipe3.pipe',
            'ExcPipeClose.pipe', 'Pipe4.pipe',
            'Pipe4.success', 'ExcPipeClose.success', 'Pipe3.success',
            'Pipe2.success', 'Pipe1.success']
        try:
            await ctx.dispatch()
        except PipeException as e:
            assert isinstance(e.pipe, ExcPipeClose)
        assert linear_flows_are_equal(linear_flow, ctx.ctx)
        assert parallel_flows_are_equal(parallel_flow, ctx.ctx)

    with ws_ctx(app, '/ws_close_error') as ctx:
        parallel_flow = [
            'Pipe1.open', 'Pipe2.open_ws', 'Pipe3.open',
            'ExcPipeClose.open', 'Pipe4.open',
            'Pipe4.close', 'Pipe3.close', 'Pipe2.close_ws', 'Pipe1.close']
        linear_flow = [
            'Pipe1.pipe', 'Pipe2.pipe_ws', 'Pipe3.pipe',
            'ExcPipeClose.pipe', 'Pipe4.pipe',
            'Pipe4.success', 'ExcPipeClose.success', 'Pipe3.success',
            'Pipe2.success', 'Pipe1.success']
        try:
            await ctx.dispatch()
        except PipeException as e:
            assert isinstance(e.pipe, ExcPipeClose)
        assert linear_flows_are_equal(linear_flow, ctx.ctx)
        assert parallel_flows_are_equal(parallel_flow, ctx.ctx)


@pytest.mark.asyncio
async def test_flow_interrupt(app):
    with request_ctx(app, '/ok?skip=yes') as ctx:
        parallel_flow = [
            'Pipe1.open', 'Pipe2.open_request', 'Pipe3.open',
            'Pipe3.close', 'Pipe2.close_request', 'Pipe1.close']
        linear_flow = [
            'Pipe1.pipe', 'Pipe2.pipe_request',
            'Pipe2.success', 'Pipe1.success']
        await ctx.dispatch()
        assert linear_flows_are_equal(linear_flow, ctx.ctx)
        assert parallel_flows_are_equal(parallel_flow, ctx.ctx)

    with ws_ctx(app, '/ws_ok?skip=yes') as ctx:
        parallel_flow = [
            'Pipe1.open', 'Pipe2.open_ws', 'Pipe3.open',
            'Pipe3.close', 'Pipe2.close_ws', 'Pipe1.close']
        linear_flow = [
            'Pipe1.pipe', 'Pipe2.pipe_ws',
            'Pipe2.success', 'Pipe1.success']
        await ctx.dispatch()
        assert linear_flows_are_equal(linear_flow, ctx.ctx)
        assert parallel_flows_are_equal(parallel_flow, ctx.ctx)


@pytest.mark.asyncio
async def test_pipeline_composition(app):
    with request_ctx(app, '/pipe4') as ctx:
        parallel_flow = [
            'Pipe1.open', 'Pipe2.open_request', 'Pipe3.open', 'Pipe4.open',
            'Pipe4.close', 'Pipe3.close', 'Pipe2.close_request', 'Pipe1.close']
        linear_flow = [
            'Pipe1.pipe', 'Pipe2.pipe_request', 'Pipe3.pipe', 'Pipe4.pipe',
            'Pipe4.success', 'Pipe3.success', 'Pipe2.success', 'Pipe1.success']
        await ctx.dispatch()
        assert linear_flows_are_equal(linear_flow, ctx.ctx)
        assert parallel_flows_are_equal(parallel_flow, ctx.ctx)

    with ws_ctx(app, '/ws_pipe4') as ctx:
        parallel_flow = [
            'Pipe1.open', 'Pipe2.open_ws', 'Pipe3.open', 'Pipe4.open',
            'Pipe4.close', 'Pipe3.close', 'Pipe2.close_ws', 'Pipe1.close']
        linear_flow = [
            'Pipe1.pipe', 'Pipe2.pipe_ws', 'Pipe3.pipe', 'Pipe4.pipe',
            'Pipe4.success', 'Pipe3.success', 'Pipe2.success', 'Pipe1.success']
        await ctx.dispatch()
        assert linear_flows_are_equal(linear_flow, ctx.ctx)
        assert parallel_flows_are_equal(parallel_flow, ctx.ctx)


@pytest.mark.asyncio
async def test_module_pipeline(app):
    with request_ctx(app, '/mod/pipe5') as ctx:
        parallel_flow = [
            'Pipe1.open', 'Pipe2.open_request', 'Pipe3.open', 'Pipe5.open',
            'Pipe5.close', 'Pipe3.close', 'Pipe2.close_request', 'Pipe1.close']
        linear_flow = [
            'Pipe1.pipe', 'Pipe2.pipe_request', 'Pipe3.pipe', 'Pipe5.pipe',
            'Pipe5.success', 'Pipe3.success', 'Pipe2.success', 'Pipe1.success']
        await ctx.dispatch()
        assert linear_flows_are_equal(linear_flow, ctx.ctx)
        assert parallel_flows_are_equal(parallel_flow, ctx.ctx)

    with ws_ctx(app, '/mod/ws_pipe5') as ctx:
        parallel_flow = [
            'Pipe1.open', 'Pipe2.open_ws', 'Pipe3.open', 'Pipe5.open',
            'Pipe5.close', 'Pipe3.close', 'Pipe2.close_ws', 'Pipe1.close']
        linear_flow = [
            'Pipe1.pipe', 'Pipe2.pipe_ws', 'Pipe3.pipe', 'Pipe5.pipe',
            'Pipe5.success', 'Pipe3.success', 'Pipe2.success', 'Pipe1.success']
        await ctx.dispatch()
        assert linear_flows_are_equal(linear_flow, ctx.ctx)
        assert parallel_flows_are_equal(parallel_flow, ctx.ctx)


@pytest.mark.asyncio
async def test_module_pipeline_composition(app):
    with request_ctx(app, '/mod/pipe6') as ctx:
        parallel_flow = [
            'Pipe1.open', 'Pipe2.open_request', 'Pipe3.open', 'Pipe5.open',
            'Pipe6.open',
            'Pipe6.close', 'Pipe5.close', 'Pipe3.close', 'Pipe2.close_request',
            'Pipe1.close']
        linear_flow = [
            'Pipe1.pipe', 'Pipe2.pipe_request', 'Pipe3.pipe', 'Pipe5.pipe',
            'Pipe6.pipe',
            'Pipe6.success', 'Pipe5.success', 'Pipe3.success', 'Pipe2.success',
            'Pipe1.success']
        await ctx.dispatch()
        assert linear_flows_are_equal(linear_flow, ctx.ctx)
        assert parallel_flows_are_equal(parallel_flow, ctx.ctx)

    with ws_ctx(app, '/mod/ws_pipe6') as ctx:
        parallel_flow = [
            'Pipe1.open', 'Pipe2.open_ws', 'Pipe3.open', 'Pipe5.open',
            'Pipe6.open',
            'Pipe6.close', 'Pipe5.close', 'Pipe3.close', 'Pipe2.close_ws',
            'Pipe1.close']
        linear_flow = [
            'Pipe1.pipe', 'Pipe2.pipe_ws', 'Pipe3.pipe', 'Pipe5.pipe',
            'Pipe6.pipe',
            'Pipe6.success', 'Pipe5.success', 'Pipe3.success', 'Pipe2.success',
            'Pipe1.success']
        await ctx.dispatch()
        assert linear_flows_are_equal(linear_flow, ctx.ctx)
        assert parallel_flows_are_equal(parallel_flow, ctx.ctx)


@pytest.mark.asyncio
async def test_module_group_pipeline(app):
    with request_ctx(app, '/mg1/pipe_mg') as ctx:
        parallel_flow = [
            'Pipe1.open', 'Pipe2.open_request', 'Pipe3.open', 'Pipe5.open',
            'Pipe5.close', 'Pipe3.close', 'Pipe2.close_request', 'Pipe1.close']
        linear_flow = [
            'Pipe1.pipe', 'Pipe2.pipe_request', 'Pipe3.pipe', 'Pipe5.pipe',
            'Pipe5.success', 'Pipe3.success', 'Pipe2.success', 'Pipe1.success']
        await ctx.dispatch()
        assert linear_flows_are_equal(linear_flow, ctx.ctx)
        assert parallel_flows_are_equal(parallel_flow, ctx.ctx)

    with request_ctx(app, '/mg2/pipe_mg') as ctx:
        parallel_flow = [
            'Pipe1.open', 'Pipe2.open_request', 'Pipe3.open', 'Pipe6.open',
            'Pipe6.close', 'Pipe3.close', 'Pipe2.close_request', 'Pipe1.close']
        linear_flow = [
            'Pipe1.pipe', 'Pipe2.pipe_request', 'Pipe3.pipe', 'Pipe6.pipe',
            'Pipe6.success', 'Pipe3.success', 'Pipe2.success', 'Pipe1.success']
        await ctx.dispatch()
        assert linear_flows_are_equal(linear_flow, ctx.ctx)
        assert parallel_flows_are_equal(parallel_flow, ctx.ctx)


@pytest.mark.asyncio
async def test_module_group_pipeline_composition(app):
    with request_ctx(app, '/mg1/mgc/pipe_mgc') as ctx:
        parallel_flow = [
            'Pipe1.open', 'Pipe2.open_request', 'Pipe3.open', 'Pipe5.open',
            'Pipe7.open',
            'Pipe7.close', 'Pipe5.close', 'Pipe3.close', 'Pipe2.close_request',
            'Pipe1.close']
        linear_flow = [
            'Pipe1.pipe', 'Pipe2.pipe_request', 'Pipe3.pipe', 'Pipe5.pipe',
            'Pipe7.pipe',
            'Pipe7.success', 'Pipe5.success', 'Pipe3.success', 'Pipe2.success',
            'Pipe1.success']
        await ctx.dispatch()
        assert linear_flows_are_equal(linear_flow, ctx.ctx)
        assert parallel_flows_are_equal(parallel_flow, ctx.ctx)

    with request_ctx(app, '/mg2/mgc/pipe_mgc') as ctx:
        parallel_flow = [
            'Pipe1.open', 'Pipe2.open_request', 'Pipe3.open', 'Pipe6.open',
            'Pipe7.open',
            'Pipe7.close', 'Pipe6.close', 'Pipe3.close', 'Pipe2.close_request',
            'Pipe1.close']
        linear_flow = [
            'Pipe1.pipe', 'Pipe2.pipe_request', 'Pipe3.pipe', 'Pipe6.pipe',
            'Pipe7.pipe',
            'Pipe7.success', 'Pipe6.success', 'Pipe3.success', 'Pipe2.success',
            'Pipe1.success']
        await ctx.dispatch()
        assert linear_flows_are_equal(linear_flow, ctx.ctx)
        assert parallel_flows_are_equal(parallel_flow, ctx.ctx)


@pytest.mark.asyncio
async def test_receive_send_flow(app):
    send_storage_key = {
        "str": "text",
        "bytes": "bytes"
    }[_json_type]
    with ws_ctx(app, '/ws_inject') as ctx:
        parallel_flow = [
            'Pipe1.open', 'Pipe2.open_ws', 'Pipe3.open',
            'PipeSR1.open_ws', 'PipeSR2.open_ws',
            'PipeSR2.close_ws', 'PipeSR1.close_ws',
            'Pipe3.close', 'Pipe2.close_ws', 'Pipe1.close']
        linear_flow = [
            'Pipe1.pipe', 'Pipe2.pipe_ws', 'Pipe3.pipe',
            'PipeSR1.pipe_ws', 'PipeSR2.pipe_ws',
            'PipeSR2.success', 'PipeSR1.success',
            'Pipe3.success', 'Pipe2.success', 'Pipe1.success']
        await ctx.dispatch()
        assert linear_flows_are_equal(linear_flow, ctx.ctx)
        assert parallel_flows_are_equal(parallel_flow, ctx.ctx)

        assert ctx.ctx._receive_storage[-1] == {
            'foo': 'bar',
            'pipe1r': 'receive_inject', 'pipe2r': 'receive_inject'
        }
        assert json_load(ctx.ctx._send_storage[-1][send_storage_key]) == {
            'foo': 'bar',
            'pipe1r': 'receive_inject', 'pipe2r': 'receive_inject',
            'pipe1s': 'send_inject', 'pipe2s': 'send_inject'
        }


@pytest.mark.asyncio
async def test_injectors(app):
    with request_ctx(app, '/inj/injpipe') as ctx:
        current.app = app

        await ctx.dispatch()
        env = ctx.ctx._pipeline_generic_storage[0]

        assert env['posts'] == []
        assert env['foo'] == "bar"
        assert env['bar'] == "baz"
        assert env['staticm']("test") == "test"
        assert env['boundm']("test") == ("bar", "test")
        assert env['prop'] == "baz"

        env = env['scoped']
        assert env.foo == "bar"
        assert env.bar == "baz"
        assert env.staticm("test") == "test"
        assert env.boundm("test") == ("bar", "test")
        assert env.prop == "baz"
