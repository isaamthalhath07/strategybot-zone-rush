"""Opponent fields used for measurement. Names resolve through sim.resolve()."""
# Strong, architecturally distinct bots from the project's history. DEV is used while
# designing; nothing in HOLDOUT_* may be looked at until a candidate is frozen.
ELITE = ['a_branch_1dca0c916af4_1dca0c', 'a_novel_b_racer', 'v2_bot_191059b37141',
         'a_research_correctness_ae1594', 'a_bot_720e5a', 't_ultimate', 'a_novel_b_blocker',
         'a_transfer_fixed_fe03b8', 'a_novel_b_feint', 'cur_e8', 'a_bot_cefe2f', 'a_novel_c_bloomer',
         'a_novel_d_shieldmaster', 'a_pr10_novel_v9', 'a_user_family_dfc547', 'a_novel_c_voronoi',
         'legacy:pro_tuned']
MID = ['n_junction_keeper_2', 'n_junction_keeper_0', 'a_action_beam_f99554', 'a_tactical_2388ad',
       'a_economic_34bdf1', 'a_novel_d_titfortat', 'n_late_flipper_0', 'a_novel_a_paranoid',
       'a_planner_beam_e7f4fd', 'a_opp_adaptive_01_e23de3', 'n_rental_horizon_4', 'a_novel_a_rhea',
       'n_space_split_3', 'a_novel_d_antileader', 'a_incumbent_bbff91', 'legacy:ai_centre',
       'legacy:ai_hawk', 'legacy:ai_homefort', 'legacy:ai_cheapraid', 'legacy:spine']
WEAK = ['a_opp_farmer_04_0db330', 'a_opp_farmer_03_885b73', 'legacy:ai_elo', 'legacy:pro',
        'legacy:camper', 'a_opp_shield_03_42e759', 'a_opp_farmer_02_ab39cd', 'a_opp_raider_04_b05ff3',
        'legacy:ai_route', 'legacy:ai_marginal', 'legacy:greedyshield', 'legacy:pacifist',
        'legacy:turtle', 'legacy:cdraider', 'legacy:greedy', 'a_opp_adaptive_02_2a9fa5',
        'a_opp_farmer_01_b2a28f', 'legacy:raider', 'legacy:baiter', 'a_opp_naive_01_216447',
        'legacy:centre', 'legacy:hunter', 'a_opp_naive_03_6af698', 'a_opp_raider_03_a6c0c5',
        'a_opp_raider_01_8eac97', 'a_opp_raider_02_19f1b4']

# Split drawn once with random.Random(20261110) before any new bot was designed.
HOLDOUT_ELITE = ['a_bot_720e5a', 'a_novel_b_feint', 'a_novel_c_bloomer', 'a_novel_d_shieldmaster', 'v2_bot_191059b37141']
HOLDOUT_MID = ['a_novel_a_paranoid', 'a_novel_a_rhea', 'a_novel_d_titfortat', 'legacy:ai_cheapraid', 'n_rental_horizon_4', 'n_space_split_3']
HOLDOUT_WEAK = ['a_opp_raider_01_8eac97', 'a_opp_raider_03_a6c0c5', 'legacy:baiter', 'legacy:camper', 'legacy:greedyshield', 'legacy:pacifist', 'legacy:raider', 'legacy:turtle']
DEV_ELITE = ['a_branch_1dca0c916af4_1dca0c', 'a_novel_b_racer', 'a_research_correctness_ae1594', 't_ultimate', 'a_novel_b_blocker', 'a_transfer_fixed_fe03b8', 'cur_e8', 'a_bot_cefe2f', 'a_pr10_novel_v9', 'a_user_family_dfc547', 'a_novel_c_voronoi', 'legacy:pro_tuned']
DEV_MID = ['n_junction_keeper_2', 'n_junction_keeper_0', 'a_action_beam_f99554', 'a_tactical_2388ad', 'a_economic_34bdf1', 'n_late_flipper_0', 'a_planner_beam_e7f4fd', 'a_opp_adaptive_01_e23de3', 'a_novel_d_antileader', 'a_incumbent_bbff91', 'legacy:ai_centre', 'legacy:ai_hawk', 'legacy:ai_homefort', 'legacy:spine']
DEV_WEAK = ['a_opp_farmer_04_0db330', 'a_opp_farmer_03_885b73', 'legacy:ai_elo', 'legacy:pro', 'a_opp_shield_03_42e759', 'a_opp_farmer_02_ab39cd', 'a_opp_raider_04_b05ff3', 'legacy:ai_route', 'legacy:ai_marginal', 'legacy:cdraider', 'legacy:greedy', 'a_opp_adaptive_02_2a9fa5', 'a_opp_farmer_01_b2a28f', 'a_opp_naive_01_216447', 'legacy:centre', 'legacy:hunter', 'a_opp_naive_03_6af698', 'a_opp_raider_02_19f1b4']
DEV_ALL = DEV_ELITE + DEV_MID + DEV_WEAK
HOLDOUT_ALL = HOLDOUT_ELITE + HOLDOUT_MID + HOLDOUT_WEAK
