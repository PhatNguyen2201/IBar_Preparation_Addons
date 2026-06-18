bl_info = {
    "name": "Gingiva/Teeth Surface Splitter",
    "author": "Phat Nguyen",
    "version": (1, 0, 0),
    "blender": (4, 5, 3),
    "location": "View3D > Sidebar > IBAR Split",
    "description": "Ve mot vong line kin tren be mat va tach object thanh Gingiva va Teeth",
    "category": "Object",
}

import bpy
import bmesh
import math
import os
import uuid
import hashlib
from mathutils import Vector
from bpy_extras import view3d_utils
import gpu
from gpu_extras.batch import batch_for_shader


# ---------------------------------------------------------------------------
# Module-level cache: lưu vòng line (điểm + normal world) đã vẽ theo tên object.
# ---------------------------------------------------------------------------
# { object_name: {"points": [Vector, ...], "normals": [Vector, ...]} }
_stroke_cache = {}


# ---------------------------------------------------------------------------
# ViewLayer safety helpers (sao chép để add-on độc lập với add-on iBar).
# ---------------------------------------------------------------------------
def _is_in_view_layer(obj, viewlayer=None):
    if obj is None:
        return False
    if viewlayer is None:
        viewlayer = bpy.context.view_layer
    return obj.name in viewlayer.objects


def _set_active_object(obj, viewlayer=None):
    if viewlayer is None:
        viewlayer = bpy.context.view_layer
    if not _is_in_view_layer(obj, viewlayer):
        return False
    viewlayer.objects.active = obj
    return True


def _select_object(obj, state=True, viewlayer=None):
    if viewlayer is None:
        viewlayer = bpy.context.view_layer
    if not _is_in_view_layer(obj, viewlayer):
        return False
    obj.select_set(state)
    return True


# ---------------------------------------------------------------------------
# License check (sao chép nguyen khoi tu Final_addon_Ibar_to_ORG.py, dong 1628-1699).
# Dung chung file key ~/addon_ibar.key voi add-on iBar hien tai.
# ---------------------------------------------------------------------------
def create_hash(data, algorithm="sha512"):
    hash_func = hashlib.new(algorithm)
    hash_func.update(data.encode('utf-8'))
    return hash_func.hexdigest()


def _read_windows_machine_guid():
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography")
        value, _ = winreg.QueryValueEx(key, "MachineGuid")
        return str(value).strip()
    except Exception:
        return ""


def _build_machine_fingerprint():
    machine_guid = _read_windows_machine_guid()
    mac_address = str(uuid.getnode())
    host_name = os.environ.get("COMPUTERNAME", "") or os.environ.get("HOSTNAME", "")
    processor = os.environ.get("PROCESSOR_IDENTIFIER", "")
    cpu_count = os.environ.get("NUMBER_OF_PROCESSORS", "")

    parts = [machine_guid, mac_address, host_name, processor, cpu_count]
    raw_fingerprint = "|".join(part for part in parts if part)
    if not raw_fingerprint:
        raw_fingerprint = mac_address

    return create_hash(raw_fingerprint, "sha256")[:32].upper()


def get_stable_hardware_id():
    user_folder = os.path.expanduser("~")
    machine_id_path = os.path.join(user_folder, ".ibar_machine_id")

    if os.path.exists(machine_id_path):
        try:
            with open(machine_id_path, "r", encoding="utf-8") as file_read:
                cached_id = file_read.read().strip()
                if cached_id:
                    return cached_id
        except Exception:
            pass

    hardware_id = _build_machine_fingerprint()
    try:
        with open(machine_id_path, "w", encoding="utf-8") as file_write:
            file_write.write(hardware_id)
    except Exception:
        pass
    return hardware_id


def hw_read_key():
    hardware_id = get_stable_hardware_id()
    hashed_text = create_hash(hardware_id * 2)
    legacy_hardware_id = str(uuid.getnode())
    legacy_hashed_text = create_hash(legacy_hardware_id * 2)
    user_folder = os.path.expanduser("~")

    license_path = os.path.join(user_folder, "addon_ibar.key")
    if not os.path.exists(license_path):
        hardware_id_filepart = os.path.join(user_folder, "Desktop", "IbarPrep.hwid")
        try:
            if not os.path.exists(hardware_id_filepart):
                with open(hardware_id_filepart, "w", encoding="utf-8") as file_write:
                    file_write.write(hardware_id)
        except Exception:
            pass
        print('No License Found')
        return False

    with open(license_path, "r", encoding="utf-8") as hardware_id_input:
        lines = hardware_id_input.readlines()
    if lines and lines[0].strip() in {hashed_text, legacy_hashed_text}:
        return True
    print('Wrong license key')
    return False


# ---------------------------------------------------------------------------
# Geometry helpers
# ---------------------------------------------------------------------------
def _world_normal(obj, normal_local):
    """Chuyen normal tu local sang world (dung cho ca scale khong deu)."""
    return (obj.matrix_world.to_3x3().inverted().transposed() @ normal_local).normalized()


def _bbox_center_world(obj):
    corners = [obj.matrix_world @ Vector(c) for c in obj.bound_box]
    center = Vector((0.0, 0.0, 0.0))
    for c in corners:
        center += c
    return center / len(corners)


def _resample_loop_on_surface(obj, points, samples_per_edge=8):
    """Chia nho moi canh cua vong kin va snap tung diem mau ve be mat object.

    Tra ve (loop_points_world, loop_normals_world) - vong kin day diem, moi diem
    nam tren be mat object kem normal be mat.
    """
    mw = obj.matrix_world
    mwi = mw.inverted()

    loop_pts = []
    loop_nrms = []
    n = len(points)
    for i in range(n):
        p_start = points[i]
        p_end = points[(i + 1) % n]
        # Lay samples_per_edge diem doc canh (khong gom diem cuoi de tranh trung lap
        # voi diem dau canh sau).
        for s in range(samples_per_edge):
            t = s / float(samples_per_edge)
            world_co = p_start.lerp(p_end, t)
            local_co = mwi @ world_co
            hit, location, normal, _idx = obj.closest_point_on_mesh(local_co)
            if hit:
                loop_pts.append(mw @ location)
                loop_nrms.append(_world_normal(obj, normal))
            else:
                loop_pts.append(world_co)
                loop_nrms.append(Vector((0.0, 0.0, 1.0)))
    return loop_pts, loop_nrms


def _smooth_normals(normals, iterations=2):
    """Lam muot vong-tron cac normal bang trung binh truot."""
    n = len(normals)
    if n < 3:
        return [v.normalized() for v in normals]
    result = [v.copy() for v in normals]
    for _ in range(iterations):
        new = []
        for i in range(n):
            prev = result[(i - 1) % n]
            cur = result[i]
            nxt = result[(i + 1) % n]
            avg = (prev + cur + nxt)
            if avg.length > 1e-9:
                avg = avg.normalized()
            else:
                avg = cur.normalized()
            new.append(avg)
        result = new
    return result


def _build_cutter(context, target, loop_pts, loop_nrms, offset, gap):
    """Dung cutter ong kin treo tu vong line, solidify len do day gap.

    Tra ve object cutter (da apply solidify), hoac None neu loi.
    """
    n = len(loop_pts)
    if n < 3:
        return None

    # Normal huong vao trong than object: lat theo huong tu diem toi tam bbox.
    center = _bbox_center_world(target)
    inward = []
    for p, nrm in zip(loop_pts, loop_nrms):
        to_center = (center - p)
        nn = nrm.normalized()
        if nn.dot(to_center) < 0:
            nn = -nn
        inward.append(nn)
    inward = _smooth_normals(inward, iterations=2)

    depth = max(target.dimensions) * 1.5
    if depth <= 0:
        depth = 1.0
    eps = max(target.dimensions) * 0.01 + 1e-4

    bm = bmesh.new()
    top_verts = []
    par_verts = []
    deep_verts = []
    for p, nn in zip(loop_pts, inward):
        # nn huong vao trong -> di vao trong = +nn; di ra ngoai be mat = -nn.
        v_top = bm.verts.new(p - eps * nn)            # nho ra ngoai be mat tai line
        v_par = bm.verts.new(p + offset * nn)          # cach be mat = offset, vao trong
        v_deep = bm.verts.new(p + depth * nn)          # sau de xuyen het than object
        top_verts.append(v_top)
        par_verts.append(v_par)
        deep_verts.append(v_deep)
    bm.verts.ensure_lookup_table()

    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((top_verts[i], top_verts[j], par_verts[j], par_verts[i]))
        bm.faces.new((par_verts[i], par_verts[j], deep_verts[j], deep_verts[i]))

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])

    me = bpy.data.meshes.new("GT_cut_wall")
    bm.to_mesh(me)
    bm.free()

    cutter = bpy.data.objects.new("GT_cut_wall", me)
    context.collection.objects.link(cutter)

    # Solidify len do day Gap (giong pattern add-on iBar).
    mod = cutter.modifiers.new(name="Solidify", type='SOLIDIFY')
    mod.solidify_mode = 'NON_MANIFOLD'
    mod.nonmanifold_thickness_mode = 'FIXED'
    mod.thickness = gap
    mod.use_flip_normals = True

    bpy.ops.object.select_all(action='DESELECT')
    _set_active_object(cutter, context.view_layer)
    _select_object(cutter, True, context.view_layer)
    bpy.ops.object.modifier_apply(modifier="Solidify")

    return cutter


def _mesh_volume(obj):
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.transform(obj.matrix_world)
    vol = abs(bm.calc_volume(signed=True))
    bm.free()
    return vol


# ---------------------------------------------------------------------------
# Properties
# ---------------------------------------------------------------------------
class GTSplitProps(bpy.types.PropertyGroup):
    offset: bpy.props.FloatProperty(
        name="Offset",
        description="Khoang cach mat cat so voi be mat object",
        default=0.3, min=0.0, unit='LENGTH',
    )
    gap: bpy.props.FloatProperty(
        name="Gap",
        description="Do day khe ho giua 2 thanh phan (phai > 0)",
        default=0.1, min=0.0001, unit='LENGTH',
    )
    samples_per_edge: bpy.props.IntProperty(
        name="Smoothness",
        description="So diem mau moi canh khi snap vong ve be mat",
        default=8, min=1, max=64,
    )


# ---------------------------------------------------------------------------
# Operator: ve vong line kin tren be mat (modal)
# ---------------------------------------------------------------------------
class GTSPLIT_OT_draw_line(bpy.types.Operator):
    """Ve mot vong line kin tren be mat object (click tung diem, Enter de dong vong)"""
    bl_idname = "object.gtsplit_draw_line"
    bl_label = "Ve duong cat (vong kin)"
    bl_options = {'REGISTER'}

    _handle = None

    def invoke(self, context, event):
        if not hw_read_key():
            self.report({'ERROR'}, "Vui long dang ky key de kich hoat su dung")
            return {'CANCELLED'}

        target = context.active_object
        if target is None or target.type != 'MESH':
            self.report({'ERROR'}, "Hay chon mot object MESH lam active")
            return {'CANCELLED'}
        if context.area is None or context.area.type != 'VIEW_3D':
            self.report({'ERROR'}, "Hay chay trong View3D")
            return {'CANCELLED'}

        self.target = target
        self.points = []          # diem click tren be mat (world)
        self.normals = []         # normal be mat tai diem click (world)
        self.preview = None       # diem preview duoi con tro

        args = (self, context)
        self._handle = bpy.types.SpaceView3D.draw_handler_add(
            _draw_callback, args, 'WINDOW', 'POST_VIEW')
        context.window_manager.modal_handler_add(self)
        context.workspace.status_text_set(
            "Click: them diem  |  Enter/Space: dong vong & ket thuc  |  Esc/Phai: huy")
        context.area.tag_redraw()
        return {'RUNNING_MODAL'}

    def _raycast(self, context, event):
        region = context.region
        rv3d = context.region_data
        coord = (event.mouse_region_x, event.mouse_region_y)
        origin = view3d_utils.region_2d_to_origin_3d(region, rv3d, coord)
        direction = view3d_utils.region_2d_to_vector_3d(region, rv3d, coord)
        mwi = self.target.matrix_world.inverted()
        ray_origin = mwi @ origin
        ray_dir = (mwi.to_3x3() @ direction).normalized()
        hit, loc, nrm, _idx = self.target.ray_cast(ray_origin, ray_dir)
        if not hit:
            return None, None
        world_co = self.target.matrix_world @ loc
        world_nrm = _world_normal(self.target, nrm)
        return world_co, world_nrm

    def modal(self, context, event):
        if context.area:
            context.area.tag_redraw()

        if event.type == 'MOUSEMOVE':
            co, _nrm = self._raycast(context, event)
            self.preview = co
            return {'RUNNING_MODAL'}

        elif event.type == 'LEFTMOUSE' and event.value == 'PRESS':
            co, nrm = self._raycast(context, event)
            if co is None:
                self.report({'WARNING'}, "Diem phai nam tren be mat object")
                return {'RUNNING_MODAL'}
            self.points.append(co)
            self.normals.append(nrm)
            return {'RUNNING_MODAL'}

        elif event.type in {'RET', 'NUMPAD_ENTER', 'SPACE'} and event.value == 'PRESS':
            if len(self.points) < 3:
                self.report({'WARNING'}, "Can it nhat 3 diem de tao vong kin")
                return {'RUNNING_MODAL'}
            self._finish(context)
            self.report({'INFO'},
                        "Da luu vong kin %d diem. Nhan 'Tach object' de cat." % len(self.points))
            return {'FINISHED'}

        elif event.type in {'ESC', 'RIGHTMOUSE'} and event.value == 'PRESS':
            self._cleanup(context)
            self.report({'INFO'}, "Da huy ve duong cat")
            return {'CANCELLED'}

        # Cho phep xoay/zoom view trong khi ve.
        elif event.type in {'MIDDLEMOUSE', 'WHEELUPMOUSE', 'WHEELDOWNMOUSE'}:
            return {'PASS_THROUGH'}

        return {'RUNNING_MODAL'}

    def _finish(self, context):
        _stroke_cache[self.target.name] = {
            "points": [p.copy() for p in self.points],
            "normals": [n.copy() for n in self.normals],
        }
        self._cleanup(context)

    def _cleanup(self, context):
        if self._handle is not None:
            bpy.types.SpaceView3D.draw_handler_remove(self._handle, 'WINDOW')
            self._handle = None
        context.workspace.status_text_set(None)
        if context.area:
            context.area.tag_redraw()


def _draw_callback(operator, context):
    pts = list(operator.points)

    shader = gpu.shader.from_builtin('UNIFORM_COLOR')
    gpu.state.line_width_set(2.0)
    gpu.state.point_size_set(8.0)

    # Vong kin (noi diem cuoi ve diem dau) neu du diem.
    if len(pts) >= 2:
        loop = pts + [pts[0]]
        batch = batch_for_shader(shader, 'LINE_STRIP', {"pos": loop})
        shader.bind()
        shader.uniform_float("color", (0.1, 0.9, 0.2, 1.0))
        batch.draw(shader)

    # Doan tu diem cuoi toi con tro (preview).
    if operator.preview is not None and len(pts) >= 1:
        seg = [pts[-1], operator.preview]
        batch = batch_for_shader(shader, 'LINE_STRIP', {"pos": seg})
        shader.bind()
        shader.uniform_float("color", (0.9, 0.9, 0.2, 1.0))
        batch.draw(shader)

    # Cac diem.
    if pts:
        batch = batch_for_shader(shader, 'POINTS', {"pos": pts})
        shader.bind()
        shader.uniform_float("color", (1.0, 0.3, 0.1, 1.0))
        batch.draw(shader)

    gpu.state.line_width_set(1.0)
    gpu.state.point_size_set(1.0)


# ---------------------------------------------------------------------------
# Operator: thuc hien cat -> Gingiva / Teeth
# ---------------------------------------------------------------------------
class GTSPLIT_OT_execute_cut(bpy.types.Operator):
    """Dung cutter tu vong line da ve va tach object thanh Gingiva / Teeth"""
    bl_idname = "object.gtsplit_execute_cut"
    bl_label = "Tach object"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        if not hw_read_key():
            self.report({'ERROR'}, "Vui long dang ky key de kich hoat su dung")
            return {'CANCELLED'}

        target = context.active_object
        if target is None or target.type != 'MESH':
            self.report({'ERROR'}, "Hay chon object MESH can cat lam active")
            return {'CANCELLED'}

        data = _stroke_cache.get(target.name)
        if not data or len(data["points"]) < 3:
            self.report({'ERROR'}, "Chua co vong line. Hay 'Ve duong cat' truoc.")
            return {'CANCELLED'}

        props = context.scene.gt_split
        offset = props.offset
        gap = props.gap
        if gap <= 0:
            self.report({'ERROR'}, "Gap phai > 0")
            return {'CANCELLED'}

        # Resample + snap toan vong ve be mat -> vong kin day diem.
        loop_pts, loop_nrms = _resample_loop_on_surface(
            target, data["points"], samples_per_edge=props.samples_per_edge)
        if len(loop_pts) < 3:
            self.report({'ERROR'}, "Khong dung duoc vong tren be mat")
            return {'CANCELLED'}

        # Dung cutter.
        cutter = _build_cutter(context, target, loop_pts, loop_nrms, offset, gap)
        if cutter is None:
            self.report({'ERROR'}, "Khong dung duoc cutter")
            return {'CANCELLED'}

        viewlayer = context.view_layer

        # Boolean DIFFERENCE (giong pattern add-on iBar).
        boolean = target.modifiers.new(name="GT_Boolean", type='BOOLEAN')
        boolean.object = cutter
        boolean.operation = 'DIFFERENCE'
        try:
            boolean.solver = 'EXACT'
        except Exception:
            pass
        bpy.ops.object.select_all(action='DESELECT')
        _set_active_object(target, viewlayer)
        _select_object(target, True, viewlayer)
        bpy.ops.object.modifier_apply(modifier="GT_Boolean")

        # Xoa cutter.
        bpy.data.objects.remove(cutter, do_unlink=True)

        # Separate by LOOSE.
        before = set(context.scene.objects)
        _set_active_object(target, viewlayer)
        bpy.ops.object.select_all(action='DESELECT')
        _select_object(target, True, viewlayer)
        bpy.ops.object.editmode_toggle()
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.mesh.separate(type='LOOSE')
        bpy.ops.object.editmode_toggle()
        after = set(context.scene.objects)

        pieces = list((after - before)) + [target]
        pieces = [o for o in pieces if o.name in context.scene.objects and o.type == 'MESH']

        if len(pieces) < 2:
            self.report({'ERROR'},
                        "Vong line chua xuyen het be day object. Hay tang Gap hoac ve lai vong.")
            # Don dep stroke da dung.
            _stroke_cache.pop(target.name, None)
            return {'CANCELLED'}

        # Tinh the tich, sap xep, giu 2 manh lon nhat.
        vols = [(o, _mesh_volume(o)) for o in pieces]
        vols.sort(key=lambda x: x[1], reverse=True)
        total = sum(v for _o, v in vols) or 1.0

        kept = vols[:2]
        scrap = vols[2:]
        # Xoa cac manh vun nho (< 1% tong).
        removed = 0
        for o, v in scrap:
            if v < 0.01 * total:
                bpy.data.objects.remove(o, do_unlink=True)
                removed += 1
            else:
                # Manh dang ke ngoai 2 manh chinh -> giu lai, canh bao.
                pass

        # kept[0] = lon nhat -> Teeth ; kept[1] = nho hon -> Gingiva
        teeth_obj, _tv = kept[0]
        gingiva_obj, _gv = kept[1]
        teeth_obj.name = "Teeth"
        gingiva_obj.name = "Gingiva"

        # Don dep stroke.
        _stroke_cache.pop(target.name, None)

        msg = "Da tach: Teeth + Gingiva (%d manh)." % len(pieces)
        if removed:
            msg += " Da xoa %d manh vun." % removed
        if len(scrap) - removed > 0:
            msg += " Con %d manh dang ke khong duoc gan ten." % (len(scrap) - removed)
            self.report({'WARNING'}, msg)
        else:
            self.report({'INFO'}, msg)
        return {'FINISHED'}


# ---------------------------------------------------------------------------
# Operator: xoa stroke hien tai
# ---------------------------------------------------------------------------
class GTSPLIT_OT_clear(bpy.types.Operator):
    """Xoa vong line da ve cua object hien tai"""
    bl_idname = "object.gtsplit_clear"
    bl_label = "Xoa duong cat"
    bl_options = {'REGISTER'}

    def execute(self, context):
        target = context.active_object
        if target is not None and target.name in _stroke_cache:
            _stroke_cache.pop(target.name, None)
            self.report({'INFO'}, "Da xoa vong line")
        else:
            self.report({'INFO'}, "Khong co vong line de xoa")
        return {'FINISHED'}


# ---------------------------------------------------------------------------
# Panel
# ---------------------------------------------------------------------------
class GTSPLIT_PT_panel(bpy.types.Panel):
    bl_label = "Gingiva / Teeth Split"
    bl_idname = "OBJECT_PT_gtsplit"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "IBAR Split"

    def draw(self, context):
        layout = self.layout
        props = context.scene.gt_split
        col = layout.column(align=True)
        col.operator(GTSPLIT_OT_draw_line.bl_idname, text="Ve duong cat", icon='GREASEPENCIL')

        target = context.active_object
        if target is not None and target.name in _stroke_cache:
            n = len(_stroke_cache[target.name]["points"])
            col.label(text="Vong line: %d diem" % n, icon='CHECKMARK')
            col.operator(GTSPLIT_OT_clear.bl_idname, text="Xoa duong cat", icon='X')
        else:
            col.label(text="Chua co vong line", icon='INFO')

        layout.separator()
        box = layout.box()
        box.prop(props, "offset")
        box.prop(props, "gap")
        box.prop(props, "samples_per_edge")

        layout.separator()
        layout.operator(GTSPLIT_OT_execute_cut.bl_idname, text="Tach object", icon='MOD_BOOLEAN')


# ---------------------------------------------------------------------------
# Register
# ---------------------------------------------------------------------------
_classes = [
    GTSplitProps,
    GTSPLIT_OT_draw_line,
    GTSPLIT_OT_execute_cut,
    GTSPLIT_OT_clear,
    GTSPLIT_PT_panel,
]


def register():
    for cls in _classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.gt_split = bpy.props.PointerProperty(type=GTSplitProps)


def unregister():
    del bpy.types.Scene.gt_split
    for cls in reversed(_classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
