# Contributing

Thanks for helping! Seen a wrong meaning, a false etymology or a missing root?
[Open an issue](https://github.com/jupsh/anki-word-roots/issues). Pull requests are welcome too.

## Making changes

All content is in `word_roots/data/`:

- **`morphemes.csv`:** one row per morpheme, in study order. `front` holds three familiar words
  with the morpheme in brackets, e.g. `[aud]ience; [aud]io; [aud]it`; `more` holds extra examples
  in the same format. Keep `id` stable: it identifies the note in people's collections.
- **`stories.csv`:** an optional story per morpheme `id`. HTML is allowed.
- **`decode.csv`:** `parts` splits the word into segments, each with the `id` of its morpheme,
  e.g. `peri=peri-around + card=cardi-heart + itis=itis-inflammation`. Leave the id empty for a
  segment that isn't in the deck (`tonsill=`). The segments must spell the whole word.

Build with `uv run python word_roots/build.py --html out.html` and check your change in
`out.html`. The build stops on unknown ids and on example words without a marked morpheme. Every
push and pull request is also built on GitHub.

## Content rules

- **Only real etymology.** Every example word must actually come from the morpheme, not just
  contain its letters (*ballistic* is from Greek *ballein* "throw"; *ball* is not). Stories must be
  well documented; leave out popular myths such as *sincere* "without wax".
- **Familiar examples first.** The front should use words a general reader knows; save rare or
  technical words for `more`.
- **Useful morphemes only.** A morpheme earns its place if it appears in several words people
  actually meet. Medical morphemes count if they appear in common medical vocabulary.
- **Short meanings.** "hear", not "of or pertaining to hearing".

## Versioning and releases

Releases are numbered `x.y`:

- `y` goes up for content changes: new, corrected or removed morphemes, stories or decode words.
- `x` goes up when users would lose progress on upgrade, for example when ids change.

To release:

1. Update the counts in `README.md` if they changed, and commit.
1. Tag the commit and push the tag, e.g. `git tag v1.1 && git push origin v1.1`.
1. GitHub builds the deck and creates a **draft release** with the `.apkg` attached.
1. Write the release notes from a user's point of view (which morphemes, stories and decode words
   changed), then publish the release.
1. Update the deck on [AnkiWeb](https://ankiweb.net/decks/): import the new `.apkg` into Anki,
   sync, then select _Actions_ > _Share_ on the deck, update the description if needed, tick the
   _Copyright_ box and click _Share_.
