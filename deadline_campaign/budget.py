"""Choose volume from timings alone, while reserving complete heldout panels."""
from datetime import datetime,timedelta,timezone
import math

START = datetime(2026,11,9,1,43,39,tzinfo=timezone.utc)
DEADLINE = START+timedelta(hours=10)
TRAIN_CUTOFF = START+timedelta(hours=6,minutes=30)
DEV_CUTOFF = START+timedelta(hours=8)
FINAL_CUTOFF = START+timedelta(hours=9,minutes=15)
DEVELOPMENT_MAP_GRID = tuple(range(24,161,8))
FINAL_MAP_GRID = tuple(range(64,513,16))
SAFETY_FACTOR = .8
DEVELOPMENT_OVERHEAD_SECONDS = 600
FINAL_OVERHEAD_SECONDS = 600


def conservative_rate(measurements):
    """Use complete original+all-audit wall time, never callback/kernel-only FPS."""
    if type(measurements) not in (list,tuple) or not measurements:
        raise ValueError('Measured complete-pipeline batches are required')
    rates=[]
    for row in measurements:
        if type(row) is not dict or set(row)!={'games','wall_seconds','full_actor_audits','both_referees'}:
            raise ValueError('Exact complete-pipeline timing record required')
        count,seconds=row['games'],row['wall_seconds']
        if (type(count) is not int or count<=0 or type(seconds) not in (int,float)
                or not math.isfinite(seconds) or seconds<=0
                or type(row['full_actor_audits']) is not int or row['full_actor_audits']!=count
                or row['both_referees'] is not True):
            raise ValueError('Incomplete, nonfinite or kernel-only throughput cannot set the budget')
        rate=count/seconds
        if not math.isfinite(rate) or rate<=0:
            raise ValueError('Computed complete-pipeline throughput must be finite and positive')
        rates.append(rate)
    return min(rates)*SAFETY_FACTOR


def _largest(grid,seconds,rate,games_per_map):
    available=[maps for maps in grid if maps*games_per_map/rate<=seconds]
    if not available:
        raise ValueError('Even the minimum complete validation panel does not fit; use the prequalified fallback')
    return max(available)


def heldout_budget(measurements):
    rate=conservative_rate(measurements)
    dev_maps=_largest(DEVELOPMENT_MAP_GRID,(DEV_CUTOFF-TRAIN_CUTOFF).total_seconds()-DEVELOPMENT_OVERHEAD_SECONDS,rate,8*4*16)
    final_maps=_largest(FINAL_MAP_GRID,(FINAL_CUTOFF-DEV_CUTOFF).total_seconds()-FINAL_OVERHEAD_SECONDS,rate,2*4*16)
    return dict(format='deadline-volume-from-timing/1',start_utc=START.isoformat(),deadline_utc=DEADLINE.isoformat(),
        training_cutoff_utc=TRAIN_CUTOFF.isoformat(),development_cutoff_utc=DEV_CUTOFF.isoformat(),
        final_cutoff_utc=FINAL_CUTOFF.isoformat(),packaging_reserved_seconds=2700,
        conservative_games_per_second=rate,safety_factor=SAFETY_FACTOR,
        development_setup_admission_analysis_reserved_seconds=DEVELOPMENT_OVERHEAD_SECONDS,
        final_setup_admission_analysis_reserved_seconds=FINAL_OVERHEAD_SECONDS,
        development_maps=dev_maps,development_games=dev_maps*8*4*16,
        final_maps=final_maps,final_games=final_maps*2*4*16,
        selection='Volume from complete-pipeline timing only; no score or confidence interval input.',
        source_qualification_required=True,heldout_outcomes_consumed=False,new_game_credit=0)


def may_start_generation(now,measurements,games=8192,coaching_and_setup_seconds=0):
    if not isinstance(now,datetime) or now.tzinfo is None or now.utcoffset()!=timedelta(0):
        raise ValueError('An explicit current UTC timestamp is required')
    if (type(games) is not int or games<=0
            or type(coaching_and_setup_seconds) not in (int,float)
            or not math.isfinite(coaching_and_setup_seconds) or coaching_and_setup_seconds<0):
        raise ValueError('A complete generation and its honest setup/coaching reserve are required')
    duration=games/conservative_rate(measurements)+coaching_and_setup_seconds
    return now+timedelta(seconds=duration)<=TRAIN_CUTOFF
