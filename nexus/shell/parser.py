"""bash parser: command lines and small scripts -> syntax tree.

Supports quoting (' " \\), $var ${var} ${var:-default} $? $$ $# $@ $* $1.., $(cmd) `cmd` $((arith)), pipes, && || ; & newlines,
redirections (> >> < 2> 2>> 2>&1 &>), assignments (VAR=x cmd), and the compound commands if/elif/else/fi, for/while/until, case, { }, ( ) and
function definitions. Expansion itself happens in interp.py.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field


class ParseError(Exception):
    """Message in bash's own wording, e.g. "syntax error near unexpected token `fi'"."""


# ------------------------------------------------------------------------------ syntax tree
@dataclass
class Part:
    kind: str          # lit | var | cmd | arith
    text: str
    quote: str = "none"        # none | single | double


@dataclass
class Word:
    parts: list[Part]

    @property
    def literal(self) -> str | None:
        """The text if the word is a plain unquoted literal (used to spot keywords), else None."""
        if len(self.parts) == 1 and self.parts[0].kind == "lit" and self.parts[0].quote == "none":
            return self.parts[0].text
        return None

    def raw(self) -> str:
        return "".join(p.text if p.kind == "lit" else ("$" + p.text) for p in self.parts)


@dataclass
class Redirect:
    fd: int            # 0, 1, 2 (or -1 for &>)
    op: str            # > >> < >&
    target: Word


@dataclass
class Simple:
    assigns: list[tuple[str, Word]] = field(default_factory=list)
    words: list[Word] = field(default_factory=list)
    redirects: list[Redirect] = field(default_factory=list)


@dataclass
class Pipeline:
    commands: list
    negate: bool = False


@dataclass
class AndOr:
    first: Pipeline
    rest: list[tuple[str, Pipeline]] = field(default_factory=list)


@dataclass
class Seq:
    items: list[tuple[AndOr, bool]] = field(default_factory=list)       # (command list item, run in background)


@dataclass
class If:
    branches: list[tuple[Seq, Seq]]
    otherwise: Seq | None = None


@dataclass
class For:
    var: str
    words: list[Word] | None          # None = "$@"
    body: Seq


@dataclass
class While:
    cond: Seq
    body: Seq
    until: bool = False


@dataclass
class Case:
    word: Word
    clauses: list[tuple[list[Word], Seq]]


@dataclass
class Group:
    body: Seq
    subshell: bool = False
    redirects: list[Redirect] = field(default_factory=list)


@dataclass
class FuncDef:
    name: str
    body: object


RESERVED = {"if", "then", "elif", "else", "fi", "for", "in", "do", "done", "while", "until", "case", "esac", "function", "{", "}", "!"}
OPERATORS = ["&>>", "2>>", "2>&", ">>", "&>", "2>", ">&", "<<", "&&", "||", ";;", "|", ";", "&", "(", ")", ">", "<"]
NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


# ------------------------------------------------------------------------------ tokenizer
class Tok:
    __slots__ = ("kind", "value", "word")

    def __init__(self, kind: str, value: str = "", word: Word | None = None):
        self.kind, self.value, self.word = kind, value, word          # kind: word | op | nl | eof

    def __repr__(self) -> str:
        return f"Tok({self.kind},{self.value!r})"


def _read_balanced(src: str, i: int, open_c: str, close_c: str) -> tuple[str, int]:
    """src[i] is the character after the opener. Returns (inner text, index after the closer)."""
    depth, j = 1, i
    while j < len(src):
        c = src[j]
        if c == "\\":
            j += 2
            continue
        if c in "'\"":
            end = src.find(c, j + 1)
            if end < 0:
                raise ParseError(f"unexpected EOF while looking for matching `{c}'")
            j = end + 1
            continue
        if c == open_c:
            depth += 1
        elif c == close_c:
            depth -= 1
            if depth == 0:
                return src[i:j], j + 1
        j += 1
    raise ParseError(f"unexpected EOF while looking for matching `{open_c}'")


def _expansion(src: str, i: int, quote: str) -> tuple[Part | None, int]:
    """src[i] == '$'. Returns (part, next index). A lone '$' becomes a literal."""
    n = len(src)
    if i + 1 >= n:
        return Part("lit", "$", quote), i + 1
    nxt = src[i + 1]
    if nxt == "(":
        if src[i + 2:i + 3] == "(":
            inner, end = _read_balanced(src, i + 3, "(", ")")
            if src[end:end + 1] == ")":
                return Part("arith", inner, quote), end + 1
        inner, end = _read_balanced(src, i + 2, "(", ")")
        return Part("cmd", inner, quote), end
    if nxt == "{":
        inner, end = _read_balanced(src, i + 2, "{", "}")
        return Part("var", "{" + inner + "}", quote), end
    m = NAME.match(src, i + 1)
    if m:
        return Part("var", m.group(0), quote), m.end()
    if nxt in "?$#@*!0123456789-":
        return Part("var", nxt, quote), i + 2
    return Part("lit", "$", quote), i + 1


def _tokenize(src: str) -> list[Tok]:
    toks: list[Tok] = []
    i, n = 0, len(src)
    while i < n:
        c = src[i]
        if c in " \t":
            i += 1
            continue
        if c == "\n":
            toks.append(Tok("nl"))
            i += 1
            continue
        if c == "\\" and src[i + 1:i + 2] == "\n":
            i += 2
            continue
        if c == "#":
            while i < n and src[i] != "\n":
                i += 1
            continue
        # redirection with a leading file descriptor, e.g. 2>file or 1>&2 (digit directly followed by > or <)
        matched = None
        for op in OPERATORS:
            if src.startswith(op, i):
                matched = op
                break
        if matched is None and c.isdigit() and src[i + 1:i + 2] in (">", "<"):
            matched = None
        if matched:
            if matched == "<<":
                raise ParseError("here-documents are not supported in this shell")
            toks.append(Tok("op", matched))
            i += len(matched)
            continue
        if c.isdigit() and src[i + 1:i + 2] == ">" and (i == 0 or src[i - 1] in " \t\n;|&("):
            op = ">>" if src[i + 2:i + 3] == ">" else (">&" if src[i + 2:i + 3] == "&" else ">")
            toks.append(Tok("op", c + op))
            i += 2 + (len(op) - 1)
            continue
        word, i = _read_word(src, i)
        toks.append(Tok("word", word.raw(), word))
    toks.append(Tok("eof"))
    return toks


def _read_word(src: str, i: int) -> tuple[Word, int]:
    parts: list[Part] = []
    buf: list[str] = []
    n = len(src)

    def flush(quote: str = "none") -> None:
        if buf:
            parts.append(Part("lit", "".join(buf), quote))
            buf.clear()

    while i < n:
        c = src[i]
        if c in " \t\n":
            break
        if c in "|&;()<>" and True:
            break
        if c == "\\":
            if i + 1 < n:
                buf.append(src[i + 1])
                flush("single")                           # an escaped character is literal: it must not be glob/word-split
                i += 2
                continue
            i += 1
            continue
        if c == "'":
            flush()
            end = src.find("'", i + 1)
            if end < 0:
                raise ParseError("unexpected EOF while looking for matching `''")
            parts.append(Part("lit", src[i + 1:end], "single"))
            i = end + 1
            continue
        if c == '"':
            flush()
            i += 1
            dq: list[str] = []
            closed = False
            while i < n:
                ch = src[i]
                if ch == '"':
                    closed = True
                    i += 1
                    break
                if ch == "\\" and i + 1 < n and src[i + 1] in '$`"\\\n':
                    if src[i + 1] != "\n":
                        dq.append(src[i + 1])
                    i += 2
                    continue
                if ch == "$":
                    if dq:
                        parts.append(Part("lit", "".join(dq), "double"))
                        dq = []
                    part, i = _expansion(src, i, "double")
                    parts.append(part)
                    continue
                if ch == "`":
                    end = src.find("`", i + 1)
                    if end < 0:
                        raise ParseError("unexpected EOF while looking for matching ``'")
                    if dq:
                        parts.append(Part("lit", "".join(dq), "double"))
                        dq = []
                    parts.append(Part("cmd", src[i + 1:end], "double"))
                    i = end + 1
                    continue
                dq.append(ch)
                i += 1
            if not closed:
                raise ParseError("unexpected EOF while looking for matching `\"'")
            if dq or not parts or parts[-1].quote != "double":
                parts.append(Part("lit", "".join(dq), "double"))
            continue
        if c == "$":
            flush()
            part, i = _expansion(src, i, "none")
            if part.kind == "lit":
                buf.append(part.text)
            else:
                parts.append(part)
            continue
        if c == "`":
            flush()
            end = src.find("`", i + 1)
            if end < 0:
                raise ParseError("unexpected EOF while looking for matching ``'")
            parts.append(Part("cmd", src[i + 1:end], "none"))
            i = end + 1
            continue
        buf.append(c)
        i += 1
    flush()
    return Word(parts), i


# ------------------------------------------------------------------------------ parser
class _Parser:
    def __init__(self, toks: list[Tok]):
        self.toks, self.pos = toks, 0

    @property
    def tok(self) -> Tok:
        return self.toks[self.pos]

    def advance(self) -> Tok:
        t = self.toks[self.pos]
        self.pos += 1
        return t

    def error(self, tok: Tok | None = None) -> ParseError:
        tok = tok or self.tok
        if tok.kind == "eof":
            return ParseError("syntax error: unexpected end of file")
        shown = "newline" if tok.kind == "nl" else tok.value
        return ParseError(f"syntax error near unexpected token `{shown}'")

    def skip_nl(self) -> None:
        while self.tok.kind == "nl":
            self.pos += 1

    def is_word(self, text: str) -> bool:
        t = self.tok
        return t.kind == "word" and t.word.literal == text

    # list ------------------------------------------------------------------
    def parse_seq(self, stop: tuple[str, ...] = ()) -> Seq:
        seq = Seq()
        self.skip_nl()
        while True:
            t = self.tok
            if t.kind == "eof":
                break
            if t.kind == "word" and t.word.literal in stop:
                break
            if t.kind == "op" and t.value in stop:
                break
            if t.kind == "op" and t.value in (";", ";;"):
                if t.value == ";;" and ";;" in stop:
                    break
                raise self.error()
            item = self.parse_and_or()
            background = False
            if self.tok.kind == "op" and self.tok.value == "&":
                background = True
                self.advance()
            elif self.tok.kind == "op" and self.tok.value == ";":
                self.advance()
            elif self.tok.kind == "nl":
                pass
            seq.items.append((item, background))
            self.skip_nl()
            while self.tok.kind == "op" and self.tok.value == ";":
                self.advance()
                self.skip_nl()
        return seq

    def parse_and_or(self) -> AndOr:
        first = self.parse_pipeline()
        rest: list[tuple[str, Pipeline]] = []
        while self.tok.kind == "op" and self.tok.value in ("&&", "||"):
            op = self.advance().value
            self.skip_nl()
            rest.append((op, self.parse_pipeline()))
        return AndOr(first, rest)

    def parse_pipeline(self) -> Pipeline:
        negate = False
        if self.is_word("!"):
            self.advance()
            negate = True
        commands = [self.parse_command()]
        while self.tok.kind == "op" and self.tok.value == "|":
            self.advance()
            self.skip_nl()
            commands.append(self.parse_command())
        return Pipeline(commands, negate)

    # commands -----------------------------------------------------------------
    def parse_command(self):
        t = self.tok
        if t.kind == "word":
            lit = t.word.literal
            if lit == "if":
                return self.parse_if()
            if lit == "for":
                return self.parse_for()
            if lit in ("while", "until"):
                return self.parse_while()
            if lit == "case":
                return self.parse_case()
            if lit == "{":
                self.advance()
                body = self.parse_seq(("}",))
                if not self.is_word("}"):
                    raise self.error()
                self.advance()
                return Group(body, False, self.parse_redirects())
            if lit == "function":
                self.advance()
                if self.tok.kind != "word":
                    raise self.error()
                name = self.advance().value
                if self.tok.kind == "op" and self.tok.value == "(":
                    self.advance()
                    if not (self.tok.kind == "op" and self.tok.value == ")"):
                        raise self.error()
                    self.advance()
                self.skip_nl()
                return FuncDef(name, self.parse_command())
            if lit in RESERVED and lit not in ("!",):
                raise self.error()
            # name() { ... }
            nxt = self.toks[self.pos + 1]
            if nxt.kind == "op" and nxt.value == "(" and self.toks[self.pos + 2].kind == "op" and self.toks[self.pos + 2].value == ")" and NAME.fullmatch(t.value):
                self.pos += 3
                self.skip_nl()
                return FuncDef(t.value, self.parse_command())
        if t.kind == "op" and t.value == "(":
            self.advance()
            body = self.parse_seq((")",))
            if not (self.tok.kind == "op" and self.tok.value == ")"):
                raise self.error()
            self.advance()
            return Group(body, True, self.parse_redirects())
        return self.parse_simple()

    def parse_redirects(self) -> list[Redirect]:
        out: list[Redirect] = []
        while self.tok.kind == "op" and self.tok.value.lstrip("012&") in (">", ">>", "<", ">&", ""):
            if self.tok.value in ("&&", "|", "||", ";", "&", "(", ")", ";;"):
                break
            r = self.parse_redirect()
            if r is None:
                break
            out.append(r)
        return out

    def parse_redirect(self) -> Redirect | None:
        op = self.tok.value
        m = re.fullmatch(r"([0-9]?)(&?)(>>|>&|>|<)", op) or re.fullmatch(r"(&)()(>>|>)", op)
        if not m:
            return None
        self.advance()
        if self.tok.kind != "word":
            raise self.error()
        target = self.advance().word
        if op.startswith("&>"):
            return Redirect(-1, ">>" if op == "&>>" else ">", target)
        fd = int(m.group(1)) if m.group(1).isdigit() else (0 if m.group(3) == "<" else 1)
        return Redirect(fd, m.group(3), target)

    def parse_simple(self) -> Simple:
        cmd = Simple()
        while True:
            t = self.tok
            if t.kind == "word":
                lit = t.value
                if not cmd.words and "=" in lit and NAME.fullmatch(lit.split("=", 1)[0]) and t.word.parts and t.word.parts[0].kind == "lit" and t.word.parts[0].quote == "none" \
                        and t.word.parts[0].text.startswith(lit.split("=", 1)[0] + "="):
                    name = lit.split("=", 1)[0]
                    first = t.word.parts[0]
                    rest = [Part("lit", first.text[len(name) + 1:], "none")] + t.word.parts[1:]
                    cmd.assigns.append((name, Word([p for p in rest if p.text or p.kind != "lit"])))
                    self.advance()
                    continue
                cmd.words.append(self.advance().word)
                continue
            if t.kind == "op" and re.fullmatch(r"([0-9]?)(&?)(>>|>&|>|<)|&>>?", t.value):
                r = self.parse_redirect()
                if r is None:
                    break
                cmd.redirects.append(r)
                continue
            break
        if not cmd.words and not cmd.assigns and not cmd.redirects:
            raise self.error()
        return cmd

    def parse_if(self) -> If:
        self.advance()
        branches = []
        cond = self.parse_seq(("then",))
        self.expect("then")
        body = self.parse_seq(("elif", "else", "fi"))
        branches.append((cond, body))
        otherwise = None
        while True:
            if self.is_word("elif"):
                self.advance()
                cond = self.parse_seq(("then",))
                self.expect("then")
                branches.append((cond, self.parse_seq(("elif", "else", "fi"))))
            elif self.is_word("else"):
                self.advance()
                otherwise = self.parse_seq(("fi",))
            else:
                break
        self.expect("fi")
        return If(branches, otherwise)

    def expect(self, word: str) -> None:
        if not self.is_word(word):
            raise ParseError(f"syntax error: expected `{word}'" if self.tok.kind != "eof" else f"syntax error: unexpected end of file (expected `{word}')")
        self.advance()

    def parse_for(self) -> For:
        self.advance()
        if self.tok.kind != "word":
            raise self.error()
        var = self.advance().value
        if not NAME.fullmatch(var):
            raise ParseError(f"`{var}': not a valid identifier")
        self.skip_nl()
        words = None
        if self.is_word("in"):
            self.advance()
            words = []
            while self.tok.kind == "word" and self.tok.word.literal not in ("do",):
                words.append(self.advance().word)
            while self.tok.kind == "op" and self.tok.value == ";" or self.tok.kind == "nl":
                self.advance()
        else:
            while self.tok.kind == "op" and self.tok.value == ";" or self.tok.kind == "nl":
                self.advance()
        self.expect("do")
        body = self.parse_seq(("done",))
        self.expect("done")
        return For(var, words, body)

    def parse_while(self) -> While:
        until = self.advance().word.literal == "until"
        cond = self.parse_seq(("do",))
        self.expect("do")
        body = self.parse_seq(("done",))
        self.expect("done")
        return While(cond, body, until)

    def parse_case(self) -> Case:
        self.advance()
        if self.tok.kind != "word":
            raise self.error()
        word = self.advance().word
        self.skip_nl()
        self.expect("in")
        self.skip_nl()
        clauses = []
        while not self.is_word("esac"):
            if self.tok.kind == "eof":
                raise self.error()
            if self.tok.kind == "op" and self.tok.value == "(":
                self.advance()
            patterns = []
            while True:
                if self.tok.kind != "word":
                    raise self.error()
                patterns.append(self.advance().word)
                if self.tok.kind == "op" and self.tok.value == "|":
                    self.advance()
                    continue
                break
            if not (self.tok.kind == "op" and self.tok.value == ")"):
                raise self.error()
            self.advance()
            body = self.parse_seq((";;", "esac"))
            if self.tok.kind == "op" and self.tok.value == ";;":
                self.advance()
            self.skip_nl()
            clauses.append((patterns, body))
        self.advance()
        return Case(word, clauses)


def parse(src: str) -> Seq:
    """Parse a command line or script. Raises ParseError with bash's wording."""
    parser = _Parser(_tokenize(src))
    seq = parser.parse_seq()
    if parser.tok.kind != "eof":
        raise parser.error()
    return seq
