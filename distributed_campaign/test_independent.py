"""Independent bounded adversarial controls; these never earn primary credit.

Existing recorded fixtures are reused as controls. A replay is deliberately not
counted as a newly assigned primary game. No primary runtime is modified here.
"""
import copy
import pickle
from pathlib import Path
import tempfile
import unittest
from unittest import mock
import zipfile

from distributed_campaign import protocol as p
from evolution import oversight, runner
from primary_campaign import core


class IndependentActorBoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        stage = core.ROOT/'.cache/primary/campaign_v1_20261109/train_000'
        if not (stage/'registration.json').exists():
            raise unittest.SkipTest('Recorded local control fixture unavailable')
        cls.registration = core.read_sealed(stage/'registration.json')
        with (stage/'games.jsonl').open('rb') as handle:
            cls.row = p.loads(handle.readline())
        cls.fixture = next(item for item in cls.registration['fixtures']
                           if item['id'] == cls.row['fixture'])
        cls.candidate = next(item for item in cls.registration['candidates']
                             if item['sha256'] == cls.row['candidate'])

    def test_original_auditor_rejects_physically_legal_all_stay_forgery(self):
        """A recomputed score and 320 claimed callbacks do not prove actors ran."""
        row = copy.deepcopy(self.row)
        game = runner.engine.Game(base=self.fixture['base'], start_token=self.fixture['token'],
                                  rules={'catch_requires_stay': True})
        row['actions'] = [['STAY']*4 for _ in range(80)]
        for actions in row['actions']:
            game.step(actions)
        seat = self.fixture['seat']
        row['scores'] = game.score
        row['focal_score'] = game.score[seat]
        row['focal_pw'] = sum(1 if game.score[seat] > other else .5 if game.score[seat] == other else 0
                              for rival, other in enumerate(game.score) if rival != seat)
        runner.verify_row(row, self.candidate, self.fixture)
        with self.assertRaisesRegex(ValueError, 'does not regenerate'):
            oversight.audit_game(self.candidate, self.fixture, self.registration['sources'], row,
                                 regenerate=True)

    def test_all_real_actor_calls_receive_only_four_public_fields(self):
        """Inspect real callback inputs; rival genes/seeds remain controller-only."""
        calls = []
        original = runner.namespace
        original_opponent = runner.opponent

        def wrap(act):
            def checked_act(view):
                self.assertEqual(set(view.__slots__),
                                 {'board', 'bot_id', 'is_priority_token', 'legal_actions'})
                self.assertFalse(hasattr(view, '__dict__'))
                for line in view.board:
                    for cell in line:
                        self.assertEqual(set(cell.__slots__),
                                         {'occupant', 'owner', 'is_upgraded', 'is_home',
                                          'is_frozen', 'base_points'})
                        self.assertFalse(hasattr(cell, '__dict__'))
                calls.append(view.bot_id)
                return act(view)
            return checked_act

        def checked_namespace(path, expected):
            namespace = original(path, expected)
            namespace['act'] = wrap(namespace['act'])
            return namespace

        def checked_opponent(spec, sources):
            act, namespace = original_opponent(spec, sources)
            return (wrap(act) if namespace is None else act), namespace

        runner.init_worker()
        with mock.patch.object(runner, 'namespace', checked_namespace), \
                mock.patch.object(runner, 'opponent', checked_opponent):
            row = runner.play_game(self.candidate, self.fixture, self.registration['sources'])
        runner.verify_row(row, self.candidate, self.fixture)
        for key in ('candidate', 'fixture', 'scores', 'actions', 'focal_pw', 'opponent_ids'):
            self.assertEqual(row[key], self.row[key])
        self.assertEqual(len(calls), 320)
        for bot_id in range(1, 5):
            self.assertEqual(calls.count(bot_id), 80)
        self.assertEqual(sum(item['calls'] for item in row['timing']), 320)
        outcome = oversight.audit_game(self.candidate, self.fixture, self.registration['sources'], row,
                                       regenerate=True)
        self.assertEqual(outcome['callbacks_regenerated'], 320)

    def test_no_partial_or_reassigned_game_is_an_actor_proof(self):
        for mutation in ('partial', 'fixture', 'candidate', 'row_hash'):
            row = copy.deepcopy(self.row)
            proof = dict(fixture=row['fixture'], candidate=row['candidate'],
                         row_sha256=p.sha(p.canonical(row)),
                         proof_kind='dual_referee_fresh_actor_regeneration',
                         all_actors_regenerated=True, referee_sha256=oversight.REFEREE_SHA,
                         engine_sha256=oversight.ENGINE_SHA,
                         oversight_sha256=p.sha((core.ROOT/'evolution/oversight.py').read_bytes()),
                         callbacks_regenerated=320, public_memory_oracles=80)
            if mutation == 'partial':
                proof['callbacks_regenerated'] = 319
            elif mutation == 'row_hash':
                proof['row_sha256'] = '0'*64
            else:
                proof[mutation] = '0'*64
            from primary_campaign import run
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                run.validate_actor_audit(proof, row)

    def test_nonlegacy_source_keeps_real_zero_oracles_and_all320_actor_checks(self):
        from distributed_campaign import proofs
        from primary_campaign import run
        original = next(item for item in self.registration['fixtures'] if item['field'] == 'independent')
        parent = core.ROOT/'.cache/distributed_campaign'
        parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='zero-oracle-', dir=parent) as name:
            path = Path(name)/'control.py'
            body = b'def act(state):\n    return "STAY"\n'
            path.write_bytes(body)
            candidate = dict(path=str(path), sha256=p.sha(body), name='honest_STAY_control')
            fixture = copy.deepcopy(original)
            fixture['candidate'] = candidate['sha256']
            fixture['id'] = p.sha(p.canonical(dict(control='zero-legacy-oracle',
                                                  original=original['id'], candidate=candidate['sha256'])))
            # An honest policy can legitimately track no private-counter belief.
            # It still executes a full game and all 320 calls in both referees.
            row = runner.play_game(candidate, fixture, self.registration['sources'])
            outcome = run.audit_task(candidate, fixture, self.registration['sources'], row)
            self.assertEqual(outcome['callbacks_regenerated'], 320)
            self.assertEqual(outcome['public_memory_oracles'], 0)
            proofs.validate(outcome, row, candidate, fixture, self.registration['sources'])
            invented = dict(outcome, public_memory_oracles=80)
            with self.assertRaisesRegex(ValueError, 'coverage'):
                proofs.validate(invented, row, candidate, fixture, self.registration['sources'])


class IndependentProtocolTests(unittest.TestCase):
    def test_duplicate_json_nonfinite_and_escape_paths_are_rejected(self):
        for body in (b'{"slot":"A","slot":"B"}', b'{"x":NaN}', b'{"x":Infinity}'):
            with self.subTest(body=body), self.assertRaises(ValueError):
                p.loads(body)
        for relative in ('../outside', 'C:/outside', '/outside', 'nested\\outside', '.'):
            with self.subTest(relative=relative), self.assertRaises(ValueError):
                p.safe_path(core.ROOT, relative)


class IndependentRoleBindingTests(unittest.TestCase):
    def setUp(self):
        from distributed_campaign import roles
        self.roles = roles
        self.bundle = dict(campaign_id='a'*64, generation=7, shard_id='b'*64,
                           work_role='audit', role='mechanics_shadow',
                           target_slot=dict(slot_id='auditor', physical_slot_id='laptop_B'),
                           creators={'f'*64: dict(slot_id='creator', physical_slot_id='laptop_A')},
                           input_rows={'f'*64: dict(fixture='f'*64, actions=[['STAY']*4]*80)},
                           files={'evolution/oversight.py': 'c'*64},
                           owner_runtime={'version': '3.12.0'})
        self.header = dict(bundle_sha256='d'*64, shard_id='b'*64, work_role='audit',
                           runtime={'version': '3.12.0'})
        self.proof = dict(fixture='f'*64, callbacks_regenerated=320)

    def test_qualification_admits_only_declared_cpython_312_release_family(self):
        for version in ('3.12.0', '3.12.10', '3.12.99'):
            self.assertTrue(self.roles.allowed_qualification_runtime(
                dict(implementation='CPython', version=version)))
        for version in ('3.11.10', '3.13.0', '3.12', '3.12.x', '3.12.0rc1', '3.12.1.1'):
            with self.subTest(version=version):
                self.assertFalse(self.roles.allowed_qualification_runtime(
                    dict(implementation='CPython', version=version)))
        self.assertFalse(self.roles.allowed_qualification_runtime(
            dict(implementation='PyPy', version='3.12.0')))

    def test_distinct_labels_cannot_hide_same_physical_auditor_and_creator(self):
        self.bundle['target_slot']['physical_slot_id'] = 'laptop_A'
        with self.assertRaisesRegex(ValueError, 'cannot audit its own'):
            self.roles.result_payload(self.bundle, self.header, self.proof)

    def test_worker_blocks_same_physical_audit_before_calling_the_auditor(self):
        from distributed_campaign import worker
        self.bundle['target_slot']['physical_slot_id'] = 'laptop_A'
        with mock.patch.object(worker, '_BUNDLE', self.bundle), \
                mock.patch.object(worker, 'audit_record') as auditor:
            with self.assertRaisesRegex(ValueError, 'cannot audit its own'):
                worker.do_task(dict(id='f'*64))
            auditor.assert_not_called()

    def test_assignment_digest_covers_source_runtime_rows_and_physical_identity(self):
        expected = self.roles.assignment_payload(self.bundle)
        for mutation in ('campaign', 'generation', 'source', 'version', 'row', 'physical', 'work_role'):
            changed = copy.deepcopy(self.bundle)
            if mutation == 'campaign':
                changed['campaign_id'] = '0'*64
            elif mutation == 'generation':
                changed['generation'] += 1
            elif mutation == 'source':
                changed['files']['evolution/oversight.py'] = '0'*64
            elif mutation == 'version':
                changed['owner_runtime']['version'] = '3.13.0'
            elif mutation == 'row':
                changed['input_rows']['f'*64]['actions'][0] = ['NORTH']*4
            elif mutation == 'physical':
                changed['target_slot']['physical_slot_id'] = 'laptop_C'
            else:
                changed['work_role'] = 'play'
            with self.subTest(mutation=mutation):
                self.assertNotEqual(self.roles.assignment_payload(changed), expected)

    def test_result_digest_binds_original_transcript_header_and_context(self):
        expected = self.roles.result_payload(self.bundle, self.header, self.proof)
        for mutation in ('campaign', 'generation', 'input_row', 'proof', 'header', 'creator'):
            bundle, header, proof = copy.deepcopy((self.bundle, self.header, self.proof))
            if mutation == 'campaign':
                bundle['campaign_id'] = '0'*64
            elif mutation == 'generation':
                bundle['generation'] += 1
            elif mutation == 'input_row':
                bundle['input_rows']['f'*64]['actions'][0] = ['NORTH']*4
            elif mutation == 'proof':
                proof['callbacks_regenerated'] = 319
            elif mutation == 'header':
                header['runtime']['version'] = '3.13.0'
            else:
                bundle['creators']['f'*64]['physical_slot_id'] = 'laptop_C'
            with self.subTest(mutation=mutation):
                self.assertNotEqual(self.roles.result_payload(bundle, header, proof), expected)


class IndependentAuthenticationTests(unittest.TestCase):
    def test_study_binding_precedes_issuance_and_rejects_second_output(self):
        from distributed_campaign import control
        study = self.directory/'b'
        study.mkdir()
        registration = study/'registration.json'
        core.seal(registration, {'synthetic_mechanics_only': True})
        output = self.directory/'bound-output'
        canonical = study/'distributed_control_v2'
        entered = []

        def issued(*args):
            binding = control._read(self.registry, 'study-binding', canonical/'binding.json')
            self.assertEqual(binding, control._study_binding(registration, output, ['creator'],
                                                            self.provisioned['registry_path']))
            with self.assertRaises(p.ResultBusy):
                with p.ResultLease(canonical):
                    pass
            entered.append(True)
            return {'synthetic_mechanics_only': True}

        # No policy, package, approval, or game is created. Full study validation
        # is mocked solely to probe the new BEFORE-issuance reservation gate.
        with mock.patch('confirmation_campaign.architectures.validate', return_value=True), \
                mock.patch.object(control, '_prepare_locked', side_effect=issued):
            control.prepare(registration, self.provisioned['registry_path'], output, ['creator'], {})
            snapshot = (canonical/'binding.json').read_bytes()
            for changed_output, helpers in ((self.directory/'another-output', ['creator']),
                                             (output, ['auditor'])):
                with self.assertRaisesRegex(ValueError, 'already reserved another canonical'):
                    control.prepare(registration, self.provisioned['registry_path'], changed_output, helpers, {})
            self.assertEqual(len(entered), 1)
            control.prepare(registration, self.provisioned['registry_path'], output, ['creator'], {})
            self.assertEqual(len(entered), 2)
            self.assertEqual((canonical/'binding.json').read_bytes(), snapshot)
            # Copying even a correctly signed plan to a second output cannot
            # bypass the study-owned pointer in _load.
            copied = self.directory/'copied-plan/plan.json'
            plan = dict(registry_path=self.provisioned['registry_path'], controller_sources=control._pins(),
                        role='extra_control_assignment', primary_games_accepted=0,
                        source_registration_path=str(registration), helpers=['creator'],
                        source_registration_sha256=p.sha(registration.read_bytes()))
            core.seal(copied, control._sign(self.registry, 'plan', plan))
            with self.assertRaisesRegex(ValueError, 'another canonical controller output'):
                control._load(copied)
            # Self-consistent file hashes do not authorize changing the binding.
            tampered = p.loads(snapshot)
            tampered['payload']['canonical_output'] = str(self.directory/'another-output')
            body = p.canonical(tampered)+b'\n'
            (canonical/'binding.json').write_bytes(body)
            (canonical/'binding.sha256').write_text(p.sha(body)+'\n')
            with self.assertRaises(self.auth.AuthUnavailable):
                control.prepare(registration, self.provisioned['registry_path'], output, ['creator'], {})
            self.assertEqual(len(entered), 2)

    def _local_primary(self):
        stage = core.ROOT/'.cache/primary/campaign_v1_20261109/train_000'
        if not all((stage/name).exists() for name in ('registration.json', 'games.jsonl')):
            self.skipTest('Private local recorded controls unavailable; no campaign acceptance is inferred')
        return stage

    @classmethod
    def setUpClass(cls):
        from distributed_campaign import auth
        cls.auth = auth
        parent = core.ROOT/'.cache/distributed_campaign'
        parent.mkdir(parents=True, exist_ok=True)
        cls.temporary = tempfile.TemporaryDirectory(prefix='independent-auth-', dir=parent)
        cls.directory = Path(cls.temporary.name).resolve()
        if not cls.directory.is_relative_to(parent.resolve()):
            raise ValueError('Independent test path escaped ignored workspace')
        info = auth.provision(cls.directory/'authority',
                              dict(creator='laptop_A', auditor='laptop_B'))
        cls.registry = auth.load_registry(info['registry_path'])
        cls.creator = auth.load_credentials(info['credentials']['creator'])
        cls.auditor = auth.load_credentials(info['credentials']['auditor'])
        cls.provisioned = info

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, 'temporary'):
            cls.temporary.cleanup()

    def test_real_private_key_mac_rejects_role_context_payload_and_other_key(self):
        payload = dict(campaign_id='a'*64, generation=3, shard_id='b'*64,
                       source_sha256='c'*64, runtime_fingerprint='d'*64,
                       row_sha256='e'*64, fixture='f'*64, callbacks_regenerated=320)
        purpose = 'distributed-result/audit/v2'
        signed = self.auth.sign(self.auditor, purpose, payload)
        self.assertEqual(self.auth.verify(self.registry, purpose, signed, expected_slot='auditor'), payload)
        for name in payload:
            changed = copy.deepcopy(signed)
            changed['payload'][name] = 0 if type(payload[name]) is int else '0'*64
            with self.subTest(changed=name), self.assertRaises(self.auth.AuthUnavailable):
                self.auth.verify(self.registry, purpose, changed, expected_slot='auditor')
        with self.assertRaises(self.auth.AuthUnavailable):
            self.auth.verify(self.registry, 'distributed-result/play/v2', signed)
        with self.assertRaises(self.auth.AuthUnavailable):
            self.auth.verify(self.registry, purpose, signed, expected_slot='creator')
        wrong_key = copy.deepcopy(signed)
        wrong_key['mac'] = self.auth.sign(self.creator, purpose, payload)['mac']
        with self.assertRaises(self.auth.AuthUnavailable):
            self.auth.verify(self.registry, purpose, wrong_key)
        wrong_physical = copy.deepcopy(signed)
        wrong_physical['physical_slot_id'] = 'laptop_A'
        with self.assertRaises(self.auth.AuthUnavailable):
            self.auth.verify(self.registry, purpose, wrong_physical)

    def test_authentication_capabilities_cannot_be_pickled_into_actor_jobs(self):
        for capability in (self.registry, self.creator, self.auditor):
            with self.subTest(type=type(capability).__name__):
                self.assertEqual(repr(capability), '<private distributed authentication capability>')
                with self.assertRaises(TypeError):
                    pickle.dumps(capability)
                with self.assertRaises(TypeError):
                    copy.deepcopy(capability)

    def test_helper_signatures_cannot_be_reused_as_owner_runtime_approval(self):
        payload = dict(approved=True, slot=dict(slot_id='auditor', physical_slot_id='laptop_B'))
        purpose = 'distributed-runtime-approval/v2'
        helper = self.auth.sign(self.auditor, purpose, payload)
        with self.assertRaises(self.auth.AuthUnavailable):
            self.auth.verify_owner(self.registry, purpose, helper)
        converted = dict(authority_id=self.provisioned['authority_id'],
                         payload=copy.deepcopy(payload), mac=helper['mac'])
        with self.assertRaises(self.auth.AuthUnavailable):
            self.auth.verify_owner(self.registry, purpose, converted)
        owner = self.auth.sign_owner(self.registry, purpose, payload)
        self.assertEqual(self.auth.verify_owner(self.registry, purpose, owner), payload)
        with self.assertRaises(self.auth.AuthUnavailable):
            self.auth.verify(self.registry, purpose, owner)
        with self.assertRaises(self.auth.AuthUnavailable):
            self.auth.verify_owner(self.registry, purpose+'/other', owner)

    def test_numeric_runtime_scope_rejects_chained_assignment_and_unbounded_genes(self):
        from distributed_campaign import owner
        body = (core.ROOT/'bot.py').read_bytes()
        logic, _ = oversight.stripped_tree(body)
        # Synthetic owner authorization exercises ONLY source-family matching;
        # it is not an executed qualification, transport plan, or primary work.
        value = dict(slot=dict(slot_id='creator', physical_slot_id='laptop_A'),
                     qualification_context=owner.qualification_context(), approved=True,
                     all_recorded_actions_equal=True, full_audit_callbacks=2560,
                     canaries_required=True, runtime=p.runtime(), focal_sources=[],
                     numeric_policy_family_qualified=True, policy_logic_sha256=p.sha(logic.encode()))
        envelope = self.auth.sign_owner(self.registry, 'distributed-runtime-approval/v2', value)
        changed = (body.replace(b'\nCONFIG =', b'\nCONFIG = deque =', 1),
                   body.replace(b"'depth': 3,", b"'depth': 1000,", 1))
        for index, modified in enumerate(changed):
            self.assertNotEqual(modified, body)
            path = self.directory/('invalid-family-%d.py' % index)
            path.write_bytes(modified)
            candidate = dict(path=str(path), sha256=p.sha(modified))
            with self.subTest(index=index), self.assertRaises((ValueError, KeyError)):
                owner.approved_runtime(self.registry, 'creator', envelope, [candidate])

    def test_authenticated_package_contains_no_owner_or_helper_key_material(self):
        from distributed_campaign import owner, roles
        stage = self._local_primary()
        registration = core.read_sealed(stage/'registration.json')
        with (stage/'games.jsonl').open('rb') as handle:
            row = p.loads(handle.readline())
        fixture = next(item for item in registration['fixtures'] if item['id'] == row['fixture'])
        # This single-fixture envelope exercises packaging only. It is NOT a
        # complete eight-genotype runtime qualification or a primary task.
        registration = dict(registration, fixtures=[fixture])
        distribution = owner.build_shards(registration, self.directory/'package', ['creator'],
                                           role='runtime_qualification', registry=self.registry,
                                           work_role='qualify', expected_rows={fixture['id']: row})
        shard = distribution['shards'][0]
        bundle = p.verify_bundle(shard['bundle_directory'], shard['bundle_sha256'])
        self.assertEqual(roles.authenticate_assignment(bundle, self.creator),
                         dict(slot_id='creator', physical_slot_id='laptop_A'))
        registry_path = Path(self.provisioned['registry_path'])
        record = p.loads(registry_path.read_bytes())
        secrets = [(registry_path.parent/record['owner_key']['key_file']).read_bytes()]
        for slot in record['slots'].values():
            secrets.append((registry_path.parent/slot['key_file']).read_bytes())
        with zipfile.ZipFile(shard['archive']) as zipped:
            names = zipped.namelist()
            self.assertFalse(any('.cache/' in name or '.authority/' in name or name.endswith('.key')
                                 or name.endswith('registry.json') or 'credentials/' in name
                                 or name.endswith('owner.py') for name in names))
            for name in names:
                body = zipped.read(name)
                for secret in secrets:
                    # Boolean assertion avoids including any secret in errors.
                    self.assertFalse(secret in body or secret.hex().encode() in body,
                                     'A private key appeared in an archive member')
        self.assertEqual(bundle['worker_primary_credit'], 0)

    def test_runtime_qualification_rejects_rehashed_fake_source_acceptance(self):
        from distributed_campaign import qualification
        original_stage = self._local_primary()
        registration = core.read_sealed(original_stage/'registration.json')
        fields = list(core.FIELDS)
        selected = [next(item for item in registration['fixtures']
                         if item['candidate'] == candidate['sha256']
                         and item['field'] == fields[index % len(fields)])
                    for index, candidate in enumerate(registration['candidates'])]
        wanted, rows = {item['id'] for item in selected}, {}
        with (original_stage/'games.jsonl').open('rb') as handle:
            for line in handle:
                row = p.loads(line)
                if row['fixture'] in wanted:
                    rows[row['fixture']] = row
                if len(rows) == len(wanted):
                    break
        self.assertEqual(len(rows), 8)
        # Rehashing eight genuine controls alongside an empty actor-proof log
        # and a manually approved header must not create an accepted cohort.
        fake = self.directory/'forged-cohort/train_000'
        fake.mkdir(parents=True)
        core.seal(fake/'registration.json', dict(registration, fixtures=selected))
        (fake/'games.jsonl').write_bytes(b''.join(p.canonical(row)+b'\n' for row in rows.values()))
        (fake/'actor_audits.jsonl').write_bytes(b'')
        core.seal(fake/'audit.json', dict(approved=True,
                  registration_sha256=p.sha((fake/'registration.json').read_bytes()),
                  games_sha256=p.sha((fake/'games.jsonl').read_bytes()),
                  actor_audits_sha256=p.sha(b'')))
        output = self.directory/'forged-qualification-packets'
        with self.assertRaises((ValueError, FileNotFoundError)):
            qualification.prepare(fake, self.provisioned['registry_path'], output, slots=['creator'])
        self.assertFalse(output.exists(), 'Rejected source must not mint qualification packets')

    def test_runtime_qualification_binds_directory_to_actual_generation(self):
        from distributed_campaign import qualification
        stage = self._local_primary()
        registration = core.read_sealed(stage/'registration.json')
        fake = self.directory/'copied-source/train_001'
        fake.mkdir(parents=True)
        core.seal(fake/'registration.json', registration)
        output = self.directory/'copied-source-packets'
        with self.assertRaisesRegex(ValueError, 'directory/generation'):
            qualification.prepare(fake, self.provisioned['registry_path'], output, slots=['creator'])
        self.assertFalse(output.exists())

    def _signed_control(self):
        """One genuine existing control, never a complete runtime approval."""
        from distributed_campaign import owner, roles
        from primary_campaign import run
        stage = self._local_primary()
        registration = core.read_sealed(stage/'registration.json')
        with (stage/'games.jsonl').open('rb') as handle:
            row = p.loads(handle.readline())
        fixture = next(item for item in registration['fixtures'] if item['id'] == row['fixture'])
        registration = dict(registration, fixtures=[fixture])
        name = p.sha(self.id().encode())[:8]
        output = self.directory/name
        distribution = owner.build_shards(registration, output/'package', ['creator'],
                                           role='runtime_qualification', registry=self.registry,
                                           work_role='qualify', expected_rows={fixture['id']: row})
        shard = distribution['shards'][0]
        bundle = p.verify_bundle(shard['bundle_directory'], shard['bundle_sha256'])
        header = dict(format=p.FORMAT, bundle_sha256=shard['bundle_sha256'], shard_id=shard['id'],
                      campaign_id=registration['campaign_id'], generation=registration['generation'],
                      role='runtime_qualification', work_role='qualify', runtime=p.runtime(), workers=1,
                      worker_primary_credit=0, bmcts_audits=0,
                      slot=dict(slot_id='creator', physical_slot_id='laptop_A'))
        header['authentication'] = self.auth.sign(self.creator, 'distributed-worker-header/v2',
                                                   roles.header_payload(header))
        proof = run.audit_task(next(item for item in registration['candidates']
                                    if item['sha256'] == row['candidate']), fixture, registration['sources'], row)
        record = dict(game=row, audit=proof)
        entry = dict(record=record, authentication=self.auth.sign(
            self.creator, 'distributed-result/qualify/v2', roles.result_payload(bundle, header, record)))
        results = output/'results'
        results.mkdir()
        (results/'header.json').write_bytes(p.canonical(header)+b'\n')
        (results/'records.jsonl').write_bytes(p.canonical(entry)+b'\n')
        plan = dict(role='runtime_qualification', campaign_id=registration['campaign_id'],
                    generation=registration['generation'], distribution=distribution,
                    registry_path=self.provisioned['registry_path'])
        return owner, roles, plan, registration, shard, bundle, header, entry, results

    def test_owner_checks_issued_context_even_when_helper_resigns_changed_header(self):
        owner, roles, plan, registration, shard, bundle, header, entry, results = self._signed_control()
        rows, _, _ = owner.validate_result(plan, registration, shard['id'], results, self.registry)
        self.assertEqual(len(rows), 1)
        for change in ('campaign_id', 'generation', 'bundle_sha256', 'work_role', 'runtime',
                       'slot', 'worker_primary_credit'):
            bad = copy.deepcopy(header)
            if change == 'generation':
                bad[change] += 1
            elif change == 'runtime':
                bad['runtime']['version'] = '3.13.0'
            elif change == 'slot':
                bad['slot']['physical_slot_id'] = 'laptop_B'
            elif change == 'worker_primary_credit':
                bad[change] = 2000000
            elif change == 'work_role':
                bad[change] = 'play'
            else:
                bad[change] = '0'*64
            bad['authentication'] = self.auth.sign(self.creator, 'distributed-worker-header/v2',
                                                   roles.header_payload(bad))
            changed_entry = copy.deepcopy(entry)
            changed_entry['authentication'] = self.auth.sign(self.creator, 'distributed-result/qualify/v2',
                roles.result_payload(bundle, bad, changed_entry['record']))
            (results/'header.json').write_bytes(p.canonical(bad)+b'\n')
            (results/'records.jsonl').write_bytes(p.canonical(changed_entry)+b'\n')
            with self.subTest(change=change), self.assertRaises(ValueError):
                owner.validate_result(plan, registration, shard['id'], results, self.registry)

    def test_owner_rejects_signed_incomplete_foreign_and_duplicate_actor_records(self):
        owner, roles, plan, registration, shard, bundle, header, entry, results = self._signed_control()
        for change in ('callbacks', 'row_hash', 'referee', 'candidate', 'fixture', 'key'):
            changed = copy.deepcopy(entry)
            record = changed['record']
            if change == 'callbacks':
                record['audit']['callbacks_regenerated'] = 319
            elif change == 'row_hash':
                record['audit']['row_sha256'] = '0'*64
            elif change == 'referee':
                record['audit']['referee_sha256'] = '0'*64
            elif change == 'candidate':
                record['game']['candidate'] = '0'*64
            elif change == 'fixture':
                record['game']['fixture'] = '0'*64
            signing_key = self.auditor if change == 'key' else self.creator
            changed['authentication'] = self.auth.sign(signing_key, 'distributed-result/qualify/v2',
                                                       roles.result_payload(bundle, header, record))
            (results/'records.jsonl').write_bytes(p.canonical(changed)+b'\n')
            with self.subTest(change=change), self.assertRaises(ValueError):
                owner.validate_result(plan, registration, shard['id'], results, self.registry)
        (results/'records.jsonl').write_bytes((p.canonical(entry)+b'\n')*2)
        with self.assertRaisesRegex(ValueError, 'bound|complete|Duplicate'):
            owner.validate_result(plan, registration, shard['id'], results, self.registry)
        (results/'records.jsonl').write_bytes(p.canonical(entry))
        with self.assertRaisesRegex(ValueError, 'complete|stable'):
            owner.validate_result(plan, registration, shard['id'], results, self.registry)

    def test_canonical_gold_reuses_outputs_and_never_resubmits_corrupt_completed_work(self):
        from confirmation_campaign import architectures
        from distributed_campaign import qualification
        from primary_campaign import run
        original = core.read_sealed(self._local_primary()/'registration.json')
        paths = [core.ROOT/'bot.py',
                 core.ROOT/'.cache/confirmation/architectures_v2_001/defense_50d.py',
                 core.ROOT/'tester_bots/blocker.py', architectures.EVIDENCE/'feint_original.py']
        if not all(path.exists() for path in paths):
            self.skipTest('Private four-source mechanics fixture unavailable; no study execution is inferred')
        candidates = [dict(name='mechanics_arm_%d' % i, path=str(path), sha256=p.sha(path.read_bytes()))
                      for i, path in enumerate(paths)]
        fixtures = []
        for field in ('economic', 'independent'):
            template = next(item for item in original['fixtures'] if item['field'] == field)
            for candidate in candidates:
                fixture = copy.deepcopy(template)
                fixture['candidate'] = candidate['sha256']
                fixture['id'] = p.sha(p.canonical(dict(control='independent-gold-mechanics',
                                                      field=field, candidate=candidate['sha256'],
                                                      original=template['id'])))
                fixtures.append(fixture)
        registration = dict(format='independent-mechanics-control-only', campaign_id='9'*64, generation=0,
                            candidates=candidates, fixtures=fixtures, sources=original['sources'],
                            required_focal_sources=[item['sha256'] for item in candidates],
                            runtime_qualification_task_ids=[item['id'] for item in fixtures])
        study = self.directory/'g'
        study.mkdir()
        registration_path = study/'registration.json'
        core.seal(registration_path, registration)
        # This positive fixture MOCKS full-study admission. All eight actual
        # controls use OLD TRAINING boards and DIFFERENT IDs from V2's reserved
        # study tasks. It consumes zero real study/primary outcomes.
        with mock.patch.object(architectures, 'validate', return_value={'mechanics_only': True}), \
                mock.patch.object(run.runner, 'play_game', wraps=run.runner.play_game) as play:
            first = qualification.prepare_control(registration_path, self.provisioned['registry_path'],
                                                   self.directory/'out1', 'creator', slots=[])
            self.assertEqual(first['newly_executed_study_games'], 8)
            self.assertEqual(play.call_count, 8)
            gold = study/'runtime_gold_v2'
            snapshot = {str(path.relative_to(gold)): (path.read_bytes(), path.stat().st_mtime_ns)
                        for path in gold.rglob('*') if path.is_file()}
            play.reset_mock()
            resumed = qualification.prepare_control(registration_path, self.provisioned['registry_path'],
                                                     self.directory/'out1', 'creator', slots=[])
            repackaged = qualification.prepare_control(registration_path, self.provisioned['registry_path'],
                                                        self.directory/'out2', 'creator', slots=[])
            self.assertEqual(resumed['newly_executed_study_games'], 0)
            self.assertEqual(repackaged['newly_executed_study_games'], 0)
            self.assertEqual(play.call_count, 0)
            self.assertEqual(snapshot, {str(path.relative_to(gold)): (path.read_bytes(), path.stat().st_mtime_ns)
                                       for path in gold.rglob('*') if path.is_file()})
            witness, records = qualification.read_control_gold(registration_path, self.registry)
            self.assertEqual(len(records), 8)
            self.assertEqual(sum(item['audit']['callbacks_regenerated'] for item in records.values()), 2560)
            self.assertTrue(witness['different_physical_peer_audit_still_required_for_distributed_study'])
            self.assertEqual(witness['primary_games_accepted'], 0)
            # A completed HMAC witness proves this task already existed. Even
            # losing BOTH the row and started marker must not make it new work.
            log = gold/'gold_records.jsonl'
            lines = log.read_bytes().splitlines(keepends=True)
            missing = fixtures[-1]['id']
            log.write_bytes(b''.join(lines[:-1]))
            marker = gold/'started'/(missing+'.json')
            marker.unlink()
            marker.with_suffix('.sha256').unlink()
            with self.assertRaises(ValueError):
                qualification.prepare_control(registration_path, self.provisioned['registry_path'],
                                               self.directory/'out3', 'creator', slots=[])
            self.assertEqual(play.call_count, 0, 'Completed witness corruption caused a consumed game to rerun')


if __name__ == '__main__':
    unittest.main()
