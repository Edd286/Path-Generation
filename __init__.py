import bpy
import bpy_extras
from mathutils import Vector

class OBJECT_OT_select_curve_type(bpy.types.Operator):
    """Operator that lets users choose between NURBS and Bezier curve types.
    This choice affects how the final curve will be generated."""
    bl_idname = "object.select_curve_type"
    bl_label = "Select Curve Type"

    curve_type: bpy.props.StringProperty()

    def execute(self, context):
        context.scene.curve_type = self.curve_type
        self.report({'INFO'}, f"Selected Curve Type: {self.curve_type}")
        return {'FINISHED'}

class ControlPointProperty(bpy.types.PropertyGroup):
    """Defines the properties that each control point has:
    - x, y, z: 3D coordinates in space
    - sphere_name: identifier for the visual sphere representation"""
    def update_coords(self, context):
        """Callback that runs whenever coordinates are changed"""
        # Find this control point's index
        control_points = context.scene.control_points
        for i, point in enumerate(control_points):
            if point == self:
                create_control_point_sphere(context, self, i)
                break

    x: bpy.props.FloatProperty(name="X", default=0.0, update=update_coords)
    y: bpy.props.FloatProperty(name="Y", default=0.0, update=update_coords)
    z: bpy.props.FloatProperty(name="Z", default=0.0, update=update_coords)
    sphere_name: bpy.props.StringProperty(default="")

def create_control_point_sphere(context, control_point, index):
    """Creates or updates a sphere to visually represent a control point.
    Each control point gets one sphere, colored red for visibility.
    
    Args:
        context: Blender context
        control_point: The control point to visualize
        index: Position in the control points list
    """
    sphere_name = f"ControlPoint_{index}"
    control_point.sphere_name = sphere_name

    # Clean up any existing sphere for this control point
    cleanup_sphere(control_point.sphere_name)

    # Store current active collection
    active_layer_collection = context.view_layer.active_layer_collection

    # Ensure Control Points collection exists
    control_points_collection = bpy.data.collections.get("Control Points")
    if not control_points_collection:
        control_points_collection = bpy.data.collections.new("Control Points")
        context.scene.collection.children.link(control_points_collection)

    # Create new sphere mesh at the control point's position
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.15, location=(control_point.x, control_point.y, control_point.z))
    sphere = context.active_object
    sphere.name = sphere_name

    # Move sphere to Control Points collection
    for collection in sphere.users_collection:
        collection.objects.unlink(sphere)
    control_points_collection.objects.link(sphere)

    # Handle material creation and assignment
    material = bpy.data.materials.get("RedControlPointMaterial")
    if not material:
        # Create new red material if it doesn't exist yet
        material = bpy.data.materials.new(name="RedControlPointMaterial")
        material.use_nodes = True
        nodes = material.node_tree.nodes
        nodes.clear()
        
        # Set up shader nodes for red color
        diffuse = nodes.new(type='ShaderNodeBsdfDiffuse')
        diffuse.inputs[0].default_value = (1, 0, 0, 1)  # Pure red in RGBA
        
        material_output = nodes.new(type='ShaderNodeOutputMaterial')
        material.node_tree.links.new(diffuse.outputs[0], material_output.inputs[0])
    
    # Assign material to the sphere
    if sphere.data.materials:
        sphere.data.materials[0] = material
    else:
        sphere.data.materials.append(material)

    # Restore original active collection
    context.view_layer.active_layer_collection = active_layer_collection

def cleanup_sphere(sphere_name):
    """Removes a sphere object from the scene by its name.
    Used when updating or removing control points."""
    if sphere_name:
        sphere = bpy.data.objects.get(sphere_name)
        if sphere:
            bpy.data.objects.remove(sphere, do_unlink=True)

class OBJECT_OT_move_control_point(bpy.types.Operator):
    """Move a control point up or down in the list"""
    bl_idname = "object.move_control_point"
    bl_label = "Move Control Point"

    direction: bpy.props.EnumProperty(
        items=[
            ('UP', "Up", "Move point up"),
            ('DOWN', "Down", "Move point down")
        ]
    )
    index: bpy.props.IntProperty()

    def execute(self, context):
        control_points = context.scene.control_points
        num_points = len(control_points)
        
        old_index = self.index
        new_index = old_index - 1 if self.direction == 'UP' else old_index + 1

        if 0 <= new_index < num_points:
            # Store points we're swapping
            current_point = control_points[old_index]
            target_point = control_points[new_index]
            
            # Clean up existing spheres
            cleanup_sphere(current_point.sphere_name)
            cleanup_sphere(target_point.sphere_name)
            
            # Move the point
            control_points.move(old_index, new_index)
            context.scene.active_control_point_index = new_index
            
            # Update sphere names and recreate spheres
            control_points[old_index].sphere_name = f"ControlPoint_{old_index}"
            control_points[new_index].sphere_name = f"ControlPoint_{new_index}"
            create_control_point_sphere(context, control_points[old_index], old_index)
            create_control_point_sphere(context, control_points[new_index], new_index)

        return {'FINISHED'}

class OBJECT_OT_reorder_control_point(bpy.types.Operator):
    """Reorder control points through drag and drop"""
    bl_idname = "object.reorder_control_point"
    bl_label = "Reorder Control Point"
    
    old_index: bpy.props.IntProperty()
    new_index: bpy.props.IntProperty()
    
    def execute(self, context):
        control_points = context.scene.control_points
        
        # Clean up existing spheres
        for point in control_points:
            cleanup_sphere(point.sphere_name)
        
        # Move the point
        control_points.move(self.old_index, self.new_index)
        
        # Recreate all spheres in new order
        for i, point in enumerate(control_points):
            point.sphere_name = f"ControlPoint_{i}"
            create_control_point_sphere(context, point, i)
        
        context.scene.active_control_point_index = self.new_index
        return {'FINISHED'}

class CONTROL_POINTS_UL_list(bpy.types.UIList):
    """UIList for displaying and managing control points"""
    bl_idname = "CONTROL_POINTS_UL_list"

    # Add filtering options
    filter_name: bpy.props.StringProperty(
        name="Search",
        default="",
        description="Search control points by index or coordinates"
    )

    def draw_filter(self, context, layout):
        row = layout.row()
        row.prop(self, "filter_name", text="")

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            row = layout.row(align=True)
            
            # Add up/down movement controls
            if index > 0:
                op = row.operator("object.move_control_point", text="", icon='TRIA_UP', emboss=False)
                op.direction = 'UP'
                op.index = index
            else:
                row.label(text="", icon='BLANK1')
                
            if index < len(context.scene.control_points) - 1:
                op = row.operator("object.move_control_point", text="", icon='TRIA_DOWN', emboss=False)
                op.direction = 'DOWN'
                op.index = index
            else:
                row.label(text="", icon='BLANK1')
            
            # Control point number and coordinates
            row.label(text=f"Control Point {index + 1}")
            row.prop(item, "x", text="X")
            row.prop(item, "y", text="Y")
            row.prop(item, "z", text="Z")
            
            # Remove button
            row.operator("object.remove_control_point", text="", icon="X", emboss=False).index = index

    def filter_items(self, context, data, propname):
        items = getattr(data, propname)
        helper_funcs = bpy.types.UI_UL_list
        
        # Initialize flags for filtering
        flt_flags = [self.bitflag_filter_item] * len(items)
        
        # Filter by search string if one is provided
        if self.filter_name:
            for idx, item in enumerate(items):
                # Convert search term to lowercase for case-insensitive comparison
                search = self.filter_name.lower()
                # Create a string representation of the control point
                point_str = f"control point {idx + 1} x:{item.x:.2f} y:{item.y:.2f} z:{item.z:.2f}".lower()
                
                # If search term not found in point string, exclude this item
                if search not in point_str:
                    flt_flags[idx] = 0

        return flt_flags, []

class OBJECT_OT_add_control_point(bpy.types.Operator):
    """Add or insert a control point"""
    bl_idname = "object.add_control_point"
    bl_label = "Add Control Point"

    index: bpy.props.IntProperty(default=-1)

    def execute(self, context):
        control_points = context.scene.control_points
        num_points = len(control_points)

        # Handle adding point at the end
        if self.index < 0 or self.index > num_points:
            new_point = control_points.add()
            new_point.x, new_point.y, new_point.z = 0.0, 0.0, 0.0
            new_point.sphere_name = f"ControlPoint_{num_points}"
            create_control_point_sphere(context, new_point, num_points)
            context.scene.active_control_point_index = num_points
            return {'FINISHED'}

        # Store existing points' data and clean up spheres
        existing_points = []
        for i in range(num_points):
            point = control_points[i]
            existing_points.append({
                'x': point.x, 'y': point.y, 'z': point.z
            })
            cleanup_sphere(point.sphere_name)

        # Add new point at the end first
        new_point = control_points.add()
        
        # Shift existing points to make room for the new point
        for i in range(num_points, self.index, -1):
            prev_idx = i - 1
            if prev_idx >= 0 and prev_idx < len(existing_points):
                point = control_points[i]
                data = existing_points[prev_idx]
                point.x, point.y, point.z = data['x'], data['y'], data['z']

        # Set up the new point at the insertion position
        insert_point = control_points[self.index]
        insert_point.x, insert_point.y, insert_point.z = 0.0, 0.0, 0.0

        # Update all sphere names and recreate spheres
        for i, point in enumerate(control_points):
            point.sphere_name = f"ControlPoint_{i}"
            create_control_point_sphere(context, point, i)

        context.scene.active_control_point_index = self.index
        return {'FINISHED'}

class OBJECT_OT_remove_control_point(bpy.types.Operator):
    """Remove a specific control point"""
    bl_idname = "object.remove_control_point"
    bl_label = "Remove Control Point"

    index: bpy.props.IntProperty()

    def execute(self, context):
        control_points = context.scene.control_points
        if 0 <= self.index < len(control_points):
            # Cleanup the associated sphere before removing the point
            cleanup_sphere(control_points[self.index].sphere_name)
            control_points.remove(self.index)
            self.report({'INFO'}, f"Removed control point {self.index + 1}")
        else:
            self.report({'WARNING'}, "Invalid point index")
        return {'FINISHED'}

class OBJECT_OT_generate_curve(bpy.types.Operator):
    """Generate a curve from the control points"""
    bl_idname = "object.generate_curve"
    bl_label = "Generate Curve"

    def execute(self, context):
        scene = context.scene
        curve_type = scene.curve_type
        control_points = scene.control_points
        curve_name = scene.curve_name if scene.curve_name else "GeneratedCurve"  # Use custom name or default

        if not control_points:
            self.report({'WARNING'}, "No control points added!")
            return {'CANCELLED'}

        curve_data = bpy.data.curves.new(name=curve_name, type='CURVE')
        curve_data.dimensions = '3D'

        if curve_type == "NURBS":
            spline = curve_data.splines.new(type='NURBS')
            spline.points.add(len(control_points) - 1)
            for i, point in enumerate(control_points):
                spline.points[i].co = (point.x, point.y, point.z, 1.0)

            spline.order_u = min(4, len(control_points))
            spline.use_endpoint_u = True

        else:
            spline = curve_data.splines.new(type='BEZIER')
            spline.bezier_points.add(len(control_points) - 1)

            for i, point in enumerate(control_points):
                bezier_point = spline.bezier_points[i]
                bezier_point.co = (point.x, point.y, point.z)
                bezier_point.handle_right_type = 'AUTO'
                bezier_point.handle_left_type = 'AUTO'

        curve_obj = bpy.data.objects.new(f"{curve_name}Obj", curve_data)
        scene.collection.objects.link(curve_obj)

        self.report({'INFO'}, f"Generated {curve_type} curve: {curve_name}")
        return {'FINISHED'}

class OBJECT_OT_show_control_points(bpy.types.Operator):
    """Show Control Points as Spheres"""
    bl_idname = "object.show_control_points"
    bl_label = "Update Control Points"

    def execute(self, context):
        # First cleanup all existing spheres
        for obj in bpy.data.objects:
            if obj.name.startswith("ControlPoint_"):
                bpy.data.objects.remove(obj, do_unlink=True)

        # Create new spheres for all control points
        control_points = context.scene.control_points
        for i, point in enumerate(control_points):
            create_control_point_sphere(context, point, i)
        
        self.report({'INFO'}, "Control points displayed as spheres")
        return {'FINISHED'}

class OBJECT_OT_hide_control_points(bpy.types.Operator):
    """Hide all control point spheres from the viewport"""
    bl_idname = "object.hide_control_points"
    bl_label = "Hide Control Points"

    def execute(self, context):
        # Get the Control Points collection
        control_points_collection = bpy.data.collections.get("Control Points")
        if control_points_collection:
            # Remove all spheres from the collection
            for obj in control_points_collection.objects:
                bpy.data.objects.remove(obj, do_unlink=True)
        
        self.report({'INFO'}, "Control points hidden")
        return {'FINISHED'}

class LayoutDemoPanel(bpy.types.Panel):
    """Control points panel"""
    bl_label = "Custom Path Control Points Panel"
    bl_idname = "SCENE_PT_layout"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "scene"
    bl_options = {'DEFAULT_CLOSED'}  # Make panel collapsible

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        # Path settings
        path_box = layout.box()
        path_box.label(text="Path Settings:")
        path_box.prop(scene, "curve_name", text="Curve Name")
        path_box.label(text="Curve Type:")
        curve_row = path_box.row(align=True)
        curve_row.operator("object.select_curve_type", text="Bezier").curve_type = "BEZIER"
        curve_row.operator("object.select_curve_type", text="NURBS").curve_type = "NURBS"
        path_box.label(text=f"Current Selection: {scene.curve_type}")

        layout.separator()

        # Control points section
        points_box = layout.box()
        points_box.label(text="Control Points:")
        
        # Control points list
        row = points_box.row()
        row.template_list(
            "CONTROL_POINTS_UL_list", "", 
            scene, "control_points",
            scene, "active_control_point_index",
            rows=10
        )

        # Insertion controls in a sub-box
        insert_box = points_box.box()
        insert_box.label(text="Insert Control Points:")
        
        # Start insertion (top row)
        row = insert_box.row(align=True)
        row.operator("object.add_control_point", text="Insert at Start", icon='TRIA_UP_BAR').index = 0
        
        # Before/After selected point (middle row)
        if len(scene.control_points) > 0:
            current_index = scene.active_control_point_index
            row = insert_box.row(align=True)
            row.operator("object.add_control_point", text="Insert Before Selected", icon='TRIA_UP').index = current_index
            row.operator("object.add_control_point", text="Insert After Selected", icon='TRIA_DOWN').index = current_index + 1
        
        # End insertion (bottom row)
        row = insert_box.row(align=True)
        row.operator("object.add_control_point", text="Insert at End", icon='TRIA_DOWN_BAR').index = -1

        # Visibility controls
        vis_row = points_box.row(align=True)
        vis_row.operator("object.show_control_points", text="Show Points", icon='HIDE_OFF')
        vis_row.operator("object.hide_control_points", text="Hide Points", icon='HIDE_ON')

        layout.separator()

        # Generate curve
        layout.label(text="Generate Path:")
        gen_row = layout.row()
        gen_row.scale_y = 1.5
        gen_row.operator("object.generate_curve", text="Generate Curve", icon='CURVE_DATA')

def register():
    """Register all classes and properties with Blender"""
    classes = [
        ControlPointProperty,  # Register property group first
        CONTROL_POINTS_UL_list,
        OBJECT_OT_select_curve_type,
        OBJECT_OT_add_control_point,
        OBJECT_OT_remove_control_point,
        OBJECT_OT_move_control_point,
        OBJECT_OT_reorder_control_point,
        OBJECT_OT_generate_curve,
        OBJECT_OT_show_control_points,
        OBJECT_OT_hide_control_points,
        LayoutDemoPanel  # Register panel last
    ]
    
    for cls in classes:
        bpy.utils.register_class(cls)

    # Define scene properties
    bpy.types.Scene.curve_type = bpy.props.StringProperty(default="BEZIER")
    bpy.types.Scene.control_points = bpy.props.CollectionProperty(type=ControlPointProperty)
    bpy.types.Scene.active_control_point_index = bpy.props.IntProperty()
    bpy.types.Scene.curve_name = bpy.props.StringProperty(
        name="Curve Name",
        description="Name for the generated curve",
        default="GeneratedCurve"
    )

    # Create initial control point and collection
    if not bpy.context.scene.control_points:
        point = bpy.context.scene.control_points.add()
        point.x, point.y, point.z = 0.0, 0.0, 0.0
        point.sphere_name = "ControlPoint_0"

        if not bpy.data.collections.get("Control Points"):
            collection = bpy.data.collections.new("Control Points")
            bpy.context.scene.collection.children.link(collection)

    # Force a UI refresh
    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            area.tag_redraw()

def unregister():
    """Unregister all classes and properties"""
    # Remove properties first
    del bpy.types.Scene.curve_name
    del bpy.types.Scene.active_control_point_index
    del bpy.types.Scene.control_points
    del bpy.types.Scene.curve_type

    # Then unregister classes in reverse order
    classes = [
        LayoutDemoPanel,
        OBJECT_OT_hide_control_points,
        OBJECT_OT_show_control_points,
        OBJECT_OT_generate_curve,
        OBJECT_OT_reorder_control_point,
        OBJECT_OT_move_control_point,
        OBJECT_OT_remove_control_point,
        OBJECT_OT_add_control_point,
        OBJECT_OT_select_curve_type,
        CONTROL_POINTS_UL_list,
        ControlPointProperty
    ]
    
    for cls in classes:
        bpy.utils.unregister_class(cls)

if __name__ == "__main__":
    register()
message.txt
21 KB
