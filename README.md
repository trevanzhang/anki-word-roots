# Word Roots for Anki

An Anki deck of the Greek and Latin prefixes, roots and suffixes that build English words,
including the ones medicine uses. It's ordered by usefulness: the morphemes inside everyday words
come first, and obscure ones aren't included at all.

**[Download Word_Roots.apkg](https://github.com/jupsh/anki-word-roots/releases/latest/download/Word_Roots.apkg)**,
then in Anki choose **File → Import**.

## What's in it

- **699 morphemes:** 569 roots, 76 prefixes and 54 suffixes (437 Latin, 251 Greek). 231 are
  tagged medical.
- **160 decode words**, half everyday and half medical, for practising taking words apart.
- **77 etymology stories** for the roots with a good one, such as why *muscle* means "little mouse".

Each morpheme is taught through words you already know, with the morpheme highlighted. Decode
cards come after you've met all of their parts.

<table>
  <tr><th scope="col" colspan="2">Morpheme</th></tr>
  <tr><th scope="col">Front</th><th scope="col">Back</th></tr>
  <tr>
    <td><img src="doc/root-front.png" width="380"></td>
    <td><img src="doc/root-back.png" width="380"></td>
  </tr>
</table>

<table>
  <tr><th scope="col" colspan="2">Morpheme, with a story</th></tr>
  <tr><th scope="col">Front</th><th scope="col">Back</th></tr>
  <tr>
    <td><img src="doc/story-front.png" width="380"></td>
    <td><img src="doc/story-back.png" width="380"></td>
  </tr>
</table>

<table>
  <tr><th scope="col" colspan="2">Decode</th></tr>
  <tr><th scope="col">Front</th><th scope="col">Back</th></tr>
  <tr>
    <td><img src="doc/decode-front.png" width="380"></td>
    <td><img src="doc/decode-back.png" width="380"></td>
  </tr>
</table>

### Custom study

Tags let you build [filtered decks](https://docs.ankiweb.net/filtered-decks.html) or suspend what
you don't need:

- `-tag:WR::Medical` to skip the medical vocabulary;
- `tag:WR::Medical` to focus on it, e.g. for anatomy or nursing courses;
- `tag:WR::Prefix or tag:WR::Suffix` for the affixes only;
- `tag:WR::Greek` or `tag:WR::Latin` for one language;
- `tag:WR::Decode` for the decode cards only.

## Where the content comes from

The morphemes started from Wikipedia's *List of Greek and Latin roots in English* and *List of
medical roots, suffixes and prefixes*. Entries were kept only if their example words are common
in English, measured with [wordfreq](https://github.com/rspeer/wordfreq). Then every entry was
reviewed by hand: wrong meanings and false etymologies fixed, duplicates merged, better example
words chosen, and missing suffixes, prefixes and medical roots added. The stories and decode
words were written for this deck.

## Building it yourself

Needs [uv](https://docs.astral.sh/uv/).

```sh
uv run python word_roots/build.py                 # writes dist/Word_Roots.apkg
uv run python word_roots/build.py --html out.html # plus an HTML preview of every note
```

The content is three CSV files in `word_roots/data/`: `morphemes.csv` (in study order),
`stories.csv` and `decode.csv`. `tools/import_wikipedia.py` generated the first version of
`morphemes.csv`. It has been hand-edited since, so edit the CSV directly. Note GUIDs come from each
morpheme's `id` and each decode word, so keep ids stable.

## Contributing

Spotted a mistake? [Open an issue](https://github.com/jupsh/anki-word-roots/issues). To change
the deck yourself, see [CONTRIBUTING.md](CONTRIBUTING.md).

## License

[CC BY-SA 4.0](LICENSE.md), because the source data comes from Wikipedia. The build code is
public domain.
