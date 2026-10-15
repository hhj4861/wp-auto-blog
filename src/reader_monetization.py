"""Move owned reader ads without reserializing any editorial or provider HTML."""
from dataclasses import dataclass
from html.parser import HTMLParser


@dataclass
class _Element:
    tag: str
    attrs: dict
    start: int
    parent: object
    end: int | None = None


class _Spans(HTMLParser):
    # HTMLParser handles script/style contents as data; their bytes stay untouched.
    VOID = frozenset('area base br col embed hr img input link meta param source track wbr'.split())

    def __init__(self, html):
        super().__init__(convert_charrefs=False)
        self.html = html
        self.lines = [0]
        for index, char in enumerate(html):
            if char == '\n':
                self.lines.append(index + 1)
        self.elements = []
        self.stack = []
        self.feed(html)
        self.close()

    def source_offset(self):
        line, column = self.getpos()
        return self.lines[line - 1] + column

    def handle_starttag(self, tag, attrs):
        element = _Element(tag, dict(attrs), self.source_offset(), self.stack[-1] if self.stack else None)
        self.elements.append(element)
        if tag in self.VOID:
            element.end = element.start + len(self.get_starttag_text())
        else:
            self.stack.append(element)

    def handle_startendtag(self, tag, attrs):
        element = _Element(tag, dict(attrs), self.source_offset(), self.stack[-1] if self.stack else None)
        element.end = element.start + len(self.get_starttag_text())
        self.elements.append(element)

    def handle_endtag(self, tag):
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index].tag == tag:
                self.stack[index].end = self.html.index('>', self.source_offset()) + 1
                del self.stack[index:]
                return


def _reader(spans):
    readers = [node for node in spans.elements
               if 'wpab-menu-reader' in (node.attrs.get('class') or '').split()]
    if (len(readers) != 1 or readers[0].end is None
            or readers[0].attrs.get('data-reader-version') != 'category-menu-v1'):
        raise ValueError('Exactly one closed reader required for ad reflow')
    return readers[0]


def _anchors(spans, article):
    def one(predicate):
        nodes = [node for node in spans.elements if node.parent is article and predicate(node)]
        if len(nodes) != 1 or nodes[0].end is None:
            raise ValueError('Reader summary/panel anchors missing or ambiguous')
        return nodes[0]
    quick = one(lambda node: node.attrs.get('id') == 'quick-answer')
    panels = one(lambda node: 'data-reader-panels' in node.attrs)
    if quick.end > panels.start:
        raise ValueError('Reader summary must precede detail panels')
    return quick, panels


def reflow_reader_ads(html):
    """Keep at most two existing ads visible outside all tab panels.

    Only complete data-monetization=ad blocks move. All other bytes, ad script
    bodies, IDs and slots are preserved. No ad requests are issued here or on tab
    selection. Legacy pages with nested/ambiguous ad ownership fail closed.
    """
    spans = _Spans(html)
    article = _reader(spans)
    ads = [node for node in spans.elements
           if node.attrs.get('data-monetization') == 'ad'
           and article.start < node.start < article.end]
    if not ads:
        return html
    if len(ads) > 2 or any(node.parent is not article or node.end is None for node in ads):
        raise ValueError('Expected at most two closed, direct owned reader ads')
    quick, panels = _anchors(spans, article)
    if any(node.start < quick.end for node in ads):
        raise ValueError('Owned ads must already be outside the summary')
    blocks = [html[node.start:node.end] for node in ads]
    # Remove only our blocks, then calculate anchors again against the remaining bytes.
    for node in reversed(ads):
        html = html[:node.start] + html[node.end:]
    remaining = _Spans(html)
    quick, panels = _anchors(remaining, _reader(remaining))
    if len(blocks) == 2:
        html = html[:panels.end] + blocks[1] + html[panels.end:]
    return html[:quick.end] + blocks[0] + html[quick.end:]
