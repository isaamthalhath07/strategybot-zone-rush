"""Preregister four frozen policies before consuming the unused V1 panel.

This prepares extra controls only. It runs no games, dispatches no jobs, grants
no primary/BMCTS credit and changes neither V1 nor the production bot.
"""
import argparse
import ast
from collections import Counter
import copy
import gzip
import json
import os
from pathlib import Path
import stat
import zipfile

from confirmation_campaign import prepare
from primary_campaign import core

FORMAT = 'zone-rush-extra-architecture-confirmation/2'
BRANCH_COMMIT = 'ae1c29646e7a7293e3ac663da4324be5a80323b0'
BLOCKER = '1bb70109a75e2880bfdf3ac9b6fd8e368b0f3d02b9a3e65de53cef0defa505e5'
FEINT = 'f95dc9fc22660331b1368a876d907f111fd3cb21aef6e3e34315b41e6af94e94'
ARMS = (core.INCUMBENT, prepare.CHALLENGER, BLOCKER, FEINT)
EVIDENCE = core.ROOT/'confirmation_campaign/evidence/architectures_v2'
EVIDENCE_HASHES = {
    'decision.json': 'c4e1e99263ed620f74436cdc5eb85540b55f104e9ae3086e6d48455c79bf6ec4',
    'feint_original.py': FEINT,
    'final_results.json.summary.json': '569c116eabc8a931dd2ed80ce58959536960cdfcb08f393d69c71961a55e82dc',
    'late_final_results.json.gz': 'e9ff577a93102020c6fd8129809b6459bea69ae8dd405c29b44853e097123a2d',
    'late_final_results.json.registration.json': '72ddca49121153377ddeda634426540ac883e7faaa3d8ca11fe70fe656e36ae9',
    'late_final_results.json.summary.json': '37c67da493d42592ffb26173b1a1c18358c7c23df850f6b930752f3f94e52077',
    'late_final_spec.json': '2de45f88af41cffb6ef4cf3419077b3c640a2048d3090b4a8a9afb4c2cc3e2e0',
    'source_archive.zip': '5248b15452932ca2637094fd44d39a43627707c4c31443568e6cfcdd1ad979fb',
    'source_archive_manifest.json': '8421033e63502c511970a341880b00e5bc79815e9b5ec9c10a430ac084b35270',
    'consumed_map_specs.zip': 'b114f25deebe965aed3556e590afe9af87db1884116dc8c5908f93e946aed966',
    'crossbranch_map_coverage.json': 'db5617abaacd0d09da206988eec5fccf2cd03822db4d84dd11f9fd438e7843e0',
}


def branch_evidence():
    for name, expected in EVIDENCE_HASHES.items():
        if core.digest((EVIDENCE/name).read_bytes()) != expected:
            raise ValueError('Pinned branch-selection evidence changed')
    archive_manifest = json.loads((EVIDENCE/'source_archive_manifest.json').read_bytes())
    if archive_manifest['sha256'] != EVIDENCE_HASHES['source_archive.zip']:
        raise ValueError('Branch source archive fingerprint changed')
    coverage = json.loads((EVIDENCE/'crossbranch_map_coverage.json').read_bytes())
    all_orbits = set()
    if (coverage['branch_commit'] != BRANCH_COMMIT or coverage['spec_count'] != 11
            or coverage['spec_archive_sha256'] != EVIDENCE_HASHES['consumed_map_specs.zip']):
        raise ValueError('Cross-branch map coverage changed')
    with zipfile.ZipFile(EVIDENCE/'consumed_map_specs.zip') as archive:
        if sorted(archive.namelist()) != sorted(entry['path'] for entry in coverage['selection_specs']):
            raise ValueError('Cross-branch map source coverage is incomplete')
        for entry in coverage['selection_specs']:
            raw = archive.read(entry['path'])
            spec_data = json.loads(raw)
            orbits = {core.rotation_orbit(fixture['base']) for fixture in spec_data['fixtures']}
            if (core.digest(raw) != entry['sha256'] or sorted(orbits) != entry['rotation_orbits']
                    or entry['map_count'] != len(orbits) or entry['fixture_count'] != len(spec_data['fixtures'])):
                raise ValueError('A cross-branch map recipe differs from its frozen source')
            all_orbits.update(orbits)
    if (sorted(all_orbits) != coverage['rotation_orbits'] or len(all_orbits) != coverage['unique_map_orbits']
            or core.digest(core.canonical(sorted(all_orbits))) != coverage['orbit_sha256']):
        raise ValueError('Cross-branch map orbit fingerprint changed')
    selected = {}
    with zipfile.ZipFile(EVIDENCE/'source_archive.zip') as archive:
        for identity in (BLOCKER, FEINT):
            entries = [entry for entry in archive_manifest['files'] if entry['sha256'] == identity]
            if len(entries) != 1:
                raise ValueError('Selected architecture archive is ambiguous')
            entry = entries[0]
            body = archive.read(entry['path'])
            if core.digest(body) != identity:
                raise ValueError('Archived architecture bytes changed')
            selected[identity] = dict(entry)
    if core.digest((core.ROOT/'tester_bots/blocker.py').read_bytes()) != BLOCKER:
        raise ValueError('Original Blocker control changed')
    def common_core(path):
        tree = ast.parse(path.read_bytes())
        entry = next(node for node in reversed(tree.body) if isinstance(node, ast.FunctionDef) and node.name == 'act')
        for node in ast.walk(entry):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in ('BlockerBot', 'FeintBot'):
                node.func.id = '_SELECTED_BEHAVIOR'
        return ast.dump(tree)
    if common_core(core.ROOT/'tester_bots/blocker.py') != common_core(EVIDENCE/'feint_original.py'):
        raise ValueError('Claimed common Blocker/Feint implementation differs')
    spec = json.loads((EVIDENCE/'late_final_spec.json').read_bytes())
    with gzip.open(EVIDENCE/'late_final_results.json.gz', 'rt', encoding='utf8') as handle:
        result = json.load(handle)
    summary = json.loads((EVIDENCE/'late_final_results.json.summary.json').read_bytes())['summary']
    if (result['registration']['spec'] != spec or not result['registration']['rules']['catch_requires_stay']
            or result['summary'] != summary or len(result['games']) != 5760
            or len(spec['fixtures']) != 1152 or len({core.rotation_orbit(f['base']) for f in spec['fixtures']}) != 24
            or any(row['faults'] for row in result['games'])):
        raise ValueError('Branch selection panel is inconsistent')
    for name, value in summary.items():
        rows = [row for row in result['games'] if row['candidate'] == name]
        if len(rows) != 1152 or sum(row['focal_pw'] for row in rows)/len(rows) != value['mean_pw']:
            raise ValueError('Branch panel mean does not recompute')
    return dict(branch_commit=BRANCH_COMMIT, files=dict(EVIDENCE_HASHES), selected=selected,
                maps=24, games_per_policy=1152, selection_data_only=True,
                excluded_branch_specs=coverage['spec_count'], excluded_branch_map_orbits=len(all_orbits),
                excluded_branch_orbits_sha256=coverage['orbit_sha256'],
                original_blocker_mean_pw=summary['bot_1bb70109a75e']['mean_pw'],
                original_feint_mean_pw=summary['bot_f95dc9fc2266']['mean_pw'],
                incumbent_mean_pw=summary['bot_e8b3682d8b39']['mean_pw']), all_orbits


def _plain(path):
    path = Path(os.path.abspath(path))
    if path.resolve() != path or path.is_symlink():
        raise ValueError('Study paths cannot use links or aliases')
    info = path.lstat()
    if getattr(info, 'st_file_attributes', 0) & 0x400 or not stat.S_ISREG(info.st_mode):
        raise ValueError('Study evidence must be regular files')
    return path


def distribution_roots():
    return [core.ROOT/relative for relative in (
        '.cache/distributed_campaign', '.cache/distributed', '.cache/compute_share',
        '.cache/gpu_farm', '.cache/shared_gpu', 'gpu_farm', 'compute_share/verified_returns')]


def assert_unplayed(directory, registration, roots=None):
    """Fail closed on local V1 execution/return/distribution evidence.

    This is a scoped filesystem check, not proof about deleted/external files.
    The owner must also keep V1 undispatched. V2 never amends V1 in place.
    """
    directory = Path(directory).resolve()
    expected = {'incumbent.py', 'challenger_50d.py', 'registration.json', 'registration.sha256'}
    if {path.name for path in directory.iterdir()} != expected:
        raise ValueError('V1 has execution/distribution or unknown artifacts; do not reuse its holdout')
    files = {path.name: core.digest(_plain(path).read_bytes()) for path in directory.iterdir()}
    identities = {fixture['id'] for fixture in registration['fixtures']}
    control_id = registration['campaign_id']
    def used(value):
        stack = [value]
        while stack:
            item = stack.pop()
            if type(item) is dict:
                fixture = item.get('fixture')
                if item.get('campaign_id') == control_id or (type(fixture) is str and fixture in identities):
                    return True
                stack.extend(item.values())
            elif type(item) is list:
                stack.extend(item)
        return False
    observed = {}
    names = ('bundle', 'dispatch', 'assignment', 'return', 'header', 'record', 'result', 'game', 'receipt',
             'plan', 'qualification', 'approval', 'admission')
    for root in (distribution_roots() if roots is None else map(Path, roots)):
        if not root.exists():
            continue
        for path in root.rglob('*'):
            if not path.is_file() or not any(word in path.name.lower() for word in names):
                continue
            if path.suffix.lower() not in ('.json', '.jsonl', '.zip'):
                continue
            _plain(path)
            body = path.read_bytes()
            observed[str(path.resolve())] = core.digest(body)
            if path.suffix == '.zip':
                with zipfile.ZipFile(path) as archive:
                    for name in archive.namelist():
                        if Path(name).name in ('bundle.json', 'header.json', 'assignment.json') and used(json.loads(archive.read(name))):
                            raise ValueError('V1 was distributed; its maps cannot be reused as unconsumed')
            elif path.suffix == '.jsonl':
                for line in body.splitlines():
                    if line and used(json.loads(line)):
                        raise ValueError('A V1 game/return already exists')
            elif used(json.loads(body)):
                raise ValueError('V1 execution/distribution evidence exists')
    return dict(v1_files=files, checked_roots=[str(Path(p).resolve()) for p in
                (distribution_roots() if roots is None else roots)], observed_artifacts=observed,
                v1_locally_unplayed=True, limitation='Scoped local check; no claim about deleted or external artifacts.')


def _parent(directory, roots=None):
    directory = Path(directory).resolve()
    registration = core.read_sealed(directory/'registration.json')
    if (registration['bmcts_audits'] != 0 or registration['protocol']['bmcts_audits'] != 0
            or registration['protocol']['primary_games_accepted'] != 0
            or registration['protocol']['promoted'] is not False):
        raise ValueError('V1 scope contradicts an unused extra control')
    excluded = core.historical_map_ids()
    prepare.validate(registration, excluded)
    proof = assert_unplayed(directory, registration, roots)
    return registration, proof


def inference_plan():
    comparisons = [dict(first=a, second=b) for i, a in enumerate(ARMS) for b in ARMS[i+1:]]
    return dict(primary_metric='Official Round1 pairwise wins with ties worth one half; equal weight to each map/field/seat/token.',
                paired_comparisons=comparisons, familywise_alpha=.05, comparison_count=6,
                adjustment='Bonferroni: each two-sided interval uses alpha=0.05/6; bootstrap coverage is approximate.',
                per_comparison_alpha=.05/6, bootstrap_replicates=60000, bootstrap_seed=202611091740,
                resampling_unit='Whole map, preserving all fields, seats, tokens and four arms together.',
                percentile_probabilities=[.05/12, 1-.05/12], quantile_method='Empirical inverted-CDF order statistic, ceil(p*B)-1, clamped to0..B-1.',
                order_statistic_indices_zero_based=[249, 59749],
                report='All six contrasts, all arm means, every field mean, worst-field mean and contrast, raw scores, faults and timing.',
                field_intervals='Exploratory/descriptive; no additional simultaneous per-field inference is claimed.',
                promotion='Never automatic. Independent fresh-source/runtime/validity review and a release decision are required.',
                caveat='Bonferroni-labelled descriptive map bootstrap is not universal superiority or a finite-sample familywise coverage proof.')


def _protocol(parent, parent_sha, evidence):
    return dict(format=FORMAT, seed=parent['protocol']['seed'], map_count=len(parent['maps']), fields=list(core.FIELDS),
                candidates=list(ARMS), primary_catalog_sha256=parent['protocol']['primary_catalog_sha256'],
                excluded_orbits_sha256=parent['protocol']['excluded_orbits_sha256'],
                parent_v1_registration_sha256=parent_sha, parent_v1_control_id=parent['campaign_id'],
                opponent_parameter_protocol_id=parent['campaign_id'], source_selection=evidence,
                design='Every unconsumed V1 map/field/seat/token condition crosses all four frozen policies with matched rival parameters and fresh actor identities.',
                implementation_families='Two guarded-Transfer genomes and two behavioral subclasses sharing the archived novel-bot core; not four independent implementations.',
                inference=inference_plan(), primary_games_accepted=0, bmcts_audits=0, promoted=False,
                runtime_qualification_selector='All four arm sources at map0/economic/seat0/token1 and map0/independent/seat1/token2.',
                existing_numeric_only_qualification_sufficient=False,
                registration_grants_dispatch=False,
                execution_gate='Separate owner-approved runtime qualification covering all four exact focal source hashes; qualification uses the eight preregistered study tasks once.')


def _conditions(parent):
    output = {}
    for fixture in parent['fixtures']:
        output.setdefault(fixture['pair_id'], fixture)
    return list(output.values())


def _fixtures(parent, control_id):
    fixtures = []
    for original in _conditions(parent):
        common = {key: copy.deepcopy(original[key]) for key in
                  ('map_id', 'map_index', 'map_family', 'base', 'seat', 'token', 'episode', 'field')}
        pair_key = core.digest(core.canonical([control_id, original['pair_id'], 'four-arm-condition']))
        for identity in ARMS:
            opponents = []
            for spec in original['opponents']:
                instance = copy.deepcopy(spec)
                instance['id'] = core.digest(core.canonical([control_id, spec['pair_parameter_id'], identity, 'fresh-rival']))
                opponents.append(instance)
            fixture = dict(common, candidate=identity, parent_pair_id=original['pair_id'], pair_key=pair_key,
                           pair_id=pair_key, focal_actor_id=core.digest(core.canonical([control_id, pair_key, identity, 'fresh-focal'])),
                           opponents=opponents)
            fixture['id'] = core.digest(core.canonical(fixture))
            fixtures.append(fixture)
    return fixtures


def _qualification(fixtures):
    selected = [fixture['id'] for fixture in fixtures if fixture['map_index'] == 0 and
                (fixture['field'], fixture['seat'], fixture['token']) in (('economic', 0, 1), ('independent', 1, 2))]
    if len(selected) != 8:
        raise ValueError('Runtime qualification recipe must cover exactly eight preregistered tasks')
    return selected


def make(parent_v1_directory, output_directory):
    parent_path, output = Path(parent_v1_directory).resolve(), Path(output_directory).resolve()
    if output.exists() or output.is_relative_to(parent_path):
        raise FileExistsError('Use a fresh separate V2 directory; preserve V1')
    parent, unplayed = _parent(parent_path)
    evidence, selection_orbits = branch_evidence()
    if selection_orbits & {board['rotation_orbit'] for board in parent['maps']}:
        raise ValueError('A V1 board overlaps consumed branch selection; preregister a separate fresh map plan')
    parent_sha = core.digest((parent_path/'registration.json').read_bytes())
    protocol = _protocol(parent, parent_sha, evidence)
    control_id = core.digest(core.canonical(protocol))
    output.mkdir(parents=True, exist_ok=False)
    original_sources = [Path(parent['candidates'][0]['path']), Path(parent['candidates'][1]['path']),
                        core.ROOT/'tester_bots/blocker.py', EVIDENCE/'feint_original.py']
    names = ('incumbent_e8', 'defense_50d', 'original_blocker', 'original_feint')
    candidates = []
    for index, (identity, name, original) in enumerate(zip(ARMS, names, original_sources)):
        body = _plain(original).read_bytes()
        if core.digest(body) != identity:
            raise ValueError('An original source differs from its frozen arm')
        path = output/(name+'.py')
        core.atomic(path, body)
        entry = dict(name=name, path=str(path), sha256=identity, source_path=str(original.resolve()),
                     source_kind='exact standalone bytes', implementation_family='guarded_transfer' if index < 2 else 'archived_novel_core')
        if index < 2:
            entry['genes'] = copy.deepcopy(parent['candidates'][index]['genes'])
        else:
            entry['archive_source'] = copy.deepcopy(evidence['selected'][identity])
        candidates.append(entry)
    fixtures = _fixtures(parent, control_id)
    guards = dict(parent['guards'])
    guards[str(Path(__file__).resolve())] = core.digest(Path(__file__).read_bytes())
    guards.update({str((EVIDENCE/name).resolve()): identity for name, identity in EVIDENCE_HASHES.items()})
    supersession = dict(status='V1 unused and superseded BEFORE any V2 outcomes',
                        parent_v1_registration_sha256=parent_sha, parent_v1_control_id=parent['campaign_id'],
                        replacement_control_id=control_id, parent_v1_unchanged=True,
                        rationale='Architecture-selection evidence justified adding exact original Blocker and Feint before any confirmation outcomes.',
                        local_nonconsumption_check=unplayed)
    registration = dict(format=FORMAT, role='extra_control_assignment', phase='architecture_confirmation', generation=0,
                        campaign_id=control_id, parent_campaign=parent['parent_campaign'], primary_campaign_id=parent['primary_campaign_id'],
                        parent_v1_directory=str(parent_path), parent_v1_registration_sha256=parent_sha,
                        protocol=protocol, candidates=candidates, sources=copy.deepcopy(parent['sources']), guards=guards,
                        rules={'catch_requires_stay': True}, maps=copy.deepcopy(parent['maps']), fixtures=fixtures,
                        required_focal_sources=list(ARMS), runtime_qualification_task_ids=_qualification(fixtures),
                        supersession=supersession, source_discovery_audits=copy.deepcopy(parent['source_discovery_audits']),
                        planned_games=len(fixtures), executed_games=0, primary_games_accepted=0, worker_primary_credit=0,
                        bmcts_audits=0, promotion_allowed=False,
                        counting='Extra complete-match controls only; zero primary credit, zero full BMCTS audits, no automatic release.')
    validate(registration)
    core.seal(output/'registration.json', registration)
    core.seal(output/'v1_unused_superseded.json', supersession)
    return registration


def validate(registration, excluded=(), distribution_roots=None):
    if (registration['format'] != FORMAT or registration['role'] != 'extra_control_assignment'
            or registration['phase'] != 'architecture_confirmation' or registration['generation'] != 0
            or any(type(registration[key]) is not int or registration[key] != 0 for key in
                   ('executed_games', 'primary_games_accepted', 'worker_primary_credit', 'bmcts_audits'))
            or registration['promotion_allowed'] is not False):
        raise ValueError('Architecture controls cannot change mode, credit or release scope')
    parent_path = Path(registration['parent_v1_directory'])
    parent, current_unused = _parent(parent_path, distribution_roots)
    evidence, selection_orbits = branch_evidence()
    parent_sha = core.digest((parent_path/'registration.json').read_bytes())
    expected_protocol = _protocol(parent, parent_sha, evidence)
    identity = core.digest(core.canonical(expected_protocol))
    if (registration['protocol'] != expected_protocol or registration['campaign_id'] != identity
            or registration['parent_v1_registration_sha256'] != parent_sha or registration['maps'] != parent['maps']
            or registration['parent_campaign'] != parent['parent_campaign']
            or registration['primary_campaign_id'] != parent['primary_campaign_id']
            or registration['rules'] != {'catch_requires_stay': True} or registration['sources'] != parent['sources']
            or registration['source_discovery_audits'] != parent['source_discovery_audits']):
        raise ValueError('Architecture source, parent, map or statistical protocol changed')
    expected_guards = dict(parent['guards'])
    expected_guards[str(Path(__file__).resolve())] = core.digest(Path(__file__).read_bytes())
    expected_guards.update({str((EVIDENCE/name).resolve()): digest for name, digest in EVIDENCE_HASHES.items()})
    if registration['guards'] != expected_guards:
        raise ValueError('Architecture source guard coverage changed')
    core.check_guards(expected_guards)
    orbits = {board['rotation_orbit'] for board in registration['maps']}
    if orbits & (set(excluded) | selection_orbits):
        raise ValueError('A consumed/excluded map leaked into architecture confirmation')
    if [candidate['sha256'] for candidate in registration['candidates']] != list(ARMS):
        raise ValueError('Every frozen arm must occur once in its preregistered order')
    for index, candidate in enumerate(registration['candidates']):
        body = _plain(Path(candidate['path'])).read_bytes()
        source = _plain(Path(candidate['source_path'])).read_bytes()
        if core.digest(body) != ARMS[index] or body != source:
            raise ValueError('An architecture source was changed instead of copied exactly')
        if index < 2 and candidate.get('genes') != parent['candidates'][index]['genes']:
            raise ValueError('A Transfer genome changed')
        if index >= 2 and candidate.get('archive_source') != evidence['selected'][ARMS[index]]:
            raise ValueError('Archived architecture lineage changed')
    expected = _fixtures(parent, identity)
    if registration['fixtures'] != expected:
        raise ValueError('A grouped condition, matched opponent, fresh actor or task recipe changed')
    if (registration['required_focal_sources'] != list(ARMS)
            or registration['runtime_qualification_task_ids'] != _qualification(expected)
            or registration['planned_games'] != len(expected)):
        raise ValueError('Task count or architecture-specific runtime qualification coverage changed')
    groups, actor_ids, task_ids, cells = {}, set(), set(), Counter()
    for fixture in expected:
        if fixture['id'] in task_ids:
            raise ValueError('A study task was duplicated')
        task_ids.add(fixture['id'])
        groups.setdefault(fixture['pair_key'], []).append(fixture)
        for actor in [fixture['focal_actor_id']]+[spec['id'] for spec in fixture['opponents']]:
            if actor in actor_ids:
                raise ValueError('An actor identity was reused')
            actor_ids.add(actor)
        cells[fixture['candidate'], fixture['field'], fixture['seat'], fixture['token']] += 1
    if (len(expected) != len(parent['maps'])*4*16*4 or len(groups) != len(parent['maps'])*4*16
            or len(cells) != 4*64 or set(cells.values()) != {len(parent['maps'])}
            or any(len(group) != 4 or {f['candidate'] for f in group} != set(ARMS) for group in groups.values())):
        raise ValueError('The four-arm map/field/seat/token crossing is incomplete')
    supersession = registration['supersession']
    if (supersession['parent_v1_registration_sha256'] != parent_sha or supersession['replacement_control_id'] != identity
            or supersession['parent_v1_control_id'] != parent['campaign_id']
            or supersession['parent_v1_unchanged'] is not True
            or supersession['status'] != 'V1 unused and superseded BEFORE any V2 outcomes'
            or supersession['local_nonconsumption_check']['v1_locally_unplayed'] is not True
            or supersession['local_nonconsumption_check']['v1_files'] != current_unused['v1_files']):
        raise ValueError('The V1 nonconsumption/supersession record changed')
    return dict(games=len(expected), matched_conditions=len(groups), arms=4, maps=len(orbits),
                unique_actor_instances=len(actor_ids), comparisons=6, primary_credit=0, bmcts_audits=0,
                runtime_qualification_tasks=8, executed_games=0, promotion_allowed=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--parent-v1', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    value = make(args.parent_v1, args.output)
    print(json.dumps(validate(value), indent=2), flush=True)


if __name__ == '__main__':
    main()
