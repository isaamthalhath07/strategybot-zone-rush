"""Root operator: run the already published three phases without idle gaps.

Launch only after observing the original TRAIN owner exit successfully. This
wrapper changes no experiment, outcome rule, source or execution configuration.
It never retries an action, mints a cache certificate or launches an extra game.
Any missing prerequisite or exception stops it for root investigation.
"""
from pathlib import Path
import json
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from deadline_campaign import budget, controller
from deadline_finalization.cache import IntegrityCache, run_phase


def finish(campaign, authority, manifest, cache, output):
    cache._guard()
    if (cache.folder/'advance_error.json').exists():
        raise ValueError('Existing advancer failure requires root investigation')
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    measurements = list(manifest['timing_measurements'])
    stages = sorted(campaign.glob('train_[0-9][0-9][0-9]'))
    if not stages:
        raise ValueError('No complete TRAIN population exists')
    for index, stage in enumerate(stages):
        if stage.name != 'train_%03d' % index or not (stage/'accepted.json').exists():
            raise ValueError('Missing, partial or nonconsecutive TRAIN generation')
        accepted = authority.read('acceptance', stage/'accepted.json')
        measurements.append(accepted['measurement'])
        # Check readiness only; run_phase performs the complete byte verification.
        # Do not hash every proof twice merely to begin the same original phase.
        certificate = authority.read('acceptance', cache.folder/(stage.name+'.json'))
        if certificate.get('stage') != stage.name:
            raise ValueError('A TRAIN integrity certificate has the wrong stage')
    if budget.may_start_generation(controller.now(), measurements, games=8192,
                                   coaching_and_setup_seconds=600):
        raise ValueError('The unchanged timing rule still permits TRAIN')
    if not controller._heldout_absent(campaign):
        raise ValueError('An earlier heldout attempt or decision already exists')
    for action in ('freeze', 'development', 'final'):
        if action == 'final':
            # The separately reviewed read-only advancer certifies completed DEV.
            # Recheck the immutable guard while waiting. The FINAL original
            # function independently enforces timing and every prerequisite.
            while not (cache.folder/'development.json').exists():
                cache._guard()
                if (cache.folder/'advance_error.json').exists():
                    raise ValueError('Completed-DEV certification failed')
                if controller.now() >= budget.FINAL_CUTOFF:
                    raise ValueError('Completed-DEV certificate missed FINAL cutoff')
                time.sleep(5)
            if (cache.folder/'advance_error.json').exists():
                raise ValueError('Advancer failure is present alongside DEV certificate')
        began = time.perf_counter()
        result = run_phase(cache, action)
        body = controller.design.canonical(result)+b'\n'
        with (output/(action+'.json')).open('xb') as stream:
            stream.write(body)
        print(json.dumps(dict(completed_phase=action,
            result_sha256=controller.design.sha(body),
            wall_seconds=time.perf_counter()-began)), flush=True)
    return result


def main():
    campaign, authority, manifest = controller._context(controller.CAMPAIGN)
    cache = IntegrityCache(campaign, authority)
    output = controller.ROOT/'.cache/deadline/finish_phases_001'
    result = finish(campaign, authority, manifest, cache, output)
    print(json.dumps(dict(status='Original primary final decision complete',
        selected=result['selected'], operator_output=str(output))), flush=True)


if __name__ == '__main__':
    main()
