"""Deep-text scanning and dependency validation module.

This module is responsible for safely parsing Nuke script files (``.nk``)
without using the heavy Nuke API. By bypassing the application layer it
can scan thousands of files in seconds, even outside a running Nuke
session, and is therefore safe to call before any Nuke import or paste
operation has been attempted.

The parser uses a single compiled regular expression to identify node
class declarations in the raw text. It cross-references those classes
against a baseline of vanilla Nuke nodes (:data:`CORE_NODES`) to detect
missing OFX plugins and proprietary studio gizmos, and extracts project
settings (FPS, resolution, colour management) from the ``Root`` block
when present.

Attributes:
    NODE_FINDER (re.Pattern): Compiled regular expression matching node
        class declarations at the start of a line, capturing the leading
        indentation, the class name, and any trailing text on the
        opening brace line. Top-level (un-indented) matches are treated
        as real nodes; indented matches are usually nested entries
        inside groups and are ignored by the default scanner pass.
    CORE_NODES (set[str]): The complete set of node class names shipped
        with vanilla Nuke. Any class found in a ``.nk`` file that is not
        present in this set, in :func:`get_available_nodes`'s output,
        and does not strip down to a known base by trailing-digit removal
        is reported as a missing dependency.
    IGNORED_WORDS (set[str]): Tokens the scanner should never treat as
        node classes even though they match the syntactic pattern. The
        ``Root`` block in particular looks like a node declaration but
        contains project settings rather than a node.
    TemplateStatus: A :data:`~typing.Literal` of the four status strings
        a :class:`Template` entry may carry: ``"OK"``,
        ``"MISSING_NODES"``, ``"READ_ERROR"``, ``"FILE_TOO_LARGE"``.
"""

import io
import os
import re
from typing import List, Optional, Set, Tuple

try:
    from typing import Literal, TypedDict
except ImportError:
    from typing_extensions import Literal, TypedDict

from . import saves
from .settings import (
    DEFAULT_PROJECT_FPS,
    DEFAULT_PROJECT_RESOLUTION,
    DEFAULT_PROJECT_COLORSPACE,
    MAX_FILE_SIZE_BYTES,
)

NODE_FINDER = re.compile(
    r"^([ \t]*)([A-Z][A-Za-z0-9_\.]*)[ \t]*\{([^\n]*)$",
    re.MULTILINE,
)
CORE_NODES = {'CameraTracker', 'Invert', 'F_Steadiness', 'Glow2', 'Crop', 'LayerContactSheet', 'ColorBars', 'SphericalTransform2', 'ZDefocus', 'GeoCube', 'C_CameraIngest2_1', 'ViewerGamma', 'EdgeScatter', 'GeoStageEdit', 'F_DeGrain', 'ReflectiveSurface', 'DegrainBlue', 'Bezier', 'FillMat', 'Inpaint2', 'FnNukeMultiTypeOpParticleOp', 'Spotlight', 'ColorMatrix', 'ApplyLUT', 'Keymix', 'IDistort', 'ViewerClipTest', 'RendermanShader', 'LiveInput', 'GeoDrawMode', 'IBKGizmo', 'GeoPoints', 'PointsTo3D', 'GeoUVProject', 'F_DeNoise', 'ChannelMerge', 'ChromaKeyer', 'Mirror2', 'StickyNote', 'Write', 'CheckerBoard', 'CameraShake2', 'BakedPointCloudMesh', 'DeepMerge', 'CornerPin2D', 'GeoReference', 'C_RayRender2_1', 'NoOp', 'ViewerScopeOp', 'IBKSFill', 'C_SphericalTransform2_1', 'GeoConstrain', 'GeomOpTester', 'Project3DShader', 'Transform3D', 'DropShadow', 'ContactSheet', 'EditGeo', 'ParticleBlinkScript', 'AddMix', 'add32p', 'DirBlur', 'ZFDefocus', 'BackdropNode', 'C_Blender2_1', 'GeoCard', 'GeoScopePrim', 'objReaderObj', 'PointCloudGenerator1_0', 'LensDistortion', 'PSDMerge', 'MultiTexture', 'BlackOutside', 'Twist', 'Axis3', 'ColorWheel', 'CameraTracker1_0', 'Normals', 'F_MotionBlur', 'C_STMap2_1', 'CameraTrackerPointCloud1_0', 'Switch', 'GeoCompare', 'Constant', 'GeoCollection', 'Modeler', 'ParticleLookAt', 'Merge2', 'Output', 'DepthGenerator', 'Read', 'StabTrack', 'Light', 'Grain', 'ZSlice', 'CurveTool', 'OCIOFileTransform', 'FnNukeMultiTypeOpGeomOp', 'ColorCorrect', 'BasicSurface', 'F_ReGrain', 'FloodFill', 'DeepWrite', 'FFT', 'IBKColour', 'PlanarTracker1_0', 'SimpleAxis', 'Black', 'SpotLight1', 'SideBySide', 'FromDeep', 'TextureFile', 'GeoSelect', 'LightWrap', 'ParticleSettings', 'AddTimeCode', 'MergeMat', 'Defocus', 'GeoRadialWarp', 'CameraTrackerPointCloud', 'UVTile2', 'BlendMat', 'Encryptomatte', 'PointCloudGenerator', 'RayRender', 'ZComp', 'GeoPointsToMesh', 'Anaglyph', 'AdjBBox', 'DiskCache', 'Cryptomatte', 'HueKeyer', 'VariableSwitch', 'CylinderObj', 'Sphere', 'PointLight', 'Fog', 'DeepDeOverlap', 'FnNukeMultiTypeOpDeepOp', 'Environment', 'ViewerProcess_1DLUT', 'DepthToPosition', 'Grain2', 'VectorGenerator', 'Bilateral2', 'Light2', 'DeepMerge2', 'MeshGeo', 'WireframeShader', 'Bilateral', 'PrimatteAdjustLighting', 'CopyBBox', 'CopyCat', 'BlinkFilterErode', 'RadialDistort', 'Mocha Pro', 'BlinkBlur', 'Checker', 'DeepHoldout2', 'Glow', 'PLogLin', 'ParticleEmitter', 'Emission', 'GeoBakedPointCloud', 'StarField', 'Tracker4', 'PrintHash', 'MindRead', 'GeoScene', 'VectorBlur', 'Dither', 'GridWarp3', 'Trilinear', 'ParticleProjectImage', 'BakedPointCloud', 'Erode', 'ParticleToGeo', 'C_ColourMatcher2_1', 'RolloffContrast', 'MakeLatLongMap', 'GeoMerge', 'ParticleConstrainToSphere', 'DeepTransform', 'FrameRange', 'DirBlurWrapper', 'ZMerge', 'PositionToPoints', 'ViewerDitherDisable', 'FrameHold', 'NoProxy', 'Soften', 'ViewMetaData', 'Cube', 'ConstantShader', 'Log2Lin', 'ParticleBlinkScriptRender', 'FrameBlend', 'DeepCompare', 'ColorLookup', 'PostageStamp', 'ParticleShockWave', 'ParticleDistributeSphere', 'GPUFileShader', 'Displacement', 'DeepChannelBlanker', 'SurfaceOptions', 'Unpremult', 'EnvironmentLight', 'ModelBuilderGeo', 'ParticleAttractToSphere', 'Gizmo', 'UnrealReader', 'DegrainSimple', 'BurnIn', 'Toe2', 'FilterErode', 'ModifyMetaData', 'OCIOLogConvert', 'Card2', 'EdgeDetectWrapper', 'Ultimatte', 'ZBlur', 'ShuffleCopy', 'VectorCornerPin', 'EdgeBlur', 'Dot', 'Retime', 'ParticleVortex', 'DeInterlace', 'ViewerLUT', 'GeoBakedPointCloudMesh', 'Ramp', 'Viewer', 'WriteGeo', 'C_Bilateral2_1', 'F_RigRemoval', 'AttribGeo', 'AddChannels', 'Inference', 'ToDeep', 'ViewerChannelSelector', 'Keyer', 'DeepClipZ', 'OpStatisticsOp', 'TimeClip', 'ParticleFlock', 'Preferences', 'TimeDissolve', 'F_DeFlicker2', 'VectorToMotion', 'DeepExpression', 'ParticleHelixFlow', 'Add', 'C_Tracker2_1', 'PythonGeo', 'Camera3', 'HSVTool', 'Reconcile3D', 'Convolve2', 'F_WireRemoval', 'MergeGeo', 'Camera4', 'DepthGenerator1_0', 'SoftClip', 'MarkerRemoval', 'Saturation', 'F_MatchGrade', 'Vectorfield', 'MotionBlur2D', 'OneView', 'BlinkScript', 'AddSTMap', 'PoissonMesh', 'OCIODisplay', 'AudioRead', 'PreviewSurface', 'TransformGeo', 'OCIOLookTransform', 'ParticleRender', 'Multiply', 'DustBust', 'ProcGeo', 'ParticleDirection', 'UVProject', 'EdgeExtend', 'CopyMetaData', 'DeepCrop', 'GeoPython', 'Text2', 'Camera2', 'SmartVector', 'EdgeDetect', 'ReLight', 'UnmultColor', 'Histogram', 'Input', 'PixelSum', 'F_Align', 'Convolve', 'Light4', 'ParticleProjectDisplace', 'ViewerGain', 'TimeBlur', 'BlockGPU', 'DeepRecolor', 'EXPTool', 'TimeToDepth', 'Compare', 'CCrosstalk', 'DisplaceGeo', 'Scene', 'ErrorIop', 'Dissolve', 'Roto', 'Keylight', 'Project3D', 'DeepSample', 'MotionBlur', 'Radial', 'ViewerCaptureOp', 'PositionToPoints2', 'Refraction', 'GeoCameraTrackerPoints1_0', 'DrawCursorShaderOp', 'GenerateLUTGeo', 'LensDistortion1_0', 'Transmission', 'Cylinder', 'NoTimeBlur', 'OCIOColorSpace', 'Primatte3', 'SphericalMap', 'ScannedGrain', 'OFlow2', 'GeoBakedPoints', 'ParticleCurve', 'IBKGizmoV3', 'ParticleColorByAge', 'AppendClip', 'TwistGeo', 'DepthToPoints', 'GeoDisplace', 'Noise', 'TextureSampler', 'Merge', 'GPUOp', 'ColorTransfer', 'Colorspace', 'DeepRead', 'ReadGeo2', 'TemporalMedian', 'ViewerDitherHighFrequency', 'ParticleGrid', 'GeoTwist', 'Premult', 'VectorBlur2', 'ViewerDitherLowFrequency', 'Axis2', 'GeoSelector', 'ViewerProcess_None', 'CatFileCreator', 'HueCorrect', 'Reflection', 'ParticleCache', 'ProjectionSolver1_0', 'ParticleMerge', 'Primatte', 'CheckerBoard2', 'Bokeh', 'F_Kronos', 'TextureMap', 'GeoNoise', 'GeoInstance', 'GenerateLUT', 'DualBlend', 'MotionBlur3D', 'VolumeRays', 'TimeBlend', 'C_CameraSolver2_1', 'C_Stitcher2_1', 'ApplyMaterial', 'BumpMat', 'MergeExpression', 'PointsGenerator', 'IT8_Reader', 'GeoSetVariant', 'ParticleDirectionalForce', 'ParticleSpawn', 'GeoIsolate', 'DeepHoldout', 'Assert', 'Upscale', 'GeoTransform', 'BasicMaterial', 'ParticleCylinderFlow', 'IBKSplit', 'SplineWarp2', 'SplineWarp', 'LevelSet', 'Camera', 'ParticleToImage', 'ZRMerge', 'IT8_Writer', 'Transform', 'NodeWrapper', 'Position', 'DirectLight1', 'Specular', 'InternalTimelineDefaultInput', 'GridWarp2', 'ParticleMove', 'Mirror', 'Axis', 'ReadGeo', 'BumpBoss', 'UpRez', 'GridWarpTracker', 'Inpaint', 'RotoPaint', 'Grid', 'Emboss', 'Difference', 'ParticleSpeedLimit', 'HistEQ', 'DeepColorCorrect2', 'ChannelSelector', 'Unwrap', 'CameraShake', 'DeepFromFrames', 'C_AlphaGenerator2_1', 'remove32p', 'GeoBindMaterial', 'Project3D2', 'InvFFT', 'Card', 'Modeler1_0', 'Paint', 'ModelBuilder', 'CMSTestPattern', 'Phong', 'ScanlineRender2', 'Shuffle2', 'ParticleDrag', 'FieldSelect', 'Laplacian', 'GeoNormals', 'Matrix', 'PrintMetaData', 'Text', 'GeoXformPrim', 'SphericalTransform', 'C_GlobalWarp2_1', 'Axis4', 'Light3', 'ParticleKill', 'GeoPrune', 'Group', 'Precomp', 'ParticleTurbulence', 'DeepVolumeMaker', 'ViewerInterlacedStereo', 'PixelStat', 'FnNukeMultiTypeOpIop', 'ParticleDrag2', 'Kronos', 'GeoCameraTrackerPoints', 'Diffuse', 'ParticleFuse', 'TimeOffset', 'Denoise2', 'C_DisparityGenerator2_1', 'PlanarTracker', 'ViewerWipe', 'GeoDuplicate', 'CameraShake3', 'Expression', 'Sparkles', 'CCorrect', 'ViewerSaturation', 'DeepColorCorrect', 'GeoViewScene', 'TransformMasked', 'ParticleGravity', 'Wireframe', 'LiveGroup', 'Deblur', 'IBK', 'GodRays', 'FishEye', 'DeepReformat', 'Shuffle1', 'FFTMultiply', 'STMap', 'VectorDistort', 'ZDefocus2', 'FillShader', 'SplineWarp3', 'Shuffle', 'Blocky', 'IBKEdge', 'CopyRectangle', 'Tile', 'C_Blur2_1', 'LookupGeo', 'Remove', 'DeepFromImage', 'ParticleInfo', 'Grade', 'GeoSphere', 'ParticleMotionAlign', 'AmbientOcclusion', 'DeepOmit', 'Gamma', 'Reformat', 'CrosstalkGeo', 'Blend', 'ParticleExpression', 'DeepClip', 'IBK2Gizmo', 'MinColor', 'ExecuteTreeMT', 'Tracker', 'DeepShift', 'Dilate', 'Sharpen', 'MergeLayerShader', 'Glint', 'CubeObj', 'CardObj', 'Sampler', 'DeepToImage', 'PanelNode', 'ParticlePointForce', 'Mocha VR (legacy)', 'TimeWarp', 'DirectLight', 'GeoExport', 'SphereToLatLongMap', 'TVIscale', 'ModifyRIB', 'ProjectionSolver', 'ScanlineRender', 'GeoTrilinearWarp', 'C_GenerateMap2_1', 'SphereObj', 'ParticleWind', 'GeoBakedMesh', 'GridWarp', 'DeepMask', 'JoinViews', 'Card3D', 'Median', 'ColorTransferWrapper', 'Profile', 'VariableGroup', 'TimeShift', 'ParticleBounce', 'LogGeo', 'PerspDistort', 'Tracker3', 'Flare', 'OCIONamedTransform', 'GeoScript', 'TimeEcho', 'LensDistortion2', 'MixViews', 'OCIOCDLTransform', 'DeepToPoints', 'FnNukeMultiTypeOpGeoOp', 'HueShift', 'Copy', 'Stabilize2D', 'DeepToImage2', 'ParticleSystem', 'MatchGrade', 'Clamp', 'Blur', 'IBKColourV3', 'F_VectorGenerator', 'Rectangle', 'ClipTest', 'ShuffleViews', 'CompareMetaData', 'ReConverge', 'Fill', 'GeoCylinder', 'GeoImport', 'Posterize'}
TemplateStatus = Literal["OK", "MISSING_NODES", "READ_ERROR", "FILE_TOO_LARGE"]


def is_running_in_nuke() -> bool:
    """Detect whether the current Python process is hosted by Nuke.

    The check imports the ``nuke`` module and verifies that the
    ``nodeTypes`` attribute exists, which is only true inside a real
    Nuke session. The standalone ``nuke`` PyPI shim, if installed in a
    venv for development, lacks this attribute and is correctly
    rejected.

    Returns:
        bool: ``True`` if the script is running inside a live Nuke
        application instance, ``False`` if the import fails or the
        imported module does not expose the Nuke API.
    """
    try:
        import nuke
        return hasattr(nuke, "nodeTypes")
    except ImportError:
        return False


def list_nk_files(folder_path: str) -> List[str]:
    """Recursively enumerate every ``.nk`` file beneath a directory.

    The walk uses :func:`os.walk`, so symlinked directories are followed
    according to the platform default. Filename matching is
    case-insensitive on the ``.nk`` extension, allowing files like
    ``Template.NK`` to be found on case-sensitive filesystems.

    Args:
        folder_path: Absolute path of the directory to search. If the
            path does not exist or is not a directory the function
            returns an empty list rather than raising.

    Returns:
        list[str]: Absolute paths of every ``.nk`` file discovered. The
        order matches the traversal order of :func:`os.walk` and is not
        explicitly sorted.
    """
    nk_files = []
    if os.path.isdir(folder_path):
        for root_folder, subfolders, files in os.walk(folder_path):
            for f in files:
                if f.lower().endswith(".nk"):
                    full_path = os.path.join(root_folder, f)
                    nk_files.append(full_path)
    return nk_files


IGNORED_WORDS: Set[str] = {"Root"}


class Template(TypedDict):
    """Typed dictionary describing one scanned template entry.

    The keys mirror the fields stored in the scanner cache and consumed
    by the UI. Every value is populated by :func:`scan_templates`,
    although several may be ``None`` when the file could not be parsed
    or when the template is project-agnostic.

    Attributes:
        name: Display name of the template, derived from the filename
            with the ``.nk`` extension stripped.
        path: Absolute path to the source ``.nk`` file.
        missing_nodes: Sorted list of node class names referenced by the
            template that are not present in the user's current Nuke
            environment. Empty when the template is fully resolvable.
        errors: Free-form error string when parsing failed, otherwise
            ``None``.
        status: One of the strings declared by :data:`TemplateStatus`.
            ``"OK"`` indicates a healthy template, ``"MISSING_NODES"``
            that one or more plugins are absent, ``"READ_ERROR"`` that
            the file could not be parsed, and ``"FILE_TOO_LARGE"`` that
            the file exceeded :data:`settings.MAX_FILE_SIZE_BYTES`.
        is_stamps: ``True`` if the template appears to depend on the
            Stamps plugin by Adrian Pueyo, detected via signature
            strings in the file.
        has_gizmos: ``True`` if any node class in the template falls
            outside :data:`CORE_NODES`, indicating a dependency on
            external gizmos or third-party plugins.
        tags: Tag strings associated with the template, merged from
            manual user metadata and the auto-tag rule engine.
        fps: Frames-per-second declared by the template's ``Root``
            block, or ``None`` for project-agnostic templates.
        resolution: ``(width, height)`` declared by the template's
            ``Root`` block, or ``None`` for project-agnostic templates.
        colorspace: Colour-management value declared by the template's
            ``Root`` block, or ``None`` for project-agnostic templates.
        project_settings_mode: Either ``"ROOT_SETTINGS"`` when project
            settings were extracted from a ``Root`` block, or
            ``"AGNOSTIC"`` when the template carries no ``Root`` block.
    """
    name: str
    path: str
    missing_nodes: List[str]
    errors: Optional[str]
    status: Optional[TemplateStatus]
    is_stamps: Optional[bool]
    has_gizmos: Optional[bool]
    tags: List[str]
    fps: Optional[float]
    resolution: Optional[Tuple[int, int]]
    colorspace: Optional[str]
    project_settings_mode: Optional[str]


def extract_root_block(text: str) -> Optional[str]:
    """Return the inner contents of a Nuke script's ``Root { ... }`` block.

    The function walks the text after the opening ``Root {`` looking for
    the matching closing brace, tracking nesting depth so braces inside
    expression knobs or string values do not terminate the block early.
    Only the body between the outermost braces is returned; the
    enclosing ``Root { ... }`` delimiters themselves are omitted.

    Args:
        text: Raw contents of a ``.nk`` file as a single string.

    Returns:
        str | None: The body of the ``Root`` block if one is present,
        or ``None`` for project-agnostic templates that contain no
        ``Root`` declaration.
    """
    match = re.search(r"^Root\s*\{", text, re.MULTILINE)
    if not match:
        return None
    start = match.end()
    depth = 1
    i = start
    while i < len(text):
        char = text[i]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start:i]
        i += 1
    return None


def extract_project_settings_from_root(text: str) -> Tuple[Optional[float], Optional[Tuple[int, int]], Optional[str], str]:
    """Parse project settings from a Nuke script's ``Root`` block.

    The function delegates to :func:`extract_root_block` to isolate the
    body of the ``Root`` declaration, then applies focused regexes to
    pull out the frame rate, resolution, and colour-management
    configuration. Missing fields fall back to the module-level defaults
    (:data:`~settings.DEFAULT_PROJECT_FPS`,
    :data:`~settings.DEFAULT_PROJECT_RESOLUTION`,
    :data:`~settings.DEFAULT_PROJECT_COLORSPACE`) rather than being
    reported as ``None``, so a partial ``Root`` block is treated as a
    valid project-settings template.

    The ``OCIO_config`` knob takes precedence over ``colorManagement``
    when both are present, mirroring Nuke's own evaluation order when a
    template is loaded.

    Args:
        text: Raw contents of a ``.nk`` file as a single string.

    Returns:
        tuple: A 4-tuple ``(fps, resolution, colorspace, mode)`` where:

        * ``fps`` is a float or ``None`` (only ``None`` when no ``Root``
          block exists),
        * ``resolution`` is a ``(width, height)`` tuple or ``None``,
        * ``colorspace`` is a string or ``None``,
        * ``mode`` is the string ``"ROOT_SETTINGS"`` when settings came
          from a ``Root`` block, or ``"AGNOSTIC"`` otherwise.
    """
    root_text = extract_root_block(text)
    if root_text is None:
        return None, None, None, "AGNOSTIC"

    fps_match = re.search(r"^\s*fps\s+([0-9.]+)", root_text, re.MULTILINE)
    fps_val = float(fps_match.group(1)) if fps_match else DEFAULT_PROJECT_FPS

    resolution_val: Optional[Tuple[int, int]] = DEFAULT_PROJECT_RESOLUTION
    format_match = re.search(r'^\s*format\s+"?(\d+)\s+(\d+)', root_text, re.MULTILINE)
    if format_match:
        resolution_val = (int(format_match.group(1)), int(format_match.group(2)))

    ocio_match = re.search(r"^\s*OCIO_config\s+(.+)", root_text, re.MULTILINE)
    color_match = re.search(r"^\s*colorManagement\s+(.+)", root_text, re.MULTILINE)

    if ocio_match:
        colorspace_val = ocio_match.group(1).strip().strip('"')
    elif color_match:
        colorspace_val = color_match.group(1).strip().strip('"')
    else:
        colorspace_val = DEFAULT_PROJECT_COLORSPACE

    return fps_val, resolution_val, colorspace_val, "ROOT_SETTINGS"


def _extract_root_metadata(text: str) -> Tuple[Optional[float], Optional[Tuple[int, int]], Optional[str], str]:
    """Backwards-compatible alias for :func:`extract_project_settings_from_root`.

    Retained as a thin wrapper to avoid breaking any external callers
    that imported the private name during earlier development. New code
    should call :func:`extract_project_settings_from_root` directly.

    Args:
        text: Raw contents of a ``.nk`` file as a single string.

    Returns:
        tuple: The same 4-tuple returned by
        :func:`extract_project_settings_from_root`.
    """
    return extract_project_settings_from_root(text)


def get_auto_tags(node_list: List[str]) -> List[str]:
    """Evaluate the auto-tag rule engine against a list of node classes.

    Loads the current rule set from disk via
    :func:`saves.load_auto_tag_rules` and applies each rule in turn. A
    rule attaches its tag name to the result if its match condition is
    satisfied. Three rule types are supported:

    * ``"any"`` — the tag applies if any of the rule's target
      substrings appears inside any node class name (case-insensitive).
    * ``"all"`` — the tag applies only if every one of the rule's
      target substrings appears inside at least one node class name.
    * ``"count"`` — the tag applies when the number of nodes that
      contain any of the rule's target substrings reaches or exceeds
      the rule's ``threshold`` value (default ``5``). Each node is
      counted at most once even if it matches several targets.

    All comparisons are performed in lowercase, so rule authors should
    use lowercase target substrings.

    Args:
        node_list: List of node class names harvested from a single
            template by the scanner pass. Need not be unique.

    Returns:
        list[str]: The tags whose rules matched, in arbitrary order.
        An empty list is returned when no rule matches.
    """
    rules = saves.load_auto_tag_rules()
    tags = set()
    node_lower_list = [n.lower() for n in node_list]

    for tag_name, rule in rules.items():
        rule_type = rule.get("type", "any")
        target_nodes = [n.lower() for n in rule.get("nodes", [])]

        if rule_type == "any":
            for t in target_nodes:
                if any(t in n for n in node_lower_list):
                    tags.add(tag_name)
                    break

        elif rule_type == "all":
            all_found = True
            for t in target_nodes:
                if not any(t in n for n in node_lower_list):
                    all_found = False
                    break
            if all_found:
                tags.add(tag_name)

        elif rule_type == "count":
            threshold = rule.get("threshold", 5)
            count = sum(1 for n in node_lower_list if any(t in n for t in target_nodes))
            if count >= threshold:
                tags.add(tag_name)

    return list(tags)


def scan_templates(folder_path: str, available_nodes: Set[str], ignored_words: Set[str] = IGNORED_WORDS) -> List[Template]:
    """Parse every ``.nk`` file under a directory and build template records.

    This is the core scanner entry point. For each ``.nk`` file found
    beneath ``folder_path`` the function:

    1. Reads file size and modification time and skips files that
       exceed :data:`settings.MAX_FILE_SIZE_BYTES`, marking them with
       the ``"FILE_TOO_LARGE"`` status.
    2. Consults the on-disk cache via :func:`saves.load_cache` and
       reuses the cached parse result when the file's modification
       time matches; otherwise re-parses the file from scratch and
       updates the cache.
    3. Extracts project settings from the ``Root`` block when present,
       falling back to ``"AGNOSTIC"`` mode for templates without one.
    4. Detects Stamps plugin usage via signature string matching.
    5. Identifies missing nodes by comparing the parsed class names
       against ``available_nodes`` and :data:`CORE_NODES`, with a
       trailing-digit-stripping heuristic to fold versioned node
       names (for example ``Tracker4`` resolving to ``Tracker``).
    6. Merges manual user tags from :func:`saves.load_metadata` with
       auto-tags from :func:`get_auto_tags` for templates that have
       never been hand-tagged. Manual tags always take precedence
       once they exist.
    7. Bypasses standard Nuke API evaluation entirely, so malformed
       or untrusted scripts cannot crash the host process during
       scanning.

    Any exception raised during parsing is captured into the
    template's ``errors`` field, the status is set to ``"READ_ERROR"``,
    and the scan continues with the next file.

    Args:
        folder_path: Absolute path of the directory tree to scan.
            Non-existent paths simply yield an empty result list.
        available_nodes: Set of node class names known to the current
            Nuke environment, typically the return value of
            :func:`get_available_nodes`. Used to flag missing
            dependencies.
        ignored_words: Tokens that match the node syntax but should
            not be treated as real nodes (typically just
            :data:`IGNORED_WORDS`).

    Returns:
        list[Template]: One :class:`Template` record per ``.nk`` file
        discovered, populated with parsed metadata and a final status.
        Caller may sort or filter the list freely; the scanner makes
        no ordering guarantee.
    """
    templates: List[Template] = []
    metadata = saves.load_metadata()
    cache = saves.load_cache()
    cache_updated = False

    for path in list_nk_files(folder_path):
        filename = os.path.basename(path)
        display_name = os.path.splitext(filename)[0]
        user_tags = metadata.get(filename, [])

        tpl: Template = {
            "name": display_name,
            "path": path,
            "missing_nodes": [],
            "errors": None,
            "status": None,
            "is_stamps": None,
            "has_gizmos": None,
            "tags": user_tags,
            "fps": None,
            "resolution": None,
            "colorspace": None,
            "project_settings_mode": "AGNOSTIC",
        }

        try:
            file_size = os.path.getsize(path)
            file_mtime = os.path.getmtime(path)

            if file_size > MAX_FILE_SIZE_BYTES:
                tpl["status"] = "FILE_TOO_LARGE"
                tpl["errors"] = "File exceeds limit."
                tpl["is_stamps"] = False
                tpl["has_gizmos"] = False
                templates.append(tpl)
                continue

            cached = cache.get(path)

            if cached and cached.get("mtime") == file_mtime:
                found_unique = cached.get("found_unique", [])
                found = cached.get("found", [])
                tpl["is_stamps"] = cached.get("is_stamps", False)
                tpl["has_gizmos"] = cached.get("has_gizmos", False)
                tpl["errors"] = cached.get("errors")
                tpl["fps"] = cached.get("fps")
                tpl["resolution"] = tuple(cached["resolution"]) if cached.get("resolution") else None
                tpl["colorspace"] = cached.get("colorspace")
                tpl["project_settings_mode"] = cached.get("project_settings_mode", "AGNOSTIC")
            else:
                with io.open(path, "r", encoding="utf-8", errors="replace") as f:
                    text = f.read()

                fps_val, resolution_val, color_val, project_settings_mode = extract_project_settings_from_root(text)
                tpl["fps"] = fps_val
                tpl["resolution"] = resolution_val
                tpl["colorspace"] = color_val
                tpl["project_settings_mode"] = project_settings_mode

                tpl["is_stamps"] = ("import stamps" in text or "Anchor Stamp" in text or "Stamps by Adrian Pueyo" in text)

                found_matches = NODE_FINDER.findall(text)
                found = [name for indent, name, extra in found_matches if indent == "" and (extra.strip() == "" or name.startswith("OFX"))]
                found_unique = sorted({s.strip() for s in found} - ignored_words)
                has_gizmos_flag = False
                for node_class in found_unique:
                    base_class = node_class.rstrip('0123456789')
                    if node_class not in CORE_NODES and base_class not in CORE_NODES:
                        has_gizmos_flag = True
                        break

                tpl["has_gizmos"] = has_gizmos_flag

                cache[path] = {
                    "mtime": file_mtime,
                    "found": found,
                    "found_unique": found_unique,
                    "is_stamps": tpl["is_stamps"],
                    "has_gizmos": tpl["has_gizmos"],
                    "errors": None,
                    "fps": tpl["fps"],
                    "resolution": list(tpl["resolution"]) if tpl["resolution"] else None,
                    "colorspace": tpl["colorspace"],
                    "project_settings_mode": tpl["project_settings_mode"],
                }
                cache_updated = True

            missing = []
            for cls in found_unique:
                if cls in available_nodes:
                    continue
                base = cls
                while base and base[-1].isdigit():
                    base = base[:-1]
                if base in available_nodes:
                    continue
                missing.append(cls)

            tpl["missing_nodes"] = sorted(missing)

            if filename not in metadata:
                auto_tags = get_auto_tags(found)
                merged_tags = sorted(list(set(user_tags + auto_tags)))
                tpl["tags"] = merged_tags
                metadata[filename] = merged_tags
                saves.save_metadata(filename, merged_tags)
            else:
                tpl["tags"] = user_tags

        except Exception as e:
            tpl["errors"] = f"{type(e).__name__}: {e}"
            if path in cache:
                cache[path]["errors"] = tpl["errors"]
                cache_updated = True

        if tpl["errors"]:
            tpl["status"] = "READ_ERROR"
        elif tpl["missing_nodes"]:
            tpl["status"] = "MISSING_NODES"
        else:
            tpl["status"] = "OK"

        templates.append(tpl)

    if cache_updated:
        saves.save_cache(cache)

    return templates


def get_available_nodes() -> Set[str]:
    """Build the set of node class names the current Nuke session can create.

    When running inside Nuke the function combines four sources of
    truth to produce as complete a picture as possible:

    1. :data:`CORE_NODES` — the vanilla Nuke baseline shipped with the
       application.
    2. ``nuke.nodeTypes()`` — the live list of registered node classes,
       including any loaded via the application's own startup logic.
    3. ``nuke.plugins(...)`` filtered to ``.gizmo``, ``.so``, ``.dylib``
       and ``.dll`` extensions, with the extension stripped to recover
       the bare class name.
    4. Every menu item under ``nuke.menu("Nodes")``, recursively walked
       and parsed with a regex for ``createNode``/``createNodeLocal``
       calls. This catches gizmos that are exposed only through custom
       menus.

    When running outside Nuke the function returns just
    :data:`CORE_NODES`, which is sufficient for offline scanning and
    development workflows. The returned set is stripped of incidental
    whitespace.

    Returns:
        set[str]: All node class names the scanner should treat as
        resolvable in the current environment.
    """
    available_nodes: Set[str] = set(CORE_NODES)
    if is_running_in_nuke():
        import nuke
        available_nodes.update(nuke.nodeTypes())
        plugin_files = nuke.plugins(nuke.ALL | nuke.NODIR, "*.gizmo", "*.so", "*.dylib", "*.dll")
        for p in plugin_files:
            available_nodes.add(os.path.splitext(p)[0])

        def get_all_menu_items(menu) -> Set[str]:
            """Recursively collect every node-creating menu item.

            Walks the supplied :class:`nuke.Menu`, descending into
            submenus and using a regex on each leaf item's script
            payload to recover the class name passed to
            ``createNode`` or ``createNodeLocal``.

            Args:
                menu: A :class:`nuke.Menu` instance to walk.

            Returns:
                set[str]: Node class names parsed out of menu item
                scripts, with empty results for items whose script
                cannot be read.
            """
            items = set()
            for item in menu.items():
                if isinstance(item, nuke.Menu):
                    items.update(get_all_menu_items(item))
                else:
                    try:
                        script = item.script()
                        matches = re.findall(r"createNode(?:Local)?\(['\"]([^'\"]+)['\"]", script)
                        items.update(matches)
                    except Exception:
                        continue
            return items
        try:
            available_nodes.update(get_all_menu_items(nuke.menu("Nodes")))
        except Exception:
            pass
    return {n.strip() for n in available_nodes}


def paste_template(tpl: Template) -> None:
    """Paste a scanned template into the current Nuke DAG.

    Verifies that the template's source file still exists on disk, then
    invokes ``nuke.nodePaste`` to insert the nodes at the current cursor
    position in the node graph. If the file has been moved or deleted
    since the scan, the function prints a diagnostic and returns
    without raising. When called outside Nuke (for development) it
    prints what would have been pasted and returns.

    Args:
        tpl: A :class:`Template` record whose ``path`` field points to
            the ``.nk`` file to paste. No other fields are consulted.
    """
    nk_path: str = tpl["path"]
    if not os.path.isfile(nk_path):
        print("ERR - file not found:", nk_path)
        return
    try:
        import nuke
    except ImportError:
        print("Not in Nuke - would paste:", nk_path)
        return
    nuke.nodePaste(nk_path)