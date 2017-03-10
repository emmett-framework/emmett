# -*- coding: utf-8 -*-
"""
    tests.pipeline
    --------------

    Test weppy pipeline

    :copyright: (c) 2014-2016 by Giovanni Barillari
    :license: BSD, see LICENSE for more details.
"""

import pytest
from weppy import App, request, abort
from weppy.globals import current
from weppy.http import HTTP
from weppy.pipeline import Pipe
from weppy.testing.env import EnvironBuilder


def flows_are_equal(p1, p2):
    try:
        for index, value in enumerate(p1):
            if p2[index] != value:
                return False
    except:
        return False
    return True


class FlowStorePipe(Pipe):
    @property
    def storage(self):
        return current._pipeline_storage

    def store_status(self, status):
        self.storage.append(self.__class__.__name__ + "." + status)

    def open(self):
        self.store_status('open')

    def pipe(self, next_pipe, **kwargs):
        self.store_status('pipe')
        return next_pipe(**kwargs)

    def on_pipe_success(self):
        self.store_status('success')

    def on_pipe_failure(self):
        self.store_status('failure')

    def close(self):
        self.store_status('close')


class Pipe1(FlowStorePipe):
    pass


class Pipe2(FlowStorePipe):
    def pipe(self, next_pipe, **kwargs):
        self.store_status('pipe')
        if request.query_params.skip:
            return "block"
        return next_pipe(**kwargs)


class Pipe3(FlowStorePipe):
    pass


class Pipe4(FlowStorePipe):
    pass


class Pipe5(FlowStorePipe):
    pass


class Pipe6(FlowStorePipe):
    pass


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


def init_current(url):
    builder = EnvironBuilder(url)
    current.initialize(builder.get_environ())
    current._pipeline_storage = []
    return builder


def test_ok_flow(app):
    init_current('/ok')
    correct_flow = [
        'Pipe1.open', 'Pipe2.open', 'Pipe3.open',
        'Pipe1.pipe', 'Pipe2.pipe', 'Pipe3.pipe',
        'Pipe3.success', 'Pipe2.success', 'Pipe1.success',
        'Pipe3.close', 'Pipe2.close', 'Pipe1.close']
    app.route.dispatch()
    assert flows_are_equal(correct_flow, current._pipeline_storage)


def test_httperror_flow(app):
    init_current('/http_error')
    correct_flow = [
        'Pipe1.open', 'Pipe2.open', 'Pipe3.open',
        'Pipe1.pipe', 'Pipe2.pipe', 'Pipe3.pipe',
        'Pipe3.success', 'Pipe2.success', 'Pipe1.success',
        'Pipe3.close', 'Pipe2.close', 'Pipe1.close']
    try:
        app.route.dispatch()
    except HTTP:
        pass
    assert flows_are_equal(correct_flow, current._pipeline_storage)


def test_error_flow(app):
    init_current('/error')
    correct_flow = [
        'Pipe1.open', 'Pipe2.open', 'Pipe3.open',
        'Pipe1.pipe', 'Pipe2.pipe', 'Pipe3.pipe',
        'Pipe3.failure', 'Pipe2.failure', 'Pipe1.failure',
        'Pipe3.close', 'Pipe2.close', 'Pipe1.close']
    try:
        app.route.dispatch()
    except Exception:
        pass
    assert flows_are_equal(correct_flow, current._pipeline_storage)


def test_flow_interrupt(app):
    init_current('/ok?skip=yes')
    correct_flow = [
        'Pipe1.open', 'Pipe2.open', 'Pipe3.open',
        'Pipe1.pipe', 'Pipe2.pipe',
        'Pipe2.success', 'Pipe1.success',
        'Pipe3.close', 'Pipe2.close', 'Pipe1.close']
    app.route.dispatch()
    assert flows_are_equal(correct_flow, current._pipeline_storage)


def test_pipeline_composition(app):
    init_current('/pipe4')
    correct_flow = [
        'Pipe1.open', 'Pipe2.open', 'Pipe3.open', 'Pipe4.open',
        'Pipe1.pipe', 'Pipe2.pipe', 'Pipe3.pipe', 'Pipe4.pipe',
        'Pipe4.success', 'Pipe3.success', 'Pipe2.success', 'Pipe1.success',
        'Pipe4.close', 'Pipe3.close', 'Pipe2.close', 'Pipe1.close']
    app.route.dispatch()
    assert flows_are_equal(correct_flow, current._pipeline_storage)


def test_module_pipeline(app):
    init_current('/mod/pipe5')
    correct_flow = [
        'Pipe1.open', 'Pipe2.open', 'Pipe3.open', 'Pipe5.open',
        'Pipe1.pipe', 'Pipe2.pipe', 'Pipe3.pipe', 'Pipe5.pipe',
        'Pipe5.success', 'Pipe3.success', 'Pipe2.success', 'Pipe1.success',
        'Pipe5.close', 'Pipe3.close', 'Pipe2.close', 'Pipe1.close']
    app.route.dispatch()
    assert flows_are_equal(correct_flow, current._pipeline_storage)


def test_module_pipeline_composition(app):
    init_current('/mod/pipe6')
    correct_flow = [
        'Pipe1.open', 'Pipe2.open', 'Pipe3.open', 'Pipe5.open', 'Pipe6.open',
        'Pipe1.pipe', 'Pipe2.pipe', 'Pipe3.pipe', 'Pipe5.pipe', 'Pipe6.pipe',
        'Pipe6.success', 'Pipe5.success',
        'Pipe3.success', 'Pipe2.success', 'Pipe1.success',
        'Pipe6.close', 'Pipe5.close',
        'Pipe3.close', 'Pipe2.close', 'Pipe1.close']
    app.route.dispatch()
    assert flows_are_equal(correct_flow, current._pipeline_storage)
