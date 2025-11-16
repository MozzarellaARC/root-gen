bl_info = {
    "name": "RootMaker",
    "category": "Animation",
    "author": "Manas R. Makde",
    "version": (1, 0, 0),
    "description": "An add-on for creating a root bone and baking it into existing actions"
}


import bpy
import logging
from .root_maker_utils import *


class RootMakerMessagePopup(bpy.types.Operator):
    bl_idname = "rootmaker.message_popup"
    bl_label = "RootMaker Message"
    message_heading: bpy.props.StringProperty(name="Heading", default="")
    message_icon: bpy.props.StringProperty(name="Icon", default="INFO")

    def execute(self, context):
        return {'FINISHED'}
    def invoke(self, context, event):
        wm = context.window_manager
        return wm.invoke_props_dialog(self, width=500)
    def draw(self, context):
        layout = self.layout
        lines = self.message_heading.split("\n")
        for i, line in enumerate(lines):
            layout.label(
                text=line,
                icon=self.message_icon if i == 0 else 'BLANK1'
            )

class RootMakerActionItem(bpy.types.PropertyGroup):
    action: bpy.props.PointerProperty(name="Action", type=bpy.types.Action)

class RootMakerProperties(bpy.types.PropertyGroup):

    target_armature: bpy.props.PointerProperty(
        name="Target Armature",
        type=bpy.types.Object,
        poll=lambda self, obj: obj.type == "ARMATURE"
    )
    root_bone_name: bpy.props.StringProperty(
        name="Root Bone Name",
        default="RootBone"
    )
    root_bone_length: bpy.props.FloatProperty(
        name="Root Bone Length",
        default=0.2,
        subtype='DISTANCE'
    )
    follow_bone: bpy.props.StringProperty(
        name="Keep Offset with Bone",
        default=""
    )
    bake_postfix: bpy.props.StringProperty(
        name="Bake Postfix",
        default="_RootBaked"
    )
    bake_mode: bpy.props.EnumProperty(
        name="Bake Mode",
        items=[
            (BakeType.KEEP_AT_ARMATURE_ORIGIN.value, "Keep at Armature Origin", "Keep root bone at origin"),
            (BakeType.KEEP_ON_GROUND.value, "Keep on Ground", "Keep the root bone on the ground"),
            (BakeType.ALLOW_OFFSET_IN_AIR.value, "Allow Offset in Air", "Allow the root bone to lift up from ground while mainintaing offset")
        ],
        default=BakeType.KEEP_AT_ARMATURE_ORIGIN.value
    )
    bake_only_root: bpy.props.BoolProperty(
        name="Bake Only Root Bone",
        default=False
    )
    actions_to_bake: bpy.props.CollectionProperty(type=RootMakerActionItem)
    actions_index: bpy.props.IntProperty(default=0)

class ROOTMAKER_UL_Actions(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        layout.prop(item, "action", text="", emboss=True)

class RootMakerPanel(bpy.types.Panel):
    bl_label = "RootMaker"
    bl_idname = "VIEW3D_PT_rootmaker_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'RootMaker'

    def draw(self, context):
        layout = self.layout
        props = context.scene.rootmaker_props

        layout.prop(props, "target_armature")
        layout.prop(props, "root_bone_name")
        layout.prop(props, "root_bone_length")
        layout.prop(props, "bake_postfix")
        layout.prop(props, "bake_mode")

        if props.target_armature and (props.bake_mode == BakeType.KEEP_ON_GROUND.value or props.bake_mode == BakeType.ALLOW_OFFSET_IN_AIR.value):
            layout.prop_search(
                props,
                "follow_bone",
                props.target_armature.data,
                "bones",
                text="Follow Bone"
            )

        box = layout.box()
        box.label(text="Actions to Affect")
        row = box.row()
        row.template_list("ROOTMAKER_UL_Actions", "", props, "actions_to_bake", props, "actions_index")
        col = row.column(align=True)
        col.operator("rootmaker.actions_add", icon='ADD', text="")
        col.operator("rootmaker.actions_remove", icon='REMOVE', text="")
        row = box.row(align=True)
        row.operator("rootmaker.actions_add_all", text="Add All")
        row.operator("rootmaker.actions_remove_all", text="Remove All")

        layout.prop(props, "bake_only_root")

        layout.separator()  # horizontal separation like <HR>
        button_box = layout.box()
        row = button_box.row()
        row.scale_y = 2.0  # increase height
        row.operator("rootmaker.create_root_bone", text="Create Root Bone", icon='BONE_DATA', emboss=True)
        row.operator("rootmaker.bake_actions", text="Bake into Actions", icon='ACTION', emboss=True)

class ROOTMAKER_OT_ActionsAdd(bpy.types.Operator):
    bl_idname = "rootmaker.actions_add"
    bl_label = "Add Action"
    tooltip = "Add an action to bake"

    def execute(self, context):
        props = context.scene.rootmaker_props
        item = props.actions_to_bake.add()
        props.actions_index = len(props.actions_to_bake) - 1
        return {'FINISHED'}

class ROOTMAKER_OT_ActionsRemove(bpy.types.Operator):
    bl_idname = "rootmaker.actions_remove"
    bl_label = "Remove Action"
    tooltip = "Remove selected action from the bake list"

    def execute(self, context):
        props = context.scene.rootmaker_props
        if props.actions_to_bake:
            props.actions_to_bake.remove(props.actions_index)
            props.actions_index = max(0, props.actions_index - 1)
        return {'FINISHED'}

class ROOTMAKER_OT_ActionsAddAll(bpy.types.Operator):
    bl_idname = "rootmaker.actions_add_all"
    bl_label = "Add All Actions"
    tooltip = "Add all actions from the scene to bake list"

    def execute(self, context):
        props = context.scene.rootmaker_props

        # Clear all first
        props.actions_to_bake.clear()
        props.actions_index = 0

        # Add all back
        for action in bpy.data.actions:
            item = props.actions_to_bake.add()
            item.action = action
        
        return {'FINISHED'}

class ROOTMAKER_OT_ActionsRemoveAll(bpy.types.Operator):
    bl_idname = "rootmaker.actions_remove_all"
    bl_label = "Remove All Actions"
    tooltip = "Remove all actions from the bake list"

    def execute(self, context):
        props = context.scene.rootmaker_props
        props.actions_to_bake.clear()
        props.actions_index = 0
        return {'FINISHED'}

class ROOTMAKER_OT_CreateRootBone(bpy.types.Operator):
    bl_idname = "rootmaker.create_root_bone"
    bl_label = "Create Root Bone"
    tooltip = "Create the root bone with the specified properties"

    def execute(self, context):
        props = context.scene.rootmaker_props
        
        # Check if armature is passed
        armature = props.target_armature
        if armature is None:
            popup(f"Target Armature cannot be blank!", "CANCEL")
            return {'FINISHED'}
        

        # Check if armature is valid
        if armature.type != 'ARMATURE' or armature.name not in bpy.context.view_layer.objects:
            popup(f"Invalid Target Armature!", "CANCEL")
            return {'FINISHED'}


        # Check if root bone name is passed
        root_bone_name = props.root_bone_name
        if not root_bone_name:
            popup(f"Root Bone Name cannot be empty!", "CANCEL")
            return {'FINISHED'}
        

        # Create bone and notify user based on return
        status = create_root_bone(armature, props.root_bone_name, props.root_bone_length)
        if(status == RootResult.ERROR):
            popup(f"Error occured while creating root bone! Check terminal for more information", "CANCEL")
        elif(status == RootResult.SUCCESS):
            popup(f"Successfully created root bone!")
        elif(status == RootResult.ROOT_BONE_AlREADY_EXISTS):
            popup(f"Root bone by that name already exists!", "CANCEL")

        return {'FINISHED'}

class ROOTMAKER_OT_BakeActions(bpy.types.Operator):
    bl_idname = "rootmaker.bake_actions"
    bl_label = "Bake Actions"
    tooltip = "Bake the selected actions with the root bone"

    def execute(self, context):
        props = context.scene.rootmaker_props
        
        # Check if armature is passed
        armature = props.target_armature
        if armature is None:
            popup(f"Target Armature cannot be blank!", "CANCEL")
            return {'FINISHED'}
        

        # Check if armature is valid
        if armature.type != 'ARMATURE' or armature.name not in bpy.context.view_layer.objects:
            popup(f"Invalid Target Armature!", "CANCEL")
            return {'FINISHED'}


        # Check if root bone name is passed
        if not props.root_bone_name:
            popup(f"Root Bone Name cannot be empty!", "CANCEL")
            return {'FINISHED'}


        # Check if root bone exists
        does_root_bone_exist = any(bone.name == props.root_bone_name for bone in armature.data.bones)
        if (not does_root_bone_exist):
            popup(f"Root Bone does not exist in '{armature.name}'", "CANCEL")
            return {'FINISHED'}
        

        # Auto calculate follow bone if not provided
        if(not props.follow_bone):
            top_bones = [b.name for b in armature.data.bones if b.parent and b.parent.name == props.root_bone_name]
            if(len(top_bones) != 0):
                props.follow_bone = top_bones[0]
            

        # Check if follow bone exists
        if (props.follow_bone not in armature.data.bones):
            popup(f"Follow Bone does not exist in '{armature.name}'", "CANCEL")
            return {'FINISHED'}
        
        
        # Get all actions
        actions = []
        for item in props.actions_to_bake:
            if not item.action:
                continue


            # To ensure "ReferenceError: StructRNA of type Action has been removed" does not occur
            try: 
                item.action.name
            except ReferenceError as e:
                continue
            

            actions.append(item.action)


        # Check if no action was provided
        if len(actions) == 0:
            popup(f"No actions provided!", "CANCEL")
            return {'FINISHED'}
        

        # Create bone and notify user
        try:
            for action in actions:
                status = bake_root_into_action(armature, props.root_bone_name, action, props.bake_postfix, props.bake_mode, props.follow_bone, props.bake_only_root)

            popup(f"Successfully Baked Actions!")
        
        except Exception as e:
            logging.exception("Error occured while baking actions!")
            popup(f"Error occured while baking actions! Check terminal for more information", "CANCEL")


        return {'FINISHED'}

def popup(message, icon="INFO"):
    bpy.ops.rootmaker.message_popup('INVOKE_DEFAULT', **{ "message_heading": message,  "message_icon" : icon })

def register():
    bpy.utils.register_class(RootMakerMessagePopup)
    bpy.utils.register_class(RootMakerActionItem)
    bpy.utils.register_class(RootMakerProperties)
    bpy.utils.register_class(ROOTMAKER_UL_Actions)
    bpy.utils.register_class(RootMakerPanel)
    bpy.utils.register_class(ROOTMAKER_OT_ActionsAdd)
    bpy.utils.register_class(ROOTMAKER_OT_ActionsRemove)
    bpy.utils.register_class(ROOTMAKER_OT_ActionsAddAll)
    bpy.utils.register_class(ROOTMAKER_OT_ActionsRemoveAll)
    bpy.utils.register_class(ROOTMAKER_OT_CreateRootBone)
    bpy.utils.register_class(ROOTMAKER_OT_BakeActions)
    bpy.types.Scene.rootmaker_props = bpy.props.PointerProperty(type=RootMakerProperties)

def unregister():
    del bpy.types.Scene.rootmaker_props
    bpy.utils.unregister_class(ROOTMAKER_OT_BakeActions)
    bpy.utils.unregister_class(ROOTMAKER_OT_CreateRootBone)
    bpy.utils.unregister_class(ROOTMAKER_OT_ActionsRemoveAll)
    bpy.utils.unregister_class(ROOTMAKER_OT_ActionsAddAll)
    bpy.utils.unregister_class(ROOTMAKER_OT_ActionsRemove)
    bpy.utils.unregister_class(ROOTMAKER_OT_ActionsAdd)
    bpy.utils.unregister_class(RootMakerPanel)
    bpy.utils.unregister_class(ROOTMAKER_UL_Actions)
    bpy.utils.unregister_class(RootMakerProperties)
    bpy.utils.unregister_class(RootMakerActionItem)
    bpy.utils.unregister_class(RootMakerMessagePopup)

if __name__ == "__main__":
    register()