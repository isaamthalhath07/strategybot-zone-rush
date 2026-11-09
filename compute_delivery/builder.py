"""Wrap an ALREADY AUTHORIZED control shard without issuing any new jobs."""
import argparse
import io
from pathlib import Path
import zipfile

from compute_delivery import runner


ROOT = Path(__file__).resolve().parents[1]


def _write(path,body):
    path = runner.no_links(path)
    if path.exists():
        if path.read_bytes()!=body:
            raise ValueError('Existing immutable delivery differs; preserve it and choose a new wrapper output')
        return
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('xb') as handle:
        handle.write(body)


def build(plan_path,shard_id,output,audit_plan_path=None):
    """Authenticate owner plan FIRST; never prepare a plan or actor task."""
    from distributed_campaign import control,protocol
    plan_path = Path(plan_path).resolve()
    if audit_plan_path is None:
        plan,registry,registration,directory,bundles = control._load(plan_path)
        issued,kind = plan,'play'
    else:
        plan,registry,registration,directory,issued,origins,bundles = control._audit_plan(plan_path,audit_plan_path)
        kind = 'audit'
    shard = next((item for item in issued['distribution']['shards'] if item['id']==shard_id),None)
    if shard is None or shard_id not in bundles:
        raise ValueError('Unknown shard in the authenticated selected work role')
    bundle = protocol.verify_bundle(shard['bundle_directory'],shard['bundle_sha256'])
    if bundle!=bundles[shard_id] or bundle['work_role']!=kind or bundle['role']!='extra_control_assignment':
        raise ValueError('Selected authorized work role/manifest changed')
    if (bundle['campaign_id']!=plan['campaign_id'] or bundle['generation']!=plan['generation']
            or bundle['source_registration_sha256']!=plan['source_registration_sha256']
            or [item['id'] for item in bundle['fixtures']]!=shard['fixture_ids']):
        raise ValueError('Selected shard differs from its original owner authorization')
    archive = runner.no_links(shard['archive'])
    config = dict(format=runner.FORMAT,role=bundle['role'],work_role=kind,campaign_id=bundle['campaign_id'],
                  generation=bundle['generation'],shard_id=shard_id,
                  source_registration_sha256=bundle['source_registration_sha256'],slot=bundle['target_slot'],
                  expected_tasks=len(bundle['fixtures']),inner_archive_sha256=shard['archive_sha256'],
                  bundle_sha256=shard['bundle_sha256'],approved_runtime=bundle['approved_runtime'],
                  approved_runtime_fingerprint=runner.fingerprint(bundle['approved_runtime']),
                  owner_plan_sha256=runner.sha(plan_path.read_bytes()),
                  audit_plan_sha256=runner.sha(Path(audit_plan_path).read_bytes()) if audit_plan_path else None,
                  primary_credit=0,cuda_used_by_policy=False)
    archived = runner.inspect_payload(archive,config)  # Complete whitelist/hash/containment checks before output.
    if archived!=bundle:
        raise ValueError('Authenticated ZIP manifest differs from verified source directory')
    output = runner.no_links(output)
    source_directory = Path(shard['bundle_directory']).resolve()
    if output.resolve().is_relative_to(source_directory) or source_directory.is_relative_to(output.resolve()):
        raise ValueError('Delivery output must be separate from the issued worker source directory')
    files = {
        'delivery.json':runner.canonical(config)+b'\n',
        'worker_payload.zip':archive.read_bytes(),
        'RUN_WORK.py':(Path(__file__).parent/'runner.py').read_bytes(),
        'START_HERE.cmd':(Path(__file__).parent/'START_HERE.cmd').read_bytes(),
        'START_HERE.ps1':(Path(__file__).parent/'START_HERE.ps1').read_bytes(),
    }
    label = 'ORIGINAL FULL MATCHES' if kind=='play' else 'FULL-GAME INDEPENDENT REPLAYS (NO NEW GAMES)'
    files['READ_ME.txt'] = (
        label+'\r\n\r\n'
        'Extract this whole ZIP to a short local folder, then double-click START_HERE.cmd.\r\n'
        'Use your same previously qualified Python environment. Nothing is installed.\r\n'
        'The cached private helper credential from qualification is reused. If missing, select only your own separately supplied credential.\r\n'
        'These Python actors run on CPU. The GPU is not used by this job.\r\n'
        'Progress appears during the run. Keep the window open. Run it again in the SAME folder to resume.\r\n'
        'Your worker count is saved for this job; it cannot silently change during resume.\r\n'
        'At completion send ONLY the RETURN_TO_OWNER ZIP, containing header, records and progress.\r\n'
        'Never send a private credential, ZoneRushPrivate folder, source tree or Python environment.\r\n'
        'Owner acceptance remains pending; worker primary credit is always0.\r\n'
        'If there is an error, preserve all files and send the error text to the owner.\r\n'
    ).encode('utf8')
    if output.exists() and any(path.name not in files or not path.is_file() for path in output.iterdir()):
        raise ValueError('Delivery output contains unrelated artifacts; use a dedicated wrapper directory')
    for name,body in files.items():
        _write(output/name,body)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as zipped:
        for name,body in sorted(files.items()):
            entry = zipfile.ZipInfo(name,date_time=(2026,1,1,0,0,0))
            entry.compress_type = zipfile.ZIP_DEFLATED
            zipped.writestr(entry,body)
    outer = output.with_name(output.name+'.zip')
    _write(outer,buffer.getvalue())
    return dict(format=runner.FORMAT,slot=config['slot'],work_role=kind,expected_tasks=config['expected_tasks'],
                archive=str(outer),archive_sha256=runner.sha(buffer.getvalue()),archive_bytes=len(buffer.getvalue()),
                inner_archive_sha256=config['inner_archive_sha256'],bundle_sha256=config['bundle_sha256'],
                owner_plan_sha256=config['owner_plan_sha256'],audit_plan_sha256=config['audit_plan_sha256'],
                wrapper_sources={name:runner.sha(body) for name,body in files.items() if name!='worker_payload.zip'},
                jobs_launched=0,primary_credit=0,cuda_used_by_policy=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan',type=Path,required=True)
    parser.add_argument('--shard',required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--audit-plan',type=Path)
    args = parser.parse_args()
    print(runner.canonical(build(args.plan,args.shard,args.output,args.audit_plan)).decode())


if __name__=='__main__':
    main()
