"""Context binding for authenticated play, qualification and independent audit."""
from distributed_campaign import protocol as p
import re

RUNTIME_KEYS = ('implementation', 'version', 'full_version', 'executable_sha256', 'platform')


def runtime_fingerprint(value):
    return p.sha(p.canonical({key: value[key] for key in RUNTIME_KEYS}))


def allowed_qualification_runtime(value):
    if (type(value) is not dict or type(value.get('implementation')) is not str
            or type(value.get('version')) is not str):
        raise ValueError('Malformed runtime qualification metadata')
    return value['implementation'] == 'CPython' and re.fullmatch(r'3\.12\.(?:0|[1-9][0-9]*)', value['version']) is not None


def assignment_payload(bundle):
    body = {key: value for key, value in bundle.items() if key != 'authentication'}
    return dict(campaign_id=bundle['campaign_id'], generation=bundle['generation'], shard_id=bundle['shard_id'],
                work_role=bundle['work_role'], role=bundle['role'], body_sha256=p.sha(p.canonical(body)))


def authenticate_assignment(bundle, credentials):
    from distributed_campaign import auth
    identity = auth.public_identity(credentials)
    if identity != bundle['target_slot']:
        raise ValueError('This assignment belongs to another physical helper slot')
    value = auth.verify(credentials, 'distributed-assignment/v2', bundle['authentication'],
                        expected_slot=identity['slot_id'])
    if value != assignment_payload(bundle):
        raise ValueError('Assignment role/source/tasks/runtime binding changed')
    return identity


def header_payload(header):
    body = {key: value for key, value in header.items() if key != 'authentication'}
    return dict(bundle_sha256=header['bundle_sha256'], shard_id=header['shard_id'],
                work_role=header['work_role'], header_sha256=p.sha(p.canonical(body)))


def result_payload(bundle, header, record):
    fixture = record['game']['fixture'] if bundle['work_role'] == 'qualify' else record['fixture']
    value = dict(campaign_id=bundle['campaign_id'], generation=bundle['generation'],
                 shard_id=bundle['shard_id'], bundle_sha256=header['bundle_sha256'],
                 work_role=bundle['work_role'], fixture=fixture,
                 header_sha256=header_payload(header)['header_sha256'],
                 record_sha256=p.sha(p.canonical(record)))
    if bundle['work_role'] == 'audit':
        creator = bundle['creators'][fixture]
        if creator['physical_slot_id'] == bundle['target_slot']['physical_slot_id']:
            raise ValueError('A physical helper cannot audit its own created game')
        value['creator'] = creator
        value['input_row_sha256'] = p.sha(p.canonical(bundle['input_rows'][fixture]))
    return value
