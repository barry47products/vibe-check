# Vibe Check v2 — Discover (OCS Code node). Start -> Resolve -> [Discover] -> Fetch -> Draft -> End.
# Finalises vc_repos for Fetch. Only acts in discovery mode (no contexts configured); otherwise
# passes through (Resolve already set vc_repos from contexts, or it's a manage/no_context turn).
# Repo selection, in order:
#   1. exact repo name in the message  -> just that repo (most specific wins)
#   2. fuzzy token match on a repo name -> those repos
#   3. activity ranking: search/commits by the author in the window, UNIONed with repos pushed in
#      the window (catches today's not-yet-indexed work), ordered by commit count then recency.
# Budget: <= 2 calls (1 repo list + 1 commit search). OCS sandbox: one main; no enumerate/zip/map.
# ruff: noqa: F821
def main(input, **kwargs):
    author_handle = "barry47products"
    auth_provider = "github-vibe-check"
    accept = {"Accept": "application/vnd.github+json"}
    search_accept = {"Accept": "application/vnd.github.cloak-preview+json"}
    top_n = 5

    if (get_temp_state_key("vc_mode") or "checkin") != "checkin":
        return input or ""
    if not get_temp_state_key("vc_discover"):
        return input or ""

    msg = get_temp_state_key("vc_message") or (input or "")
    since_date = get_temp_state_key("vc_since_date") or ""

    listing = http.get("https://api.github.com/user/repos",
                       params={"sort": "pushed", "direction": "desc", "per_page": 100,
                               "affiliation": "owner,collaborator,organization_member"},
                       headers=accept, auth=auth_provider, timeout=15)
    catalog = []
    if listing["is_success"]:
        for r in (listing["json"] or []):
            full = r.get("full_name", "") or ""
            if full:
                catalog.append({"full": full, "tail": full.split("/")[-1].lower(),
                                "pushed": (r.get("pushed_at", "") or "")[:10]})

    stop = ("vibe", "check", "vibecheck", "give", "show", "what", "about", "last", "this",
            "past", "week", "weeks", "weekly", "month", "months", "day", "days", "yesterday",
            "fortnight", "the", "for", "and", "since", "over", "from", "couple", "few")
    words = []
    for w in msg.lower().replace("-", " ").replace("_", " ").replace("/", " ").replace(".", " ").split():
        if w not in stop and not w.isdigit():
            words.append(w)
    norm = "-".join(words)

    tail_of = {}
    for entry in catalog:
        tail_of[entry["full"]] = entry["tail"]

    exact = []
    fuzzy = []
    for entry in catalog:
        tail = entry["tail"]
        if len(tail) >= 4 and tail in norm:
            exact.append(entry["full"])
        else:
            hit = False
            for p in tail.replace("-", " ").replace("_", " ").split():
                if len(p) >= 4 and p in words:
                    hit = True
            if hit:
                fuzzy.append(entry["full"])

    # Keep only the most specific exact matches (drop a tail contained in a longer matched tail).
    specific = []
    for a in exact:
        contained = False
        for b in exact:
            if a != b and tail_of[a] in tail_of[b]:
                contained = True
        if not contained:
            specific.append(a)

    if specific:
        chosen = specific[:top_n]
    elif fuzzy:
        chosen = fuzzy[:top_n]
    else:
        counts = {}
        if since_date:
            si = http.get("https://api.github.com/search/commits",
                          params={"q": "author:" + author_handle + " author-date:>=" + since_date, "per_page": 100},
                          headers=search_accept, auth=auth_provider, timeout=20)
            if si["is_success"]:
                for it in ((si["json"] or {}).get("items", []) or []):
                    repo = it.get("repository", {}) or {}
                    full = repo.get("full_name", "") or ""
                    if full:
                        counts[full] = counts.get(full, 0) + 1
        pushed_of = {}
        for entry in catalog:
            pushed_of[entry["full"]] = entry["pushed"]
        keyed = []
        for full in counts:
            keyed.append((counts[full], pushed_of.get(full, ""), full))
        for entry in catalog:
            if entry["pushed"] and since_date and entry["pushed"] >= since_date and entry["full"] not in counts:
                keyed.append((0, entry["pushed"], entry["full"]))
        # Manual top-N by (commit count, push recency) — avoids relying on list.sort in the sandbox.
        chosen = []
        guard = 0
        while len(chosen) < top_n and guard < 500:
            guard = guard + 1
            best = None
            for item in keyed:
                if item[2] in chosen:
                    continue
                if best is None or item > best:
                    best = item
            if best is None:
                break
            chosen.append(best[2])

    set_temp_state_key("vc_repos", chosen)
    set_temp_state_key("vc_author", author_handle)
    return input or ""
