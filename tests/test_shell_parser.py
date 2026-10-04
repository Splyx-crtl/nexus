"""bash parser: quoting, expansions, pipes, lists, redirections, compound commands and error wording."""
import unittest

from nexus.shell.parser import AndOr, Case, For, FuncDef, Group, If, ParseError, Pipeline, Simple, While, parse


def first(src):
    return parse(src).items[0][0]


def simple(src) -> Simple:
    cmd = first(src).first.commands[0]
    assert isinstance(cmd, Simple), cmd
    return cmd


def words(src):
    return [w.raw() for w in simple(src).words]


class Words(unittest.TestCase):
    def test_plain_and_quotes(self):
        self.assertEqual(words("echo hello   world"), ["echo", "hello", "world"])
        self.assertEqual(words("echo 'a  b' \"c  d\" e\\ f"), ["echo", "a  b", "c  d", "e f"])
        self.assertEqual(words("echo a'b'\"c\"d"), ["echo", "abcd"])

    def test_quote_kinds_are_remembered(self):
        parts = simple("echo 'a'\"b\"c").words[1].parts
        self.assertEqual([(p.text, p.quote) for p in parts], [("a", "single"), ("b", "double"), ("c", "none")])

    def test_expansions(self):
        w = simple('echo $HOME ${USER:-nobody} "$?" $(date) `id` $((1+2)) $1 $#').words
        kinds = [(p.kind, p.text, p.quote) for word in w[1:] for p in word.parts]
        self.assertEqual(kinds, [("var", "HOME", "none"), ("var", "{USER:-nobody}", "none"), ("var", "?", "double"), ("cmd", "date", "none"),
                                 ("cmd", "id", "none"), ("arith", "1+2", "none"), ("var", "1", "none"), ("var", "#", "none")])

    def test_dollar_inside_double_quotes_and_literal_dollar(self):
        w = simple('echo "price: $5 and $HOME/x" $').words
        self.assertEqual([(p.kind, p.text) for p in w[1].parts], [("lit", "price: "), ("var", "5"), ("lit", " and "), ("var", "HOME"), ("lit", "/x")])
        self.assertEqual(w[2].literal, "$")

    def test_nested_command_substitution(self):
        w = simple('echo $(echo $(echo hi) there)').words[1]
        self.assertEqual((w.parts[0].kind, w.parts[0].text), ("cmd", "echo $(echo hi) there"))

    def test_comments(self):
        self.assertEqual(words("echo hi # not this"), ["echo", "hi"])
        self.assertEqual(words("echo 'a # b'"), ["echo", "a # b"])


class Lists(unittest.TestCase):
    def test_pipeline(self):
        p = first("cat f | grep x | wc -l").first
        self.assertIsInstance(p, Pipeline)
        self.assertEqual(len(p.commands), 3)
        self.assertTrue(first("! false").first.negate)

    def test_and_or(self):
        node = first("a && b || c")
        self.assertIsInstance(node, AndOr)
        self.assertEqual([op for op, _ in node.rest], ["&&", "||"])

    def test_sequences_and_background(self):
        seq = parse("a; b & c\nd")
        self.assertEqual([bg for _, bg in seq.items], [False, True, False, False])

    def test_assignments(self):
        s = simple("FOO=bar BAZ='x y' env")
        self.assertEqual([(n, w.raw()) for n, w in s.assigns], [("FOO", "bar"), ("BAZ", "x y")])
        self.assertEqual([w.raw() for w in s.words], ["env"])
        self.assertEqual(simple("X=1").assigns[0][0], "X")
        self.assertEqual(words("echo A=b"), ["echo", "A=b"])                    # not an assignment after the command word


class Redirects(unittest.TestCase):
    def test_redirects(self):
        s = simple("cmd > out 2> err >> log < in")
        self.assertEqual([(r.fd, r.op, r.target.raw()) for r in s.redirects], [(1, ">", "out"), (2, ">", "err"), (1, ">>", "log"), (0, "<", "in")])

    def test_dup_and_both(self):
        s = simple("cmd 2>&1")
        self.assertEqual([(r.fd, r.op, r.target.raw()) for r in s.redirects], [(2, ">&", "1")])
        s = simple("cmd &> all")
        self.assertEqual([(r.fd, r.op) for r in s.redirects], [(-1, ">")])

    def test_redirect_without_spaces_and_between_words(self):
        s = simple("echo hi>out")
        self.assertEqual(([w.raw() for w in s.words], s.redirects[0].target.raw()), (["echo", "hi"], "out"))
        s = simple("echo > out hi")
        self.assertEqual([w.raw() for w in s.words], ["echo", "hi"])

    def test_digits_in_arguments_are_not_redirects(self):
        self.assertEqual(words("echo 2 3 > x"), ["echo", "2", "3"])
        self.assertEqual(words("head -n 20"), ["head", "-n", "20"])


class Compound(unittest.TestCase):
    def test_if(self):
        node = first("if test -f x; then echo yes; elif true; then echo mid; else echo no; fi").first.commands[0]
        self.assertIsInstance(node, If)
        self.assertEqual(len(node.branches), 2)
        self.assertIsNotNone(node.otherwise)

    def test_multiline_if_and_for(self):
        src = "for f in a b c\ndo\n  echo $f\ndone"
        node = first(src).first.commands[0]
        self.assertIsInstance(node, For)
        self.assertEqual([w.raw() for w in node.words], ["a", "b", "c"])
        node = first("for i in 1 2; do echo $i; done").first.commands[0]
        self.assertEqual(node.var, "i")

    def test_while_until_case_group_function(self):
        self.assertIsInstance(first("while true; do break; done").first.commands[0], While)
        self.assertTrue(first("until false; do echo x; done").first.commands[0].until)
        case = first('case $x in a|b) echo ab;; c) echo c;; *) echo other;; esac').first.commands[0]
        self.assertIsInstance(case, Case)
        self.assertEqual(len(case.clauses), 3)
        self.assertEqual(len(case.clauses[0][0]), 2)
        self.assertIsInstance(first("{ echo a; echo b; }").first.commands[0], Group)
        self.assertTrue(first("(cd /tmp; ls)").first.commands[0].subshell)
        fn = first("greet() { echo hi $1; }").first.commands[0]
        self.assertIsInstance(fn, FuncDef)
        self.assertEqual(fn.name, "greet")
        self.assertIsInstance(first("function f { echo x; }").first.commands[0], FuncDef)

    def test_keywords_as_arguments_stay_words(self):
        self.assertEqual(words("echo if then fi done"), ["echo", "if", "then", "fi", "done"])
        self.assertEqual(words('"if" x'), ["if", "x"])


class Errors(unittest.TestCase):
    def check(self, src, fragment):
        with self.assertRaises(ParseError) as cm:
            parse(src)
        self.assertIn(fragment, str(cm.exception))

    def test_messages(self):
        self.check("echo 'oops", "matching `''")
        self.check('echo "oops', 'matching `"\'')
        self.check("if true; then echo x", "unexpected end of file")
        self.check("echo hi |", "syntax error")
        self.check("; ls", "unexpected token `;'")
        self.check("fi", "unexpected token `fi'")
        self.check("echo $(ls", "matching `('")
        self.check("cat <<EOF", "here-documents")
        self.check("for 1x in a; do :; done", "not a valid identifier")


if __name__ == "__main__":
    unittest.main()
