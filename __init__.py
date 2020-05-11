import os
from pathlib import Path

NO_BPY = int(os.environ.get('NO_BPY', '0'))

bl_info = {
    "name": "Source1/Source2 Engine model(.mdl, .vmdl_c)",
    "author": "RED_EYE",
    "version": (3, 7, 5),
    "blender": (2, 80, 0),
    "location": "File > Import-Export > SourceEngine MDL (.mdl, .vmdl_c) ",
    "description": "Addon allows to import Source Engine models",
    "category": "Import-Export"
}

if not NO_BPY:

    import bpy
    from bpy.props import StringProperty, BoolProperty, CollectionProperty, EnumProperty, FloatProperty

    from .source1.mdl import mdl2model, qc_generator
    from .source1.vtf.blender_material import BlenderMaterial
    from .source1.vtf.export_vtf import export_texture
    from .source1.vtf.import_vtf import import_texture
    from .source1.dmx.dmx import Session
    from .source1.bsp.import_bsp import BSP
    from .source1.vtf.vmt import VMT

    from .utilities.path_utilities import backwalk_file_resolver

    from .source2.resouce_types.valve_model import ValveModel
    from .source2.resouce_types.valve_texture import ValveTexture
    from .source2.resouce_types.valve_material import ValveMaterial
    from .source2.resouce_types.valve_world import ValveWorld


    class SourceIOPreferences(bpy.types.AddonPreferences):
        bl_idname = __package__

        sfm_path: StringProperty(default='', name='SFM path')

        def draw(self, context):
            layout = self.layout
            layout.label(text='Enter SFM install path:')
            row = layout.row()
            row.prop(self, 'sfm_path')


    # noinspection PyUnresolvedReferences
    class MDLImporter_OT_operator(bpy.types.Operator):
        """Load Source Engine MDL models"""
        bl_idname = "source_io.mdl"
        bl_label = "Import Source MDL file"
        bl_options = {'UNDO'}

        filepath: StringProperty(subtype="FILE_PATH")
        files: CollectionProperty(name='File paths', type=bpy.types.OperatorFileListElement)

        normal_bones: BoolProperty(name="Normalize bones", default=False, subtype='UNSIGNED')
        new_mode: BoolProperty(name="Use experimental import mode", default=False, subtype='UNSIGNED')

        join_clamped: BoolProperty(name="Join clamped meshes", default=False, subtype='UNSIGNED')

        organize_bodygroups: BoolProperty(name="Organize bodygroups", default=True, subtype='UNSIGNED')

        write_qc: BoolProperty(name="Write QC file", default=True, subtype='UNSIGNED')

        import_textures: BoolProperty(name="Import textures", default=False, subtype='UNSIGNED')

        filter_glob: StringProperty(default="*.mdl", options={'HIDDEN'})

        def execute(self, context):

            if Path(self.filepath).is_file():
                directory = Path(self.filepath).parent.absolute()
            else:
                directory = Path(self.filepath).absolute()
            for file in self.files:
                importer = mdl2model.Source2Blender(str(directory / file.name),
                                                    normal_bones=self.normal_bones,
                                                    join_clamped=self.join_clamped,
                                                    import_textures=self.import_textures,
                                                    context=context
                                                    )
                importer.sort_bodygroups = self.organize_bodygroups
                importer.load(dont_build_mesh=False, experemental=self.new_mode)
                if self.write_qc:
                    qc = qc_generator.QC(importer.model)
                    qc_file = bpy.data.texts.new(
                        '{}.qc'.format(Path(file.name).stem))
                    qc.write_header(qc_file)
                    qc.write_models(qc_file)
                    qc.write_skins(qc_file)
                    qc.write_misc(qc_file)
                    qc.write_sequences(qc_file)
            return {'FINISHED'}

        def invoke(self, context, event):
            wm = context.window_manager
            wm.fileselect_add(self)
            return {'RUNNING_MODAL'}


    # noinspection PyUnresolvedReferences
    class BSPImporter_OT_operator(bpy.types.Operator):
        """Load Source Engine BSP models"""
        bl_idname = "source_io.bsp"
        bl_label = "Import Source BSP file"
        bl_options = {'UNDO'}

        filepath: StringProperty(subtype="FILE_PATH")
        # files: CollectionProperty(name='File paths', type=bpy.types.OperatorFileListElement)

        filter_glob: StringProperty(default="*.bsp", options={'HIDDEN'})

        def execute(self, context):
            model = BSP(self.filepath)
            model.load_map_mesh()
            model.load_lights()
            return {'FINISHED'}

        def invoke(self, context, event):
            wm = context.window_manager
            wm.fileselect_add(self)
            return {'RUNNING_MODAL'}


    # noinspection PyUnresolvedReferences
    class VMDLImporter_OT_operator(bpy.types.Operator):
        """Load Source2 VMDL"""
        bl_idname = "source_io.vmdl"
        bl_label = "Import Source2 VMDL file"
        bl_options = {'UNDO'}

        filepath: StringProperty(subtype="FILE_PATH")
        invert_uv: BoolProperty(name="invert UV?", default=True)
        files: CollectionProperty(name='File paths', type=bpy.types.OperatorFileListElement)

        filter_glob: StringProperty(default="*.vmdl_c", options={'HIDDEN'})

        def execute(self, context):

            if Path(self.filepath).is_file():
                directory = Path(self.filepath).parent.absolute()
            else:
                directory = Path(self.filepath).absolute()
            for n, file in enumerate(self.files):
                print(f"Loading {n}/{len(self.files)}")
                model = ValveModel(str(directory / file.name))
                model.load_mesh(self.invert_uv)
            return {'FINISHED'}

        def invoke(self, context, event):
            wm = context.window_manager
            wm.fileselect_add(self)
            return {'RUNNING_MODAL'}


    # noinspection PyUnresolvedReferences
    class VWRLDImporter_OT_operator(bpy.types.Operator):
        """Load Source2 VWRLD"""
        bl_idname = "source_io.vwrld"
        bl_label = "Import Source2 VWRLD file"
        bl_options = {'UNDO'}

        filepath: StringProperty(subtype="FILE_PATH")
        files: CollectionProperty(name='File paths', type=bpy.types.OperatorFileListElement)
        filter_glob: StringProperty(default="*.vwrld_c", options={'HIDDEN'})

        invert_uv: BoolProperty(name="invert UV?", default=True)
        scale: FloatProperty(name="World scale", default=0.0328083989501312)  # LifeForLife suggestion

        use_placeholders: BoolProperty(name="Use placeholders instead of objects", default=False)
        load_static: BoolProperty(name="Load static meshes", default=True)
        load_dynamic: BoolProperty(name="Load entities", default=True)

        def execute(self, context):

            if Path(self.filepath).is_file():
                directory = Path(self.filepath).parent.absolute()
            else:
                directory = Path(self.filepath).absolute()
            for n, file in enumerate(self.files):
                print(f"Loading {n}/{len(self.files)}")
                world = ValveWorld(str(directory / file.name), self.invert_uv, self.scale)
                if self.load_static:
                    world.load_static()
                if self.load_dynamic:
                    world.load_entities(self.use_placeholders)
            print("Hey @LifeForLife, everything is imported as you wanted!!")
            return {'FINISHED'}

        def invoke(self, context, event):
            wm = context.window_manager
            wm.fileselect_add(self)
            return {'RUNNING_MODAL'}


    # noinspection PyUnresolvedReferences
    class VMATImporter_OT_operator(bpy.types.Operator):
        """Load Source2 material"""
        bl_idname = "source_io.vmat"
        bl_label = "Import Source2 VMDL file"
        bl_options = {'UNDO'}

        filepath: StringProperty(subtype="FILE_PATH")
        files: CollectionProperty(name='File paths', type=bpy.types.OperatorFileListElement)
        flip: BoolProperty(name="Flip texture", default=True)
        filter_glob: StringProperty(default="*.vmat_c", options={'HIDDEN'})

        def execute(self, context):

            if Path(self.filepath).is_file():
                directory = Path(self.filepath).parent.absolute()
            else:
                directory = Path(self.filepath).absolute()
            for n, file in enumerate(self.files):
                print(f"Loading {n}/{len(self.files)}")
                material = ValveMaterial(str(directory / file.name))
                material.load(self.flip)
            return {'FINISHED'}

        def invoke(self, context, event):
            wm = context.window_manager
            wm.fileselect_add(self)
            return {'RUNNING_MODAL'}


    class VTEXImporter_OT_operator(bpy.types.Operator):
        """Load Source Engine VTF texture"""
        bl_idname = "source_io.vtex"
        bl_label = "Import VTEX"
        bl_options = {'UNDO'}

        filepath: StringProperty(subtype='FILE_PATH', )
        flip: BoolProperty(name="Flip texture", default=True)
        files: CollectionProperty(name='File paths', type=bpy.types.OperatorFileListElement)
        filter_glob: StringProperty(default="*.vtex_c", options={'HIDDEN'})

        def execute(self, context):
            if Path(self.filepath).is_file():
                directory = Path(self.filepath).parent.absolute()
            else:
                directory = Path(self.filepath).absolute()
            for file in self.files:
                texture = ValveTexture(str(directory / file.name))
                texture.load(self.flip)
            return {'FINISHED'}

        def invoke(self, context, event):
            wm = context.window_manager
            wm.fileselect_add(self)
            return {'RUNNING_MODAL'}


    class LoadPlaceholder_OT_operator(bpy.types.Operator):
        bl_idname = "source_io.load_placeholder"
        bl_label = "Load placeholder"
        bl_options = {'UNDO'}

        def execute(self, context):
            for obj in context.selected_objects:

                if obj.get("entity_data", None):
                    custom_prop_data = obj['entity_data']

                    model_path = backwalk_file_resolver(custom_prop_data['parent_path'],
                                                        Path(custom_prop_data['prop_path'] + "_c"))
                    if model_path:

                        collection = bpy.data.collections.get(custom_prop_data['type'],
                                                              None) or bpy.data.collections.new(
                            name=custom_prop_data['type'])
                        try:
                            bpy.context.scene.collection.children.link(collection)
                        except:
                            pass

                        model = ValveModel(model_path)
                        model.load_mesh(True, parent_collection=collection)
                        for ob in model.objects:  # type:bpy.types.Object
                            ob.location = obj.location
                            ob.rotation_mode = "XYZ"
                            ob.rotation_euler = obj.rotation_euler
                            ob.scale = obj.scale
                        bpy.data.objects.remove(obj)
                    else:
                        self.report({'INFO'}, f"Model '{custom_prop_data['prop_path']}_c' not found!")
            return {'FINISHED'}


    class SourceIOUtils_PT_panel(bpy.types.Panel):
        bl_label = "SourceIO utils"
        bl_idname = "source_io.utils"
        bl_space_type = "VIEW_3D"
        bl_region_type = "UI"
        bl_category = "SourceIO"

        @classmethod
        def poll(cls, context):
            obj = context.active_object  # type:bpy.types.Object
            if obj.type == "EMPTY" or obj.type == 'MESH':
                return True
            return False

        def draw(self, context):
            self.layout.label(text="SourceIO stuff")
            obj = context.active_object  # type:bpy.types.Object
            if obj.get("entity_data", None):
                self.layout.operator('source_io.load_placeholder')


    class DMXImporter_OT_operator(bpy.types.Operator):
        """Load Source Engine DMX scene"""
        bl_idname = "source_io.dmx"
        bl_label = "Import Source Session file"
        bl_options = {'UNDO'}

        filepath: StringProperty(subtype="FILE_PATH")
        files: CollectionProperty(name='File paths', type=bpy.types.OperatorFileListElement)
        project_dir: StringProperty(default='', name='SFM project folder (usermod)')
        filter_glob: StringProperty(default="*.dmx", options={'HIDDEN'})

        def execute(self, context):
            directory = Path(self.filepath).parent.absolute()
            preferences = context.preferences
            addon_prefs = preferences.addons['SourceIO'].preferences
            print(addon_prefs)
            sfm_path = self.project_dir if self.project_dir else addon_prefs.sfm_path
            for file in self.files:
                importer = Session(str(directory / file.name), sfm_path)
                importer.parse()
                importer.load_scene()
                # importer.load_lights()
                # importer.create_cameras()
            return {'FINISHED'}

        def invoke(self, context, event):
            wm = context.window_manager
            wm.fileselect_add(self)
            return {'RUNNING_MODAL'}


    class VTFImporter_OT_operator(bpy.types.Operator):
        """Load Source Engine VTF texture"""
        bl_idname = "import_texture.vtf"
        bl_label = "Import VTF"
        bl_options = {'UNDO'}

        filepath: StringProperty(subtype='FILE_PATH', )
        files: CollectionProperty(name='File paths', type=bpy.types.OperatorFileListElement)

        load_alpha: BoolProperty(default=True, name='Load alpha into separate image')
        only_alpha: BoolProperty(default=False, name='Only load alpha')

        filter_glob: StringProperty(default="*.vtf", options={'HIDDEN'})

        def execute(self, context):
            if Path(self.filepath).is_file():
                directory = Path(self.filepath).parent.absolute()
            else:
                directory = Path(self.filepath).absolute()
            for file in self.files:
                import_texture(str(directory / file.name), self.load_alpha, self.only_alpha)
            return {'FINISHED'}

        def invoke(self, context, event):
            wm = context.window_manager
            wm.fileselect_add(self)
            return {'RUNNING_MODAL'}


    # class VMTImporter_OT_operator(bpy.types.Operator):
    #     """Load Source Engine VMT material"""
    #     bl_idname = "import_texture.vmt"
    #     bl_label = "Import VMT"
    #     bl_options = {'UNDO'}
    #
    #     filepath: StringProperty(
    #         subtype='FILE_PATH',
    #     )
    #     files: CollectionProperty(type=bpy.types.PropertyGroup)
    #     load_alpha: BoolProperty(default=True, name='Load alpha into separate image')
    #
    #     filter_glob: StringProperty(default="*.vmt", options={'HIDDEN'})
    #     game: StringProperty(name="PATH TO GAME", subtype='FILE_PATH', default="")
    #     override: BoolProperty(default=False, name='Override existing?')
    #
    #     def execute(self, context):
    #         if Path(self.filepath).is_file():
    #             directory = Path(self.filepath).parent.absolute()
    #         else:
    #             directory = Path(self.filepath).absolute()
    #         for file in self.files:
    #             vmt = VMT(str(directory / file.name), self.game)
    #             mat = BlenderMaterial(vmt)
    #             mat.load_textures(self.load_alpha)
    #             if mat.create_material(
    #                     self.override) == 'EXISTS' and not self.override:
    #                 self.report({'INFO'}, '{} material already exists')
    #         return {'FINISHED'}
    #
    #     def invoke(self, context, event):
    #         wm = context.window_manager
    #         wm.fileselect_add(self)
    #         return {'RUNNING_MODAL'}

    class VTFExport_OT_operator(bpy.types.Operator):
        """Export VTF texture"""
        bl_idname = "export_texture.vtf"
        bl_label = "Export VTF"

        filename_ext = ".vtf"

        filter_glob: StringProperty(default="*.vtf", options={'HIDDEN'})

        filepath: StringProperty(
            subtype='FILE_PATH',
        )

        filename: StringProperty(
            name="File Name",
            description="Name used by the exported file",
            maxlen=255,
            subtype='FILE_NAME',
        )

        img_format: EnumProperty(
            name="VTF Type Preset",
            description="Choose a preset. It will affect the result's format and flags.",
            items=(
                ('RGBA8888', "RGBA8888 Simple", "RGBA8888 format, format-specific Eight Bit Alpha flag only"),
                ('RGBA8888Normal', "RGBA8888 Normal Map",
                 "RGBA8888 format, format-specific Eight Bit Alpha and Normal Map flags"),
                ('RGB888', "RGBA888 Simple", "RGB888 format, no alpha"),
                ('RGB888Normal', "RGB888 Normal Map", "RGB888 format, no alpha and Normal map flag"),
                ('DXT1', "DXT1 Simple", "DXT1 format, no flags"),
                ('DXT5', "DXT5 Simple", "DXT5 format, format-specific Eight Bit Alpha flag only"),
                ('DXT1Normal', "DXT1 Normal Map",
                 "DXT1 format, Normal Map flag only"),
                ('DXT5Normal', "DXT5 Normal Map",
                 "DXT5 format, format-specific Eight Bit Alpha and Normal Map flags")),
            default='RGBA8888',
        )

        def execute(self, context):
            sima = context.space_data
            ima = sima.image
            if ima is None:
                self.report({"ERROR_INVALID_INPUT"}, "No Image provided")
            else:
                print(context)
                export_texture(ima, self.filepath, self.img_format)
            return {'FINISHED'}

        def invoke(self, context, event):
            if not self.filepath:
                blend_filepath = context.blend_data.filepath
                if not blend_filepath:
                    blend_filepath = "untitled"
                else:
                    blend_filepath = os.path.splitext(blend_filepath)[0]
                    self.filepath = os.path.join(
                        os.path.dirname(blend_filepath),
                        self.filename + self.filename_ext)
            else:
                self.filepath = os.path.join(
                    os.path.dirname(
                        self.filepath),
                    self.filename +
                    self.filename_ext)

            context.window_manager.fileselect_add(self)
            return {'RUNNING_MODAL'}


    def export(self, context):
        cur_img = context.space_data.image
        if cur_img is None:
            self.layout.operator(VTFExport_OT_operator.bl_idname, text='Export to VTF')
        else:
            self.layout.operator(VTFExport_OT_operator.bl_idname, text='Export to VTF').filename = \
                os.path.splitext(cur_img.name)[0]


    # noinspection PyPep8Naming
    class SourceIO_MT_Menu(bpy.types.Menu):
        bl_label = "Source engine"
        bl_idname = "IMPORT_MT_sourceio"

        def draw(self, context):
            layout = self.layout
            layout.operator(MDLImporter_OT_operator.bl_idname, text="Source model (.mdl)")
            layout.operator(BSPImporter_OT_operator.bl_idname, text="Source map (.bsp)")
            layout.operator(VTFImporter_OT_operator.bl_idname, text="Source texture (.vtf)")
            # self.layout.operator(VMTImporter_OT_operator.bl_idname, text="Source material (.vmt)")
            layout.operator(DMXImporter_OT_operator.bl_idname, text="SFM session (.dmx)")
            layout.operator(VMDLImporter_OT_operator.bl_idname, text="Source2 model (.vmdl)")
            layout.operator(VWRLDImporter_OT_operator.bl_idname, text="Source2 map (.vwrld)")
            layout.operator(VTEXImporter_OT_operator.bl_idname, text="Source2 texture (.vtex)")
            layout.operator(VMATImporter_OT_operator.bl_idname, text="Source2 material (.vmat)")


    def menu_import(self, context):
        self.layout.menu(SourceIO_MT_Menu.bl_idname)


    # VMTImporter_OT_operator,
    classes = (MDLImporter_OT_operator, BSPImporter_OT_operator, DMXImporter_OT_operator,
               VTFExport_OT_operator, VTFImporter_OT_operator,
               VMDLImporter_OT_operator, VTEXImporter_OT_operator, VMATImporter_OT_operator, VWRLDImporter_OT_operator,
               SourceIOPreferences, SourceIO_MT_Menu, SourceIOUtils_PT_panel, LoadPlaceholder_OT_operator)
    try:
        register_, unregister_ = bpy.utils.register_classes_factory(classes)
    except:
        register_ = lambda: 0
        unregister_ = lambda: 0


    def register():
        register_()
        bpy.types.TOPBAR_MT_file_import.append(menu_import)
        bpy.types.IMAGE_MT_image.append(export)


    def unregister():
        bpy.types.TOPBAR_MT_file_import.remove(menu_import)
        bpy.types.IMAGE_MT_image.remove(export)
        unregister_()
else:
    def register():
        pass


    def unregister():
        pass

if __name__ == "__main__":
    register()
