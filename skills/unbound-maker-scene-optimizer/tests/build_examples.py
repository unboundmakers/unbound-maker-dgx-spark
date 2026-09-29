"""Build preview examples into new folders and emit their observed CPU metrics."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from scene_optimizer import optimize, read_json


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--artifacts',required=True,type=Path)
    args = parser.parse_args()
    for scene in ('meadow','space','moon'):
        output = args.artifacts/('optimized-'+scene+'-v0.1.0')
        manifest = optimize(args.artifacts/('scene-'+scene+'-v0.1.0'),
                            dict(schema_version=1,profile='preview'),output)
        report = read_json(output/'optimization-report.json')
        print(json.dumps(dict(scene=scene,output=str(output),changes=len(report['changes']),
                              before=report['before'],after=report['after'],
                              bytes_without_manifest=manifest['package_bytes_without_manifest']),sort_keys=True),flush=True)


if __name__=='__main__':
    main()
