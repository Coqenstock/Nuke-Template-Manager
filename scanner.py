"""Deep-text scanning and dependency validation module.

This module is responsible for safely parsing Nuke script files (.nk) without 
using the heavy Nuke API (bypassing the application layer for performance). 
It utilizes Regex to identify node classes, detects missing OFX plugins, 
and checks for proprietary studio dependencies before import.
"""

import re
import os
from . import settings
from typing import TypedDict
NODE_FINDER: re.Pattern[str] = re.compile(r"^([ \t]*)([A-Z][A-Za-z0-9_\.]*)[ \t]*\{([^\n]*)$", re.MULTILINE)

def is_running_in_nuke():
    """Checks if the script is currently executing inside the Nuke application.

    Returns:
        bool: True if the `nuke` module is successfully imported and active.
    """
    try:
        import nuke
        return hasattr(nuke, "nodeTypes")
    except ImportError:
        return False


def list_nk_files(folder_path: str) -> list[str]:
    """Recursively searches a directory for Nuke script files.

    Args:
        folder_path (str): The absolute path of the root directory to search.

    Returns:
        list[str]: A list of absolute file paths to all discovered `.nk` files.
    """
    nk_files = []
    if os.path.isdir(folder_path):
        for root_folder, subfolders, files in os.walk(folder_path):
            for f in files:
                if f.lower().endswith(".nk"):
                    full_path = os.path.join(root_folder, f)
                    nk_files.append(full_path)
                    
    return nk_files


IGNORED_WORDS: set[str] = {"Root"}  # Variable qui contient le mot root

class Template(TypedDict):
    """A data structure representing a scanned Nuke template's metadata and health."""
    #: The display name of the template (filename without extension).
    name: str
    #: The absolute file path to the .nk file.
    path: str
    #: A list of plugins required by the template that are missing locally.
    missing_nodes: list[str]
    #: Traceback string if the file failed to read.
    errors: str | None
    #: The health status ("OK", "MISSING_NODES", "READ_ERROR").
    status: str | None
    #: True if the template contains proprietary Stamps nodes.
    is_stamps: bool | None
    #: Custom metadata tags assigned to this template.
    tags: list[str]

def scan_templates(
    folder_path: str, available_nodes: set[str], ignored_words: set[str] = IGNORED_WORDS
) -> list[Template]:
    """Parses .nk files as raw text to extract node dependencies safely.

    This function bypasses standard API evaluation to prevent pipeline crashes. 
    It checks for standard Nuke nodes, OFX plugins, and proprietary studio 
    tools (like "Stamps") by analyzing the file's text structure via Regex.

    Args:
        folder_path (str): The directory containing the templates to scan.
        available_nodes (set[str]): A master list of nodes currently installed on the user's machine.
        ignored_words (set[str], optional): Nodes to skip during parsing (e.g., "Root").

    Returns:
        list[Template]: A list of dictionary objects containing the parsed status of each template.
    """
    templates: list[Template] = []
    ofxnames = {x.lower().replace(" ", "") for x in available_nodes} # type: ignore
    metadata = settings.load_metadata()
    for path in list_nk_files(folder_path):  # Pour tous les éléments de NK_FILES
        filename: str = os.path.basename(path)  # nom de fichier.nk
        display_name: str = os.path.splitext(filename)[0]  # nom de fichier sans le .nk
        tags = metadata.get(filename, [])
        tpl: Template = {
            "name": display_name,
            "path": path,
            "missing_nodes": [],
            "errors": None,
            "status": None,
            "is_stamps": None,
            "tags": tags,
        }  # dans la liste y a le nom le chemin d'accès, si il y a des noeuds qui manquent ou si y a des erreurs genre si ça crash
        try:
            with open(
                path, "r", encoding="utf-8", errors="replace"
            ) as f:  # ouvrir fichier puis fermer quand c'est fini
                text = f.read()  # lire le text
            is_stamps = False
            if "import stamps" in text or "Anchor Stamp" in text or "Stamps by Adrian Pueyo" in text:
                is_stamps = True
            tpl["is_stamps"] = is_stamps
            found_matches: list[tuple[str, str, str]] = NODE_FINDER.findall(text)
            found: list[str] = []
            for indent, name, extra_text in found_matches:
                if indent == "":
                    if extra_text.strip() == "" or name.startswith("OFX"):
                        found.append(name)  # utiliser la fonction regex pour trouver les noms de noeuds
            found_unique: list[str] = sorted(
                set([s.strip() for s in found]) - ignored_words
            )  # enlever root 
            missing: list[str] = []
            for cls in found_unique:
                if cls in available_nodes:
                    continue
                base: str = cls
                while base and base[-1].isdigit():
                    base = base[:-1]
                if base in available_nodes:
                    continue
                if cls.startswith("OFX"):
                    core_name = cls.split('.')[-1].lower()
                    core_name = core_name.split('_')[0]
                    while core_name and core_name[-1].isdigit():
                        core_name = core_name[:-1]
                    if any(core_name in node for node in ofxnames):
                        continue 
                missing.append(cls)
            tpl["missing_nodes"] = sorted(
                missing
            )  # ajouter le noeuds manquant dans errors
        except Exception as e:
            tpl["errors"] = f"{type(e).__name__}: {e}"  # si ça merde
        if tpl["errors"]:
            tpl["status"] = "READ_ERROR"
        elif tpl["missing_nodes"]:
            tpl["status"] = "MISSING_NODES"
        else:
            tpl["status"] = "OK"
        templates.append(tpl)
    return templates

def get_available_nodes():
    """Generates a comprehensive list of all nodes available in the environment.

    Provides a massive hardcoded fallback list of default Nuke nodes. If executed 
    inside the active Nuke application, it dynamically augments this list by 
    scraping `nuke.nodeTypes()`, loaded `.gizmo`/`.dll` plugins, and custom menus.

    Returns:
        set[str]: A unique set of all node class names available to the artist.
    """
    available_nodes: set[str] = {'CameraTracker', 'Invert', 'F_Steadiness', 'Glow2', 'Crop', 'LayerContactSheet', 'ColorBars', 'SphericalTransform2', 'ZDefocus', 'GeoCube', 'C_CameraIngest2_1', 'ViewerGamma', 'EdgeScatter', 'GeoStageEdit', 'F_DeGrain', 'ReflectiveSurface', 'DegrainBlue', 'Bezier', 'FillMat', 'Inpaint2', 'FnNukeMultiTypeOpParticleOp', 'Spotlight', 'ColorMatrix', 'ApplyLUT', 'Keymix', 'IDistort', 'ViewerClipTest', 'RendermanShader', 'LiveInput', 'GeoDrawMode', 'IBKGizmo', 'GeoPoints', 'PointsTo3D', 'GeoUVProject', 'F_DeNoise', 'ChannelMerge', 'ChromaKeyer', 'Mirror2', 'StickyNote', 'Write', 'CheckerBoard', 'CameraShake2', 'BakedPointCloudMesh', 'DeepMerge', 'CornerPin2D', 'GeoReference', 'C_RayRender2_1', 'NoOp', 'ViewerScopeOp', 'IBKSFill', 'C_SphericalTransform2_1', 'GeoConstrain', 'GeomOpTester', 'Project3DShader', 'Transform3D', 'DropShadow', 'ContactSheet', 'EditGeo', 'ParticleBlinkScript', 'AddMix', 'add32p', 'DirBlur', 'ZFDefocus', 'BackdropNode', 'C_Blender2_1', 'GeoCard', 'GeoScopePrim', 'objReaderObj', 'PointCloudGenerator1_0', 'LensDistortion', 'PSDMerge', 'MultiTexture', 'BlackOutside', 'Twist', 'Axis3', 'ColorWheel', 'CameraTracker1_0', 'Normals', 'F_MotionBlur', 'C_STMap2_1', 'CameraTrackerPointCloud1_0', 'Switch', 'GeoCompare', 'Constant', 'GeoCollection', 'Modeler', 'ParticleLookAt', 'Merge2', 'Output', 'DepthGenerator', 'Read', 'StabTrack', 'Light', 'Grain', 'ZSlice', 'CurveTool', 'OCIOFileTransform', 'FnNukeMultiTypeOpGeomOp', 'ColorCorrect', 'BasicSurface', 'F_ReGrain', 'FloodFill', 'DeepWrite', 'FFT', 'IBKColour', 'PlanarTracker1_0', 'SimpleAxis', 'Black', 'SpotLight1', 'SideBySide', 'FromDeep', 'TextureFile', 'GeoSelect', 'LightWrap', 'ParticleSettings', 'AddTimeCode', 'MergeMat', 'Defocus', 'GeoRadialWarp', 'CameraTrackerPointCloud', 'UVTile2', 'BlendMat', 'Encryptomatte', 'PointCloudGenerator', 'RayRender', 'ZComp', 'GeoPointsToMesh', 'Anaglyph', 'AdjBBox', 'DiskCache', 'Cryptomatte', 'HueKeyer', 'VariableSwitch', 'CylinderObj', 'Sphere', 'PointLight', 'Fog', 'DeepDeOverlap', 'FnNukeMultiTypeOpDeepOp', 'Environment', 'ViewerProcess_1DLUT', 'DepthToPosition', 'Grain2', 'VectorGenerator', 'Bilateral2', 'Light2', 'DeepMerge2', 'MeshGeo', 'WireframeShader', 'Bilateral', 'PrimatteAdjustLighting', 'CopyBBox', 'CopyCat', 'BlinkFilterErode', 'RadialDistort', 'Mocha Pro', 'BlinkBlur', 'Checker', 'DeepHoldout2', 'Glow', 'PLogLin', 'ParticleEmitter', 'Emission', 'GeoBakedPointCloud', 'StarField', 'Tracker4', 'PrintHash', 'MindRead', 'GeoScene', 'VectorBlur', 'Dither', 'GridWarp3', 'Trilinear', 'ParticleProjectImage', 'BakedPointCloud', 'Erode', 'ParticleToGeo', 'C_ColourMatcher2_1', 'RolloffContrast', 'MakeLatLongMap', 'GeoMerge', 'ParticleConstrainToSphere', 'DeepTransform', 'FrameRange', 'DirBlurWrapper', 'ZMerge', 'PositionToPoints', 'ViewerDitherDisable', 'FrameHold', 'NoProxy', 'Soften', 'ViewMetaData', 'Cube', 'ConstantShader', 'Log2Lin', 'ParticleBlinkScriptRender', 'FrameBlend', 'DeepCompare', 'ColorLookup', 'PostageStamp', 'ParticleShockWave', 'ParticleDistributeSphere', 'GPUFileShader', 'Displacement', 'DeepChannelBlanker', 'SurfaceOptions', 'Unpremult', 'EnvironmentLight', 'ModelBuilderGeo', 'ParticleAttractToSphere', 'Gizmo', 'UnrealReader', 'DegrainSimple', 'BurnIn', 'Toe2', 'FilterErode', 'ModifyMetaData', 'OCIOLogConvert', 'Card2', 'EdgeDetectWrapper', 'Ultimatte', 'ZBlur', 'ShuffleCopy', 'VectorCornerPin', 'EdgeBlur', 'Dot', 'Retime', 'ParticleVortex', 'DeInterlace', 'ViewerLUT', 'GeoBakedPointCloudMesh', 'Ramp', 'Viewer', 'WriteGeo', 'C_Bilateral2_1', 'F_RigRemoval', 'AttribGeo', 'AddChannels', 'Inference', 'ToDeep', 'ViewerChannelSelector', 'Keyer', 'DeepClipZ', 'OpStatisticsOp', 'TimeClip', 'ParticleFlock', 'Preferences', 'TimeDissolve', 'F_DeFlicker2', 'VectorToMotion', 'DeepExpression', 'ParticleHelixFlow', 'Add', 'C_Tracker2_1', 'PythonGeo', 'Camera3', 'HSVTool', 'Reconcile3D', 'Convolve2', 'F_WireRemoval', 'MergeGeo', 'Camera4', 'DepthGenerator1_0', 'SoftClip', 'MarkerRemoval', 'Saturation', 'F_MatchGrade', 'Vectorfield', 'MotionBlur2D', 'OneView', 'BlinkScript', 'AddSTMap', 'PoissonMesh', 'OCIODisplay', 'AudioRead', 'PreviewSurface', 'TransformGeo', 'OCIOLookTransform', 'ParticleRender', 'Multiply', 'DustBust', 'ProcGeo', 'ParticleDirection', 'UVProject', 'EdgeExtend', 'CopyMetaData', 'DeepCrop', 'GeoPython', 'Text2', 'Camera2', 'SmartVector', 'EdgeDetect', 'ReLight', 'UnmultColor', 'Histogram', 'Input', 'PixelSum', 'F_Align', 'Convolve', 'Light4', 'ParticleProjectDisplace', 'ViewerGain', 'TimeBlur', 'BlockGPU', 'DeepRecolor', 'EXPTool', 'TimeToDepth', 'Compare', 'CCrosstalk', 'DisplaceGeo', 'Scene', 'ErrorIop', 'Dissolve', 'Roto', 'Keylight', 'Project3D', 'DeepSample', 'MotionBlur', 'Radial', 'ViewerCaptureOp', 'PositionToPoints2', 'Refraction', 'GeoCameraTrackerPoints1_0', 'DrawCursorShaderOp', 'GenerateLUTGeo', 'LensDistortion1_0', 'Transmission', 'Cylinder', 'NoTimeBlur', 'OCIOColorSpace', 'Primatte3', 'SphericalMap', 'ScannedGrain', 'OFlow2', 'GeoBakedPoints', 'ParticleCurve', 'IBKGizmoV3', 'ParticleColorByAge', 'AppendClip', 'TwistGeo', 'DepthToPoints', 'GeoDisplace', 'Noise', 'TextureSampler', 'Merge', 'GPUOp', 'ColorTransfer', 'Colorspace', 'DeepRead', 'ReadGeo2', 'TemporalMedian', 'ViewerDitherHighFrequency', 'ParticleGrid', 'GeoTwist', 'Premult', 'VectorBlur2', 'ViewerDitherLowFrequency', 'Axis2', 'GeoSelector', 'ViewerProcess_None', 'CatFileCreator', 'HueCorrect', 'Reflection', 'ParticleCache', 'ProjectionSolver1_0', 'ParticleMerge', 'Primatte', 'CheckerBoard2', 'Bokeh', 'F_Kronos', 'TextureMap', 'GeoNoise', 'GeoInstance', 'GenerateLUT', 'DualBlend', 'MotionBlur3D', 'VolumeRays', 'TimeBlend', 'C_CameraSolver2_1', 'C_Stitcher2_1', 'ApplyMaterial', 'BumpMat', 'MergeExpression', 'PointsGenerator', 'IT8_Reader', 'GeoSetVariant', 'ParticleDirectionalForce', 'ParticleSpawn', 'GeoIsolate', 'DeepHoldout', 'Assert', 'Upscale', 'GeoTransform', 'BasicMaterial', 'ParticleCylinderFlow', 'IBKSplit', 'SplineWarp2', 'SplineWarp', 'LevelSet', 'Camera', 'ParticleToImage', 'ZRMerge', 'IT8_Writer', 'Transform', 'NodeWrapper', 'Position', 'DirectLight1', 'Specular', 'InternalTimelineDefaultInput', 'GridWarp2', 'ParticleMove', 'Mirror', 'Axis', 'ReadGeo', 'BumpBoss', 'UpRez', 'GridWarpTracker', 'Inpaint', 'RotoPaint', 'Grid', 'Emboss', 'Difference', 'ParticleSpeedLimit', 'HistEQ', 'DeepColorCorrect2', 'ChannelSelector', 'Unwrap', 'CameraShake', 'DeepFromFrames', 'C_AlphaGenerator2_1', 'remove32p', 'GeoBindMaterial', 'Project3D2', 'InvFFT', 'Card', 'Modeler1_0', 'Paint', 'ModelBuilder', 'CMSTestPattern', 'Phong', 'ScanlineRender2', 'Shuffle2', 'ParticleDrag', 'FieldSelect', 'Laplacian', 'GeoNormals', 'Matrix', 'PrintMetaData', 'Text', 'GeoXformPrim', 'SphericalTransform', 'C_GlobalWarp2_1', 'Axis4', 'Light3', 'ParticleKill', 'GeoPrune', 'Group', 'Precomp', 'ParticleTurbulence', 'DeepVolumeMaker', 'ViewerInterlacedStereo', 'PixelStat', 'FnNukeMultiTypeOpIop', 'ParticleDrag2', 'Kronos', 'GeoCameraTrackerPoints', 'Diffuse', 'ParticleFuse', 'TimeOffset', 'Denoise2', 'C_DisparityGenerator2_1', 'PlanarTracker', 'ViewerWipe', 'GeoDuplicate', 'CameraShake3', 'Expression', 'Sparkles', 'CCorrect', 'ViewerSaturation', 'DeepColorCorrect', 'GeoViewScene', 'TransformMasked', 'ParticleGravity', 'Wireframe', 'LiveGroup', 'Deblur', 'IBK', 'GodRays', 'FishEye', 'DeepReformat', 'Shuffle1', 'FFTMultiply', 'STMap', 'VectorDistort', 'ZDefocus2', 'FillShader', 'SplineWarp3', 'Shuffle', 'Blocky', 'IBKEdge', 'CopyRectangle', 'Tile', 'C_Blur2_1', 'LookupGeo', 'Remove', 'DeepFromImage', 'ParticleInfo', 'Grade', 'GeoSphere', 'ParticleMotionAlign', 'AmbientOcclusion', 'DeepOmit', 'Gamma', 'Reformat', 'CrosstalkGeo', 'Blend', 'ParticleExpression', 'DeepClip', 'IBK2Gizmo', 'MinColor', 'ExecuteTreeMT', 'Tracker', 'DeepShift', 'Dilate', 'Sharpen', 'MergeLayerShader', 'Glint', 'CubeObj', 'CardObj', 'Sampler', 'DeepToImage', 'PanelNode', 'ParticlePointForce', 'Mocha VR (legacy)', 'TimeWarp', 'DirectLight', 'GeoExport', 'SphereToLatLongMap', 'TVIscale', 'ModifyRIB', 'ProjectionSolver', 'ScanlineRender', 'GeoTrilinearWarp', 'C_GenerateMap2_1', 'SphereObj', 'ParticleWind', 'GeoBakedMesh', 'GridWarp', 'DeepMask', 'JoinViews', 'Card3D', 'Median', 'ColorTransferWrapper', 'Profile', 'VariableGroup', 'TimeShift', 'ParticleBounce', 'LogGeo', 'PerspDistort', 'Tracker3', 'Flare', 'OCIONamedTransform', 'GeoScript', 'TimeEcho', 'LensDistortion2', 'MixViews', 'OCIOCDLTransform', 'DeepToPoints', 'FnNukeMultiTypeOpGeoOp', 'HueShift', 'Copy', 'Stabilize2D', 'DeepToImage2', 'ParticleSystem', 'MatchGrade', 'Clamp', 'Blur', 'IBKColourV3', 'F_VectorGenerator', 'Rectangle', 'ClipTest', 'ShuffleViews', 'CompareMetaData', 'ReConverge', 'Fill', 'GeoCylinder', 'GeoImport', 'Posterize'}
    if is_running_in_nuke():
        import nuke
        available_nodes.update(nuke.nodeTypes())
        plugin_files = nuke.plugins(nuke.ALL | nuke.NODIR, "*.gizmo", "*.so", "*.dylib", "*.dll")
        for p in plugin_files:
            clean_name = os.path.splitext(p)[0]
            available_nodes.add(clean_name)
        def get_all_menu_items(menu):
            items = set()
            for item in menu.items():
                if isinstance(item, nuke.Menu):
                    items.update(get_all_menu_items(item))
                elif isinstance(item, nuke.MenuItem):
                    items.add(item.name())
            return items
        available_nodes.update(get_all_menu_items(nuke.menu("Nodes")))
    available_nodes = set(n.strip() for n in available_nodes)
    return available_nodes

def paste_template(tpl: Template) -> None:
    """Executes the Nuke API command to paste the selected template into the DAG.

    Args:
        tpl (Template): The template dictionary object containing the absolute path.
    """
    import os
    nk_path: str = tpl["path"]
    if not os.path.isfile(nk_path):
        print("ERR - file not found:", nk_path)
        return

    try:
        import nuke
    except ImportError:
        print("Not in Nuke - would paste:", nk_path)
        return

    nuke.nodePaste(nk_path) # type: ignore
