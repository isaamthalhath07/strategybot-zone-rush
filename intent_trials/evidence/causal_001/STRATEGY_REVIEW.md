# Posthoc strategy review

The frozen teacher has not demonstrated an improvement over e8. Across the16 registered positions its mean pairwise delta is **−0.03125**, with a descriptive95% interval **[−0.21875,0.15625]**:2 wins,3 losses,11 ties and8 changed recommendations. Keep e8 unchanged. These are consumed TRAIN-position hybrid interventions, not fresh full-match policy evidence. All case numbers below are zero-based. Sources: [results](results.json), [sealed protocol](registration.json) and the `case_XX.json`, `teacher_XX.json`, `public_input_XX.json` entries in [raw evidence](raw_results.zip).

Let the official utility be

\[
U_f(s)=\sum_{j\ne f}\bigl[\mathbf1(s_f>s_j)+\tfrac12\mathbf1(s_f=s_j)\bigr]\in[0,3].
\]

For this realized responding rival instance, let \(Q^C(a)\) be the result of root action \(a\) followed by the declared e8 hybrid continuation \(C\). With baseline action \(B\) and teacher action \(A\), define \(\Delta=Q^C(A)-Q^C(B)\), \(H=\max_aQ^C(a)-Q^C(B)\), and realized root regret \(H-\Delta\). Only cases01/07/15 have positive headroom \(H=1\); the teacher captures07/15 and misses01. Mean headroom is0.1875 and mean regret0.21875. The three losses00/09/13 occur where the baseline already achieves the best tested root rank. Hindsight is an evaluator diagnostic, not an available public policy or global optimum.

1. **Align the evaluated own continuation with the intervention target.** The experiment forces one action and then resumes e8, retaining its planner intent updates while synchronizing accepted-action memory. The teacher instead combines future tree choices with public economic rollouts. Thus, even with perfect estimation,

   \[
   E_{\rm model}[U\mid a,\pi_{\rm tree/economic}]
   \ne E_{\rm model}[U\mid a,C]
   \ne Q^C(a)
   \]

   in general. The first difference is structural; the second also involves the rival model and one realized instance. See [`focal_rollout`/`_search`](../../../intent_search/mcts.py) and [`continuation`](../../experiment.py).

   A **root-only public-e8 evaluator** would use e8 at every own future step after the root. This changes both the continuation target and search design by removing future UCT control. It is a package comparison, not one-factor causal isolation. Changing **only the fallback rollout** to e8 would retain future MCTS subtree control and would not fully match the one-step intervention target. These are distinct proposals.

2. **Separate horizon bias from terminal mistakes and sampling uncertainty.** The leaf evaluates \(U(s_h+kI_h)\), where \(k=\min(12,81-t-h)\). For \(h=6\), turns30/50/65/75 leave45/25/10/0 turns and use tails12/12/10/0. Early values omit future dynamic captures/upgrades and clip static income; turn75 uses exact terminal utility. See [`utility`](../../../intent_search/mcts.py).

   Case00 estimates EAST2.175 versus STAY2.02778, but realized points are2 versus3. Case13 estimates SHIELD1.58696 versus STAY1.54545, but realizes1.5 versus2 **despite reaching the true terminal**. Its actual own suffixes are `STAY,SHIELD,STAY×4` versus `SHIELD,STAY×5`; focal score2597 becomes2595 while rival4 remains2595. Only1/23 chosen-root simulated own suffixes matches the latter sequence. This establishes sequencing sensitivity and describes sampled continuation differences; it does not identify how much loss comes from own policy, rival prediction, inferred state or Monte Carlo variation. Short horizon alone cannot explain13.

   Root action counts are11..24, and all16 searches have zero node-cap hits. Small estimated advantages can be unstable. These adaptive tree returns do not justify naive independent-sample confidence intervals. More simulations can also reinforce model bias. No reachable-cap witness or universal coverage claim follows.

3. **Persistent style does not identify persistent goals.** The joint posterior \(b_t(x,\theta)\) correctly retains correlated physical explanations and persistent style assignments. But the four hypothetical policies recompute actions from the current public board; no latent target, route commitment or plan memory persists. Observationally equivalent explanations cannot be distinguished, and blocked intentions can alias. Concentration on a style is conditional on this policy family, not proof of actual identity, goal or calibration. See [`policy`/`IntentFilter`](../../../opponent_prediction/intent_filter.py). Add no latent-goal system before testing the simpler continuation package.

4. **Preserve the distinction between exploration and confirmation.** These16 deliberately selected TRAIN boundaries are mostly rank-insensitive under the tested interventions. Do not select replacements using realized headroom, favor the winning field, or fit an estimate-gap switching threshold to the eight observed changes. A model-based best response to fixed heuristic rivals is not a four-player equilibrium or robustness guarantee; \(\sum_fU_f=6\), but there is no two-player minimax certificate here.

The next small comparison should preregister **current teacher versus baseline-aligned root-only public-e8 evaluation** on16 new disjoint admitted TRAIN maps, four per field, all at turn75. Fixed public-only boundary selection, exclusions of previously used map orbits and published seeds/caps must precede outcomes. Keep the same joint filter,96 trajectories and six two-referee transitions per trajectory; share public-order random keys across arms. Reconstruct e8 memory exclusively from public history and accepted own actions, using fresh namespaces. Report extra e8 callback/wall-time cost: equal simulated-physics budget is not equal latency.

Score both recommendations against one complete shared set of regenerated responding-controller root alternatives. The primary contrast is paired \(Q^C(A_{\rm aligned})-Q^C(A_{\rm current})\), with the fixed within-field map bootstrap; report each versus baseline and hindsight regret. Terminal roots remove leaf-tail differences, but the package comparison still does not isolate all model and sampling errors. Preserve failures and every case. No current case is rerun or tuned.

Even a favorable result requires an **actual fresh full-match architecture comparison** under legal public inputs, actor deadlines, complete referee/callback checks and the campaign's existing admission/heldout/promotion rules. Repeated teacher control, a distilled single-file policy and the one-step hybrid are different architectures and need their own fixed definitions. This review creates no runtime, new outcome, primary-game credit, completed per-game BMCTS credit or promotion.
