"""Narration sentences parsed from script.md (single source of truth): CHAPTERS {n: (title, [sentences])} and
PARAGRAPH_ENDS {n: {k, ...}} (sentence k is followed by a paragraph break)."""
import re
from pathlib import Path

_SPLIT = re.compile(r"(?<=[.?!…])\s+(?=[A-ZÀ-Ỹ\"“])")


def parse(path=Path(__file__).resolve().parent / "script.md"):
    text = path.read_text().split("## Lời đọc", 1)[1].split("\n## ", 1)[0].replace("\n---", "")
    chapters, ends = {}, {}
    for block in re.split(r"^### ", text, flags=re.M)[1:]:
        head, *body = block.strip().split("\n")
        n, title = head.split(" · ", 1)
        n = int(n)
        sents, pe = [], set()
        for para in "\n".join(body).split("\n\n"):
            para = " ".join(para.split())
            if not para or para.startswith(">"):
                continue
            sents += [s for s in _SPLIT.split(para) if s]
            pe.add(len(sents) - 1)
        chapters[n] = (re.sub(r"\s*\(.*\)$", "", title), sents)
        ends[n] = pe - {len(sents) - 1}
    return chapters, ends


CHAPTERS, PARAGRAPH_ENDS = parse()

if __name__ == "__main__":
    for n, (title, ss) in CHAPTERS.items():
        print(f"== {n} {title}")
        for k, s in enumerate(ss):
            print(f"  {k:2d}{'¶' if k in PARAGRAPH_ENDS[n] else ' '} {s}")
