"""
One registry, shared by every measurement script.

The realism problem with the original zoo was not that the bots were bad, it was
that they were all *mine*. The field that actually decides Round 1 is made of
other teams' bots, built the same way this one was -- so the dangerous entrants
are near-peers, not archetypes. This registry therefore has three tiers:

  peers     my own tuned versions and the counter-bots bred against them. The
            closest available model of "another team also used an agentic AI".
  designs   serious hand-written designs (aifield), each getting some part of
            the rulebook right and some part wrong, which is what real entries
            look like.
  weak      the original zoo and the held-out archetypes, because a real field
            of twenty-odd teams always contains several that barely work.

TIERS lets a script ask for a realistic mix or a deliberately brutal one.
"""
import arena


def registry(peers=True, designs=True, weak=True, holdouts=True, main=None):
    reg = arena.Registry()
    if designs:
        import aifield
        for c in aifield.AIFIELD:
            reg.add(c.name, (lambda k: (lambda s: k(s)))(c))
    if weak:
        import zoo
        for c in zoo.ZOO:
            if c.name in ("stay", "random"):
                continue                       # keep the floor, not the carpet
            reg.add(c.name, (lambda k: (lambda s: k(s)))(c))
    if holdouts:
        import holdout
        for c in holdout.HOLDOUT:
            reg.add(c.name, (lambda k: (lambda s: k(s)))(c))
    if peers:
        import rivals
        for n in rivals.names():
            reg.add(n, rivals.factory(n))
    if main is not None:
        import mybot
        reg.add("main", (lambda p: (lambda s: mybot.Agent(seed=s, params=p)))(main))
    return reg


# The mixes a measurement can be run against. "realistic" is the one that should
# drive decisions; "peer" is the hard case; "legacy" reproduces older numbers.
TIERS = {
    "realistic": ["v3", "v6", "nemesis2", "nemesis3", "ai_marginal", "ai_hawk",
                  "ai_homefort", "ai_cheapraid", "ai_centre", "ai_route",
                  "ai_elo", "spine", "camper", "greedy", "greedyshield",
                  "raider", "baiter", "turtle", "centre", "cdraider",
                  "hunter", "pro", "pro_tuned"],
    "peer": ["v3", "v4", "v6", "nemesis1", "nemesis2", "nemesis3", "ai_hawk",
             "ai_homefort", "spine", "pro", "pro_tuned"],
    # Discriminating but containing NONE of my own snapshots. The peer tier is
    # six-elevenths my own lineage, so "good on peer" partly means "good against
    # my own architecture", which is not the Round 1 field. This is the fix:
    # strong, varied, and all of it written as an opponent rather than as me.
    "strangers": ["pro_tuned", "pro", "spine", "camper", "ai_hawk", "ai_homefort",
                  "ai_marginal", "ai_cheapraid", "turtle", "cdraider", "centre",
                  "hunter", "ai_route", "ai_elo"],
    # Pure-style fields, grouped by what each design does rather than how well
    # it does it. Real games mix styles, so measuring against one style at a time
    # gives the CEILING on what adapting to opponent style could be worth: if
    # the best fixed response is the same against every style, then knowing the
    # style perfectly buys nothing, however good the classifier.
    "style_raiders": ["raider", "cdraider", "ai_cheapraid", "hunter", "ai_hawk",
                      "baiter"],
    "style_passive": ["pacifist", "turtle", "camper", "ai_homefort",
                      "greedyshield"],
    "style_farmers": ["greedy", "spine", "ai_marginal", "ai_route", "ai_centre",
                      "centre", "ai_elo"],
    "designs": [c for c in ("ai_marginal", "ai_cheapraid", "ai_homefort",
                            "ai_centre", "ai_route", "ai_hawk", "ai_elo")],
    "legacy": ["spine", "camper", "greedy_value", "greedy_shield", "raider",
               "baiter", "pacifist"],
}


def tier(name):
    """A named tier, or `only:NAME` for a field of that one opponent, which is
    how to tell which member of a style tier is actually driving a result."""
    if name.startswith("only:"):
        opponent(name.split(":", 1)[1])          # fail now, not mid-measurement
        return [name.split(":", 1)[1]]
    return list(TIERS[name])


def opponent(name):
    """Resolve an opponent name to a zero-arg-plus-seed factory.

    One resolver for every measurement script. There were five near-copies of
    this lookup (measure, tune, tune_rival, audit, diag_loss) and they had
    already drifted: aifield bots were invisible to the tuner, and probot was
    invisible to everything. A name that silently resolves to nothing is the
    kind of mistake that shows up as a quietly weaker field, not as an error.
    """
    import aifield
    import holdout
    import probot
    import zoo

    c = zoo.ZOO_BY_NAME.get(name) or aifield.AIFIELD_BY_NAME.get(name)
    if c is not None:
        return c
    h = dict((x.name, x) for x in holdout.HOLDOUT)
    if name in h:
        return h[name]
    if name == "pro":
        return probot.factory(None, "pro")
    if name.startswith("probot:"):
        # A ProBot weight file by path, e.g. "probot:n6_pro_v7.json", so a freshly
        # bred rival can be measured without first being registered anywhere.
        import json
        path = name.split(":", 1)[1]
        return probot.factory(json.load(open(path)), name)
    if name == "pro_tuned":
        import json
        import os
        p = (json.load(open("pro_params_v1.json"))
             if os.path.exists("pro_params_v1.json") else None)
        return probot.factory(p, "pro_tuned")
    import rivals
    if name in rivals.names():
        return rivals.factory(name)
    raise KeyError("unknown opponent %r" % name)
