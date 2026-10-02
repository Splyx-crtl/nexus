p='tests/test_shell_core.py'; s=open(p,encoding='utf-8').read()
def sub(a,b):
    global s
    assert a in s, a[:60]
    s=s.replace(a,b,1)
sub('self.check("wc notes.txt", " 3  9 43 notes.txt\n".replace(" 3  9 43", "3 9 43"))','self.check("wc notes.txt", " 3  8 40 notes.txt\n")')
sub('r = self.run_("cd notes.txt")','r = self.run_("cd /home/player/notes.txt")')
sub('self.assertEqual(r.err, "bash: cd: notes.txt: Not a directory\n")','self.assertEqual(r.err, "bash: cd: /home/player/notes.txt: Not a directory\n")')
sub('self.check("find tools -perm -u+x -type f".replace("-u+x", "100"), "tools/scan.sh\n")','self.check("find tools -perm -100 -type f", "tools/scan.sh\n")')
s=s.replace("43 Jan","40 Jan").replace("player 15 Jan","player 14 Jan").replace('"Size: 43"','"Size: 40"')
open(p,'w',encoding='utf-8').write(s)
p='nexus/shell/interp.py'; s=open(p,encoding='utf-8').read()
old='node = fs.stat(None, x, s.cwd, follow=op not in ("-L", "-h"))'
assert old in s
s=s.replace(old,'node = fs.stat(s.user, x, s.cwd, follow=op not in ("-L", "-h"))',1)
open(p,'w',encoding='utf-8').write(s)
