import bpy
from mathutils import Vector
from enum import Enum


class RootResult(Enum):
    ROOT_BONE_AlREADY_EXISTS = -3
    ROOT_BONE_DOES_NOT_EXIST = -2
    INVALID_ROOT_BONE_NAME = -1
    ERROR = 0
    SUCCESS = 1

class BakeType(Enum):
    KEEP_AT_ARMATURE_ORIGIN = "KEEP_AT_ARMATURE_ORIGIN"
    KEEP_ON_GROUND = "KEEP_ON_GROUND"
    ALLOW_OFFSET_IN_AIR = "ALLOW_OFFSET_IN_AIR"

def remove_bone_tracks(action, bone_name):
    if not action:
        print("No action provided")
        return

    target_path = f'pose.bones["{bone_name}"]'


    # This is for blender 5.0 since fcurves property have been removed from Action
    if not hasattr(action, "fcurves"): 
        from bpy_extras import anim_utils

        for slot in action.slots:
            channelbag = anim_utils.action_ensure_channelbag_for_slot(action, slot)
            to_remove = [fcu for fcu in channelbag.fcurves if fcu.data_path.startswith(target_path)]
            for fcu in to_remove:
                channelbag.fcurves.remove(fcu)

        return


    # This is for blender <5.0
    to_remove = [fcu for fcu in action.fcurves if fcu.data_path.startswith(target_path)]
    for fcu in to_remove:
        action.fcurves.remove(fcu)

def create_root_bone(armature, root_bone_name, root_length):

    # Get armature
    if not armature or armature.type != 'ARMATURE':
        print(f"Armature not found!")
        return RootResult.ERROR
    
    
    # Check for valid root bone name
    if not root_bone_name:
        print(f"No Root Bone name provided")
        return RootResult.INVALID_ROOT_BONE_NAME
    

    # Go into edit mode
    bpy.context.view_layer.objects.active = armature
    armature.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT')
    

    # Check if root bone already exists
    ebones = armature.data.edit_bones
    if root_bone_name in ebones:
        root_bone = ebones[root_bone_name]
        return RootResult.ROOT_BONE_AlREADY_EXISTS


    # Get inverse of armature object transformation
    armature_rot = armature.matrix_world.to_quaternion()


    # Create root bone
    root_bone = ebones.new(root_bone_name)
    root_bone.head = Vector((0, 0, 0))
    root_bone.tail = armature_rot.inverted() @ Vector((0, 0, root_length))  # This assumes whatever rotation the armature object has is it's upright position 


    # Make root bone parent of top most bones
    top_bones = [bone for bone in ebones if bone.parent is None]
    for top_bone in top_bones:
        top_bone.parent = root_bone


    # Return to object mode or otherwise the bone won't be detected    
    bpy.ops.object.mode_set(mode='OBJECT')


    return RootResult.SUCCESS

def bake_root_into_action(armature, root_bone_name, action, postfix, bake_mode, follow_bone_name, bake_only_root):

    # To ensure "ReferenceError: StructRNA of type Action has been removed" is isolated i.e. when an unused action is passed
    try:
        action.name
    except ReferenceError as e:
        return RootResult.ERROR


    # Make sure armature is selected and Go into object mode
    bpy.context.view_layer.objects.active = armature
    bpy.ops.object.mode_set(mode='OBJECT')


    # Check if valid armature armature
    if not armature or armature.type != 'ARMATURE':
        print(f"Armature not found!")
        return RootResult.ERROR
    

    # Check if root bone exists
    root_bone_exists = any(bone.name == root_bone_name for bone in armature.data.bones)
    if (not root_bone_name) or (not root_bone_exists):
        print(f"Root Bone does not exist!")
        return RootResult.ROOT_BONE_DOES_NOT_EXIST


    # Check if follow bone name
    is_follow_required = (bake_mode == BakeType.ALLOW_OFFSET_IN_AIR.value or bake_mode == BakeType.ALLOW_OFFSET_IN_AIR.value)
    follow_bone_exists = any(bone.name == follow_bone_name for bone in armature.data.bones)
    if is_follow_required and (not follow_bone_name) or (not follow_bone_exists):
        print(f"Follow Bone does not exist!")
        return RootResult.FOLLOW_BONE_DOES_NOT_EXIST


    # If Follow Bone found then use it to calculate offset with root bone
    offset_height = 0.0
    if(bake_mode == BakeType.ALLOW_OFFSET_IN_AIR.value and follow_bone_name is not None and follow_bone_name in armature.data.bones):
        
        # Go into edit mode and get edit bones
        bpy.ops.object.mode_set(mode='EDIT')
        ebones = armature.data.edit_bones


        # Calculate offset height
        armature_rot = armature.matrix_world.to_quaternion()
        follow_bone_world_loc = armature_rot @ ebones[follow_bone_name].head
        root_bone_world_loc = armature_rot @ ebones[root_bone_name].head
        offset_height = follow_bone_world_loc.z - root_bone_world_loc.z


    # Go into armature pose mode
    bpy.ops.object.mode_set(mode='POSE')
    

    # Delete baked action if it already exists
    new_action_name = action.name + postfix
    if (new_action_name in bpy.data.actions) and (postfix is not None):
        existing_action = bpy.data.actions[new_action_name]
        bpy.data.actions.remove(existing_action)
    

    # Duplicate action (or get same action based on postfix), assign to armature and bake
    new_action = action.copy() if postfix is not None else action
    new_action.name = new_action_name
    armature.animation_data.action = new_action


    # Get start and end frame number
    frame_start, frame_end = int(new_action.frame_range[0]), int(new_action.frame_range[1])
    pose_bones = armature.pose.bones


    # Clear existing tracks of root bone
    remove_bone_tracks(new_action, root_bone_name)


    # Get root and follow pose bones
    root_bone = armature.pose.bones[root_bone_name]
    follow_bone = armature.pose.bones[follow_bone_name]

    
    # Before starting make sure root is at armature origin
    bpy.ops.pose.select_all(action='DESELECT')
    root_bone.select = True
    bpy.ops.pose.transforms_clear()


    # Iterate and store armature locations of follow bone at each frame 
    new_root_locations = {}
    new_follow_locations = {}
    for frame in range(frame_start, frame_end + 1):
        bpy.context.scene.frame_set(frame)


        # === KEEP ROOT AT ORIGIN ===
        if bake_mode == BakeType.KEEP_AT_ARMATURE_ORIGIN.value:
            new_root_locations[frame] = Vector((0, 0, 0))
            new_follow_locations[frame] = follow_bone.location

        
        # === KEEP ROOT ON GROUND ===
        elif bake_mode == BakeType.KEEP_ON_GROUND.value:
            # Set root bone location "on ground" 
            armature_transform = armature.matrix_world
            root_world_pos = armature_transform @ (follow_bone.bone.matrix_local @ follow_bone.location)
            ground_z = (armature_transform @ root_bone.bone.head).z
            root_world_pos.z = ground_z

            # Calculate new root location
            new_root_locations[frame] = root_bone.bone.matrix_local.inverted() @ armature_transform.inverted() @ root_world_pos

            # Calculate new follow bone location
            follow_world_pos = armature_transform @ (follow_bone.bone.matrix_local @ follow_bone.location)
            new_follow_locations[frame] = (follow_bone.bone.matrix_local.inverted() @ armature_transform.inverted() @ follow_world_pos) - new_root_locations[frame]

        
        # === ALLOW ROOT OFFSET IN AIR ===
        elif bake_mode == BakeType.ALLOW_OFFSET_IN_AIR.value:

            # Set root bone location same as follow bone location with offset and make sure root does not go below ground
            armature_global_rot = armature.matrix_world.to_quaternion() # Intentionally used rotation instead of transformation otherwise scaled armature causes issues
            root_world_pos = armature_global_rot @ (follow_bone.bone.matrix_local @ follow_bone.location)
            ground_z = (armature_global_rot @ root_bone.bone.head).z
            diff_world_pos = root_world_pos.z - offset_height 
            root_world_pos.z = max(diff_world_pos, ground_z)

            # Calculate new root location
            new_root_locations[frame] = root_bone.bone.matrix_local.inverted() @ (armature_global_rot.inverted() @ root_world_pos)


            # This ensures follow bone moves with root bone and not on it's own
            follow_local_pos = follow_bone.location
            follow_local_pos.x = 0  
            follow_local_pos.y = 0  
            follow_local_pos.z = 0  
            
            # This ensures follow bone's z is such that the feet are on ground
            follow_world_pos = armature_global_rot @ (follow_bone.bone.matrix_local @ follow_local_pos)
            if(diff_world_pos < ground_z):
                follow_world_pos.z = follow_world_pos.z - (ground_z - diff_world_pos)

            # Calculate new follow bone location
            new_follow_locations[frame] = follow_bone.bone.matrix_local.inverted() @ (armature_global_rot.inverted() @ follow_world_pos)


    # Iterate and insert keyframes
    for frame in range(frame_start, frame_end + 1):

        # Set frame
        bpy.context.scene.frame_set(frame)

        # Set locations
        root_bone.location = new_root_locations[frame]
        follow_bone.location = new_follow_locations[frame]

        # Insert keyframes
        root_bone.keyframe_insert(data_path="location", frame=frame)
        follow_bone.keyframe_insert(data_path="location", frame=frame)


    # Bake action
    bpy.ops.pose.select_all(action='DESELECT')
    root_bone.select = True
    bpy.ops.nla.bake(
        frame_start=frame_start, 
        frame_end=frame_end,
        step=1, 
        only_selected=bake_only_root,
        visual_keying=True, 
        clear_constraints=False,
        clear_parents=False, 
        use_current_action=True,
        bake_types={'POSE'}
    )
