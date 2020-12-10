import math
import random
import re
from pathlib import Path
from typing import Optional, List, Tuple, Any, Dict

import numpy as np
from .bsp_file import BSPFile
from .datatypes.face import Face
from .datatypes.model import Model
from .lump import LumpTypes
from .datatypes.world_light import EmitType, Color32

import bpy

from .lumps.edge_lump import EdgeLump
from .lumps.entity_lump import EntityLump
from .lumps.face_lump import FaceLump
from .lumps.model_lump import ModelLump
from .lumps.string_lump import StringsLump
from .lumps.surf_edge_lump import SurfEdgeLump
from .lumps.texture_lump import TextureInfoLump, TextureDataLump
from .lumps.vertex_lump import VertexLump
from .lumps.world_light_lump import WorldLightLump
from ..new_model_import import get_or_create_collection
from ..vtf.blender_material import BlenderMaterial
from ..vtf.import_vtf import import_texture
from ..vtf.vmt import VMT
from ...utilities import valve_utils
from ...utilities.gameinfo import Gameinfo
from ...utilities.math_utilities import parse_source2_hammer_vector, convert_rotation_source2_to_blender, \
    watt_power_spot, watt_power_point
from ...utilities.path_utilities import NonSourceInstall
from ...utilities.valve_utils import fix_workshop_not_having_gameinfo_file

material_name_fix = re.compile(r"_-?[\d]+_-?[\d]+_-?[\d]+")


def fix_material_name(material_name):
    if material_name:
        if material_name_fix.search(material_name):
            material_name = material_name_fix.sub("", material_name)
            material_name = str(Path(material_name).with_suffix(''))
    return material_name


def get_material(mat_name, model_ob):
    if mat_name:
        mat_name = fix_material_name(mat_name)
    else:
        mat_name = "Material"
    mat_ind = 0
    md = model_ob.data
    mat = None
    for candidate in bpy.data.materials:  # Do we have this material already?
        if candidate.name == mat_name:
            mat = candidate
    if mat:
        if md.materials.get(mat.name):  # Look for it on this mesh_data
            for i in range(len(md.materials)):
                if md.materials[i].name == mat.name:
                    mat_ind = i
                    break
        else:  # material exists, but not on this mesh_data
            md.materials.append(mat)
            mat_ind = len(md.materials) - 1
    else:  # material does not exist
        mat = bpy.data.materials.new(mat_name)
        md.materials.append(mat)
        # Give it a random colour
        rand_col = []
        for i in range(3):
            rand_col.append(random.uniform(.4, 1))
        rand_col.append(1.0)
        mat.diffuse_color = rand_col

        mat_ind = len(md.materials) - 1

    return mat_ind


class BSP:
    scale = 0.0133

    def __init__(self, map_path):
        self.filepath = Path(map_path)
        print('Loading map from', self.filepath)
        self.map_file = BSPFile(self.filepath)
        self.map_file.parse()
        self.main_collection = bpy.data.collections.new(self.filepath.name)
        bpy.context.scene.collection.children.link(self.main_collection)

        self.model_lump: Optional[ModelLump] = self.map_file.lumps.get(LumpTypes.LUMP_MODELS, None)
        self.vertex_lump: Optional[VertexLump] = self.map_file.lumps.get(LumpTypes.LUMP_VERTICES, None)
        self.edge_lump: Optional[EdgeLump] = self.map_file.lumps.get(LumpTypes.LUMP_EDGES, None)
        self.surf_edge_lump: Optional[SurfEdgeLump] = self.map_file.lumps.get(LumpTypes.LUMP_SURFEDGES, None)
        self.face_lump: Optional[FaceLump] = self.map_file.lumps.get(LumpTypes.LUMP_FACES, None)
        self.texture_info_lump: Optional[TextureInfoLump] = self.map_file.lumps.get(LumpTypes.LUMP_TEXINFO, None)
        self.texture_data_lump: Optional[TextureDataLump] = self.map_file.lumps.get(LumpTypes.LUMP_TEXDATA, None)
        if self.vertex_lump:
            self.scaled_vertices = np.multiply(self.vertex_lump.vertices, self.scale)

    @staticmethod
    def gather_vertex_ids(model: Model,
                          faces: List[Face],
                          surf_edges: List[Tuple[int, int]],
                          edges: List[Tuple[int, int]]):
        vertex_ids = []
        for map_face in faces[model.first_face:model.first_face + model.face_count]:
            first_edge = map_face.first_edge
            edge_count = map_face.edge_count
            for surf_edge in surf_edges[first_edge:first_edge + edge_count]:
                reverse = surf_edge >= 0
                edge = edges[abs(surf_edge)]
                vertex_id = edge[0] if reverse else edge[1]
                vertex_ids.append(vertex_id)
        return len(vertex_ids)

    def get_string(self, string_id):
        strings_lump: Optional[StringsLump] = self.map_file.lumps.get(LumpTypes.LUMP_TEXDATA_STRING_TABLE, None)
        return strings_lump.strings[string_id] or "NO_NAME"

    def load_map_mesh(self):

        if self.vertex_lump and self.face_lump and self.model_lump:
            self.load_bmodel(0, 'world_geometry')

    def load_entities(self):
        entity_lump: Optional[EntityLump] = self.map_file.lumps.get(LumpTypes.LUMP_ENTITIES, None)
        if entity_lump:
            for entity in entity_lump.entities:
                class_name = entity.get('classname', None)
                if not class_name:
                    continue
                hammer_id = entity.get('hammerid', 'SOURCE_WTF?')
                target_name = entity.get('targetname', None)
                parent_collection = get_or_create_collection(class_name, self.main_collection)
                if class_name == 'env_sprite':

                    material = entity['model']
                    scale = float(entity.get('scale', '1.0'))
                    location = parse_source2_hammer_vector(entity['origin'])

                    self.create_empty(f'Sprite_{hammer_id}_{target_name or material}',
                                      location,
                                      scale=[scale, scale, scale],
                                      parent_collection=parent_collection,
                                      custom_data=dict(entity))
                elif class_name in ['func_brush', 'func_rotating', 'func_door', 'trigger_multiple',
                                    'func_respawnroomvisualizer']:
                    model_id = int(entity['model'][1:])
                    location = parse_source2_hammer_vector(entity['origin'])
                    mesh_obj = self.load_bmodel(model_id, target_name or hammer_id, parent_collection)

                    mesh_obj.location = np.multiply(location, self.scale)

                elif class_name == 'light_spot':
                    location = np.multiply(parse_source2_hammer_vector(entity['origin']), self.scale)
                    rotation = convert_rotation_source2_to_blender(parse_source2_hammer_vector(entity['angles']))
                    color_hrd = parse_source2_hammer_vector(entity['_lightHDR'])
                    color = parse_source2_hammer_vector(entity['_light'])
                    if color_hrd[0] > 0:
                        color = color_hrd
                    lumens = color[-1]
                    color_max = max(color[:-1])
                    lumens *= color_max / 255 * (1.0 / self.scale)
                    color = np.divide(color[:-1], color_max)
                    inner_cone = float(entity['_inner_cone'])
                    cone = float(entity['_cone'])
                    watts = watt_power_spot(lumens, color, cone)
                    self.load_lights(target_name or hammer_id, location, rotation, 'SPOT', watts, color, cone,
                                     parent_collection)
                elif class_name == 'light':
                    location = np.multiply(parse_source2_hammer_vector(entity['origin']), self.scale)
                    color_hrd = parse_source2_hammer_vector(entity['_lightHDR'])
                    color = parse_source2_hammer_vector(entity['_light'])
                    if color_hrd[0] > 0:
                        color = color_hrd
                    lumens = color[-1]
                    color_max = max(color[:-1])
                    lumens *= color_max / 255 * (1.0 / self.scale)
                    color = np.divide(color[:-1], color_max)
                    watts = watt_power_point(lumens, color)
                    self.load_lights(target_name or hammer_id, location, [0.0, 0.0, 0.0], 'POINT', watts, color, 1,
                                     parent_collection)

    def load_bmodel(self, model_id, model_name, parent_collection=None):
        model = self.model_lump.models[model_id]
        print(f'Loading "{model_name}"')
        mesh_obj = bpy.data.objects.new(f"{self.filepath.stem}_{model_name}",
                                        bpy.data.meshes.new(f"{self.filepath.stem}_{model_name}_MESH"))
        mesh_data = mesh_obj.data
        if parent_collection is not None:
            parent_collection.objects.link(mesh_obj)
        else:
            self.main_collection.objects.link(mesh_obj)
        mesh_obj.location = model.origin

        material_lookup_table = {}
        for texture_info in self.texture_info_lump.texture_info:
            texture_data = self.texture_data_lump.texture_data[texture_info.texture_data_id]
            material_name = self.get_string(texture_data.name_id)
            material_lookup_table[texture_data.name_id] = get_material(material_name, mesh_obj)

        faces = []
        material_indices = []
        vertices = []
        vertex_count = self.gather_vertex_ids(model,
                                              self.face_lump.faces,
                                              self.surf_edge_lump.surf_edges,
                                              self.edge_lump.edges)

        uvs_per_face = []
        for map_face in self.face_lump.faces[model.first_face:model.first_face + model.face_count]:
            uvs = np.zeros((vertex_count, 2), dtype=np.float)
            face = []
            first_edge = map_face.first_edge
            edge_count = map_face.edge_count

            texture_info = self.texture_info_lump.texture_info[map_face.tex_info_id]
            texture_data = self.texture_data_lump.texture_data[texture_info.texture_data_id]
            for surf_edge in self.surf_edge_lump.surf_edges[first_edge:first_edge + edge_count]:
                reverse = surf_edge >= 0
                edge = self.edge_lump.edges[abs(surf_edge)]
                vertex_id = edge[0] if reverse else edge[1]

                vert = tuple(self.scaled_vertices[vertex_id])
                if vert in vertices:
                    new_vert_index = vertices.index(vert)
                    face.append(vertices.index(vert))
                else:
                    new_vert_index = len(vertices)
                    face.append(new_vert_index)
                    vertices.append(vert)

                tv1, tv2 = texture_info.texture_vectors
                uco = np.array(tv1[:3])
                vco = np.array(tv2[:3])
                unscaled_vertex = self.vertex_lump.vertices[vertex_id]
                u = np.dot(np.array(unscaled_vertex), uco) + tv1[3]
                v = np.dot(np.array(unscaled_vertex), vco) + tv2[3]
                uvs[new_vert_index] = [u / texture_data.width, 1 - (v / texture_data.height)]

            material_indices.append(material_lookup_table[texture_data.name_id])
            uvs_per_face.append(uvs)
            faces.append(face)

        mesh_data.from_pydata(vertices, [], faces)
        mesh_data.polygons.foreach_set('material_index', material_indices)

        mesh_data.uv_layers.new()
        uv_data = mesh_data.uv_layers[0].data
        for poly in mesh_data.polygons:
            for loop_index in range(poly.loop_start, poly.loop_start + poly.loop_total):
                uv_data[loop_index].uv = uvs_per_face[poly.index][mesh_data.loops[loop_index].vertex_index]

        return mesh_obj

    def create_empty(self, name: str, location, rotation=None, scale=None, parent_collection=None,
                     custom_data=None):
        if custom_data is None:
            custom_data = {}
        if scale is None:
            scale = [1.0, 1.0, 1.0]
        if rotation is None:
            rotation = [0.0, 0.0, 0.0]
        placeholder = bpy.data.objects.new(name, None)
        placeholder.location = np.multiply(location, self.scale)
        placeholder.rotation_mode = 'XYZ'
        placeholder.rotation_euler = rotation
        placeholder.scale = np.multiply(scale, self.scale)
        placeholder['entity_data'] = custom_data
        if parent_collection is not None:
            parent_collection.objects.link(placeholder)
        else:
            self.main_collection.objects.link(placeholder)

    def load_lights(self, name, location, rotation, light_type, watts, color, core_or_size=0.0, parent_collection=None):
        lamp = bpy.data.objects.new(f'{light_type}_{name}',
                                    bpy.data.lights.new(f'{light_type}_{name}_DATA', light_type))
        lamp.location = location
        lamp_data = lamp.data
        lamp_data.energy = watts
        lamp_data.color = color
        lamp.rotation_euler = rotation
        if light_type == 'SPOT':
            lamp_data.spot_size = math.radians(core_or_size)

        if parent_collection is not None:
            parent_collection.objects.link(lamp)
        else:
            self.main_collection.objects.link(lamp)

    def load_materials(self):
        mod_path = valve_utils.get_mod_path(self.filepath)
        rel_model_path = self.filepath.relative_to(mod_path)
        print('Mod path', mod_path)
        print('Relative map path', rel_model_path)
        mod_path = fix_workshop_not_having_gameinfo_file(mod_path)
        gi_path = mod_path / 'gameinfo.txt'
        if gi_path.exists():
            path_resolver = Gameinfo(gi_path)
        else:
            path_resolver = NonSourceInstall(rel_model_path)

        texture_data_lump: Optional[TextureDataLump] = self.map_file.lumps.get(LumpTypes.LUMP_TEXDATA, None)
        for texture_data in texture_data_lump.texture_data:
            material_name = fix_material_name(self.get_string(texture_data.name_id))
            print(f"Loading {material_name} material")
            try:
                material_path = path_resolver.find_material(material_name, True)

                if material_path and material_path.exists():
                    try:
                        vmt = VMT(material_path)
                        vmt.parse()
                        for name, tex in vmt.textures.items():
                            import_texture(tex)
                        mat = BlenderMaterial(vmt)
                        mat.load_textures()
                        mat.create_material(material_name, True)
                    except Exception as m_ex:
                        print(f'Failed to import material "{material_name}", caused by {m_ex}')
                        import traceback
                        traceback.print_exc()
                else:
                    print(f'Failed to find {material_name} material')
            except Exception as t_ex:
                print(f'Failed to import materials, caused by {t_ex}')
                import traceback
                traceback.print_exc()
