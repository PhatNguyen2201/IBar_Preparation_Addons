bl_info = {
    "name": "Gingiva/Teeth Surface Splitter",
    "author": "Phat Nguyen",
    "version": (2, 0, 0),
    "blender": (4, 5, 3),
    "location": "View3D > Sidebar > IBAR Split",
    "description": "Ve mot vong line dang object bam tren be mat Target va tach thanh Gingiva / Teeth",
    "category": "Object",
}

import bpy
import bmesh
import os
import uuid
import hashlib
from mathutils import Vector


# ---------------------------------------------------------------------------
# ViewLayer safety helpers (sao chép de add-on doc lap voi add-on iBar).
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
# Surface snapping helpers
# ---------------------------------------------------------------------------
# Bat "Face Project" snapping kieu retopo: khi extrude/di chuyen, chinh DINH THAT
# (tam/gizmo) duoc chieu thang xuong be mat Target, chu khong chi rieng cage hien
# thi cua Shrinkwrap. Nho do ca tam va diem extrude deu nam tren be mat.
_SNAP_BACKUP = None


def _enable_surface_snap(context):
    global _SNAP_BACKUP
    ts = context.scene.tool_settings

    if _SNAP_BACKUP is None:
        backup = {"use_snap": ts.use_snap}
        for attr in ("use_snap_translate", "use_snap_nonedit", "use_snap_self",
                     "use_snap_project"):
            if hasattr(ts, attr):
                backup[attr] = getattr(ts, attr)
        for attr in ("snap_elements", "snap_elements_individual"):
            if hasattr(ts, attr):
                backup[attr] = set(getattr(ts, attr))
        _SNAP_BACKUP = backup

    ts.use_snap = True
    if hasattr(ts, "use_snap_translate"):
        try:
            ts.use_snap_translate = True
        except Exception:
            pass
    # Blender 4.x: chieu tung phan tu len be mat object khac.
    if hasattr(ts, "snap_elements_individual"):
        try:
            ts.snap_elements_individual = {'FACE_PROJECT'}
        except Exception:
            pass
    elif hasattr(ts, "snap_elements"):
        try:
            ts.snap_elements = {'FACE'}
        except Exception:
            pass
        if hasattr(ts, "use_snap_project"):
            try:
                ts.use_snap_project = True
            except Exception:
                pass
    # Cho phep snap len object khong o edit mode (Target), khong snap len chinh line.
    if hasattr(ts, "use_snap_nonedit"):
        try:
            ts.use_snap_nonedit = True
        except Exception:
            pass
    if hasattr(ts, "use_snap_self"):
        try:
            ts.use_snap_self = False
        except Exception:
            pass


def _restore_snap(context):
    global _SNAP_BACKUP
    if _SNAP_BACKUP is None:
        return
    ts = context.scene.tool_settings
    for attr, value in _SNAP_BACKUP.items():
        if hasattr(ts, attr):
            try:
                setattr(ts, attr, value)
            except Exception:
                pass
    _SNAP_BACKUP = None


def _snap_bmesh_verts_to_surface(bm, line, target):
    """Ghi de toa do DINH THAT cua line ve dung be mat Target (world).

    Dam bao moi diem (ke ca tam) nam tren be mat du truoc do co bi troi.
    """
    if target is None or target.type != 'MESH':
        return
    mw_t = target.matrix_world
    mwi_t = mw_t.inverted()
    mwl = line.matrix_world
    mwi_l = mwl.inverted()
    for v in bm.verts:
        world_co = mwl @ v.co
        hit, location, _nrm, _idx = target.closest_point_on_mesh(mwi_t @ world_co)
        if hit:
            v.co = mwi_l @ (mw_t @ location)


# ---------------------------------------------------------------------------
# License check (sao chép nguyen khoi tu Final_addon_Ibar_to_ORG.py).
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


def _ordered_world_loop(obj):
    """Doc vong line tu object line theo thu tu noi canh (da ap dung Shrinkwrap).

    Tra ve (points_world, closed) - danh sach dinh world theo thu tu di vong, va
    co la vong kin hay khong.
    """
    depsgraph = bpy.context.evaluated_depsgraph_get()
    eval_obj = obj.evaluated_get(depsgraph)
    me = eval_obj.to_mesh()
    mw = obj.matrix_world

    nverts = len(me.vertices)
    adj = {i: [] for i in range(nverts)}
    for e in me.edges:
        a, b = e.vertices
        adj[a].append(b)
        adj[b].append(a)

    endpoints = [i for i, nb in adj.items() if len(nb) == 1]
    closed = (nverts >= 3 and not endpoints and all(len(nb) == 2 for nb in adj.values()))

    start = endpoints[0] if endpoints else 0
    order = []
    visited = set()
    cur = start
    prev = None
    while cur is not None and cur not in visited:
        visited.add(cur)
        order.append(cur)
        nxts = [v for v in adj[cur] if v != prev and v not in visited]
        prev = cur
        cur = nxts[0] if nxts else None

    pts = [mw @ me.vertices[i].co for i in order]
    eval_obj.to_mesh_clear()
    return pts, closed


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
def _poll_mesh(self, obj):
    return obj.type == 'MESH'


class GTSplitProps(bpy.types.PropertyGroup):
    target_object: bpy.props.PointerProperty(
        name="Target Object",
        description="Object MESH se duoc ve len va tach (line se tu snap vao be mat object nay)",
        type=bpy.types.Object,
        poll=_poll_mesh,
    )
    line_object: bpy.props.PointerProperty(
        name="Line Object",
        description="Object line dang ve",
        type=bpy.types.Object,
    )
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
# Operator: dat Target Object
# ---------------------------------------------------------------------------
class GTSPLIT_OT_set_target(bpy.types.Operator):
    """Dat object MESH dang active lam Target (line se snap vao be mat object nay)"""
    bl_idname = "object.gtsplit_set_target"
    bl_label = "Chon Target Object"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        obj = context.active_object
        if obj is None or obj.type != 'MESH':
            self.report({'ERROR'}, "Hay chon mot object MESH lam active truoc")
            return {'CANCELLED'}
        context.scene.gt_split.target_object = obj
        self.report({'INFO'}, "Da dat Target: %s" % obj.name)
        return {'FINISHED'}


# ---------------------------------------------------------------------------
# Operator: tao line object + vao edit mode de ve
# ---------------------------------------------------------------------------
class GTSPLIT_OT_create_line(bpy.types.Operator):
    """Tao object line bam tren be mat Target va vao Edit Mode de ve (E de extrude diem)"""
    bl_idname = "object.gtsplit_create_line"
    bl_label = "Ve duong cat (tao line)"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        if not hw_read_key():
            self.report({'ERROR'}, "Vui long dang ky key de kich hoat su dung")
            return {'CANCELLED'}

        props = context.scene.gt_split
        target = props.target_object
        if target is None or target.type != 'MESH':
            self.report({'ERROR'}, "Hay dat Target Object truoc (nut Chon Target Object)")
            return {'CANCELLED'}

        # Bao dam dang o Object Mode truoc khi tao.
        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')

        # Xoa line cu neu con.
        if props.line_object is not None and props.line_object.name in bpy.data.objects:
            bpy.data.objects.remove(props.line_object, do_unlink=True)

        # Diem bat dau: snap tam bounding-box ve be mat target.
        center_world = _bbox_center_world(target)
        local_center = target.matrix_world.inverted() @ center_world
        hit, location, _nrm, _idx = target.closest_point_on_mesh(local_center)
        start_world = target.matrix_world @ location if hit else center_world

        me = bpy.data.meshes.new("GT_Line")
        me.from_pydata([start_world], [], [])
        me.update()

        line = bpy.data.objects.new("GT_Line", me)
        context.collection.objects.link(line)

        # Shrinkwrap giu moi dinh line dung tren be mat Target.
        sw = line.modifiers.new(name="GT_Shrinkwrap", type='SHRINKWRAP')
        sw.target = target
        sw.wrap_method = 'NEAREST_SURFACEPOINT'
        sw.wrap_mode = 'ON_SURFACE'
        sw.show_in_editmode = True
        sw.show_on_cage = True

        props.line_object = line

        viewlayer = context.view_layer
        bpy.ops.object.select_all(action='DESELECT')
        _set_active_object(line, viewlayer)
        _select_object(line, True, viewlayer)
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='SELECT')

        # Bat snapping Face Project: dinh that duoc chieu len be mat khi extrude.
        _enable_surface_snap(context)

        self.report(
            {'INFO'},
            "Nhan E de extrude diem tiep theo, xoay view tu do. Xong nhan 'Noi diem dau-cuoi'.")
        return {'FINISHED'}


# ---------------------------------------------------------------------------
# Operator: noi 2 diem dau-cuoi (tuong tu chon 2 diem roi nhan F)
# ---------------------------------------------------------------------------
class GTSPLIT_OT_close_loop(bpy.types.Operator):
    """Noi diem dau va diem cuoi cua line thanh vong kin (tuong tu chon 2 diem + F)"""
    bl_idname = "object.gtsplit_close_loop"
    bl_label = "Noi diem dau-cuoi"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        props = context.scene.gt_split
        line = props.line_object
        if line is None or line.name not in bpy.data.objects:
            self.report({'ERROR'}, "Chua co line. Hay 'Ve duong cat' truoc.")
            return {'CANCELLED'}

        target = props.target_object
        in_edit = (context.mode == 'EDIT_MESH' and context.edit_object == line)

        if in_edit:
            bm = bmesh.from_edit_mesh(line.data)
            ends = [v for v in bm.verts if len(v.link_edges) == 1]
            if len(ends) != 2:
                self.report({'WARNING'},
                            "Can dung 2 diem dau cuoi (line dang co %d diem ho)" % len(ends))
                return {'CANCELLED'}
            try:
                bm.edges.new((ends[0], ends[1]))
            except ValueError:
                self.report({'INFO'}, "Hai diem da duoc noi san")
                return {'CANCELLED'}
            _snap_bmesh_verts_to_surface(bm, line, target)
            bmesh.update_edit_mesh(line.data)
        else:
            bm = bmesh.new()
            bm.from_mesh(line.data)
            bm.verts.ensure_lookup_table()
            ends = [v for v in bm.verts if len(v.link_edges) == 1]
            if len(ends) != 2:
                bm.free()
                self.report({'WARNING'},
                            "Can dung 2 diem dau cuoi (line dang co %d diem ho)" % len(ends))
                return {'CANCELLED'}
            try:
                bm.edges.new((ends[0], ends[1]))
            except ValueError:
                bm.free()
                self.report({'INFO'}, "Hai diem da duoc noi san")
                return {'CANCELLED'}
            _snap_bmesh_verts_to_surface(bm, line, target)
            bm.to_mesh(line.data)
            bm.free()
            line.data.update()

        self.report({'INFO'}, "Da noi diem dau-cuoi (vong kin), moi diem da bam be mat")
        return {'FINISHED'}


# ---------------------------------------------------------------------------
# Operator: thuc hien cat -> Gingiva / Teeth
# ---------------------------------------------------------------------------
class GTSPLIT_OT_execute_cut(bpy.types.Operator):
    """Dung cutter tu vong line da ve va tach Target thanh Gingiva / Teeth"""
    bl_idname = "object.gtsplit_execute_cut"
    bl_label = "Tach object"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        if not hw_read_key():
            self.report({'ERROR'}, "Vui long dang ky key de kich hoat su dung")
            return {'CANCELLED'}

        props = context.scene.gt_split
        target = props.target_object
        if target is None or target.type != 'MESH':
            self.report({'ERROR'}, "Chua co Target Object")
            return {'CANCELLED'}

        line = props.line_object
        if line is None or line.name not in bpy.data.objects:
            self.report({'ERROR'}, "Chua co line. Hay 'Ve duong cat' truoc.")
            return {'CANCELLED'}

        gap = props.gap
        if gap <= 0:
            self.report({'ERROR'}, "Gap phai > 0")
            return {'CANCELLED'}

        # Ve Object Mode de doc/xu ly an toan.
        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')

        # Doc vong line (da snap tren be mat nho Shrinkwrap) theo thu tu.
        raw_pts, closed = _ordered_world_loop(line)
        if not closed:
            self.report({'ERROR'},
                        "Vong chua kin. Hay nhan 'Noi diem dau-cuoi' truoc khi tach.")
            return {'CANCELLED'}
        if len(raw_pts) < 3:
            self.report({'ERROR'}, "Can it nhat 3 diem de tao vong kin")
            return {'CANCELLED'}

        # Resample + snap toan vong ve be mat -> vong kin day diem.
        loop_pts, loop_nrms = _resample_loop_on_surface(
            target, raw_pts, samples_per_edge=props.samples_per_edge)
        if len(loop_pts) < 3:
            self.report({'ERROR'}, "Khong dung duoc vong tren be mat")
            return {'CANCELLED'}

        # Dung cutter.
        cutter = _build_cutter(context, target, loop_pts, loop_nrms, props.offset, gap)
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
            return {'CANCELLED'}

        # Tinh the tich, sap xep, giu 2 manh lon nhat.
        vols = [(o, _mesh_volume(o)) for o in pieces]
        vols.sort(key=lambda x: x[1], reverse=True)
        total = sum(v for _o, v in vols) or 1.0

        kept = vols[:2]
        scrap = vols[2:]
        removed = 0
        for o, v in scrap:
            if v < 0.01 * total:
                bpy.data.objects.remove(o, do_unlink=True)
                removed += 1

        # kept[0] = lon nhat -> Teeth ; kept[1] = nho hon -> Gingiva
        teeth_obj, _tv = kept[0]
        gingiva_obj, _gv = kept[1]
        teeth_obj.name = "Teeth"
        gingiva_obj.name = "Gingiva"

        # Don dep line + khoi phuc cai dat snap cua nguoi dung.
        if props.line_object is not None and props.line_object.name in bpy.data.objects:
            bpy.data.objects.remove(props.line_object, do_unlink=True)
        props.line_object = None
        _restore_snap(context)

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
# Operator: xoa line hien tai
# ---------------------------------------------------------------------------
class GTSPLIT_OT_clear(bpy.types.Operator):
    """Xoa object line dang ve"""
    bl_idname = "object.gtsplit_clear"
    bl_label = "Xoa duong cat"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        props = context.scene.gt_split
        line = props.line_object
        if line is not None and line.name in bpy.data.objects:
            if context.mode != 'OBJECT':
                bpy.ops.object.mode_set(mode='OBJECT')
            bpy.data.objects.remove(line, do_unlink=True)
            props.line_object = None
            _restore_snap(context)
            self.report({'INFO'}, "Da xoa line")
        else:
            _restore_snap(context)
            self.report({'INFO'}, "Khong co line de xoa")
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

        # 1) Target Object - nut doi ten thanh ten Target khi da chon.
        box = layout.box()
        box.label(text="1. Target Object", icon='OBJECT_DATA')
        target = props.target_object
        if target is not None and target.name in bpy.data.objects:
            box.operator(GTSPLIT_OT_set_target.bl_idname,
                         text=target.name, icon='RESTRICT_SELECT_OFF')
        else:
            box.operator(GTSPLIT_OT_set_target.bl_idname,
                         text="Chon Target Object", icon='EYEDROPPER')

        # 2) Ve line.
        box = layout.box()
        box.label(text="2. Ve duong cat", icon='GREASEPENCIL')
        col = box.column(align=True)
        row = col.row()
        row.enabled = target is not None
        row.operator(GTSPLIT_OT_create_line.bl_idname, text="Ve duong cat (tao line)",
                     icon='GREASEPENCIL')

        line = props.line_object
        has_line = line is not None and line.name in bpy.data.objects
        col.label(text="Edit Mode: E them diem (da bat snap be mat)", icon='INFO')
        sub = col.column(align=True)
        sub.enabled = has_line
        sub.operator(GTSPLIT_OT_close_loop.bl_idname, text="Noi diem dau-cuoi (F)",
                     icon='MESH_CIRCLE')
        sub.operator(GTSPLIT_OT_clear.bl_idname, text="Xoa line", icon='X')

        # 3) Tham so + tach.
        box = layout.box()
        box.label(text="3. Tach object", icon='MOD_BOOLEAN')
        box.prop(props, "offset")
        box.prop(props, "gap")
        box.prop(props, "samples_per_edge")
        row = box.row()
        row.enabled = has_line and target is not None
        row.operator(GTSPLIT_OT_execute_cut.bl_idname, text="Tach object", icon='MOD_BOOLEAN')


# ---------------------------------------------------------------------------
# Register
# ---------------------------------------------------------------------------
_classes = [
    GTSplitProps,
    GTSPLIT_OT_set_target,
    GTSPLIT_OT_create_line,
    GTSPLIT_OT_close_loop,
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
