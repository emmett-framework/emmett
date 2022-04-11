# -*- coding: utf-8 -*-
"""
    tests.orm_pks
    -------------

    Test ORM primary keys hendling
"""

import os
import pytest

from uuid import uuid4

from emmett import App, sdict
from emmett.orm import Database, Model, Field, belongs_to, has_many
from emmett.orm.errors import SaveException
from emmett.orm.helpers import RowReferenceMixin
from emmett.orm.migrations.utils import generate_runtime_migration

require_postgres = pytest.mark.skipif(
    not os.environ.get("POSTGRES_URI"), reason="No postgres database"
)


class Standard(Model):
    foo = Field.string()
    bar = Field.string()


class CustomType(Model):
    id = Field.string()
    foo = Field.string()
    bar = Field.string()


class CustomName(Model):
    primary_keys = ["foo"]
    foo = Field.string()
    bar = Field.string()


class CustomMulti(Model):
    primary_keys = ["foo", "bar"]
    foo = Field.string()
    bar = Field.string()
    baz = Field.string()


class SourceCustom(Model):
    has_many("dest_custom_customs", "dest_custom_multis")

    id = Field.string(default=lambda: uuid4().hex)
    foo = Field.string()


class SourceMulti(Model):
    primary_keys = ["foo", "bar"]

    has_many("dest_multi_customs", "dest_multi_multis")

    foo = Field.string(default=lambda: uuid4().hex)
    bar = Field.string(default=lambda: uuid4().hex)
    baz = Field.string()


class DestCustomCustom(Model):
    belongs_to("source_custom")

    id = Field.string(default=lambda: uuid4().hex)
    foo = Field.string()


class DestCustomMulti(Model):
    primary_keys = ["foo", "bar"]

    belongs_to("source_custom")

    foo = Field.string(default=lambda: uuid4().hex)
    bar = Field.string(default=lambda: uuid4().hex)
    baz = Field.string()


class DestMultiCustom(Model):
    belongs_to("source_multi")

    id = Field.string(default=lambda: uuid4().hex)
    foo = Field.string()


class DestMultiMulti(Model):
    primary_keys = ["foo", "bar"]

    belongs_to("source_multi")

    foo = Field.string(default=lambda: uuid4().hex)
    bar = Field.string(default=lambda: uuid4().hex)
    baz = Field.string()


class DoctorCustom(Model):
    has_many(
        {"appointments": "AppointmentCustom"},
        {"patients": {"via": "appointments.patient_custom"}},
        {"symptoms_to_treat": {"via": "patients.symptoms"}}
    )

    id = Field.string(default=lambda: uuid4().hex)
    name = Field.string()


class DoctorMulti(Model):
    primary_keys = ["foo", "bar"]

    has_many(
        {"appointments": "AppointmentMulti"},
        {"patients": {"via": "appointments.patient_multi"}},
        {"symptoms_to_treat": {"via": "patients.symptoms"}}
    )

    foo = Field.string(default=lambda: uuid4().hex)
    bar = Field.string(default=lambda: uuid4().hex)
    name = Field.string()


class PatientCustom(Model):
    primary_keys = ["code"]

    has_many(
        {"appointments": "AppointmentCustom"},
        {"symptoms": "SymptomCustom.patient"},
        {"doctors": {"via": "appointments.doctor_custom"}}
    )

    code = Field.string(default=lambda: uuid4().hex)
    name = Field.string()


class PatientMulti(Model):
    primary_keys = ["foo", "bar"]

    has_many(
        {"appointments": "AppointmentMulti"},
        {"symptoms": "SymptomMulti.patient"},
        {"doctors": {"via": "appointments.doctor_multi"}}
    )

    foo = Field.string(default=lambda: uuid4().hex)
    bar = Field.string(default=lambda: uuid4().hex)
    name = Field.string()


class SymptomCustom(Model):
    belongs_to({"patient": "PatientCustom"})

    id = Field.string(default=lambda: uuid4().hex)
    name = Field.string()


class SymptomMulti(Model):
    primary_keys = ["foo", "bar"]

    belongs_to({"patient": "PatientMulti"})

    foo = Field.string(default=lambda: uuid4().hex)
    bar = Field.string(default=lambda: uuid4().hex)
    name = Field.string()


class AppointmentCustom(Model):
    primary_keys = ["code"]

    belongs_to("patient_custom", "doctor_custom")

    code = Field.string(default=lambda: uuid4().hex)
    name = Field.string()


class AppointmentMulti(Model):
    primary_keys = ["foo", "bar"]

    belongs_to("patient_multi", "doctor_multi")

    foo = Field.string(default=lambda: uuid4().hex)
    bar = Field.string(default=lambda: uuid4().hex)
    name = Field.string()


@pytest.fixture(scope='module')
def _db():
    app = App(__name__)
    db = Database(
        app,
        config=sdict(
            uri=f'sqlite://{uuid4().hex}.db',
            auto_connect=True
        )
    )
    db.define_models(
        Standard,
        CustomType,
        CustomName,
        CustomMulti
    )
    return db


@pytest.fixture(scope='module')
def _pgs():
    app = App(__name__)
    db = Database(
        app,
        config=sdict(
            uri=f"postgres://{os.environ.get('POSTGRES_URI')}",
            auto_connect=True
        )
    )
    db.define_models(
        SourceCustom,
        SourceMulti,
        DestCustomCustom,
        DestCustomMulti,
        DestMultiCustom,
        DestMultiMulti,
        DoctorCustom,
        PatientCustom,
        AppointmentCustom,
        DoctorMulti,
        PatientMulti,
        AppointmentMulti,
        SymptomCustom,
        SymptomMulti
    )
    return db


@pytest.fixture(scope='function')
def db(_db):
    migration = generate_runtime_migration(_db)
    migration.up()
    yield _db
    migration.down()


@pytest.fixture(scope='function')
def pgs(_pgs):
    migration = generate_runtime_migration(_pgs)
    migration.up()
    yield _pgs
    migration.down()


def test_insert(db):
    res = db.Standard.insert(foo="test1", bar="test2")
    assert isinstance(res, int)
    assert res.id
    assert res.foo == "test1"
    assert res.bar == "test2"

    res = db.CustomType.insert(id="test1", foo="test2", bar="test3")
    assert isinstance(res, str)
    assert res.id == "test1"
    assert res.foo == "test2"
    assert res.bar == "test3"

    res = db.CustomName.insert(foo="test1", bar="test2")
    assert isinstance(res, str)
    assert not res.id
    assert res.foo == "test1"
    assert res.bar == "test2"

    res = db.CustomMulti.insert(foo="test1", bar="test2", baz="test3")
    assert isinstance(res, tuple)
    assert not res.id
    assert res.foo == "test1"
    assert res.bar == "test2"
    assert res.baz == "test3"


def test_save_insert(db):
    row = Standard.new(foo="test1", bar="test2")
    done = row.save()
    assert done
    assert row._concrete
    assert row.id
    assert type(row.id) == int

    row = CustomType.new(id="test1", foo="test2", bar="test3")
    done = row.save()
    assert done
    assert row._concrete
    assert row.id == "test1"

    row = CustomName.new(foo="test1", bar="test2")
    done = row.save()
    assert done
    assert row._concrete
    assert "id" not in row
    assert row.foo == "test1"

    row = CustomMulti.new(foo="test1", bar="test2", baz="test3")
    done = row.save()
    assert done
    assert row._concrete
    assert "id" not in row
    assert row.foo == "test1"
    assert row.bar == "test2"
    assert row.baz == "test3"


def test_save_update(db):
    row = Standard.new(foo="test1", bar="test2")
    row.save()
    row.bar = "test2a"
    done = row.save()
    assert done
    assert row._concrete
    assert row.bar == "test2a"
    row.id = 123
    done = row.save()
    assert not done
    with pytest.raises(SaveException):
        row.save(raise_on_error=True)

    row = CustomType.new(id="test1", foo="test2", bar="test3")
    row.save()
    row.bar = "test2a"
    done = row.save()
    assert done
    assert row._concrete
    assert row.bar == "test2a"
    row.id = "test1a"
    done = row.save()
    assert not done
    with pytest.raises(SaveException):
        row.save(raise_on_error=True)

    row = CustomName.new(foo="test1", bar="test2")
    row.save()
    row.bar = "test2a"
    done = row.save()
    assert done
    assert row._concrete
    assert row.bar == "test2a"
    row.foo = "test1a"
    done = row.save()
    assert not done
    with pytest.raises(SaveException):
        row.save(raise_on_error=True)

    row = CustomMulti.new(foo="test1", bar="test2", baz="test3")
    row.save()
    row.baz = "test3a"
    done = row.save()
    assert done
    assert row._concrete
    assert row.baz == "test3a"
    row.foo = "test1a"
    done = row.save()
    assert not done
    with pytest.raises(SaveException):
        row.save(raise_on_error=True)


def test_destroy_delete(db):
    row = Standard.new(foo="test1", bar="test2")
    row.save()
    done = row.destroy()
    assert done
    assert not row._concrete
    assert row.id is None
    assert row.foo == "test1"

    row = CustomType.new(id="test1", foo="test2", bar="test3")
    row.save()
    done = row.destroy()
    assert done
    assert not row._concrete
    assert row.id is None
    assert row.foo == "test2"

    row = CustomName.new(foo="test1", bar="test2")
    row.save()
    done = row.destroy()
    assert done
    assert not row._concrete
    assert row.foo is None
    assert row.bar == "test2"

    row = CustomMulti.new(foo="test1", bar="test2", baz="test3")
    row.save()
    done = row.destroy()
    assert done
    assert not row._concrete
    assert row.foo is None
    assert row.bar is None
    assert row.baz == "test3"


@require_postgres
def test_relations(pgs):
    sc1 = SourceCustom.new(foo="test1")
    sc1.save()
    sc2 = SourceCustom.new(foo="test2")
    sc2.save()
    sm1 = SourceMulti.new(baz="test1")
    sm1.save()
    sm2 = SourceMulti.new(baz="test2")
    sm2.save()

    #: new
    dcc1 = sc1.dest_custom_customs.new(foo="test")
    assert dcc1.source_custom == sc1.id
    assert isinstance(dcc1.source_custom, str)

    dcm1 = sc1.dest_custom_multis.new(baz="test")
    assert dcm1.source_custom == sc1.id
    assert isinstance(dcc1.source_custom, str)

    dmc1 = sm1.dest_multi_customs.new(foo="test")
    assert dmc1.source_multi_foo == sm1.foo
    assert dmc1.source_multi_bar == sm1.bar

    dmm1 = sm1.dest_multi_multis.new(baz="test")
    assert dmm1.source_multi_foo == sm1.foo
    assert dmm1.source_multi_bar == sm1.bar

    #: create
    dcc1 = sc1.dest_custom_customs.create(foo="test")
    assert isinstance(dcc1.id, str)
    row = sc1.dest_custom_customs().first()
    assert row.foo == "test"
    rc = DestCustomCustom.get(row.id)
    assert rc.foo == row.foo
    assert isinstance(rc.source_custom, str)

    dcm1 = sc1.dest_custom_multis.create(baz="test")
    assert isinstance(dcm1.id, tuple)
    row = sc1.dest_custom_multis().first()
    assert row.baz == "test"
    rc = DestCustomMulti.get(row.foo, row.bar)
    assert rc.foo == row.foo
    assert rc.bar == row.bar
    assert isinstance(rc.source_custom, str)
    rc = DestCustomMulti.get(foo=row.foo, bar=row.bar)
    assert rc.foo == row.foo
    assert rc.bar == row.bar
    assert isinstance(rc.source_custom, str)
    rc = DestCustomMulti.get((row.foo, row.bar))
    assert rc.foo == row.foo
    assert rc.bar == row.bar
    assert isinstance(rc.source_custom, str)
    rc = DestCustomMulti.get({"foo": row.foo, "bar": row.bar})
    assert rc.foo == row.foo
    assert rc.bar == row.bar
    assert isinstance(rc.source_custom, str)

    dmc1 = sm1.dest_multi_customs.create(foo="test")
    assert isinstance(dmc1.id, str)
    row = sm1.dest_multi_customs().first()
    assert row.foo == "test"
    rc = DestMultiCustom.get(row.id)
    assert rc.foo == row.foo
    assert isinstance(rc.source_multi, tuple)
    assert rc.source_multi.foo == rc.source_multi_foo
    assert rc.source_multi.bar == rc.source_multi_bar
    assert rc.source_multi.baz == "test1"

    dmm1 = sm1.dest_multi_multis.create(baz="test")
    assert isinstance(dmm1.id, tuple)
    row = sm1.dest_multi_multis().first()
    assert row.baz == "test"
    rc = DestMultiMulti.get(row.foo, row.bar)
    assert rc.foo == row.foo
    assert rc.bar == row.bar
    assert isinstance(rc.source_multi, tuple)
    assert rc.source_multi.foo == rc.source_multi_foo
    assert rc.source_multi.bar == rc.source_multi_bar
    assert rc.source_multi.baz == "test1"
    rc = DestMultiMulti.get(foo=row.foo, bar=row.bar)
    assert rc.foo == row.foo
    assert rc.bar == row.bar
    assert isinstance(rc.source_multi, tuple)
    assert rc.source_multi.foo == rc.source_multi_foo
    assert rc.source_multi.bar == rc.source_multi_bar
    assert rc.source_multi.baz == "test1"
    rc = DestMultiMulti.get((row.foo, row.bar))
    assert rc.foo == row.foo
    assert rc.bar == row.bar
    assert isinstance(rc.source_multi, tuple)
    assert rc.source_multi.foo == rc.source_multi_foo
    assert rc.source_multi.bar == rc.source_multi_bar
    assert rc.source_multi.baz == "test1"
    rc = DestMultiMulti.get({"foo": row.foo, "bar": row.bar})
    assert rc.foo == row.foo
    assert rc.bar == row.bar
    assert isinstance(rc.source_multi, tuple)
    assert rc.source_multi.foo == rc.source_multi_foo
    assert rc.source_multi.bar == rc.source_multi_bar
    assert rc.source_multi.baz == "test1"

    #: add, remove
    dcc1 = DestCustomCustom.first()
    sc2.dest_custom_customs.add(dcc1)
    assert sc1.dest_custom_customs.count() == 0
    assert sc2.dest_custom_customs.count() == 1
    assert dcc1.source_custom.id == sc2.id
    sc2.dest_custom_customs.remove(dcc1)
    assert sc1.dest_custom_customs.count() == 0
    assert sc2.dest_custom_customs.count() == 0
    assert dcc1.source_custom is None
    assert not dcc1.is_valid

    dcm1 = DestCustomMulti.first()
    sc2.dest_custom_multis.add(dcm1)
    assert sc1.dest_custom_multis.count() == 0
    assert sc2.dest_custom_multis.count() == 1
    assert dcm1.source_custom.id == sc2.id
    sc2.dest_custom_multis.remove(dcm1)
    assert sc1.dest_custom_multis.count() == 0
    assert sc2.dest_custom_multis.count() == 0
    assert dcm1.source_custom is None
    assert not dcm1.is_valid

    dmc1 = DestMultiCustom.first()
    sm2.dest_multi_customs.add(dmc1)
    assert sm1.dest_multi_customs.count() == 0
    assert sm2.dest_multi_customs.count() == 1
    assert dmc1.source_multi.foo == sm2.foo
    assert dmc1.source_multi.bar == sm2.bar
    sm2.dest_multi_customs.remove(dmc1)
    assert sm1.dest_multi_customs.count() == 0
    assert sm2.dest_multi_customs.count() == 0
    assert dmc1.source_multi is None
    assert not dmc1.is_valid

    dmm1 = DestMultiMulti.first()
    sm2.dest_multi_multis.add(dmm1)
    assert sm1.dest_multi_multis.count() == 0
    assert sm2.dest_multi_multis.count() == 1
    assert dmm1.source_multi.foo == sm2.foo
    assert dmm1.source_multi.bar == sm2.bar
    sm2.dest_multi_multis.remove(dmm1)
    assert sm1.dest_multi_multis.count() == 0
    assert sm2.dest_multi_multis.count() == 0
    assert dmm1.source_multi is None
    assert not dmm1.is_valid


@require_postgres
def test_via_relations(pgs):
    doc1 = DoctorCustom.new(name="test1")
    doc1.save()
    doc2 = DoctorCustom.new(name="test2")
    doc2.save()
    pat1 = PatientCustom.new(name="test1")
    pat1.save()
    pat1.symptoms.create(name="test1a")
    pat2 = PatientCustom.new(name="test2")
    pat2.save()
    pat2.symptoms.create(name="test2a")
    pat2.symptoms.create(name="test2b")
    doc3 = DoctorMulti.new(name="test1")
    doc3.save()
    doc4 = DoctorMulti.new(name="test2")
    doc4.save()
    pat3 = PatientMulti.new(name="test1")
    pat3.save()
    pat3.symptoms.create(name="test3a")
    pat3.symptoms.create(name="test3b")
    pat4 = PatientMulti.new(name="test2")
    pat4.save()
    pat4.symptoms.create(name="test4a")

    #: add, remove
    doc1.patients.add(pat1, name="test1")
    doc2.patients.add(pat2, name="test2")
    assert doc1.patients.count() == 1
    assert doc1.patients.count() == 1
    assert doc1.symptoms_to_treat.count() == 1
    assert doc2.symptoms_to_treat.count() == 2
    doc1.patients.add(pat2, name="test2")
    assert doc1.patients.count() == 2
    assert doc2.patients.count() == 1
    assert doc1.symptoms_to_treat.count() == 3
    assert doc2.symptoms_to_treat.count() == 2
    doc2.patients.remove(pat2)
    assert doc1.patients.count() == 2
    assert doc2.patients.count() == 0
    assert doc1.symptoms_to_treat.count() == 3
    assert doc2.symptoms_to_treat.count() == 0

    doc3.patients.add(pat3, name="test1")
    doc4.patients.add(pat4, name="test2")
    assert doc3.patients.count() == 1
    assert doc3.patients.count() == 1
    assert doc3.symptoms_to_treat.count() == 2
    assert doc4.symptoms_to_treat.count() == 1
    doc3.patients.add(pat4, name="test2")
    assert doc3.patients.count() == 2
    assert doc4.patients.count() == 1
    assert doc3.symptoms_to_treat.count() == 3
    assert doc4.symptoms_to_treat.count() == 1
    doc4.patients.remove(pat4)
    assert doc3.patients.count() == 2
    assert doc4.patients.count() == 0
    assert doc3.symptoms_to_treat.count() == 3
    assert doc4.symptoms_to_treat.count() == 0


@require_postgres
def test_relations_set(pgs):
    doc1 = DoctorCustom.new(name="test1")
    doc1.save()
    doc2 = DoctorCustom.new(name="test2")
    doc2.save()
    pat1 = PatientCustom.new(name="test1")
    pat1.save()
    pat1.symptoms.create(name="test1a")
    pat2 = PatientCustom.new(name="test2")
    pat2.save()
    pat2.symptoms.create(name="test2a")
    pat2.symptoms.create(name="test2b")
    doc3 = DoctorMulti.new(name="test1")
    doc3.save()
    doc4 = DoctorMulti.new(name="test2")
    doc4.save()
    pat3 = PatientMulti.new(name="test1")
    pat3.save()
    pat3.symptoms.create(name="test3a")
    pat3.symptoms.create(name="test3b")
    pat4 = PatientMulti.new(name="test2")
    pat4.save()
    pat4.symptoms.create(name="test4a")

    doc1.patients.add(pat1, name="test1")

    djoin = DoctorCustom.all().join("appointments").select()
    assert len(djoin) == 1
    assert djoin[0].id == doc1.id
    assert len(djoin[0].appointments()) == 1

    djoin = DoctorCustom.all().join("patients").select()
    assert len(djoin) == 1
    assert djoin[0].id == doc1.id
    assert len(djoin[0].patients()) == 1
    assert djoin[0].patients()[0].code == pat1.code

    pjoin = PatientCustom.all().join("appointments").select()
    assert len(pjoin) == 1
    assert pjoin[0].code == pat1.code
    assert len(pjoin[0].appointments()) == 1

    pjoin = PatientCustom.all().join("doctors").select()
    assert len(pjoin) == 1
    assert pjoin[0].code == pat1.code
    assert len(pjoin[0].doctors()) == 1
    assert pjoin[0].doctors()[0].id == doc1.id

    ajoin = AppointmentCustom.all().join("doctor_custom", "patient_custom").select()
    assert len(ajoin) == 1
    assert ajoin[0].doctor_custom.id == doc1.id
    assert ajoin[0].patient_custom.code == pat1.code

    djoin = DoctorCustom.all().select(including=["appointments"])
    assert len(djoin) == 2
    assert len(djoin[0].appointments()) == 1
    assert len(djoin[1].appointments()) == 0

    djoin = DoctorCustom.all().join("appointments").select(including=["patients"])
    assert len(djoin) == 1
    assert djoin[0].id == doc1.id
    assert len(djoin[0].patients()) == 1

    pjoin = PatientCustom.all().select(including=["appointments"])
    assert len(pjoin) == 2
    assert len(pjoin[0].appointments()) == 1
    assert len(pjoin[1].appointments()) == 0

    pjoin = PatientCustom.all().join("appointments").select(including=["doctors"])
    assert len(pjoin) == 1
    assert pjoin[0].code == pat1.code
    assert len(pjoin[0].doctors()) == 1

    doc3.patients.add(pat3, name="test1")

    djoin = DoctorMulti.all().join("appointments").select()
    assert len(djoin) == 1
    assert djoin[0].foo == doc3.foo
    assert djoin[0].bar == doc3.bar
    assert len(djoin[0].appointments()) == 1

    djoin = DoctorMulti.all().join("patients").select()
    assert len(djoin) == 1
    assert djoin[0].foo == doc3.foo
    assert djoin[0].bar == doc3.bar
    assert len(djoin[0].patients()) == 1
    assert djoin[0].patients()[0].foo == pat3.foo
    assert djoin[0].patients()[0].bar == pat3.bar

    pjoin = PatientMulti.all().join("appointments").select()
    assert len(pjoin) == 1
    assert pjoin[0].foo == pat3.foo
    assert pjoin[0].bar == pat3.bar
    assert len(pjoin[0].appointments()) == 1

    pjoin = PatientMulti.all().join("doctors").select()
    assert len(pjoin) == 1
    assert pjoin[0].foo == pat3.foo
    assert pjoin[0].bar == pat3.bar
    assert len(pjoin[0].doctors()) == 1
    assert pjoin[0].doctors()[0].foo == doc3.foo
    assert pjoin[0].doctors()[0].bar == doc3.bar

    ajoin = AppointmentMulti.all().join("doctor_multi", "patient_multi").select()
    assert len(ajoin) == 1
    assert ajoin[0].doctor_multi.foo == doc3.foo
    assert ajoin[0].doctor_multi.bar == doc3.bar
    assert ajoin[0].patient_multi.foo == pat3.foo
    assert ajoin[0].patient_multi.bar == pat3.bar

    djoin = DoctorMulti.all().select(including=["appointments"])
    assert len(djoin) == 2
    assert len(djoin[0].appointments()) == 1
    assert len(djoin[1].appointments()) == 0

    djoin = DoctorMulti.all().join("appointments").select(including=["patients"])
    assert len(djoin) == 1
    assert djoin[0].foo == doc3.foo
    assert djoin[0].bar == doc3.bar
    assert len(djoin[0].patients()) == 1

    pjoin = PatientMulti.all().select(including=["appointments"])
    assert len(pjoin) == 2
    assert len(pjoin[0].appointments()) == 1
    assert len(pjoin[1].appointments()) == 0

    pjoin = PatientMulti.all().join("appointments").select(including=["doctors"])
    assert len(pjoin) == 1
    assert pjoin[0].foo == pat3.foo
    assert pjoin[0].bar == pat3.bar
    assert len(pjoin[0].doctors()) == 1


@require_postgres
def test_row(pgs):
    sc1 = SourceCustom.new(foo="test1")
    sc1.save()
    sc2 = SourceCustom.new(foo="test2")
    sc2.save()

    dcc1 = DestCustomCustom.new(foo="test1", source_custom=sc1.id)
    assert isinstance(dcc1.source_custom, RowReferenceMixin)
    dcc1.save()
    assert isinstance(dcc1.source_custom, RowReferenceMixin)

    dcc1 = DestCustomCustom.get(dcc1.id)
    dcc1.source_custom = sc2.id
    assert isinstance(dcc1.source_custom, RowReferenceMixin)
    dcc1.save()
    assert isinstance(dcc1.source_custom, RowReferenceMixin)

    sm1 = SourceMulti.new(baz="test1")
    sm1.save()
    sm2 = SourceMulti.new(baz="test2")
    sm2.save()

    dmm1 = DestMultiMulti.new(source_multi=sm1, baz="test")
    dmm1.save()
    assert sm1.dest_multi_multis.count() == 1
    assert sm2.dest_multi_multis.count() == 0

    dmm1.source_multi = sm2
    assert set(dmm1._changes.keys()).issubset(
        {"source_multi", "source_multi_foo", "source_multi_bar"}
    )
    dmm1.save()
    assert sm1.dest_multi_multis.count() == 0
    assert sm2.dest_multi_multis.count() == 1

    DestMultiMulti.create(source_multi=sm1, baz="test")
    assert sm1.dest_multi_multis.count() == 1
