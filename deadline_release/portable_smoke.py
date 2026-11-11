"""Explicit1..2 ordinary process smoke games; zero strength/primary credit."""
import argparse
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parents[1]


def signature(view):
    return (view.bot_id,view.is_priority_token,tuple(view.legal_actions),
        tuple((c.occupant,c.owner,c.is_upgraded,c.is_home,c.is_frozen,c.base_points) for row in view.board for c in row))


def main():
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument('--games',type=int,choices=(1,2),default=1)
    parser.add_argument('--output',default='validation/smoke_result.json'); args=parser.parse_args(); sys.path.insert(0,str(ROOT))
    if sys.version_info[:2]!=(3,12): raise SystemExit('Use Python3.12 for this release.')
    from simulator import server
    from tests import reference_engine as engine
    destination=(ROOT/args.output).resolve()
    if not destination.is_relative_to(ROOT/'validation'): raise ValueError('Smoke output must stay in validation/')
    if destination.exists(): raise FileExistsError('Preserve completed/failed smoke evidence; choose a fresh output file')
    destination.parent.mkdir(parents=True,exist_ok=True)
    manifest=json.loads((ROOT/'release_manifest.json').read_bytes()); selected=(ROOT/'bot.py').read_bytes()
    if hashlib.sha256(selected).hexdigest()!=manifest['bot_sha256']: raise ValueError('Selected source bytes changed')
    package_body=(ROOT/'package_manifest.json').read_bytes(); package=json.loads(package_body)
    def source_guard():
        for name,expected in package['files'].items():
            if hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=expected: raise ValueError('Packaged source changed: '+name)
    source_guard()
    evidence=[]; began=time.perf_counter(); app=None; active=None
    try:
        for index in range(args.games):
            app=server.App(history_dir=ROOT/'validation'/'smoke_history')
            state=app.new(dict(seed=2026110971+index,seat=index+1,start_token=index+1,view='ai')); identifier=state['game_id']
            game=engine.Game(base=app.game.g.base,start_token=index+1,rules={'catch_requires_stay':True})
            active=dict(game_id=identifier,completed_turns=0,actual_ai_callbacks=0,fresh_replay_callbacks=0)
            modules={}
            for seat in app.game.workers:
                name='smoke_replay_%d_%d'%(index,seat); spec=importlib.util.spec_from_file_location(name,ROOT/'bot.py')
                module=importlib.util.module_from_spec(spec); sys.modules[name]=module; spec.loader.exec_module(module); modules[seat]=module
            callbacks=0; replay_callbacks=0; actual_max_ms=0.; replay_max_ms=0.; oracle_checks=0
            for turn in range(1,81):
                assert set(state)=={'game_id','turn','over','observation'}
                assert set(state['observation'])=={'board','bot_id','is_priority_token','legal_actions'}
                observations={seat:app.game.g.observation(seat) for seat in app.game.workers}
                requested={}
                for seat,module in modules.items():
                    raw=observations[seat]
                    board=[[engine.Cell(*cell) for cell in row] for row in raw['board']]
                    view=engine.View(board,raw['bot_id'],raw['is_priority_token'],list(raw['legal_actions']))
                    before=signature(view); started=time.perf_counter(); requested[seat]=module.act(view); elapsed=time.perf_counter()-started
                    if signature(view)!=before: raise ValueError('Replay mutated public input')
                    if elapsed>(2 if turn==1 else .2): raise ValueError('Replay callback deadline')
                    replay_max_ms=max(replay_max_ms,elapsed*1000)
                    if requested[seat] not in raw['legal_actions']: raise ValueError('Replay returned illegal action')
                    if getattr(module,'_input_failures',0) or getattr(module,'_policy_failures',0): raise ValueError('Replay policy fallback')
                    memory=getattr(module,'_history',{}).get(seat,{})
                    if 'cooldown_possible' in memory:
                        if (memory.get('inference_failures',0) or memory['progress']!=game.prog[seat-1]
                                or memory['scores'][1:]!=game.score
                                or any(game.cd[i] not in memory['cooldown_possible'][i+1] for i in range(4))):
                            raise ValueError('Supported replay memory oracle mismatch')
                        oracle_checks+=1
                    replay_callbacks+=1; active['fresh_replay_callbacks']=replay_callbacks
                state=app.action(dict(game_id=identifier,turn=turn,action='STAY',view='ai'))
                active['actual_ai_callbacks']+=len(app.game.workers); active['completed_turns']=turn
                if app.game.faults: raise ValueError('Actual simulator worker fault')
                transcript=app.history_export(identifier); record=transcript['turns'][-1]
                for seat,action in requested.items():
                    if record['used'][seat-1]!=action: raise ValueError('Exact fresh source replay disagrees with actual worker')
                    if record['observations'][str(seat)]!=observations[seat]: raise ValueError('Worker public input changed')
                    callback=record['bots'][seat-1]
                    if callback['status']!='ok' or callback['used']!=callback['chosen']: raise ValueError('Actual worker substituted action')
                    if type(callback['ms']) not in (int,float) or not math.isfinite(callback['ms']) or callback['ms']<0 or callback['ms']>(2000 if turn==1 else 200): raise ValueError('Actual worker deadline')
                    actual_max_ms=max(actual_max_ms,callback['ms'])
                    callbacks+=1
                game.step(record['used'])
                for field in ('base','owner','upg','home','pos','frozen','cd','prog','score','turn','token'):
                    if getattr(game,field)!=getattr(app.game.g,field): raise ValueError('Independent referee disagreement: '+field)
                if game.income!=app.game.g.income(): raise ValueError('Independent income disagreement')
                for seat in range(1,5):
                    if set(game.legal(seat-1))!=set(app.game.g.legal(seat-1)): raise ValueError('Independent legal-action disagreement')
            if not state['over'] or not game.over(): raise ValueError('Smoke game incomplete')
            history_file='validation/smoke_history/'+identifier+'.jsonl'
            evidence.append(dict(game_id=identifier,turns=80,actual_ai_callbacks=callbacks,fresh_replay_callbacks=replay_callbacks,
                                 actual_max_callback_ms=actual_max_ms,replay_max_callback_ms=replay_max_ms,
                                 supported_memory_oracle_checks=oracle_checks,faults=0,dual_referee_turns=80,
                                 history_file=history_file,history_sha256=hashlib.sha256((ROOT/history_file).read_bytes()).hexdigest()))
            app.close(); app=None; active=None
        source_guard()
        report=dict(format='portable-process-smoke/1',passed=True,bot_sha256=manifest['bot_sha256'],games=evidence,
                    package_manifest_sha256=hashlib.sha256(package_body).hexdigest(),
                    wall_seconds=time.perf_counter()-began,ordinary_worker_games=args.games,primary_games=0,
                    scope='Ordinary process/interface/recording smoke, not strength evidence or new research game credit.')
    except BaseException as error:
        report=dict(format='portable-process-smoke/1',passed=False,bot_sha256=manifest['bot_sha256'],completed_games=evidence,
                    active_game=active,exception_type=type(error).__name__,message=str(error),primary_games=0)
        destination.write_text(json.dumps(report,sort_keys=True,indent=2)+'\n',encoding='utf8'); raise
    finally:
        if app is not None: app.close()
    if (ROOT/'bot.py').read_bytes()!=selected: raise ValueError('Selected source changed during smoke')
    destination.write_text(json.dumps(report,sort_keys=True,indent=2)+'\n',encoding='utf8'); print(json.dumps(report,sort_keys=True))


if __name__=='__main__': main()
