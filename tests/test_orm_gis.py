# -*- coding: utf-8 -*-
"""
    tests.orm_gis
    -------------

    Test ORM GIS features
"""

import os
import pytest

from emmett import App, sdict
from emmett.orm import Database, Model, Field, geo
from emmett.orm.migrations.utils import generate_runtime_migration

require_postgres = pytest.mark.skipif(
    not os.environ.get("POSTGRES_URI"), reason="No postgres database"
)


class Geography(Model):
    name = Field.string()
    geo = Field.geography()
    point = Field.geography("POINT")
    line = Field.geography("LINESTRING")
    polygon = Field.geography("POLYGON")
    multipoint = Field.geography("MULTIPOINT")
    multiline = Field.geography("MULTILINESTRING")
    multipolygon = Field.geography("MULTIPOLYGON")


class Geometry(Model):
    name = Field.string()
    geo = Field.geometry()
    point = Field.geometry("POINT")
    line = Field.geometry("LINESTRING")
    polygon = Field.geometry("POLYGON")
    multipoint = Field.geometry("MULTIPOINT")
    multiline = Field.geometry("MULTILINESTRING")
    multipolygon = Field.geometry("MULTIPOLYGON")


@pytest.fixture(scope='module')
def _db():
    app = App(__name__)
    db = Database(
        app,
        config=sdict(
            uri=f"postgres://{os.environ.get('POSTGRES_URI')}"
        )
    )
    db.define_models(
        Geography,
        Geometry
    )
    return db


@pytest.fixture(scope='function')
def db(_db):
    migration = generate_runtime_migration(_db)
    with _db.connection():
        migration.up()
        yield _db
        migration.down()


@require_postgres
def test_field_types(_db):
    assert Geography.geo.type == "geography(GEOMETRY,4326,2)"
    assert Geography.point.type == "geography(POINT,4326,2)"
    assert Geography.line.type == "geography(LINESTRING,4326,2)"
    assert Geography.polygon.type == "geography(POLYGON,4326,2)"
    assert Geography.multipoint.type == "geography(MULTIPOINT,4326,2)"
    assert Geography.multiline.type == "geography(MULTILINESTRING,4326,2)"
    assert Geography.multipolygon.type == "geography(MULTIPOLYGON,4326,2)"
    assert Geometry.geo.type == "geometry(GEOMETRY,4326,2)"
    assert Geometry.point.type == "geometry(POINT,4326,2)"
    assert Geometry.line.type == "geometry(LINESTRING,4326,2)"
    assert Geometry.polygon.type == "geometry(POLYGON,4326,2)"
    assert Geometry.multipoint.type == "geometry(MULTIPOINT,4326,2)"
    assert Geometry.multiline.type == "geometry(MULTILINESTRING,4326,2)"
    assert Geometry.multipolygon.type == "geometry(MULTIPOLYGON,4326,2)"


@require_postgres
def test_gis_insert(db):
    for model in [Geometry, Geography]:
        row = model.new(
            point=geo.Point(1, 1),
            line=geo.Line((0, 0), (20, 80), (80, 80)),
            polygon=geo.Polygon((0, 0), (150, 0), (150, 10), (0, 10), (0, 0)),
            multipoint=geo.MultiPoint((1, 1), (2, 2)),
            multiline=geo.MultiLine(((1, 1), (2, 2), (3, 3)), ((1, 1), (4, 4), (5, 5))),
            multipolygon=geo.MultiPolygon(
                (
                    ((0, 0), (20, 0), (20, 20), (0, 0)),
                    ((0, 0), (30, 0), (30, 30), (0, 0))
                ),
                (
                    ((1, 1), (21, 1), (21, 21), (1, 1)),
                    ((1, 1), (31, 1), (31, 31), (1, 1))
                )
            )
        )
        row.save()

        assert row.point == "POINT(1.000000 1.000000)"
        assert row.point.geometry == "POINT"
        assert row.point.coordinates == (1, 1)
        assert not row.point.groups

        assert row.line == "LINESTRING({})".format(
            ",".join([
                " ".join(f"{v}.000000" for v in tup)
                for tup in [
                    (0, 0),
                    (20, 80),
                    (80, 80)
                ]
            ])
        )
        assert row.line.geometry == "LINESTRING"
        assert row.line.coordinates == ((0, 0), (20, 80), (80, 80))
        assert not row.line.groups

        assert row.polygon == "POLYGON(({}))".format(
            ",".join([
                " ".join(f"{v}.000000" for v in tup)
                for tup in [
                    (0, 0),
                    (150, 0),
                    (150, 10),
                    (0, 10),
                    (0, 0)
                ]
            ])
        )
        assert row.polygon.geometry == "POLYGON"
        assert row.polygon.coordinates == (
            ((0, 0), (150, 0), (150, 10), (0, 10), (0, 0)),
        )
        assert not row.polygon.groups

        assert row.multipoint == "MULTIPOINT((1.000000 1.000000),(2.000000 2.000000))"
        assert row.multipoint.geometry == "MULTIPOINT"
        assert row.multipoint.coordinates == ((1, 1), (2, 2))
        assert len(row.multipoint.groups) == 2
        assert row.multipoint.groups[0] == geo.Point(1, 1)
        assert row.multipoint.groups[1] == geo.Point(2, 2)

        assert row.multiline == "MULTILINESTRING({})".format(
            ",".join([
                "({})".format(
                    ",".join([
                        " ".join(f"{v}.000000" for v in tup)
                        for tup in group
                    ])
                ) for group in [
                    ((1, 1), (2, 2), (3, 3)),
                    ((1, 1), (4, 4), (5, 5))
                ]
            ])
        )
        assert row.multiline.geometry == "MULTILINESTRING"
        assert row.multiline.coordinates == (
            ((1, 1), (2, 2), (3, 3)),
            ((1, 1), (4, 4), (5, 5))
        )
        assert len(row.multiline.groups) == 2
        assert row.multiline.groups[0] == geo.Line((1, 1), (2, 2), (3, 3))
        assert row.multiline.groups[1] == geo.Line((1, 1), (4, 4), (5, 5))

        assert row.multipolygon == "MULTIPOLYGON({})".format(
            ",".join([
                "({})".format(
                    ",".join([
                        "({})".format(
                            ",".join([
                                " ".join(f"{v}.000000" for v in tup)
                                for tup in group
                            ])
                        ) for group in polygon
                    ])
                ) for polygon in [
                    (
                        ((0, 0), (20, 0), (20, 20), (0, 0)),
                        ((0, 0), (30, 0), (30, 30), (0, 0))
                    ),
                    (
                        ((1, 1), (21, 1), (21, 21), (1, 1)),
                        ((1, 1), (31, 1), (31, 31), (1, 1))
                    )
                ]
            ])
        )
        assert row.multipolygon.geometry == "MULTIPOLYGON"
        assert row.multipolygon.coordinates == (
            (
                ((0, 0), (20, 0), (20, 20), (0, 0)),
                ((0, 0), (30, 0), (30, 30), (0, 0))
            ),
            (
                ((1, 1), (21, 1), (21, 21), (1, 1)),
                ((1, 1), (31, 1), (31, 31), (1, 1))
            )
        )
        assert len(row.multipolygon.groups) == 2
        assert row.multipolygon.groups[0] == geo.Polygon(
            ((0, 0), (20, 0), (20, 20), (0, 0)),
            ((0, 0), (30, 0), (30, 30), (0, 0))
        )
        assert row.multipolygon.groups[1] == geo.Polygon(
            ((1, 1), (21, 1), (21, 21), (1, 1)),
            ((1, 1), (31, 1), (31, 31), (1, 1))
        )


@require_postgres
def test_gis_select(db):
    for model in [Geometry, Geography]:
        row = model.new(
            point=geo.Point(1, 1),
            line=geo.Line((0, 0), (20, 80), (80, 80)),
            polygon=geo.Polygon((0, 0), (150, 0), (150, 10), (0, 10), (0, 0)),
            multipoint=geo.MultiPoint((1, 1), (2, 2)),
            multiline=geo.MultiLine(((1, 1), (2, 2), (3, 3)), ((1, 1), (4, 4), (5, 5))),
            multipolygon=geo.MultiPolygon(
                (
                    ((0, 0), (20, 0), (20, 20), (0, 0)),
                    ((0, 0), (30, 0), (30, 30), (0, 0))
                ),
                (
                    ((1, 1), (21, 1), (21, 21), (1, 1)),
                    ((1, 1), (31, 1), (31, 31), (1, 1))
                )
            )
        )
        row.save()
        row = model.get(row.id)

        assert row.point.geometry == "POINT"
        assert row.point.coordinates == (1, 1)
        assert not row.point.groups

        assert row.line.geometry == "LINESTRING"
        assert row.line.coordinates == ((0, 0), (20, 80), (80, 80))
        assert not row.line.groups

        assert row.polygon.geometry == "POLYGON"
        assert row.polygon.coordinates == (
            ((0, 0), (150, 0), (150, 10), (0, 10), (0, 0)),
        )
        assert not row.polygon.groups

        assert row.multipoint.geometry == "MULTIPOINT"
        assert row.multipoint.coordinates == ((1, 1), (2, 2))
        assert len(row.multipoint.groups) == 2
        assert row.multipoint.groups[0] == geo.Point(1, 1)
        assert row.multipoint.groups[1] == geo.Point(2, 2)

        assert row.multiline.geometry == "MULTILINESTRING"
        assert row.multiline.coordinates == (
            ((1, 1), (2, 2), (3, 3)),
            ((1, 1), (4, 4), (5, 5))
        )
        assert len(row.multiline.groups) == 2
        assert row.multiline.groups[0] == geo.Line((1, 1), (2, 2), (3, 3))
        assert row.multiline.groups[1] == geo.Line((1, 1), (4, 4), (5, 5))

        assert row.multipolygon.geometry == "MULTIPOLYGON"
        assert row.multipolygon.coordinates == (
            (
                ((0, 0), (20, 0), (20, 20), (0, 0)),
                ((0, 0), (30, 0), (30, 30), (0, 0))
            ),
            (
                ((1, 1), (21, 1), (21, 21), (1, 1)),
                ((1, 1), (31, 1), (31, 31), (1, 1))
            )
        )
        assert len(row.multipolygon.groups) == 2
        assert row.multipolygon.groups[0] == geo.Polygon(
            ((0, 0), (20, 0), (20, 20), (0, 0)),
            ((0, 0), (30, 0), (30, 30), (0, 0))
        )
        assert row.multipolygon.groups[1] == geo.Polygon(
            ((1, 1), (21, 1), (21, 21), (1, 1)),
            ((1, 1), (31, 1), (31, 31), (1, 1))
        )
