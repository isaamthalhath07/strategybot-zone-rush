# Why the evolved bot may choose side squares

This is a source-based diagnosis plus a captured final position, not a recovered
turn-by-turn transcript. The previous human-play server retained only its latest
state and last resolved turn. The browser's retained requests did not contain
the user's complete match. Earlier moves have not been invented.

The captured completed match `096cd9d0b111475fb71dc5476b20a55b` ended with scores
2287, 2165, 2132, 1622. The human won. Its final board gives the human two of the
four central three-point cells, and seats 2 and 3 one each. Thus the final
position does not establish that every AI ignored the centre; identifying the
specific missed intervention requires the newly recorded turns.

The selected source is research/evolution-2026-11-07, commit 0796039, outputs/bot.py,
raw Git SHA-256 1dca0c916af4ff4ac4c2e90fabe3f3c29c550c5db61663f8a3c2b0efc72f81ca.

## The suspicion has a concrete basis

Its configured depth of two means two of its **own capture/upgrade jobs**, not
two rounds of predicting all four players. It does not assign each opponent a
likely destination, project their routes, or simulate their responses to its
candidate moves. Its second-job ranking reuses rewards computed from the current
board and current rival positions. Enemy territory that may appear before it
arrives is not simulated.

It does account for opponents in narrower ways: occupied cells block paths;
adjacent rivals and priority affect the first step; nearest-rival distance
discounts expected territory retention; observed shields/cooldowns change raid
risk; and observed raid commitment affects defensive shielding. Saying it
ignores opponents altogether would be incorrect.

## Why that produces the behaviour you noticed

1. **Current proximity is treated mainly as danger.** The retention formula is
   `40.67114 + min(5, nearest rival distance) × 3.52153`, capped by remaining
   scoring turns. Moving into the middle shortens its estimated residence there,
   making safer side cells relatively attractive. There is no matching model
   of the long-term income it permits you to acquire by conceding a neutral cell.
2. **It ranks immediate economic rates and short own routes.** A nearby two-point
   cell can pay sooner than a distant three-point centre cell. For an illustrative
   early-game claim, one move plus one stay to a safe two-point cell gives an
   initial rate around 58.3. Five moves plus one stay to a three-point cell near
   a rival gives a rate around 21.5 after its contest penalty. These are examples
   of its formula, not reconstructed values from a particular user turn. The
   continuation bonus can change the final ranking.
3. **It strongly favours upgrades.** Its upgrade multiplier increases from
   1.46008 to 3.3705, with a further 1.11474 fortification premium on nonhome
   upgrades. Completing nearby upgrades can legitimately beat a long centre trip.
4. **It becomes difficult to undo a late concession.** Once you upgrade the
   centre, capture needs three stays. Its raid-risk penalty grows to 8 late in
   the game, so it may farm elsewhere rather than contest your fortified land.

## What would constitute a good correction

Estimate each rival's likely target and completion time from public movement and
work history, then compare profitable farming with contests that prevent a
specific rival's compounding income. A small joint-response lookahead should
update occupancy and ownership as it forecasts. It must use beliefs based on
public history, not the human's already-chosen simultaneous action.

Do not force a centre rush or punish all side farming. That can waste tempo,
invite shields, and help the two uninvolved opponents. Validate an intent model
with paired, fresh matches, different openings, maps and seats, and measure both
placement and execution time. The new recorder now preserves the evidence needed
to determine whether a particular side move was productive or an exploitable
failure to anticipate your plan.
