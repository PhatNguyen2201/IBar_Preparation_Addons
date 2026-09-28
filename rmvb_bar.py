bl_info = {
    "name": "Rmvb-Bar",
    "author": "Phat Nguyen",
    "version": (0, 1, 0),
    "blender": (4, 5, 3),
    "location": "View3D > Sidebar > Rmvb-Bar",
    "description": "Thiet ke bar implant: Bar Pillar / Bar Segment / Top Bar / Attachment / Sleeve",
    "warning": "",
    "doc_url": "",
    "category": "3D View",
}

"""Rmvb-Bar
===========
Panel thiet ke khung bar implant. Lay Connection Base va Attachment tu add-on
Dental-Lib. Quy trinh:

    Import (Gingiva / Denture-reference / Antagonist)
      -> Select Connection Base + Place Connection (doc .constructionInfo)
      -> Bar Design: Bar Pillar -> Bar Segment -> Top Bar Plane -> Cut Top Bar
      -> Attachment
      -> Sleeve Design
      -> Save (STL)

Chuan do luong: 1 Blender unit = 1 mm (dung chung cach lam voi add-on iBar).
"""

import bpy
import bmesh
import os
import re
import sys
import time

from mathutils import Vector, Matrix
from bpy.props import (
    StringProperty,
    BoolProperty,
    IntProperty,
    FloatProperty,
    EnumProperty,
    CollectionProperty,
    PointerProperty,
)
from bpy.types import Operator, Panel, PropertyGroup
from bpy_extras.io_utils import ImportHelper
from bpy_extras import view3d_utils
import xml.etree.ElementTree as ET

MESH_EXTS = (".stl", ".ply")
MM_TO_BU = 1.0

COL_IMPORT = "Rmvb Import"
COL_CONNECTION = "Rmvb Connections"
COL_PILLAR = "Rmvb Bar Pillar"
COL_SEGMENT = "Rmvb Bar Segment"
COL_TOPBAR = "Rmvb Top Bar"
COL_ATTACHMENT = "Rmvb Attachment"
COL_SLEEVE = "Rmvb Sleeve"
COL_PREVIEW = "Rmvb Preview"

OBJ_BAR = "Rmvb_Bar"
OBJ_SEGMENT = "Rmvb_BarSegment"
OBJ_LINE = "Rmvb_BarLine"
OBJ_PLANE = "Rmvb_TopBarPlane"
OBJ_CUTTER = "Rmvb_TopBarCutter"
OBJ_SLEEVE = "Rmvb_Sleeve"
OBJ_ATTACH_AXIS = "Rmvb_AttachmentAxis"

VG_SCREW = "Screw"
VG_OUTSIDE = "Outside"

CST_ON_PLANE = "RMVB_on_plane"


# ---------------------------------------------------------------------------
# Tiep can add-on Dental-Lib
# ---------------------------------------------------------------------------
def dlib():
    """Tra ve module dental_lib (add-on thu vien) hoac None."""
    module = sys.modules.get("dental_lib")
    if module is not None:
        return module
    try:
        import dental_lib as module  # noqa
        return module
    except Exception:
        pass
    # Fallback: thu tim trong thu muc add-on dang dung
    try:
        here = os.path.dirname(os.path.abspath(__file__))
        if here not in sys.path:
            sys.path.append(here)
        import dental_lib as module  # noqa
        return module
    except Exception as exc:
        print(f"[Rmvb-Bar] Khong tim thay add-on Dental-Lib: {exc}")
        return None


def lib_connection_names():
    lib = dlib()
    return lib.connection_names() if lib else []


def lib_attachment_names():
    lib = dlib()
    return lib.attachment_names() if lib else []


def lib_connection_asset(name, slot):
    lib = dlib()
    return lib.connection_asset(name, slot) if lib else ""


def lib_attachment(name):
    lib = dlib()
    return lib.get_attachment(name) if lib else None


def lib_visuals(name):
    lib = dlib()
    return lib.attachment_visuals(name) if lib else []


# ---------------------------------------------------------------------------
# Collection / object helpers
# ---------------------------------------------------------------------------
def ensure_collection(name, parent=None):
    coll = bpy.data.collections.get(name)
    if coll is None:
        coll = bpy.data.collections.new(name)
        host = parent if parent is not None else bpy.context.scene.collection
        host.children.link(coll)
    return coll


def link_to(obj, coll):
    for user in list(obj.users_collection):
        user.objects.unlink(obj)
    coll.objects.link(obj)
    return obj


def new_object(name, mesh, coll):
    obj = bpy.data.objects.new(name, mesh)
    coll.objects.link(obj)
    return obj


def remove_object(obj):
    if obj is None:
        return
    try:
        data = obj.data
        bpy.data.objects.remove(obj, do_unlink=True)
    except (ReferenceError, RuntimeError):
        return
    if data is not None and data.users == 0:
        try:
            bpy.data.meshes.remove(data)
        except Exception:
            pass


def purge_collection(coll):
    """Xoa sach moi object trong collection (cho duoc goi nhieu lan)."""
    for name in [ob.name for ob in list(coll.objects)]:
        remove_object(bpy.data.objects.get(name))


def set_color(obj, rgba):
    """Dat mau hien thi trong viewport cho de phan biet cac thanh phan."""
    try:
        obj.color = rgba
        obj.display_color = 'OBJECT'
    except Exception:
        pass


def activate(context, obj, select=True):
    bpy.ops.object.select_all(action='DESELECT')
    try:
        obj.select_set(select)
    except Exception:
        pass
    context.view_layer.objects.active = obj
    return obj


def project_dir():
    path = bpy.path.abspath("//")
    return path if path else os.path.expanduser("~")


def timestamp():
    return time.strftime("%y%m%d-%H%M")


# ---------------------------------------------------------------------------
# Mesh cache: doc STL/PLY thanh bpy.data.meshes (khong de lai object roi)
# ---------------------------------------------------------------------------
_MESH_CACHE = {}


def mesh_from_file(filepath, scale=1.0):
    """Import STL/PLY va tra ve Mesh datablock duoc dung lai nhieu lan."""
    if not filepath or not os.path.exists(filepath):
        raise FileNotFoundError("Khong tim thay file mesh: %s" % filepath)
    key = (os.path.abspath(filepath), os.path.getmtime(filepath), round(scale, 6))
    cached = _MESH_CACHE.get(key)
    if cached is not None and cached.name in bpy.data.meshes:
        return cached

    ext = os.path.splitext(filepath)[1].lower()
    before = {ob.name for ob in bpy.data.objects}
    if ext == ".ply":
        bpy.ops.wm.ply_import(filepath=filepath, global_scale=scale)
    else:
        bpy.ops.wm.stl_import(filepath=filepath, global_scale=scale)
    created = [ob for ob in bpy.data.objects
               if ob.name not in before and ob.type == 'MESH']
    if not created:
        raise RuntimeError("File khong chua mesh: %s" % filepath)

    bm = bmesh.new()
    for ob in created:
        temp = bmesh.new()
        temp.from_mesh(ob.data)
        temp.transform(ob.matrix_world)
        merge_map = {}
        for vert in temp.verts:
            merge_map[vert.index] = bm.verts.new(vert.co)
        for face in temp.faces:
            try:
                bm.faces.new([merge_map[v.index] for v in face.verts])
            except ValueError:
                pass
        temp.free()
    mesh = bpy.data.meshes.new(os.path.basename(filepath))
    bm.to_mesh(mesh)
    bm.free()
    for ob in created:
        if ob.name in bpy.data.objects:
            bpy.data.objects.remove(ob, do_unlink=True)
    if mesh.users == 0:
        mesh.use_fake_user = True
    _MESH_CACHE[key] = mesh
    return mesh


def object_from_mesh(name, mesh, coll, matrix=None):
    obj = bpy.data.objects.new(name, mesh)
    coll.objects.link(obj)
    if matrix is not None:
        obj.matrix_world = matrix
    return obj


# ---------------------------------------------------------------------------
# Boundary loop: phat hien cac vung mo cua mesh
# ---------------------------------------------------------------------------
def boundary_loops(bm):
    """Danh sach cac vong bien cua mesh mo.

    Tra ve list[dict]: {"edges": [BMEdge...], "verts": [BMVert theo thu tu vong],
    "z": gia tri Z trung binh trong toa do local}
    """
    bm.edges.ensure_lookup_table()
    seen = set()
    loops = []
    for edge in bm.edges:
        if not edge.is_boundary or edge.index in seen:
            continue
        stack = [edge]
        comp = []
        while stack:
            cur = stack.pop()
            if cur.index in seen:
                continue
            seen.add(cur.index)
            comp.append(cur)
            for vert in cur.verts:
                for link in vert.link_edges:
                    if link.is_boundary and link.index not in seen:
                        stack.append(link)
        verts = ordered_loop_verts(comp)
        z_mean = sum(v.co.z for v in verts) / max(1, len(verts))
        loops.append({"edges": comp, "verts": verts, "z": z_mean})
    return loops


def ordered_loop_verts(loop):
    """Thu tu dinh cua mot vong bien lien ket kin."""
    if not loop:
        return []
    edge_ids = {edge.index for edge in loop}
    ordered = []
    current = loop[0]
    prev_vert = None
    used_edges = set()
    guard = 0
    while current is not None and guard <= len(loop) * 2 + 4:
        guard += 1
        used_edges.add(current.index)
        vert_a, vert_b = current.verts
        if prev_vert is None:
            ordered.append(vert_a)
            nxt_vert = vert_b
        else:
            nxt_vert = vert_b if prev_vert is vert_a else vert_a
        ordered.append(nxt_vert)
        prev_vert = nxt_vert
        following = None
        for edge in nxt_vert.link_edges:
            if edge.index in edge_ids and edge.index not in used_edges:
                following = edge
                break
        current = following
    return ordered


# ---------------------------------------------------------------------------
# Boolean / modifier khong dung ops (an toan trong background va modal)
# ---------------------------------------------------------------------------
def cleanup_mesh(obj, dist=1e-6, dissolve=False):
    """Doi chieu sau boolean: lap kin lo mo con lai (va tuy chon xoa mat thoai).

    Khong weld dinh (remove_doubles) vi boolean da chinh xac, weld lam mo them
    cac canh non-manifold.
    """
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    if dissolve:
        try:
            bmesh.ops.dissolve_degenerate(bm, edges=bm.edges, dist=dist)
        except Exception:
            pass
    left = [e for e in bm.edges if e.is_boundary]
    if left:
        try:
            bmesh.ops.holes_fill(bm, edges=left, sides=0)
        except Exception:
            pass
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    try:
        if bm.calc_volume(signed=True) < 0:
            bmesh.ops.reverse_faces(bm, faces=bm.faces)
    except Exception:
        pass
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.validate()
    obj.data.update()
    return obj


def union_all(objs, name, coll):
    """Union tuan tu cac solid thanh 1 the manifold (khong trung lap shell)."""
    objs = [o for o in objs if o is not None and o.name in bpy.data.objects]
    if not objs:
        return None
    base = objs[0]
    for other in objs[1:]:
        boolean_objects(base, [other], 'UNION')
        remove_object(other)
    if base.name != name:
        base.name = name
    # Ket qua luu vao collection chinh (khong de nam trong temp bi purge)
    for user in list(base.users_collection):
        if user != coll:
            user.objects.unlink(base)
    if base.name not in coll.objects:
        coll.objects.link(base)
    return base


def evaluated_mesh_object(obj, name=None, coll=None):
    """Copy da apply toan bo modifier (mesh tinh theo toa do local cua obj)."""
    context = bpy.context
    context.view_layer.update()
    depsgraph = context.evaluated_depsgraph_get()
    depsgraph.update()
    mesh = _mesh_from_evaluated(obj.evaluated_get(depsgraph))
    mesh.name = (name or obj.name) + "_eval"
    new = bpy.data.objects.new(name or obj.name + ".eval", mesh)
    host = coll if coll is not None else context.scene.collection
    host.objects.link(new)
    new.matrix_world = obj.matrix_world.copy()
    return new


def _mesh_from_evaluated(evaluated):
    """new_from_object co fallback (preserve_all_data_layers lam mat mesh)."""
    mesh = bpy.data.meshes.new_from_object(evaluated)
    if len(mesh.polygons) == 0:
        try:
            alt = bpy.data.meshes.new_from_object(
                evaluated, preserve_all_data_layers=True)
            if len(alt.polygons) > 0:
                bpy.data.meshes.remove(mesh)
                return alt
            bpy.data.meshes.remove(alt)
        except Exception:
            pass
    return mesh


def add_boolean(target, operand, operation, keep_source=True,
                solver='EXACT', use_self=False):
    mod = target.modifiers.new(name="RMVB_Boolean", type='BOOLEAN')
    mod.operation = operation            # 'DIFFERENCE' | 'UNION' | 'INTERSECT'
    mod.object = operand
    mod.solver = solver
    for prop, value in (("use_self", use_self), ("use_hole_tolerant", False)):
        if hasattr(mod, prop):
            try:
                setattr(mod, prop, value)
            except Exception:
                pass
    return mod


def _mesh_quality(obj):
    """(polys, boundary_edges, non_manifold_edges) - dung quyet dinh solver."""
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    polys = len(bm.faces)
    bnd = sum(1 for edge in bm.edges if edge.is_boundary)
    nonmani = sum(1 for edge in bm.edges if len(edge.link_faces) != 2)
    bm.free()
    return polys, bnd, nonmani


def solid_volume(obj):
    """The tich (mm^3) cua khoi mesh dang o toa do world."""
    try:
        bm = bmesh.new()
        bm.from_mesh(obj.data)
        bm.transform(obj.matrix_world)
        volume = abs(bm.calc_volume(signed=True))
        bm.free()
        return volume
    except Exception:
        return 0.0


def apply_modifiers_in_place(obj):
    """Apply kieu khong ops: lay mesh evaluated roi thay vao data cu."""
    context = bpy.context
    context.view_layer.update()
    depsgraph = context.evaluated_depsgraph_get()
    depsgraph.update()
    mesh = _mesh_from_evaluated(obj.evaluated_get(depsgraph))
    old = obj.data
    obj.data = mesh
    mesh.name = old.name
    if old.users == 0:
        bpy.data.meshes.remove(old)
    return obj


def boolean_objects(target, operands, operation, solvers=('MANIFOLD', 'EXACT')):
    """target = target <operation> cac operand; thu lan luot cac solver.

    Solver MANIFOLD cho ket qua kin dao nhat; EXACT (va EXACT + use_self) duoc
    dung lam bo phan khi dau vao co dinh ky khong manifold.
    """
    operands = [o for o in operands if o is not None]
    if not operands:
        return target
    original = target.data.copy()
    original.name = target.name + ".src"
    best = None
    for index, solver in enumerate(solvers):
        for flag in ((False, True) if solver == 'EXACT' else (False,)):
            target.data = original.copy()
            for mod in [m for m in target.modifiers
                        if m.name.startswith("RMVB_Boolean")]:
                target.modifiers.remove(mod)
            for operand in operands:
                add_boolean(target, operand, operation, solver=solver,
                            use_self=(solver == 'EXACT' and flag))
            bpy.context.view_layer.update()
            apply_modifiers_in_place(target)
            for mod in [m for m in target.modifiers
                        if m.name.startswith("RMVB_Boolean")]:
                target.modifiers.remove(mod)
            polys, bnd, nonmani = _mesh_quality(target)
            if polys == 0:
                continue
            score = bnd * 1000 + nonmani
            if best is None or score < best[0]:
                best = (score, target.data.copy(), solver, flag)
            if bnd == 0:
                break
        if best and best[0] == 0:
            break
    if best is not None:
        old = target.data
        target.data = best[1]
        target.data.name = old.name
        if old.users == 0:
            bpy.data.meshes.remove(old)
    if original.users == 0:
        bpy.data.meshes.remove(original)
    return target


def join_objects(objs, name, coll):
    """Hop nhat thanh 1 object (ket qua nam trong toa do world)."""
    objs = [o for o in objs if o is not None and o.name in bpy.data.objects]
    if not objs:
        return None
    if len(objs) == 1:
        objs[0].name = name
        return objs[0]
    base = bpy.data.meshes.new(name)
    holder = bpy.data.objects.new(name, base)
    coll.objects.link(holder)
    bm = bmesh.new()
    for obj in objs:
        temp = bmesh.new()
        temp.from_mesh(obj.data)
        temp.transform(obj.matrix_world)
        merge = {}
        for vert in temp.verts:
            merge[vert.index] = bm.verts.new(vert.co)
        for face in temp.faces:
            try:
                bm.faces.new([merge[v.index] for v in face.verts])
            except ValueError:
                pass
        temp.free()
    bm.to_mesh(base)
    bm.free()
    for obj in objs:
        remove_object(obj)
    return holder


# ---------------------------------------------------------------------------
# Xuat STL (tuong thich Blender 4.x / 5.x)
# ---------------------------------------------------------------------------
def export_stl(objects, filepath, context):
    """Xuat danh sach object ra STL binary."""
    objs = [o for o in objects if o is not None and o.name in bpy.data.objects]
    if not objs:
        raise RuntimeError("Khong co object de xuat STL")
    folder = os.path.dirname(filepath)
    if folder:
        os.makedirs(folder, exist_ok=True)
    unhidden = []
    for obj in objs:
        if obj.hide_get():
            obj.hide_set(False)
            unhidden.append(obj)
    activate(context, objs[0])
    for obj in objs:
        try:
            obj.select_set(True)
        except Exception:
            pass
    if hasattr(bpy.ops.wm, "stl_export"):
        bpy.ops.wm.stl_export(filepath=filepath, export_selected_objects=True,
                              apply_modifiers=True, global_scale=1.0)
    elif hasattr(bpy.ops.export_mesh, "stl"):
        bpy.ops.export_mesh.stl(filepath=filepath, use_selection=True)
    else:
        raise RuntimeError("Blender khong co exporter STL")
    for obj in unhidden:
        obj.hide_set(True)
    return filepath


# ---------------------------------------------------------------------------
# View / transform orientation
# ---------------------------------------------------------------------------
def use_local_orientation(context):
    """Dat transform orientation = Local (dung khi Edit Bar Pillar/Segment).

    Blender 4.x: tool_settings.transform_orientation
    Blender 5.x: scene.transform_orientation_slots[0].type
    """
    done = False
    try:
        context.tool_settings.transform_orientation = 'LOCAL'
        done = True
    except Exception:
        pass
    if not done:
        try:
            slots = context.scene.transform_orientation_slots
            if slots:
                slots[0].type = 'LOCAL'
                done = True
        except Exception:
            pass
    try:
        context.tool_settings.transform_pivot_point = 'INDIVIDUAL_ORIGINS'
    except Exception:
        pass
    return done


def view_3d_area(context):
    if context.area is not None and context.area.type == 'VIEW_3D':
        return context.area
    if context.screen is None:
        return None
    for area in context.screen.areas:
        if area.type == 'VIEW_3D':
            return area
    return None


# ---------------------------------------------------------------------------
# Doc file .constructionInfo / ImplantDirectionPosition.xml
# ---------------------------------------------------------------------------
def matrix_from_element(element):
    """Chuyen <MatrixImplantGeometry> (_00.._33) thanh mathutils.Matrix."""
    values = {child.tag: child.text for child in element}

    def num(key):
        try:
            return float(values.get(key, 0.0))
        except (TypeError, ValueError):
            return 0.0

    return Matrix((
        (num("_00"), num("_10"), num("_20"), num("_30")),
        (num("_01"), num("_11"), num("_21"), num("_31")),
        (num("_02"), num("_12"), num("_22"), num("_32")),
        (num("_03"), num("_13"), num("_23"), num("_33")),
    ))


def parse_construction_info(filepath):
    """Lay danh sach implant: [{'tooth','type','matrix','axis'}]."""
    root = ET.parse(filepath).getroot()
    implants = []
    for tooth in root.findall(".//Tooth"):
        implant_type = tooth.findtext("ImplantType", default="None")
        geometry = tooth.find("MatrixImplantGeometry")
        if implant_type in (None, "None") or geometry is None:
            continue
        axis = None
        axis_element = tooth.find("AxisImplant")
        if axis_element is not None:
            try:
                axis = Vector((float(axis_element.findtext("x", 0.0)),
                               float(axis_element.findtext("y", 0.0)),
                               float(axis_element.findtext("z", 0.0))))
            except (TypeError, ValueError):
                axis = None
        implants.append({
            "tooth": tooth.findtext("Number", default="?"),
            "type": implant_type,
            "matrix": matrix_from_element(geometry),
            "axis": axis,
        })
    return implants


# ---------------------------------------------------------------------------
# Combobox lay danh sach tu thu vien Dental-Lib
# ---------------------------------------------------------------------------
def get_connection_items():
    return lib_connection_names()


def get_attachment_items():
    return lib_attachment_names()


def _index_enum(names, icon='MESH_CYLINDER'):
    """Enum dung index lam identifier (an toan voi ten co dau/khoang trang)."""
    if not names:
        return [("0", "(Trống)", "Chưa có mục nào trong thư viện Dental-Lib",
                 'ERROR', 0)]
    return [(str(i), name, name, icon, i) for i, name in enumerate(names)]


def enum_connection_base(self, context):
    return _index_enum(get_connection_items())


def enum_attachment(self, context):
    return _index_enum(get_attachment_items(), 'MESH_CUBE')


def _safe_index(value, count):
    """Index an toan cho combobox (khong bao gio vuot khoi danh sach)."""
    try:
        index = int(value)
    except (TypeError, ValueError):
        index = 0
    return max(0, min(index, max(0, count - 1)))


def _connection_get(self):
    try:
        names = get_connection_items()
        if not names:
            return "0"
        return str(_safe_index(self.connection_index, len(names)))
    except Exception:
        return "0"


def _connection_set(self, value):
    if not str(value).isdigit():
        return
    index = int(value)
    names = get_connection_items()
    self.connection_index = _safe_index(index, len(names))
    self.connection_name = (names[self.connection_index] if names else "")


def _attachment_get(self):
    try:
        names = get_attachment_items()
        if not names:
            return "0"
        return str(_safe_index(self.attachment_index, len(names)))
    except Exception:
        return "0"


def _attachment_set(self, value):
    if not str(value).isdigit():
        return
    names = get_attachment_items()
    self.attachment_index = _safe_index(int(value), len(names))
    self.active_attachment = (names[self.attachment_index] if names else "")


class RMVB_PG_PlacedConnection(PropertyGroup):
    tooth: StringProperty(name="Tooth", default="?")
    lib_name: StringProperty(name="Library", default="")
    base_object: PointerProperty(name="Base", type=bpy.types.Object)
    analog_object: PointerProperty(name="Analog", type=bpy.types.Object)
    screw_object: PointerProperty(name="Screw", type=bpy.types.Object)
    scanbody_object: PointerProperty(name="Scanbody", type=bpy.types.Object)


class RMVB_PG_PartRef(PropertyGroup):
    object: PointerProperty(name="Object", type=bpy.types.Object)
    tooth: StringProperty(name="Tooth", default="")


class RMVB_PG_AttachmentRef(PropertyGroup):
    att_name: StringProperty(name="Attachment", default="")
    object: PointerProperty(name="Object", type=bpy.types.Object)
    on_bar: BoolProperty(name="On Bar", default=True)
    on_sleeve: BoolProperty(name="On Sleeve", default=False)
    visuals: CollectionProperty(type=RMVB_PG_PartRef)


class RMVB_PG_props(PropertyGroup):
    # 1-3: doi tuong import
    gingiva_object: PointerProperty(name="Gingiva", type=bpy.types.Object)
    denture_object: PointerProperty(name="Denture-reference", type=bpy.types.Object)
    antagonist_object: PointerProperty(name="Antagonist", type=bpy.types.Object)

    # 4-5: Connection Base + constructionInfo
    connection_index: IntProperty(name="Connection Index", default=0, min=0)
    connection_name: StringProperty(name="Connection Name", default="")
    connection_base: EnumProperty(name="Select Connection Base",
                                  items=enum_connection_base,
                                  get=_connection_get, set=_connection_set)
    construction_file: StringProperty(name="constructionInfo",
                                      subtype='FILE_PATH', default="")
    placed: CollectionProperty(type=RMVB_PG_PlacedConnection)
    place_parts: BoolProperty(
        name="Đặt kèm Analog / Screw / Scanbody",
        description="Tao them cac mesh con lai cua Connection (an) tai cung "
                    "vi tri implant",
        default=False)

    # 6.1 Bar Pillar
    pillars: CollectionProperty(type=RMVB_PG_PartRef)
    pillar_lift: FloatProperty(
        name="Vùng 2 cao lên (mm)",
        description="Extrude vung ho ket noi thang len theo local Z (mac dinh 7 li)",
        default=7.0, min=0.0, unit='LENGTH')
    pillar_equalize: BoolProperty(
        name="Vùng 1 cao bằng Vùng 2 (local)",
        description="Extrude vung lo oc len den cung do cao Z local nhu vung "
                    "ket noi",
        default=True)

    # 6.2 Bar Segment
    bar_line: PointerProperty(name="Bar Line", type=bpy.types.Object)
    bar_segment: PointerProperty(name="Bar Segment", type=bpy.types.Object)
    bar_width: FloatProperty(name="Bề rộng bar (mm)", default=4.0, min=0.1,
                             unit='LENGTH')
    bar_height: FloatProperty(name="Chiều cao bar (mm)", default=3.0, min=0.1,
                              unit='LENGTH')
    bar_clearance: FloatProperty(name="Khe hở với Gingiva (mm)", default=0.0,
                                 unit='LENGTH')

    # 6.3 Top Bar Plane
    top_plane: PointerProperty(name="Top Bar Plane", type=bpy.types.Object)
    top_cutter: PointerProperty(name="Top Bar Block", type=bpy.types.Object)
    cutter_height: FloatProperty(name="Chiều cao khối cắt (mm)", default=20.0,
                                 min=0.1, unit='LENGTH')
    cutter_size: FloatProperty(name="Kích thước khối cắt (mm)", default=120.0,
                               min=1.0, unit='LENGTH')
    cut_mode: EnumProperty(
        name="Kiểu cắt",
        description="DIFFERENCE: phan bar nam trong khoi bi cat bo. "
                    "INTERSECT: giu lai phan nam trong khoi",
        items=[('DIFFERENCE', "Cut bỏ phần trong khối", ""),
               ('INTERSECT', "Giữ phần trong khối", "")],
        default='DIFFERENCE')
    connection_cut_extend: FloatProperty(
        name="Chỗi Connection (mm)",
        description="Extrude 2 vung ho cua Connection ra 2 huong nguoc nhau "
                    "mot khoang nay roi nap kin 2 dau, tao lang tru dao mat de "
                    "cat xuyen hoan toan Bar Segment",
        default=10.0, min=0.1, unit='LENGTH')

    # 6.4 Attachment
    attachment_index: IntProperty(name="Attachment Index", default=0, min=0)
    active_attachment: StringProperty(name="Attachment", default="")
    attachment_name: EnumProperty(name="Select Attachment",
                                  items=enum_attachment,
                                  get=_attachment_get, set=_attachment_set)
    attachments: CollectionProperty(type=RMVB_PG_AttachmentRef)
    group_axis: BoolProperty(
        name="Group Axis Attachment",
        description="Gom cac Attachment da dat duoi mot Empty truc chung de "
                    "di chuyen / xoay cung luc",
        default=False)
    group_axis_topbar: BoolProperty(
        name="Group Axis với Top Bar",
        description="Attachment xoay theo Top Bar Plane va tam cua no luon "
                    "nam tren mat phang (chi khoa translate doc theo Z cua "
                    "Plane, X/Y tu do)",
        default=False)
    apply_attachment_bar: BoolProperty(
        name="Apply attachment on Bar",
        description="Ket hop cac Attachment da dat vao khoi Bar khi Cut Top "
                    "Bar: toggle Add/Remove on Bar = UNION (them) hoac "
                    "DIFFERENCE (khoet lo)",
        default=True)

    # 7 Sleeve Design
    sleeve_offset: FloatProperty(name="Offset bar (mm)", default=0.1, min=0.0,
                                 unit='LENGTH')
    sleeve_thickness: FloatProperty(name="Sleeve thickness (mm)", default=0.5,
                                    min=0.01, unit='LENGTH')
    apply_attachment_sleeve: BoolProperty(
        name="Apply attachment on Sleeve",
        description="Cong don cac Attachment (toggle Add/Remove on Sleeve) vao "
                    "khoi Sleeve",
        default=True)
    sleeve_object: PointerProperty(name="Sleeve", type=bpy.types.Object)

    # 8 Save
    save_dir: StringProperty(name="Thư mục lưu", subtype='DIR_PATH', default="")


# ---------------------------------------------------------------------------
# 1-3. Import Gingiva / Denture-reference / Antagonist (STL, PLY)
# ---------------------------------------------------------------------------
ROLE_COLOR = {
    'GINGIVA': (0.90, 0.45, 0.50, 0.65),
    'DENTURE': (0.35, 0.62, 0.90, 1.00),
    'ANTAGONIST': (0.55, 0.55, 0.55, 1.00),
}
ROLE_OBJECT_NAME = {
    'GINGIVA': "Gingiva",
    'DENTURE': "Denture_Reference",
    'ANTAGONIST': "Antagonist",
}
ROLE_PROPERTY = {
    'GINGIVA': "gingiva_object",
    'DENTURE': "denture_object",
    'ANTAGONIST': "antagonist_object",
}


class RMVB_OT_import_mesh(Operator, ImportHelper):
    """Import file STL/PLY va gan vao dung vai tro trong thiet ke"""
    bl_idname = "rmvb.import_mesh"
    bl_label = "Import STL/PLY"
    bl_options = {'REGISTER', 'UNDO'}

    filepath: StringProperty(subtype='FILE_PATH', default="")
    files: CollectionProperty(type=bpy.types.OperatorFileListElement)
    directory: StringProperty(subtype='DIR_PATH', default="")
    filter_glob: StringProperty(default="*.stl;*.ply;*.STL;*.PLY",
                                options={'HIDDEN'})

    role: EnumProperty(
        name="Role",
        items=[('GINGIVA', "Gingiva", ""),
               ('DENTURE', "Denture-reference", ""),
               ('ANTAGONIST', "Antagonist", "")],
        default='GINGIVA')

    def execute(self, context):
        props = context.scene.rmvb
        paths = []
        for item in self.files:
            full = os.path.join(self.directory, item.name) if self.directory else item.name
            if os.path.exists(full):
                paths.append(full)
        single = bpy.path.abspath(self.filepath)
        if not paths and single and os.path.exists(single):
            paths.append(single)
        if not paths:
            self.report({'ERROR'}, "Chon file STL/PLY truoc")
            return {'CANCELLED'}

        coll = ensure_collection(COL_IMPORT)
        created = []
        for path in paths:
            try:
                mesh = mesh_from_file(path)
            except Exception as exc:
                self.report({'WARNING'}, "Bo qua %s: %s"
                            % (os.path.basename(path), exc))
                continue
            obj = bpy.data.objects.new(
                ROLE_OBJECT_NAME[self.role] if len(paths) == 1
                else os.path.splitext(os.path.basename(path))[0],
                mesh.copy())
            coll.objects.link(obj)
            created.append(obj)
        if not created:
            self.report({'ERROR'}, "Khong import duoc file nao")
            return {'CANCELLED'}

        if len(created) > 1:
            obj = join_objects(created, ROLE_OBJECT_NAME[self.role], coll)
        else:
            obj = created[0]
            obj.name = ROLE_OBJECT_NAME[self.role]
        set_color(obj, ROLE_COLOR[self.role])
        setattr(props, ROLE_PROPERTY[self.role], obj)
        activate(context, obj)
        self.report({'INFO'}, "Da import %d file -> %s" % (len(paths), obj.name))
        return {'FINISHED'}


# ---------------------------------------------------------------------------
# 5. Place Connection - doc .constructionInfo va dat theo toa do XML
# ---------------------------------------------------------------------------
def clear_placed_connections(context, remove_pillars=False):
    props = context.scene.rmvb
    for item in list(props.placed):
        for field in ("base_object", "analog_object", "screw_object",
                      "scanbody_object"):
            remove_object(getattr(item, field))
    props.placed.clear()
    if remove_pillars:
        for ref in list(props.pillars):
            remove_object(ref.object)
        props.pillars.clear()


def current_connection_name(props):
    name = props.connection_name
    names = get_connection_items()
    if name in names:
        return name
    if names:
        return names[min(props.connection_index, len(names) - 1)]
    return ""


class RMVB_OT_place_connection(Operator, ImportHelper):
    """Doc file constructionInfo va dat Implant Connection theo dung toa do XML"""
    bl_idname = "rmvb.place_connection"
    bl_label = "Place Connection"
    bl_options = {'REGISTER', 'UNDO'}

    filepath: StringProperty(subtype='FILE_PATH', default="")
    filter_glob: StringProperty(default="*.constructionInfo;*.xml",
                                options={'HIDDEN'})

    def execute(self, context):
        props = context.scene.rmvb
        path = bpy.path.abspath(self.filepath)
        if not path or not os.path.exists(path):
            self.report({'ERROR'}, "Khong tim thay file constructionInfo")
            return {'CANCELLED'}

        lib_name = current_connection_name(props)
        if not lib_name:
            self.report({'ERROR'},
                        "Chua chon Connection Base trong thu vien Dental-Lib")
            return {'CANCELLED'}

        base_path = lib_connection_asset(lib_name, "base")
        if not base_path or not os.path.exists(base_path):
            self.report({'ERROR'}, "Connection '%s' chua co mesh Base" % lib_name)
            return {'CANCELLED'}

        try:
            implants = parse_construction_info(path)
        except Exception as exc:
            self.report({'ERROR'}, "Loi doc XML: %s" % exc)
            return {'CANCELLED'}
        if not implants:
            self.report({'ERROR'},
                        "File khong chua implant nao (ImplantType + MatrixImplantGeometry)")
            return {'CANCELLED'}

        try:
            base_mesh = mesh_from_file(base_path)
        except Exception as exc:
            self.report({'ERROR'}, "Loi doc mesh Base: %s" % exc)
            return {'CANCELLED'}

        part_meshes = {}
        if props.place_parts:
            for slot in ("analog", "screw", "scanbody"):
                asset = lib_connection_asset(lib_name, slot)
                if asset and os.path.exists(asset):
                    try:
                        part_meshes[slot] = mesh_from_file(asset)
                    except Exception as exc:
                        self.report({'WARNING'}, "%s: %s" % (slot, exc))

        clear_placed_connections(context, remove_pillars=True)
        coll = ensure_collection(COL_CONNECTION)
        for implant in implants:
            tooth = str(implant["tooth"])
            matrix = implant["matrix"]
            obj = object_from_mesh("Conn_%s_Base" % tooth, base_mesh, coll, matrix)
            set_color(obj, (0.72, 0.74, 0.78, 1.0))
            item = props.placed.add()
            item.tooth = tooth
            item.lib_name = lib_name
            item.base_object = obj
            for slot, field in (("analog", "analog_object"),
                                ("screw", "screw_object"),
                                ("scanbody", "scanbody_object")):
                mesh = part_meshes.get(slot)
                if mesh is None:
                    continue
                part = object_from_mesh("Conn_%s_%s" % (tooth, slot.capitalize()),
                                        mesh, coll, matrix)
                part.hide_set(True)
                setattr(item, field, part)

        props.construction_file = path
        props.connection_name = lib_name
        self.report({'INFO'}, "Da dat %d Connection (%s) tu %s"
                    % (len(implants), lib_name, os.path.basename(path)))
        return {'FINISHED'}


# ---------------------------------------------------------------------------
# 6.1 Bar Pillar
# ---------------------------------------------------------------------------
def extrude_loop_to(bm, loop, target_z):
    """Extrude vong bien thang len theo local Z den do cao target_z."""
    old_count = len(bm.verts)
    rim = list(loop["verts"])
    result = bmesh.ops.extrude_edge_only(bm, edges=loop["edges"])
    new_verts = [g for g in result['geom']
                 if isinstance(g, bmesh.types.BMVert) and g.index >= old_count]
    for vert in new_verts:
        vert.co.z = target_z
    new_faces = [g for g in result['geom'] if isinstance(g, bmesh.types.BMFace)]
    return new_verts, new_faces, rim


def bridge_extruded_rims(bm, new_verts):
    """Noi cac mieng extrude lai thanh mat kin.

    Sau khi extrude 2 vung ho len theo local Z, chi con lai 2 vong bien o
    dinh. bridge_loops tao mat phang noi 2 vong do -> toan bo mesh thanh
    solid kin (manifold), khong can nap day.
    """
    keep = set(new_verts)
    rims = [e for e in bm.edges
            if e.is_boundary and all(v in keep for v in e.verts)]
    if len(rims) < 2:
        return False
    try:
        bmesh.ops.bridge_loops(bm, edges=rims)
    except Exception:
        try:
            bmesh.ops.edgenet_fill(bm, edges=rims)
        except Exception:
            return False
    left = [e for e in bm.edges if e.is_boundary and all(v in keep for v in e.verts)]
    if left:
        try:
            bmesh.ops.holes_fill(bm, edges=left)
        except Exception:
            pass
    return not [e for e in bm.edges if e.is_boundary]


def build_pillar_mesh(base_obj, lift, equalize):
    """Tao mesh Bar Pillar tu mesh Connection Base - KIN (solid manifold).

    Vung ho duoi (ket noi) extrude len `lift` mm, vung ho tren (lo oc) extrude
    len toi cung do cao (neu equalize) hoac cung `lift` mm; hai mieng extrude
    sau do duoc NOI lai thanh mot solid kin.
    """
    mesh = base_obj.data.copy()
    mesh.name = base_obj.name + ".pillar"
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bm.verts.ensure_lookup_table()
    loops = boundary_loops(bm)
    info = {"loops": len(loops), "skipped": [], "closed": False, "volume": 0.0}
    if not loops:
        bm.free()
        return mesh, info

    ordered = sorted(loops, key=lambda item: item["z"])
    lower = ordered[0]                                   # vung 2: ho ket noi
    upper = ordered[-1] if len(ordered) > 1 else None    # vung 1: lo oc
    for extra in ordered[1:-1]:
        info["skipped"].append(round(extra["z"], 3))

    top_z = lower["z"] + lift
    new_out, _faces_out, rim_out = extrude_loop_to(bm, lower, top_z)
    info["outside_top"] = top_z
    screw_verts = []
    new_all = list(new_out)
    if upper is not None:
        target = top_z if equalize else upper["z"] + lift
        new_sc, _faces_sc, rim_sc = extrude_loop_to(bm, upper, target)
        screw_verts = new_sc + rim_sc
        new_all += new_sc
        info["screw_top"] = target
    else:
        info["screw_top"] = None

    info["closed"] = bridge_extruded_rims(bm, new_all)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-7)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    try:
        volume = bm.calc_volume(signed=True)
        if volume < 0:
            bmesh.ops.reverse_faces(bm, faces=bm.faces)
            volume = -volume
        info["volume"] = volume
    except Exception:
        pass
    info["closed"] = info["closed"] and not any(e.is_boundary for e in bm.edges)
    pillar_verts = new_out + rim_out
    screw_index = [v.index for v in screw_verts]
    try:
        pillar_index = [v.index for v in pillar_verts]
    except ValueError:                       # vert bi gop khi remove_doubles
        bm.verts.ensure_lookup_table()
        pillar_index = [v.index for v in bm.verts
                        if v.co.z > top_z - 1e-6 or abs(v.co.z - lower["z"]) < 1e-6]
        screw_index = []
    bm.to_mesh(mesh)
    bm.free()

    info[VG_OUTSIDE] = pillar_index
    info[VG_SCREW] = screw_index
    mesh.validate()
    mesh.update()
    return mesh, info


class RMVB_OT_create_bar_pillar(Operator):
    """Tao Bar Pillar tu cac Connection Base: extrude 2 vung ho thang len local Z"""
    bl_idname = "rmvb.create_bar_pillar"
    bl_label = "Create Bar Pillar"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        props = context.scene.rmvb
        if not props.placed:
            self.report({'ERROR'}, "Chua dat Connection nao (bam Place Connection)")
            return {'CANCELLED'}
        coll = ensure_collection(COL_PILLAR)
        for ref in list(props.pillars):
            remove_object(ref.object)
        props.pillars.clear()

        made = 0
        notes = []
        all_closed = True
        for item in props.placed:
            base = item.base_object
            if base is None or base.type != 'MESH':
                continue
            try:
                mesh, info = build_pillar_mesh(base, props.pillar_lift,
                                               props.pillar_equalize)
            except Exception as exc:
                self.report({'WARNING'}, "Rang %s: %s" % (item.tooth, exc))
                continue
            obj = bpy.data.objects.new("BarPillar_%s" % item.tooth, mesh)
            coll.objects.link(obj)
            obj.matrix_world = base.matrix_world.copy()
            for group in (VG_OUTSIDE, VG_SCREW):
                if obj.vertex_groups.get(group) is None:
                    obj.vertex_groups.new(name=group)
                indices = info.get(group) or []
                if indices:
                    obj.vertex_groups[group].add(indices, 1.0, 'REPLACE')
            set_color(obj, (0.85, 0.65, 0.25, 1.0))
            obj["rmvb_role"] = "PILLAR"
            obj["rmvb_tooth"] = item.tooth
            ref = props.pillars.add()
            ref.object = obj
            ref.tooth = item.tooth
            made += 1
            if not info.get("closed"):
                all_closed = False
                notes.append("rang %s pillar khong kin" % item.tooth)
            if info.get("loops", 0) != 2:
                notes.append("rang %s co %d vung ho" % (item.tooth, info["loops"]))
        if not made:
            self.report({'ERROR'}, "Khong tao duoc Bar Pillar nao")
            return {'CANCELLED'}
        message = "Da tao %d Bar Pillar (vung 2 cao %g mm, solid kin)" % (
            made, props.pillar_lift)
        if not all_closed:
            message = "Da tao %d Bar Pillar (vung 2 cao %g mm, CHUA kin)" % (
                made, props.pillar_lift)
        if notes:
            self.report({'WARNING'},
                        "Khong dung 2 vung ho: " + "; ".join(notes))
        self.report({'INFO'}, message)
        return {'FINISHED'}


def select_vertex_group(context, group_name):
    """Chon dinh thuoc vertex group (Edit Mode hoac Object Mode)."""
    targets = [ob for ob in context.selected_objects
               if ob.type == 'MESH' and ob.vertex_groups.get(group_name)]
    if not targets:
        active = context.active_object
        if active is not None and active.type == 'MESH':
            targets = [active]
    if not targets:
        return -1
    count = 0
    if context.mode == 'EDIT_MESH':
        for obj in targets:
            group = obj.vertex_groups.get(group_name)
            if group is None:
                continue
            try:
                bm = bmesh.from_edit_mesh(obj.data)
            except Exception:
                continue
            deform = bm.verts.layers.deform.verify()
            for vert in bm.verts:
                state = vert[deform].get(group.index, 0.0) > 0.5
                if vert.select != state:
                    vert.select_set(state)
                if state:
                    count += 1
            bmesh.update_edit_mesh(obj.data, destructive=False)
    else:
        for obj in targets:
            group = obj.vertex_groups.get(group_name)
            bpy.ops.object.select_all(action='DESELECT')
            activate(context, obj)
            for vert in obj.data.vertices:
                state = any(g.group == group.index and g.weight > 0.5
                            for g in vert.groups)
                vert.select = state
                if state:
                    count += 1
            obj.data.update()
    return count


class RMVB_OT_edit_bar_pillar(Operator):
    """Vao Edit Mode (transform orientation Local) de chinh Bar Pillar"""
    bl_idname = "rmvb.edit_bar_pillar"
    bl_label = "Edit Bar Pillar"

    def execute(self, context):
        props = context.scene.rmvb
        pillars = [r.object for r in props.pillars if r.object is not None]
        if not pillars:
            self.report({'ERROR'}, "Chua co Bar Pillar. Bam Create Bar Pillar truoc")
            return {'CANCELLED'}
        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        bpy.ops.object.select_all(action='DESELECT')
        for obj in pillars:
            obj.hide_set(False)
            obj.select_set(True)
        context.view_layer.objects.active = pillars[0]
        bpy.ops.object.mode_set(mode='EDIT')
        use_local_orientation(context)
        self.report({'INFO'}, "Edit Bar Pillar - Transform Orientation: Local")
        return {'FINISHED'}


class RMVB_OT_select_pillar_region(Operator):
    """Chon vung ho tren (Screw) hoac vung ho duoi (Outside) cua Bar Pillar"""
    bl_idname = "rmvb.select_pillar_region"
    bl_label = "Select Pillar Region"

    region: EnumProperty(
        name="Region",
        items=[('SCREWS', "Select Screws", "Vung ho tren - lo oc"),
               ('OUTSIDE', "Select Outside", "Vung ho duoi - ket noi")],
        default='SCREWS')

    def execute(self, context):
        group = VG_SCREW if self.region == 'SCREWS' else VG_OUTSIDE
        found = select_vertex_group(context, group)
        if found < 0:
            self.report({'ERROR'},
                        "Khong tim thay vung '%s'. Vao Edit Bar Pillar truoc." % group)
            return {'CANCELLED'}
        self.report({'INFO'}, "Da chon %d dinh thuoc vung %s" % (found, group))
        return {'FINISHED'}


class RMVB_OT_exit_edit(Operator):
    """Thoat Edit Mode ve Object Mode"""
    bl_idname = "rmvb.exit_edit"
    bl_label = "Exit Edit"

    def execute(self, context):
        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        self.report({'INFO'}, "Da ve Object Mode")
        return {'FINISHED'}


# ---------------------------------------------------------------------------
# 6.2 Bar Segment - ve line snap tren be mat Gingiva va Sweep thanh bar
# ---------------------------------------------------------------------------
def polyline_from_object(obj):
    """Lay danh sach toa do world theo thu tu di doc duong line."""
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.verts.ensure_lookup_table()
    points = []
    if not bm.verts:
        bm.free()
        return points, False
    ends = [v for v in bm.verts if len(v.link_edges) <= 1]
    closed = not ends
    start = ends[0] if ends else bm.verts[0]
    visited = set()
    current = start
    while current is not None:
        visited.add(current.index)
        points.append(obj.matrix_world @ current.co)
        nxt = None
        for edge in current.link_edges:
            other = edge.other_vert(current)
            if other.index not in visited:
                nxt = other
                break
        if nxt is None and closed and len(points) > 1:
            for edge in current.link_edges:
                other = edge.other_vert(current)
                if other.index == start.index:
                    points.append(points[0])
                    break
            nxt = None
        current = nxt
    bm.free()
    return points, closed


def sweep_polyline(points, width, height, closed=False, up=None):
    """Tao mesh dang thanh co tiet dien nhat (width x height) di theo points."""
    bm = bmesh.new()
    if len(points) < 2:
        bm.free()
        return None
    up = up if up is not None else Vector((0.0, 0.0, 1.0))
    count = len(points)
    rings = []
    for index, point in enumerate(points):
        if closed:
            prev_p = points[(index - 1) % count]
            next_p = points[(index + 1) % count]
        else:
            prev_p = points[index - 1] if index > 0 else points[index]
            next_p = points[index + 1] if index + 1 < count else points[index]
        tangent = next_p - prev_p
        if tangent.length < 1e-6:
            tangent = next_p - point if (next_p - point).length > 1e-6 else Vector((0, 1, 0))
        tangent.normalize()
        side = up.cross(tangent)
        if side.length < 1e-6:
            side = Vector((1.0, 0.0, 0.0))
        side.normalize()
        normal = tangent.cross(side)
        if normal.length < 1e-6:
            normal = Vector((0.0, 0.0, 1.0))
        normal.normalize()
        hw = width * 0.5
        ring = [
            point - side * hw,
            point + side * hw,
            point + side * hw + normal * height,
            point - side * hw + normal * height,
        ]
        rings.append([bm.verts.new(co) for co in ring])

    def bridge(a, b):
        for i in range(4):
            j = (i + 1) % 4
            try:
                bm.faces.new((a[i], a[j], b[j], b[i]))
            except ValueError:
                pass

    for i in range(len(rings) - 1):
        bridge(rings[i], rings[i + 1])
    if closed:
        bridge(rings[-1], rings[0])
    else:
        try:
            bm.faces.new(tuple(reversed(rings[0])))
        except ValueError:
            pass
        try:
            bm.faces.new(tuple(rings[-1]))
        except ValueError:
            pass
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    mesh = bpy.data.meshes.new("Rmvb_sweep")
    bm.to_mesh(mesh)
    bm.free()
    return mesh


class RMVB_OT_create_bar_line(Operator):
    """Tao duong line bat dau tu 3D Cursor va ve theo be mat Gingiva"""
    bl_idname = "rmvb.create_bar_line"
    bl_label = "Draw Line Bar"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        props = context.scene.rmvb
        target = props.gingiva_object
        if target is None or target.type != 'MESH':
            self.report({'ERROR'}, "Can import Gingiva truoc khi ve line")
            return {'CANCELLED'}
        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        old = props.bar_line
        if old is not None and old.name in bpy.data.objects:
            remove_object(old)
        coll = ensure_collection(COL_SEGMENT)
        start = context.scene.cursor.location.copy()
        hit, local, _n, _i = target.closest_point_on_mesh(
            target.matrix_world.inverted() @ start)
        if hit:
            start = target.matrix_world @ local
        mesh = bpy.data.meshes.new(OBJ_LINE)
        mesh.from_pydata([start], [], [])
        mesh.update()
        line = bpy.data.objects.new(OBJ_LINE, mesh)
        coll.objects.link(line)
        props.bar_line = line
        set_color(line, (1.0, 0.35, 0.05, 1.0))
        line.display_type = 'WIRE'
        activate(context, line)
        try:
            bpy.ops.rmvb.draw_bar_line('INVOKE_DEFAULT')
        except Exception as exc:
            self.report({'WARNING'}, "Khong mo duoc che do ve: %s" % exc)
        return {'FINISHED'}


class RMVB_OT_draw_bar_line(Operator):
    """Ve duong bar theo con tro: E/click trai = them diem NAM TREN be mat
    Gingiva, Backspace = xoa diem cuoi, F = noi vong, Enter/Esc = xong"""
    bl_idname = "rmvb.draw_bar_line"
    bl_label = "Ve duong bar (snap Gingiva)"

    def _find_view(self, context):
        area = view_3d_area(context)
        if area is None:
            return None, None, None
        region = None
        for reg in area.regions:
            if reg.type == 'WINDOW':
                region = reg
        return area, region, area.spaces.active.region_3d

    def _raycast(self, context, mouse_x, mouse_y):
        """Vi tri world tren be mat Gingiva duoi con tro (hoac None)."""
        if self.region is None or self.rv3d is None:
            return None
        coord = (mouse_x - self.region.x, mouse_y - self.region.y)
        if (coord[0] < 0 or coord[1] < 0 or coord[0] > self.region.width
                or coord[1] > self.region.height):
            return None
        direction = view3d_utils.region_2d_to_vector_3d(self.region, self.rv3d, coord)
        origin = view3d_utils.region_2d_to_origin_3d(self.region, self.rv3d, coord)
        depsgraph = context.evaluated_depsgraph_get()
        result, location, _n, _f, _o, _m = context.scene.ray_cast(
            depsgraph, origin, direction)
        if not result:
            return None
        target = self.target
        hit, local, _n2, _i = target.closest_point_on_mesh(
            target.matrix_world.inverted() @ location)
        return (target.matrix_world @ local) if hit else location

    def _write(self):
        self.bm.to_mesh(self.line.data)
        self.bm.free()
        self.line.data.update()
        self.bm = bmesh.new()
        self.bm.from_mesh(self.line.data)
        self.bm.verts.ensure_lookup_table()

    def _add_point(self, context, event):
        world = self._raycast(context, event.mouse_x, event.mouse_y)
        if world is None:
            return
        local = self.line.matrix_world.inverted() @ world
        vert = self.bm.verts.new(local)
        if self.tip is not None and self.tip.is_valid:
            try:
                self.bm.edges.new((self.tip, vert))
            except ValueError:
                pass
        self.tip = vert
        self._write()
        if self.area:
            self.area.tag_redraw()

    def _remove_last(self, context):
        if self.tip is None or not self.tip.is_valid or len(self.bm.verts) <= 1:
            return
        previous = None
        for edge in self.tip.link_edges:
            previous = edge.other_vert(self.tip)
            break
        try:
            self.bm.verts.remove(self.tip)
        except Exception:
            return
        self.bm.verts.ensure_lookup_table()
        if previous is not None and previous.is_valid:
            self.tip = previous
        else:
            self.tip = self.bm.verts[-1] if self.bm.verts else None
        self._write()
        if self.area:
            self.area.tag_redraw()

    def _draw_cb(self):
        if self.hit_world is None or self.tip is None or not self.tip.is_valid:
            return
        try:
            import gpu
            from gpu_extras.batch import batch_for_shader
        except Exception:
            return
        tip_world = self.line.matrix_world @ self.tip.co
        shader = gpu.shader.from_builtin('UNIFORM_COLOR')
        gpu.state.blend_set('ALPHA')
        gpu.state.depth_test_set('NONE')
        gpu.state.line_width_set(2.0)
        gpu.state.point_size_set(9.0)
        try:
            batch = batch_for_shader(shader, 'LINES',
                                     {"pos": [tip_world, self.hit_world]})
            shader.uniform_float("color", (1.0, 0.8, 0.1, 0.9))
            batch.draw(shader)
            point = batch_for_shader(shader, 'POINTS', {"pos": [self.hit_world]})
            shader.uniform_float("color", (1.0, 0.3, 0.1, 1.0))
            point.draw(shader)
        except Exception:
            pass
        finally:
            gpu.state.line_width_set(1.0)
            gpu.state.point_size_set(1.0)
            gpu.state.depth_test_set('LESS_EQUAL')
            gpu.state.blend_set('NONE')

    def invoke(self, context, event):
        props = context.scene.rmvb
        target = props.gingiva_object
        line = props.bar_line
        if target is None or target.type != 'MESH':
            self.report({'ERROR'}, "Can import Gingiva truoc khi ve line")
            return {'CANCELLED'}
        if line is None or line.name not in bpy.data.objects:
            self.report({'ERROR'}, "Chua co line. Bam Draw Line Bar truoc")
            return {'CANCELLED'}
        self.target = target
        self.line = line
        self.hit_world = None
        self.handle = None
        self.area, self.region, self.rv3d = self._find_view(context)
        if self.region is None or self.rv3d is None:
            self.report({'ERROR'}, "Khong tim thay vung 3D View")
            return {'CANCELLED'}
        self.bm = bmesh.new()
        self.bm.from_mesh(line.data)
        self.bm.verts.ensure_lookup_table()
        ends = [v for v in self.bm.verts if len(v.link_edges) <= 1]
        self.tip = ends[-1] if ends else (
            self.bm.verts[-1] if self.bm.verts else None)
        try:
            self.handle = bpy.types.SpaceView3D.draw_handler_add(
                self._draw_cb, (), 'WINDOW', 'POST_VIEW')
        except Exception:
            self.handle = None
        context.window_manager.modal_handler_add(self)
        self._status(context, True)
        return {'RUNNING_MODAL'}

    def _status(self, context, on=True):
        try:
            if on:
                context.workspace.status_text_set(
                    "Ve duong bar | E/Click trai: them diem tren Gingiva | "
                    "Backspace: xoa diem cuoi | F: noi vong | Enter/Esc: xong")
            else:
                context.workspace.status_text_set(None)
        except Exception:
            pass

    def _finish(self, context):
        self._status(context, False)
        if self.handle is not None:
            try:
                bpy.types.SpaceView3D.draw_handler_remove(self.handle, 'WINDOW')
            except Exception:
                pass
            self.handle = None
        try:
            self.bm.free()
        except Exception:
            pass
        if self.area:
            self.area.tag_redraw()

    def modal(self, context, event):
        if event.value == 'PRESS' and (
                event.type == 'E' or (event.type == 'LEFTMOUSE' and not event.alt)):
            self._add_point(context, event)
            return {'RUNNING_MODAL'}
        if event.value == 'PRESS' and event.type in {'BACK_SPACE', 'DEL'}:
            self._remove_last(context)
            return {'RUNNING_MODAL'}
        if event.value == 'PRESS' and event.type == 'F':
            bpy.ops.rmvb.close_bar_line()
            return {'RUNNING_MODAL'}
        if event.value == 'PRESS' and event.type in {'RET', 'NUMPAD_ENTER', 'SPACE',
                                                     'ESC', 'RIGHTMOUSE'}:
            self._finish(context)
            self.report({'INFO'}, "Line bar co %d diem - bam Create Bar Segment"
                        % len(self.line.data.vertices))
            return {'FINISHED'}
        if event.type == 'MOUSEMOVE':
            self.hit_world = self._raycast(context, event.mouse_x, event.mouse_y)
            if self.area:
                self.area.tag_redraw()
            return {'RUNNING_MODAL'}
        if (event.type in {'MIDDLEMOUSE', 'WHEELUPMOUSE', 'WHEELDOWNMOUSE',
                           'WHEELINMOUSE', 'WHEELOUTMOUSE'}
                or (event.type == 'LEFTMOUSE' and event.alt)
                or (event.type.startswith('NUMPAD_')
                    and event.type != 'NUMPAD_ENTER')):
            return {'PASS_THROUGH'}
        return {'RUNNING_MODAL'}


class RMVB_OT_close_bar_line(Operator):
    """Noi diem dau va diem cuoi cua line thanh vong kin"""
    bl_idname = "rmvb.close_bar_line"
    bl_label = "Noi vong line bar"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        props = context.scene.rmvb
        line = props.bar_line
        if line is None or line.name not in bpy.data.objects:
            self.report({'ERROR'}, "Chua co line bar")
            return {'CANCELLED'}
        bm = bmesh.new()
        bm.from_mesh(line.data)
        ends = [v for v in bm.verts if len(v.link_edges) <= 1]
        if len(ends) < 2:
            bm.free()
            self.report({'INFO'}, "Line da kin vong")
            return {'FINISHED'}
        try:
            bm.edges.new((ends[0], ends[-1]))
            bm.to_mesh(line.data)
            line.data.update()
        except ValueError:
            pass
        bm.free()
        self.report({'INFO'}, "Da noi vong line bar")
        return {'FINISHED'}


class RMVB_OT_create_bar_segment(Operator):
    """Tao Bar Segment: thanh co tiet chu nhat di theo line bar tren Gingiva"""
    bl_idname = "rmvb.create_bar_segment"
    bl_label = "Create Bar Segment"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        props = context.scene.rmvb
        line = props.bar_line
        if line is None or line.name not in bpy.data.objects:
            self.report({'ERROR'}, "Chua co line bar. Bam Draw Line Bar truoc")
            return {'CANCELLED'}
        points, closed = polyline_from_object(line)
        if len(points) < 2:
            self.report({'ERROR'}, "Line bar can it nhat 2 diem")
            return {'CANCELLED'}

        # Up = truc Z trung binh cua cac Bar Pillar (neu co) de bar doc dung
        # huong khung; nguoi dung co the xoay lai trong Edit Mode.
        up = Vector((0.0, 0.0, 1.0))
        pillars = [r.object for r in props.pillars if r.object is not None]
        if pillars:
            total = Vector((0.0, 0.0, 0.0))
            for pillar in pillars:
                total += pillar.matrix_world.to_quaternion() @ Vector((0, 0, 1))
            if total.length > 1e-6:
                up = total.normalized()

        clearance = props.bar_clearance
        target = props.gingiva_object
        if clearance and target is not None and target.type == 'MESH':
            moved = []
            inverse = target.matrix_world.inverted()
            for point in points:
                hit, local, normal, _i = target.closest_point_on_mesh(inverse @ point)
                if hit:
                    world = target.matrix_world @ local
                    direction = target.matrix_world.to_quaternion() @ normal
                    if direction.length > 1e-6:
                        direction.normalize()
                    moved.append(world + direction * clearance)
                else:
                    moved.append(point)
            points = moved

        mesh = sweep_polyline(points, props.bar_width, props.bar_height, closed, up)
        if mesh is None:
            self.report({'ERROR'}, "Khong tao duoc Bar Segment")
            return {'CANCELLED'}
        coll = ensure_collection(COL_SEGMENT)
        old = props.bar_segment
        if old is not None and old.name in bpy.data.objects:
            remove_object(old)
        obj = bpy.data.objects.new(OBJ_SEGMENT, mesh)
        coll.objects.link(obj)
        set_color(obj, (0.20, 0.65, 0.95, 1.0))
        obj["rmvb_role"] = "SEGMENT"
        props.bar_segment = obj
        activate(context, obj)
        self.report({'INFO'}, "Da tao Bar Segment (%d miet tiet dien %g x %g mm)"
                    % (len(points), props.bar_width, props.bar_height))
        return {'FINISHED'}


class RMVB_OT_edit_bar_segment(Operator):
    """Vao Edit Mode (transform orientation Local) de chinh Bar Segment"""
    bl_idname = "rmvb.edit_bar_segment"
    bl_label = "Edit Bar Segment"

    def execute(self, context):
        props = context.scene.rmvb
        obj = props.bar_segment
        if obj is None or obj.name not in bpy.data.objects:
            self.report({'ERROR'},
                        "Chua co Bar Segment. Bam Create Bar Segment truoc")
            return {'CANCELLED'}
        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        bpy.ops.object.select_all(action='DESELECT')
        obj.hide_set(False)
        obj.select_set(True)
        context.view_layer.objects.active = obj
        bpy.ops.object.mode_set(mode='EDIT')
        use_local_orientation(context)
        self.report({'INFO'}, "Edit Bar Segment - Transform Orientation: Local")
        return {'FINISHED'}




# ---------------------------------------------------------------------------
# 6.3 Top Bar Plane - mat phang dieu khien khoi cat (an)
# ---------------------------------------------------------------------------
def world_copy(obj, name, coll):
    """Ban sao object cung toa do world (mesh local duoc copy)."""
    copy = bpy.data.objects.new(name, obj.data.copy())
    coll.objects.link(copy)
    copy.matrix_world = obj.matrix_world.copy()
    return copy


def cap_boundary(bm, edges):
    """Nap kin mot vong bien (danh sach canh) bang 1 mat n-gon."""
    verts = ordered_loop_verts(edges)
    if len(verts) > 1 and verts[0] is verts[-1]:
        verts = verts[:-1]
    if len(verts) < 3:
        return False
    try:
        bm.faces.new(verts)
        return True
    except ValueError:
        try:
            bmesh.ops.holes_fill(bm, edges=edges)
            return not any(e.is_boundary for e in edges)
        except Exception:
            return False


def connection_cut_solid(base, extend, name, coll, flip=True):
    """Khoi cat lay tu Connection Base (diem a).

    Extrude 2 vung ho ra 2 HUONG NGUOC nhau `extend` mm (vung ket noi xuong
    duoi, vung lo oc len tren), nap kin 2 dau extrude -> lang tru kin bao tron
    than Connection, roi DAO MAT de DIFFERENCE cat het phan Segment xuyen qua.
    """
    copy = world_copy(base, name, coll)
    bm = bmesh.new()
    bm.from_mesh(copy.data)
    loops = boundary_loops(bm)
    if loops:
        ordered = sorted(loops, key=lambda item: item["z"])
        targets = [(ordered[0], ordered[0]["z"] - extend)]
        if len(ordered) > 1:
            targets.append((ordered[-1], ordered[-1]["z"] + extend))
        for loop, target_z in targets:
            new_verts, _faces, _rim = extrude_loop_to(bm, loop, target_z)
            keep = set(new_verts)
            rims = [e for e in bm.edges
                    if e.is_boundary and all(v in keep for v in e.verts)]
            if not cap_boundary(bm, rims):
                bmesh.ops.holes_fill(bm, edges=rims)
        left = [e for e in bm.edges if e.is_boundary]
        if left:
            bmesh.ops.holes_fill(bm, edges=left)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        if flip:
            bmesh.ops.reverse_faces(bm, faces=bm.faces)
    bm.to_mesh(copy.data)
    bm.free()
    copy.data.update()
    return copy


def cut_segment_by_connections(segment, bases, extend, name, coll, flip=True):
    """Bar Segment - (moi Connection dao mat) -> tra ve ban da cat."""
    ws = world_copy(segment, name, coll)
    for base in bases:
        if base is None or base.type != 'MESH':
            continue
        operand = connection_cut_solid(base, extend, base.name + ".neg", coll, flip)
        boolean_objects(ws, [operand], 'DIFFERENCE')
        remove_object(operand)
    return ws


def fill_holes(obj, relax=1e-6):
    """Lap kin cac vung mo cua mesh de boolean solver ra khoi solid hop le.

    Neu chi co 2 vong bien gan dong phang va dong tam (thuong la 2 rim cua
    thanh wall) thi bridge thanh vong xuyen tam; nguoi dung lap day tung vong.
    Cuoi cung dao normal neu khoi am (normal quay vao trong).
    """
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    loops = boundary_loops(bm)
    if len(loops) == 2:
        dz = abs(loops[0]["z"] - loops[1]["z"])
        c0 = sum((v.co for v in loops[0]["verts"]), Vector()) / len(loops[0]["verts"])
        c1 = sum((v.co for v in loops[1]["verts"]), Vector()) / len(loops[1]["verts"])
        radial = (c0 - c1).length
        if dz <= 0.05 and radial <= 0.05:
            edges = [e for loop in loops for e in loop["edges"]]
            try:
                bmesh.ops.bridge_loops(bm, edges=edges, use_disks=False)
            except Exception:
                pass
    boundary = [e for e in bm.edges if e.is_boundary]
    filled = False
    if boundary:
        try:
            bmesh.ops.holes_fill(bm, edges=boundary, sides=0)
            filled = True
        except Exception:
            pass
        left = [e for e in bm.edges if e.is_boundary]
        if left:
            try:
                bmesh.ops.triangle_fill(bm, use_beauty=True, edges=left)
                filled = True
            except Exception:
                pass
    if filled:
        try:
            bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=relax)
        except Exception:
            pass
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    try:
        if bm.calc_volume(signed=True) < 0:
            bmesh.ops.reverse_faces(bm, faces=bm.faces)
    except Exception:
        pass
    bm.to_mesh(obj.data)
    bm.free()
    if filled:
        # validate() co the thay doi topology nen chi dung khi thuc su lap lo
        obj.data.validate()
    obj.data.update()
    return obj


def closed_copy(obj, name, coll):
    """Ban sao da lap kin (manifold) - dung lam operand cho boolean."""
    return fill_holes(world_copy(obj, name, coll))


def design_objects(context):
    """Moi object tham gia khoi bar (pillar + segment)."""
    props = context.scene.rmvb
    objs = [r.object for r in props.pillars if r.object is not None]
    if props.bar_segment is not None and props.bar_segment.name in bpy.data.objects:
        objs.append(props.bar_segment)
    return objs


def _bbox_corners(objs):
    depsgraph = bpy.context.evaluated_depsgraph_get()
    corners = []
    for obj in objs:
        evaluated = obj.evaluated_get(depsgraph)
        corners.extend(evaluated.matrix_world @ Vector(c) for c in evaluated.bound_box)
    return corners


def objects_top_z(objs):
    corners = _bbox_corners(objs)
    return max(co.z for co in corners) if corners else 0.0


def bar_center(objs):
    corners = _bbox_corners(objs)
    if not corners:
        return Vector((0.0, 0.0, 0.0))
    total = Vector((0.0, 0.0, 0.0))
    for corner in corners:
        total += corner
    return total / len(corners)


class RMVB_OT_create_top_bar_plane(Operator):
    """Tao mat phang Top Bar + khoi lop (an) bi khoa toa do theo mat phang"""
    bl_idname = "rmvb.create_top_bar_plane"
    bl_label = "Create Top Bar Plane"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        props = context.scene.rmvb
        objs = design_objects(context)
        if not objs:
            self.report({'ERROR'}, "Chua co Bar Pillar / Bar Segment nao")
            return {'CANCELLED'}

        coll = ensure_collection(COL_TOPBAR)
        for name in (OBJ_PLANE, OBJ_CUTTER):
            old = bpy.data.objects.get(name)
            if old is not None:
                remove_object(old)

        center = bar_center(objs)
        top = objects_top_z(objs)
        size = props.cutter_size * 0.5

        plane_mesh = bpy.data.meshes.new(OBJ_PLANE)
        plane_mesh.from_pydata(
            [(-size, -size, 0), (size, -size, 0), (size, size, 0), (-size, size, 0)],
            [], [(0, 1, 2, 3)])
        plane_mesh.update()
        plane = bpy.data.objects.new(OBJ_PLANE, plane_mesh)
        coll.objects.link(plane)
        plane.location = (center.x, center.y, top)
        set_color(plane, (1.0, 0.90, 0.20, 1.0))
        plane["rmvb_role"] = "TOPBAR_PLANE"

        height = props.cutter_height
        block = bpy.data.meshes.new(OBJ_CUTTER)
        block.from_pydata(
            [(-size, -size, 0.0), (size, -size, 0.0), (size, size, 0.0),
             (-size, size, 0.0), (-size, -size, height), (size, -size, height),
             (size, size, height), (-size, size, height)],
            [], [(0, 1, 2, 3), (7, 6, 5, 4), (0, 4, 5, 1),
                 (1, 5, 6, 2), (2, 6, 7, 3), (3, 7, 4, 0)])
        block.validate()
        _bm = bmesh.new()
        _bm.from_mesh(block)
        bmesh.ops.recalc_face_normals(_bm, faces=_bm.faces)
        _bm.to_mesh(block)
        _bm.free()
        block.update()
        cutter = bpy.data.objects.new(OBJ_CUTTER, block)
        coll.objects.link(cutter)
        cutter.parent = plane
        cutter.matrix_parent_inverse = plane.matrix_world.inverted()
        cutter.display_type = 'WIRE'
        cutter["rmvb_role"] = "TOPBAR_CUTTER"
        cutter.hide_render = True
        cutter.hide_set(True)

        props.top_plane = plane
        props.top_cutter = cutter
        activate(context, plane)
        self.report({'INFO'}, "Da tao Top Bar Plane tai Z=%.2f (khoi cat %g mm, an)"
                    % (top, height))
        return {'FINISHED'}


class RMVB_OT_cut_top_bar(Operator):
    """3 buoc: Pillar - Segment, union Pillar + Segment, cat theo khoi Top Bar"""
    bl_idname = "rmvb.cut_top_bar"
    bl_label = "Cut Top Bar"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        props = context.scene.rmvb
        pillars = [r.object for r in props.pillars if r.object is not None]
        segment = props.bar_segment
        if segment is not None and segment.name not in bpy.data.objects:
            segment = None
        if not pillars and segment is None:
            self.report({'ERROR'}, "Chua co Bar Pillar hoac Bar Segment")
            return {'CANCELLED'}

        coll = ensure_collection(COL_TOPBAR)
        temp = ensure_collection("Rmvb Temp", coll)
        # Xoa ket qua cu de bam Cut Top Bar nhieu lan khong tao object trung
        previous = bpy.data.objects.get(OBJ_BAR)
        if previous is not None:
            remove_object(previous)
        bases = {}
        for item in props.placed:
            if item.base_object is not None:
                bases[item.tooth] = item.base_object
        work = []
        note = ""
        try:
            # Buoc 1 (diem a + b): Bar Segment - tung Connection dao mat.
            # Connection duoc extrude 2 vung ho ra 2 huong nguoc nhau
            # `connection_cut_extend` mm, nap 2 dau roi dao mat -> lang tru kin
            # cat xuyen hoan toan phan Segment di qua tru Connection.
            segment_cut = None
            if segment is not None:
                bases_list = [b for b in bases.values() if b is not None]
                extend = props.connection_cut_extend
                v_seg = solid_volume(segment)
                segment_cut = cut_segment_by_connections(
                    segment, bases_list, extend, OBJ_SEGMENT + ".cut", temp, True)
                v_cut = solid_volume(segment_cut)
                if v_cut > v_seg * 1.001 or v_cut < 0.02 * v_seg:
                    # DIFFERENCE khong duoc lam khoi TANG len: khi operand da
                    # kin thi normal dao bi solver hieu nguoc -> dung lai
                    # normal goc (khoi van la lang tru chieu dai nhu diem a)
                    remove_object(segment_cut)
                    segment_cut = cut_segment_by_connections(
                        segment, bases_list, extend, OBJ_SEGMENT + ".cut",
                        temp, False)
                    note = " (khoi Connection giu normal goc)"
            # Buoc 2: union toan bo Bar Pillar + Segment da cat
            for pillar in pillars:
                work.append(world_copy(pillar, pillar.name + ".union", temp))
            if segment_cut is not None:
                work.append(segment_cut)
            if not work:
                raise RuntimeError("Khong co thanh phan de union")
            bar = union_all(work, OBJ_BAR, coll)
            purge_collection(temp)

            # Buoc 3: cat theo khoi an gan voi Top Bar Plane
            cutter = props.top_cutter
            if cutter is not None and cutter.name in bpy.data.objects:
                was_hidden = cutter.hide_get()
                if was_hidden:
                    cutter.hide_set(False)
                context.view_layer.update()
                boolean_objects(bar, [cutter], props.cut_mode)
                if was_hidden:
                    cutter.hide_set(True)

            # Attachment: toggle Add/Remove on Bar = UNION (them) hoac
            # DIFFERENCE (khoet l6)
            if props.apply_attachment_bar:
                for ref in props.attachments:
                    if ref.object is None or ref.object.name not in bpy.data.objects:
                        continue
                    copy = world_copy(ref.object, ref.object.name + ".bar", temp)
                    boolean_objects(bar, [copy],
                                    'UNION' if ref.on_bar else 'DIFFERENCE')
                    remove_object(copy)
        except Exception as exc:
            purge_collection(temp)
            self.report({'ERROR'}, "Loi Cut Top Bar: %s" % exc)
            return {'CANCELLED'}

        purge_collection(temp)
        try:
            bpy.data.collections.remove(temp)
        except Exception:
            pass

        bar["rmvb_role"] = "BAR"
        set_color(bar, (0.85, 0.55, 0.15, 1.0))
        activate(context, bar)
        message = "Da Cut Top Bar (%s)%s" % (props.cut_mode, note)
        self.report({'INFO'}, message)
        return {'FINISHED'}


# ---------------------------------------------------------------------------
# 6.4 Attachment
# ---------------------------------------------------------------------------
def current_attachment_name(props):
    names = get_attachment_items()
    if props.active_attachment in names:
        return props.active_attachment
    if names:
        return names[min(props.attachment_index, len(names) - 1)]
    return ""


def attachment_axis_empty(context):
    """Empty dung lam truc chung cho cac Attachment (Group Axis Attachment)."""
    empty = bpy.data.objects.get(OBJ_ATTACH_AXIS)
    if empty is None:
        empty = bpy.data.objects.new(OBJ_ATTACH_AXIS, None)
        empty.empty_display_type = 'PLAIN_AXES'
        empty.empty_display_size = 6.0
        ensure_collection(COL_ATTACHMENT).objects.link(empty)
        empty["rmvb_role"] = "ATTACH_AXIS"
    return empty


class RMVB_OT_add_attachment(Operator):
    """Dat Attachment da chon (Apply Part Bar) vao vi tri hien tai cua bar"""
    bl_idname = "rmvb.add_attachment"
    bl_label = "Add selected Attachment"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        props = context.scene.rmvb
        context.view_layer.update()
        name = current_attachment_name(props)
        if not name:
            self.report({'ERROR'}, "Chua chon Attachment trong Dental-Lib")
            return {'CANCELLED'}
        entry = lib_attachment(name) or {}
        lib = dlib()
        asset = lib.attachment_asset(name, "part_bar") if lib else ""
        if not asset or not os.path.exists(asset):
            self.report({'ERROR'}, "Attachment '%s' chua co Apply Part Bar (STL/PLY)"
                        % name)
            return {'CANCELLED'}
        try:
            mesh = mesh_from_file(asset)
        except Exception as exc:
            self.report({'ERROR'}, "Loi doc mesh Attachment: %s" % exc)
            return {'CANCELLED'}

        coll = ensure_collection(COL_ATTACHMENT)
        # Diem 6: dat theo 3D Cursor (vi tri + huong cua cursor), add nhieu lan
        anchor = context.scene.cursor.location.copy()
        matrix = context.scene.cursor.matrix.copy()

        index = len(props.attachments)
        obj = object_from_mesh("Attachment_%s_%d" % (slugify(name), index),
                               mesh, coll, matrix)
        set_color(obj, (0.30, 0.85, 0.40, 1.0))
        obj["rmvb_role"] = "ATTACHMENT"
        obj["rmvb_attachment"] = name

        ref = props.attachments.add()
        ref.att_name = name
        ref.object = obj
        ref.on_bar = bool(entry.get("on_bar", True))
        ref.on_sleeve = bool(entry.get("on_sleeve", False))

        # Diem 9: Visual Object chi xuat hien kem, khong tham gia boolean
        made_visuals = 0
        if lib:
            for slot, path in lib_visuals(name):
                if not path or not os.path.exists(path):
                    continue
                try:
                    vmesh = mesh_from_file(path)
                except Exception as exc:
                    self.report({'WARNING'},
                                "Loi doc Visual Object '%s': %s" % (slot, exc))
                    continue
                vobj = object_from_mesh("Visual_%s_%s_%d" % (slugify(name),
                                                              slugify(slot), index),
                                        vmesh, coll, matrix)
                vobj["rmvb_role"] = "VISUAL"
                vobj["rmvb_attachment"] = name
                set_color(vobj, (0.75, 0.75, 0.80, 1.0))
                vref = ref.visuals.add()
                vref.object = vobj
                vref.tooth = slot
                made_visuals += 1

        plane = props.top_plane
        if props.group_axis:
            axis = attachment_axis_empty(context)
            if props.group_axis_topbar and plane is not None:
                lock_to_plane(axis, plane)
                # Empty vua di chuyen nen cac Attachment da parent truoc do
                # phai duoc chieu lai len Plane
                for other in props.attachments:
                    for child in ([other.object] +
                                  [v.object for v in other.visuals]):
                        if child is not None and child.parent == axis:
                            project_to_plane(child, plane)
            parent_keep_transform(obj, axis)
            for vref in ref.visuals:
                if vref.object is not None:
                    if props.group_axis_topbar and plane is not None:
                        project_to_plane(vref.object, plane)
                    parent_keep_transform(vref.object, axis)
            if props.group_axis_topbar and plane is not None:
                project_to_plane(obj, plane)
        elif props.group_axis_topbar:
            if plane is None:
                self.report({'WARNING'},
                            "Chua co Top Bar Plane - khong lock duoc truc")
            else:
                lock_to_plane(obj, plane)
                for vref in ref.visuals:
                    if vref.object is not None:
                        lock_to_plane(vref.object, plane)
        self.report({'INFO'}, "Da dat Attachment '%s' (index %d, %d Visual Object)"
                    % (name, index, made_visuals))
        return {'FINISHED'}


def project_to_plane(obj, plane):
    """Tinh dich tam cua obj nam len mat phang Plane (giu nguyen rotation)."""
    bpy.context.view_layer.update()
    world = obj.matrix_world.copy()
    local = plane.matrix_world.inverted() @ world.translation
    local.z = 0.0
    obj.matrix_world = (Matrix.Translation(plane.matrix_world @ local)
                        @ world.to_quaternion().to_matrix().to_4x4())
    return obj


def lock_to_plane(obj, plane):
    """Diem 7: Attachment xoay theo Plane va tam luon nam tren mat Plane.

    Parent vao Plane (khong dung matrix_parent_inverse de tinh ro), dat vi tri
    local = chieu cua tam len mat phang (z = 0) va them LIMIT_LOCATION khoa
    dung chieu Z trong he truc Plane; X/Y tu do, rotation follow Plane.
    """
    bpy.context.view_layer.update()
    world = obj.matrix_world.copy()
    parent_rot = plane.matrix_world.to_quaternion()
    local = plane.matrix_world.inverted() @ world.translation
    local.z = 0.0                                   # chieu ve mat phang
    scale = plane.matrix_world.to_scale()
    obj.parent = plane
    obj.matrix_parent_inverse = Matrix.Identity(4)
    obj.location = local
    obj.rotation_mode = 'QUATERNION'
    obj.rotation_quaternion = (parent_rot.inverted()
                               @ world.to_quaternion())
    obj.scale = Vector((
        world.to_scale()[0] / (scale[0] or 1.0),
        world.to_scale()[1] / (scale[1] or 1.0),
        world.to_scale()[2] / (scale[2] or 1.0)))
    constraint = obj.constraints.get(CST_ON_PLANE)
    if constraint is None:
        constraint = obj.constraints.new('LIMIT_LOCATION')
        constraint.name = CST_ON_PLANE
    if hasattr(constraint, "owner_space"):
        constraint.owner_space = 'LOCAL'
    constraint.use_min_z = True
    constraint.use_max_z = True
    constraint.min_z = 0.0
    constraint.max_z = 0.0
    constraint.use_transform_limit = True
    bpy.context.view_layer.update()


def parent_keep_transform(child, parent):
    """Parent giu nguyen vi tri world cua child."""
    child.parent = parent
    child.matrix_parent_inverse = parent.matrix_world.inverted()


def slugify(text):
    return re.sub(r"[^\w\-.]+", "_", (text or "att"), flags=re.UNICODE)


class RMVB_OT_clear_attachments(Operator):
    """Xoa toan bo Attachment da dat tren bar"""
    bl_idname = "rmvb.clear_attachments"
    bl_label = "Xoa Attachment da dat"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        props = context.scene.rmvb
        for ref in list(props.attachments):
            for vref in list(ref.visuals):
                remove_object(vref.object)
            ref.visuals.clear()
            remove_object(ref.object)
        props.attachments.clear()
        axis = bpy.data.objects.get(OBJ_ATTACH_AXIS)
        if axis is not None:
            bpy.data.objects.remove(axis, do_unlink=True)
        self.report({'INFO'}, "Da xoa Attachment")
        return {'FINISHED'}


# ---------------------------------------------------------------------------
# 7. Sleeve Design
# ---------------------------------------------------------------------------
def _solidify(obj, thickness, offset):
    mod = obj.modifiers.new("RMVB_solidify", 'SOLIDIFY')
    mod.thickness = thickness
    mod.offset = offset
    for prop, value in (("use_even_offset", False), ("use_rim", False),
                        ("material_offset", 0), ("material_offset_rim", 0)):
        if hasattr(mod, prop):
            try:
                setattr(mod, prop, value)
            except Exception:
                pass
    bpy.context.view_layer.update()
    apply_modifiers_in_place(obj)
    for mod in list(obj.modifiers):
        obj.modifiers.remove(mod)
    return obj


def dilate_solid(source, distance, name, coll):
    """Solid mo rong cua source them `distance` mm ra ben ngoai theo normal.

    Shell solidify(offset=0, thickness=2d) duoc union voi ban da kin -> thanh
    solid moi, tranh truong hop 2 mat trung nhau gay treo boolean solver.
    """
    base = closed_copy(source, name, coll)
    if distance > 1e-6:
        shell = world_copy(source, name + ".shell", coll)
        _solidify(shell, distance * 2.0, 0.0)
        boolean_objects(base, [shell], 'UNION')
        remove_object(shell)
    return base


def sleeve_shell(source, inner_gap, wall, name, coll):
    """Vo Sleeve: mat trong cach bar `inner_gap`, day `wall` mm."""
    inner = dilate_solid(source, inner_gap, name + ".inner", coll)
    return _solidify(inner, wall, 1.0)


def bar_source(context):
    """Object bar hien hanh (ket qua Cut Top Bar hoac gop pillar + segment)."""
    props = context.scene.rmvb
    bar = bpy.data.objects.get(OBJ_BAR)
    if bar is not None:
        return bar
    objs = design_objects(context)
    if not objs:
        return None
    coll = ensure_collection(COL_SEGMENT)
    copies = [world_copy(o, o.name + ".src", coll) for o in objs]
    return join_objects(copies, OBJ_BAR + ".src", coll)


class RMVB_OT_create_sleeve_design(Operator):
    """Tao Sleeve: vo mong bao quanh bar voi offset + chieu day da chon"""
    bl_idname = "rmvb.create_sleeve_design"
    bl_label = "Create Sleeve Design"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        props = context.scene.rmvb
        source = bar_source(context)
        if source is None:
            self.report({'ERROR'}, "Chua co bar (hay tao Bar Pillar/Segment truoc)")
            return {'CANCELLED'}

        coll = ensure_collection(COL_SLEEVE)
        work = ensure_collection("Rmvb Temp", coll)
        old = props.sleeve_object
        if old is not None and old.name in bpy.data.objects:
            remove_object(old)

        inner_gap = max(props.sleeve_offset, 0.0)
        wall = max(props.sleeve_thickness, 0.01)
        try:
            sleeve = sleeve_shell(source, inner_gap, wall, "Sleeve", work)
            sleeve.name = OBJ_SLEEVE
            sleeve.data.name = OBJ_SLEEVE
            for user in list(sleeve.users_collection):
                if user != coll:
                    user.objects.unlink(sleeve)
            if sleeve.name not in coll.objects:
                coll.objects.link(sleeve)

            # Toggle Add/Remove on Sleeve: UNION (them) hoac DIFFERENCE (khoet)
            if props.apply_attachment_sleeve:
                for ref in props.attachments:
                    if ref.object is None or ref.object.name not in bpy.data.objects:
                        continue
                    copy = world_copy(ref.object, ref.object.name + ".sleeve", work)
                    boolean_objects(sleeve, [copy],
                                    'UNION' if ref.on_sleeve else 'DIFFERENCE')
                    remove_object(copy)
        except Exception as exc:
            purge_collection(work)
            self.report({'ERROR'}, "Loi tao Sleeve: %s" % exc)
            return {'CANCELLED'}

        purge_collection(work)
        try:
            bpy.data.collections.remove(work)
        except Exception:
            pass

        set_color(sleeve, (0.95, 0.55, 0.85, 1.0))
        sleeve["rmvb_role"] = "SLEEVE"
        props.sleeve_object = sleeve
        activate(context, sleeve)
        self.report({'INFO'}, "Da tao Sleeve (offset %g mm, day %g mm)"
                    % (inner_gap, wall))
        return {'FINISHED'}


# ---------------------------------------------------------------------------
# 8. Save Design
# ---------------------------------------------------------------------------
def write_construction_info(stl_path, source_ci):
    """Diem 10: chep constructionInfo goc va thay <Filename> dau bang ten STL
    moi (dung cach add-on iBar dang lam). Tra ve duong dan file ghi duoc."""
    src = bpy.path.abspath(source_ci) if source_ci else ""
    if not src or not os.path.exists(src):
        folder = os.path.dirname(stl_path)
        src = ""
        try:
            for name in sorted(os.listdir(folder)):
                if name.endswith('.constructionInfo'):
                    src = os.path.join(folder, name)
                    break
        except OSError:
            pass
    if not src or not os.path.exists(src):
        return ""
    try:
        with open(src, 'r', encoding='utf-8') as handle:
            content = handle.read()
    except OSError:
        return ""
    replacement = "<Filename>%s</Filename>" % os.path.basename(stl_path)
    updated, count = re.subn(r'<Filename>[^<]*</Filename>',
                             lambda _m: replacement, content, count=1)
    if not count:
        return ""
    ci_path = os.path.splitext(stl_path)[0] + ".constructionInfo"
    try:
        with open(ci_path, 'w', encoding='utf-8') as handle:
            handle.write(updated)
    except OSError:
        return ""
    return ci_path


class RMVB_OT_save_design(Operator):
    """Xuat STL cho Bar Design hoac Sleeve Design (kem Visual Object + constructionInfo)"""
    bl_idname = "rmvb.save_design"
    bl_label = "Save Design"
    bl_options = {'REGISTER', 'UNDO'}

    which: EnumProperty(
        name="Which",
        items=[('BAR', "Bar Design", ""), ('SLEEVE', "Sleeve Design", "")],
        default='BAR')

    def execute(self, context):
        props = context.scene.rmvb
        if self.which == 'BAR':
            objects = [bpy.data.objects.get(OBJ_BAR)]
            prefix = "Rmvb_Bar"
            if objects[0] is None:
                objects = [r.object for r in props.pillars if r.object is not None]
                if props.bar_segment is not None:
                    objects.append(props.bar_segment)
        else:
            objects = [props.sleeve_object]
            prefix = "Rmvb_Sleeve"
        objects = [o for o in objects if o is not None]
        if not objects:
            self.report({'ERROR'}, "Chua co %s de luu" % prefix)
            return {'CANCELLED'}

        # Diem 9: Visual Object chi duoc xuat kem, khong tham gia boolean
        visuals = []
        for ref in props.attachments:
            for vref in ref.visuals:
                obj = vref.object
                if obj is not None and obj.name not in [o.name for o in objects]:
                    visuals.append(obj)

        folder = bpy.path.abspath(props.save_dir) if props.save_dir else project_dir()
        if not folder or not os.path.isdir(folder):
            folder = project_dir()
        filepath = os.path.join(folder, "%s_%s.stl" % (prefix, timestamp()))
        try:
            export_stl(objects + visuals, filepath, context)
        except Exception as exc:
            self.report({'ERROR'}, "Khong xuat duoc STL: %s" % exc)
            return {'CANCELLED'}
        ci_path = write_construction_info(filepath, props.construction_file)
        self.report({'INFO'}, "Da luu: %s" % filepath)
        if ci_path:
            self.report({'INFO'}, "Da cap nhat: %s" % ci_path)
        else:
            self.report({'WARNING'},
                        "Khong tim thay constructionInfo de cap nhat")
        return {'FINISHED'}


# ---------------------------------------------------------------------------
# Panel
# ---------------------------------------------------------------------------
class RMVB_PT_panel(Panel):
    bl_label = "Rmvb-Bar"
    bl_idname = "VIEW3D_PT_rmvb_bar"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Rmvb-Bar"

    def draw(self, context):
        layout = self.layout
        props = context.scene.rmvb
        if dlib() is None:
            layout.label(text="Chua bat add-on Dental-Lib", icon='ERROR')

        # ---- 1-3: Import ------------------------------------------------
        box = layout.box()
        box.label(text="1. Import", icon='IMPORT')
        col = box.column(align=True)
        for role, label in (('GINGIVA', "Import Gingiva (STL/PLY)"),
                            ('DENTURE', "Import Denture-reference (STL/PLY)"),
                            ('ANTAGONIST', "Import Antagonist (STL/PLY)")):
            col.operator(RMVB_OT_import_mesh.bl_idname, text=label,
                         icon='MESH_UVSPHERE').role = role
        for label, field in (("Gingiva", "gingiva_object"),
                             ("Denture", "denture_object"),
                             ("Antagonist", "antagonist_object")):
            row = box.row(align=True)
            row.label(text=label, icon='OUTLINER_OB_MESH')
            row.prop(props, field, text="")

        # ---- 4-5: Connection --------------------------------------------
        box = layout.box()
        box.label(text="2. Connection Base", icon='MESH_CYLINDER')
        box.prop(props, "connection_base")
        if props.connection_name:
            box.label(text="Library: " + props.connection_name, icon='INFO')
        box.prop(props, "place_parts")
        box.operator(RMVB_OT_place_connection.bl_idname,
                     text="Place Connection (XML constructionInfo)",
                     icon='EMPTY_SINGLE_ARROW')
        if props.construction_file:
            box.label(text=os.path.basename(bpy.path.abspath(props.construction_file)),
                      icon='FILE')
        box.label(text="Da dat: %d implant" % len(props.placed), icon='CHECKMARK')

        # ---- 6.1 Bar Pillar ---------------------------------------------
        box = layout.box()
        box.label(text="3. Bar Design - Bar Pillar", icon='MESH_CONE')
        box.prop(props, "pillar_lift")
        box.prop(props, "pillar_equalize")
        col = box.column(align=True)
        col.operator(RMVB_OT_create_bar_pillar.bl_idname,
                     text="Create Bar Pillar", icon='MOD_SCREW')
        sub = col.column(align=True)
        sub.operator(RMVB_OT_edit_bar_pillar.bl_idname,
                     text="Edit Bar Pillar (Local)", icon='EDITMODE_HLT')
        sub.operator(RMVB_OT_select_pillar_region.bl_idname,
                     text="Select Screws", icon='VERTEXSEL').region = 'SCREWS'
        sub.operator(RMVB_OT_select_pillar_region.bl_idname,
                     text="Select Outside", icon='FACESEL').region = 'OUTSIDE'
        sub.operator(RMVB_OT_exit_edit.bl_idname, text="Exit Edit Bar Pillar",
                     icon='OBJECT_DATA')
        box.label(text="Bar Pillar: %d" % len(props.pillars), icon='INFO')

        # ---- 6.2 Bar Segment --------------------------------------------
        box = layout.box()
        box.label(text="4. Bar Design - Bar Segment", icon='CURVE_PATH')
        col = box.column(align=True)
        col.operator(RMVB_OT_create_bar_line.bl_idname,
                     text="Draw Line Bar (snap Gingiva)", icon='GREASEPENCIL')
        col.operator(RMVB_OT_close_bar_line.bl_idname,
                     text="Noi diem dau-cuoi (F)", icon='MESH_CIRCLE')
        col.prop(props, "bar_width")
        col.prop(props, "bar_height")
        col.prop(props, "bar_clearance")
        col.operator(RMVB_OT_create_bar_segment.bl_idname,
                     text="Create Bar Segment", icon='MOD_SCREW')
        col.operator(RMVB_OT_edit_bar_segment.bl_idname,
                     text="Edit Bar Segment (Local)", icon='EDITMODE_HLT')
        col.operator(RMVB_OT_exit_edit.bl_idname, text="Exit Edit Bar Segment",
                     icon='OBJECT_DATA')

        # ---- 6.3 Top Bar Plane ------------------------------------------
        box = layout.box()
        box.label(text="5. Bar Design - Top Bar", icon='MESH_PLANE')
        box.prop(props, "cutter_height")
        box.prop(props, "cutter_size")
        box.operator(RMVB_OT_create_top_bar_plane.bl_idname,
                     text="Create Top Bar Plane", icon='MESH_PLANE')
        box.prop(props, "cut_mode")
        box.prop(props, "connection_cut_extend")
        box.operator(RMVB_OT_cut_top_bar.bl_idname, text="Cut Top Bar",
                     icon='MOD_BOOLEAN')
        box.label(text="Plane: di chuyen / xoay de dat lai khoi cut", icon='INFO')

        # ---- 6.4 Attachment ----------------------------------------------
        box = layout.box()
        box.label(text="6. Bar Design - Attachment", icon='MESH_CUBE')
        box.prop(props, "attachment_name")
        box.operator(RMVB_OT_add_attachment.bl_idname,
                     text="Add selected Attachment", icon='ADD')
        box.prop(props, "group_axis")
        box.prop(props, "group_axis_topbar")
        box.prop(props, "apply_attachment_bar")
        box.operator(RMVB_OT_clear_attachments.bl_idname,
                     text="Xoa Attachment da dat", icon='X')
        visual_count = sum(len(ref.visuals) for ref in props.attachments)
        box.label(text="Da dat: %d  Visual: %d" % (len(props.attachments),
                                                   visual_count), icon='INFO')

        # ---- 7 Sleeve Design ---------------------------------------------
        box = layout.box()
        box.label(text="7. Sleeve Design", icon='MOD_SOLIDIFY')
        box.prop(props, "sleeve_offset")
        box.prop(props, "sleeve_thickness")
        box.prop(props, "apply_attachment_sleeve")
        box.operator(RMVB_OT_create_sleeve_design.bl_idname,
                     text="Create Sleeve Design", icon='MOD_SOLIDIFY')

        # ---- 8 Save Design -----------------------------------------------
        box = layout.box()
        box.label(text="8. Save Design", icon='EXPORT')
        box.prop(props, "save_dir")
        col = box.column(align=True)
        col.operator(RMVB_OT_save_design.bl_idname, text="Save Bar Design",
                     icon='EXPORT').which = 'BAR'
        col.operator(RMVB_OT_save_design.bl_idname, text="Save Sleeve Design",
                     icon='EXPORT').which = 'SLEEVE'


# ---------------------------------------------------------------------------
# Register
# ---------------------------------------------------------------------------
_classes = (
    RMVB_PG_PlacedConnection,
    RMVB_PG_PartRef,
    RMVB_PG_AttachmentRef,
    RMVB_PG_props,
    RMVB_OT_import_mesh,
    RMVB_OT_place_connection,
    RMVB_OT_create_bar_pillar,
    RMVB_OT_edit_bar_pillar,
    RMVB_OT_select_pillar_region,
    RMVB_OT_exit_edit,
    RMVB_OT_create_bar_line,
    RMVB_OT_draw_bar_line,
    RMVB_OT_close_bar_line,
    RMVB_OT_create_bar_segment,
    RMVB_OT_edit_bar_segment,
    RMVB_OT_create_top_bar_plane,
    RMVB_OT_cut_top_bar,
    RMVB_OT_add_attachment,
    RMVB_OT_clear_attachments,
    RMVB_OT_create_sleeve_design,
    RMVB_OT_save_design,
    RMVB_PT_panel,
)


def register():
    for cls in _classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.rmvb = PointerProperty(type=RMVB_PG_props)


def unregister():
    del bpy.types.Scene.rmvb
    for cls in reversed(_classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()

