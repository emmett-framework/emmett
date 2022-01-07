# -*- coding: utf-8 -*-
"""
    emmett.orm.geo
    --------------

    Provides geographic facilities.

    :copyright: 2014 Giovanni Barillari
    :license: BSD-3-Clause
"""

from .helpers import GeoFieldWrapper


def Point(x, y):
    return GeoFieldWrapper("POINT(%f %f)" % (x, y))


def Line(*coordinates):
    return GeoFieldWrapper(
        "LINESTRING(%s)" % ','.join("%f %f" % point for point in coordinates)
    )


def Polygon(*coordinates_groups):
    try:
        if not isinstance(coordinates_groups[0][0], (tuple, list)):
            coordinates_groups = (coordinates_groups,)
    except Exception:
        pass
    return GeoFieldWrapper(
        "POLYGON(%s)" % (
            ",".join([
                "(%s)" % ",".join("%f %f" % point for point in group)
                for group in coordinates_groups
            ])
        )
    )


def MultiPoint(*points):
    return GeoFieldWrapper(
        "MULTIPOINT(%s)" % (
            ",".join([
                "(%f %f)" % point for point in points
            ])
        )
    )


def MultiLine(*lines):
    return GeoFieldWrapper(
        "MULTILINESTRING(%s)" % (
            ",".join([
                "(%s)" % ",".join("%f %f" % point for point in line)
                for line in lines
            ])
        )
    )


def MultiPolygon(*polygons):
    return GeoFieldWrapper(
        "MULTIPOLYGON(%s)" % (
            ",".join([
                "(%s)" % (
                    ",".join([
                        "(%s)" % ",".join("%f %f" % point for point in group)
                        for group in polygon
                    ])
                ) for polygon in polygons
            ])
        )
    )
