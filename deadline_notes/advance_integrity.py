"""Root-only orchestration of the published cache API; no game execution.

Certify each already admitted TRAIN stage once, then completed DEV. Missing or
bad certificates are never overwritten. Final phase still verifies all hashes.
"""
from datetime import datetime,timezone
from pathlib import Path
import json
import sys
import time

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from deadline_campaign import controller,budget
from deadline_finalization.cache import IntegrityCache,FORMAT,ROLE


def main():
    campaign,authority,_=controller._context(controller.CAMPAIGN)
    cache=IntegrityCache(campaign,authority);active=None
    try:
        while datetime.now(timezone.utc)<budget.DEADLINE:
            cache._guard()
            stages=sorted(p.name for p in campaign.glob('train_[0-9][0-9][0-9]') if (p/'accepted.json').exists())
            if (campaign/'development'/'accepted.json').exists():stages.append('development')
            for active in stages:
                target=cache.folder/(active+'.json')
                if target.exists():
                    prior=authority.read('acceptance',target)
                    if prior.get('format')!=FORMAT or prior.get('role')!=ROLE or prior.get('stage')!=active:
                        raise ValueError('An existing certificate has the wrong role or stage')
                    continue
                began=time.perf_counter();result=cache.create(active)
                print(json.dumps(dict(certified_stage=active,wall_seconds=time.perf_counter()-began,
                    proof_files=len(result['proof_tree']['files']),new_games=0,new_actor_callbacks=0)),flush=True)
            if (cache.folder/'development.json').exists():
                print(json.dumps(dict(status='All admitted TRAIN and DEV certificates ready; final phase must rehash them.',new_games=0)),flush=True)
                return
            if (campaign/'final_decision.json').exists():return
            time.sleep(15)
    except BaseException as error:
        payload=dict(stage=active,error_type=type(error).__name__,message=str(error),new_games=0,
                     status='Preserve evidence; no automatic retry, overwrite or fallback')
        controller.frozen._seal(cache.folder/'advance_error.json',payload)
        print(json.dumps(payload),flush=True)
        raise


if __name__=='__main__':main()
