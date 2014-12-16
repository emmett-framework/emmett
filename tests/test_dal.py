# -*- coding: utf-8 -*-
"""
    tests.dal
    ---------

    pyDAL implementation over weppy.

    :copyright: (c) 2014 by Giovanni Barillari
    :license: BSD, see LICENSE for more details.
"""

from weppy import App
from weppy.dal import DAL, ModelsDAL, Field
from weppy.dal.objects import Table
from weppy.dal.models import Model, AuthModel
from weppy.validators import IS_NOT_EMPTY


class TModel(Model):
    tablename = "test"

    fields = [
        Field("a", "string"),
        Field("invisible")
    ]

    validators = {
        "a": IS_NOT_EMPTY()
    }

    visibility = {
        "invisible": (False, False)
    }

    labels = {
        "a": "A label"
    }

    comments = {
        "a": "A comment"
    }


class TestDAL(object):
    def _init_db(self):
        self.app = App(__name__)
        self.db = ModelsDAL(self.app)

    def _init_tables(self):
        self.db.define_datamodels([TModel])

    def test_db_instance(self):
        self._init_db()
        assert isinstance(self.db, DAL)

    def test_table_definition(self):
        self._init_tables()
        assert isinstance(self.db.TModel, Table)
        assert isinstance(self.db[TModel.tablename], Table)

    def test_fields(self):
        assert isinstance(self.db.TModel.a, Field)
        assert self.db.TModel.a.type == "string"

    def test_validators(self):
        assert isinstance(self.db.TModel.a.requires, IS_NOT_EMPTY)

    def test_visibility(self):
        assert self.db.TModel.a.readable is True
        assert self.db.TModel.a.writable is True
        assert self.db.TModel.invisible.readable is False
        assert self.db.TModel.invisible.writable is False

    def test_labels(self):
        assert self.db.TModel.a.lable == "A label"

    def test_comments(self):
        assert self.db.TModel.a.comment == "A comment"

    def test_updates(self):
        pass

    def test_representation(self):
        pass

    def test_widgets(self):
        pass

    def test_set_helper(self):
        pass

    def test_computations(self):
        pass

    def test_callbacks(self):
        pass

    def test_virtualfields(self):
        pass

    def test_fieldmethods(self):
        pass

    def test_modelmethods(self):
        pass
