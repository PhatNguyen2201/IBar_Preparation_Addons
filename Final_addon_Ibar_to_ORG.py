bl_info = {
    "name": "Custom Ibar Preparation Panel",
    "author": "Phat Nguyen",
    "version": (2, 3, 4),
    "blender": (4, 5, 3),
    "location": "View3D Panel",
    "description": "iBar Custom Panel",
    "warning": "",
    "doc_url": "",
    "category": "iBar Preparation Panel",
}

import bpy
import uuid
import os
import hashlib
import math
import re
import json
import shutil
import urllib.error
import urllib.request
import mathutils
from bpy.props import StringProperty, CollectionProperty
from bpy.types import Operator
from bpy_extras.io_utils import ImportHelper
from pathlib import Path
from mathutils import Vector
import xml.etree.ElementTree as ET
from typing import List, Dict

GITHUB_OWNER = "PhatNguyen2201"
GITHUB_REPO = "IBar_Preparation_Addons"
GITHUB_BRANCH = "main"
GITHUB_FILE_PATH = "Final_addon_Ibar_to_ORG.py"
GITHUB_BRANCH_FALLBACKS = ("main", "master")


def _version_to_str(version_tuple):
    return ".".join(str(v) for v in version_tuple)


def _http_get_text(url):
    request = urllib.request.Request(url, headers={"User-Agent": "Blender-Ibar-Updater"})
    with urllib.request.urlopen(request, timeout=20) as response:
        return response.read().decode("utf-8")


def _discover_remote_download_url():
    branches = [GITHUB_BRANCH] + [b for b in GITHUB_BRANCH_FALLBACKS if b != GITHUB_BRANCH]
    file_candidates = [GITHUB_FILE_PATH, Path(__file__).name]
    last_error = None

    for branch in branches:
        api_url = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/contents/?ref={branch}"
        try:
            root_items = json.loads(_http_get_text(api_url))
        except Exception as err:
            last_error = err
            continue

        if not isinstance(root_items, list):
            continue

        for candidate in file_candidates:
            for item in root_items:
                if item.get("type") == "file" and item.get("name") == candidate:
                    download_url = item.get("download_url")
                    if download_url:
                        return download_url

    raise FileNotFoundError(
        f"Khong tim thay file add-on tren GitHub ({GITHUB_OWNER}/{GITHUB_REPO}). Loi cuoi: {last_error}"
    )


def _fetch_remote_addon_source():
    raw_url = _discover_remote_download_url()
    return _http_get_text(raw_url)


def _extract_version_from_source(source_text):
    match = re.search(r'"version"\s*:\s*\((\d+)\s*,\s*(\d+)\s*,\s*(\d+)\)', source_text)
    if not match:
        raise ValueError("Khong tim thay thong tin version trong file update")
    return tuple(int(item) for item in match.groups())


def _get_remote_version_and_source():
    source_text = _fetch_remote_addon_source()
    return _extract_version_from_source(source_text), source_text


class IBAR_OT_CheckAddonUpdate(bpy.types.Operator):
    """Check for a newer addon version on GitHub"""
    bl_idname = "ibar.check_addon_update"
    bl_label = "Check Update"

    def execute(self, context):
        local_version = tuple(bl_info.get("version", (0, 0, 0)))
        try:
            remote_version, _ = _get_remote_version_and_source()
        except urllib.error.HTTPError as err:
            self.report({'ERROR'}, f"Loi HTTP khi kiem tra update: {err.code}")
            return {'FINISHED'}
        except Exception as err:
            self.report({'ERROR'}, f"Khong the kiem tra update: {err}")
            return {'FINISHED'}

        if remote_version > local_version:
            self.report(
                {'INFO'},
                f"Co ban moi: {_version_to_str(local_version)} -> {_version_to_str(remote_version)}",
            )
        else:
            self.report({'INFO'}, f"Dang la ban moi nhat: {_version_to_str(local_version)}")
        return {'FINISHED'}


class IBAR_OT_UpdateAddonFromGitHub(bpy.types.Operator):
    """Update this addon file from GitHub"""
    bl_idname = "ibar.update_addon_from_github"
    bl_label = "Update From GitHub"

    def execute(self, context):
        local_version = tuple(bl_info.get("version", (0, 0, 0)))
        try:
            remote_version, remote_source = _get_remote_version_and_source()
        except urllib.error.HTTPError as err:
            self.report({'ERROR'}, f"Loi HTTP khi tai update: {err.code}")
            return {'FINISHED'}
        except Exception as err:
            self.report({'ERROR'}, f"Khong the tai update: {err}")
            return {'FINISHED'}

        if remote_version <= local_version:
            self.report({'INFO'}, f"Khong co ban moi hon {_version_to_str(local_version)}")
            return {'FINISHED'}

        addon_file = Path(__file__)
        backup_file = addon_file.with_suffix(addon_file.suffix + ".bak")

        try:
            shutil.copy2(addon_file, backup_file)
            addon_file.write_text(remote_source, encoding="utf-8")
        except Exception as err:
            self.report({'ERROR'}, f"Cap nhat that bai: {err}")
            return {'FINISHED'}

        self.report(
            {'WARNING'},
            (
                f"Da cap nhat len {_version_to_str(remote_version)}. "
                "Vui long disable/enable lai add-on hoac khoi dong lai Blender"
            ),
        )
        return {'FINISHED'}

class buttonOperator_SetORG(bpy.types.Operator):
    """Get ORG object info"""
    bl_idname = "object.pnfunction1"
    bl_label = "Get ORG Object"

    def execute(self, context):
        if not hw_read_key():
            self.report({'ERROR'},"Vui lòng đăng ký key để kích hoạt sử dụng")
            return {'FINISHED'}
        obj = bpy.context.active_object
        if obj == None:
            self.report({'ERROR'},"Vui lòng tải file vào và chọn vào đối tượng cần làm việc để tiếp tục")
            return {'FINISHED'}
        bpy.ops.object.origin_set(type='ORIGIN_CENTER_OF_MASS', center='MEDIAN')
        obj.name = "Models"
        matrixObjectORG = bpy.context.object.matrix_world
        path = bpy.path.abspath("//")
        if path == '':
           self.report({'ERROR'},"Vui lòng lưu project trước khi bắt đầu")
           return {'FINISHED'}
        file_path = Path(path) / "before.txt"
        if file_path.exists():
           self.report({'ERROR'},"Đã tồn tại dữ liệu tọa độ. Vui lòng dùng offset transform để đưa về tọa độ làm việc")
           return {'FINISHED'}
        file = open(file_path, "w")
        file.write("{}, {}, {}, {}\n".format(matrixObjectORG[0][0], matrixObjectORG[0][1], matrixObjectORG[0][2],matrixObjectORG[0][3]))
        file.write("{}, {}, {}, {}\n".format(matrixObjectORG[1][0], matrixObjectORG[1][1], matrixObjectORG[1][2],matrixObjectORG[1][3]))
        file.write("{}, {}, {}, {}\n".format(matrixObjectORG[2][0], matrixObjectORG[2][1], matrixObjectORG[2][2],matrixObjectORG[2][3]))
        file.write("{}, {}, {}, {}\n".format(matrixObjectORG[3][0], matrixObjectORG[3][1], matrixObjectORG[3][2],matrixObjectORG[3][3]))
        file.close()
        collection_models = bpy.data.collections.new("Models")
        collection = bpy.data.collections.get("Collection")
        bpy.context.scene.collection.children.link(collection_models)
        if obj.name in collection.objects:
            collection.objects.unlink(obj)
        if obj.name not in collection_models.objects:
            collection_models.objects.link(obj)
        self.report({'INFO'},"Đã lưu ORG! Tiếp theo chọn 3 điểm để đưa hàm vào mặt phẳng")
        return {'FINISHED'}

class buttonOperator_SaveSTL(bpy.types.Operator):
    """Save Ibar design without ORG"""
    bl_idname = "object.pnfunction2"
    bl_label = "STLs"

    def execute(self, context):
        if not hw_read_key():
            self.report({'ERROR'},"Vui lòng đăng ký key để kích hoạt sử dụng")
            return {'FINISHED'}
        scene = context.scene
        viewlayer = context.view_layer
        obs = [o for o in scene.objects if o.type == 'MESH']
        bpy.ops.object.select_all(action='DESELECT')

        path = bpy.path.abspath("//")
        for ob in obs:
            viewlayer.objects.active = ob
            if ob.name == "Hybrid_Shell" or ob.name == "iBar" or ob.name == "Closed_Bar":
                ob.select_set(True)
                stl_path = path + f"{ob.name}.stl"
                bpy.ops.export_mesh.stl(
                    filepath=str(stl_path),
                    use_selection=True)
                ob.select_set(False)
        return {'FINISHED'}

class buttonOperator_SaveSTLORG(bpy.types.Operator):
    """Save Ibar design ORG"""
    bl_idname = "object.pnfunction3"
    bl_label = "STLs ORG"

    def execute(self, context):
        if not hw_read_key():
            self.report({'ERROR'},"Vui lòng đăng ký key để kích hoạt sử dụng")
            return {'FINISHED'}
        scene = context.scene
        viewlayer = context.view_layer
        obs = [o for o in scene.objects if o.type == 'MESH']
        
        path = bpy.path.abspath("//")
        file_path = path + "transform.txt"
        file = open(file_path, "r")
        lines = file.readlines()
        matrixObjectTransform = bpy.context.scene.cursor.matrix
        matrixValues1 = lines[0].split(",")
        matrixValues2 = lines[1].split(",")
        matrixValues3 = lines[2].split(",")
        matrixValues4 = lines[3].split(",")
        matrixObjectTransform[0] = [float(val) for val in matrixValues1]
        matrixObjectTransform[1] = [float(val) for val in matrixValues2]
        matrixObjectTransform[2] = [float(val) for val in matrixValues3]
        matrixObjectTransform[3] = [float(val) for val in matrixValues4]

        bpy.ops.object.select_all(action='DESELECT')

        bpy.ops.object.empty_add(type='ARROWS', radius=10, align='WORLD', location=(0, 0, 0), scale=(1, 1, 1))
        object = bpy.context.active_object
        object.matrix_world = matrixObjectTransform

        for obj in bpy.context.selected_objects:
            obj.name = "fileORG"
        for ob in obs:
            if ob.name == "Closed_Bar":
                ob.select_set(True)
            if ob.name == "Hybrid_Shell":
                ob.select_set(True)
            if ob.name == "iBar":
                ob.select_set(True)
        bpy.ops.object.parent_set(type='OBJECT')
        file_pathORG = path + "before.txt"
        fileORG = open(file_pathORG, "r")
        linesORG = fileORG.readlines()
        matrixObjectORG = bpy.context.scene.cursor.matrix
        matrixValuesORG1 = linesORG[0].split(",")
        matrixValuesORG2 = linesORG[1].split(",")
        matrixValuesORG3 = linesORG[2].split(",")
        matrixValuesORG4 = linesORG[3].split(",")
        matrixObjectORG[0] = [float(val) for val in matrixValuesORG1]
        matrixObjectORG[1] = [float(val) for val in matrixValuesORG2]
        matrixObjectORG[2] = [float(val) for val in matrixValuesORG3]
        matrixObjectORG[3] = [float(val) for val in matrixValuesORG4]
        
        object2 = bpy.context.active_object
        object2.matrix_world = matrixObjectORG

        bpy.ops.object.select_all(action='DESELECT')
        
        for ob in obs:
            viewlayer.objects.active = ob
            if ob.name == "Hybrid_Shell" or ob.name == "iBar" or ob.name == "Closed_Bar":
                ob.select_set(True)
                stl_path = path + f"{ob.name}.stl"
                bpy.ops.export_mesh.stl(
                    filepath=str(stl_path),
                    use_selection=True)
                ob.select_set(False)
        bpy.ops.object.select_all(action='DESELECT')
        objectArrows = bpy.data.objects['fileORG']
        objectArrows.select_set(True)
        for ob in obs:
            if ob.name == "Hybrid_Shell" or ob.name == "iBar" or ob.name == "Closed_Bar":
                ob.select_set(True)
        bpy.ops.object.parent_clear(type='CLEAR_KEEP_TRANSFORM')
        bpy.data.objects.remove(objectArrows)
        return {'FINISHED'}

class buttonOperator_GetTransformORG(bpy.types.Operator):
    """Get Object Transform"""
    bl_idname = "object.pnfunction4"
    bl_label = "Get transform to ORG"
    def execute(self, context):
        if not hw_read_key():
            self.report({'ERROR'},"Vui lòng đăng ký key để kích hoạt sử dụng")
            return {'FINISHED'}
        bpy.context.view_layer.objects.active = bpy.data.objects['Models']
        obj = bpy.context.active_object
        matrixObjectORG = bpy.context.object.matrix_world
        path = bpy.path.abspath("//")
        file_path = Path(path) / "transform.txt"
        if file_path.exists():
           self.report({'ERROR'},"Đã tồn tại dữ liệu tọa độ. Vui lòng dùng offset transform để đưa về tọa độ làm việc")
           return {'FINISHED'}
        file = open(file_path, "w")
        file.write("{}, {}, {}, {}\n".format(matrixObjectORG[0][0], matrixObjectORG[0][1], matrixObjectORG[0][2],matrixObjectORG[0][3]))
        file.write("{}, {}, {}, {}\n".format(matrixObjectORG[1][0], matrixObjectORG[1][1], matrixObjectORG[1][2],matrixObjectORG[1][3]))
        file.write("{}, {}, {}, {}\n".format(matrixObjectORG[2][0], matrixObjectORG[2][1], matrixObjectORG[2][2],matrixObjectORG[2][3]))
        file.write("{}, {}, {}, {}\n".format(matrixObjectORG[3][0], matrixObjectORG[3][1], matrixObjectORG[3][2],matrixObjectORG[3][3]))
        file.close()
        bpy.ops.object.editmode_toggle()
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.mesh.separate(type='LOOSE')
        bpy.ops.object.editmode_toggle()
        self.report({'INFO'},"Đã lưu vị trí hàm! Vui lòng chuyển sang add-on IBAR và tiếp tục quy trình thông thường")
        return {'FINISHED'}

class buttonAddRedPoint1(bpy.types.Operator):
    """Add Incisor Point"""
    bl_idname = "object.pnfunction5"
    bl_label = "Add Q1-Q3 Molar Point"
    def execute(self, context):
        if not hw_read_key():
            self.report({'ERROR'},"Vui lòng đăng ký key để kích hoạt sử dụng")
            return {'FINISHED'}
        for ob in bpy.context.scene.objects:
            if ob.name == "pointLeft":
                bpy.data.objects.remove(ob)
        cursorLocation = bpy.context.scene.cursor.location
        bpy.ops.mesh.primitive_uv_sphere_add(enter_editmode=False, align='WORLD', location=cursorLocation, scale=(0.5, 0.5, 0.5))
        matg = bpy.data.materials.new("Red")
        matg.diffuse_color = (0.8, 0, 0, 1)
        for obj in bpy.context.selected_objects:
            obj.active_material = matg
            obj.name = "pointLeft"
        return {'FINISHED'}
class buttonAddRedPoint2(bpy.types.Operator):
    """Add Q1-Q3 Molar Point"""
    bl_idname = "object.pnfunction6"
    bl_label = "Add Incisor Point"
    def execute(self, context):
        if not hw_read_key():
            self.report({'ERROR'},"Vui lòng đăng ký key để kích hoạt sử dụng")
            return {'FINISHED'}
        for ob in bpy.context.scene.objects:
            if ob.name == "pointIncisor":
                bpy.data.objects.remove(ob)
        cursorLocation = bpy.context.scene.cursor.location
        bpy.ops.mesh.primitive_uv_sphere_add(enter_editmode=False, align='WORLD', location=cursorLocation, scale=(0.5, 0.5, 0.5))
        matg = bpy.data.materials.new("Green")
        matg.diffuse_color = (0, 0.8, 0, 1)
        for obj in bpy.context.selected_objects:
            obj.active_material = matg
            obj.name = "pointIncisor"
        return {'FINISHED'}
class buttonAddRedPoint3(bpy.types.Operator):
    """Add Q2-Q4 Molar Point"""
    bl_idname = "object.pnfunction7"
    bl_label = "Add Q2-Q4 Molar Point"
    def execute(self, context):
        if not hw_read_key():
            self.report({'ERROR'},"Vui lòng đăng ký key để kích hoạt sử dụng")
            return {'FINISHED'}
        for ob in bpy.context.scene.objects:
            if ob.name == "pointRight":
                bpy.data.objects.remove(ob)
        cursorLocation = bpy.context.scene.cursor.location
        bpy.ops.mesh.primitive_uv_sphere_add(enter_editmode=False, align='WORLD', location=cursorLocation, scale=(0.5, 0.5, 0.5))
        matg = bpy.data.materials.new("Blue")
        matg.diffuse_color = (0, 0, 0.8, 1)
        for obj in bpy.context.selected_objects:
            obj.active_material = matg
            obj.name = "pointRight"
        return {'FINISHED'}

class buttonOperator_TransformToPlane(bpy.types.Operator):
    """Align Selected To Occlusal Plane"""
    bl_idname = "object.pnfunction8"
    bl_label = "Align To OcclusalPlane"

    def execute(self, context):
        if not hw_read_key():
            self.report({'ERROR'},"Vui lòng đăng ký key để kích hoạt sử dụng")
            return {'FINISHED'}
        def calMultiVector(vect1, vect2):
            xVec = vect1[1]*vect2[2] - vect1[2]*vect2[1]
            yVec = vect1[2]*vect2[0] - vect1[0]*vect2[2]
            zVec = vect1[0]*vect2[1] - vect1[1]*vect2[0]
            return mathutils.Vector((xVec, yVec, zVec))
        def calAveragePoint(p1,p2,p3):
            xPoint = (p1[0] + p2[0] + p3[0])/3
            yPoint = (p1[1] + p2[1] + p3[1])/3
            zPoint = (p1[2] + p2[2] + p3[2])/3
            return mathutils.Vector((xPoint, yPoint, zPoint))
        def calVectorToMatrixRotationItem(vect):
            nValue = 1/math.sqrt(vect[0]**2 + vect[1]**2 + vect[2]**2)
            xVect = vect[0]*nValue
            yVect = vect[1]*nValue
            zVect = vect[2]*nValue
            return mathutils.Vector((xVect, yVect, zVect))

        def convertThreePointToMatrix(p1,p2,p3):
            averagePoint = calAveragePoint(point1,point2,point3)
            vector1 = mathutils.Vector((point2[0]-point1[0],point2[1]-point1[1],point2[2]-point1[2]))
            vector2 = mathutils.Vector((point3[0]-point2[0],point3[1]-point2[1],point3[2]-point2[2]))
            vector3 = mathutils.Vector((point1[0]-point3[0],point1[1]-point3[1],point1[2]-point3[2]))
            ZVector = calMultiVector(vector2, vector1)
            YVector = calMultiVector(ZVector, vector3)
            XVector = calMultiVector(YVector, ZVector)
            Zmatrix = calVectorToMatrixRotationItem(ZVector)
            Ymatrix = calVectorToMatrixRotationItem(YVector)
            Xmatrix = calVectorToMatrixRotationItem(XVector)
            return mathutils.Matrix(((Xmatrix.x,Ymatrix.x,Zmatrix.x,averagePoint[0]),(Xmatrix.y,Ymatrix.y,Zmatrix.y,averagePoint[1]),(Xmatrix.z,Ymatrix.z,Zmatrix.z,averagePoint[2]),(0,0,0,1)))
        scene = bpy.context.scene
        viewlayer = bpy.context.view_layer
        obs = [o for o in scene.objects if o.type == 'MESH']
        bpy.ops.object.select_all(action='DESELECT')

        point1 = mathutils.Vector((0, 0, 0))
        point2 = mathutils.Vector((0, 0, 0))
        point3 = mathutils.Vector((0, 0, 0))

        for ob in obs:
            viewlayer.objects.active = ob
            if ob.name == "pointLeft":
                point1 = ob.location
                continue
            if ob.name == "pointIncisor":
                point2 = ob.location
                continue
            if ob.name == "pointRight":
                point3 = ob.location
                continue

        matrixTranformToPlane = convertThreePointToMatrix(point1,point2,point3)
        bpy.ops.object.select_all(action='DESELECT')
        bpy.ops.object.empty_add(type='ARROWS', radius=10, align='WORLD', location=(0, 0, 0), scale=(1, 1, 1))
        object = bpy.context.active_object
        object.matrix_world = matrixTranformToPlane
        for obj in bpy.context.selected_objects:
            obj.name = "ArrowAxisTransform"
        
        objectpoint1 = bpy.data.objects['pointIncisor']
        objectpoint2 = bpy.data.objects['pointRight']
        objectpoint3 = bpy.data.objects['pointLeft']
        bpy.data.objects.remove(objectpoint1)
        bpy.data.objects.remove(objectpoint2)
        bpy.data.objects.remove(objectpoint3)
        bpy.ops.object.select_all(action='DESELECT')
        objectArrows = bpy.data.objects['ArrowAxisTransform']
        objectwaxup = bpy.data.objects['Models']

        objectArrows.select_set(True)
        objectwaxup.select_set(True)

        bpy.context.view_layer.objects.active = objectArrows
        bpy.ops.object.parent_set(type='OBJECT')

        objectArrows.location.x = 0
        objectArrows.location.y = 0
        objectArrows.location.z = 0
        objectArrows.rotation_euler.x = 0
        objectArrows.rotation_euler.y = 0
        objectArrows.rotation_euler.z = 0    
        bpy.ops.object.parent_clear(type='CLEAR_KEEP_TRANSFORM')
        bpy.data.objects.remove(objectArrows)
        return {'FINISHED'}

class buttonOperator_ImportAllSTL(bpy.types.Operator):
    """Import all STL in project"""
    bl_idname = "object.pnfunction9"
    bl_label = "Import all STL"
    def execute(self, context):
        if not hw_read_key():
            self.report({'ERROR'},"Vui lòng đăng ký key để kích hoạt sử dụng")
            return {'FINISHED'}
        path = bpy.path.abspath("//")
        if path == '':
           self.report({'ERROR'},"Vui lòng lưu project vào thư mục chứa stl đã chuẩn bị. Có thể sử dụng tổ hợp phím Ctrl-Shift-S sau đó chọn vị trí lưu")
           return {'FINISHED'}
        dir_list = os.listdir(path)
        for item in dir_list:
            if item.endswith('.stl'):
                fullFileName = path + "//" + item
                bpy.ops.wm.stl_import(filepath=fullFileName)
        
        self.report({'INFO'},"Đã tải vào các file STL! Tiếp theo chọn Set Object ORG để lấy vị trí ORG của vật thể")
        return {'FINISHED'}
        
class buttonSetAsGingiva(bpy.types.Operator):
    """Set Selected as Gingiva"""
    bl_idname = "object.pnfunction10"
    bl_label = "Set as Gingiva"
    def execute(self, context):
        if not hw_read_key():
            self.report({'ERROR'},"Vui lòng đăng ký key để kích hoạt sử dụng")
            return {'FINISHED'}
        matg = bpy.data.materials.new("Gingiva")
        matg.diffuse_color = (0.7, 0.4, 0.4, 0.5)
        for obj in bpy.context.selected_objects:
            obj.active_material = matg
            obj.name = "Gingiva"
        return {'FINISHED'}
class buttonSetAsScrews(bpy.types.Operator):
    """Set Selected as Screws"""
    bl_idname = "object.pnfunction11"
    bl_label = "Set as Screws"
    def execute(self, context):
        if not hw_read_key():
            self.report({'ERROR'},"Vui lòng đăng ký key để kích hoạt sử dụng")
            return {'FINISHED'}
        mats = bpy.data.materials.new("Screw")
        mats.diffuse_color = (0.3, 0.3, 0.3, 1)
        for obj in bpy.context.selected_objects:
            obj.active_material = mats
            obj.name = "Screw"
        bpy.ops.object.origin_set(type='ORIGIN_CENTER_OF_MASS', center='MEDIAN')
        return {'FINISHED'}
        
class buttonSnapToScrews(bpy.types.Operator):
    """Snap Cursor to Screw"""
    bl_idname = "object.pnfunction12"
    bl_label = "Snap Cursor to Screw"
    def execute(self, context):        
        if not hw_read_key():
            self.report({'ERROR'},"Vui lòng đăng ký key để kích hoạt sử dụng")
            return {'FINISHED'}
        bpy.ops.view3d.snap_cursor_to_selected()
        return {'FINISHED'}

class buttonDeleteOther(bpy.types.Operator):
    """Delete Other object"""
    bl_idname = "object.pnfunction13"
    bl_label = "Delete Other object"
    def execute(self, context):
        if not hw_read_key():
            self.report({'ERROR'},"Vui lòng đăng ký key để kích hoạt sử dụng")
            return {'FINISHED'}
        scene = bpy.context.scene
        viewlayer = bpy.context.view_layer
        obs = [o for o in scene.objects if o.type == 'MESH']
        bpy.ops.object.select_all(action='DESELECT')
        for ob in obs:
            if ob.name.find('Models') > -1:
                bpy.data.objects.remove(ob)
        return {'FINISHED'}

class buttonFramework_Thickness(bpy.types.Operator):
    """Create Framework thickness from Waxup design"""
    bl_idname = "object.pnfunction14"
    bl_label = "Create Framework thickness from Waxup design"
    def execute(seft, context):
        if not hw_read_key():
            self.report({'ERROR'},"Vui lòng đăng ký key để kích hoạt sử dụng")
            return {'FINISHED'}
        obj = bpy.context.active_object
        new_obj = obj.copy()
        new_obj.data = obj.data.copy()
        bpy.context.collection.objects.link(new_obj)

        bpy.ops.object.select_all(action='DESELECT')
        new_obj.select_set(True)
        bpy.context.view_layer.objects.active = new_obj
        new_obj.name = 'framework_thickness'

        bpy.ops.object.modifier_add(type='REMESH')
        bpy.context.object.modifiers["Remesh"].mode = 'SMOOTH'
        bpy.context.object.modifiers["Remesh"].octree_depth = 7
        bpy.context.object.modifiers["Remesh"].use_smooth_shade = True
        bpy.ops.object.modifier_apply(modifier="Remesh")

        bpy.ops.object.modifier_add(type='SOLIDIFY')
        bpy.context.object.modifiers["Solidify"].solidify_mode = 'NON_MANIFOLD'
        bpy.context.object.modifiers["Solidify"].thickness = 1.5
        bpy.context.object.modifiers["Solidify"].nonmanifold_thickness_mode = 'FIXED'
        bpy.context.object.modifiers["Solidify"].use_flip_normals = True
        bpy.ops.object.modifier_apply(modifier="Solidify")

        bpy.ops.object.editmode_toggle()
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.mesh.separate(type='LOOSE')
        bpy.ops.object.editmode_toggle()

        scene = bpy.context.scene
        viewlayer = bpy.context.view_layer
        obs = [o for o in scene.objects if o.type == 'MESH']
        bpy.ops.object.select_all(action='DESELECT')
        matg = bpy.data.materials.new("Red")
        matg.diffuse_color = (0.8, 0, 0, 0.3)
        for obj in obs:
            if obj.name.find(new_obj.name) > -1:
                viewlayer.objects.active = obj
                bpy.ops.object.modifier_add(type='REMESH')
                bpy.context.object.modifiers["Remesh"].mode = 'SMOOTH'
                bpy.context.object.modifiers["Remesh"].octree_depth = 7
                bpy.context.object.modifiers["Remesh"].use_smooth_shade = True
                bpy.ops.object.modifier_apply(modifier="Remesh")
                obj.active_material = matg
        return {'FINISHED'}
        
class buttonOperator_TransformToCurrentDesign(bpy.types.Operator):
    """Offset selected from ORG to current"""
    bl_idname = "object.pnfunction15"
    bl_label = "Offset selected from ORG to current"

    def execute(self, context):
        if not hw_read_key():
            self.report({'ERROR'},"Vui lòng đăng ký key để kích hoạt sử dụng")
            return {'FINISHED'}
        scene = context.scene
        viewlayer = context.view_layer
        obs = [o for o in scene.objects if o.type == 'MESH']

        for obj in bpy.context.selected_objects:
            obj.name = "MeshTransform"
        path = bpy.path.abspath("//")
        file_pathORG = path + "before.txt"
        fileORG = open(file_pathORG, "r")
        linesORG = fileORG.readlines()
        matrixObjectORG = bpy.context.scene.cursor.matrix
        matrixValuesORG1 = linesORG[0].split(",")
        matrixValuesORG2 = linesORG[1].split(",")
        matrixValuesORG3 = linesORG[2].split(",")
        matrixValuesORG4 = linesORG[3].split(",")
        matrixObjectORG[0] = [float(val) for val in matrixValuesORG1]
        matrixObjectORG[1] = [float(val) for val in matrixValuesORG2]
        matrixObjectORG[2] = [float(val) for val in matrixValuesORG3]
        matrixObjectORG[3] = [float(val) for val in matrixValuesORG4]

        bpy.ops.object.select_all(action='DESELECT')

        bpy.ops.object.empty_add(type='ARROWS', radius=10, align='WORLD', location=(0, 0, 0), scale=(1, 1, 1))
        object = bpy.context.active_object
        object.matrix_world = matrixObjectORG
        object.name = "currentAxis"
        objectArrows = bpy.data.objects['currentAxis']
        for ob in obs:
            viewlayer.objects.active = ob
            if ob.name.find('MeshTransform')>-1:
                ob.select_set(True)
        bpy.context.view_layer.objects.active = objectArrows
        bpy.ops.object.parent_set(type='OBJECT')

        file_path = path + "transform.txt"
        file = open(file_path, "r")
        lines = file.readlines()
        matrixObjectTransform = bpy.context.scene.cursor.matrix
        matrixValues1 = lines[0].split(",")
        matrixValues2 = lines[1].split(",")
        matrixValues3 = lines[2].split(",")
        matrixValues4 = lines[3].split(",")
        matrixObjectTransform[0] = [float(val) for val in matrixValues1]
        matrixObjectTransform[1] = [float(val) for val in matrixValues2]
        matrixObjectTransform[2] = [float(val) for val in matrixValues3]
        matrixObjectTransform[3] = [float(val) for val in matrixValues4]

        object2 = bpy.context.active_object
        object2.matrix_world = matrixObjectTransform

        objectArrows.select_set(True)
        for ob in obs:
            viewlayer.objects.active = ob
            if ob.name.find('MeshTransform')>-1:
                ob.select_set(True)
        bpy.ops.object.parent_clear(type='CLEAR_KEEP_TRANSFORM')
        bpy.data.objects.remove(objectArrows)
        return {'FINISHED'}
        
class buttonOperator_SaveAllSTL(bpy.types.Operator):
    """Save All object to STL """
    bl_idname = "object.pnfunction16"
    bl_label = "STLs"

    def execute(self, context):
        if not hw_read_key():
            self.report({'ERROR'},"Vui lòng đăng ký key để kích hoạt sử dụng")
            return {'FINISHED'}
        scene = context.scene
        viewlayer = context.view_layer
        obs = [o for o in scene.objects if o.type == 'MESH']
        bpy.ops.object.select_all(action='DESELECT')

        path = bpy.path.abspath("//")
        for ob in obs:
            viewlayer.objects.active = ob
            ob.select_set(True)
            stl_path = path + f"{ob.name}.stl"
            bpy.ops.export_mesh.stl(
                filepath=str(stl_path),
                use_selection=True)
            ob.select_set(False)
        return {'FINISHED'}
        
class buttonOperator_CreateTubes(bpy.types.Operator):
    """Create Tubes from ConstructionInfo"""
    bl_idname = "object.pnfunction17"
    bl_label = "Import all STL"
    def execute(self, context):
        if not hw_read_key():
            self.report({'ERROR'},"Vui lòng đăng ký key để kích hoạt sử dụng")
            return {'FINISHED'}
        class ConstructionInfoParser:
            def __init__(self, file_path: str):
                self.file_path = file_path
                self.tree = ET.parse(file_path)
                self.root = self.tree.getroot()

            def extract_valid_implants(self) -> List[Dict]:
                valid_implants = []
                
                for tooth in self.root.findall(".//Tooth"):
                    implant_type = tooth.findtext("ImplantType", default="None")
                    matrix_implant_geometry = tooth.find("MatrixImplantGeometry")
                    axis_implant = tooth.find("AxisImplant")

                    if implant_type != "None" and matrix_implant_geometry is not None:
                        tooth_number = tooth.findtext("Number", default="Unknown")
                        matrixG = {child.tag: child.text for child in matrix_implant_geometry}
                        axisImplant = {childAxis.tag: childAxis.text for childAxis in axis_implant}
                        
                        m00 = float(matrixG['_00'])
                        m01 = float(matrixG['_10'])
                        m02 = float(matrixG['_20'])
                        m03 = float(matrixG['_30'])
                        m10 = float(matrixG['_01'])
                        m11 = float(matrixG['_11'])
                        m12 = float(matrixG['_21'])
                        m13 = float(matrixG['_31'])
                        m20 = float(matrixG['_02'])
                        m21 = float(matrixG['_12'])
                        m22 = float(matrixG['_22'])
                        m23 = float(matrixG['_32'])
                        m30 = float(matrixG['_03'])
                        m31 = float(matrixG['_13'])
                        m32 = float(matrixG['_23'])
                        m33 = float(matrixG['_33'])
                        MatrixForUse =  mathutils.Matrix(((m00,m01,m02,m03),(m10,m11,m12,m13),(m20,m21,m22,m23),(m30,m31,m32,m33)))
                        
                        axisImplantX = float(axisImplant['x'])
                        axisImplantY = float(axisImplant['y'])
                        axisImplantZ = float(axisImplant['z'])
                        
                        deltaX1 = abs(m00 - axisImplantX) < 0.0001 
                        deltaX2 = abs(m10 - axisImplantY) < 0.0001 
                        deltaX3 = abs(m20 - axisImplantZ) < 0.0001 
                        deltaY1 = abs(m01 - axisImplantX) < 0.0001 
                        deltaY2 = abs(m11 - axisImplantY) < 0.0001 
                        deltaY3 = abs(m21 - axisImplantZ) < 0.0001 
                        deltaZ1 = abs(m02 - axisImplantX) < 0.0001 
                        deltaZ2 = abs(m12 - axisImplantY) < 0.0001 
                        deltaZ3 = abs(m22 - axisImplantZ) < 0.0001
                        
                        ndeltaX1 = abs(m00 + axisImplantX) < 0.0001 
                        ndeltaX2 = abs(m10 + axisImplantY) < 0.0001 
                        ndeltaX3 = abs(m20 + axisImplantZ) < 0.0001 
                        ndeltaY1 = abs(m01 + axisImplantX) < 0.0001 
                        ndeltaY2 = abs(m11 + axisImplantY) < 0.0001 
                        ndeltaY3 = abs(m21 + axisImplantZ) < 0.0001 
                        ndeltaZ1 = abs(m02 + axisImplantX) < 0.0001 
                        ndeltaZ2 = abs(m12 + axisImplantY) < 0.0001 
                        ndeltaZ3 = abs(m22 + axisImplantZ) < 0.0001
                        
                        axisZ = deltaZ1 and deltaZ2 and deltaZ3
                        axisY = deltaY1 and deltaY2 and deltaY3
                        axisX = deltaX1 and deltaX2 and deltaX3
                        axisnZ = ndeltaZ1 and ndeltaZ2 and ndeltaZ3
                        axisnY = ndeltaY1 and ndeltaY2 and ndeltaY3
                        axisnX = ndeltaX1 and ndeltaX2 and ndeltaX3
                        
                        if axisZ:
                            rotateXaxis = 0.0
                            rotateYaxis = 0.0
                        elif axisnZ:
                            rotateYaxis = math.pi
                            rotateXaxis = 0.0
                        elif axisY:
                            rotateXaxis = math.pi/2
                            rotateYaxis = 0.0
                        elif axisnY:
                            rotateXaxis = - math.pi/2
                            rotateYaxis = 0.0
                        elif axisX:
                            rotateYaxis = - math.pi/2
                            rotateXaxis = 0.0
                        elif axisnX:
                            rotateYaxis = math.pi/2
                            rotateXaxis = 0.0
                        else:
                            rotateXaxis = 0.0
                            rotateYaxis = 0.0

                        valid_implants.append({
                            "Number": tooth_number,
                            "MatrixImplantGeometry": MatrixForUse,
                            "RotateX": rotateXaxis,
                            "RotateY": rotateYaxis,
                        })
                return valid_implants
        
        class ImplantDirectionPositionParser:
            def __init__(self, file_path: str):
                self.file_path = file_path
                self.tree = ET.parse(file_path)
                self.root = self.tree.getroot()

            def extract_valid_implants(self) -> List[Dict]:
                valid_implants = []
                
                for tooth in self.root.findall("ToothIndex"):
                    tooth_number = tooth.get("unn")  # ToothNumber từ attribute unn
                    axis_implant = tooth.find("Direction")
                    matrix_implant_geometry = tooth.find("TransformMatrix")
                    
                    if axis_implant is None: continue
                    if matrix_implant_geometry is None: continue
                    
                    axisImplantX = float(axis_implant.get("x"))
                    axisImplantY = float(axis_implant.get("y"))
                    axisImplantZ = float(axis_implant.get("z"))

                    
                    m00 = float(matrix_implant_geometry.get('m00'))
                    m01 = float(matrix_implant_geometry.get('m01'))
                    m02 = float(matrix_implant_geometry.get('m02'))
                    m03 = float(matrix_implant_geometry.get('m03'))
                    m10 = float(matrix_implant_geometry.get('m10'))
                    m11 = float(matrix_implant_geometry.get('m11'))
                    m12 = float(matrix_implant_geometry.get('m12'))
                    m13 = float(matrix_implant_geometry.get('m13'))
                    m20 = float(matrix_implant_geometry.get('m20'))
                    m21 = float(matrix_implant_geometry.get('m21'))
                    m22 = float(matrix_implant_geometry.get('m22'))
                    m23 = float(matrix_implant_geometry.get('m23'))
                    m30 = float(matrix_implant_geometry.get('m30'))
                    m31 = float(matrix_implant_geometry.get('m31'))
                    m32 = float(matrix_implant_geometry.get('m32'))
                    m33 = float(matrix_implant_geometry.get('m33'))
                    MatrixForUse =  mathutils.Matrix(((m00,m01,m02,m03),(m10,m11,m12,m13),(m20,m21,m22,m23),(m30,m31,m32,m33)))
                    
                    deltaX1 = abs(m00 - axisImplantX) < 0.0001 
                    deltaX2 = abs(m10 - axisImplantY) < 0.0001 
                    deltaX3 = abs(m20 - axisImplantZ) < 0.0001 
                    deltaY1 = abs(m01 - axisImplantX) < 0.0001 
                    deltaY2 = abs(m11 - axisImplantY) < 0.0001 
                    deltaY3 = abs(m21 - axisImplantZ) < 0.0001 
                    deltaZ1 = abs(m02 - axisImplantX) < 0.0001 
                    deltaZ2 = abs(m12 - axisImplantY) < 0.0001 
                    deltaZ3 = abs(m22 - axisImplantZ) < 0.0001
                    
                    ndeltaX1 = abs(m00 + axisImplantX) < 0.0001 
                    ndeltaX2 = abs(m10 + axisImplantY) < 0.0001 
                    ndeltaX3 = abs(m20 + axisImplantZ) < 0.0001 
                    ndeltaY1 = abs(m01 + axisImplantX) < 0.0001 
                    ndeltaY2 = abs(m11 + axisImplantY) < 0.0001 
                    ndeltaY3 = abs(m21 + axisImplantZ) < 0.0001 
                    ndeltaZ1 = abs(m02 + axisImplantX) < 0.0001 
                    ndeltaZ2 = abs(m12 + axisImplantY) < 0.0001 
                    ndeltaZ3 = abs(m22 + axisImplantZ) < 0.0001
                    
                    axisZ = deltaZ1 and deltaZ2 and deltaZ3
                    axisY = deltaY1 and deltaY2 and deltaY3
                    axisX = deltaX1 and deltaX2 and deltaX3
                    axisnZ = ndeltaZ1 and ndeltaZ2 and ndeltaZ3
                    axisnY = ndeltaY1 and ndeltaY2 and ndeltaY3
                    axisnX = ndeltaX1 and ndeltaX2 and ndeltaX3
                    
                    if axisZ:
                        rotateXaxis = 0.0
                        rotateYaxis = 0.0
                    elif axisnZ:
                        rotateYaxis = math.pi
                        rotateXaxis = 0.0
                    elif axisY:
                        rotateXaxis = math.pi/2
                        rotateYaxis = 0.0
                    elif axisnY:
                        rotateXaxis = - math.pi/2
                        rotateYaxis = 0.0
                    elif axisX:
                        rotateYaxis = - math.pi/2
                        rotateXaxis = 0.0
                    elif axisnX:
                        rotateYaxis = math.pi/2
                        rotateXaxis = 0.0
                    else:
                        rotateXaxis = 0.0
                        rotateYaxis = 0.0
                    
                    valid_implants.append({
                        "Number": tooth.findtext("Number", default="Unknown"),
                        "MatrixImplantGeometry": MatrixForUse,
                        "RotateX": rotateXaxis,
                        "RotateY": rotateYaxis,
                    })
                return valid_implants

        collection_tubes_name = "Tubes"
        collection_tubes = bpy.data.collections.get(collection_tubes_name)
        if collection_tubes:
            collection_tubes.hide_viewport = False
        path = bpy.path.abspath("//")
        if path == '':
           self.report({'ERROR'},"Vui lòng lưu project vào thư mục chứa stl đã chuẩn bị. Có thể sử dụng tổ hợp phím Ctrl-Shift-S sau đó chọn vị trí lưu")
        dir_list = os.listdir(path)
        fullFileName = ''
        for item in dir_list:
            if item.endswith('.constructionInfo'):      
                fullFileName = path + "//" + item
                parser = ConstructionInfoParser(fullFileName)
                valid_implants = parser.extract_valid_implants()
            elif item.startswith('ImplantDirectionPosition') and item.endswith('.xml'):             
                fullFileName = path + "//" + item
                parser = ImplantDirectionPositionParser(fullFileName)
                valid_implants = parser.extract_valid_implants()
            else:
                continue
            
            for i in range(len(valid_implants)):

                tubesMatrix = valid_implants[i]['MatrixImplantGeometry']

                curve_data = bpy.data.curves.new(name="MyCurve", type='CURVE')
                curve_data.dimensions = '3D'

                # Create a new spline in the curve
                spline = curve_data.splines.new(type='POLY')
                spline.points.add(count=2)

                # Set the coordinates of the points
                spline.points[0].co = (0, 0, -8, 1)
                spline.points[1].co = (0, 0, 4.5, 1)
                spline.points[2].co = (0, 0, 25, 1)

                # Create a new object with the curve
                curve_object = bpy.data.objects.new("Tubes", curve_data)

                # Create or get the "Tubes" collection
                if "Tubes" in bpy.data.collections:
                    tubes_collection = bpy.data.collections["Tubes"]
                else:
                    tubes_collection = bpy.data.collections.new("Tubes")
                    bpy.context.scene.collection.children.link(tubes_collection)

                # Link the object to the "Tubes" collection
                tubes_collection.objects.link(curve_object)

                # Set the curve object as active and select it
                bpy.context.view_layer.objects.active = curve_object
                curve_object.select_set(True)

                # Convert the curve to a mesh
                bpy.ops.object.convert(target='MESH')

                # Create vertex groups
                vertex_groups = ["End", "Middle", "Start"]
                vertex_indices = [0, 1, 2]  # Indices of the vertices

                for group_name, idx in zip(vertex_groups, vertex_indices):
                    vertex_group = curve_object.vertex_groups.new(name=group_name)
                    vertex_group.add([idx], 1.0, 'ADD')

                # Optionally, select the vertices in each vertex group (for demonstration purposes)
                bpy.ops.object.mode_set(mode='EDIT')
                bpy.ops.mesh.select_all(action='DESELECT')
                for group_name in vertex_groups:
                    curve_object.vertex_groups.active = curve_object.vertex_groups[group_name]
                    bpy.ops.object.vertex_group_select()
                bpy.ops.object.mode_set(mode='OBJECT')
                object = bpy.context.active_object
                object.matrix_world = tubesMatrix
                object.rotation_euler.x -= valid_implants[i]["RotateX"]
                object.rotation_euler.y -= valid_implants[i]["RotateY"]
            break
            
        if (fullFileName == ''):
            self.report({'ERROR'},"Không tìm thấy file chứa vị trí implant, vui lòng chép file vào thư mục làm việc")
            return {'FINISHED'}

        # Transform Tubes to current design
        scene = context.scene
        viewlayer = context.view_layer
        obs = [o for o in scene.objects if o.type == 'MESH']

        path = bpy.path.abspath("//")
        file_pathORG = path + "before.txt"
        fileORG = open(file_pathORG, "r")
        linesORG = fileORG.readlines()
        matrixObjectORG = bpy.context.scene.cursor.matrix
        matrixValuesORG1 = linesORG[0].split(",")
        matrixValuesORG2 = linesORG[1].split(",")
        matrixValuesORG3 = linesORG[2].split(",")
        matrixValuesORG4 = linesORG[3].split(",")
        matrixObjectORG[0] = [float(val) for val in matrixValuesORG1]
        matrixObjectORG[1] = [float(val) for val in matrixValuesORG2]
        matrixObjectORG[2] = [float(val) for val in matrixValuesORG3]
        matrixObjectORG[3] = [float(val) for val in matrixValuesORG4]

        bpy.ops.object.select_all(action='DESELECT')

        bpy.ops.object.empty_add(type='ARROWS', radius=10, align='WORLD', location=(0, 0, 0), scale=(1, 1, 1))
        object = bpy.context.active_object
        object.matrix_world = matrixObjectORG
        object.name = "currentAxis"
        objectArrows = bpy.data.objects['currentAxis']
        for ob in obs:
            viewlayer.objects.active = ob
            if ob.name.find('Tubes')>-1:
                ob.select_set(True)
        bpy.context.view_layer.objects.active = objectArrows
        bpy.ops.object.parent_set(type='OBJECT')

        file_path = path + "transform.txt"
        file = open(file_path, "r")
        lines = file.readlines()
        matrixObjectTransform = bpy.context.scene.cursor.matrix
        matrixValues1 = lines[0].split(",")
        matrixValues2 = lines[1].split(",")
        matrixValues3 = lines[2].split(",")
        matrixValues4 = lines[3].split(",")
        matrixObjectTransform[0] = [float(val) for val in matrixValues1]
        matrixObjectTransform[1] = [float(val) for val in matrixValues2]
        matrixObjectTransform[2] = [float(val) for val in matrixValues3]
        matrixObjectTransform[3] = [float(val) for val in matrixValues4]

        object2 = bpy.context.active_object
        object2.matrix_world = matrixObjectTransform

        objectArrows.select_set(True)
        for ob in obs:
            viewlayer.objects.active = ob
            if ob.name.find('Tubes')>-1:
                ob.select_set(True)
        bpy.ops.object.parent_clear(type='CLEAR_KEEP_TRANSFORM')
        bpy.data.objects.remove(objectArrows)
        
        bpy.ops.object.select_all(action='DESELECT')
        for ob in obs:
            if ob.name.find('Tubes') > -1:
                viewlayer.objects.active = ob
                ob.select_set(True)
                bpy.ops.object.modifier_add(type='SKIN')
                bpy.ops.object.modifier_add(type='SUBSURF')
                bpy.context.object.modifiers["Subdivision"].levels = 3
                matg = bpy.data.materials.new("Green")
                matg.diffuse_color = (0, 1, 0, 0.2)
                ob.active_material = matg
                bpy.ops.object.mode_set(mode='EDIT')
                bpy.ops.mesh.select_all(action='SELECT')
                bpy.ops.transform.skin_resize(value=(7.1, 7.1, 7.1), orient_type='LOCAL', orient_matrix=((1, 0, 0), (0, 1, 0), (0, 0, 1)), orient_matrix_type='LOCAL', mirror=True, use_proportional_edit=False, proportional_edit_falloff='SMOOTH', proportional_size=1, use_proportional_connected=False, use_proportional_projected=False, snap=False, snap_elements={'FACE'}, use_snap_project=False, snap_target='CENTER', use_snap_self=False, use_snap_edit=False, use_snap_nonedit=False, use_snap_selectable=False)
                bpy.ops.object.mode_set(mode='EDIT')
                bpy.ops.mesh.select_mode(type="VERT")
                bpy.ops.mesh.select_all(action='DESELECT')
                vgroup = bpy.context.object.vertex_groups["End"]
                bpy.ops.object.mode_set(mode='OBJECT')
                for v in bpy.context.object.data.vertices:
                    for g in v.groups:
                        if g.group == vgroup.index:
                            v.select = True
                bpy.ops.object.mode_set(mode='EDIT')
                bpy.ops.transform.skin_resize(value=(2.5, 2.5, 2.5), orient_type='LOCAL', orient_matrix=((1, 0, 0), (0, 1, 0), (0, 0, 1)), orient_matrix_type='LOCAL', mirror=True, use_proportional_edit=False, proportional_edit_falloff='SMOOTH', proportional_size=1, use_proportional_connected=False, use_proportional_projected=False, snap=False, snap_elements={'FACE'}, use_snap_project=False, snap_target='CENTER', use_snap_self=False, use_snap_edit=False, use_snap_nonedit=False, use_snap_selectable=False)
                bpy.ops.object.mode_set(mode='OBJECT')
                ob.select_set(False)
        for ob in obs:
            if ob.name.find('Tubes') > -1:
                ob.select_set(True)
        return {'FINISHED'}
class buttonOperator_SetAntagonist(bpy.types.Operator):
    """Set selected as Antagonist"""
    bl_idname = "object.pnfunction18"
    bl_label = "Antagonist"

    def execute(self, context):
        if not hw_read_key():
            self.report({'ERROR'},"Vui lòng đăng ký key để kích hoạt sử dụng")
            return {'FINISHED'}
        mata = bpy.data.materials.new("AntaColor")
        mata.diffuse_color = (0.7, 0.7, 0.7, 1)
        for obj in bpy.context.selected_objects:
            obj.active_material = mata
            obj.name = "Antagonist"
        return {'FINISHED'}

class buttonOperator_ShowAntagonist(bpy.types.Operator):
    """Show Antagonist"""
    bl_idname = "object.pnfunction19"
    bl_label = "Show Antagonist"

    def execute(self, context):
        if not hw_read_key():
            self.report({'ERROR'},"Vui lòng đăng ký key để kích hoạt sử dụng")
            return {'FINISHED'}
        obj = bpy.data.objects.get("Antagonist")
        if obj is not None:
            obj.hide_set(False)
        return {'FINISHED'}

class buttonOperator_HideAntagonist(bpy.types.Operator):
    """Hide Antagonist"""
    bl_idname = "object.pnfunction20"
    bl_label = "Antagonist"

    def execute(self, context):
        if not hw_read_key():
            self.report({'ERROR'},"Vui lòng đăng ký key để kích hoạt sử dụng")
            return {'FINISHED'}
        obj = bpy.data.objects.get("Antagonist")
        if obj is not None:
            obj.hide_set(True)
        return {'FINISHED'}
class buttonOperator_ShowGingiva(bpy.types.Operator):
    """Show Gingiva"""
    bl_idname = "object.pnfunction21"
    bl_label = "Show Gingiva"
    def execute(self, context):
        if not hw_read_key():
            self.report({'ERROR'},"Vui lòng đăng ký key để kích hoạt sử dụng")
            return {'FINISHED'}
        obj = bpy.data.objects.get("Gingiva")
        if obj is not None:
            obj.hide_set(False)
        return {'FINISHED'}
class buttonOperator_HideGingiva(bpy.types.Operator):
    """Hide Gingiva"""
    bl_idname = "object.pnfunction22"
    bl_label = "Hide Gingiva"
    def execute(self, context):
        if not hw_read_key():
            self.report({'ERROR'},"Vui lòng đăng ký key để kích hoạt sử dụng")
            return {'FINISHED'}
        obj = bpy.data.objects.get("Gingiva")
        if obj is not None:
            obj.hide_set(True)
        return {'FINISHED'}

class buttonOperator_ShowScrew(bpy.types.Operator):
    """Show Screw"""
    bl_idname = "object.pnfunction23"
    bl_label = "Show Antagonist"
    def execute(self, context):
        if not hw_read_key():
            self.report({'ERROR'},"Vui lòng đăng ký key để kích hoạt sử dụng")
            return {'FINISHED'}
        scene = context.scene
        viewlayer = context.view_layer
        obs = [o for o in scene.objects if o.type == 'MESH']
        for ob in obs:
            if ob.name.find('Screw') > -1:
                ob.hide_set(False)
        return {'FINISHED'}

class buttonOperator_HideScrew(bpy.types.Operator):
    """Hide Screw"""
    bl_idname = "object.pnfunction24"
    bl_label = "Antagonist"
    def execute(self, context):
        if not hw_read_key():
            self.report({'ERROR'},"Vui lòng đăng ký key để kích hoạt sử dụng")
            return {'FINISHED'}
        scene = context.scene
        viewlayer = context.view_layer
        obs = [o for o in scene.objects if o.type == 'MESH']
        for ob in obs:
            if ob.name.find('Screw') > -1:
                ob.hide_set(True)
        return {'FINISHED'}
class buttonOperator_Retention(bpy.types.Operator):
    """Hide Screw"""
    bl_idname = "object.pnfunction25"
    bl_label = "Create Retention"
    def execute(self, context):
        if not hw_read_key():
            self.report({'ERROR'},"Vui lòng đăng ký key để kích hoạt sử dụng")
            return {'FINISHED'}
        currentScene = bpy.context.scene
        cursorLocation = currentScene.cursor.location
        bpy.ops.mesh.primitive_cube_add(size = 5, enter_editmode=False, align='WORLD', location=cursorLocation, scale=(1, 2, 1))
        retentionObject = bpy.context.active_object
        retentionObject.name = 'retentionCube'
        retentionObject.rotation_euler.y = math.pi/2
        vertex_indices = range(8)

        vertex_groupTop = retentionObject.vertex_groups.new(name='Top')
        vertex_groupBottom = retentionObject.vertex_groups.new(name='Bottom')
        for idx in vertex_indices:
            if idx < 4:
                vertex_groupTop.add([idx], 1.0, 'ADD')
            else:
                vertex_groupBottom.add([idx], 1.0, 'ADD')
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_mode(type="VERT")
        bpy.ops.mesh.select_all(action='DESELECT')
        bpy.ops.object.mode_set(mode='OBJECT')
        for v in bpy.context.object.data.vertices:
            for g in v.groups:
                if g.group == vertex_groupTop.index:
                    v.select = True
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.transform.resize(value=(1.7, 1, 1), orient_type='GLOBAL', orient_matrix=((1, 0, 0), (0, 1, 0), (0, 0, 1)), orient_matrix_type='GLOBAL', mirror=True, use_proportional_edit=False, proportional_edit_falloff='SMOOTH', proportional_size=1, use_proportional_connected=False, use_proportional_projected=False, snap=False, snap_elements={'FACE'}, use_snap_project=False, snap_target='CENTER', use_snap_self=False, use_snap_edit=False, use_snap_nonedit=False, use_snap_selectable=False)
        bpy.ops.mesh.select_all(action='DESELECT')
        bpy.ops.object.mode_set(mode='OBJECT')
        for v in bpy.context.object.data.vertices:
            for g in v.groups:
                if g.group == vertex_groupBottom.index:
                    v.select = True
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.bevel(offset=1, offset_pct=0, segments=8, affect='EDGES')
        bpy.ops.object.mode_set(mode='OBJECT')
        return {'FINISHED'}
class buttonOperator_ApplyRetention(bpy.types.Operator):
    """Hide Screw"""
    bl_idname = "object.pnfunction26"
    bl_label = "Apply retention on Bar"
    def execute(self, context):
        if not hw_read_key():
            self.report({'ERROR'},"Vui lòng đăng ký key để kích hoạt sử dụng")
            return {'FINISHED'}
        bpy.ops.object.select_all(action='DESELECT')
        objectIbar = bpy.data.objects['iBar']
        objectIbar.select_set(True)
        scene = context.scene
        viewlayer = context.view_layer
        obs = [o for o in scene.objects if o.type == 'MESH']
        for ob in obs:
            if ob.name.find('retentionCube') > -1:
                boolean_modifier = objectIbar.modifiers.new(name="Boolean", type='BOOLEAN')
                boolean_modifier.object = ob
                boolean_modifier.operation = 'DIFFERENCE'
                viewlayer.objects.active = objectIbar
                bpy.ops.object.modifier_apply(modifier="Boolean")
        for ob in obs:
            if ob.name.find('retentionCube') > -1:
                bpy.data.objects.remove(ob)
        return {'FINISHED'}
class buttonOperator_ShowHybrid(bpy.types.Operator):
    """Show Hybrid"""
    bl_idname = "object.pnfunction27"
    bl_label = "Hybrid"
    def execute(self, context):
        obj = bpy.data.objects.get("Hybrid")
        if obj is not None:
            obj.hide_set(False)
        return {'FINISHED'}
class buttonOperator_HideHybrid(bpy.types.Operator):
    """Hide Hybrid"""
    bl_idname = "object.pnfunction28"
    bl_label = "Antagonist"
    def execute(self, context):
        obj = bpy.data.objects.get("Hybrid")
        if obj is not None:
            obj.hide_set(True)
        return {'FINISHED'}
class buttonOperator_ShowBar(bpy.types.Operator):
    """Show Bar"""
    bl_idname = "object.pnfunction29"
    bl_label = "Antagonist"
    def execute(self, context):
        obj = bpy.data.objects.get("iBar")
        if obj is not None:
            obj.hide_set(False)
        return {'FINISHED'}
class buttonOperator_HideBar(bpy.types.Operator):
    """Hide Bar"""
    bl_idname = "object.pnfunction30"
    bl_label = "Antagonist"
    def execute(self, context):
        obj = bpy.data.objects.get("iBar")
        if obj is not None:
            obj.hide_set(True)
        return {'FINISHED'}
class buttonOperator_SetPreop(bpy.types.Operator):
    """Set selected as Antagonist"""
    bl_idname = "object.pnfunction31"
    bl_label = "Preop"
    def execute(self, context):
        if not hw_read_key():
            self.report({'ERROR'},"Vui lòng đăng ký key để kích hoạt sử dụng")
            return {'FINISHED'}
        matg = bpy.data.materials.new("AntaColor")
        matg.diffuse_color = (0, 0.7, 0, 0.5)
        for obj in bpy.context.selected_objects:
            obj.active_material = matg
            obj.name = "Preop"
        return {'FINISHED'}
class buttonOperator_ShowPreop(bpy.types.Operator):
    """Show Bar"""
    bl_idname = "object.pnfunction32"
    bl_label = "Preop"
    def execute(self, context):
        if not hw_read_key():
            self.report({'ERROR'},"Vui lòng đăng ký key để kích hoạt sử dụng")
            return {'FINISHED'}
        obj = bpy.data.objects.get("Preop")
        if obj is not None:
            obj.hide_set(False)
        return {'FINISHED'}
class buttonOperator_HidePreop(bpy.types.Operator):
    """Hide Bar"""
    bl_idname = "object.pnfunction33"
    bl_label = "Preop"
    def execute(self, context):
        if not hw_read_key():
            self.report({'ERROR'},"Vui lòng đăng ký key để kích hoạt sử dụng")
            return {'FINISHED'}
        obj = bpy.data.objects.get("Preop")
        if obj is not None:
            obj.hide_set(True)
        return {'FINISHED'}
class buttonOperator_SelectExtrude(bpy.types.Operator):
    """Select bar body"""
    bl_idname = "object.pnfunction34"
    bl_label = "Select bar body"
    def execute(self, context):
        if not hw_read_key():
            self.report({'ERROR'},"Vui lòng đăng ký key để kích hoạt sử dụng")
            return {'FINISHED'}
        obj = bpy.context.active_object
        bpy.ops.object.mode_set(mode='OBJECT')
        vertex_group_extrude = obj.vertex_groups.get('Extrude')
        for v in bpy.context.object.data.vertices:
            for g in v.groups:
                if g.group == vertex_group_extrude.index:
                    v.select = True
        bpy.ops.object.mode_set(mode='EDIT')
        return {'FINISHED'}
class buttonOperator_SelectFlat(bpy.types.Operator):
    """Select bar body"""
    bl_idname = "object.pnfunction35"
    bl_label = "Select bar flat"
    def execute(self, context):
        if not hw_read_key():
            self.report({'ERROR'},"Vui lòng đăng ký key để kích hoạt sử dụng")
            return {'FINISHED'}
        obj = bpy.context.active_object
        bpy.ops.object.mode_set(mode='OBJECT')
        vertex_group_flat = obj.vertex_groups.get('Flat')
        for v in bpy.context.object.data.vertices:
            for g in v.groups:
                if g.group == vertex_group_flat.index:
                    v.select = True
        bpy.ops.object.mode_set(mode='EDIT')
        return {'FINISHED'}
class buttonOperator_SelectMargin(bpy.types.Operator):
    """Select bar body"""
    bl_idname = "object.pnfunction36"
    bl_label = "Select bar Margin"
    def execute(self, context):
        if not hw_read_key():
            self.report({'ERROR'},"Vui lòng đăng ký key để kích hoạt sử dụng")
            return {'FINISHED'}
        obj = bpy.context.active_object
        bpy.ops.object.mode_set(mode='OBJECT')
        vertex_group_margin = obj.vertex_groups.get('MARGIN')
        for v in bpy.context.object.data.vertices:
            for g in v.groups:
                if g.group == vertex_group_margin.index:
                    v.select = True
        bpy.ops.object.mode_set(mode='EDIT')
        return {'FINISHED'}
class buttonOperator_JoinObject(bpy.types.Operator):
    """Join Selected Object"""
    bl_idname = "object.pnfunction37"
    bl_label = "Select bar Margin"
    def execute(self, context):
        if not hw_read_key():
            self.report({'ERROR'},"Vui lòng đăng ký key để kích hoạt sử dụng")
            return {'FINISHED'}
        bpy.ops.object.join()
        return {'FINISHED'}
class buttonOperator_SeparateObject(bpy.types.Operator):
    """Separate Selected Object"""
    bl_idname = "object.pnfunction38"
    bl_label = "Separate Selected Object"
    def execute(self, context):
        if not hw_read_key():
            self.report({'ERROR'},"Vui lòng đăng ký key để kích hoạt sử dụng")
            return {'FINISHED'}
        bpy.ops.object.editmode_toggle()
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.mesh.separate(type='LOOSE')
        bpy.ops.object.editmode_toggle()
        return {'FINISHED'}

class buttonOperator_SelectTop(bpy.types.Operator):
    """Select bar Top"""
    bl_idname = "object.pnfunction39"
    bl_label = "Select bar Top"
    def execute(self, context):
        if not hw_read_key():
            self.report({'ERROR'},"Vui lòng đăng ký key để kích hoạt sử dụng")
            return {'FINISHED'}
        obj = bpy.context.active_object
        bpy.ops.object.mode_set(mode='OBJECT')
        vertex_group_top = obj.vertex_groups.get('TOP')
        for v in bpy.context.object.data.vertices:
            for g in v.groups:
                if g.group == vertex_group_top.index:
                    v.select = True
        bpy.ops.object.mode_set(mode='EDIT')
        return {'FINISHED'}
        
class buttonOperator_BevelExtrude(bpy.types.Operator):
    """Bevel Extrude Part of Bar"""
    bl_idname = "object.pnfunction40"
    bl_label = "Bevel extrude area"
    def execute(self, context):
        if not hw_read_key():
            self.report({'ERROR'},"Vui lòng đăng ký key để kích hoạt sử dụng")
            return {'FINISHED'}
        obj = bpy.context.active_object
        bpy.ops.object.mode_set(mode='OBJECT')
        vertex_group_extrude = obj.vertex_groups.get('Extrude')
        for v in bpy.context.object.data.vertices:
            for g in v.groups:
                if g.group == vertex_group_extrude.index:
                    v.select = True
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.bevel(offset=0.75, offset_pct=0, segments=3, affect='EDGES')
        return {'FINISHED'}
        
class buttonOperator_ShowFrameThickness(bpy.types.Operator):
    """Show Thickness"""
    bl_idname = "object.pnfunction41"
    bl_label = "Show Thickness"
    def execute(self, context):
        if not hw_read_key():
            self.report({'ERROR'},"Vui lòng đăng ký key để kích hoạt sử dụng")
            return {'FINISHED'}
        scene = bpy.context.scene
        viewlayer = bpy.context.view_layer
        obs = [o for o in scene.objects if o.type == 'MESH']
        for ob in obs:
            if ob.name.startswith("framework_thickness"):
               ob.hide_set(False)
        return {'FINISHED'}

class buttonOperator_HideFrameThickness(bpy.types.Operator):
    """Hide Thickness"""
    bl_idname = "object.pnfunction42"
    bl_label = "Hide Thickness"
    def execute(self, context):
        if not hw_read_key():
            self.report({'ERROR'},"Vui lòng đăng ký key để kích hoạt sử dụng")
            return {'FINISHED'}
        scene = bpy.context.scene
        viewlayer = bpy.context.view_layer
        obs = [o for o in scene.objects if o.type == 'MESH']
        for ob in obs:
            if ob.name.startswith("framework_thickness"):
               ob.hide_set(True)
        return {'FINISHED'}
        
class buttonOperator_ApplyRetentionCutter(bpy.types.Operator):
    """Hide Screw"""
    bl_idname = "object.pnfunction43"
    bl_label = "Apply retention on Cutter"
    def execute(self, context):
        if not hw_read_key():
            self.report({'ERROR'},"Vui lòng đăng ký key để kích hoạt sử dụng")
            return {'FINISHED'}
        bpy.ops.object.select_all(action='DESELECT')
        objectCutter = bpy.data.objects['CUTTER']
        objectCutter.select_set(True)
        scene = context.scene
        viewlayer = context.view_layer
        obs = [o for o in scene.objects if o.type == 'MESH']
        for ob in obs:
            if ob.name.find('retentionCube') > -1:
                boolean_modifier = objectCutter.modifiers.new(name="Boolean", type='BOOLEAN')
                boolean_modifier.object = ob
                boolean_modifier.operation = 'DIFFERENCE'
                viewlayer.objects.active = objectCutter
                bpy.ops.object.modifier_apply(modifier="Boolean")
        for ob in obs:
            if ob.name.find('retentionCube') > -1:
                bpy.data.objects.remove(ob)
        return {'FINISHED'}
        
class ImportFileSTLOperator(bpy.types.Operator, ImportHelper):
    bl_idname = "wm.open_file_dialog_1"
    bl_label = "Import STL"
    filename_ext = ".stl"
    filter_glob: StringProperty(
        default="*.stl",
        options={'HIDDEN'},
        maxlen=255,
    )
    files: CollectionProperty(
        type=bpy.types.OperatorFileListElement,
        options={'HIDDEN', 'SKIP_SAVE'},
    )
    directory: StringProperty(
        subtype='DIR_PATH',
    )
    def execute(self, context):
        if not hw_read_key():
            self.report({'ERROR'},"Vui lòng đăng ký key để kích hoạt sử dụng")
            return {'FINISHED'}
        for current_file in self.files:
            fileDIR = os.path.join(self.directory, current_file.name)
            bpy.ops.wm.stl_import(filepath=fileDIR)
        return {'FINISHED'}

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

    # Keep the displayed hardware ID compact while still being deterministic.
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
    hashed_text = create_hash(hardware_id*2)
    legacy_hardware_id = str(uuid.getnode())
    legacy_hashed_text = create_hash(legacy_hardware_id*2)
    user_folder = os.path.expanduser("~")

    license_path = os.path.join(user_folder, "addon_ibar.key")
    if not os.path.exists(license_path):
        hardware_id_filepart = os.path.join(user_folder, "Desktop", "IbarPrep.hwid")
        if not os.path.exists(hardware_id_filepart):
            with open(hardware_id_filepart, "w", encoding="utf-8") as file_write:
                file_write.write(hardware_id)
        print('No License Found')
        return False

    with open(license_path, "r", encoding="utf-8") as hardware_id_input:
        lines = hardware_id_input.readlines()
    if lines and lines[0].strip() in {hashed_text, legacy_hashed_text}:
        return True
    print('Wrong license key')
    return False

class ConstructionFileItem(bpy.types.PropertyGroup):
    part_name: bpy.props.StringProperty(name="PartName", default="")
    filename: bpy.props.StringProperty(name="Filename", default="")

class buttonOperator_LoadConstructionInfo(bpy.types.Operator):
    """Load ConstructionInfo and list parts"""
    bl_idname = "object.pnfunction_load_ci"
    bl_label = "Load ConstructionInfo"

    def execute(self, context):
        if not hw_read_key():
            self.report({'ERROR'}, "Vui lòng đăng ký key để kích hoạt sử dụng")
            return {'FINISHED'}
        path = bpy.path.abspath("//")
        if path == '':
            self.report({'ERROR'}, "Vui lòng lưu project trước khi bắt đầu")
            return {'FINISHED'}
        ci_file = None
        for fn in os.listdir(path):
            if fn.endswith('.constructionInfo'):
                ci_file = os.path.join(path, fn)
                break
        if ci_file is None:
            self.report({'ERROR'}, "Không tìm thấy file .constructionInfo trong thư mục làm việc")
            return {'FINISHED'}
        try:
            tree = ET.parse(ci_file)
            root = tree.getroot()
        except Exception as e:
            self.report({'ERROR'}, f"Không thể đọc file constructionInfo: {e}")
            return {'FINISHED'}
        context.scene.construction_files.clear()
        for cf in root.findall(".//ConstructionFileList/ConstructionFile"):
            filename = cf.findtext("Filename", default="")
            part_name = cf.findtext("PartName", default="")
            item = context.scene.construction_files.add()
            item.part_name = part_name
            item.filename = filename
        count = len(context.scene.construction_files)
        if count == 0:
            self.report({'WARNING'}, "Không tìm thấy ConstructionFile trong file")
        else:
            self.report({'INFO'}, f"Đã tải {count} phần từ constructionInfo")
        return {'FINISHED'}

def _read_patient_info(path):
    """Đọc PatientName và PatientFirstName từ file .dentalProject trong thư mục path."""
    for fn in os.listdir(path):
        if fn.endswith('.dentalProject'):
            try:
                tree = ET.parse(os.path.join(path, fn))
                root = tree.getroot()
                patient_name = root.findtext(".//Patient/PatientName") or ""
                patient_first_name = root.findtext(".//Patient/PatientFirstName") or ""
                return patient_name.strip(), patient_first_name.strip()
            except Exception:
                pass
    return "", ""

class buttonOperator_SaveSTLByPart(bpy.types.Operator):
    """Save STL for a specific construction part with ORG transform and rename"""
    bl_idname = "object.pnfunction_save_stl_part"
    bl_label = "Save STL by Part"

    part_name: bpy.props.StringProperty(name="PartName", default="")
    filename: bpy.props.StringProperty(name="Filename", default="")

    def execute(self, context):
        if not hw_read_key():
            self.report({'ERROR'}, "Vui lòng đăng ký key để kích hoạt sử dụng")
            return {'FINISHED'}
        scene = context.scene
        viewlayer = context.view_layer
        obs = [o for o in scene.objects if o.type == 'MESH']
        path = bpy.path.abspath("//")
        if path == '':
            self.report({'ERROR'}, "Vui lòng lưu project trước khi bắt đầu")
            return {'FINISHED'}

        # === Phần 1: Transform về ORG (giống SaveSTLORG đến trước dòng xuất STL) ===
        file_path = path + "transform.txt"
        try:
            with open(file_path, "r") as tf:
                lines = tf.readlines()
        except Exception as e:
            self.report({'ERROR'}, f"Không thể đọc transform.txt: {e}")
            return {'FINISHED'}
        matrixObjectTransform = bpy.context.scene.cursor.matrix
        matrixValues1 = lines[0].split(",")
        matrixValues2 = lines[1].split(",")
        matrixValues3 = lines[2].split(",")
        matrixValues4 = lines[3].split(",")
        matrixObjectTransform[0] = [float(val) for val in matrixValues1]
        matrixObjectTransform[1] = [float(val) for val in matrixValues2]
        matrixObjectTransform[2] = [float(val) for val in matrixValues3]
        matrixObjectTransform[3] = [float(val) for val in matrixValues4]
        bpy.ops.object.select_all(action='DESELECT')
        bpy.ops.object.empty_add(type='ARROWS', radius=10, align='WORLD', location=(0, 0, 0), scale=(1, 1, 1))
        object = bpy.context.active_object
        object.matrix_world = matrixObjectTransform
        for obj in bpy.context.selected_objects:
            obj.name = "fileORG"
        for ob in obs:
            if ob.name == "Closed_Bar":
                ob.select_set(True)
            if ob.name == "Hybrid_Shell":
                ob.select_set(True)
            if ob.name == "iBar":
                ob.select_set(True)
        bpy.ops.object.parent_set(type='OBJECT')
        file_pathORG = path + "before.txt"
        try:
            with open(file_pathORG, "r") as of:
                linesORG = of.readlines()
        except Exception as e:
            self.report({'ERROR'}, f"Không thể đọc before.txt: {e}")
            return {'FINISHED'}
        matrixObjectORG = bpy.context.scene.cursor.matrix
        matrixValuesORG1 = linesORG[0].split(",")
        matrixValuesORG2 = linesORG[1].split(",")
        matrixValuesORG3 = linesORG[2].split(",")
        matrixValuesORG4 = linesORG[3].split(",")
        matrixObjectORG[0] = [float(val) for val in matrixValuesORG1]
        matrixObjectORG[1] = [float(val) for val in matrixValuesORG2]
        matrixObjectORG[2] = [float(val) for val in matrixValuesORG3]
        matrixObjectORG[3] = [float(val) for val in matrixValuesORG4]
        object2 = bpy.context.active_object
        object2.matrix_world = matrixObjectORG
        bpy.ops.object.select_all(action='DESELECT')
        # === Kết thúc phần 1 ===

        # === Phần 2: Lấy tham chiếu object rồi đổi tên thêm PartName và PatientName ===
        patient_name, patient_first_name = _read_patient_info(path)
        patient_suffix = ""
        if patient_first_name:
            patient_suffix += "_" + patient_first_name
        part_suffix = "_" + self.part_name + patient_suffix

        def _make_name(prefix, suffix, max_len=63):
            full = prefix + suffix
            return full[:max_len] if len(full) > max_len else full

        hybrid_obj = bpy.data.objects.get("Hybrid_Shell")
        ibar_obj = bpy.data.objects.get("iBar")
        closedbar_obj = bpy.data.objects.get("Closed_Bar")
        ibar_new_name = _make_name("iBar", part_suffix)
        if hybrid_obj:
            hybrid_obj.name = _make_name("Hybrid_Shell", part_suffix)
        if ibar_obj:
            ibar_obj.name = ibar_new_name
        if closedbar_obj:
            closedbar_obj.name = _make_name("Closed_Bar", part_suffix)

        # === Phần 3: Đổi tên tất cả file khớp Filename trong thư mục làm việc ===
        old_filename = self.filename
        if old_filename:
            old_ext = os.path.splitext(old_filename)[1]
            new_file_name = ibar_new_name + old_ext
            for fn in os.listdir(path):
                if fn == old_filename:
                    try:
                        os.rename(os.path.join(path, fn), os.path.join(path, new_file_name))
                    except Exception as e:
                        self.report({'WARNING'}, f"Không thể đổi tên file {fn}: {e}")

        # === Phần 4: Tạo constructionInfo mới với Filename đã được cập nhật ===
        ci_source = None
        for fn in os.listdir(path):
            if fn.endswith('.constructionInfo'):
                ci_source = os.path.join(path, fn)
                break
        if ci_source and old_filename:
            try:
                with open(ci_source, 'r', encoding='utf-8') as f:
                    ci_content = f.read()
                old_fn_tag = re.escape(f"<Filename>{old_filename}</Filename>")
                new_fn_tag = f"<Filename>{ibar_new_name}.stl</Filename>"
                new_ci_content = re.sub(old_fn_tag, new_fn_tag, ci_content, count=1)
                new_ci_path = os.path.join(path, ibar_new_name + ".constructionInfo")
                with open(new_ci_path, 'w', encoding='utf-8') as f:
                    f.write(new_ci_content)
            except Exception as e:
                self.report({'WARNING'}, f"Không thể tạo constructionInfo mới: {e}")

        # === Phần 5: Xuất STL cho các object đã đổi tên (giống dòng 284-302 SaveSTLORG) ===
        objects_to_save = [o for o in [hybrid_obj, ibar_obj, closedbar_obj] if o is not None]
        for ob in objects_to_save:
            viewlayer.objects.active = ob
            ob.select_set(True)
            stl_path = path + f"{ob.name}.stl"
            bpy.ops.export_mesh.stl(
                filepath=str(stl_path),
                use_selection=True)
            ob.select_set(False)

        # === Phần 6: Clear parent và xóa fileORG ===
        bpy.ops.object.select_all(action='DESELECT')
        objectArrows = bpy.data.objects.get('fileORG')
        if objectArrows:
            objectArrows.select_set(True)
            for ob in objects_to_save:
                ob.select_set(True)
            bpy.ops.object.parent_clear(type='CLEAR_KEEP_TRANSFORM')
            bpy.data.objects.remove(objectArrows)

        self.report({'INFO'}, f"Đã lưu STL cho phần: {self.part_name}")
        return {'FINISHED'}

class IbarPrepPanel(bpy.types.Panel):
    bl_label = "IBar Function Prepare"
    bl_idname = "OBJECT_PT_Ibar_Transform"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "IBAR Prep"

    def draw(self, context):
        layout = self.layout
        row0 = layout.row(align=True)
        row0.operator(IBAR_OT_CheckAddonUpdate.bl_idname, text = "Check Update", icon = 'URL')
        row0.operator(IBAR_OT_UpdateAddonFromGitHub.bl_idname, text = "Update", icon = 'FILE_REFRESH')
        row1 = layout.row()
        row1.operator(ImportFileSTLOperator.bl_idname, text = "Select STLs", icon = 'FILE_FOLDER')
        row2 = layout.row()
        row2.operator(buttonOperator_ImportAllSTL.bl_idname, text = "Import all STL", icon = 'FILE_3D')
        row3 = layout.row()
        row3.operator(buttonOperator_JoinObject.bl_idname, text = "Join", icon = 'LINKED')
        row3.operator(buttonOperator_SeparateObject.bl_idname, text = "Separate", icon = 'UNLINKED')
        row4 = layout.row()
        row4.operator(buttonOperator_SetORG.bl_idname, text = "Set Object ORG", icon = 'PIVOT_CURSOR')

class OcclusalAlignment(bpy.types.Panel):
    bl_label = "Occlusal Alignment"
    bl_idname = "OBJECT_PT_OcclusalAlign"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "IBAR Prep"
    
    def draw(self, context):
        layout = self.layout
        row1 = layout.row()
        row1.operator(buttonAddRedPoint1.bl_idname, text = "Molar Q1-3 Point (Red)", icon = 'NODE_SOCKET_MATERIAL')
        row2 = layout.row()
        row2.operator(buttonAddRedPoint2.bl_idname, text = "Central Incisor Point (Green)", icon = 'NODE_SOCKET_SHADER')
        row3 = layout.row()
        row3.operator(buttonAddRedPoint3.bl_idname, text = "Molar Q2-4 Point (Blue)", icon = 'NODE_SOCKET_STRING')
        row4 = layout.row()
        row4.operator(buttonOperator_TransformToPlane.bl_idname, text = "Ailgn to OcclusalPlane", icon = 'TRANSFORM_ORIGINS')
        row5 = layout.row()
        row5.operator(buttonOperator_GetTransformORG.bl_idname, text = "Save Transform Info", icon = 'PINNED')
        row6 = layout.row()
        row6.operator(buttonOperator_TransformToCurrentDesign.bl_idname, text = "Offset Transform Object", icon = 'GIZMO')

class IbarAddCustomPanel(bpy.types.Panel):
    bl_label = "IBar Custom Function"
    bl_idname = "OBJECT_PT_Ibar_AddCustom"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "IBAR Prep"

    def draw(self, context):
        layout = self.layout
        row1 = layout.row()
        row1.operator(buttonSnapToScrews.bl_idname, text = "Cursor to Object", icon = 'PIVOT_CURSOR')
        row2 = layout.row()
        row2.operator(buttonDeleteOther.bl_idname, text = "Clean other mesh", icon = 'TRASH')
        row3 = layout.row()
        row3.operator(buttonOperator_CreateTubes.bl_idname, text = "Create Tubes Automatically", icon = 'ORIENTATION_LOCAL')
        row4 = layout.row()
        row4.operator(buttonFramework_Thickness.bl_idname, text = "Create Framework thickness", icon = 'MOD_THICKNESS')

class IbarMeshControlPanel(bpy.types.Panel):
    bl_label = "Object Control"
    bl_idname = "OBJECT_PT_Ibar_MeshControl"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "IBAR Prep"

    def draw(self, context):
        layout = self.layout
        row1 = layout.row()
        row1.operator(buttonSetAsGingiva.bl_idname, text = "Set", icon = 'STRIP_COLOR_01')
        row1.label(text="Gingiva")
        row1.operator(buttonOperator_ShowGingiva.bl_idname, text = "Show")
        row1.operator(buttonOperator_HideGingiva.bl_idname, text = "Hide")
        row2 = layout.row()
        row2.operator(buttonOperator_SetAntagonist.bl_idname, text = "Set", icon = 'STRIP_COLOR_02')
        row2.label(text="Antagonist")
        row2.operator(buttonOperator_ShowAntagonist.bl_idname, text = "Show")
        row2.operator(buttonOperator_HideAntagonist.bl_idname, text = "Hide")
        row3 = layout.row()
        row3.operator(buttonSetAsScrews.bl_idname, text = "Set", icon = 'STRIP_COLOR_09')
        row3.label(text="Screws")
        row3.operator(buttonOperator_ShowScrew.bl_idname, text = "Show")
        row3.operator(buttonOperator_HideScrew.bl_idname, text = "Hide")
        row4 = layout.row()
        row4.operator(buttonOperator_SetPreop.bl_idname, text = "Set", icon = 'STRIP_COLOR_04')
        row4.label(text="Preop")
        row4.operator(buttonOperator_ShowPreop.bl_idname, text = "Show")
        row4.operator(buttonOperator_HidePreop.bl_idname, text = "Hide")
        row5 = layout.row()
        row5.label(text="Hybrid")
        row5.operator(buttonOperator_ShowHybrid.bl_idname, text = "Show")
        row5.operator(buttonOperator_HideHybrid.bl_idname, text = "Hide")
        row6 = layout.row()
        row6.label(text="Bar")
        row6.operator(buttonOperator_ShowBar.bl_idname, text = "Show")
        row6.operator(buttonOperator_HideBar.bl_idname, text = "Hide")
        row7 = layout.row()
        row7.label(text="Bar Thick")
        row7.operator(buttonOperator_ShowFrameThickness.bl_idname, text = "Show")
        row7.operator(buttonOperator_HideFrameThickness.bl_idname, text = "Hide")
        row8 = layout.row()
        row8.label(text="Select basic bar area")
        row9 = layout.row()
        row9.operator(buttonOperator_SelectTop.bl_idname, text = "Select top")
        row9.operator(buttonOperator_SelectExtrude.bl_idname, text = "Select extrude ")
        row10 = layout.row()
        row10.operator(buttonOperator_SelectFlat.bl_idname, text = "Select flat")
        row10.operator(buttonOperator_SelectMargin.bl_idname, text = "Select margin")
        row11 = layout.row()
        row11.operator(buttonOperator_BevelExtrude.bl_idname, text = "Bevel extrude area", icon = 'MOD_BEVEL')

class IbarRetentionPanel(bpy.types.Panel):
    bl_label = "IBar Retention"
    bl_idname = "OBJECT_PT_Ibar_Retention"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "IBAR Prep"

    def draw(self, context):
        layout = self.layout
        row1 = layout.row()
        row1.operator(buttonOperator_Retention.bl_idname, text = "Add Retention", icon = 'MESH_CUBE')
        row2 = layout.row()
        row2.operator(buttonOperator_ApplyRetentionCutter.bl_idname, text = "Cut on Cutter", icon = 'CHECKBOX_HLT')
        row2.operator(buttonOperator_ApplyRetention.bl_idname, text = "Cut on Bar", icon = 'CHECKBOX_HLT')
        
class SaveSTLIPSPanel(bpy.types.Panel):
    bl_label = "IBar Save STL"
    bl_idname = "OBJECT_PT_SaveSTL"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "IBAR Prep"

    def draw(self, context):
        layout = self.layout
        row1 = layout.row()
        row1.operator(buttonOperator_SaveSTL.bl_idname, text = "STL only", icon = 'DISK_DRIVE')
        row1.operator(buttonOperator_SaveSTLORG.bl_idname, text = "STL to ORG", icon = 'TRANSFORM_ORIGINS')
        row2 = layout.row()
        row2.operator(buttonOperator_SaveAllSTL.bl_idname, text = "Save All STL", icon = 'DISK_DRIVE')
        layout.separator()
        row3 = layout.row()
        row3.operator(buttonOperator_LoadConstructionInfo.bl_idname, text = "Load ConstructionInfo", icon = 'FILE_FOLDER')
        if hasattr(context.scene, 'construction_files'):
            for item in context.scene.construction_files:
                row = layout.row()
                op = row.operator(buttonOperator_SaveSTLByPart.bl_idname, text = item.part_name if item.part_name else "(no name)")
                op.part_name = item.part_name
                op.filename = item.filename

from bpy.utils import register_class, unregister_class

_classes = [
ConstructionFileItem,
buttonOperator_LoadConstructionInfo,
buttonOperator_SaveSTLByPart,
IBAR_OT_CheckAddonUpdate,
IBAR_OT_UpdateAddonFromGitHub,
buttonOperator_SetORG,
buttonFramework_Thickness,
buttonDeleteOther,
buttonSnapToScrews,
buttonSetAsGingiva,
buttonSetAsScrews,
buttonOperator_GetTransformORG,
buttonAddRedPoint1,
buttonAddRedPoint2,
buttonAddRedPoint3,
buttonOperator_TransformToPlane,
buttonOperator_TransformToCurrentDesign,
buttonOperator_SaveSTL,
buttonOperator_SaveSTLORG,
buttonOperator_ImportAllSTL,
buttonOperator_CreateTubes,
buttonOperator_SaveAllSTL,
buttonOperator_SetAntagonist,
buttonOperator_ShowAntagonist,
buttonOperator_HideAntagonist,
buttonOperator_ShowScrew,
buttonOperator_HideScrew,
buttonOperator_ShowGingiva,
buttonOperator_HideGingiva,
buttonOperator_Retention,
buttonOperator_ApplyRetention,
buttonOperator_ShowHybrid,
buttonOperator_HideHybrid,
buttonOperator_ShowBar,
buttonOperator_HideBar,
buttonOperator_SetPreop,
buttonOperator_ShowPreop,
buttonOperator_HidePreop,
buttonOperator_SelectTop,
buttonOperator_SelectExtrude,
buttonOperator_SelectFlat,
buttonOperator_SelectMargin,
buttonOperator_JoinObject,
buttonOperator_SeparateObject,
buttonOperator_BevelExtrude,
buttonOperator_ShowFrameThickness,
buttonOperator_HideFrameThickness,
ImportFileSTLOperator,
buttonOperator_ApplyRetentionCutter,
IbarPrepPanel,
OcclusalAlignment,
IbarAddCustomPanel,
IbarMeshControlPanel,
IbarRetentionPanel,
SaveSTLIPSPanel]

def register():
    for cls in _classes:
        register_class(cls)
    bpy.types.Scene.construction_files = bpy.props.CollectionProperty(type=ConstructionFileItem)

def unregister():
    del bpy.types.Scene.construction_files
    for cls in _classes:
        unregister_class(cls)

if __name__ == "__main__":
    register()