"""Maintainer-only: inventory an inspected LOCAL meadow-v0.3 asset root. Never download assets."""
import argparse
from pathlib import Path
import sys
from scene_builder import digest, write_json


def snapshot(root, output):
    from pxr import UsdUtils
    root=Path(root).resolve()
    common=dict(spawn=[0,0,0],camera_eye=[6,-9,4],camera_target=[0,0,.8])
    configs={
        'meadow':dict(**common,gravity_m_s2=9.81,components=[dict(prim='/World/Environment',entry='scene.usda',source_prim='/World')],
                      credits=['README.md','assets/GRAVEL-SOURCE.md'],
                      runtime=dict(mode='story',gravity_m_s2=9.81,dynamic_lod_requires_runner=True),
                      renderer_settings={'/rtx/background/source/type':2,'/rtx/background/source/color':[.34,.64,.85],
                                         '/rtx/fog/enabled':True,'/rtx/fog/fogColor':[.55,.72,.77],
                                         '/rtx/fog/fogColorIntensity':1.,'/rtx/fog/fogHeightDensity':0.,
                                         '/rtx/fog/fogStartDist':22.,'/rtx/fog/fogEndDist':200.,'/rtx/fog/fogDistanceDensity':.35},
                      notes=['Authored meadow-v0.3 terrain, rocks and trees; two NVIDIA grass meshes and adapted NVIDIA gravel maps.',
                             'Poly Haven meadow_2k.exr sky; preserve source credits. Assets are not collectively CC0.',
                             'Keep authored grass detail variants; camera-driven switching belongs to Simulation Runner.']),
        'space':dict(spawn=[0,0,5],camera_eye=[6,-9,9],camera_target=[0,8,7],gravity_m_s2=0.,
                     components=[dict(prim='/World/Environment',entry='assets/space/space.usdc',source_prim='/Space')],
                     credits=['assets/space/nasa/provenance.json','SOLAR-UPGRADE-20260929.md'],
                     runtime=dict(mode='story',gravity_m_s2=0.,dynamic_lod_requires_runner=True),
                     renderer_settings={'/rtx/background/source/type':2,'/rtx/background/source/color':[.001,.002,.008],'/rtx/fog/enabled':False},
                     notes=['NASA-derived planetary materials; exact source and adaptation records are retained.',
                            'Fictional compressed planetary playground: sizes/distances are not a true-scale solar system or orbital simulation.']),
        'moon':dict(**common,gravity_m_s2=1.62,astronaut_ground_z=0.,
                    components=[dict(prim='/World/Environment',entry='assets/moon/moon.usdc',source_prim='/Moon'),
                                dict(prim='/World/LunarVehicles',entry='assets/lunar-vehicles-v1/camp.usda',source_prim='/LunarVehicles'),
                                dict(prim='/World/Astronaut',entry='assets/astronaut-static.usdc',source_prim='/Astronaut')],
                    credits=['assets/moon/provenance.json','assets/ASTRONAUT-SOURCE.md','assets/astronaut-textures/provenance.json',
                             'assets/astronaut-textures/overrides.json','assets/lunar-vehicles-v1/README.md','assets/lunar-vehicles-v1/placement.json'],
                    runtime=dict(mode='experiment',gravity_m_s2=1.62,duration_s=10,dynamic_lod_requires_runner=False),
                    renderer_settings={'/rtx/background/source/type':0,'/rtx/fog/enabled':False},
                    notes=['Illustrative lunar terrain; near craters and PBR regolith are synthetic, distant relief adapted from NASA data.',
                           'Pink-blue glow is decorative, not a real lunar atmosphere. Lunar vehicles are static educational props.',
                           'NVIDIA astronaut retains its material graphs and neutralized clothing atlases; OmniPBR/OmniGlass MDL are Isaac runtime dependencies.'])}
    # This maintenance tool is only for our inspected local source tree, not downloaded code.
    from pxr import Usd
    astronaut_stage=Usd.Stage.Open(str(root/'assets/astronaut-static.usdc'))
    configs['moon']['components'][-1]['source_prim']=str(astronaut_stage.GetDefaultPrim().GetPath())
    # Same fixed near-camp location as the current runtime; height is provided by maintained local rules.
    sys.path.insert(0,str(root))
    from moon_rules import ASTRONAUT
    configs['moon']['astronaut_ground_z']=ASTRONAUT[2]
    for config in configs.values():
        paths={root/name for name in config.pop('credits')}
        missing_all=set()
        for component in config['components']:
            layers,assets,missing=UsdUtils.ComputeAllDependencies(str(root/component['entry']))
            paths.update(Path(l.realPath) for l in layers)
            paths.update(Path(p) for p in assets)
            missing_all.update(missing)
        if missing_all-{'OmniPBR.mdl','OmniGlass.mdl'}:
            raise ValueError('Unresolved source assets: '+str(missing_all))
        config['runtime_mdl_dependencies']=sorted(missing_all)
        config['files']=[dict(path=str(p.resolve().relative_to(root)),sha256=digest(p),bytes=p.stat().st_size) for p in sorted(paths)]
    write_json(output,dict(schema_version=1,version='meadow-v0.3-snapshot-20260929',scenes=configs))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.output.exists():
        raise SystemExit('Refusing to overwrite an existing catalog.')
    args.output.parent.mkdir(parents=True,exist_ok=True)
    snapshot(args.source,args.output)
