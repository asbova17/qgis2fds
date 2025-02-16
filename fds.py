# -*- coding: utf-8 -*-

"""qgis2fds"""

__author__ = "Emanuele Gissi, Ruggero Poletto"
__date__ = "2020-05-04"
__copyright__ = "(C) 2020 by Emanuele Gissi"
__revision__ = "$Format:%H$"  # replaced with git SHA1

from qgis.core import QgsExpressionContextUtils, QgsProject
from qgis.utils import pluginMetadata
import time, os
from . import utils

# Config

landuse_types = "Landfire F13", "CIMA Propagator"

landuse_choices = {
    0: {  # Landfire F13
        0: 19,
        1: 1,
        2: 2,
        3: 3,
        4: 4,
        5: 5,
        6: 6,
        7: 7,
        8: 8,
        9: 9,
        10: 10,
        11: 11,
        12: 12,
        13: 13,
        91: 14,
        92: 15,
        93: 16,
        98: 17,
        99: 18,
    },  # Cima Propagator
    1: {
        0: 19,
        1: 5,
        2: 4,
        3: 18,
        4: 10,
        5: 10,
        6: 1,
        7: 1,
    },
}


def write_case(
    feedback,
    dem_layer,
    landuse_layer,
    path,
    chid,
    wgs84_origin,
    utm_origin,
    wgs84_fire_origin,
    utm_fire_origin,
    utm_crs,
    verts,
    faces,
    landuses,
    landuse_type,
    utm_extent,
):
    """
    Get FDS case.
    """

    # Calc header
    pv = pluginMetadata("qgis2fds", "version")
    qv = QgsExpressionContextUtils.globalScope().variable("qgis_version")
    now = time.strftime("%a, %d %b %Y, %H:%M:%S", time.localtime())
    filepath = QgsProject.instance().fileName() or "not saved"
    if len(filepath) > 60:
        filepath = "..." + filepath[-57:]

    # Calc MESH XB
    mesh_xb = (
        utm_extent.xMinimum() - utm_origin.x(),  # relative to origin
        utm_extent.xMaximum() - utm_origin.x(),
        utm_extent.yMinimum() - utm_origin.y(),
        utm_extent.yMaximum() - utm_origin.y(),
        min(v[2] for v in verts) - 2.0,
        max(v[2] for v in verts) + 50.0,
    )

    # Calc MESH IJK
    cell_size = 10.0
    mesh_ijk = (
        int((mesh_xb[1] - mesh_xb[0]) / cell_size),
        int((mesh_xb[3] - mesh_xb[2]) / cell_size),
        int((mesh_xb[5] - mesh_xb[4]) / cell_size),
    )

    # Calc ignition point VENT XB
    fx, fy = (
        utm_fire_origin.x() - utm_origin.x(),  # relative to origin
        utm_fire_origin.y() - utm_origin.y(),
    )
    fxb = (
        fx - cell_size / 2,
        fx + cell_size / 2,
        fy - cell_size / 2,
        fy + cell_size / 2,
        mesh_xb[4] + 1.0,
        mesh_xb[4] + 1.0,
    )

    # Prepare and write FDS file
    content = f"""
! Generated by qgis2fds <{pv}> on QGIS <{qv.encode('utf-8')}>
! QGIS file: <{filepath}>
! Selected UTM CRS: <{utm_crs.description()}>
! Terrain extent: <{utm_extent.toString(precision=1)}>
! DEM layer: <{dem_layer.name()}>
! Landuse layer: <{landuse_layer and landuse_layer.name() or 'None'}>
! Landuse type: <{landuse_layer and ('Landfire F13', 'CIMA Propagator')[landuse_type] or 'None'}>
! Domain Origin: <{utm_origin.x():.1f}, {utm_origin.y():.1f}>
!   {utils.get_lonlat_url(wgs84_origin)}
! Fire Origin: <{utm_fire_origin.x():.1f}, {utm_fire_origin.y():.1f}>
!   {utils.get_lonlat_url(wgs84_fire_origin)}
! Date: <{now}>
 
&HEAD CHID='{chid}' TITLE='Description of {chid}' /
&TIME T_END=1. /

! MISC LEVEL_SET_MODE parameter
! 1: Wind not affected by the terrain. No fire.
! 2: Wind field established over the terrain, then frozen. No fire.
! 3: Wind field following the terrain, no fire.
! 4: Wind and fire fully-coupled.

&MISC ORIGIN_LAT={wgs84_origin.y():.7f} ORIGIN_LON={wgs84_origin.x():.7f} NORTH_BEARING=0.
      TERRAIN_IMAGE='{chid}_tex.png'
      LEVEL_SET_MODE=1 /

! Domain and its boundary conditions
&MESH IJK={mesh_ijk[0]:d},{mesh_ijk[1]:d},{mesh_ijk[2]:d}
      XB={mesh_xb[0]:.3f},{mesh_xb[1]:.3f},{mesh_xb[2]:.3f},{mesh_xb[3]:.3f},{mesh_xb[4]:.3f},{mesh_xb[5]:.3f} /
&VENT ID='Domain BC XMIN' MB='XMIN' SURF_ID='OPEN' /
&VENT ID='Domain BC XMAX' MB='XMAX' SURF_ID='OPEN' /
&VENT ID='Domain BC YMIN' MB='YMIN' SURF_ID='OPEN' /
&VENT ID='Domain BC YMAX' MB='YMAX' SURF_ID='OPEN' /
&VENT ID='Domain BC ZMAX' MB='ZMAX' SURF_ID='OPEN' /

! Fire origin
&SURF ID='Ignition' VEG_LSET_IGNITE_TIME=0. COLOR='RED' /
&VENT ID='Ignition point' SURF_ID='Ignition', GEOM=T
      XB={fxb[0]:.3f},{fxb[1]:.3f},{fxb[2]:.3f},{fxb[3]:.3f},{fxb[4]:.3f},{fxb[5]:.3f} /
 
! Output quantities
&SLCF AGL_SLICE=1. QUANTITY='LEVEL SET VALUE' /
&SLCF AGL_SLICE=1. QUANTITY='TEMPERATURE' VECTOR=T /
&SLCF PBX={fx:.3f} QUANTITY='TEMPERATURE' /
&SLCF PBX={fy:.3f} QUANTITY='TEMPERATURE' /

! Wind (example)
&WIND SPEED=1., RAMP_SPEED='ws', RAMP_DIRECTION='wd' /
&RAMP ID='ws', T=   0, F=10. /
&RAMP ID='ws', T= 600, F=10. /
&RAMP ID='ws', T=1200, F=20. /
&RAMP ID='wd', T=   0, F=315. /
&RAMP ID='wd', T= 600, F=270. /
&RAMP ID='wd', T=1200, F=360. /
 
! Boundary conditions
! 13 Anderson Fire Behavior Fuel Models
&SURF ID='A01' RGB=255,254,212 VEG_LSET_FUEL_INDEX= 1 /
&SURF ID='A02' RGB=255,253,102 VEG_LSET_FUEL_INDEX= 2 /
&SURF ID='A03' RGB=236,212, 99 VEG_LSET_FUEL_INDEX= 3 /
&SURF ID='A04' RGB=254,193,119 VEG_LSET_FUEL_INDEX= 4 /
&SURF ID='A05' RGB=249,197, 92 VEG_LSET_FUEL_INDEX= 5 /
&SURF ID='A06' RGB=217,196,152 VEG_LSET_FUEL_INDEX= 6 /
&SURF ID='A07' RGB=170,155,127 VEG_LSET_FUEL_INDEX= 7 /
&SURF ID='A08' RGB=229,253,214 VEG_LSET_FUEL_INDEX= 8 /
&SURF ID='A09' RGB=162,191, 90 VEG_LSET_FUEL_INDEX= 9 /
&SURF ID='A10' RGB=114,154, 85 VEG_LSET_FUEL_INDEX=10 /
&SURF ID='A11' RGB=235,212,253 VEG_LSET_FUEL_INDEX=11 /
&SURF ID='A12' RGB=163,177,243 VEG_LSET_FUEL_INDEX=12 /
&SURF ID='A13' RGB=  0,  0,  0 VEG_LSET_FUEL_INDEX=13 /
&SURF ID='Urban' RGB=186,119, 80 /
&SURF ID='Snow-Ice' RGB=234,234,234 /
&SURF ID='Agriculture' RGB=253,242,242 /
&SURF ID='Water' RGB=137,183,221 /
&SURF ID='Barren' RGB=133,153,156 /
&SURF ID='NA' RGB=255,255,255 /

! Terrain
&GEOM ID='Terrain'
      SURF_ID='A01','A02','A03','A04','A05','A06','A07',
              'A08','A09','A10','A11','A12','A13','Urban',
              'Snow-Ice','Agriculture','Water','Barren','NA'
      BINARY_FILE='{chid}_terrain.bingeom'
      IS_TERRAIN=T EXTEND_TERRAIN=F /

&TAIL /
    """
    utils.write_file(feedback=feedback, filepath=f"{path}/{chid}.fds", content=content)

    # Write bingeom file
    filepath = os.path.join(path, chid + "_terrain.bingeom")
    landuse_select = landuse_choices[landuse_type]
    fds_surfs = tuple(
        landuse_select.get(landuses[i], landuses[0]) for i, _ in enumerate(faces)
    )
    n_surf_id = max(fds_surfs)
    fds_verts = tuple(v for vs in verts for v in vs)
    fds_faces = tuple(f for fs in faces for f in fs)
    utils.write_bingeom(
        feedback=feedback,
        geom_type=2,
        n_surf_id=n_surf_id,
        fds_verts=fds_verts,
        fds_faces=fds_faces,
        fds_surfs=fds_surfs,
        fds_volus=list(),
        filepath=filepath,
    )
