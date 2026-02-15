#import nukescripts
import os
import settings
from scanner import scan_templates, Template
def is_running_in_nuke():
    try:
        import nuke
        return hasattr(nuke, "nodeTypes")
    except ImportError:
        return None

def get_available_nodes():
    if is_running_in_nuke():
        import nuke
        try:
            available_nodes: set[str] = set(nuke.nodeTypes(force_plugin_load=True)) # type: ignore
        except TypeError:
            available_nodes: set[str] = set(nuke.nodeTypes()) # type: ignore
    else:
        available_nodes: set[str] = {'Add', 'AddChannels', 'AddMix', 'AddSTMap', 'AddTimeCode', 'AdditiveKeyer', 'AdditiveKeyer_2', 'AdjBBox', 'AmbientOcclusion', 'Anaglyph', 'AppendClip', 'ApplyLUT', 'ApplyMaterial', 'Assert', 'AttribGeo', 'AudioRead', 'Axis', 'Axis2', 'Axis3', 'Axis4', 'BackdropNode', 'BackgroundMatting', 'BakedPointCloud', 'BakedPointCloudMesh', 'BasicMaterial', 'BasicSurface', 'Bezier', 'Bilateral', 'Bilateral2', 'Black', 'BlackOutside', 'Blend', 'BlendMat', 'BlinkBlur', 'BlinkFilterErode', 'BlinkScript', 'BlockGPU', 'Blocky', 'Blur', 'Bokeh', 'Breakdown_Accordion_v01', 'Breakdown_Maker', 'Breakdown_Tool', 'Breakdowner', 'BumpBoss', 'BumpMat', 'BurnIn', 'CCorrect', 'CCrosstalk', 'CMSTestPattern', 'C_AlphaGenerator2_1', 'C_Bilateral2_1', 'C_Blender2_1', 'C_Blur2_1', 'C_CameraIngest2_1', 'C_CameraSolver2_1', 'C_ColourMatcher2_1', 'C_DisparityGenerator2_1', 'C_GenerateMap2_1', 'C_GlobalWarp2_1', 'C_RayRender2_1', 'C_STMap2_1', 'C_SphericalTransform2_1', 'C_Stitcher2_1', 'C_Tracker2_1', 'Camera', 'Camera2', 'Camera3', 'Camera4', 'CameraShake', 'CameraShake2', 'CameraShake3', 'CameraTracker', 'CameraTracker1_0', 'CameraTrackerPointCloud', 'CameraTrackerPointCloud1_0', 'Card', 'Card2', 'Card3D', 'CardObj', 'CatFileCreator', 'Caustics', 'ChannelMerge', 'ChannelSelector', 'Checker', 'CheckerBoard', 'CheckerBoard2', 'ChromaKeyer', 'Clamp', 'ClipTest', 'ColorBars', 'ColorCorrect', 'ColorLookup', 'ColorMatrix', 'ColorTransfer', 'ColorTransferWrapper', 'ColorWheel', 'Colorspace', 'Compare', 'CompareMetaData', 'Constant', 'ConstantShader', 'ContactSheet', 'Convolve', 'Convolve2', 'Copy', 'CopyBBox', 'CopyCat', 'CopyMetaData', 'CopyRectangle', 'CornerPin2D', 'Crop', 'CrosstalkGeo', 'Cryptomatte', 'Cube', 'CubeObj', 'CurveTool', 'Cylinder', 'CylinderObj', 'D_QCTool_v02', 'DeInterlace', 'Deblur', 'DeepChannelBlanker', 'DeepClip', 'DeepClipZ', 'DeepColorCorrect', 'DeepColorCorrect2', 'DeepCompare', 'DeepCrop', 'DeepDeOverlap', 'DeepExpression', 'DeepFromFrames', 'DeepFromImage', 'DeepHoldout', 'DeepHoldout2', 'DeepMask', 'DeepMerge', 'DeepMerge2', 'DeepOmit', 'DeepRead', 'DeepRecolor', 'DeepReformat', 'DeepSample', 'DeepShift', 'DeepToImage', 'DeepToImage2', 'DeepToPoints', 'DeepTransform', 'DeepVolumeMaker', 'DeepWrite', 'Defocus', 'DegrainBlue', 'DegrainSimple', 'Denoise2', 'DepthGenerator', 'DepthGenerator1_0', 'DepthToPoints', 'DepthToPosition', 'Difference', 'Diffuse', 'Dilate', 'DilateErodeFine_CB', 'DirBlur', 'DirBlurWrapper', 'DirectLight', 'DirectLight1', 'DiskCache', 'DisplaceGeo', 'Displacement', 'Dissolve', 'Dither', 'Dot', 'DrawCursorShaderOp', 'DropShadow', 'DualBlend', 'DummyCam', 'DustBust', 'EXPTool', 'EZ_Backdrop', 'EdgeBlur', 'EdgeDetect', 'EdgeDetectWrapper', 'EdgeExtend', 'EdgeScatter', 'EditGeo', 'Emboss', 'Emission', 'Encryptomatte', 'Environment', 'EnvironmentLight', 'Erode', 'ErrorIop', 'ExecuteTreeMT', 'Expression', 'FFT', 'FFTMultiply', 'F_Align', 'F_DeFlicker2', 'F_DeGrain', 'F_DeNoise', 'F_Kronos', 'F_MatchGrade', 'F_MotionBlur', 'F_ReGrain', 'F_RigRemoval', 'F_Steadiness', 'F_VectorGenerator', 'F_WireRemoval', 'FieldSelect', 'Fill', 'FillMat', 'FillShader', 'FilterErode', 'FishEye', 'Flare', 'FloodFill', 'FnNukeMultiTypeOpDeepOp', 'FnNukeMultiTypeOpGeoOp', 'FnNukeMultiTypeOpGeomOp', 'FnNukeMultiTypeOpIop', 'FnNukeMultiTypeOpParticleOp', 'Fog', 'FrameBlend', 'FrameHold', 'FrameRange', 'FromDeep', 'GPUFileShader', 'GPUOp', 'Gabor_filter', 'Gamma', 'GenerateLUT', 'GenerateLUTGeo', 'GeoBakedMesh', 'GeoBakedPointCloud', 'GeoBakedPointCloudMesh', 'GeoBakedPoints', 'GeoBindMaterial', 'GeoCameraTrackerPoints', 'GeoCameraTrackerPoints1_0', 'GeoCard', 'GeoCollection', 'GeoCompare', 'GeoConstrain', 'GeoCube', 'GeoCylinder', 'GeoDisplace', 'GeoDrawMode', 'GeoDuplicate', 'GeoExport', 'GeoImport', 'GeoInstance', 'GeoIsolate', 'GeoMerge', 'GeoNoise', 'GeoNormals', 'GeoPoints', 'GeoPointsToMesh', 'GeoPrune', 'GeoPython', 'GeoRadialWarp', 'GeoReference', 'GeoScene', 'GeoScopePrim', 'GeoScript', 'GeoSelect', 'GeoSelector', 'GeoSetVariant', 'GeoSphere', 'GeoStageEdit', 'GeoTransform', 'GeoTrilinearWarp', 'GeoTwist', 'GeoUVProject', 'GeoViewScene', 'GeoXformPrim', 'GeomOpTester', 'Gizmo', 'Glint', 'Glow', 'Glow2', 'GodRays', 'Grade', 'Grain', 'Grain2', 'Grid', 'GridWarp', 'GridWarp2', 'GridWarp3', 'GridWarpTracker', 'Group', 'HSVTool', 'HighPassing', 'HistEQ', 'Histogram', 'HueCorrect', 'HueKeyer', 'HueShift', 'IBK', 'IBK2Gizmo', 'IBKColour', 'IBKColourV3', 'IBKEdge', 'IBKGizmo', 'IBKGizmoV3', 'IBKSFill', 'IBKSplit', 'IDistort', 'IT8_Reader', 'IT8_Writer', 'Inference', 'Inpaint', 'Inpaint2', 'Input', 'InternalTimelineDefaultInput', 'InvFFT', 'Invert', 'JoinViews', 'Keyer', 'Keylight', 'Keymix', 'Kronos', 'L_ExponBlur_v03', 'Laplacian', 'LayerContactSheet', 'LensDistortion', 'LensDistortion1_0', 'LensDistortion2', 'LevelSet', 'Light', 'Light2', 'Light3', 'Light4', 'LightWrap', 'LiveGroup', 'LiveInput', 'Log2Lin', 'LogGeo', 'LookupGeo', 'MODNet', 'MV2Nuke', 'MakeLatLongMap', 'MarkerRemoval', 'Mask3DCubical_ik', 'Mask3DGradient_ik', 'Mask3DSpherical_ik', 'MatchGrade', 'Matrix', 'Median', 'Merge', 'Merge2', 'MergeExpression', 'MergeGeo', 'MergeLayerShader', 'MergeMat', 'MeshGeo', 'MinColor', 'MindRead', 'Mirror', 'Mirror2', 'MixViews', 'Mocha Pro', 'Mocha VR (legacy)', 'ModelBuilder', 'ModelBuilderGeo', 'Modeler', 'Modeler1_0', 'ModifyMetaData', 'ModifyRIB', 'MoirePattern', 'Morph_Dissolve', 'MotionBlur', 'MotionBlur2D', 'MotionBlur3D', 'MultiTexture', 'Multiply', 'NST_AdditiveKeyerPro', 'NST_AnimationCurve', 'NST_AntiAliasingFilter', 'NST_AutoCropTool', 'NST_AutoFlare2', 'NST_BBoxToFormat', 'NST_BeautifulSkin', 'NST_BiasedSaturation', 'NST_BinaryAlpha', 'NST_BlacksExpon', 'NST_BlacksMatch', 'NST_BokehBuilder', 'NST_C44Kernel', 'NST_CProject', 'NST_CameraNormals', 'NST_CardToTrack', 'NST_CatsEyeDefocus', 'NST_CellNoise', 'NST_ChannelCombiner', 'NST_ChannelControl', 'NST_ChannelCreator', 'NST_Chromatik', 'NST_ColorCopy', 'NST_ColorSampler', 'NST_ColorSmear', 'NST_ContactSheetAuto', 'NST_Contrast', 'NST_ConvertPNZ', 'NST_ConvolutionMatrix', 'NST_CornerPin2D_Matrix', 'NST_CrossProductVector2', 'NST_CrossProductVector3', 'NST_DVPColorCorrect', 'NST_DVPToImage', 'NST_DVP_Shader', 'NST_DVP_ToonShader', 'NST_DVPattern', 'NST_DVPfresnel', 'NST_DVPmatte', 'NST_DVPortal', 'NST_DVPrelight', 'NST_DVPrelightPT', 'NST_DVProjection', 'NST_DVPscene', 'NST_DVPsetLight', 'NST_DasGrain', 'NST_Deep2VP', 'NST_Deep2VPosition', 'NST_DeepBoolean', 'NST_DeepCopyBBox', 'NST_DeepCropSoft', 'NST_DeepFromDepth', 'NST_DeepFromPosition', 'NST_DeepHoldoutSmoother', 'NST_DeepKeyMix', 'NST_DeepMerge_Advanced', 'NST_DeepRecolorMatte', 'NST_DeepSampleCount', 'NST_DeepSer', 'NST_DeflickerVelocity', 'NST_DefocusSwirlyBokeh', 'NST_DespillToColor', 'NST_Diffusion', 'NST_DirectionalBlur', 'NST_Distance3D', 'NST_DistanceBetween_CS', 'NST_DotProductVector2', 'NST_DotProductVector3', 'NST_DummyCam', 'NST_Edge', 'NST_EdgeDetectAlias', 'NST_EdgeDetectPRO', 'NST_EdgeFromAlpha', 'NST_Edge_Expand', 'NST_Edge_RimLight', 'NST_EnvReflect_BB', 'NST_ErodeSmooth', 'NST_Erode_Fine', 'NST_ExponBlurSimple', 'NST_ExponGlow', 'NST_F_P_Project', 'NST_F_P_Ramp', 'NST_FillSampler', 'NST_FlareSuperStar', 'NST_FractalBlur', 'NST_FrameFiller', 'NST_FrameHoldSpecial', 'NST_FrameMedian', 'NST_GUI_Switch', 'NST_GammaPlus', 'NST_GenerateMatrix4', 'NST_GenerateSTMap', 'NST_GeoToPoints', 'NST_Glass', 'NST_GlobalCTRL', 'NST_Glow_Exponential', 'NST_GlueP', 'NST_GodRaysProjector', 'NST_GradMagic', 'NST_GradeLayerPass', 'NST_Grain_Advanced', 'NST_HSL_Tool', 'NST_Halation', 'NST_HeatWave', 'NST_HighPass', 'NST_HighlightSuppress', 'NST_IIDistort', 'NST_ITransformU', 'NST_ImagePlane3D', 'NST_InjectMatteChannel', 'NST_InverseMatrix33', 'NST_InverseMatrix44', 'NST_InvertAxis', 'NST_InvertMatrix4', 'NST_KeyChew', 'NST_KeymixBBox', 'NST_KillOutline', 'NST_LabelFromRead', 'NST_LensEngine', 'NST_LightWrapPro', 'NST_Lightning3D', 'NST_LineTool', 'NST_Looper', 'NST_LumaGrain', 'NST_LumaKeyer', 'NST_LumaToVector3', 'NST_MECfiller', 'NST_MagnitudeVector2', 'NST_MagnitudeVector3', 'NST_Matrix4x4Math', 'NST_Matrix4x4_Inverse', 'NST_MergeAll', 'NST_MergeAtmos', 'NST_MergeBlend', 'NST_MirrorBorder', 'NST_MonochromePlus', 'NST_MorphDissolve', 'NST_MotionBlurPaint', 'NST_MultiplyVector3Matrix3', 'NST_NAN_INF_Killer', 'NST_N_Reflection', 'NST_Noise3DTexture', 'NST_Noise3D_spin', 'NST_NoiseAdvanced', 'NST_NormalizeVector2', 'NST_NormalizeVector3', 'NST_NormalsRotate', 'NST_NukeZ', 'NST_P2N', 'NST_P2Z', 'NST_P_Noise_Advanced', 'NST_ParticleKiller', 'NST_ParticleLights', 'NST_PerspectiveGuide', 'NST_PlanarProjection', 'NST_PlotScanline', 'NST_PosMatte_MJ', 'NST_PosPattern_MJ', 'NST_PosProjection_MJ', 'NST_ProductMatrix4', 'NST_Pyclopedia', 'NST_Python_and_TCL', 'NST_RP_Reformat', 'NST_RadialAdvanced', 'NST_RainMaker', 'NST_Randomizer', 'NST_RankFilter', 'NST_RayDeepAO', 'NST_ReProject_3D', 'NST_Reconcile3DFast', 'NST_Relight_Simple', 'NST_Relight_bb', 'NST_RotateMatrix4', 'NST_RotateVector2', 'NST_RotateVector3', 'NST_RotoCentroid', 'NST_RotoPaintTransform', 'NST_RotoQC', 'NST_SSMesh', 'NST_STMapToVector2', 'NST_STmapInverse', 'NST_ScaleMatrix4', 'NST_SceneDepthCalculator', 'NST_ShadowMult', 'NST_SimpleSSS', 'NST_SliceTool', 'NST_Sparky', 'NST_Spill_Correct', 'NST_SpotFlare', 'NST_Suppress_RGBCMY', 'NST_TProject', 'NST_TimeMachine', 'NST_TransformCutOut', 'NST_TransformMatrix', 'NST_TransformMatrix4', 'NST_TransformMix', 'NST_TransformVector2', 'NST_TransformVector3', 'NST_TranslateMatrix4', 'NST_TransposeMatrix4', 'NST_UVEditor', 'NST_UV_Map', 'NST_UV_Mapper', 'NST_Unify3DCoordinate', 'NST_Vector2ToSTMap', 'NST_Vector3ToMatrix4', 'NST_VectorExtendEdge', 'NST_VectorTracker', 'NST_Vectors_Direction', 'NST_Vectors_to_Degrees', 'NST_VoronoiGradient', 'NST_WaterLens', 'NST_WaveletBlur', 'NST_WhiteBalance', 'NST_WhiteSoftClip', 'NST_X_Aton_Volumetrics', 'NST_X_Denoise', 'NST_X_Distort', 'NST_X_Sharpen', 'NST_X_Soften', 'NST_X_Tesla', 'NST_Z2N', 'NST_Z2P', 'NST_ZeroAxis', 'NST_aPCard', 'NST_aPMatte_v2', 'NST_apChroma', 'NST_apChromaBlurNew', 'NST_apChromaMergeNew', 'NST_apChromaPremult', 'NST_apChromaTransformNew', 'NST_apChromaUnpremult', 'NST_apDespill', 'NST_apDespill_v2', 'NST_apDirLight', 'NST_apEdgePush', 'NST_apFresnel', 'NST_apLoop', 'NST_apViewerBlocker', 'NST_apVignette', 'NST_apeGlow', 'NST_apeScreenClean', 'NST_apeScreenGrow', 'NST_bm_CameraShake', 'NST_bm_CurveRemapper', 'NST_bm_Lightwrap', 'NST_bm_MatteCheck', 'NST_bm_NoiseGen', 'NST_bm_OpticalGlow', 'NST_deHaze', 'NST_h_gradienteditor', 'NST_h_silk', 'NST_h_stickit', 'NST_iBlurU', 'NST_iConvolve', 'NST_iMorph', 'NST_iMorph_v2', 'NST_mScatterGeo', 'NST_origami', 'NST_renameChannels', 'NST_streamCart', 'NST_vector3DMathExpression', 'NST_viewer_render', 'NST_waterSchmutz', 'NST_waveCustom', 'NST_waveGrade', 'NST_waveMaker', 'NST_waveMerge', 'NST_waveRetime', 'NoOp', 'NoProxy', 'NoTimeBlur', 'NodeWrapper', 'Noise', 'Normals', 'OCIOCDLTransform', 'OCIOColorSpace', 'OCIODisplay', 'OCIOFileTransform', 'OCIOLogConvert', 'OCIOLookTransform', 'OCIONamedTransform', 'OFlow2', 'OneView', 'OpStatisticsOp', 'Output', 'PLogLin', 'PSDMerge', 'Paint', 'PanelNode', 'ParticleAttractToSphere', 'ParticleBlinkScript', 'ParticleBlinkScriptRender', 'ParticleBounce', 'ParticleCache', 'ParticleColorByAge', 'ParticleConstrainToSphere', 'ParticleCurve', 'ParticleCylinderFlow', 'ParticleDirection', 'ParticleDirectionalForce', 'ParticleDistributeSphere', 'ParticleDrag', 'ParticleDrag2', 'ParticleEmitter', 'ParticleExpression', 'ParticleFlock', 'ParticleFuse', 'ParticleGravity', 'ParticleGrid', 'ParticleHelixFlow', 'ParticleInfo', 'ParticleKill', 'ParticleLookAt', 'ParticleMerge', 'ParticleMotionAlign', 'ParticleMove', 'ParticlePointForce', 'ParticleProjectDisplace', 'ParticleProjectImage', 'ParticleRender', 'ParticleSettings', 'ParticleShockWave', 'ParticleSpawn', 'ParticleSpeedLimit', 'ParticleSystem', 'ParticleToGeo', 'ParticleToImage', 'ParticleTurbulence', 'ParticleVortex', 'ParticleWind', 'PerspDistort', 'Phong', 'PixelStat', 'PixelSum', 'PlanarTracker', 'PlanarTracker1_0', 'PointCloudGenerator', 'PointCloudGenerator1_0', 'PointLight', 'PointsGenerator', 'PointsTo3D', 'PoissonMesh', 'Position', 'PositionToPoints', 'PositionToPoints2', 'PostageStamp', 'Posterize', 'Precomp', 'Preferences', 'Premult', 'PreviewSurface', 'Primatte', 'Primatte3', 'PrimatteAdjustLighting', 'PrintHash', 'PrintMetaData', 'ProcGeo', 'Profile', 'Project3D', 'Project3D2', 'Project3DShader', 'ProjectionSolver', 'ProjectionSolver1_0', 'PxF_AreaLight', 'PxF_Bandpass', 'PxF_ChromaBlur', 'PxF_DeepDefocus', 'PxF_DeepFade', 'PxF_DeepMask', 'PxF_DeepResample', 'PxF_Distort', 'PxF_EnvLight', 'PxF_Erode', 'PxF_Filler', 'PxF_GeoLight', 'PxF_Grain', 'PxF_HueSat', 'PxF_IDefocus', 'PxF_KillSpill', 'PxF_Line', 'PxF_MergeWrap', 'PxF_Nukebench', 'PxF_RingLight', 'PxF_ScreenClean', 'PxF_SmokeBox', 'PxF_Smoother', 'PxF_TimeMerge', 'PxF_TubeLight', 'PxF_VectorEdgeBlur', 'PxF_ZDefocus', 'PythonGeo', 'RP_Reformat', 'Radial', 'RadialDistort', 'Ramp', 'RayRender', 'ReConverge', 'ReLight', 'Read', 'ReadGeo', 'ReadGeo2', 'Reconcile3D', 'Rectangle', 'Reflection', 'ReflectiveSurface', 'Reformat', 'Refraction', 'Remove', 'RendermanShader', 'Retime', 'RolloffContrast', 'Roto', 'RotoPaint', 'STMap', 'Sampler', 'Saturation', 'ScanlineRender', 'ScanlineRender2', 'ScannedGrain', 'Scene', 'Sharpen', 'Shuffle', 'Shuffle1', 'Shuffle2', 'ShuffleCopy', 'ShuffleViews', 'SideBySide', 'Silhouette', 'SimpleAxis', 'SmartVector', 'SoftClip', 'Soften', 'Sparkles', 'Specular', 'Sphere', 'SphereObj', 'SphereToLatLongMap', 'SphericalMap', 'SphericalTransform', 'SphericalTransform2', 'SplineWarp', 'SplineWarp2', 'SplineWarp3', 'SpotLight1', 'Spotlight', 'StabTrack', 'Stabilize2D', 'StarField', 'StickyNote', 'SurfaceOptions', 'Switch', 'TECH_CHECK_HELPER', 'TVIscale', 'TX_HueKeyer', 'TemporalMedian', 'Text', 'Text2', 'TextureFile', 'TextureMap', 'TextureSampler', 'Tile', 'TimeBlend', 'TimeBlur', 'TimeClip', 'TimeDissolve', 'TimeEcho', 'TimeOffset', 'TimeShift', 'TimeToDepth', 'TimeWarp', 'ToDeep', 'Toe2', 'Tracker', 'Tracker3', 'Tracker4', 'Tracker4', 'Transform', 'Transform3D', 'TransformGeo', 'TransformMasked', 'TransformWorld_ik', 'Transmission', 'Trilinear', 'Twist', 'TwistGeo', 'UVProject', 'UVTile2', 'Ultimatte', 'UnmultColor', 'Unpremult', 'UnrealReader', 'Unwrap', 'UpRez', 'Upscale', 'VariableGroup', 'VariableSwitch', 'VectorBlur', 'VectorBlur2', 'VectorCornerPin', 'VectorDistort', 'VectorGenerator', 'VectorToMotion', 'Vectorfield', 'ViTMatte', 'ViewMetaData', 'Viewer', 'ViewerCaptureOp', 'ViewerChannelSelector', 'ViewerClipTest', 'ViewerDitherDisable', 'ViewerDitherHighFrequency', 'ViewerDitherLowFrequency', 'ViewerGain', 'ViewerGamma', 'ViewerInterlacedStereo', 'ViewerLUT', 'ViewerProcess_1DLUT', 'ViewerProcess_None', 'ViewerSaturation', 'ViewerScopeOp', 'ViewerWipe', 'VolumeRays', 'Wireframe', 'WireframeShader', 'WorldPos_Lambert_Shader_ik', 'WorldPos_Texture_Generator_ik', 'WorldPos_Texture_Projection_ik', 'Write', 'WriteGeo', 'X_Denoise', 'ZBlur', 'ZComp', 'ZDefocus', 'ZDefocus2', 'ZFDefocus', 'ZMerge', 'ZRMerge', 'ZSlice', 'add32p', 'apDespill', 'bl_ColorEdge', 'bl_Convolve', 'bm_Lightwrap', 'cyBreakdown', 'emDepthFix', 'emMatte', 'expoglow', 'fl_VirtualLens', 'fxT_compQC', 'k_pMatte', 'objReaderObj', 'ray_march', 'remove32p', 'sdf_light', 'sdf_material', 'sdf_noise', 'sdf_primitive', 'special_K'}
    available_nodes = set(n.strip() for n in available_nodes)
    print("AVAILABLE NODES:", len(available_nodes))
    return available_nodes

def make_label(t: Template) -> str:
    if t["status"] == "OK":
        return t["name"] + ":OK"
    elif t["status"] == "MISSING_NODES":
        return "{}:MISSING({})". format(t["name"], len(t["missing_nodes"]))
    else:
        return t["name"] + ":ERROR"
    
def paste_template(tpl: Template) -> None:
    nk_path: str = tpl["path"]
    if not os.path.isfile(nk_path):
        print("ERR - file not found:", nk_path)
        return

    try:
        import nuke
    except ImportError:
        print("Not in Nuke - would paste:", nk_path)
        return

    if tpl["status"] != "OK":
        print("Not pasting because status is:", tpl["status"])
        return

    nuke.nodePaste(nk_path) # type: ignore
def start() -> list[Template]:
    path: str = settings.get_effective_template_path()
    os.makedirs(path, exist_ok=True)
    available_nodes = get_available_nodes()
    templates: list[Template] = scan_templates(path, available_nodes)
    def format_missing_nodes(t: Template, limit: int=5):
        if t["status"] != "MISSING_NODES":
            return None

        nodes = t["missing_nodes"]
        shown = nodes[:limit]
        text = ", ".join(shown)

        if len(nodes) > limit:
            text += ", ..."

        return "missing nodes: " + text

    for t in templates:
        print(make_label(t))

        details = format_missing_nodes(t, limit=5)
        if details:
            print("       " + details)
    return templates

def open_template_manager():
    path: str = settings.get_effective_template_path()
    templates: list[Template] = start()
    label_to_template: dict[str, Template] = {}
    labels: list[str] = []
    for t in templates:
        label: str = make_label(t).replace("|", "/")
        label: str = label.replace(" ", "_")
        labels.append(label)
        label_to_template[label] = t
    try:
        import nuke
        if not labels:
            nuke.message(f"No Templates Found in\n{path}") # type: ignore
            return
        p = nuke.Panel("Template Manager") # type: ignore
        p.addEnumerationPulldown("Template", " ".join(labels)) # type: ignore
        if not p.show(): # type: ignore
            return
        selected = p.value("Template") # type: ignore
        tpl: Template | None = label_to_template.get(selected) # pyright: ignore[reportUnknownArgumentType]
        if not tpl:
            nuke.message(f"Selected label not found:\n{selected}") # type: ignore
            return
        if tpl.get("status") != "OK":
<<<<<<< HEAD
            nuke.message(f"Template not OK: {tpl.get('status')}") # type: ignore
            return
=======
            if tpl.get("status") == "MISSING_NODES":
                nuke.message(f"Missing: {tpl.get('missing_nodes')}")
                return
            else:
                nuke.message(f"Template not OK: {tpl.get('status')}")
                return
>>>>>>> 6eda2f3 (Bug Fix)
        paste_template(tpl)
    except ImportError:
        return None
if __name__ == "__main__":
    start()
