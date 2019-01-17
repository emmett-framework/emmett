# -*- coding: utf-8 -*-
"""
    tests.pipeline
    --------------

    Test weppy pipeline

    :copyright: (c) 2014-2016 by Giovanni Barillari
    :license: BSD, see LICENSE for more details.
"""

import pytest

from contextlib import contextmanager

from helpers import current_ctx as _current_ctx
from weppy import App, request, abort
from weppy.ctx import current
from weppy.http import HTTP
from weppy.pipeline import Pipe


class FlowStorePipe(Pipe):
    @property
    def storage(self):
        return current._pipeline_storage

    def store_status(self, status):
        self.storage.append(self.__class__.__name__ + "." + status)

    async def open(self):
        self.store_status('open')

    async def pipe(self, next_pipe, **kwargs):
        self.store_status('pipe')
        return await next_pipe(**kwargs)

    async def on_pipe_success(self):
        self.store_status('success')

    async def on_pipe_failure(self):
        self.store_status('failure')

    async def close(self):
        self.store_status('close')


class Pipe1(FlowStorePipe):
    pass


class Pipe2(FlowStorePipe):
    async def pipe(self, next_pipe, **kwargs):
        self.store_status('pipe')
        if request.query_params.skip:
            return "block"
        return await next_pipe(**kwargs)


class Pipe3(FlowStorePipe):
    pass


class Pipe4(FlowStorePipe):
    pass


class Pipe5(FlowStorePipe):
    pass


class Pipe6(FlowStorePipe):
    pass


@contextmanager
def current_ctx(path):
    with _current_ctx(path) as ctx:
        ctx._pipeline_storage = []
        yield ctx


def flows_are_equal(p1, p2):
    try:
        for index, value in enumerate(p1):
            if p2[index] != value:
                return False
    except Exception:
        return False
    return True


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

    @app.route(pipeline=[Pipe4()])
    def pipe4():
        return "4"

    mod = app.module(__name__, 'mod', url_prefix='mod')
    mod.pipeline = [Pipe5()]

    @mod.route()
    def pipe5():
        return "5"

    @mod.route(pipeline=[Pipe6()])
    def pipe6():
        return "6"

    return app


@pytest.mark.asyncio
async def test_ok_flow(app):
    with current_ctx('/ok') as ctx:
        correct_flow = [
            'Pipe1.open', 'Pipe2.open', 'Pipe3.open',
            'Pipe1.pipe', 'Pipe2.pipe', 'Pipe3.pipe',
            'Pipe3.success', 'Pipe2.success', 'Pipe1.success',
            'Pipe3.close', 'Pipe2.close', 'Pipe1.close']
        await app.route.dispatch()
        assert flows_are_equal(correct_flow, ctx._pipeline_storage)


@pytest.mark.asyncio
async def test_httperror_flow(app):
    with current_ctx('/http_error') as ctx:
        correct_flow = [
            'Pipe1.open', 'Pipe2.open', 'Pipe3.open',
            'Pipe1.pipe', 'Pipe2.pipe', 'Pipe3.pipe',
            'Pipe3.success', 'Pipe2.success', 'Pipe1.success',
            'Pipe3.close', 'Pipe2.close', 'Pipe1.close']
        try:
            await app.route.dispatch()
        except HTTP:
            pass
        assert flows_are_equal(correct_flow, ctx._pipeline_storage)


@pytest.mark.asyncio
async def test_error_flow(app):
    with current_ctx('/error') as ctx:
        correct_flow = [
            'Pipe1.open', 'Pipe2.open', 'Pipe3.open',
            'Pipe1.pipe', 'Pipe2.pipe', 'Pipe3.pipe',
            'Pipe3.failure', 'Pipe2.failure', 'Pipe1.failure',
            'Pipe3.close', 'Pipe2.close', 'Pipe1.close']
        try:
            await app.route.dispatch()
        except Exception:
            pass
        assert flows_are_equal(correct_flow, ctx._pipeline_storage)


@pytest.mark.asyncio
async def test_flow_interrupt(app):
    with current_ctx('/ok?skip=yes') as ctx:
        correct_flow = [
            'Pipe1.open', 'Pipe2.open', 'Pipe3.open',
            'Pipe1.pipe', 'Pipe2.pipe',
            'Pipe2.success', 'Pipe1.success',
            'Pipe3.close', 'Pipe2.close', 'Pipe1.close']
        await app.route.dispatch()
        assert flows_are_equal(correct_flow, ctx._pipeline_storage)


@pytest.mark.asyncio
async def test_pipeline_composition(app):
    with current_ctx('/pipe4') as ctx:
        correct_flow = [
            'Pipe1.open', 'Pipe2.open', 'Pipe3.open', 'Pipe4.open',
            'Pipe1.pipe', 'Pipe2.pipe', 'Pipe3.pipe', 'Pipe4.pipe',
            'Pipe4.success', 'Pipe3.success', 'Pipe2.success', 'Pipe1.success',
            'Pipe4.close', 'Pipe3.close', 'Pipe2.close', 'Pipe1.close']
        await app.route.dispatch()
        assert flows_are_equal(correct_flow, ctx._pipeline_storage)


@pytest.mark.asyncio
async def test_module_pipeline(app):
    with current_ctx('/mod/pipe5') as ctx:
        correct_flow = [
            'Pipe1.open', 'Pipe2.open', 'Pipe3.open', 'Pipe5.open',
            'Pipe1.pipe', 'Pipe2.pipe', 'Pipe3.pipe', 'Pipe5.pipe',
            'Pipe5.success', 'Pipe3.success', 'Pipe2.success', 'Pipe1.success',
            'Pipe5.close', 'Pipe3.close', 'Pipe2.close', 'Pipe1.close']
        await app.route.dispatch()
        assert flows_are_equal(correct_flow, ctx._pipeline_storage)


@pytest.mark.asyncio
async def test_module_pipeline_composition(app):
    with current_ctx('/mod/pipe6') as ctx:
        correct_flow = [
            'Pipe1.open', 'Pipe2.open', 'Pipe3.open', 'Pipe5.open',
            'Pipe6.open',
            'Pipe1.pipe', 'Pipe2.pipe', 'Pipe3.pipe', 'Pipe5.pipe',
            'Pipe6.pipe',
            'Pipe6.success', 'Pipe5.success', 'Pipe3.success', 'Pipe2.success',
            'Pipe1.success',
            'Pipe6.close', 'Pipe5.close', 'Pipe3.close', 'Pipe2.close',
            'Pipe1.close']
        await app.route.dispatch()
        assert flows_are_equal(correct_flow, ctx._pipeline_storage)
